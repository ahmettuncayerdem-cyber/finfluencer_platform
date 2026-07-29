"""Tests for finfluencer.reporting.manuscript_data.

Same three tiers as test_master_table.py / test_inferential.py:

* Unit tests build small, synthetic fixtures with a KNOWN structure.
* Differential tests compare packaged output against the real,
  pre-existing manuscript_table1.csv / manuscript_fig1_data.csv /
  manuscript_fig3_data.csv this repository's root-level
  build_manuscript_data.py script produced (found directly in the repo
  root, not the /tmp/ path the script itself writes to -- someone
  copied them there at some point; treated here purely as reference
  fixtures). Skipped automatically if absent.
* An acceptance test reproduces the manuscript's headline analyzed-
  comment count (N=17566) via fig1_data, independently of Sprint 1A's
  own N=17566 check on master_table.csv -- a different code path
  (this module reads only two columns via ``usecols``) reaching the
  same published invariant.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.exceptions import CorpusValidationError
from finfluencer.reporting.manuscript_data import (
    ANALYST_DISPLAY_NAMES,
    build_dataset_characteristics_table,
    build_sentiment_by_analyst_figure_data,
    build_topic_volcano_figure_data,
    save_dataset_characteristics_table,
    save_sentiment_by_analyst_figure_data,
    save_topic_volcano_figure_data,
)

# =============================================================================
# Real-data fixture locations (repo root), for differential/acceptance tests.
# =============================================================================

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_VIDEOS = _REPO_ROOT / "data" / "raw" / "videos.parquet"
_REAL_COMMENTS = _REPO_ROOT / "data" / "raw" / "comments.parquet"
_REAL_MASTER_TABLE = _REPO_ROOT / "master_table.csv"
_REAL_INFERENTIAL_RESULTS = _REPO_ROOT / "inferential_results.json"
_REAL_TABLE1 = _REPO_ROOT / "manuscript_table1.csv"
_REAL_FIG1_DATA = _REPO_ROOT / "manuscript_fig1_data.csv"
_REAL_FIG3_DATA = _REPO_ROOT / "manuscript_fig3_data.csv"

_REAL_TABLE1_INPUTS_PRESENT = _REAL_VIDEOS.exists() and _REAL_COMMENTS.exists() and _REAL_TABLE1.exists()
_REAL_FIG1_INPUTS_PRESENT = _REAL_MASTER_TABLE.exists() and _REAL_FIG1_DATA.exists()
_REAL_FIG3_INPUTS_PRESENT = _REAL_INFERENTIAL_RESULTS.exists() and _REAL_FIG3_DATA.exists()

_SKIP_REASON = (
    "Real reference file(s) not present in this environment (gitignored, "
    "regenerable research artifacts) -- differential/acceptance test skipped."
)


# =============================================================================
# Synthetic fixtures
# =============================================================================


def _write_synthetic_videos_and_comments(tmp_path: Path) -> tuple[Path, Path]:
    videos = pd.DataFrame({
        "analyst_key": ["satiroglu", "satiroglu", "yesilada"],
        "video_id": ["v1", "v2", "v3"],
        "eligible": [True, True, False],
        "selected": [True, False, False],
    })
    videos_path = tmp_path / "videos.parquet"
    videos.to_parquet(videos_path)

    comments = pd.DataFrame({
        "analyst_key": ["satiroglu", "satiroglu", "yesilada"],
        "video_id": ["v1", "v1", "v3"],
        "comment_id": ["c1", "c2", "c3"],
        "posted_date": pd.to_datetime(["2025-01-01", "2025-01-05", "2025-02-01"]),
        "n_tokens": [5, 15, 10],
        "likes": [0, 2, 1],
    })
    comments_path = tmp_path / "comments.parquet"
    comments.to_parquet(comments_path)

    return videos_path, comments_path


class TestBuildDatasetCharacteristicsTable:
    def test_shape_and_display_name_mapping(self, tmp_path):
        videos_path, comments_path = _write_synthetic_videos_and_comments(tmp_path)

        table1 = build_dataset_characteristics_table(videos_path=videos_path, comments_path=comments_path)

        assert len(table1) == 2  # two analysts present
        assert set(table1["analyst_key"]) == {"satiroglu", "yesilada"}
        assert table1.set_index("analyst_key").loc["satiroglu", "display_name"] == ANALYST_DISPLAY_NAMES["satiroglu"]

    def test_sorted_by_comment_count_descending(self, tmp_path):
        videos_path, comments_path = _write_synthetic_videos_and_comments(tmp_path)
        table1 = build_dataset_characteristics_table(videos_path=videos_path, comments_path=comments_path)
        # satiroglu has 2 comments, yesilada has 1 -> satiroglu first.
        assert table1.iloc[0]["analyst_key"] == "satiroglu"

    def test_video_and_comment_counts_are_independent_aggregates(self, tmp_path):
        videos_path, comments_path = _write_synthetic_videos_and_comments(tmp_path)
        table1 = build_dataset_characteristics_table(
            videos_path=videos_path, comments_path=comments_path,
        ).set_index("analyst_key")

        assert table1.loc["satiroglu", "n_collected"] == 2
        assert table1.loc["satiroglu", "n_eligible"] == 2
        assert table1.loc["satiroglu", "n_selected"] == 1
        assert table1.loc["satiroglu", "n_comments"] == 2
        assert table1.loc["satiroglu", "n_videos_final"] == 1  # both comments are on v1

    @pytest.mark.parametrize("empty_source", ["videos", "comments"])
    def test_empty_source_raises_corpus_validation_error(self, tmp_path, empty_source):
        videos_path, comments_path = _write_synthetic_videos_and_comments(tmp_path)
        paths = {"videos": videos_path, "comments": comments_path}
        empty_df = pd.read_parquet(paths[empty_source]).iloc[0:0]
        empty_df.to_parquet(paths[empty_source])

        with pytest.raises(CorpusValidationError):
            build_dataset_characteristics_table(videos_path=videos_path, comments_path=comments_path)

    @pytest.mark.skipif(not _REAL_TABLE1_INPUTS_PRESENT, reason=_SKIP_REASON)
    def test_differential_matches_real_build_manuscript_data_script(self):
        table1 = build_dataset_characteristics_table(videos_path=_REAL_VIDEOS, comments_path=_REAL_COMMENTS)
        real = pd.read_csv(_REAL_TABLE1)

        assert list(table1.columns) == list(real.columns)
        assert len(table1) == len(real) == 4  # four analysts, published invariant
        for col in ("n_collected", "n_eligible", "n_selected", "n_videos_final", "n_comments"):
            assert table1[col].tolist() == real[col].tolist(), col
        assert table1["display_name"].tolist() == real["display_name"].tolist()


class TestSaveDatasetCharacteristicsTable:
    def test_round_trips_without_a_bom(self, tmp_path):
        df = pd.DataFrame({"analyst_key": ["a"], "n_comments": [1]})
        out_path = tmp_path / "table1.csv"

        save_dataset_characteristics_table(df, output_path=out_path)

        raw = out_path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")
        reloaded = pd.read_csv(out_path)
        assert list(reloaded.columns) == ["analyst_key", "n_comments"]


class TestBuildSentimentByAnalystFigureData:
    def test_selects_only_the_two_required_columns(self, tmp_path):
        df = pd.DataFrame({
            "comment_id": ["c1", "c2"],
            "analyst_key": ["satiroglu", "yesilada"],
            "sentiment_prob": [0.8, 0.3],
            "text_clean": ["merhaba", "tesekkurler"],
        })
        path = tmp_path / "master_table.csv"
        df.to_csv(path, index=False)

        fig1_data = build_sentiment_by_analyst_figure_data(master_table_path=path)

        assert list(fig1_data.columns) == ["analyst_key", "sentiment_prob"]
        assert len(fig1_data) == 2

    def test_raises_on_empty_master_table(self, tmp_path):
        df = pd.DataFrame({"analyst_key": [], "sentiment_prob": []})
        path = tmp_path / "master_table.csv"
        df.to_csv(path, index=False)

        with pytest.raises(CorpusValidationError):
            build_sentiment_by_analyst_figure_data(master_table_path=path)

    @pytest.mark.skipif(not _REAL_FIG1_INPUTS_PRESENT, reason=_SKIP_REASON)
    def test_differential_matches_real_build_manuscript_data_script(self):
        fig1_data = build_sentiment_by_analyst_figure_data(master_table_path=_REAL_MASTER_TABLE)
        real = pd.read_csv(_REAL_FIG1_DATA)

        assert list(fig1_data.columns) == list(real.columns)
        assert len(fig1_data) == len(real)
        assert fig1_data.reset_index(drop=True).equals(real.reset_index(drop=True))


class TestSaveSentimentByAnalystFigureData:
    def test_round_trips_without_a_bom(self, tmp_path):
        df = pd.DataFrame({"analyst_key": ["a"], "sentiment_prob": [0.5]})
        out_path = tmp_path / "fig1.csv"

        save_sentiment_by_analyst_figure_data(df, output_path=out_path)

        raw = out_path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")


class TestBuildTopicVolcanoFigureData:
    def test_computes_neglog10_p_fdr_and_selects_expected_columns(self, tmp_path):
        inf = {
            "E2_topic_sentiment": {
                "topic_results": [
                    {"topic_id": 1, "topic_label": "a", "n": 40, "pos_ratio": 0.6,
                     "z": 1.0, "p": 0.05, "cohens_h": 0.2, "p_fdr": 0.1, "significant_fdr": False},
                    {"topic_id": 2, "topic_label": "b", "n": 50, "pos_ratio": 0.2,
                     "z": -3.0, "p": 0.001, "cohens_h": -0.6, "p_fdr": 0.01, "significant_fdr": True},
                ],
            },
        }
        path = tmp_path / "inferential_results.json"
        import json
        path.write_text(json.dumps(inf), encoding="utf-8")

        fig3_data = build_topic_volcano_figure_data(inferential_results_path=path)

        assert list(fig3_data.columns) == [
            "topic_id", "topic_label", "cohens_h", "p_fdr", "neglog10_p_fdr", "significant_fdr", "n",
        ]
        assert fig3_data.set_index("topic_id").loc[2, "neglog10_p_fdr"] == pytest.approx(-np.log10(0.01))

    def test_p_fdr_of_zero_is_floored_not_infinite(self, tmp_path):
        inf = {"E2_topic_sentiment": {"topic_results": [
            {"topic_id": 1, "topic_label": "a", "n": 40, "pos_ratio": 0.6,
             "z": 1.0, "p": 0.0, "cohens_h": 0.2, "p_fdr": 0.0, "significant_fdr": True},
        ]}}
        path = tmp_path / "inferential_results.json"
        import json
        path.write_text(json.dumps(inf), encoding="utf-8")

        fig3_data = build_topic_volcano_figure_data(inferential_results_path=path)

        assert np.isfinite(fig3_data["neglog10_p_fdr"].iloc[0])

    def test_raises_on_empty_topic_results(self, tmp_path):
        inf = {"E2_topic_sentiment": {"topic_results": []}}
        path = tmp_path / "inferential_results.json"
        import json
        path.write_text(json.dumps(inf), encoding="utf-8")

        with pytest.raises(CorpusValidationError):
            build_topic_volcano_figure_data(inferential_results_path=path)

    @pytest.mark.skipif(not _REAL_FIG3_INPUTS_PRESENT, reason=_SKIP_REASON)
    def test_differential_matches_real_build_manuscript_data_script(self):
        fig3_data = build_topic_volcano_figure_data(inferential_results_path=_REAL_INFERENTIAL_RESULTS)
        real = pd.read_csv(_REAL_FIG3_DATA)

        assert list(fig3_data.columns) == list(real.columns)
        assert len(fig3_data) == len(real)
        r_by_id = real.set_index("topic_id")
        n_by_id = fig3_data.set_index("topic_id")
        assert set(r_by_id.index) == set(n_by_id.index)
        for tid in r_by_id.index:
            for col in ("cohens_h", "p_fdr", "neglog10_p_fdr", "n"):
                assert n_by_id.loc[tid, col] == pytest.approx(r_by_id.loc[tid, col], rel=1e-6), (tid, col)
            assert bool(n_by_id.loc[tid, "significant_fdr"]) == bool(r_by_id.loc[tid, "significant_fdr"])


class TestSaveTopicVolcanoFigureData:
    def test_round_trips_without_a_bom(self, tmp_path):
        df = pd.DataFrame({"topic_id": [1], "cohens_h": [0.1]})
        out_path = tmp_path / "fig3.csv"

        save_topic_volcano_figure_data(df, output_path=out_path)

        raw = out_path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")


# =============================================================================
# Acceptance test: reproduce a specific published numerical result exactly.
# =============================================================================


@pytest.mark.skipif(not _REAL_FIG1_INPUTS_PRESENT, reason=_SKIP_REASON)
class TestManuscriptReproduction:
    def test_reproduces_published_comment_count_via_fig1_data(self):
        """Sprint 1B.1 acceptance criterion, reached via a different code
        path than Sprint 1A's own N=17566 check (this module reads only
        two columns from master_table.csv via ``usecols``, independent
        of reporting.inferential's full-table load)."""
        fig1_data = build_sentiment_by_analyst_figure_data(master_table_path=_REAL_MASTER_TABLE)
        assert len(fig1_data) == 17566

    @pytest.mark.skipif(not _REAL_TABLE1_INPUTS_PRESENT, reason=_SKIP_REASON)
    def test_reproduces_published_analyst_count(self):
        table1 = build_dataset_characteristics_table(videos_path=_REAL_VIDEOS, comments_path=_REAL_COMMENTS)
        assert len(table1) == 4
        assert set(table1["analyst_key"]) == {"satiroglu", "yesilada", "basaran", "gecer"}
