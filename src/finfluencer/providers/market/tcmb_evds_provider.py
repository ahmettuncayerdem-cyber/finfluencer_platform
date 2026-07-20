"""
finfluencer.providers.market.tcmb_evds_provider
=================================================

TCMB EVDS (Elektronik Veri Dağıtım Sistemi) provider — concrete
implementation of :class:`finfluencer.providers.market.base.MarketDataProvider`
for the gram-gold (TRY) series.

Design decisions
-----------------
* **Raw REST calls via httpx**, not the third-party ``evds`` PyPI
  wrapper — httpx is already a platform dependency (see pyproject.toml)
  and using it directly keeps every HTTP call auditable in this file,
  which matters for a peer-reviewed research pipeline.
* **Series code discovered at query time, never hardcoded.** EVDS
  gram-gold series codes are not stably documented outside the EVDS
  web UI; guessing a code (e.g. an unverified "TP.MK.ALTIN.TL") risks
  silently pulling the wrong series. Instead, :meth:`_discover_series_code`
  walks EVDS's own category → datagroup → series hierarchy and matches
  on a case-insensitive Turkish substring search over series names,
  raising :class:`finfluencer.core.exceptions.ResourceNotFoundError`
  with the categories inspected if nothing matches, rather than
  falling back to a guess. The discovered code is logged and cached
  in-memory for the life of the instance (one discovery call per run,
  not per date range).
* **Legacy SSL renegotiation.** EVDS's server requires the
  ``OP_LEGACY_SERVER_CONNECT`` option on some OpenSSL builds or the TLS
  handshake fails; this is a known, independently-documented quirk of
  the EVDS3 endpoint (see the community ``evds`` package's
  ``legacySSL`` flag). Reproduced here via a custom ``ssl.SSLContext``
  passed to httpx; disable via ``legacy_ssl=False`` if your environment
  does not need it.
* **API key required** — read from the ``EVDS_API_KEY`` environment
  variable unless passed explicitly, following this platform's
  ``<PREFIX>_API_KEY`` convention (cf. ``YT_API_KEY``). Free
  registration: https://evds3.tcmb.gov.tr/ → "Bana Özel" → Kayıt Ol.
"""

from __future__ import annotations

import os
import ssl
from datetime import date
from typing import Any

import httpx
import pandas as pd

from finfluencer.core.exceptions import (
    AuthenticationError,
    NetworkError,
    ProviderConfigurationError,
    ResourceNotFoundError,
)
from finfluencer.core.logging import get_logger
from finfluencer.core.registry import register
from finfluencer.utils.time import now_utc

_log = get_logger(__name__)

_BASE_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"

#: Symbols this provider serves. Only gram gold is in scope for the
#: reduced-scope confirmatory analysis (design doc Table D1); other
#: EVDS-sourced series (USD/TRY buy/sell, CDS) can be added the same
#: way by extending this dict and the discovery keyword list below.
_SYMBOL_METADATA: dict[str, dict[str, str]] = {
    "gram_gold_try": {
        "name": "Gram gold price (TRY)", "unit": "TRY_per_gram", "frequency": "daily",
        "source_url": "https://evds3.tcmb.gov.tr/",
    },
}

#: Case-insensitive Turkish substrings a matching series name must all
#: contain. "gram" + "altın" together identify the per-gram gold price
#: series and exclude e.g. ounce-denominated or index series.
_GOLD_SERIES_NAME_TOKENS = ("gram", "altın")


def _fold_tr(s: str) -> str:
    """Lowercase + fold Turkish dotless/dotted I variants to plain ASCII "i".

    EVDS series names are not guaranteed to use proper Turkish
    typography consistently (e.g. "Altın" vs the ASCII-typed "Altin"
    both appear across TCMB's own data exports). Python's ``str.lower()``
    without a Turkish locale does not equate "ı" and "i", so a naive
    substring match would silently miss a real series and fall through
    to the "could not discover" error. Folding both the tokens and the
    candidate series name through this function before comparison makes
    discovery robust to that inconsistency without weakening the "never
    guess a code" guarantee — matching is still exact substring matching,
    just on a normalised alphabet.
    """
    return (
        s.lower()
        .replace("ı", "i")
        .replace("İ", "i")
        .replace("I", "i")
    )


#: Category/datagroup names to search, in priority order, before
#: falling back to a full category scan. Narrows the common case to a
#: handful of HTTP calls instead of walking the entire EVDS tree.
_CANDIDATE_CATEGORY_HINTS = ("piyasa", "kur")


def _legacy_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
    return ctx


