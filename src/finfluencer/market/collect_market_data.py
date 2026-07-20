"""
finfluencer.market.collect_market_data
========================================

Reproducible market-data collection module - minimal confirmatory
scope (BIST100 only) for the Borsa Istanbul Review submission.

This module is a completely independent downstream stage. It reads
``data/raw/comments.parquet`` ONLY to determine the observation window
(read-only; never writes to ``data/raw/`` or any existing pipeline
output). It writes exactly one new artefact:

    data/market/market_data.parquet

with columns::

    date, xu100_close, xu100_return

Returns are natural-log returns, ``r_t = ln(P_t / P_{t-1})``.

Scope note
----------
Earlier drafts of this module also fetched USD/TRY, BIST Bank, gram
gold, and VIX (see git history / the shelved
``finfluencer_tr_2025_market_integration_design.docx``). Per an
explicit scope decision, this module now fetches BIST100 ONLY - no
other market variables, no multi-market model. The TCMB EVDS provider
class remains in ``finfluencer.providers.market`` as general
infrastructure but is not invoked here.

Usage
-----
    python -m finfluencer.market.collect_market_data \\
        --comments-path data/raw/comments.parquet \\
        --output data/market/market_data.parquet \\
        --buffer-days 10

Requires
--------
* ``yfinance`` installed (``poetry install --extras market``).
* Outbound network access to finance.yahoo.com.

This module performs NO fallback to synthetic or simulated data if
network access is unavailable or the provider call fails - it raises
rather than fabricate market figures. This is a deliberate scientific-
integrity constraint, not an oversight.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Importing this subpackage runs the @register("market", ...) decorators
# on YFinanceMarketProvider / TCMBEvdsMarketProvider. Required so that
# registry.instantiate("market", ...) below can find them when this
# module is invoked standalone (e.g. `python -m finfluencer.market.collect_market_data`)
# rather than via a caller that already imported the providers package.
import finfluencer.providers.market  # noqa: F401
from finfluencer.core.exceptions import DataError
from finfluencer.core.logging import get_logger
from finfluencer.core.registry import instantiate
from finfluencer.utils.io import ensure_parent, read_parquet, write_json, write_parquet

_log = get_logger(__name__)

#: (output_prefix, provider_kind, symbol). BIST100 only - minimal
#: confirmatory scope. Order here determines the column order in the
#: final parquet (close, return per series).
SERIES_SPEC: list[tuple[str, str, str]] = [
    ("xu100", "yfinance", "XU100.IS"),
]


def determine_observation_window(
    comments_path: Path, *, buffer_days: int = 10,
) -> tuple[date, date]:
    """Read ``comments.parquet`` (read-only) and return a padded ``(start, end)``.

    The buffer ensures the first log return inside the actual coverage
    window is computable (a return needs one prior observation) without
    hardcoding a project-external start date; it is derived entirely
    from the corpus itself.
    """
    df = read_parquet(comments_path)
    if "posted_date" not in df.columns:
        raise DataError(
            "comments.parquet missing 'posted_date' column; cannot determine window",
            path=str(comments_path), columns=list(df.columns),
        )
    dates = pd.to_datetime(df["posted_date"])
    raw_min, raw_max = dates.min().date(), dates.max().date()
    start = raw_min - timedelta(days=buffer_days)
    end = raw_max
    _log.info(
        "observation_window_determined",
        start=str(start), end=str(end), raw_min=str(raw_min), raw_max=str(raw_max),
        buffer_days=buffer_days,
    )
    return start, end


def _log_return(close: pd.Series) -> pd.Series:
    return np.log(close / close.shift(1))


def fetch_all_series(
    start: date, end: date, *, providers: dict[str, object] | None = None,
) -> dict[str, pd.DataFrame]:
    """Fetch each configured series via its registered ``MarketDataProvider``.

    ``providers`` allows injecting pre-built provider instances (e.g.
    ones constructed with a stub ``download_fn``/``http_client``) for
    offline, deterministic testing of the merge/return logic below.
    Production callers leave it ``None``; providers are then
    instantiated from ``core.registry`` (which requires ``yfinance``
    to be installed).
    """
    out: dict[str, pd.DataFrame] = {}
    cache: dict[str, object] = dict(providers or {})
    for prefix, kind, symbol in SERIES_SPEC:
        if kind not in cache:
            cache[kind] = instantiate("market", kind)
        provider = cache[kind]
        _log.info("fetching_series", prefix=prefix, kind=kind, symbol=symbol,
                  start=str(start), end=str(end))
        out[prefix] = provider.fetch_series(symbol, start=start, end=end)
    return out


def build_market_panel(
    series: dict[str, pd.DataFrame], *, require_complete: bool = True,
) -> pd.DataFrame:
    """Merge fetched series onto a shared date index and compute log returns.

    ``require_complete`` (default ``True``) raises :class:`DataError`
    if ANY configured series came back empty, rather than silently
    dropping that series' columns from the output. This matters
    specifically because some HTTP client libraries (observed with
    ``yfinance`` against a restrictive network proxy) catch connection
    errors internally and return an empty result instead of raising -
    without this check, ``market_data.parquet`` could otherwise be
    written silently missing entire series with no visible error. Set
    ``require_complete=False`` only for deliberate partial/exploratory
    runs, never for the confirmatory analysis.
    """
    frames = []
    empty_prefixes = []
    for prefix, df in series.items():
        if df.empty:
            _log.warning("empty_series_in_panel", prefix=prefix)
            empty_prefixes.append(prefix)
            continue
        s = df["value"].rename(f"{prefix}_close")
        idx = pd.to_datetime(s.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        s.index = idx.normalize()
        frames.append(s)

    if not frames:
        raise DataError("No series returned any data; cannot build market_data.parquet")

    if require_complete and empty_prefixes:
        raise DataError(
            "One or more configured series returned no data; refusing to write a "
            "silently-partial market_data.parquet. This usually means a provider "
            "call failed without raising (e.g. yfinance swallowing a proxy/network "
            "error) rather than a genuine absence of trading data. Pass "
            "require_complete=False to override for a deliberate partial run.",
            empty_series=empty_prefixes,
        )

    panel = pd.concat(frames, axis=1).sort_index()
    panel = panel[~panel.index.duplicated(keep="last")]
    panel.index.name = "date"

    for prefix in series:
        col = f"{prefix}_close"
        if col in panel.columns:
            panel[f"{prefix}_return"] = _log_return(panel[col])

    ordered_cols = [
        f"{prefix}_{suffix}"
        for prefix, _, _ in SERIES_SPEC
        for suffix in ("close", "return")
        if f"{prefix}_{suffix}" in panel.columns
    ]
    return panel[ordered_cols].reset_index()


def collect(
    *,
    comments_path: Path = Path("data/raw/comments.parquet"),
    output_path: Path = Path("data/market/market_data.parquet"),
    buffer_days: int = 10,
    providers: dict[str, object] | None = None,
    require_complete: bool = True,
) -> pd.DataFrame:
    """End-to-end: determine window -> fetch -> merge/compute returns -> write.

    Returns the panel DataFrame (also written to ``output_path``) so
    callers/tests can inspect it without re-reading the parquet.
    """
    start, end = determine_observation_window(comments_path, buffer_days=buffer_days)
    series = fetch_all_series(start, end, providers=providers)
    panel = build_market_panel(series, require_complete=require_complete)

    ensure_parent(output_path)
    write_parquet(panel, output_path)

    manifest = {
        "output": str(output_path),
        "n_rows": int(len(panel)),
        "date_min": str(panel["date"].min().date()) if not panel.empty else None,
        "date_max": str(panel["date"].max().date()) if not panel.empty else None,
        "requested_window": {"start": str(start), "end": str(end)},
        "series_coverage_n_obs": {
            prefix: int(series[prefix]["value"].notna().sum())
            if prefix in series and not series[prefix].empty else 0
            for prefix, _, _ in SERIES_SPEC
        },
        "provider_kinds": sorted({kind for _, kind, _ in SERIES_SPEC}),
    }
    write_json(manifest, Path(str(output_path).replace(".parquet", "_manifest.json")))
    _log.info("market_data_collection_complete", n_rows=manifest["n_rows"],
              date_min=manifest["date_min"], date_max=manifest["date_max"])
    return panel


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Collect daily BIST100 market data (minimal confirmatory scope)."
    )
    parser.add_argument("--comments-path", type=Path, default=Path("data/raw/comments.parquet"))
    parser.add_argument("--output", type=Path, default=Path("data/market/market_data.parquet"))
    parser.add_argument("--buffer-days", type=int, default=10)
    parser.add_argument(
        "--allow-partial", action="store_true",
        help="Write market_data.parquet even if the series returned no data. "
             "Never use this for the pre-specified confirmatory analysis.",
    )
    args = parser.parse_args()
    panel = collect(comments_path=args.comments_path, output_path=args.output,
                     buffer_days=args.buffer_days, require_complete=not args.allow_partial)
    print(f"Wrote {len(panel)} rows to {args.output}")


if __name__ == "__main__":
    _cli()
