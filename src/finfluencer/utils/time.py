"""
finfluencer.utils.time
=======================

Timezone-aware datetime helpers.

All datetime values inside the platform are timezone-aware UTC. Naive
datetimes are rejected at boundaries to prevent silent timezone bugs.
Day-truncation is the sole anonymisation point for timestamps per
Methods §3.11 (Ethics-in-design).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Union

_ISO_DURATION_RE = re.compile(
    r"^P"
    r"(?:(?P<days>\d+)D)?"
    r"T?"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?$",
)

DateLike = Union[str, date, datetime]
TimeLike = Union[str, datetime]


def now_utc() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def parse_iso8601(s: str) -> datetime:
    """Parse an ISO 8601 timestamp into a timezone-aware UTC datetime.

    Accepts trailing ``Z`` (YouTube's convention) or an explicit offset.
    Naive inputs (no offset) raise :class:`ValueError`.
    """
    if not s:
        raise ValueError("parse_iso8601: input is empty")
    # Python's fromisoformat handles Z from 3.11+ but be defensive
    normalized = s.replace("Z", "+00:00") if s.endswith("Z") else s
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as e:
        raise ValueError(f"parse_iso8601: cannot parse {s!r}") from e
    if dt.tzinfo is None:
        raise ValueError(f"parse_iso8601: naive datetime rejected: {s!r}")
    return dt.astimezone(timezone.utc)


def format_iso8601(dt: datetime) -> str:
    """Format a timezone-aware datetime as ISO 8601 UTC with ``Z`` suffix.

    Naive datetimes raise :class:`ValueError`.
    """
    if dt.tzinfo is None:
        raise ValueError("format_iso8601: naive datetime rejected")
    utc = dt.astimezone(timezone.utc)
    # Drop microseconds for canonical output; use Z suffix.
    return utc.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware UTC; convert or raise.

    Naive datetimes raise :class:`ValueError`.
    """
    if dt.tzinfo is None:
        raise ValueError("ensure_utc: naive datetime rejected")
    return dt.astimezone(timezone.utc)


def truncate_to_day(ts: TimeLike) -> str:
    """Truncate a timestamp to day resolution (``YYYY-MM-DD``).

    Sole anonymisation point for timestamps per Methods §3.11:
    sub-daily resolution is stripped so commenters cannot be
    correlated across videos by exact posting time.

    Accepts a datetime (must be timezone-aware) or an ISO 8601 string.
    """
    if isinstance(ts, str):
        dt = parse_iso8601(ts)
    else:
        dt = ensure_utc(ts)
    return dt.strftime("%Y-%m-%d")


def _coerce_boundary(x: DateLike) -> datetime:
    if isinstance(x, str):
        # Allow bare dates like "2025-01-01"
        if "T" not in x and " " not in x:
            return datetime.fromisoformat(x).replace(tzinfo=timezone.utc)
        return parse_iso8601(x)
    if isinstance(x, datetime):
        return ensure_utc(x)
    # date
    return datetime(x.year, x.month, x.day, tzinfo=timezone.utc)


def is_in_window(
    ts: TimeLike,
    start: DateLike,
    end: DateLike,
    *,
    inclusive: bool = True,
) -> bool:
    """Test whether a timestamp falls within a ``[start, end]`` window.

    ``start`` and ``end`` may be given as dates, datetimes, or ISO 8601
    strings. If ``end`` is a bare date, it is expanded to end-of-day
    (23:59:59 UTC) when ``inclusive`` is True — matching how researchers
    typically mean "up to and including 2025-12-31".
    """
    ts_dt = parse_iso8601(ts) if isinstance(ts, str) else ensure_utc(ts)
    start_dt = _coerce_boundary(start)
    end_dt = _coerce_boundary(end)

    # If end was a bare date, extend to end-of-day for intuitive semantics.
    if isinstance(end, (str, date)) and not isinstance(end, datetime):
        if inclusive and end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0:
            end_dt = end_dt.replace(hour=23, minute=59, second=59)

    if inclusive:
        return start_dt <= ts_dt <= end_dt
    return start_dt <= ts_dt < end_dt


def iso8601_duration_to_seconds(duration: str) -> int:
    """Parse an ISO 8601 duration string (e.g. ``PT1M30S``) to seconds.

    Used for YouTube Shorts detection: videos with duration <= 60s are
    classified as Shorts. Returns 0 for empty or unparseable inputs
    rather than raising, since YouTube occasionally returns absent
    duration fields for private or transcoding videos.
    """
    if not duration:
        return 0
    m = _ISO_DURATION_RE.match(duration)
    if not m:
        return 0
    parts = {k: int(v) if v else 0 for k, v in m.groupdict().items()}
    return (
        parts["days"] * 86_400
        + parts["hours"] * 3_600
        + parts["minutes"] * 60
        + parts["seconds"]
    )


def month_key(ts: TimeLike) -> str:
    """Return the year-month key ``YYYY-MM`` for temporal aggregation."""
    dt = parse_iso8601(ts) if isinstance(ts, str) else ensure_utc(ts)
    return dt.strftime("%Y-%m")


__all__ = [
    "now_utc",
    "parse_iso8601",
    "format_iso8601",
    "ensure_utc",
    "truncate_to_day",
    "is_in_window",
    "iso8601_duration_to_seconds",
    "month_key",
]
