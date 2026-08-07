"""Tests for finfluencer.reporting.master_table.

Two tiers, matching this project's established convention (see
tests/unit/test_market/test_confirmatory_analysis.py):

* Unit tests build small, synthetic Parquet fixtures with a KNOWN
  structure, so they verify the join/rename logic itself and do not
  depend on any real data being present.
* A differential test additionally compares the packaged function's
  output against the real, pre-existing ``master_table.csv`` this
  repository's root-level ``export_master_table.py`` script produced.
  It is skipped automatically if that file (or its real Parquet
  sources) is absent -- these are gitignored, regenerable artifacts,
  not tracked inputs (see ``af4792d chore(repo): stop tracking
  generated data/cache artifacts``), so they are expected to be
  present locally but absent in CI.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from finfluencer.core.exceptions import CorpusValidationError
from finfluencer.reporting.master_table import build_master_table, save_master_table

# =============================================================================
# Real-data fixture locations (repo root), for the differential test only.
# =============================================================================

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_MASTER_TABLE = _REPO_ROOT / "master_table.csv"
_REAL_COMMENTS = _REPO_ROOT / "data" / "raw" / "comments.parquet"
_REAL_TOPICS = _REPO_ROOT / "data" / "processed" / "topics.parquet"
_REAL_SENTIMENT = _REPO_ROOT / "data" / "processed" / "sentiment.parquet"

_REAL_DATA_PRESENT = all(
    p.exists() for p in (_REAL_MASTER_TABLE, _REAL_COMMENTS, _REAL_TOPICS, _REAL_SENTIMENT)
)
_SKIP_REASON = (
    "Real master_table.csv / raw+processed parquet fixtures not present in this "
    "environment (gitignored, regenerable research artifacts) -- differential "
    "test skipped."
)


def _write_synthetic_sources(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a small, hand-checkable set of comments/topics/sentiment fixtures.

    Deliberately includes one comment (``c4``) with no sentiment/topic
    match, to exercise the left-join null-handling the same way the
    real corpus does (not every comment has a topic/sentiment label).
    """
    comments = pd.DataFrame({
        "comment_id": ["c1", "c2", "c3", "c4"],
        "video_id": ["v1", "v1", "v2", "v2"],
        "analyst_key": ["satiroglu", "satiroglu", "yesilada", "yesilada"],
        "posted_date": pd.to_datetime(["2025-01-03", "2025-01-04", "2025-01-05", "2025-01-06"]),
        "text_clean": ["merhaba", "tesekkurler", "cok guzel", "bilmiyorum"],
        "n_tokens": [1, 1, 2, 1],
        "likes": [0, 3, 1, 0],
    })
    comments_path = tmp_path / "comments.parquet"
    comments.to_parquet(comments_path)

    sentiment = pd.DataFrame({
        "comment_id": ["c1", "c2", "c3"],
        "sentiment_class": ["positive", "positive", "neutral"],
        "sentiment_prob": [0.9, 0.8, 0.5],
    })
    sentiment_path = tmp_path / "sentiment.parquet"
    sentiment.to_parquet(sentiment_path)

    topics = pd.DataFrame({
        "comment_id": ["c1", "c2", "c3", "c1", "c2", "c3"],
        "configuration": ["pooled", "pooled", "pooled", "within_analyst", "within_analyst", "within_analyst"],
        "topic_id": [1, 1, 2, 1, 1, 5],
        "topic_label": ["greeting", "greeting", "praise", "greeting", "greeting", "praise_within"],
        "topic_prob": [0.7, 0.6, 0.4, 0.7, 0.6, 0.4],
    })
    topics_path = tmp_path / "topics.parquet"
    topics.to_parquet(topics_path)

    return comments_path, topics_path, sentiment_path


