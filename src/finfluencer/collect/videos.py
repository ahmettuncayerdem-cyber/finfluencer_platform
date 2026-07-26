"""
finfluencer.collect.videos
===========================

Video enumeration + metadata + census sampling stage.

Consumes the ``channels.parquet`` produced by :mod:`collect.channels`.

Pipeline per analyst
--------------------
1. Enumerate video IDs from the uploads playlist within the observation
   window (newest-first, early-stopping).
2. Fetch metadata for every enumerated video (batched, 50 IDs per call).
3. Apply eligibility rules (Shorts, made-for-kids, promo keywords) —
   handled by the provider.
4. Census-based sampling: if eligible-count > max_videos_per_analyst,
   perform month-stratified systematic random sampling; otherwise keep
   all eligible videos.
5. Persist to ``videos.parquet``.

The month-stratified sampling uses a seed derived deterministically
from ``settings.study.root_seed`` (Methods §3.2.3), so the same corpus
is drawn on every re-run.
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import Settings, VideoRecord
from finfluencer.core.logging import bind_context, clear_context, get_logger
from finfluencer.core.reproducibility import derive_seed
from finfluencer.utils.io import write_parquet
from finfluencer.utils.time import month_key


_log = get_logger(__name__)
_STAGE_NAME = "collect_videos"


def _config_slice(settings: Settings, channels_df: pd.DataFrame) -> dict[str, Any]:
    """Slice of config that affects this stage's output."""
    return {
        "platform": settings.providers.platform,
        "window": {
            "start": settings.study.observation_window.start.isoformat(),
            "end": settings.study.observation_window.end.isoformat(),
        },
        "collection": {
            "max_videos_per_analyst": settings.collection.max_videos_per_analyst,
            "shorts_max_duration_sec": settings.collection.shorts_max_duration_sec,
            "promo_keywords": sorted(settings.collection.promo_keywords),
        },
        "channels": sorted(channels_df["channel_id"].tolist()) if not channels_df.empty else [],
    }


def _month_stratified_sample(
    videos: list[VideoRecord],
    *,
    target_n: int,
    seed: int,
) -> list[VideoRecord]:
    """Month-stratified systematic random sample of size ``target_n``.

    Groups eligible videos by ``month_key(published_at)`` and draws
    proportionally from each month via systematic sampling with a
    seed-derived random start. Preserves temporal balance.
    """
    if len(videos) <= target_n:
        return list(videos)

    rng = np.random.default_rng(seed)
    by_month: dict[str, list[VideoRecord]] = defaultdict(list)
    for v in videos:
        by_month[month_key(v.published_at)].append(v)

    # Proportional allocation per month
    total = len(videos)
    month_keys = sorted(by_month)
    quotas = {
        m: max(1, round(target_n * len(by_month[m]) / total))
        for m in month_keys
    }
    # Adjust so sum == target_n (rounding drift)
    diff = target_n - sum(quotas.values())
    if diff != 0:
        # Distribute residual to the largest months first
        largest = sorted(month_keys, key=lambda m: len(by_month[m]), reverse=True)
        for m in largest:
            if diff == 0:
                break
            if diff > 0:
                quotas[m] += 1
                diff -= 1
            elif quotas[m] > 1:
                quotas[m] -= 1
                diff += 1

    selected: list[VideoRecord] = []
    for m in month_keys:
        bucket = by_month[m]
        k = quotas[m]
        n = len(bucket)
        if k >= n:
            selected.extend(bucket)
            continue
        # Systematic sampling with seeded random start
        step = n / k
        start = float(rng.uniform(0.0, step))
        indices = sorted({min(int(start + i * step), n - 1) for i in range(k)})
        if len(indices) < k:
            # Rounding collisions in the systematic-sampling positions can
            # collapse two distinct draws onto the same index; this is
            # visible here rather than silently under-delivering the quota.
            _log.warning(
                "month_stratified_sample_index_collision",
                month=m, requested=k, got=len(indices),
            )
        selected.extend(bucket[i] for i in indices)

    if len(selected) != target_n:
        _log.warning(
            "month_stratified_sample_quota_mismatch",
            target_n=target_n, actual_n=len(selected),
        )

    return selected


