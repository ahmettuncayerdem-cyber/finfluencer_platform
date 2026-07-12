"""
finfluencer.core.budgets
=========================

Memory and API-quota budget accounting.

Two kinds of budget
-------------------
:class:`MemoryBudget`
    Context manager that samples resident memory at entry and periodically
    during a stage. Raises :class:`MemoryBudgetExceededError` when a
    configured ceiling is crossed (in ``raise`` mode) or logs a warning
    (in ``warn`` mode).

:class:`QuotaTracker`
    Running counter for API units consumed against a daily quota
    (Methods §3.2.4). Provides :meth:`spend` (attribute) and
    :meth:`ensure_capacity` (pre-flight); raises
    :class:`QuotaBudgetExceededError` pre-emptively so callers can
    checkpoint and exit cleanly rather than crash on 403.

Neither module enforces at operating-system level; both are cooperative.
Callers must invoke the budget methods; the budget cannot magically
intercept malloc or HTTP calls.
"""

from __future__ import annotations

import os
from types import TracebackType
from typing import Literal

from finfluencer.core.exceptions import (
    MemoryBudgetExceededError,
    QuotaBudgetExceededError,
)
from finfluencer.core.logging import get_logger


_log = get_logger(__name__)


BudgetMode = Literal["raise", "warn", "off"]


# =============================================================================
# Memory budget
# =============================================================================


def _current_memory_gb() -> float:
    """Return the current process's resident set size in gigabytes.

    Cross-platform implementation with graceful fallback chain:
    1. Prefer ``psutil.Process().memory_info().rss`` — works identically
       on Linux, macOS, and Windows.
    2. Fall back to POSIX ``resource.getrusage`` when psutil is not
       installed (preserves the pre-Batch-4 behaviour on POSIX).
    3. Return ``0.0`` when neither is available (Windows without psutil)
       — memory tracking becomes a no-op rather than an ``AttributeError``.

    The zero fallback is safe: MemoryBudget compares ``current > max_gb``,
    so a zero reading means "budget never triggers" — a warning is
    logged once so operators know memory telemetry is off.
    """
    # 1. Preferred path: psutil (cross-platform, accurate RSS)
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024**3)
    except ImportError:
        pass
    except Exception:  # noqa: BLE001
        # psutil imported but process access failed (very rare)
        pass

    # 2. Fallback: POSIX resource module
    try:
        import resource as _resource  # POSIX-only; ImportError on Windows
        ru = _resource.getrusage(_resource.RUSAGE_SELF)
        # macOS reports bytes; Linux reports kilobytes.
        if hasattr(os, "uname") and os.uname().sysname == "Darwin":
            return ru.ru_maxrss / (1024**3)
        return ru.ru_maxrss / (1024**2)
    except ImportError:
        pass

    # 3. Last resort: no memory tracking available.
    # Warn once per process so this is not silent.
    global _MEMORY_TRACKING_WARNED
    if not _MEMORY_TRACKING_WARNED:
        _log.warning(
            "memory_tracking_unavailable",
            reason="neither psutil nor POSIX resource module available",
            action="memory_budget_disabled_returning_zero",
        )
        _MEMORY_TRACKING_WARNED = True
    return 0.0


_MEMORY_TRACKING_WARNED: bool = False