@register("market", "tcmb_evds")
class TCMBEvdsMarketProvider:
    """Concrete TCMB EVDS implementation of ``MarketDataProvider``."""

    key: str = "tcmb_evds"
    display_name: str = "TCMB EVDS"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        legacy_ssl: bool = True,
        http_client: httpx.Client | None = None,
    ) -> None:
        api_key = api_key or os.environ.get("EVDS_API_KEY", "")
        if not api_key:
            raise AuthenticationError(
                "TCMB EVDS API key not provided; set EVDS_API_KEY env or pass "
                "api_key=. Free registration at https://evds3.tcmb.gov.tr/."
            )
        self._api_key = api_key
        verify: Any = _legacy_ssl_context() if legacy_ssl else True
        self._client = http_client or httpx.Client(
            base_url=_BASE_URL, headers={"key": api_key}, verify=verify, timeout=30.0,
        )
        self._series_code_cache: dict[str, str] = {}

    # -- MarketDataProvider interface --------------------------------------

    def symbols(self) -> list[str]:
        return sorted(_SYMBOL_METADATA)

    def symbol_metadata(self, symbol: str) -> dict[str, Any]:
        if symbol not in _SYMBOL_METADATA:
            raise ResourceNotFoundError(f"Unknown EVDS symbol: {symbol!r}", symbol=symbol)
        return dict(_SYMBOL_METADATA[symbol])

    def fetch_series(self, symbol: str, *, start: date, end: date) -> pd.DataFrame:
        if symbol not in _SYMBOL_METADATA:
            raise ResourceNotFoundError(f"Unknown EVDS symbol: {symbol!r}", symbol=symbol)

        series_code = self._resolve_series_code(symbol)
        payload = self._get_json(
            "",
            params={
                "series": series_code,
                "startDate": start.strftime("%d-%m-%Y"),
                "endDate": end.strftime("%d-%m-%Y"),
                "type": "json",
                "frequency": "1",  # daily
            },
        )
        items = payload.get("items", [])
        if not items:
            _log.warning("evds_empty_result", symbol=symbol, series_code=series_code,
                         start=str(start), end=str(end))
            empty = pd.DataFrame(columns=["value", "source", "retrieved_at"])
            empty.index.name = "date"
            return empty

        col = series_code.replace(".", "_")
        df = pd.DataFrame(items)
        if col not in df.columns:
            raise NetworkError(
                f"EVDS response missing expected column {col!r} for series {series_code!r}",
                series_code=series_code, columns=list(df.columns),
            )
        df["date"] = pd.to_datetime(df["Tarih"], format="%d-%m-%Y", utc=True).dt.normalize()
        df["value"] = pd.to_numeric(df[col], errors="coerce")
        out = df.set_index("date")[["value"]]
        out["source"] = self.key
        out["retrieved_at"] = now_utc().isoformat()
        return out.dropna(subset=["value"]).sort_index()

    # -- Series discovery ----------------------------------------------------

    def _resolve_series_code(self, symbol: str) -> str:
        if symbol in self._series_code_cache:
            return self._series_code_cache[symbol]
        if symbol == "gram_gold_try":
            code = self._discover_series_code(_GOLD_SERIES_NAME_TOKENS)
        else:  # pragma: no cover — guarded by symbols() check upstream
            raise ResourceNotFoundError(f"No discovery rule for symbol: {symbol!r}", symbol=symbol)
        self._series_code_cache[symbol] = code
        _log.info("evds_series_code_resolved", symbol=symbol, series_code=code)
        return code

    def _discover_series_code(self, name_tokens: tuple[str, ...]) -> str:
        """Walk EVDS categories → datagroups → series to find a matching code.

        Never returns a hardcoded guess. Raises ``ResourceNotFoundError``
        with the full list of categories inspected if no series name
        contains every token in ``name_tokens`` (case-insensitive,
        Turkish-locale-aware lowering).
        """
        categories = self._get_json("categories/", params={"type": "json"})
        if isinstance(categories, dict):
            categories = categories.get("items", categories)
        inspected: list[str] = []

        # Priority pass: categories whose title hints at markets/rates.
        ordered = sorted(
            categories,
            key=lambda c: 0 if any(h in str(c.get("TOPIC_TITLE_TR", "")).lower()
                                    for h in _CANDIDATE_CATEGORY_HINTS) else 1,
        )
        for cat in ordered:
            cat_id = cat.get("CATEGORY_ID")
            inspected.append(str(cat.get("TOPIC_TITLE_TR", cat_id)))
            datagroups = self._get_json("datagroups/", params={"mode": 2, "code": cat_id, "type": "json"})
            if isinstance(datagroups, dict):
                datagroups = datagroups.get("items", [])
            for dg in datagroups or []:
                dg_code = dg.get("DATAGROUP_CODE")
                if not dg_code:
                    continue
                series_list = self._get_json("serieList/", params={"type": "json", "code": dg_code})
                if isinstance(series_list, dict):
                    series_list = series_list.get("items", [])
                for s in series_list or []:
                    sname = _fold_tr(str(s.get("SERIE_NAME", "")))
                    if all(_fold_tr(tok) in sname for tok in name_tokens):
                        return s["SERIE_CODE"]

        raise ResourceNotFoundError(
            "Could not discover an EVDS series matching name tokens "
            f"{name_tokens!r} after searching {len(inspected)} categories. "
            "Verify the series exists at https://evds3.tcmb.gov.tr/tumSeriler "
            "and adjust _GOLD_SERIES_NAME_TOKENS if the naming has changed.",
            tokens=name_tokens, categories_inspected=inspected,
        )

    # -- HTTP plumbing ---------------------------------------------------------

    def _get_json(self, path: str, *, params: dict[str, Any]) -> Any:
        try:
            resp = self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise NetworkError(f"EVDS request failed: {exc}", path=path, params=params) from exc
        if resp.status_code == 401 or resp.status_code == 403:
            raise AuthenticationError(
                "EVDS rejected the API key (401/403). Check EVDS_API_KEY.",
                status_code=resp.status_code,
            )
        if resp.status_code != 200:
            raise NetworkError(
                f"EVDS returned HTTP {resp.status_code} for {path!r}",
                status_code=resp.status_code, path=path,
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise ProviderConfigurationError(
                f"EVDS response for {path!r} was not valid JSON", path=path,
            ) from exc

    def close(self) -> None:
        self._client.close()


__all__ = ["TCMBEvdsMarketProvider"]
