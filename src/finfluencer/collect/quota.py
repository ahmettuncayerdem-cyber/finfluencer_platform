"""
finfluencer.collect.quota
==========================

Collection-time quota bookkeeping.

Thin wrapper around :class:`finfluencer.core.budgets.QuotaTracker` that:

* Constructs a tracker from settings.collection.quota
* Adds optional disk persistence so a multi-day run can resume against
  the same daily counter
* Handles UTC midnight rollover (Google's YouTube API quota resets at
  midnight Pacific Time — configurable)

This is NOT a new abstraction; it is a constructor + persistence layer
over the Phase 1 QuotaTracker primitive.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from finfluencer.core.budgets import QuotaTracker
from finfluencer.core.contracts import QuotaConfig
from finfluencer.utils.io import read_json, write_json
from finfluencer.utils.time import now_utc


#: Google's YouTube API quota resets at midnight Pacific Time.
#: We approximate this as UTC-8; the exact PT boundary doesn't matter
#: for safety-margin-protected accounting.
_QUOTA_RESET_UTC_OFFSET = timedelta(hours=8)


def _quota_day(now: datetime | None = None) -> date:
    """Return the "quota day" — the date under which the current time falls
    after adjusting for the Pacific reset boundary."""
    n = now or now_utc()
    return (n - _QUOTA_RESET_UTC_OFFSET).date()


def create_youtube_tracker(cfg: QuotaConfig, *, service: str = "youtube_data_api_v3") -> QuotaTracker:
    """Construct a QuotaTracker for YouTube from settings."""
    return QuotaTracker(
        daily_units=cfg.daily_units,
        safety_margin=cfg.safety_margin,
        service=service,
    )


def load_persisted_tracker(
    cfg: QuotaConfig,
    state_path: Path | str,
    *,
    service: str = "youtube_data_api_v3",
) -> QuotaTracker:
    """Load a QuotaTracker from disk, or create fresh if:

    * the state file does not exist, or
    * the persisted quota-day differs from today (rollover).
    """
    state_path = Path(state_path)
    tracker = create_youtube_tracker(cfg, service=service)
    if not state_path.exists():
        return tracker
    try:
        state = read_json(state_path)
    except Exception:  # noqa: BLE001
        return tracker

    persisted_day = state.get("quota_day")
    today = _quota_day().isoformat()
    if persisted_day != today:
        return tracker  # rollover; start fresh

    used = int(state.get("used_units", 0))
    if 0 <= used <= tracker.daily_units:
        tracker.spend(used)
    return tracker


def persist_tracker(
    tracker: QuotaTracker,
    state_path: Path | str,
) -> None:
    """Persist tracker state to disk for resume-friendly runs."""
    state = {
        "quota_day": _quota_day().isoformat(),
        "written_at_utc": now_utc().isoformat(),
        **tracker.snapshot(),
    }
    write_json(state, state_path)


__all__ = [
    "create_youtube_tracker",
    "load_persisted_tracker",
    "persist_tracker",
]
