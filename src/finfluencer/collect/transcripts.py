"""
finfluencer.collect.transcripts
================================

Video transcript collection stage.

For each ``selected=True`` video, attempts to fetch the auto-generated
or manual transcript from YouTube. Used by Phase 4 H4 video-topic coding
(title + description + transcript → topic class).

Design decisions
----------------
* **YouTube-specific.** Transcript fetching does not go through
  PlatformProvider because there is no cross-platform equivalent
  (TikTok/Reddit have no transcripts, X has none for text posts).
  Adding a TranscriptProvider Protocol is a future v2.2 concern when
  a second platform actually needs it.
* **Graceful degradation.** Videos without a transcript (disabled,
  no captions, private) yield ``transcript_available=False`` records,
  not errors — H4 falls back to title+description for those.
* **Language preference.** Tries the language of the study's
  ``providers.language`` provider first (Turkish for MVP-B), then any
  available auto-transcript. The chosen language is recorded so
  downstream analysis can filter.
* **No quota accounting.** The transcript endpoint is not billed
  against the YouTube Data API quota; it is a separate public endpoint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import Settings
from finfluencer.core.logging import bind_context, clear_context, get_logger
from finfluencer.utils.io import write_parquet
from finfluencer.utils.time import now_utc


_log = get_logger(__name__)
_STAGE_NAME = "collect_transcripts"


# -----------------------------------------------------------------------------
# Soft dependency on youtube-transcript-api
# -----------------------------------------------------------------------------
# Imported lazily so unit tests can substitute a stub without requiring the
# real package. Production code installs the dependency via pyproject.toml.
# -----------------------------------------------------------------------------


def _default_fetcher(video_id: str, *, preferred_languages: list[str]) -> dict[str, Any]:
    """Default transcript fetcher using youtube-transcript-api.

    Returns a dict with keys:
        available (bool)
        text (str)
        language (str | None)
        reason (str)  -- explanation when unavailable

    Never raises on missing transcripts. Only raises on catastrophic errors
    (e.g. programmer error, unexpected library exception).
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
        )
    except ImportError as e:
        raise RuntimeError(
            "youtube-transcript-api is not installed; run "
            "`poetry install` or `pip install youtube-transcript-api`",
        ) from e

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    except TranscriptsDisabled:
        return {"available": False, "text": "", "language": None,
                "reason": "transcripts_disabled"}
    except VideoUnavailable:
        return {"available": False, "text": "", "language": None,
                "reason": "video_unavailable"}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "text": "", "language": None,
                "reason": f"list_error:{type(e).__name__}"}

    # Try preferred languages first, then any generated transcript.
    transcript = None
    for lang in preferred_languages:
        try:
            transcript = transcript_list.find_transcript([lang])
            break
        except NoTranscriptFound:
            continue

    if transcript is None:
        # Fall back to any generated transcript
        try:
            transcript = transcript_list.find_generated_transcript(preferred_languages)
        except NoTranscriptFound:
            # Last resort: any transcript at all
            available_langs = [t.language_code for t in transcript_list]
            if available_langs:
                try:
                    transcript = transcript_list.find_transcript(available_langs[:1])
                except NoTranscriptFound:
                    return {"available": False, "text": "", "language": None,
                            "reason": "no_matching_transcript"}
            else:
                return {"available": False, "text": "", "language": None,
                        "reason": "no_transcripts"}

    try:
        segments = transcript.fetch()
    except Exception as e:  # noqa: BLE001
        return {"available": False, "text": "", "language": None,
                "reason": f"fetch_error:{type(e).__name__}"}

    text = " ".join(seg.get("text", "").strip() for seg in segments if seg.get("text"))
    return {
        "available": True,
        "text": text,
        "language": transcript.language_code,
        "reason": "",
    }


# -----------------------------------------------------------------------------
# Config slice + config-change invalidation
# -----------------------------------------------------------------------------


def _config_slice(settings: Settings, videos_df: pd.DataFrame) -> dict[str, Any]:
    """Slice of config that invalidates this stage on change."""
    selected_ids = (
        sorted(videos_df.loc[videos_df["selected"], "video_id"].tolist())
        if "selected" in videos_df.columns and not videos_df.empty
        else []
    )
    return {
        "language": settings.providers.language,
        "selected_video_ids": selected_ids,
    }


# -----------------------------------------------------------------------------
# Stage entry point
# -----------------------------------------------------------------------------


