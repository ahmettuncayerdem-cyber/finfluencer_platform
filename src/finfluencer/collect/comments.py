"""
finfluencer.collect.comments
=============================

Top-level comment collection stage.

For each ``selected=True`` video in ``videos.parquet``:
    1. Fetch top-level comments via the provider (window-filtered,
       anonymised at ingest, day-truncated).
    2. Apply per-commenter cap (``max_comments_per_user_per_video``):
       if one hashed identifier posts more than the cap on this video,
       retain a deterministic random subset.
    3. Apply per-video cap (``max_comments_per_video``): if the total
       exceeds the cap, retain a deterministic random subset.
    4. Append kept records to a Tier-1 JSONL checkpoint (resume-safe).
    5. At end, materialise ``comments.parquet``.

Anonymisation invariant
-----------------------
Raw ``authorChannelId`` values never enter this module. The provider
hashes them at ingest; this module only ever sees ``commenter_hash``.
Similarly ``posted_date`` is already day-truncated by the provider.
"""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import CommentRecord, Settings
from finfluencer.core.exceptions import CollectionError
from finfluencer.core.logging import bind_context, clear_context, get_logger
from finfluencer.core.reproducibility import derive_seed
from finfluencer.utils.hashing import validate_salt
from finfluencer.utils.io import write_parquet


_log = get_logger(__name__)
_STAGE_NAME = "collect_comments"


def _config_slice(settings: Settings, videos_df: pd.DataFrame) -> dict[str, Any]:
    """Slice of config that invalidates this stage's output on change."""
    selected_ids = (
        sorted(videos_df.loc[videos_df["selected"], "video_id"].tolist())
        if "selected" in videos_df.columns and not videos_df.empty
        else []
    )
    return {
        "platform": settings.providers.platform,
        "window": {
            "start": settings.study.observation_window.start.isoformat(),
            "end": settings.study.observation_window.end.isoformat(),
        },
        "collection": {
            "max_comments_per_video": settings.collection.max_comments_per_video,
            "max_comments_per_user_per_video":
                settings.collection.max_comments_per_user_per_video,
        },
        "selected_video_ids": selected_ids,
    }


def _apply_user_cap(
    comments: list[CommentRecord],
    *,
    cap: int,
    seed: int,
) -> tuple[list[CommentRecord], int]:
    """Cap the number of comments per commenter_hash on this video.

    Deterministic: same input + same seed → same output.
    Returns (kept, dropped_count).
    """
    if cap <= 0:
        raise ValueError(f"user cap must be >= 1, got {cap}")
    by_hash: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(comments):
        by_hash[c.commenter_hash].append(i)

    rng = np.random.default_rng(seed)
    keep_indices: set[int] = set()
    dropped = 0
    for h in sorted(by_hash):
        indices = by_hash[h]
        if len(indices) <= cap:
            keep_indices.update(indices)
        else:
            chosen = rng.choice(
                np.array(indices, dtype=np.int64), size=cap, replace=False,
            )
            keep_indices.update(int(i) for i in chosen.tolist())
            dropped += len(indices) - cap
    kept = [c for i, c in enumerate(comments) if i in keep_indices]
    return kept, dropped


def _apply_video_cap(
    comments: list[CommentRecord],
    *,
    cap: int,
    seed: int,
) -> tuple[list[CommentRecord], int]:
    """Cap the total number of comments on this video.

    Deterministic: same input + same seed → same output.
    Returns (kept, dropped_count).
    """
    if cap <= 0:
        raise ValueError(f"video cap must be >= 1, got {cap}")
    if len(comments) <= cap:
        return comments, 0
    rng = np.random.default_rng(seed)
    indices = rng.choice(len(comments), size=cap, replace=False)
    kept_indices = sorted(int(i) for i in indices.tolist())
    dropped = len(comments) - cap
    return [comments[i] for i in kept_indices], dropped