def collect_videos(
    settings: Settings,
    channels_df: pd.DataFrame,
    provider: Any,
    checkpoint: CheckpointManager,
    *,
    output_path: Path | str,
) -> pd.DataFrame:
    """Run the video-collection stage.

    Parameters
    ----------
    settings
        Validated Settings.
    channels_df
        Output of :func:`collect.channels.collect_channels`.
    provider
        Ready-to-use PlatformProvider.
    checkpoint
        Shared CheckpointManager.
    output_path
        Where to write ``videos.parquet``.

    Returns
    -------
    pd.DataFrame
        One row per video (eligible + selected + non-eligible retained
        with ``eligible=False`` for auditability).
    """
    output_path = Path(output_path)
    cfg_slice = _config_slice(settings, channels_df)

    # Peek at marker state before should_run() mutates it; a marker that
    # existed before but is deleted after means config changed → Tier-1
    # records are stale and must be cleared.
    _marker = checkpoint.checkpoint_root / f"{_STAGE_NAME}.done"
    _had_marker = _marker.exists()

    if not checkpoint.should_run(_STAGE_NAME, cfg_slice) and output_path.exists():
        return pd.read_parquet(output_path, engine="pyarrow")

    if _had_marker and not _marker.exists():
        # Config changed since last run; discard stale Tier-1 records.
        checkpoint.invalidate(_STAGE_NAME)

    already_done_pairs = {
        (rec["analyst_key"], rec["video_id"])
        for rec in checkpoint.read_records(_STAGE_NAME)
    }

    window_start = settings.study.observation_window.start.isoformat()
    window_end = settings.study.observation_window.end.isoformat()
    max_per_analyst = settings.collection.max_videos_per_analyst

    all_records: list[dict[str, Any]] = [
        rec for rec in checkpoint.read_records(_STAGE_NAME)
    ]

    for _, chan in channels_df.iterrows():
        analyst_key = chan["analyst_key"]
        uploads_ref = chan["uploads_ref"]

        bind_context(analyst_key=analyst_key, stage=_STAGE_NAME)
        try:
            # Step 1: enumerate video IDs in window (newest-first)
            vid_ids = list(
                provider.enumerate_videos(
                    uploads_ref,
                    window_start_iso=window_start,
                    window_end_iso=window_end,
                ),
            )
            _log.info(
                "videos_enumerated",
                analyst=analyst_key,
                n_ids=len(vid_ids),
                uploads_ref=uploads_ref,
            )
            if not vid_ids:
                continue

            # Step 2: batch metadata fetch (skip pairs already checkpointed)
            new_ids = [
                v for v in vid_ids
                if (analyst_key, v) not in already_done_pairs
            ]
            if new_ids:
                records = provider.fetch_video_metadata(
                    new_ids, analyst_key=analyst_key,
                )
            else:
                records = []

            # Step 3+4: apply sampling to eligible subset only
            eligible = [r for r in records if r.eligible]
            non_eligible = [r for r in records if not r.eligible]

            if len(eligible) > max_per_analyst:
                seed = derive_seed(
                    settings.study.root_seed,
                    f"videos_sample_{analyst_key}",
                )
                sampled = _month_stratified_sample(
                    eligible, target_n=max_per_analyst, seed=seed,
                )
                sampled_ids = {v.video_id for v in sampled}
                for v in eligible:
                    v_dict = v.model_dump(mode="json")
                    v_dict["selected"] = v.video_id in sampled_ids
                    checkpoint.append_record(_STAGE_NAME, v_dict)
                    all_records.append(v_dict)
                _log.info(
                    "videos_sampled",
                    analyst=analyst_key,
                    eligible=len(eligible),
                    selected=len(sampled),
                    strategy="month_stratified",
                )
            else:
                for v in eligible:
                    v_dict = v.model_dump(mode="json")
                    v_dict["selected"] = True
                    checkpoint.append_record(_STAGE_NAME, v_dict)
                    all_records.append(v_dict)
                _log.info(
                    "videos_all_selected",
                    analyst=analyst_key,
                    eligible=len(eligible),
                )

            # Non-eligible retained for auditability (never selected)
            for v in non_eligible:
                v_dict = v.model_dump(mode="json")
                v_dict["selected"] = False
                checkpoint.append_record(_STAGE_NAME, v_dict)
                all_records.append(v_dict)

        finally:
            clear_context()

    df = pd.DataFrame(all_records)
    if df.empty:
        _log.warning("no_videos_collected")
    else:
        _log.info(
            "collection_summary",
            total=len(df),
            eligible=int(df["eligible"].sum()) if "eligible" in df else 0,
            selected=int(df["selected"].sum()) if "selected" in df else 0,
        )
    write_parquet(df, output_path)
    checkpoint.mark_done(
        _STAGE_NAME, cfg_slice, extras={"n_videos": len(df)},
    )
    return df


__all__ = ["collect_videos", "_month_stratified_sample"]