def collect_transcripts(
    settings: Settings,
    videos_df: pd.DataFrame,
    checkpoint: CheckpointManager,
    *,
    output_path: Path | str,
    fetcher: Any = None,
    language_pref: str | None = None,
) -> pd.DataFrame:
    """Run the transcript-collection stage.

    Parameters
    ----------
    settings
        Validated :class:`Settings`.
    videos_df
        Output of :func:`collect.videos.collect_videos`; only rows with
        ``selected=True`` are processed.
    checkpoint
        Shared :class:`CheckpointManager`.
    output_path
        Destination for ``transcripts.parquet``.
    fetcher
        Callable ``(video_id, *, preferred_languages) -> dict`` returning
        the transcript metadata. Defaults to
        :func:`_default_fetcher` (youtube-transcript-api).
        Tests inject a stub.
    language_pref
        Two-letter ISO code, e.g. ``"tr"``. Defaults to the ISO code
        of the study's language provider (Turkish → "tr").

    Returns
    -------
    pd.DataFrame
        One row per selected video with columns:
            analyst_key, video_id, transcript_available, transcript_text,
            transcript_language, unavailable_reason, retrieved_at_utc
    """
    output_path = Path(output_path)
    cfg_slice = _config_slice(settings, videos_df)

    _marker = checkpoint.checkpoint_root / f"{_STAGE_NAME}.done"
    _had_marker = _marker.exists()

    if not checkpoint.should_run(_STAGE_NAME, cfg_slice) and output_path.exists():
        return pd.read_parquet(output_path, engine="pyarrow")

    if _had_marker and not _marker.exists():
        checkpoint.invalidate(_STAGE_NAME)

    fetcher = fetcher or _default_fetcher

    # Default language preference: study's language provider ISO code.
    if language_pref is None:
        # Fall back to "tr" for MVP-B; safe since Turkish is the only
        # registered language provider for this study.
        language_pref = "tr"

    if videos_df.empty or "selected" not in videos_df.columns:
        _log.warning("no_videos_available_for_transcripts")
        empty = pd.DataFrame()
        write_parquet(empty, output_path)
        checkpoint.mark_done(_STAGE_NAME, cfg_slice, extras={"n_transcripts": 0})
        return empty

    selected = videos_df[videos_df["selected"]].copy()
    if selected.empty:
        empty = pd.DataFrame()
        write_parquet(empty, output_path)
        checkpoint.mark_done(_STAGE_NAME, cfg_slice, extras={"n_transcripts": 0})
        return empty

    already_done_ids = {
        rec.get("video_id")
        for rec in checkpoint.read_records(_STAGE_NAME)
        if "video_id" in rec
    }
    all_records: list[dict[str, Any]] = list(checkpoint.read_records(_STAGE_NAME))

    n_ok = n_disabled = n_missing = n_error = 0

    for _, video_row in selected.iterrows():
        video_id = video_row["video_id"]
        analyst_key = video_row["analyst_key"]
        if video_id in already_done_ids:
            continue

        bind_context(video_id=video_id, analyst_key=analyst_key, stage=_STAGE_NAME)
        try:
            result = fetcher(
                video_id,
                preferred_languages=[language_pref, "en"],
            )
            record = {
                "analyst_key": analyst_key,
                "video_id": video_id,
                "transcript_available": bool(result.get("available", False)),
                "transcript_text": result.get("text", "") or "",
                "transcript_language": result.get("language"),
                "unavailable_reason": result.get("reason", "") or "",
                "retrieved_at_utc": now_utc().isoformat(),
            }
            checkpoint.append_record(_STAGE_NAME, record)
            all_records.append(record)

            if record["transcript_available"]:
                n_ok += 1
                _log.info("transcript_ok", video_id=video_id,
                          language=record["transcript_language"],
                          n_chars=len(record["transcript_text"]))
            elif record["unavailable_reason"] == "transcripts_disabled":
                n_disabled += 1
                _log.info("transcript_disabled", video_id=video_id)
            elif "no_" in record["unavailable_reason"]:
                n_missing += 1
                _log.info("transcript_missing", video_id=video_id,
                          reason=record["unavailable_reason"])
            else:
                n_error += 1
                _log.warning("transcript_error", video_id=video_id,
                             reason=record["unavailable_reason"])
        finally:
            clear_context()

    df = pd.DataFrame(all_records)
    write_parquet(df, output_path)
    checkpoint.mark_done(
        _STAGE_NAME,
        cfg_slice,
        extras={
            "n_total": len(df),
            "n_ok": n_ok,
            "n_disabled": n_disabled,
            "n_missing": n_missing,
            "n_error": n_error,
        },
    )
    _log.info("transcripts_stage_summary",
              n_total=len(df), n_ok=n_ok, n_disabled=n_disabled,
              n_missing=n_missing, n_error=n_error)
    return df


__all__ = ["collect_transcripts"]
