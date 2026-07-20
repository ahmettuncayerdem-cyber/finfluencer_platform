"""Offline tests for the minimal market-integration confirmatory analysis.

No network access, no real market data required. Synthetic panels are
constructed with a KNOWN statistical structure so the tests verify
correctness of the statistics themselves, not just that the code runs.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.exceptions import DataError
from finfluencer.market.confirmatory_analysis import (
    GRANGER_LAGS,
    build_analysis_panel,
    descriptive_table,
    granger_table,
    regression_table,
    run_confirmatory_analysis,
)
from finfluencer.market.figures import plot_sentiment_vs_bist100
from finfluencer.market.sentiment_index import build_pooled_sentiment_index


class TestBuildPooledSentimentIndex:
    def _write_inputs(self, tmp_path):
        market_data = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-03", "2025-01-06", "2025-01-07"]),
            "xu100_close": [100.0, 101.0, 102.0],
            "xu100_return": [np.nan, 0.00995, 0.00985],
        })
        market_data_path = tmp_path / "market_data.parquet"
        market_data.to_parquet(market_data_path)

        comments = pd.DataFrame({
            "comment_id": ["c1", "c2", "c3", "c4"],
            "posted_date": pd.to_datetime([
                "2025-01-03", "2025-01-04", "2025-01-05", "2025-01-07",
            ]),
        })
        comments_path = tmp_path / "comments.parquet"
        comments.to_parquet(comments_path)

        sentiment = pd.DataFrame({
            "comment_id": ["c1", "c2", "c3", "c4"],
            "sentiment_prob": [0.9, 0.2, 0.4, 0.6],
        })
        sentiment_path = tmp_path / "sentiment.parquet"
        sentiment.to_parquet(sentiment_path)

        return comments_path, sentiment_path, market_data_path

    def test_weekend_comments_forward_map_to_next_trading_day(self, tmp_path):
        comments_path, sentiment_path, market_data_path = self._write_inputs(tmp_path)
        out_path = tmp_path / "sentiment_index_daily.parquet"

        daily = build_pooled_sentiment_index(
            comments_path=comments_path, sentiment_path=sentiment_path,
            market_data_path=market_data_path, output_path=out_path,
        )

        daily = daily.set_index("trading_date")
        assert daily.loc[pd.Timestamp("2025-01-03"), "sentiment_index"] == pytest.approx(0.9)
        assert daily.loc[pd.Timestamp("2025-01-03"), "n_comments"] == 1
        assert daily.loc[pd.Timestamp("2025-01-06"), "sentiment_index"] == pytest.approx(0.3)
        assert daily.loc[pd.Timestamp("2025-01-06"), "n_comments"] == 2
        assert daily.loc[pd.Timestamp("2025-01-07"), "sentiment_index"] == pytest.approx(0.6)

    def test_missing_market_data_raises(self, tmp_path):
        comments_path, sentiment_path, _ = self._write_inputs(tmp_path)
        with pytest.raises(DataError):
            build_pooled_sentiment_index(
                comments_path=comments_path, sentiment_path=sentiment_path,
                market_data_path=tmp_path / "does_not_exist.parquet",
                output_path=tmp_path / "out.parquet",
            )


def _synthetic_panel(n=120, seed=0, causal_strength=0.6, direction="x_causes_y"):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-01", periods=n)

    if direction == "x_causes_y":
        x = rng.normal(0.5, 0.1, size=n)
        y = np.zeros(n)
        for t in range(1, n):
            y[t] = causal_strength * (x[t - 1] - 0.5) + 0.05 * rng.normal()
        y[0] = 0.05 * rng.normal()
    else:
        x = rng.normal(0.5, 0.1, size=n)
        y = 0.01 * rng.normal(size=n)

    return pd.DataFrame({
        "date": dates, "sentiment_index": np.clip(x, 0, 1),
        "n_comments": rng.integers(1, 20, size=n),
        "xu100_close": 100 * np.exp(np.cumsum(y)),
        "xu100_return": y,
    })


class TestBuildAnalysisPanel:
    def test_inner_join_and_dropna(self, tmp_path):
        pad_dates = pd.bdate_range("2025-02-01", periods=12)
        edge_dates = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])

        idx = pd.DataFrame({
            "trading_date": list(edge_dates) + list(pad_dates),
            "sentiment_index": [0.5, 0.6, np.nan] + [0.5] * 12,
            "n_comments": [3, 4, 2] + [5] * 12,
        })
        idx_path = tmp_path / "idx.parquet"
        idx.to_parquet(idx_path)

        mkt_dates = list(edge_dates) + [pd.Timestamp("2025-01-07")] + list(pad_dates)
        mkt = pd.DataFrame({
            "date": mkt_dates,
            "xu100_close": [100.0 + i for i in range(len(mkt_dates))],
            "xu100_return": [np.nan, 0.00995, 0.00985, 0.0098] + [0.001] * 12,
        })
        mkt_path = tmp_path / "mkt.parquet"
        mkt.to_parquet(mkt_path)

        panel = build_analysis_panel(sentiment_index_path=idx_path, market_data_path=mkt_path)
        result_dates = set(panel["date"].dt.strftime("%Y-%m-%d"))
        assert "2025-01-03" in result_dates
        assert "2025-01-02" not in result_dates
        assert "2025-01-06" not in result_dates
        assert "2025-01-07" not in result_dates
        assert len(panel) == 1 + 12

    def test_too_few_rows_raises(self, tmp_path):
        idx = pd.DataFrame({
            "trading_date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "sentiment_index": [0.5, 0.6], "n_comments": [3, 4],
        })
        idx_path = tmp_path / "idx.parquet"
        idx.to_parquet(idx_path)
        mkt = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "xu100_close": [100.0, 101.0], "xu100_return": [np.nan, 0.01],
        })
        mkt_path = tmp_path / "mkt.parquet"
        mkt.to_parquet(mkt_path)
        with pytest.raises(DataError):
            build_analysis_panel(sentiment_index_path=idx_path, market_data_path=mkt_path)


class TestDescriptiveTable:
    def test_schema_and_values(self):
        panel = _synthetic_panel(n=100, direction="independent")
        desc = descriptive_table(panel)
        assert set(desc["series"]) == {"Pooled sentiment index", "BIST100 daily log return"}
        assert {"n", "mean", "sd", "min", "max", "adf_statistic", "adf_p_value",
                "stationary_at_5pct"} <= set(desc.columns)
        assert (desc["n"] == 100).all()


class TestGrangerDirectionCorrectness:
    def test_true_causal_direction_is_detected_significant(self):
        panel = _synthetic_panel(n=200, seed=1, causal_strength=0.8, direction="x_causes_y")
        results = run_confirmatory_analysis(panel)
        granger = results["granger"]

        row = granger[(granger["direction"] == "sentiment_index -> xu100_return")
                       & (granger["lag"] == 1)].iloc[0]
        assert row["p_value"] < 0.01

    def test_reverse_of_true_direction_is_not_spuriously_strong(self):
        panel = _synthetic_panel(n=200, seed=1, causal_strength=0.8, direction="x_causes_y")
        results = run_confirmatory_analysis(panel)
        granger = results["granger"]

        true_p = granger[(granger["direction"] == "sentiment_index -> xu100_return")
                          & (granger["lag"] == 1)].iloc[0]["p_value"]
        reverse_p = granger[(granger["direction"] == "xu100_return -> sentiment_index")
                             & (granger["lag"] == 1)].iloc[0]["p_value"]
        assert true_p < reverse_p

    def test_independent_series_show_no_strong_granger_signal(self):
        panel = _synthetic_panel(n=200, seed=2, direction="independent")
        results = run_confirmatory_analysis(panel)
        granger = results["granger"]
        lag1 = granger[granger["lag"] == 1]
        assert (lag1["p_value"] > 0.01).all()

    def test_granger_output_has_all_lags_both_directions(self):
        panel = _synthetic_panel(n=150, seed=3, direction="independent")
        results = run_confirmatory_analysis(panel)
        granger = results["granger"]
        assert set(granger["lag"]) == set(GRANGER_LAGS)
        assert set(granger["direction"]) == {
            "sentiment_index -> xu100_return", "xu100_return -> sentiment_index",
        }
        assert len(granger) == 2 * len(GRANGER_LAGS)

    def test_granger_table_matches_results_granger(self):
        panel = _synthetic_panel(n=150, seed=3, direction="independent")
        results = run_confirmatory_analysis(panel)
        gt = granger_table(results)
        pd.testing.assert_frame_equal(gt, results["granger"])


class TestCorrelationAndOLS:
    def test_pearson_spearman_positive_when_positively_related(self):
        rng = np.random.default_rng(4)
        n = 150
        x = rng.normal(0.5, 0.1, n)
        y = 0.5 * (x - 0.5) + 0.01 * rng.normal(size=n)
        panel = pd.DataFrame({
            "date": pd.bdate_range("2025-01-01", periods=n),
            "sentiment_index": np.clip(x, 0, 1), "n_comments": 5,
            "xu100_close": 100 * np.exp(np.cumsum(y)), "xu100_return": y,
        })
        results = run_confirmatory_analysis(panel)
        assert results["pearson"]["r"] > 0.5
        assert results["pearson"]["p_value"] < 0.001
        assert results["spearman"]["rho"] > 0.5
        assert results["ols"]["sentiment_coef"] > 0
        assert results["ols"]["cov_type"] == "HAC (Newey-West)"

    def test_regression_table_schema(self):
        panel = _synthetic_panel(n=100, direction="independent")
        results = run_confirmatory_analysis(panel)
        reg = regression_table(results)
        assert {"statistic", "value", "p_value", "n"} <= set(reg.columns)
        # Pearson, Spearman, OLS const, OLS sentiment coef, OLS R-squared.
        # Granger now lives in its own dedicated table (granger_table),
        # not folded into regression_table.
        assert len(reg) == 5
        assert "Granger" not in " ".join(reg["statistic"])


class TestFigure:
    def test_creates_a_real_png(self, tmp_path):
        panel = _synthetic_panel(n=60, direction="independent")
        out = tmp_path / "fig.png"
        result_path = plot_sentiment_vs_bist100(panel, output_path=out)
        assert result_path == out
        assert out.exists()
        assert out.stat().st_size > 1000

    def test_empty_panel_raises(self, tmp_path):
        with pytest.raises(DataError):
            plot_sentiment_vs_bist100(pd.DataFrame(), output_path=tmp_path / "fig.png")
