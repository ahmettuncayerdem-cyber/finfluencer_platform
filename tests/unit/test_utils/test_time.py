"""Tests for :mod:`finfluencer.utils.time`."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from finfluencer.utils.time import (
    ensure_utc,
    format_iso8601,
    is_in_window,
    iso8601_duration_to_seconds,
    month_key,
    now_utc,
    parse_iso8601,
    truncate_to_day,
)


class TestParseIso8601:
    def test_youtube_z_suffix(self):
        dt = parse_iso8601("2025-04-17T13:22:05Z")
        assert dt.tzinfo is timezone.utc

    def test_explicit_offset(self):
        dt = parse_iso8601("2025-04-17T13:22:05+03:00")
        assert dt.tzinfo is timezone.utc
        assert dt.hour == 10  # converted to UTC

    def test_rejects_naive(self):
        with pytest.raises(ValueError, match="naive"):
            parse_iso8601("2025-04-17T13:22:05")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            parse_iso8601("")

    def test_rejects_garbage(self):
        with pytest.raises(ValueError):
            parse_iso8601("banana")


class TestFormatIso8601:
    def test_roundtrip(self):
        s = "2025-04-17T13:22:05Z"
        assert format_iso8601(parse_iso8601(s)) == s

    def test_rejects_naive(self):
        with pytest.raises(ValueError):
            format_iso8601(datetime(2025, 4, 17, 13, 22, 5))


class TestTruncateToDay:
    def test_from_string(self):
        assert truncate_to_day("2025-04-17T13:22:05Z") == "2025-04-17"

    def test_from_datetime(self):
        dt = datetime(2025, 4, 17, 13, 22, 5, tzinfo=timezone.utc)
        assert truncate_to_day(dt) == "2025-04-17"

    def test_rejects_naive_datetime(self):
        with pytest.raises(ValueError):
            truncate_to_day(datetime(2025, 4, 17))


class TestIsInWindow:
    def test_inclusive_bounds(self):
        assert is_in_window("2025-01-01T00:00:00Z", "2025-01-01", "2025-12-31")
        # End-of-day expansion for bare-date end
        assert is_in_window("2025-12-31T23:59:00Z", "2025-01-01", "2025-12-31")

    def test_before_start(self):
        assert not is_in_window("2024-12-31T23:59:00Z", "2025-01-01", "2025-12-31")

    def test_after_end(self):
        assert not is_in_window("2026-01-01T00:00:00Z", "2025-01-01", "2025-12-31")


class TestDurationParsing:
    @pytest.mark.parametrize("s,expected", [
        ("", 0),
        ("PT45S", 45),
        ("PT1M", 60),
        ("PT1M30S", 90),
        ("PT1H", 3600),
        ("PT1H30M", 5400),
        ("garbage", 0),
    ])
    def test_iso_duration(self, s, expected):
        assert iso8601_duration_to_seconds(s) == expected

    def test_shorts_threshold(self):
        # Anything <= 60s should be classified as a Short.
        assert iso8601_duration_to_seconds("PT60S") == 60
        assert iso8601_duration_to_seconds("PT59S") == 59


def test_now_utc_is_aware():
    n = now_utc()
    assert n.tzinfo is not None


def test_ensure_utc_naive_rejected():
    with pytest.raises(ValueError):
        ensure_utc(datetime(2025, 1, 1))


def test_month_key():
    assert month_key("2025-04-17T00:00:00Z") == "2025-04"
