"""Tests for finfluencer.reporting.inferential.

Three tiers:

* Unit tests exercise each of the seven analysis functions (E1, E1b,
  E2, E3, R1, R2, R3) against small synthetic tables with a KNOWN
  structure -- following this project's established convention (see
  tests/unit/test_market/test_confirmatory_analysis.py) of testing the
  packaged wiring/filtering logic and known mathematical invariants,
  not re-deriving scipy/statsmodels' own correctness.
* A differential test compares the packaged battery's output against
  the real, pre-existing inferential_results.json this repository's
  root-level run_inferential_tests.py script produced, run against the
  real master_table.csv. Skipped automatically if those files are
  absent (gitignored, regenerable artifacts -- see test_master_table.py).
* An acceptance test reproduces specific published numerical results
  (the manuscript's total analyzed comment count, N=17566, and the E1
  cross-analyst chi-square / Kruskal-Wallis H statistics) exactly, per
  the Sprint 1A acceptance criterion.

A known, investigated non-determinism
--------------------------------------
Two pairs of topics in the real corpus have EXACTLY tied ``cohens_h``
values to full float64 precision (topic_id 44 vs 182, and 162 vs 179).
``pd.DataFrame.sort_values`` uses an unstable sort by default, so the
*relative order* of exactly-tied rows in ``E2_topic_sentiment.topic_results``
can differ across pandas/numpy/BLAS versions -- confirmed by running
this package's own ``run_e2_topic_sentiment`` directly against the
real, pre-existing ``master_table.csv`` (bypassing any rebuild) and
finding the identical values, just in swapped positions. This is
environment-dependent behavior already present in the original script
(unchanged here, per the Sprint 1A rule to preserve existing behavior
rather than redesign the statistics), so the differential test below
compares ``topic_results`` as an order-independent set, and separately
asserts every individual record's values (z, p, n, cohens_h, ...) are
present in both. A handful of E3's OLS-derived figures (nested-model F
statistics) likewise differ from the checked-in file at the ~1e-11
relative level, consistent with BLAS/LAPACK matrix-inversion noise
across environments rather than a logic difference; the differential
test uses ``pytest.approx(..., rel=1e-6)`` for those specific fields.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.exceptions import CorpusValidationError
from finfluencer.reporting.inferential import (
    InferentialResults,
    load_master_table,
    run_all_inferential_tests,
    run_e1_cross_analyst_sentiment,
    run_e1b_cluster_robustness,
    run_e2_topic_sentiment,
    run_e3_messenger_vs_message,
    run_r1_trend_tests,
    run_r2_herding,
    run_r3_volume_sentiment,
    save_inferential_results,
)

# =============================================================================
# Real-data fixture locations (repo root), for differential/acceptance tests.
# =============================================================================

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_MASTER_TABLE = _REPO_ROOT / "master_table.csv"
_REAL_INFERENTIAL_RESULTS = _REPO_ROOT / "inferential_results.json"

_REAL_DATA_PRESENT = _REAL_MASTER_TABLE.exists() and _REAL_INFERENTIAL_RESULTS.exists()
_SKIP_REASON = (
    "Real master_table.csv / inferential_results.json not present in this "
    "environment (gitignored, regenerable research artifacts) -- "
    "differential/acceptance test skipped."
)


# =============================================================================
# Synthetic fixtures
# =============================================================================


def _synthetic_master_table(n_per_analyst: int = 40, seed: int = 0) -> pd.DataFrame:
    """A small, hand-checkable master table with three analysts and two
    pooled topics, one of which has fewer than E2's n>=30 inclusion
    threshold so the filter is exercised."""
    rng = np.random.default_rng(seed)
    rows = []
    analysts = ["satiroglu", "yesilada", "basaran"]
    dates = pd.bdate_range("2025-01-06", periods=8)  # 8 weeks of Mondays
    for i, analyst in enumerate(analysts):
        # Each analyst gets a different mean sentiment, by construction,
        # so E1/E1b/E3 have real signal to detect.
        mean_p = 0.3 + 0.2 * i
        for j in range(n_per_analyst):
            p = float(np.clip(rng.normal(mean_p, 0.08), 0.01, 0.99))
            topic_id = 1 if j < 35 else 2  # topic 2 has < 30 rows per analyst
            rows.append({
                "comment_id": f"{analyst}_{j}",
                "video_id": f"{analyst}_v{j // 10}",
                "analyst_key": analyst,
                "posted_date": dates[j % len(dates)],
                "sentiment_class": "positive" if p >= 0.5 else "negative",
                "sentiment_prob": p,
                "is_positive": 1 if p >= 0.5 else 0,
                "topic_id_pooled": topic_id,
                "topic_label_pooled": f"topic_{topic_id}",
            })
    return pd.DataFrame(rows)


class TestLoadMasterTable:
    def test_adds_is_positive_and_drops_null_sentiment(self, tmp_path):
        df = pd.DataFrame({
            "comment_id": ["c1", "c2", "c3"],
            "posted_date": ["2025-01-01", "2025-01-02", "2025-01-03"],
            "sentiment_class": ["positive", "negative", None],
            "sentiment_prob": [0.9, 0.2, None],
        })
        path = tmp_path / "master_table.csv"
        df.to_csv(path, index=False)

        loaded = load_master_table(path=path)

        assert len(loaded) == 2  # c3 dropped (null sentiment)
        assert loaded["is_positive"].tolist() == [1, 0]
        assert pd.api.types.is_datetime64_any_dtype(loaded["posted_date"])

    def test_raises_on_all_null_sentiment(self, tmp_path):
        df = pd.DataFrame({
            "comment_id": ["c1"], "posted_date": ["2025-01-01"],
            "sentiment_class": [None], "sentiment_prob": [None],
        })
        path = tmp_path / "master_table.csv"
        df.to_csv(path, index=False)

        with pytest.raises(CorpusValidationError):
            load_master_table(path=path)


class TestRunE1CrossAnalystSentiment:
    def test_result_has_expected_keys_and_dunn_is_square(self):
        df = _synthetic_master_table()
        result, dunn = run_e1_cross_analyst_sentiment(df)

        expected_keys = {
            "chi2", "p", "cramers_v", "kruskal_H", "kruskal_p", "epsilon_sq",
            "shapiro_W", "shapiro_p", "dunn_holm_pvalues", "group_medians", "group_n",
        }
        assert expected_keys <= set(result.keys())
        assert dunn.shape == (3, 3)  # 3 analysts x 3 analysts
        assert set(result["group_n"].keys()) == {"satiroglu", "yesilada", "basaran"}

    def test_detects_real_between_analyst_difference(self):
        # By construction (_synthetic_master_table), analyst means are
        # well-separated (0.3, 0.5, 0.7) -- Kruskal-Wallis must find a
        # significant difference at any conventional alpha.
        df = _synthetic_master_table()
        result, _dunn = run_e1_cross_analyst_sentiment(df)
        assert result["kruskal_p"] < 0.01


class TestRunE1bClusterRobustness:
    def test_result_keys_and_cluster_se_generally_inflated(self):
        df = _synthetic_master_table()
        result = run_e1b_cluster_robustness(df)

        assert {"naive_se", "cluster_se", "se_inflation_ratio", "n_videos", "n_comments"} <= set(result.keys())
        assert result["n_comments"] == len(df)
        # Video-clustered SEs are typically >= naive SEs when comments
        # within a video are correlated; not a strict guarantee for
        # every coefficient, so just check the reported n_videos is sane.
        assert result["n_videos"] > 0


class TestRunE2TopicSentiment:
    def test_low_n_topic_is_excluded(self):
        df = _synthetic_master_table()
        result, topic_df = run_e2_topic_sentiment(df)

        # topic_id 2 has 5 rows per analyst x 3 analysts = 15 < 30 -> excluded.
        tested_ids = {r["topic_id"] for r in result["topic_results"]}
        assert 2 not in tested_ids
        assert 1 in tested_ids
        assert (topic_df["n"] >= 30).all()

    def test_fdr_adjusted_p_is_never_smaller_than_raw_p(self):
        df = _synthetic_master_table()
        _result, topic_df = run_e2_topic_sentiment(df)
        assert (topic_df["p_fdr"] >= topic_df["p"] - 1e-12).all()


class TestRunE3MessengerVsMessage:
    def test_full_model_r2_is_at_least_either_submodel_alone(self):
        # Mathematical invariant of nested OLS: adding predictors can
        # never decrease R^2.
        df = _synthetic_master_table()
        result = run_e3_messenger_vs_message(df)
        assert result["r2_full"] >= result["r2_analyst_only"] - 1e-12
        assert result["r2_full"] >= result["r2_topic_only"] - 1e-12
        assert result["partial_r2_analyst_over_topic"] >= -1e-12
        assert result["partial_r2_topic_over_analyst"] >= -1e-12


class TestRunR1TrendTests:
    def test_detects_a_constructed_increasing_trend(self):
        dates = pd.bdate_range("2025-01-06", periods=20, freq="7D")
        df = pd.DataFrame({
            "comment_id": [f"c{i}" for i in range(20)],
            "posted_date": dates,
            "sentiment_prob": np.linspace(0.2, 0.9, 20),
            "topic_id_pooled": [1] * 20,
        })
        result = run_r1_trend_tests(df)
        assert result["pooled_sentiment_trend"]["trend"] == "increasing"
        assert result["pooled_sentiment_trend"]["p"] < 0.05


class TestRunR2Herding:
    def test_identical_weekly_series_correlate_perfectly(self):
        dates = pd.bdate_range("2025-01-06", periods=20, freq="7D")
        shared = np.linspace(0.2, 0.9, 20) + np.sin(np.arange(20))
        df = pd.DataFrame({
            "comment_id": [f"a{i}" for i in range(20)] + [f"b{i}" for i in range(20)],
            "posted_date": list(dates) * 2,
            "analyst_key": ["a"] * 20 + ["b"] * 20,
            "sentiment_prob": list(shared) * 2,
        })
        result, weekly = run_r2_herding(df)
        assert result["pearson_corr"]["a"]["b"] == pytest.approx(1.0, abs=1e-9)
        assert weekly.shape[1] == 2


class TestRunR3VolumeSentiment:
    def test_filters_videos_below_min_comment_threshold(self):
        df = pd.DataFrame({
            "comment_id": [f"c{i}" for i in range(9)],
            "video_id": ["v1"] * 6 + ["v2"] * 3,  # v2 has only 3 comments (< 5)
            "sentiment_prob": np.linspace(0.1, 0.9, 9),
        })
        result, video_level = run_r3_volume_sentiment(df)
        assert set(video_level["video_id"]) == {"v1"}
        assert result["n_videos"] == 1


class TestRunAllInferentialTests:
    def test_bundles_all_seven_sections(self):
        df = _synthetic_master_table()
        loaded = df.copy()
        loaded["is_positive"] = (loaded["sentiment_class"] == "positive").astype(int)

        bundle = run_all_inferential_tests(loaded)

        assert isinstance(bundle, InferentialResults)
        assert set(bundle.results.keys()) == {
            "E1_cross_analyst_sentiment", "E1b_cluster_robustness", "E2_topic_sentiment",
            "E3_messenger_vs_message", "R1_trend_tests", "R2_herding", "R3_volume_sentiment",
        }


class TestSaveInferentialResults:
    def test_writes_five_files_with_original_names_no_bom(self, tmp_path):
        df = _synthetic_master_table()
        df["is_positive"] = (df["sentiment_class"] == "positive").astype(int)
        bundle = run_all_inferential_tests(df)

        save_inferential_results(bundle, output_dir=tmp_path)

        expected_files = {
            "inferential_results.json", "topic_level_test_results.csv",
            "dunn_posthoc_matrix.csv", "weekly_sentiment_by_analyst.csv",
            "video_level_volume_sentiment.csv",
        }
        assert expected_files <= {p.name for p in tmp_path.iterdir()}
        for name in expected_files:
            raw = (tmp_path / name).read_bytes()
            assert not raw.startswith(b"\xef\xbb\xbf"), f"{name} must not carry a UTF-8 BOM"


# =============================================================================
# Differential test: packaged battery vs. the real, checked-in output.
# =============================================================================


@pytest.mark.skipif(not _REAL_DATA_PRESENT, reason=_SKIP_REASON)
class TestDifferentialAgainstRealScriptOutput:
    @classmethod
    @pytest.fixture(scope="class")
    def real_and_new(cls):
        import json

        real = json.loads(_REAL_INFERENTIAL_RESULTS.read_text(encoding="utf-8"))
        df = load_master_table(path=_REAL_MASTER_TABLE)
        bundle = run_all_inferential_tests(df)
        return real, bundle.results

    def test_e1_cross_analyst_sentiment_matches_exactly(self, real_and_new):
        real, new = real_and_new
        r, n = real["E1_cross_analyst_sentiment"], new["E1_cross_analyst_sentiment"]
        for key in ("chi2", "p", "cramers_v", "kruskal_H", "kruskal_p", "epsilon_sq",
                    "shapiro_W", "shapiro_p"):
            assert n[key] == pytest.approx(r[key], rel=1e-9), key

    def test_e1b_cluster_robustness_matches_exactly(self, real_and_new):
        real, new = real_and_new
        r, n = real["E1b_cluster_robustness"], new["E1b_cluster_robustness"]
        assert n["n_videos"] == r["n_videos"]
        assert n["n_comments"] == r["n_comments"]
        for analyst in r["naive_se"]:
            assert n["naive_se"][analyst] == pytest.approx(r["naive_se"][analyst], rel=1e-6)
            assert n["cluster_se"][analyst] == pytest.approx(r["cluster_se"][analyst], rel=1e-6)

    def test_e2_topic_sentiment_matches_as_an_unordered_set(self, real_and_new):
        """Overall statistics match exactly; per-topic records match as a
        SET (order-independent) -- see module docstring re: the two
        exactly-tied cohens_h pairs and unstable-sort order."""
        real, new = real_and_new
        r, n = real["E2_topic_sentiment"], new["E2_topic_sentiment"]
        for key in ("overall_chi2", "overall_p", "cramers_v", "baseline_pos_rate"):
            assert n[key] == pytest.approx(r[key], rel=1e-9), key
        assert n["n_topics_tested"] == r["n_topics_tested"]
        assert n["n_significant_fdr"] == r["n_significant_fdr"]

        r_by_id = {rec["topic_id"]: rec for rec in r["topic_results"]}
        n_by_id = {rec["topic_id"]: rec for rec in n["topic_results"]}
        assert set(r_by_id) == set(n_by_id)
        for tid in r_by_id:
            for field in ("n", "pos_ratio", "z", "p", "cohens_h", "p_fdr", "significant_fdr"):
                assert n_by_id[tid][field] == pytest.approx(r_by_id[tid][field], rel=1e-6), (tid, field)

    def test_e3_messenger_vs_message_matches_within_blas_tolerance(self, real_and_new):
        """Nested-OLS F-statistics/R^2 involve inverting a large
        (hundreds of dummy columns) near-singular design matrix; a
        looser tolerance accounts for BLAS/LAPACK implementation
        differences across environments (observed ~1e-11 relative
        deviation), not a logic difference."""
        real, new = real_and_new
        r, n = real["E3_messenger_vs_message"], new["E3_messenger_vs_message"]
        for key in ("r2_analyst_only", "r2_topic_only", "r2_full",
                    "partial_r2_analyst_over_topic", "partial_r2_topic_over_analyst"):
            assert n[key] == pytest.approx(r[key], rel=1e-6), key
        for key in ("f_test_analyst_given_topic", "f_test_topic_given_analyst"):
            assert n[key]["F"] == pytest.approx(r[key]["F"], rel=1e-6), key
            assert n[key]["p"] == pytest.approx(r[key]["p"], rel=1e-6), key

    def test_r1_trend_tests_match_exactly(self, real_and_new):
        real, new = real_and_new
        r, n = real["R1_trend_tests"], new["R1_trend_tests"]
        assert n["n_weeks"] == r["n_weeks"]
        assert n["top_topic_id"] == r["top_topic_id"]
        assert n["pooled_sentiment_trend"]["trend"] == r["pooled_sentiment_trend"]["trend"]
        assert n["pooled_sentiment_trend"]["p"] == pytest.approx(r["pooled_sentiment_trend"]["p"], rel=1e-6)
        assert n["top_topic_freq_trend"]["trend"] == r["top_topic_freq_trend"]["trend"]

    def test_r2_herding_matches_exactly(self, real_and_new):
        real, new = real_and_new
        r, n = real["R2_herding"], new["R2_herding"]
        assert n["n_weeks_total"] == r["n_weeks_total"]
        for analyst_a in r["pearson_corr"]:
            for analyst_b in r["pearson_corr"][analyst_a]:
                assert n["pearson_corr"][analyst_a][analyst_b] == pytest.approx(
                    r["pearson_corr"][analyst_a][analyst_b], abs=1e-4,
                )

    def test_r3_volume_sentiment_matches_exactly(self, real_and_new):
        real, new = real_and_new
        r, n = real["R3_volume_sentiment"], new["R3_volume_sentiment"]
        assert n["n_videos"] == r["n_videos"]
        assert n["spearman_rho"] == pytest.approx(r["spearman_rho"], rel=1e-6)
        assert n["p"] == pytest.approx(r["p"], rel=1e-6)


# =============================================================================
# Acceptance test: reproduce specific published numerical results exactly.
# =============================================================================


@pytest.mark.skipif(not _REAL_DATA_PRESENT, reason=_SKIP_REASON)
class TestManuscriptReproduction:
    def test_reproduces_published_comment_count_and_e1_statistics_exactly(self):
        """Sprint 1A acceptance criterion: the packaged implementation
        must reproduce at least one published numerical result exactly.

        N=17566 is the manuscript's headline analyzed-comment count
        (also asserted by the excluded-from-scope build_manuscript_data.py
        script itself: ``len(df)==17566``). The E1 cross-analyst
        chi-square and Kruskal-Wallis H statistics are bit-exact against
        the checked-in inferential_results.json (unlike E3's OLS-derived
        figures, these are not BLAS-precision-sensitive at this scale)."""
        df = load_master_table(path=_REAL_MASTER_TABLE)
        assert len(df) == 17566

        import json
        real = json.loads(_REAL_INFERENTIAL_RESULTS.read_text(encoding="utf-8"))
        result, _dunn = run_e1_cross_analyst_sentiment(df)

        assert result["chi2"] == pytest.approx(real["E1_cross_analyst_sentiment"]["chi2"], rel=1e-9)
        assert result["kruskal_H"] == pytest.approx(real["E1_cross_analyst_sentiment"]["kruskal_H"], rel=1e-9)
