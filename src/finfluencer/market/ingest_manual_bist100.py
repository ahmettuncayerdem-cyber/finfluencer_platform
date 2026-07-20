"""
finfluencer.market.ingest_manual_bist100
===========================================

One-off, documented, reproducible ingestion of a MANUALLY-downloaded
BIST100 (XU100.IS) daily OHLC file, used ONLY because this deployment
environment's outbound network access to finance.yahoo.com is blocked
by a sandbox proxy allowlist (confirmed repeatedly: HTTP 403 Forbidden
via both direct requests and the yfinance-backed
``finfluencer.market.collect_market_data`` module).

The source file was downloaded by the study author directly from
Yahoo Finance (https://finance.yahoo.com/quote/XU100.IS/history/,
Jan 1, 2025 - Dec 31, 2025, daily frequency) in their own browser and
uploaded for ingestion. This is the SAME series
``collect_market_data.py`` would have fetched automatically had
network access been available; this script performs the identical
normalisation (comma-formatted numbers -> float, string dates ->
datetime, ascending date order, natural-log returns) and writes to the
SAME output schema, so downstream code
(``sentiment_index.py``, ``confirmatory_analysis.py``) is agnostic to
which ingestion path produced ``market_data.parquet``.

This is disclosed explicitly (not silently substituted for the
automated path) because it is a material methods detail for the
eventual manuscript: data provenance is "Yahoo Finance, manually
retrieved by the author," not "programmatically fetched."
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from finfluencer.core.exceptions import DataError
from finfluencer.core.logging import get_logger
from finfluencer.utils.io import ensure_parent, write_json, write_parquet

_log = get_logger(__name__)


def _parse_yahoo_number(series: pd.Series) -> pd.Series:
    """Yahoo Finance's exported numbers use comma thousands separators
    (e.g. "11,249.70") and are read as strings/objects; strip and cast."""
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


def ingest_manual_bist100_xlsx(
    source_path: Path,
    *,
    output_path: Path = Path("data/market/market_data.parquet"),
) -> pd.DataFrame:
    """Read a manually-downloaded Yahoo-Finance-format BIST100 file
    (accepts .xlsx despite a possible .csv filename - Excel "Save As
    CSV" from a pasted web table sometimes actually writes xlsx bytes,
    which is what this specific upload turned out to be) and write
    ``market_data.parquet`` with columns: date, xu100_close, xu100_return.

    Raises if the expected columns are missing or if, after parsing,
    fewer than 10 valid rows remain - the same "don't silently proceed
    on bad/insufficient data" discipline as the rest of this module.
    """
    source_path = Path(source_path)
    try:
        raw = pd.read_excel(source_path)
    except Exception as exc:  # noqa: BLE001
        raise DataError(
            f"Could not read {source_path} as an Excel file: {exc}", path=str(source_path),
        ) from exc

    raw.columns = [str(c).strip() for c in raw.columns]
    close_col = next((c for c in raw.columns if c.lower().startswith("close")), None)
    if "Date" not in raw.columns or close_col is None:
        raise DataError(
            "Expected 'Date' and a 'Close' column in the source file",
            path=str(source_path), columns=list(raw.columns),
        )

    df = pd.DataFrame({
        "date": pd.to_datetime(raw["Date"], format="%b %d, %Y", errors="coerce"),
        "xu100_close": _parse_yahoo_number(raw[close_col]),
    })
    n_before = len(df)
    df = df.dropna(subset=["date", "xu100_close"]).drop_duplicates(subset=["date"])
    if len(df) < n_before:
        _log.warning("manual_bist100_rows_dropped_on_parse",
                      n_dropped=n_before - len(df), n_remaining=len(df))

    df = df.sort_values("date").reset_index(drop=True)
    df["xu100_return"] = np.log(df["xu100_close"] / df["xu100_close"].shift(1))

    if len(df) < 10:
        raise DataError(f"Only {len(df)} valid BIST100 rows parsed; too few to proceed",
                         n_rows=len(df))

    ensure_parent(output_path)
    write_parquet(df, output_path)

    manifest = {
        "output": str(output_path),
        "source": "Yahoo Finance (finance.yahoo.com/quote/XU100.IS/history/), "
                   "manually retrieved by the author due to sandbox network restrictions",
        "source_file": str(source_path),
        "ingestion_method": "manual_download_then_local_ingest",
        "n_rows": int(len(df)),
        "date_min": str(df["date"].min().date()),
        "date_max": str(df["date"].max().date()),
    }
    write_json(manifest, Path(str(output_path).replace(".parquet", "_manifest.json")))
    _log.info("manual_bist100_ingested", n_rows=len(df),
              date_min=manifest["date_min"], date_max=manifest["date_max"])
    return df


__all__ = ["ingest_manual_bist100_xlsx"]
