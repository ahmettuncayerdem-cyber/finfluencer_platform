"""Tests for the market-data providers and the collect_market_data orchestrator.

These tests never touch the network. Provider HTTP/download calls are
stubbed via dependency injection (``download_fn`` / ``http_client`` /
the ``providers=`` kwarg on the orchestrator functions), mirroring the
``client_factory`` injection pattern used for
``YouTubePlatformProvider`` tests elsewhere in this suite. This keeps
the merge / log-return / schema logic deterministically testable
without EVDS_API_KEY or outbound internet access.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.exceptions import DataError, ResourceNotFoundError
from finfluencer.core.registry import get, list_registered
from finfluencer.market.collect_market_data import (
    SERIES_SPEC,
    build_market_panel,
    determine_observation_window,
)
from finfluencer.providers.market.tcmb_evds_provider import TCMBEvdsMarketProvider
from finfluencer.providers.market.yfinance_provider import YFinanceMarketProvider


@pytest.fixture(autouse=True)
def _ensure_market_providers_registered(_reset_registry):
    """conftest.py's ``_reset_registry`` (autouse) wipes the provider
    registry before every test and only re-imports the language
    subpackage. Depending on it explicitly here guarantees this runs
    AFTER that wipe.

    Reloading the submodules (not just the ``providers.market``
    package) matters: once ``yfinance_provider``/``tcmb_evds_provider``
    are already in ``sys.modules`` (from this file's top-level imports
    at collection time), re-importing the parent package's
    ``__init__.py`` only rebinds the cached module objects -- it does
    NOT re-execute their top-level code, so the ``@register(...)``
    class decorators never re-run and the registry stays empty.
    Reloading the submodules directly forces that re-execution.
    """
    import importlib

    from finfluencer.providers.market import tcmb_evds_provider, yfinance_provider

    importlib.reload(yfinance_provider)
    importlib.reload(tcmb_evds_provider)
    yield


def test_yfinance_and_evds_registered_under_market_kind():
    assert ("market", "yfinance") in list_registered("market")
    assert ("market", "tcmb_evds") in list_registered("market")
    # Compare by name/key rather than identity (`is`): the autouse
    # fixture above uses importlib.reload() to force re-registration,
    # which creates a fresh class object distinct from the one this
    # test file imported at collection time. Functional equivalence
    # (same key, same qualified name) is what actually matters here.
    yf_cls = get("market", "yfinance")
    evds_cls = get("market", "tcmb_evds")
    assert yf_cls.__name__ == "YFinanceMarketProvider"
    assert yf_cls.key == "yfinance"
    assert evds_cls.__name__ == "TCMBEvdsMarketProvider"
    assert evds_cls.key == "tcmb_evds"


class TestYFinanceMarketProvider:
    def test_symbols_and_metadata(self):
        p = YFinanceMarketProvider(download_fn=lambda *a, **kw: pd.DataFrame())
        assert "XU100.IS" in p.symbols()
        meta = p.symbol_metadata("XU100.IS")
        assert meta["unit"] == "index_points"

    def test_unknown_symbol_raises(self):
        p = YFinanceMarketProvider(download_fn=lambda *a, **kw: pd.DataFrame())
        with pytest.raises(ResourceNotFoundError):
            p.symbol_metadata("NOT_A_SYMBOL")

    def test_fetch_series_normalises_multiindex_close_column(self):
        idx = pd.date_range("2025-01-01", periods=5, freq="D")
        raw = pd.DataFrame(
            {("Close", "XU100.IS"): [100.0, 101.0, 99.0, 102.0, 103.0]}, index=idx,
        )
        raw.columns = pd.MultiIndex.from_tuples(raw.columns)

        def stub_download(*args, **kwargs):
            return raw

        p = YFinanceMarketProvider(download_fn=stub_download)
        out = p.fetch_series("XU100.IS", start=date(2025, 1, 1), end=date(2025, 1, 5))
        assert list(out.columns) == ["value", "source", "retrieved_at"]
        assert len(out) == 5
        assert out["value"].iloc[0] == 100.0

    def test_empty_download_returns_empty_frame_not_an_error(self):
        p = YFinanceMarketProvider(download_fn=lambda *a, **kw: pd.DataFrame())
        out = p.fetch_series("TRY=X", start=date(2025, 1, 1), end=date(2025, 1, 5))
        assert out.empty


class TestTCMBEvdsMarketProvider:
    def test_requires_api_key(self, monkeypatch):
        monkeypatch.delenv("EVDS_API_KEY", raising=False)
        with pytest.raises(Exception):
            TCMBEvdsMarketProvider(api_key=None)

    def test_series_discovery_matches_gram_and_altin_tokens(self):
        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload
                self.status_code = 200

            def json(self):
                return self._payload

        class FakeClient:
            def get(self, path, params=None):
                if path == "categories/":
                    return FakeResponse([{"CATEGORY_ID": 1, "TOPIC_TITLE_TR": "PIYASA VERILERI"}])
                if path == "datagroups/":
                    return FakeResponse([{"DATAGROUP_CODE": "bie_mkaltytl"}])
                if path == "serieList/":
                    return FakeResponse([
                        {"SERIE_CODE": "TP.MK.SOMETHING", "SERIE_NAME": "Ounce gold price"},
                        {"SERIE_CODE": "TP.MK.GRAMALTIN", "SERIE_NAME": "Gram Altin (TL)"},
                    ])
                raise AssertionError(f"unexpected path {path}")

            def close(self):
                pass

        p = TCMBEvdsMarketProvider(api_key="test_key", http_client=FakeClient())
        code = p._resolve_series_code("gram_gold_try")
        assert code == "TP.MK.GRAMALTIN"

    def test_discovery_raises_rather_than_guessing_when_no_match(self):
        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def json(self):
                return self._payload

            status_code = 200

        class FakeClientNoMatch:
            def get(self, path, params=None):
                if path == "categories/":
                    return FakeResponse([{"CATEGORY_ID": 1, "TOPIC_TITLE_TR": "X"}])
                if path == "datagroups/":
                    return FakeResponse([{"DATAGROUP_CODE": "dg"}])
                if path == "serieList/":
                    return FakeResponse([{"SERIE_CODE": "TP.X", "SERIE_NAME": "Unrelated series"}])
                raise AssertionError(path)

            def close(self):
                pass

        p = TCMBEvdsMarketProvider(api_key="test_key", http_client=FakeClientNoMatch())
        with pytest.raises(ResourceNotFoundError):
            p._resolve_series_code("gram_gold_try")


class _StubProvider:
    """Deterministic synthetic price series for offline orchestration tests."""

    def __init__(self, base_value: float, dates: pd.DatetimeIndex, seed: int):
        rng = np.random.default_rng(seed)
        rets = rng.normal(0, 0.01, size=len(dates))
        prices = base_value * np.exp(np.cumsum(rets))
        self._df = pd.DataFrame(
            {"value": prices, "source": "stub", "retrieved_at": "test"},
            index=pd.DatetimeIndex(dates, name="date"),
        )

    def fetch_series(self, symbol, *, start, end):
        return self._df.copy()


class TestBuildMarketPanel:
    def _make_series(self, n_days=30):
        dates = pd.bdate_range("2025-01-01", periods=n_days)
        series = {}
        for i, (prefix, _, _) in enumerate(SERIES_SPEC):
            series[prefix] = _StubProvider(100 + i * 10, dates, seed=i).fetch_series(
                "x", start=dates[0], end=dates[-1],
            )
        return series

    def test_schema_and_column_order(self):
        panel = build_market_panel(self._make_series())
        expected = ["date"] + [
            f"{prefix}_{suffix}"
            for prefix, _, _ in SERIES_SPEC
            for suffix in ("close", "return")
        ]
        assert list(panel.columns) == expected

    def test_log_return_matches_manual_computation(self):
        panel = build_market_panel(self._make_series())
        manual = np.log(panel["xu100_close"] / panel["xu100_close"].shift(1))
        pd.testing.assert_series_equal(panel["xu100_return"], manual, check_names=False)

    def test_only_first_row_return_is_nan(self):
        panel = build_market_panel(self._make_series())
        assert panel["xu100_return"].isna().sum() == 1
        assert panel["xu100_return"].isna().iloc[0]

    def test_require_complete_raises_on_partial_series(self):
        series = self._make_series()
        series["gold"] = pd.DataFrame(columns=["value", "source", "retrieved_at"])
        with pytest.raises(DataError, match="silently-partial"):
            build_market_panel(series, require_complete=True)

    def test_allow_partial_when_require_complete_false(self):
        series = self._make_series()
        series["gold"] = pd.DataFrame(columns=["value", "source", "retrieved_at"])
        panel = build_market_panel(series, require_complete=False)
        assert "gold_close" not in panel.columns
        assert "xu100_close" in panel.columns

    def test_all_empty_raises(self):
        empty = pd.DataFrame(columns=["value", "source", "retrieved_at"])
        series = {prefix: empty for prefix, _, _ in SERIES_SPEC}
        with pytest.raises(DataError):
            build_market_panel(series)


class TestDetermineObservationWindow:
    def test_window_derived_from_comments_parquet(self, tmp_path):
        comments = pd.DataFrame({
            "posted_date": pd.to_datetime(["2025-01-02", "2025-06-15", "2025-12-31"]),
        })
        path = tmp_path / "comments.parquet"
        comments.to_parquet(path)

        start, end = determine_observation_window(path, buffer_days=10)
        assert end == date(2025, 12, 31)
        assert start == date(2024, 12, 23)

    def test_missing_posted_date_column_raises(self, tmp_path):
        path = tmp_path / "comments.parquet"
        pd.DataFrame({"other_col": [1, 2, 3]}).to_parquet(path)
        with pytest.raises(DataError):
            determine_observation_window(path)
