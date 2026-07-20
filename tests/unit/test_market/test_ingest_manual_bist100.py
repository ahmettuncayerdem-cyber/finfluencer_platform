"""Tests for :mod:`finfluencer.market.ingest_manual_bist100`.

No network access required. Source files are synthetic .xlsx fixtures
built in-memory with pandas, matching the exact shape of a manually
downloaded Yahoo Finance BIST100 (XU100.IS) history export: a "Date"
column formatted like "Jan 03, 2025" and a comma-thousands "Close*"
column (Yahoo Finance actually exports "Close/Last Adjusted Close" or
similar, hence the "starts with Close" matching in production code).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.exceptions import DataError
from finfluencer.market.ingest_manual_bist100 import (
    _parse_yahoo_number,
    ingest_manual_bist100_xlsx,
)


def _yahoo_dates(n: int) -> list[str]:
    """Business-day dates formatted like Yahoo Finance's export
    (e.g. "Jan 03, 2025"), oldest first."""
    dates = pd.bdate_range("2025-01-01", periods=n)
    return [d.strftime("%b %d, %Y") for d in dates]


def _write_source_xlsx(tmp_path, *, dates, closes, date_col="Date", close_col="Close"):
    df = pd.DataFrame({date_col: dates, close_col: closes})
    path = tmp_path / "source.xlsx"
    df.to_excel(path, index=False)
    return path


class TestParseYahooNumber:
    def test_strips_comma_thousands_separator(self):
        result = _parse_yahoo_number(pd.Series(["11,249.70"]))
        assert result.iloc[0] == pytest.approx(11249.70)

    def test_already_clean_float_strings(self):
        result = _parse_yahoo_number(pd.Series(["102.5"]))
        assert result.iloc[0] == pytest.approx(102.5)

    def test_non_numeric_junk_coerces_to_nan(self):
        result = _parse_yahoo_number(pd.Series(["not-a-number"]))
        assert pd.isna(result.iloc[0])

    def test_strips_surrounding_whitespace(self):
        result = _parse_yahoo_number(pd.Series([" 1,000.00 "]))
        assert result.iloc[0] == pytest.approx(1000.0)


class TestIngestManualBist100Xlsx:
    def test_happy_path_writes_parquet_and_manifest(self, tmp_path):
        dates = _yahoo_dates(12)
        # Yahoo-style closes: comma thousands separator, dot decimals.
        closes = [f"{9000 + i * 10:,.2f}" for i in range(12)]
        source = _write_source_xlsx(tmp_path, dates=dates, closes=closes)
        output_path = tmp_path / "out" / "market_data.parquet"

        df = ingest_manual_bist100_xlsx(source, output_path=output_path)

        assert output_path.exists()
        manifest_path = tmp_path / "out" / "market_data_manifest.json"
        assert manifest_path.exists()

        assert list(df.columns) == ["date", "xu100_close", "xu100_return"]
        assert len(df) == 12
        # Ascending date order.
        assert df["date"].is_monotonic_increasing
        # First return is NaN (no prior day), rest are populated log returns.
        assert pd.isna(df["xu100_return"].iloc[0])
        assert not df["xu100_return"].iloc[1:].isna().any()

    def test_manifest_contents(self, tmp_path):
        dates = _yahoo_dates(10)
        closes = [f"{9000 + i:,.2f}" for i in range(10)]
        source = _write_source_xlsx(tmp_path, dates=dates, closes=closes)
        output_path = tmp_path / "market_data.parquet"

        df = ingest_manual_bist100_xlsx(source, output_path=output_path)

        import json
        manifest = json.loads(
            (tmp_path / "market_data_manifest.json").read_text(encoding="utf-8"),
        )
        assert manifest["n_rows"] == len(df) == 10
        assert manifest["date_min"] == str(df["date"].min().date())
        assert manifest["date_max"] == str(df["date"].max().date())
        assert manifest["source_file"] == str(source)
        assert manifest["ingestion_method"] == "manual_download_then_local_ingest"

    def test_close_column_matched_case_insensitively_by_prefix(self, tmp_path):
        # Production code matches any column whose lowercased name starts
        # with "close" (e.g. Yahoo's actual "Close/Last Adjusted Close").
        dates = _yahoo_dates(10)
        closes = [f"{9000 + i:,.2f}" for i in range(10)]
        source = _write_source_xlsx(
            tmp_path, dates=dates, closes=closes, close_col="Close/Last Adjusted Close",
        )
        output_path = tmp_path / "market_data.parquet"

        df = ingest_manual_bist100_xlsx(source, output_path=output_path)
        assert len(df) == 10

    def test_rows_with_unparseable_date_or_close_are_dropped(self, tmp_path):
        dates = _yahoo_dates(12)
        closes = [f"{9000 + i:,.2f}" for i in range(12)]
        # Corrupt one date and one close value so they fail to parse.
        dates[2] = "not-a-date"
        closes[5] = "garbage"
        source = _write_source_xlsx(tmp_path, dates=dates, closes=closes)
        output_path = tmp_path / "market_data.parquet"

        df = ingest_manual_bist100_xlsx(source, output_path=output_path)
        # 12 rows minus 2 corrupted rows = 10, exactly at the boundary.
        assert len(df) == 10

    def test_duplicate_dates_are_deduplicated(self, tmp_path):
        dates = _yahoo_dates(11)
        dates[1] = dates[0]  # introduce a duplicate date
        closes = [f"{9000 + i:,.2f}" for i in range(11)]
        source = _write_source_xlsx(tmp_path, dates=dates, closes=closes)
        output_path = tmp_path / "market_data.parquet"

        df = ingest_manual_bist100_xlsx(source, output_path=output_path)
        # 11 rows, one duplicate date collapsed -> 10 remain.
        assert len(df) == 10
        assert df["date"].is_unique

    def test_source_file_not_readable_as_excel_raises_data_error(self, tmp_path):
        bad_source = tmp_path / "not_really_excel.xlsx"
        bad_source.write_text("this is plain text, not an xlsx file", encoding="utf-8")

        with pytest.raises(DataError, match="Could not read"):
            ingest_manual_bist100_xlsx(bad_source, output_path=tmp_path / "out.parquet")

    def test_missing_date_column_raises_data_error(self, tmp_path):
        df = pd.DataFrame({"NotDate": _yahoo_dates(10), "Close": [1.0] * 10})
        source = tmp_path / "source.xlsx"
        df.to_excel(source, index=False)

        with pytest.raises(DataError, match="Expected 'Date'"):
            ingest_manual_bist100_xlsx(source, output_path=tmp_path / "out.parquet")

    def test_missing_close_column_raises_data_error(self, tmp_path):
        df = pd.DataFrame({"Date": _yahoo_dates(10), "Open": [1.0] * 10})
        source = tmp_path / "source.xlsx"
        df.to_excel(source, index=False)

        with pytest.raises(DataError, match="Expected 'Date'"):
            ingest_manual_bist100_xlsx(source, output_path=tmp_path / "out.parquet")

    def test_exactly_ten_valid_rows_succeeds_at_boundary(self, tmp_path):
        dates = _yahoo_dates(10)
        closes = [f"{9000 + i:,.2f}" for i in range(10)]
        source = _write_source_xlsx(tmp_path, dates=dates, closes=closes)

        df = ingest_manual_bist100_xlsx(source, output_path=tmp_path / "out.parquet")
        assert len(df) == 10

    def test_nine_valid_rows_raises_data_error(self, tmp_path):
        dates = _yahoo_dates(9)
        closes = [f"{9000 + i:,.2f}" for i in range(9)]
        source = _write_source_xlsx(tmp_path, dates=dates, closes=closes)

        with pytest.raises(DataError, match="too few to proceed"):
            ingest_manual_bist100_xlsx(source, output_path=tmp_path / "out.parquet")

    def test_return_is_log_return_of_close(self, tmp_path):
        dates = _yahoo_dates(10)
        closes = [100.0 * (1.01 ** i) for i in range(10)]
        closes_str = [f"{c:,.2f}" for c in closes]
        source = _write_source_xlsx(tmp_path, dates=dates, closes=closes_str)

        df = ingest_manual_bist100_xlsx(source, output_path=tmp_path / "out.parquet")
        expected_return = np.log(closes[1] / closes[0])
        assert df["xu100_return"].iloc[1] == pytest.approx(expected_return, rel=1e-3)

    def test_output_path_default_is_used_when_not_specified(self, tmp_path, monkeypatch):
        # Avoid writing to the real default relative path; run inside tmp_path.
        monkeypatch.chdir(tmp_path)
        dates = _yahoo_dates(10)
        closes = [f"{9000 + i:,.2f}" for i in range(10)]
        source = _write_source_xlsx(tmp_path, dates=dates, closes=closes)

        ingest_manual_bist100_xlsx(source)

        assert (tmp_path / "data" / "market" / "market_data.parquet").exists()
        assert (tmp_path / "data" / "market" / "market_data_manifest.json").exists()

    def test_accepts_str_source_path(self, tmp_path):
        dates = _yahoo_dates(10)
        closes = [f"{9000 + i:,.2f}" for i in range(10)]
        source = _write_source_xlsx(tmp_path, dates=dates, closes=closes)
        output_path = tmp_path / "market_data.parquet"

        df = ingest_manual_bist100_xlsx(str(source), output_path=output_path)
        assert len(df) == 10
