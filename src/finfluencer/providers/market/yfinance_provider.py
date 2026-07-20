"""
finfluencer.providers.market.yfinance_provider
================================================

Yahoo Finance provider — concrete implementation of
:class:`finfluencer.providers.market.base.MarketDataProvider` for
equity/index/FX/volatility series: BIST100, BIST Bank, USD/TRY, VIX.

Design decisions
-----------------
* **Client injection.** The actual data pull is delegated to a
  ``download_fn`` callable (default: the real ``yfinance.download``),
  mirroring the ``client_factory`` pattern used by
  ``YouTubePlatformProvider``. Tests inject a stub returning a
  synthetic DataFrame; production code lets the default run. This
  means the merge/return-computation logic in
  ``finfluencer.market.collect_market_data`` can be unit-tested without
  any network access.
* **No API key required** — Yahoo Finance's public chart endpoint
  (wrapped by the ``yfinance`` package) is unauthenticated.
* **Missing observations are omitted, never interpolated**, per the
  ``MarketDataProvider`` contract (non-trading days, data gaps).
* **yfinance is an optional dependency** (``poetry install --extras
  market``); importing this module does not require it to be
  installed, only instantiating :class:`YFinanceMarketProvider` does.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable

import pandas as pd

from finfluencer.core.exceptions import NetworkError, ResourceNotFoundError
from finfluencer.core.logging import get_logger
from finfluencer.core.registry import register
from finfluencer.utils.time import now_utc

_log = get_logger(__name__)

#: Symbol → metadata. Tickers verified against Yahoo Finance during
#: market-integration design research (see design doc Table D1).
_SYMBOL_METADATA: dict[str, dict[str, str]] = {
    "XU100.IS": {
        "name": "BIST 100 Index", "unit": "index_points", "frequency": "daily",
        "source_url": "https://finance.yahoo.com/quote/XU100.IS/history/",
    },
    "TRY=X": {
        "name": "USD/TRY exchange rate", "unit": "TRY_per_USD", "frequency": "daily",
        "source_url": "https://finance.yahoo.com/quote/TRY=X/history/",
    },
    "XBANK.IS": {
        "name": "BIST Bank Index", "unit": "index_points", "frequency": "daily",
        "source_url": "https://finance.yahoo.com/quote/XBANK.IS/history/",
    },
    "^VIX": {
        "name": "CBOE Volatility Index", "unit": "index_points", "frequency": "daily",
        "source_url": "https://finance.yahoo.com/quote/%5EVIX/history/",
    },
}


def _default_download_fn() -> Callable[..., Any]:
    """Return the real ``yfinance.download`` callable.

    Isolated in its own function (rather than a bare module-level
    import) so tests can substitute a stub without monkey-patching the
    ``yfinance`` module, and so a missing ``yfinance`` install only
    raises when a real provider is actually constructed.
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError(
            "yfinance is required for YFinanceMarketProvider. Install with "
            "`poetry install --extras market` or `pip install yfinance`."
        ) from exc
    return yf.download


@register("market", "yfinance")
class YFinanceMarketProvider:
    """Concrete Yahoo Finance implementation of ``MarketDataProvider``."""

    key: str = "yfinance"
    display_name: str = "Yahoo Finance"

    def __init__(self, *, download_fn: Callable[..., Any] | None = None) -> None:
        self._download = download_fn or _default_download_fn()

    def symbols(self) -> list[str]:
        return sorted(_SYMBOL_METADATA)

    def symbol_metadata(self, symbol: str) -> dict[str, Any]:
        if symbol not in _SYMBOL_METADATA:
            raise ResourceNotFoundError(f"Unknown yfinance symbol: {symbol!r}", symbol=symbol)
        return dict(_SYMBOL_METADATA[symbol])

    def fetch_series(self, symbol: str, *, start: date, end: date) -> pd.DataFrame:
        if symbol not in _SYMBOL_METADATA:
            raise ResourceNotFoundError(f"Unknown yfinance symbol: {symbol!r}", symbol=symbol)

        # yfinance's `end` bound is exclusive; add one day so the caller's
        # inclusive `end` date is actually returned.
        end_exclusive = end + timedelta(days=1)
        try:
            raw = self._download(
                symbol,
                start=start.isoformat(),
                end=end_exclusive.isoformat(),
                interval="1d",
                progress=False,
                auto_adjust=False,
                threads=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise NetworkError(
                f"yfinance download failed for {symbol!r}: {exc}",
                symbol=symbol, start=str(start), end=str(end),
            ) from exc

        if raw is None or raw.empty:
            _log.warning("yfinance_empty_result", symbol=symbol, start=str(start), end=str(end))
            empty = pd.DataFrame(columns=["value", "source", "retrieved_at"])
            empty.index.name = "date"
            return empty

        # Newer yfinance versions return a MultiIndex column frame even for
        # a single ticker; normalise to a flat "Close" Series.
        close = raw["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        out = pd.DataFrame({"value": close.astype(float)})
        out.index = pd.to_datetime(out.index, utc=True).normalize()
        out.index.name = "date"
        out["source"] = self.key
        out["retrieved_at"] = now_utc().isoformat()
        return out.dropna(subset=["value"]).sort_index()


__all__ = ["YFinanceMarketProvider"]
