"""
finfluencer.providers.market.base
==================================

Protocol for market-data providers.

A ``MarketDataProvider`` fetches a time series (BIST 100, USD/TRY,
gold, CPI, etc.) and returns it as a normalised pandas DataFrame with
a UTC-aware DatetimeIndex. Concrete implementations in Phase 2:
``TCMB EVDS``, ``TÜİK``, ``BIST``, ``CryptoCoinbase``.

MVP-B: bases only; concrete implementations arrive in Phase 2 and are
consumed by Module D (Market Integration Engine).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class MarketDataProvider(Protocol):
    """Structural interface for market time-series providers.

    All timestamps in returned DataFrames are UTC-aware. Series values
    are floats; missing values are ``NaN``. Providers cache retrieved
    series content-addressably under ``cache/market/<provider>/<key>/``.
    """

    #: Registry key, e.g. ``"tcmb_evds"``, ``"bist"``, ``"tuik"``.
    key: str

    #: Human-readable name for reports.
    display_name: str

    def symbols(self) -> list[str]:
        """Return the list of symbols this provider can serve."""
        ...

    def symbol_metadata(self, symbol: str) -> dict[str, Any]:
        """Return metadata for a symbol.

        Fields must include: ``name``, ``unit``, ``frequency``
        (``"daily"``, ``"weekly"``, ``"monthly"``), ``source_url``.
        """
        ...

    def fetch_series(
        self,
        symbol: str,
        *,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        """Fetch a time series for ``symbol`` over ``[start, end]``.

        Returns a DataFrame with columns:

        * ``date`` : UTC-aware datetime, index
        * ``value`` : float, the observation
        * ``source`` : str, provider key (for provenance)
        * ``retrieved_at`` : ISO 8601 UTC, when the value was fetched

        Missing observations (weekends, holidays) are omitted rather
        than interpolated; interpolation is the analytical layer's
        decision, not the provider's.
        """
        ...


__all__ = ["MarketDataProvider"]