class MemoryBudget:
    """Track peak memory against a ceiling.

    Usage::

        with MemoryBudget(max_gb=8.0, mode="raise", stage="embedding"):
            model.encode(documents)
    """

    def __init__(
        self,
        max_gb: float,
        *,
        mode: BudgetMode = "warn",
        stage: str = "unknown",
    ) -> None:
        if max_gb <= 0:
            raise ValueError(f"max_gb must be positive, got {max_gb}")
        self.max_gb: float = max_gb
        self.mode: BudgetMode = mode
        self.stage: str = stage
        self.baseline_gb: float = 0.0
        self.peak_gb: float = 0.0

    def __enter__(self) -> "MemoryBudget":
        self.baseline_gb = _current_memory_gb()
        self.peak_gb = self.baseline_gb
        return self

    def sample(self) -> float:
        """Sample current memory and update peak. Raise/warn if over."""
        current = _current_memory_gb()
        if current > self.peak_gb:
            self.peak_gb = current
        if current > self.max_gb and self.mode != "off":
            msg = f"Memory budget exceeded in stage {self.stage}"
            if self.mode == "raise":
                raise MemoryBudgetExceededError(
                    msg,
                    stage=self.stage,
                    used_gb=round(current, 2),
                    limit_gb=self.max_gb,
                )
            _log.warning(
                "memory_budget_exceeded",
                stage=self.stage,
                used_gb=round(current, 2),
                limit_gb=self.max_gb,
            )
        return current

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            self.sample()
        finally:
            _log.info(
                "memory_budget_summary",
                stage=self.stage,
                baseline_gb=round(self.baseline_gb, 2),
                peak_gb=round(self.peak_gb, 2),
                limit_gb=self.max_gb,
            )


# =============================================================================
# API quota tracker
# =============================================================================


class QuotaTracker:
    """Running counter for API units against a daily quota.

    The tracker does not know about time-of-day resets; callers must
    reset it at day boundaries or checkpoint when it flags exhaustion.
    """

    def __init__(
        self,
        *,
        daily_units: int,
        safety_margin: int,
        service: str = "youtube_data_api_v3",
    ) -> None:
        if daily_units < 1:
            raise ValueError(f"daily_units must be >= 1, got {daily_units}")
        if safety_margin < 0:
            raise ValueError(f"safety_margin must be >= 0, got {safety_margin}")
        if safety_margin >= daily_units:
            raise ValueError("safety_margin must be less than daily_units")
        self.daily_units: int = daily_units
        self.safety_margin: int = safety_margin
        self.service: str = service
        self.used_units: int = 0

    @property
    def remaining(self) -> int:
        return self.daily_units - self.used_units

    @property
    def effective_ceiling(self) -> int:
        return self.daily_units - self.safety_margin

    @property
    def is_exhausted(self) -> bool:
        return self.used_units >= self.effective_ceiling

    def ensure_capacity(self, units: int) -> None:
        """Raise :class:`QuotaBudgetExceededError` if this call would
        cross the effective ceiling. Pre-flight check; does not mutate.
        """
        if self.used_units + units > self.effective_ceiling:
            raise QuotaBudgetExceededError(
                f"API quota would be exhausted by upcoming call",
                service=self.service,
                used=self.used_units,
                would_use=units,
                effective_ceiling=self.effective_ceiling,
                daily_units=self.daily_units,
            )

    def spend(self, units: int) -> None:
        """Record that ``units`` of quota have been consumed.

        Called *after* a successful API call, not before. If units would
        exceed the ceiling, :meth:`ensure_capacity` should have caught it
        first; if not (e.g. a call was pre-authorised but consumed more),
        we log and continue — the API itself will 403 shortly.
        """
        if units < 0:
            raise ValueError(f"spend: units must be >= 0, got {units}")
        self.used_units += units
        if self.used_units > self.effective_ceiling:
            _log.warning(
                "quota_ceiling_crossed",
                service=self.service,
                used=self.used_units,
                effective_ceiling=self.effective_ceiling,
            )

    def reset(self) -> None:
        """Reset the counter (call at daily rollover)."""
        self.used_units = 0

    def snapshot(self) -> dict[str, int | str]:
        """Return a dict suitable for logging or provenance."""
        return {
            "service": self.service,
            "used_units": self.used_units,
            "daily_units": self.daily_units,
            "effective_ceiling": self.effective_ceiling,
            "safety_margin": self.safety_margin,
            "remaining": self.remaining,
        }


__all__ = [
    "BudgetMode",
    "MemoryBudget",
    "QuotaTracker",
]
