"""Tests for :mod:`finfluencer.collect.quota`.

Pure logic over dates and JSON state files - no network, no platform
branching, no mocking of ``now_utc`` required. Day-boundary/rollover
cases are constructed by writing a fixture state file whose
``quota_day`` is computed relative to :func:`_quota_day` itself, so
tests remain deterministic regardless of what "today" actually is.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from finfluencer.collect.quota import (
    _quota_day,
    create_youtube_tracker,
    load_persisted_tracker,
    persist_tracker,
)
from finfluencer.core.contracts import QuotaConfig
from finfluencer.utils.io import write_json


def _cfg(daily_units: int = 10_000, safety_margin: int = 500) -> QuotaConfig:
    return QuotaConfig(daily_units=daily_units, safety_margin=safety_margin)


class TestQuotaDay:
    def test_explicit_now_before_reset_boundary(self):
        # 07:59 UTC is still "yesterday" under the UTC-8 reset offset.
        now = datetime(2025, 1, 2, 7, 59, tzinfo=timezone.utc)
        assert _quota_day(now).isoformat() == "2025-01-01"

    def test_explicit_now_at_reset_boundary(self):
        # 08:00 UTC is exactly the rollover instant into the new quota day.
        now = datetime(2025, 1, 2, 8, 0, tzinfo=timezone.utc)
        assert _quota_day(now).isoformat() == "2025-01-02"

    def test_default_now_uses_current_time(self):
        # No explicit `now` -> falls back to now_utc() internally.
        expected = (datetime.now(timezone.utc) - timedelta(hours=8)).date()
        assert _quota_day() == expected


class TestCreateYoutubeTracker:
    def test_builds_tracker_from_config(self):
        tracker = create_youtube_tracker(_cfg(daily_units=5000, safety_margin=100))
        assert tracker.daily_units == 5000
        assert tracker.safety_margin == 100
        assert tracker.service == "youtube_data_api_v3"
        assert tracker.used_units == 0

    def test_custom_service_name(self):
        tracker = create_youtube_tracker(_cfg(), service="custom_service")
        assert tracker.service == "custom_service"


class TestLoadPersistedTracker:
    def test_missing_state_file_returns_fresh_tracker(self, tmp_path):
        state_path = tmp_path / "quota_state.json"
        tracker = load_persisted_tracker(_cfg(), state_path)
        assert tracker.used_units == 0

    def test_corrupt_json_falls_back_to_fresh_tracker(self, tmp_path):
        state_path = tmp_path / "quota_state.json"
        state_path.write_text("{not valid json", encoding="utf-8")
        tracker = load_persisted_tracker(_cfg(), state_path)
        assert tracker.used_units == 0

    def test_rollover_day_mismatch_returns_fresh_tracker(self, tmp_path):
        state_path = tmp_path / "quota_state.json"
        write_json(
            {"quota_day": "2000-01-01", "used_units": 9000},
            state_path,
        )
        tracker = load_persisted_tracker(_cfg(daily_units=10_000), state_path)
        assert tracker.used_units == 0

    def test_same_day_restores_used_units(self, tmp_path):
        state_path = tmp_path / "quota_state.json"
        today = _quota_day().isoformat()
        write_json(
            {"quota_day": today, "used_units": 250},
            state_path,
        )
        tracker = load_persisted_tracker(_cfg(daily_units=10_000), state_path)
        assert tracker.used_units == 250

    def test_out_of_bounds_used_units_not_restored(self, tmp_path):
        state_path = tmp_path / "quota_state.json"
        today = _quota_day().isoformat()
        # used_units exceeds daily_units -> bounds check rejects it.
        write_json(
            {"quota_day": today, "used_units": 999_999},
            state_path,
        )
        tracker = load_persisted_tracker(_cfg(daily_units=10_000), state_path)
        assert tracker.used_units == 0

    def test_negative_used_units_not_restored(self, tmp_path):
        state_path = tmp_path / "quota_state.json"
        today = _quota_day().isoformat()
        write_json(
            {"quota_day": today, "used_units": -5},
            state_path,
        )
        tracker = load_persisted_tracker(_cfg(daily_units=10_000), state_path)
        assert tracker.used_units == 0

    def test_missing_used_units_key_defaults_to_zero(self, tmp_path):
        state_path = tmp_path / "quota_state.json"
        today = _quota_day().isoformat()
        write_json({"quota_day": today}, state_path)
        tracker = load_persisted_tracker(_cfg(daily_units=10_000), state_path)
        assert tracker.used_units == 0

    def test_accepts_str_path(self, tmp_path):
        state_path = tmp_path / "quota_state.json"
        tracker = load_persisted_tracker(_cfg(), str(state_path))
        assert tracker.used_units == 0


class TestPersistTracker:
    def test_writes_state_file(self, tmp_path):
        state_path = tmp_path / "quota_state.json"
        tracker = create_youtube_tracker(_cfg(daily_units=10_000, safety_margin=500))
        tracker.spend(123)

        persist_tracker(tracker, state_path)

        assert state_path.exists()
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["quota_day"] == _quota_day().isoformat()
        assert "written_at_utc" in state
        assert state["used_units"] == 123
        assert state["daily_units"] == 10_000
        assert state["service"] == "youtube_data_api_v3"

    def test_roundtrip_through_load(self, tmp_path):
        state_path = tmp_path / "quota_state.json"
        tracker = create_youtube_tracker(_cfg(daily_units=10_000, safety_margin=500))
        tracker.spend(4000)
        persist_tracker(tracker, state_path)

        reloaded = load_persisted_tracker(_cfg(daily_units=10_000, safety_margin=500), state_path)
        assert reloaded.used_units == 4000