def collect_comments(
    settings: Settings,
    videos_df: pd.DataFrame,
    provider: Any,
    checkpoint: CheckpointManager,
    *,
    output_path: Path | str,
    salt: str | None = None,
) -> pd.DataFrame:
    """Run the comment-collection stage."""
    output_path = Path(output_path)
    cfg_slice = _config_slice(settings, videos_df)

    _marker = checkpoint.checkpoint_root / f"{_STAGE_NAME}.done"
    _had_marker = _marker.exists()

    if not checkpoint.should_run(_STAGE_NAME, cfg_slice) and output_path.exists():
        return pd.read_parquet(output_path, engine="pyarrow")

    if _had_marker and not _marker.exists():
        checkpoint.invalidate(_STAGE_NAME)

    salt = salt if salt is not None else os.environ.get("ANON_SALT", "")
    if not salt:
        raise CollectionError(
            "collect_comments requires a non-empty salt (set ANON_SALT env "
            "or pass salt= explicitly)",
        )
    from finfluencer.core.contracts import ReplicationStage
    strict = settings.replication.stage in (
        ReplicationStage.submission,
        ReplicationStage.publication,
    )
    validate_salt(salt, strict=strict)

    if videos_df.empty or "selected" not in videos_df.columns:
        _log.warning("no_videos_available_for_comments")
        empty = pd.DataFrame()
        write_parquet(empty, output_path)
        checkpoint.mark_done(_STAGE_NAME, cfg_slice, extras={"n_comments": 0})
        return empty

    selected = videos_df[videos_df["selected"]].copy()
    if selected.empty:
        _log.warning("no_selected_videos_for_comments")
        empty = pd.DataFrame()
        write_parquet(empty, output_path)
        checkpoint.mark_done(_STAGE_NAME, cfg_slice, extras={"n_comments": 0})
        return empty

    already_done_pairs = {
        (rec.get("analyst_key"), rec.get("video_id"))
        for rec in checkpoint.read_records(_STAGE_NAME)
        if "video_id" in rec
    }
    all_records: list[dict[str, Any]] = list(checkpoint.read_records(_STAGE_NAME))

    window_start = settings.study.observation_window.start.isoformat()
    window_end = settings.study.observation_window.end.isoformat()
    user_cap = settings.collection.max_comments_per_user_per_video
    video_cap = settings.collection.max_comments_per_video

    total_kept = 0
    total_dropped_user = 0
    total_dropped_video = 0

    for _, video_row in selected.iterrows():
        analyst_key = video_row["analyst_key"]
        video_id = video_row["video_id"]
        if (analyst_key, video_id) in already_done_pairs:
            continue

        bind_context(analyst_key=analyst_key, video_id=video_id, stage=_STAGE_NAME)
        try:
            comments = provider.fetch_top_level_comments(
                video_id,
                analyst_key=analyst_key,
                salt=salt,
                window_start_iso=window_start,
                window_end_iso=window_end,
            )

            fetched_n = len(comments)
            if fetched_n == 0:
                _log.info("video_has_no_comments", video_id=video_id)
                continue

            user_seed = derive_seed(
                settings.study.root_seed,
                f"comments_user_cap_{video_id}",
            )
            comments, dropped_user = _apply_user_cap(
                comments, cap=user_cap, seed=user_seed,
            )

            video_seed = derive_seed(
                settings.study.root_seed,
                f"comments_video_cap_{video_id}",
            )
            comments, dropped_video = _apply_video_cap(
                comments, cap=video_cap, seed=video_seed,
            )

            for c in comments:
                record = c.model_dump(mode="json")
                checkpoint.append_record(_STAGE_NAME, record)
                all_records.append(record)

            total_kept += len(comments)
            total_dropped_user += dropped_user
            total_dropped_video += dropped_video

            _log.info(
                "video_comments_collected",
                video_id=video_id,
                fetched=fetched_n,
                kept=len(comments),
                dropped_user=dropped_user,
                dropped_video=dropped_video,
            )
        finally:
            clear_context()

    df = pd.DataFrame(all_records)
    write_parquet(df, output_path)
    checkpoint.mark_done(
        _STAGE_NAME,
        cfg_slice,
        extras={
            "n_comments": len(df),
            "n_kept_new": total_kept,
            "n_dropped_user_cap": total_dropped_user,
            "n_dropped_video_cap": total_dropped_video,
        },
    )
    _log.info(
        "comments_stage_summary",
        n_comments_total=len(df),
        n_kept_new=total_kept,
        n_dropped_user_cap=total_dropped_user,
        n_dropped_video_cap=total_dropped_video,
    )
    return df


__all__ = ["collect_comments", "_apply_user_cap", "_apply_video_cap"]