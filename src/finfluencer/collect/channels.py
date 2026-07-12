"""
finfluencer.collect.channels
=============================

Channel resolution stage.

For every analyst in the roster:
    1. resolve their handle/channel-id → canonical UC... channel ID
    2. fetch channel metadata (title, uploads playlist, statistics)
    3. persist a row to data/raw/channels.parquet
    4. append a checkpoint record so subsequent runs skip resolved analysts

Output frame columns
--------------------
    analyst_key           (str) — from roster
    channel_id            (str) — canonical UC...
    title                 (str)
    description           (str)
    published_at          (str, ISO 8601)
    uploads_ref           (str) — uploads playlist ID; consumed by videos stage
    subscriber_count      (int)
    video_count           (int)
    view_count            (int)
    resolved_at_utc       (str, ISO 8601)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import AnalystRoster, Settings
from finfluencer.core.exceptions import ResourceNotFoundError
from finfluencer.core.logging import bind_context, clear_context, get_logger
from finfluencer.utils.io import write_parquet
from finfluencer.utils.time import now_utc


_log = get_logger(__name__)
_STAGE_NAME = "collect_channels"


def _config_slice(settings: Settings, roster: AnalystRoster) -> dict[str, Any]:
    """Deterministic slice of config that affects this stage's output.

    If this changes, the .done marker is invalidated and the stage re-runs.
    """
    return {
        "roster": [
            {
                "key": a.key,
                "handle": a.handle,
                "channel_id": a.channel_id,
            }
            for a in roster.analysts
        ],
        "platform": settings.providers.platform,
    }


def collect_channels(
    settings: Settings,
    roster: AnalystRoster,
    provider: Any,
    checkpoint: CheckpointManager,
    *,
    output_path: Path | str,
) -> pd.DataFrame:
    """Run the channel-collection stage.

    Parameters
    ----------
    settings
        Validated Settings object.
    roster
        Validated AnalystRoster.
    provider
        A ready-to-use PlatformProvider (already constructed with quota).
    checkpoint
        Shared CheckpointManager for the study.
    output_path
        Where to write the final channels.parquet.

    Returns
    -------
    pd.DataFrame
        One row per successfully resolved analyst.
    """
    output_path = Path(output_path)
    cfg_slice = _config_slice(settings, roster)

    # Peek at marker state before should_run() mutates it; a marker that
    # existed before but is deleted after means config changed → Tier-1
    # records are stale and must be cleared.
    _marker = checkpoint.checkpoint_root / f"{_STAGE_NAME}.done"
    _had_marker = _marker.exists()

    # Skip if already done and config unchanged
    if not checkpoint.should_run(_STAGE_NAME, cfg_slice) and output_path.exists():
        return pd.read_parquet(output_path, engine="pyarrow")

    if _had_marker and not _marker.exists():
        # Config changed since last run; discard stale Tier-1 records.
        checkpoint.invalidate(_STAGE_NAME)

    # Resume support: skip analysts already in Tier-1 checkpoint
    already_done = checkpoint.completed_ids(_STAGE_NAME, key="analyst_key")
    rows: list[dict[str, Any]] = []

    # Reload previously-checkpointed rows (idempotent resume)
    for rec in checkpoint.read_records(_STAGE_NAME):
        rows.append(rec)

    for analyst in roster.analysts:
        if analyst.key in already_done:
            continue

        bind_context(analyst_key=analyst.key, stage=_STAGE_NAME)
        try:
            # Prefer channel_id if configured (more stable than handle)
            lookup = analyst.channel_id or analyst.handle
            if not lookup or lookup.startswith("@REPLACE"):
                _log.warning(
                    "channel_lookup_placeholder_skipped",
                    analyst=analyst.key,
                    reason="handle_is_placeholder",
                )
                continue

            channel_id = provider.resolve_channel(lookup)
            meta = provider.channel_metadata(channel_id)

            row = {
                "analyst_key": analyst.key,
                "channel_id": meta["channel_id"],
                "title": meta["title"],
                "description": meta["description"],
                "published_at": meta["published_at"],
                "uploads_ref": meta["uploads_ref"],
                "subscriber_count": meta["subscriber_count"],
                "video_count": meta["video_count"],
                "view_count": meta["view_count"],
                "resolved_at_utc": now_utc().isoformat(),
            }
            checkpoint.append_record(_STAGE_NAME, row)
            rows.append(row)
            _log.info(
                "channel_resolved",
                analyst=analyst.key,
                channel_id=meta["channel_id"],
                uploads_ref=meta["uploads_ref"],
                video_count=meta["video_count"],
            )
        except ResourceNotFoundError as e:
            _log.error(
                "channel_not_found",
                analyst=analyst.key,
                lookup=lookup,
                error=str(e),
            )
            continue
        finally:
            clear_context()

    df = pd.DataFrame(rows)
    if df.empty:
        _log.warning("no_channels_resolved", analyst_count=len(roster.analysts))
    write_parquet(df, output_path)
    checkpoint.mark_done(_STAGE_NAME, cfg_slice, extras={"n_resolved": len(df)})
    return df


__all__ = ["collect_channels"]