class TestBuildMasterTable:
    def test_join_shape_and_columns(self, tmp_path):
        comments_path, topics_path, sentiment_path = _write_synthetic_sources(tmp_path)

        master = build_master_table(
            comments_path=comments_path, topics_path=topics_path, sentiment_path=sentiment_path,
        )

        assert len(master) == 4  # one row per comment, regardless of join misses
        assert list(master.columns) == [
            "comment_id", "video_id", "analyst_key", "posted_date", "text_clean",
            "n_tokens", "likes", "sentiment_class", "sentiment_prob",
            "topic_id_pooled", "topic_label_pooled", "topic_prob_pooled",
            "topic_id_within", "topic_label_within",
        ]

    def test_pooled_and_within_configurations_do_not_collide(self, tmp_path):
        comments_path, topics_path, sentiment_path = _write_synthetic_sources(tmp_path)
        master = build_master_table(
            comments_path=comments_path, topics_path=topics_path, sentiment_path=sentiment_path,
        ).set_index("comment_id")

        # c3: pooled topic_id=2 ("praise"), within topic_id=5 ("praise_within").
        assert master.loc["c3", "topic_id_pooled"] == 2
        assert master.loc["c3", "topic_label_pooled"] == "praise"
        assert master.loc["c3", "topic_id_within"] == 5
        assert master.loc["c3", "topic_label_within"] == "praise_within"
        # within-analyst configuration carries no topic_prob column at all.
        assert "topic_prob_within" not in master.columns

    def test_comment_with_no_sentiment_or_topic_match_is_kept_with_nulls(self, tmp_path):
        comments_path, topics_path, sentiment_path = _write_synthetic_sources(tmp_path)
        master = build_master_table(
            comments_path=comments_path, topics_path=topics_path, sentiment_path=sentiment_path,
        ).set_index("comment_id")

        assert pd.isna(master.loc["c4", "sentiment_class"])
        assert pd.isna(master.loc["c4", "topic_id_pooled"])
        assert pd.isna(master.loc["c4", "topic_id_within"])

    @pytest.mark.parametrize("empty_source", ["comments", "topics", "sentiment"])
    def test_empty_source_raises_corpus_validation_error(self, tmp_path, empty_source):
        comments_path, topics_path, sentiment_path = _write_synthetic_sources(tmp_path)
        paths = {"comments": comments_path, "topics": topics_path, "sentiment": sentiment_path}

        empty_df = pd.read_parquet(paths[empty_source]).iloc[0:0]
        empty_df.to_parquet(paths[empty_source])

        with pytest.raises(CorpusValidationError):
            build_master_table(
                comments_path=comments_path, topics_path=topics_path, sentiment_path=sentiment_path,
            )

    @pytest.mark.skipif(not _REAL_DATA_PRESENT, reason=_SKIP_REASON)
    def test_differential_matches_real_export_master_table_script(self, tmp_path):
        """The packaged join must reproduce export_master_table.py's real,
        pre-existing master_table.csv exactly, compared the way any real
        consumer actually reads it: through the CSV interchange format
        (round-tripped via save_master_table + pd.read_csv), not as raw
        in-memory Parquet-sourced floats vs. text-sourced floats.

        Comparing the two DataFrames *before* any CSV round-trip is not
        a fair test: text<->float64 conversion is lossy at the ULP level
        (observed max abs diff ~1.1e-16, i.e. exactly one machine
        epsilon) regardless of which of the two float columns went
        through the CSV format and which did not, and ``posted_date``
        would only be a proper ``datetime64`` on the side that was
        explicitly parsed. Both DataFrames go through the identical
        save+reload path here, which is what the real real script and
        this package's own ``load_master_table`` both do -- so this is
        an apples-to-apples comparison of what downstream consumers
        actually see.
        """
        master = build_master_table(
            comments_path=_REAL_COMMENTS, topics_path=_REAL_TOPICS, sentiment_path=_REAL_SENTIMENT,
        )
        new_csv_path = tmp_path / "master_table.csv"
        save_master_table(master, output_path=new_csv_path)

        new = pd.read_csv(new_csv_path, parse_dates=["posted_date"])
        real = pd.read_csv(_REAL_MASTER_TABLE, parse_dates=["posted_date"])

        assert list(new.columns) == list(real.columns)
        assert len(new) == len(real)
        assert new.equals(real)

        # Published invariant, independent of whatever the reference file on
        # disk currently contains: the manuscript's headline analyzed-comment
        # count is N=17566 (also asserted by the excluded-from-scope
        # build_manuscript_data.py script itself: ``len(df)==17566``). The
        # len(new) == len(real) check above only proves internal consistency
        # with the reference file; it would not catch the reference file
        # itself silently drifting from the published number (e.g. an
        # accidental swap to a different or partial dataset). This assertion
        # anchors the differential test to the actual published invariant.
        assert len(new) == 17566


    def test_provenance_columns_omitted_by_default(self, tmp_path):
        """V1.0 Research Readiness freeze (docs/implementation/V1.0_RESEARCH_READINESS_AUDIT.md
        section 8 item 2): the new provenance kwargs are opt-in and must not change the column
        set when omitted, so `test_join_shape_and_columns` above stays valid unmodified."""
        comments_path, topics_path, sentiment_path = _write_synthetic_sources(tmp_path)
        master = build_master_table(
            comments_path=comments_path, topics_path=topics_path, sentiment_path=sentiment_path,
        )
        for col in (
            "sentiment_analysis_run_id", "sentiment_model_name", "sentiment_model_revision",
            "topics_analysis_run_id", "topics_model_name", "topics_model_revision",
        ):
            assert col not in master.columns

    def test_provenance_columns_added_when_given_and_constant_across_rows(self, tmp_path):
        comments_path, topics_path, sentiment_path = _write_synthetic_sources(tmp_path)
        master = build_master_table(
            comments_path=comments_path, topics_path=topics_path, sentiment_path=sentiment_path,
            topics_analysis_run_id="ar-topics-1",
            topics_model_name="paraphrase-multilingual-MiniLM-L12-v2",
            topics_model_revision="e8f8c21",
            sentiment_analysis_run_id="ar-sentiment-1",
            sentiment_model_name="bert-base-turkish-sentiment-cased",
            sentiment_model_revision="f607086",
        )
        assert (master["topics_analysis_run_id"] == "ar-topics-1").all()
        assert (master["topics_model_name"] == "paraphrase-multilingual-MiniLM-L12-v2").all()
        assert (master["topics_model_revision"] == "e8f8c21").all()
        assert (master["sentiment_analysis_run_id"] == "ar-sentiment-1").all()
        assert (master["sentiment_model_name"] == "bert-base-turkish-sentiment-cased").all()
        assert (master["sentiment_model_revision"] == "f607086").all()

    def test_provenance_columns_partial_subset_only_adds_given_ones(self, tmp_path):
        """Callers that only know some of the six values (e.g. a run_id but not a model name)
        must be able to pass just those -- not all-or-nothing."""
        comments_path, topics_path, sentiment_path = _write_synthetic_sources(tmp_path)
        master = build_master_table(
            comments_path=comments_path, topics_path=topics_path, sentiment_path=sentiment_path,
            sentiment_analysis_run_id="ar-sentiment-1",
        )
        assert "sentiment_analysis_run_id" in master.columns
        assert "sentiment_model_name" not in master.columns
        assert "topics_analysis_run_id" not in master.columns


class TestSaveMasterTable:
    def test_round_trips_without_a_bom(self, tmp_path):
        """save_master_table must write plain UTF-8, not utf-8-sig: a BOM
        would corrupt the first column's name on the downstream
        pd.read_csv(..., parse_dates=[...]) call in reporting.inferential,
        which passes no encoding override (see module docstring)."""
        df = pd.DataFrame({"comment_id": ["c1"], "posted_date": pd.to_datetime(["2025-01-01"])})
        out_path = tmp_path / "master_table.csv"

        save_master_table(df, output_path=out_path)

        raw = out_path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), "output must not carry a UTF-8 BOM"
        reloaded = pd.read_csv(out_path, parse_dates=["posted_date"])
        assert list(reloaded.columns) == ["comment_id", "posted_date"]

    def test_creates_missing_parent_directory(self, tmp_path):
        df = pd.DataFrame({"comment_id": ["c1"]})
        out_path = tmp_path / "nested" / "dir" / "master_table.csv"

        save_master_table(df, output_path=out_path)

        assert out_path.exists()
