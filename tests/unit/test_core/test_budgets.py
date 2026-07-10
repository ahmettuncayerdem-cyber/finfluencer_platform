"""Tests for :mod:`finfluencer.core.budgets`."""

from __future__ import annotations

import pytest
from finfluencer.core.budgets import MemoryBudget, QuotaTracker
from finfluencer.core.exceptions import (
    MemoryBudgetExceededError,
    QuotaBudgetExceededError,
)


class TestMemoryBudget:
    def test_warn_mode_never_raises(self):
        with MemoryBudget(max_gb=1e-9, mode="warn", stage="t") as mb:
            mb.sample()
        # Peak recorded regardless.
        assert mb.peak_gb > 0

    def test_raise_mode_raises(self):
        with pytest.raises(MemoryBudgetExceededError):
            with MemoryBudget(max_gb=1e-9, mode="raise", stage="t") as mb:
                mb.sample()

    def test_off_mode_never_raises_or_warns(self):
        with MemoryBudget(max_gb=1e-9, mode="off", stage="t") as mb:
            mb.sample()

    def test_invalid_ceiling_rejected(self):
        with pytest.raises(ValueError):
            MemoryBudget(max_gb=0.0)


class TestQuotaTracker:
    def test_ensure_capacity_ok(self):
        qt = QuotaTracker(daily_units=100, safety_margin=10)
        qt.ensure_capacity(50)  # 50 <= 90

    def test_ensure_capacity_pre_flight_raises(self):
        qt = QuotaTracker(daily_units=100, safety_margin=10)
        qt.spend(50)
        with pytest.raises(QuotaBudgetExceededError):
            qt.ensure_capacity(50)  # 50+50=100 > 90

    def test_spend_accumulates(self):
        qt = QuotaTracker(daily_units=100, safety_margin=0)
        qt.spend(30)
        qt.spend(40)
        assert qt.used_units == 70

    def test_is_exhausted(self):
        qt = QuotaTracker(daily_units=10, safety_margin=0)
        qt.spend(10)
        assert qt.is_exhausted

    def test_reset(self):
        qt = QuotaTracker(daily_units=100, safety_margin=0)
        qt.spend(50)
        qt.reset()
        assert qt.used_units == 0

    def test_snapshot_shape(self):
        qt = QuotaTracker(daily_units=100, safety_margin=10)
        qt.spend(20)
        snap = qt.snapshot()
        assert snap["used_units"] == 20
        assert snap["effective_ceiling"] == 90
        assert snap["remaining"] == 80

    @pytest.mark.parametrize("daily,margin", [
        (0, 0), (100, 100), (100, 101),
    ])
    def test_bad_config_rejected(self, daily, margin):
        with pytest.raises(ValueError):
            QuotaTracker(daily_units=daily, safety_margin=margin)
