"""
finfluencer.migration.backfill_entity_model
=============================================

Reads the current analyst-centric ``videos.parquet``/``comments.parquet``
(plus ``channels.parquet`` for entity metadata) and derives the four
entity-centric tables described in ``entity_centric_platform_architecture.md``
(Phase 0):

    EntityRecord            -> entities.parquet
    EntityVideoLinkRecord   -> entity_video_link.parquet
    CanonicalVideoRecord    -> videos_canonical.parquet
    CanonicalCommentRecord  -> comments_canonical.parquet

Design
------
Every row of the current ``videos.parquet`` becomes exactly one
``EntityVideoLinkRecord`` (its ``analyst_key`` -> ``entity_key``,
``eligible``/``exclusion_reason``/``selected`` carried over unchanged).
The canonical ``Video``/``Comment`` tables are produced by deduplicating
on ``video_id``/``comment_id`` respectively, keeping only fields that
are intrinsic to the video/comment (not per-entity decisions).

Safety
------
Before deduplicating, every fixed intrinsic field is checked for
consistency across duplicate rows of the same ``video_id``/``comment_id``
(e.g. the same video's ``title`` must be identical regardless of which
analyst's row it came from). Any inconsistency raises :class:`ValueError`
rather than silently picking one value - this is a data-integrity signal,
not something to paper over. Volatile snapshot metrics (views/likes/
comment_count) are handled separately - see ``_VOLATILE_VIDEO_METRICS``.

Nothing here mutates or removes the source parquet files. Existing
pipeline stages (embeddings/sentiment/topics) are entirely unaffected -
they keep reading the original ``videos.parquet``/``comments.parquet``
exactly as before.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from finfluencer.core.contracts import (
    CanonicalCommentRecord,
    CanonicalVideoRecord,
    EntityRecord,
    EntityType,
    EntityVideoLinkRecord,
)
from finfluencer.core.logging import get_logger
from finfluencer.utils.io import read_parquet, write_parquet

_log = get_logger(__name__)

_VIDEO_INTRINSIC_COLUMNS: list[str] = list(CanonicalVideoRecord.model_fields.keys())
_COMMENT_INTRINSIC_COLUMNS: list[str] = list(CanonicalCommentRecord.model_fields.keys())

#: Fields that are point-in-time snapshots of a live counter, not fixed
#: properties of the video - re-collecting the same video for a second
#: entity days/weeks later legitimately observes a higher view/like/
#: comment count. These are exempt from the strict cross-row consistency
#: check and are instead resolved by taking the maximum observed value
#: (the most up-to-date snapshot) when deduplicating. Confirmed against
#: production data: 7 of the platform's real multi-entity videos differ
#: only in ``views`` across their duplicate rows - a real, benign
#: consequence of collection-time drift, not a data-integrity problem.
_VOLATILE_VIDEO_METRICS: frozenset[str] = frozenset({"views", "likes", "comment_count"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hashable(value: Any) -> Any:
    """Make list/ndarray values hashable for ``groupby(...).nunique()``."""
    if isinstance(value, (list, np.ndarray)):
        return tuple(value)
    return value


def _assert_consistent(
    df: pd.DataFrame, key_col: str, intrinsic_cols: list[str], *, label: str,
) -> None:
    """Raise if any ``key_col`` value has divergent intrinsic-field values
    across its duplicate rows - dedup would silently discard information."""
    check_cols = [c for c in intrinsic_cols if c != key_col and c in df.columns]
    if not check_cols or df.empty:
        return
    hashable_df = df[[key_col] + check_cols].copy()
    for col in check_cols:
        hashable_df[col] = hashable_df[col].map(_hashable)
    nunique = hashable_df.groupby(key_col)[check_cols].nunique(dropna=False)
    inconsistent = nunique[(nunique > 1).any(axis=1)]
    if not inconsistent.empty:
        bad_cols = inconsistent.columns[(inconsistent > 1).any(axis=0)].tolist()
        raise ValueError(
            f"{label}: {len(inconsistent)} {key_col} value(s) have "
            f"inconsistent values across duplicate rows in columns "
            f"{bad_cols} - cannot safely deduplicate. First offenders: "
            f"{inconsistent.index.tolist()[:10]}",
        )


def _build_entities(
    videos_df: pd.DataFrame,
    channels_df: pd.DataFrame | None,
    *,
    study_id: str,
) -> pd.DataFrame:
    """One ``EntityRecord`` per existing ``analyst_key`` (``entity_type="creator"``)."""
    entity_keys = sorted(videos_df["analyst_key"].dropna().unique().tolist())
    channel_ids_by_key: dict[str, str | None] = {}
    if channels_df is not None and "analyst_key" in channels_df.columns:
        for _, row in channels_df.iterrows():
            channel_ids_by_key.setdefault(row["analyst_key"], row.get("channel_id"))

    now = _now_iso()
    records = [
        EntityRecord(
            entity_key=key,
            entity_type=EntityType.creator,
            display_name=key,
            description=f"Backfilled from analyst_key={key!r} (Phase 0 migration).",
            membership_strategy="creator_channel",
            membership_params={
                "channel_ids": (
                    [channel_ids_by_key[key]] if channel_ids_by_key.get(key) else []
                ),
            },
            study_id=study_id,
            created_at=now,
        ).model_dump(mode="json")
        for key in entity_keys
    ]
    return pd.DataFrame.from_records(records)


def _build_entity_video_link(
    videos_df: pd.DataFrame, *, criteria_version: str,
) -> pd.DataFrame:
    """One ``EntityVideoLinkRecord`` per row of the source ``videos.parquet`` -
    this is where the many-to-many relationship becomes explicit."""
    now = _now_iso()
    records = [
        EntityVideoLinkRecord(
            entity_key=row["analyst_key"],
            video_id=row["video_id"],
            matched_via="channel_membership",
            eligible=bool(row.get("eligible", True)),
            exclusion_reason=row.get("exclusion_reason", "") or "",
            selected=bool(row.get("selected", False)),
            criteria_version=criteria_version,
            linked_at=now,
        ).model_dump(mode="json")
        for _, row in videos_df.iterrows()
    ]
    return pd.DataFrame.from_records(records)


def _build_canonical_videos(videos_df: pd.DataFrame) -> pd.DataFrame:
    """Dedup ``videos_df`` by ``video_id``, keeping only intrinsic fields.

    Fixed fields (title, description, duration_sec, published_at,
    category_id, made_for_kids) must be identical across duplicate rows
    of the same ``video_id`` - inconsistency there is refused (see
    ``_assert_consistent``). Volatile snapshot metrics
    (``_VOLATILE_VIDEO_METRICS``) are exempt and instead resolved by
    taking the maximum observed value across duplicates.
    """
    fixed_cols = [c for c in _VIDEO_INTRINSIC_COLUMNS if c not in _VOLATILE_VIDEO_METRICS]
    _assert_consistent(videos_df, "video_id", fixed_cols, label="videos_canonical")

    cols = [c for c in _VIDEO_INTRINSIC_COLUMNS if c in videos_df.columns]
    volatile_present = [c for c in _VOLATILE_VIDEO_METRICS if c in cols]
    fixed_present = [c for c in cols if c not in volatile_present]

    dedup = videos_df[cols].drop_duplicates(subset=["video_id"], keep="first")
    if volatile_present:
        maxima = videos_df.groupby("video_id")[volatile_present].max().reset_index()
        dedup = dedup.drop(columns=volatile_present).merge(
            maxima, on="video_id", how="left",
        )
        dedup = dedup[fixed_present + volatile_present]

    records = [
        CanonicalVideoRecord(**row.to_dict()).model_dump(mode="json")
        for _, row in dedup.iterrows()
    ]
    return pd.DataFrame.from_records(records)


def _build_canonical_comments(comments_df: pd.DataFrame) -> pd.DataFrame:
    """Dedup ``comments_df`` by ``comment_id``, keeping only intrinsic fields."""
    _assert_consistent(
        comments_df, "comment_id", _COMMENT_INTRINSIC_COLUMNS, label="comments_canonical",
    )
    cols = [c for c in _COMMENT_INTRINSIC_COLUMNS if c in comments_df.columns]
    canonical = comments_df[cols].drop_duplicates(subset=["comment_id"], keep="first")
    records = [
        CanonicalCommentRecord(**row.to_dict()).model_dump(mode="json")
        for _, row in canonical.iterrows()
    ]
    return pd.DataFrame.from_records(records)


def backfill_entity_model(
    videos_path: Path | str,
    comments_path: Path | str,
    *,
    channels_path: Path | str | None = None,
    study_id: str = "finfluencer_platform",
    criteria_version: str = "v1_backfill",
    output_dir: Path | str,
) -> dict[str, Any]:
    """Derive the entity-centric tables from the current analyst-centric ones.

    Parameters
    ----------
    videos_path, comments_path
        Existing ``videos.parquet``/``comments.parquet`` (read-only).
    channels_path
        Existing ``channels.parquet``, used to populate
        ``EntityRecord.membership_params.channel_ids``. Optional - if
        omitted, ``channel_ids`` is left empty.
    study_id
        Value stamped into every ``EntityRecord.study_id``.
    criteria_version
        Value stamped into every ``EntityVideoLinkRecord.criteria_version`` -
        marks these links as produced by this one-time backfill, distinct
        from any future live membership-resolver run.
    output_dir
        Destination directory for the four canonical parquet files.
        Created if missing. Existing files there are overwritten - this
        function is idempotent, safe to re-run.

    Returns
    -------
    dict
        ``{"entities": df, "entity_video_link": df, "videos_canonical": df,
        "comments_canonical": df, "report": {...}}`` - the four frames
        (also written to ``output_dir``) plus a validation report with row
        counts and the multi-entity-video count, for sanity-checking against
        what is already known about the source dataset.

    Raises
    ------
    ValueError
        If a ``video_id``/``comment_id`` has inconsistent fixed-field
        values across its duplicate source rows (see ``_assert_consistent``) -
        this would make deduplication silently lossy, so it is refused
        rather than guessed at.
    """
    videos_df = read_parquet(Path(videos_path))
    comments_df = read_parquet(Path(comments_path))
    channels_df = read_parquet(Path(channels_path)) if channels_path is not None else None

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    entities_df = _build_entities(videos_df, channels_df, study_id=study_id)
    entity_video_link_df = _build_entity_video_link(
        videos_df, criteria_version=criteria_version,
    )
    videos_canonical_df = _build_canonical_videos(videos_df)
    comments_canonical_df = _build_canonical_comments(comments_df)

    write_parquet(entities_df, output_dir / "entities.parquet")
    write_parquet(entity_video_link_df, output_dir / "entity_video_link.parquet")
    write_parquet(videos_canonical_df, output_dir / "videos_canonical.parquet")
    write_parquet(comments_canonical_df, output_dir / "comments_canonical.parquet")

    video_multiplicity = entity_video_link_df.groupby("video_id")["entity_key"].nunique()
    n_multi_entity_videos = int((video_multiplicity > 1).sum())

    report = {
        "n_entities": len(entities_df),
        "n_videos_raw_rows": len(videos_df),
        "n_videos_canonical": len(videos_canonical_df),
        "n_entity_video_links": len(entity_video_link_df),
        "n_multi_entity_videos": n_multi_entity_videos,
        "n_comments_raw_rows": len(comments_df),
        "n_comments_canonical": len(comments_canonical_df),
        "n_duplicate_comment_rows_collapsed": len(comments_df) - len(comments_canonical_df),
    }
    _log.info("backfill_entity_model_done", **report)

    return {
        "entities": entities_df,
        "entity_video_link": entity_video_link_df,
        "videos_canonical": videos_canonical_df,
        "comments_canonical": comments_canonical_df,
        "report": report,
    }


__all__ = ["backfill_entity_model"]
