"""Tests for :mod:`finfluencer.market.run_confirmatory_analysis`.

This module is a thin CLI orchestrator: it calls into
``confirmatory_analysis.py``, ``figures.py``, and ``sentiment_index.py``
(all already covered at 95%+ by their own dedicated test modules) and
writes their outputs to disk. These tests therefore verify the
*wiring* - correct arguments passed through, correct files written,
correct return value - by substituting small, fully-controlled fakes
for the six analysis functions rather than re-deriving statistical
correctness that is already tested elsewhere.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import finfluencer.market.run_confirmatory_analysis as run_mod


def _install_fakes(monkeypatch, *, desc_df, reg_df, granger_df, results, calls):
    def fake_build_pooled_sentiment_index(*, comments_path, sentiment_path,
                                           market_data_path, output_path):
        calls["build_pooled_sentiment_index"] = {
            "comments_path": comments_path,
            "sentiment_path": sentiment_path,
            "market_data_path": market_data_path,
            "output_path": output_path,
        }

    def fake_build_analysis_panel(*, sentiment_index_path, market_data_path):
        calls["build_analysis_panel"] = {
            "sentiment_index_path": sentiment_index_path,
            "market_data_path": market_data_path,
        }
        return "PANEL_SENTINEL"

    def fake_descriptive_table(panel):
        calls["descriptive_table_panel"] = panel
        return desc_df

    def fake_run_confirmatory_analysis(panel):
        calls["run_confirmatory_analysis_panel"] = panel
        return results

    def fake_regression_table(res):
        calls["regression_table_results"] = res
        return reg_df

    def fake_granger_table(res):
        calls["granger_table_results"] = res
        return granger_df

    def fake_plot(panel, *, output_path):
        calls["plot"] = {"panel": panel, "output_path": output_path}
        return output_path

    monkeypatch.setattr(run_mod, "build_pooled_sentiment_index", fake_build_pooled_sentiment_index)
    monkeypatch.setattr(run_mod, "build_analysis_panel", fake_build_analysis_panel)
    monkeypatch.setattr(run_mod, "descriptive_table", fake_descriptive_table)
    monkeypatch.setattr(run_mod, "run_confirmatory_analysis", fake_run_confirmatory_analysis)
    monkeypatch.setattr(run_mod, "regression_table", fake_regression_table)
    monkeypatch.setattr(run_mod, "granger_table", fake_granger_table)
    monkeypatch.setattr(run_mod, "plot_sentiment_vs_bist100", fake_plot)


class TestMain:
    def test_orchestrates_pipeline_and_writes_expected_artifacts(self, tmp_path, monkeypatch):
        desc_df = pd.DataFrame({"variable": ["sentiment_index"], "mean": [0.12]})
        reg_df = pd.DataFrame({"term": ["const"], "coef": [0.01]})
        granger_df = pd.DataFrame({"lag": [1], "p_value": [0.05]})
        results = {"n_obs": 42, "granger": {"p": 0.05}, "ols": {"r2": 0.3}}
        calls: dict = {}
        _install_fakes(monkeypatch, desc_df=desc_df, reg_df=reg_df,
                        granger_df=granger_df, results=results, calls=calls)

        output_dir = tmp_path / "out"
        comments_path = tmp_path / "comments.parquet"
        sentiment_path = tmp_path / "sentiment.parquet"
        market_data_path = tmp_path / "market_data.parquet"
        sentiment_index_path = tmp_path / "sentiment_index_daily.parquet"

        result = run_mod.main(
            comments_path=comments_path,
            sentiment_path=sentiment_path,
            market_data_path=market_data_path,
            sentiment_index_path=sentiment_index_path,
            output_dir=output_dir,
        )

        # Return value is exactly what run_confirmatory_analysis produced.
        assert result is results

        # Output directory created.
        assert output_dir.is_dir()

        # All four artefacts written.
        assert (output_dir / "Table1_descriptive_statistics.csv").exists()
        assert (output_dir / "Table2_OLS_regression.csv").exists()
        assert (output_dir / "Table3_granger_causality.csv").exists()
        assert (output_dir / "confirmatory_analysis_summary.json").exists()

        # Arguments correctly threaded through the pipeline.
        assert calls["build_pooled_sentiment_index"] == {
            "comments_path": comments_path,
            "sentiment_path": sentiment_path,
            "market_data_path": market_data_path,
            "output_path": sentiment_index_path,
        }
        assert calls["build_analysis_panel"] == {
            "sentiment_index_path": sentiment_index_path,
            "market_data_path": market_data_path,
        }
        assert calls["descriptive_table_panel"] == "PANEL_SENTINEL"
        assert calls["run_confirmatory_analysis_panel"] == "PANEL_SENTINEL"
        assert calls["regression_table_results"] == results
        assert calls["granger_table_results"] == results
        assert calls["plot"]["panel"] == "PANEL_SENTINEL"
        assert calls["plot"]["output_path"] == output_dir / "Figure_sentiment_vs_bist100.png"

    def test_summary_json_excludes_granger_key(self, tmp_path, monkeypatch):
        desc_df = pd.DataFrame({"variable": ["x"], "mean": [1.0]})
        reg_df = pd.DataFrame({"term": ["const"], "coef": [0.1]})
        granger_df = pd.DataFrame({"lag": [1], "p_value": [0.2]})
        results = {"n_obs": 7, "granger": {"p": 0.2}, "ols": {"r2": 0.5}}
        calls: dict = {}
        _install_fakes(monkeypatch, desc_df=desc_df, reg_df=reg_df,
                        granger_df=granger_df, results=results, calls=calls)

        output_dir = tmp_path / "out"
        run_mod.main(
            comments_path=tmp_path / "c.parquet",
            sentiment_path=tmp_path / "s.parquet",
            market_data_path=tmp_path / "m.parquet",
            sentiment_index_path=tmp_path / "idx.parquet",
            output_dir=output_dir,
        )

        summary = json.loads(
            (output_dir / "confirmatory_analysis_summary.json").read_text(encoding="utf-8"),
        )
        assert summary["n_obs"] == 7
        assert summary["ols"] == {"r2": 0.5}
        assert "granger" not in summary

    def test_default_paths_used_when_omitted(self, tmp_path, monkeypatch):
        # Run inside tmp_path so the relative default paths don't touch the
        # real repo, and mock everything so no real input files are needed.
        monkeypatch.chdir(tmp_path)
        desc_df = pd.DataFrame({"variable": ["x"], "mean": [1.0]})
        reg_df = pd.DataFrame({"term": ["const"], "coef": [0.1]})
        granger_df = pd.DataFrame({"lag": [1], "p_value": [0.2]})
        results = {"n_obs": 5, "granger": {}, "ols": {}}
        calls: dict = {}
        _install_fakes(monkeypatch, desc_df=desc_df, reg_df=reg_df,
                        granger_df=granger_df, results=results, calls=calls)

        run_mod.main()

        assert (tmp_path / "outputs" / "market").is_dir()
        assert calls["build_pooled_sentiment_index"]["comments_path"] == Path("data/raw/comments.parquet")
        assert calls["build_pooled_sentiment_index"]["market_data_path"] == Path("data/market/market_data.parquet")


class TestCli:
    def test_parses_explicit_args_and_calls_main(self, tmp_path, monkeypatch):
        captured: dict = {}

        def fake_main(*, comments_path, sentiment_path, market_data_path, output_dir):
            captured.update(
                comments_path=comments_path, sentiment_path=sentiment_path,
                market_data_path=market_data_path, output_dir=output_dir,
            )
            return {}

        monkeypatch.setattr(run_mod, "main", fake_main)
        argv = [
            "prog",
            "--comments-path", str(tmp_path / "c.parquet"),
            "--sentiment-path", str(tmp_path / "s.parquet"),
            "--market-data-path", str(tmp_path / "m.parquet"),
            "--output-dir", str(tmp_path / "out"),
        ]
        monkeypatch.setattr("sys.argv", argv)

        run_mod._cli()

        assert captured["comments_path"] == tmp_path / "c.parquet"
        assert captured["sentiment_path"] == tmp_path / "s.parquet"
        assert captured["market_data_path"] == tmp_path / "m.parquet"
        assert captured["output_dir"] == tmp_path / "out"

    def test_defaults_used_when_no_args_given(self, monkeypatch):
        captured: dict = {}

        def fake_main(*, comments_path, sentiment_path, market_data_path, output_dir):
            captured.update(
                comments_path=comments_path, sentiment_path=sentiment_path,
                market_data_path=market_data_path, output_dir=output_dir,
            )
            return {}

        monkeypatch.setattr(run_mod, "main", fake_main)
        monkeypatch.setattr("sys.argv", ["prog"])

        run_mod._cli()

        assert captured["comments_path"] == Path("data/raw/comments.parquet")
        assert captured["sentiment_path"] == Path("data/processed/sentiment.parquet")
        assert captured["market_data_path"] == Path("data/market/market_data.parquet")
        assert captured["output_dir"] == Path("outputs/market")
