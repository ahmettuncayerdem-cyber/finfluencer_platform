"""Tests for :mod:`finfluencer.migration.backfill_topic_scope` (Migration
Step 3.2.5)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from finfluencer.migration.backfill_topic_scope import (
    SCOPE_CRITERIA_VERSION,
    backfill_topic_scope,
)
from finfluencer.scope import resolve_scope
from finfluencer.core.contracts import AnalysisScopeType
from finfluencer.utils.io import write_parquet


def _write_inputs(
    tmp_path: Path, topics_rows: list[dict], comments_rows: list[dict],
) -> tuple[Path, Path]:
    topics_path = tmp_path / "topics.parquet"
    comments_path = tmp_path / "comments.parquet"
    write_parquet(pd.DataFrame(topics_rows), topics_path)
    write_parquet(pd.DataFrame(comments_rows), comments_path)
    return topics_path, comments_path


def _topic_row(*, comment_id: str, configuration: str, topic_id: int = 0, prob: float = 0.9) -> dict:
    return dict(
        comment_id=comment_id, topic_id=topic_id, topic_prob=prob, topic_tier=None,
        configuration=configuration, topic_label=f"{topic_id}_label",
    )


def _comment_row(*, comment_id: str, analyst_key: str) -> dict:
    return dict(analyst_key=analyst_key, comment_id=comment_id)


class TestBackfillTopicScopeBasics:
    def test_adds_scope_id_column(self, tmp_path: Path):
        topics_rows = [
            _topic_row(comment_id="c1", configuration="pooled"),
            _topic_row(comment_id="c1", configuration="within_analyst"),
        ]
        comments_rows = [_comment_row(comment_id="c1", analyst_key="gecer")]
        topics_path, comments_path = _write_inputs(tmp_path, topics_rows, comments_rows)

        result = backfill_topic_scope(topics_path, comments_path)
        out = result["topics"]

        assert "scope_id" in out.columns
        assert out["scope_id"].notna().all()

    def test_pooled_rows_share_one_scope_id(self, tmp_path: Path):
        topics_rows = [
            _topic_row(comment_id="c1", configuration="pooled"),
            _topic_row(comment_id="c2", configuration="pooled"),
            _topic_row(comment_id="c3", configuration="pooled"),
        ]
        comments_rows = [
            _comment_row(comment_id="c1", analyst_key="gecer"),
            _comment_row(comment_id="c2", analyst_key="satiroglu"),
            _comment_row(comment_id="c3", analyst_key="satiroglu"),
        ]
        topics_path, comments_path = _write_inputs(tmp_path, topics_rows, comments_rows)

        out = backfill_topic_scope(topics_path, comments_path)["topics"]
        assert out["scope_id"].nunique() == 1

    def test_within_analyst_rows_grouped_per_analyst(self, tmp_path: Path):
        topics_rows = [
            _topic_row(comment_id="c1", configuration="within_analyst"),
            _topic_row(comment_id="c2", configuration="within_analyst"),
            _topic_row(comment_id="c3", configuration="within_analyst"),
        ]
        comments_rows = [
            _comment_row(comment_id="c1", analyst_key="gecer"),
            _comment_row(comment_id="c2", analyst_key="gecer"),
            _comment_row(comment_id="c3", analyst_key="satiroglu"),
        ]
        topics_path, comments_path = _write_inputs(tmp_path, topics_rows, comments_rows)

        out = backfill_topic_scope(topics_path, comments_path)["topics"]
        gecer_ids = out.loc[out["comment_id"].isin(["c1", "c2"]), "scope_id"]
        satiroglu_ids = out.loc[out["comment_id"] == "c3", "scope_id"]
        assert gecer_ids.nunique() == 1
        assert satiroglu_ids.nunique() == 1
        assert gecer_ids.iloc[0] != satiroglu_ids.iloc[0]

    def test_scope_id_matches_live_resolve_scope(self, tmp_path: Path):
        """The backfilled scope_id must be bit-identical to what a live
        run_topics() call would independently compute for the same
        group - this is the whole point of using the same
        criteria_version (see module docstring)."""
        topics_rows = [
            _topic_row(comment_id="c1", configuration="pooled"),
            _topic_row(comment_id="c2", configuration="pooled"),
        ]
        comments_rows = [
            _comment_row(comment_id="c1", analyst_key="gecer"),
            _comment_row(comment_id="c2", analyst_key="satiroglu"),
        ]
        topics_path, comments_path = _write_inputs(tmp_path, topics_rows, comments_rows)

        out = backfill_topic_scope(topics_path, comments_path)["topics"]
        expected = resolve_scope(
            ["c1", "c2"], scope_type=AnalysisScopeType.global_,
            criteria_version=SCOPE_CRITERIA_VERSION,
        )
        assert out["scope_id"].unique().tolist() == [expected.scope_id]


class TestBackfillTopicScopePreservation:
    def test_row_count_preserved(self, tmp_path: Path):
        topics_rows = [
            _topic_row(comment_id="c1", configuration="pooled"),
            _topic_row(comment_id="c2", configuration="within_analyst"),
        ]
        comments_rows = [
            _comment_row(comment_id="c1", analyst_key="gecer"),
            _comment_row(comment_id="c2", analyst_key="gecer"),
        ]
        topics_path, comments_path = _write_inputs(tmp_path, topics_rows, comments_rows)
        report = backfill_topic_scope(topics_path, comments_path)["report"]
        assert report["n_rows_in"] == report["n_rows_out"] == 2

    def test_row_order_preserved(self, tmp_path: Path):
        topics_rows = [
            _topic_row(comment_id="c3", configuration="pooled", topic_id=2),
            _topic_row(comment_id="c1", configuration="pooled", topic_id=0),
            _topic_row(comment_id="c2", configuration="pooled", topic_id=1),
        ]
        comments_rows = [
            _comment_row(comment_id=c, analyst_key="gecer") for c in ("c1", "c2", "c3")
        ]
        topics_path, comments_path = _write_inputs(tmp_path, topics_rows, comments_rows)
        out = backfill_topic_scope(topics_path, comments_path)["topics"]
        assert out["comment_id"].tolist() == ["c3", "c1", "c2"]
        assert out["topic_id"].tolist() == [2, 0, 1]

    def test_topic_id_and_prob_unchanged(self, tmp_path: Path):
        topics_rows = [
            _topic_row(comment_id="c1", configuration="pooled", topic_id=7, prob=0.4321),
        ]
        comments_rows = [_comment_row(comment_id="c1", analyst_key="gecer")]
        topics_path, comments_path = _write_inputs(tmp_path, topics_rows, comments_rows)
        out = backfill_topic_scope(topics_path, comments_path)["topics"]
        assert out.iloc[0]["topic_id"] == 7
        assert out.iloc[0]["topic_prob"] == pytest.approx(0.4321)

    def test_configuration_and_topic_label_unchanged(self, tmp_path: Path):
        topics_rows = [_topic_row(comment_id="c1", configuration="pooled", topic_id=3)]
        comments_rows = [_comment_row(comment_id="c1", analyst_key="gecer")]
        topics_path, comments_path = _write_inputs(tmp_path, topics_rows, comments_rows)
        out = backfill_topic_scope(topics_path, comments_path)["topics"]
        assert out.iloc[0]["configuration"] == "pooled"
        assert out.iloc[0]["topic_label"] == "3_label"

    def test_idempotent_rerun_same_scope_ids(self, tmp_path: Path):
        topics_rows = [
            _topic_row(comment_id="c1", configuration="pooled"),
            _topic_row(comment_id="c1", configuration="within_analyst"),
        ]
        comments_rows = [_comment_row(comment_id="c1", analyst_key="gecer")]
        topics_path, comments_path = _write_inputs(tmp_path, topics_rows, comments_rows)

        first = backfill_topic_scope(topics_path, comments_path)["topics"]
        # Re-run against the ALREADY-backfilled frame written back out.
        write_parquet(first, topics_path)
        second = backfill_topic_scope(topics_path, comments_path)["topics"]

        assert first["scope_id"].tolist() == second["scope_id"].tolist()


class TestBackfillTopicScopeFailureModes:
    def test_unknown_configuration_raises(self, tmp_path: Path):
        topics_rows = [_topic_row(comment_id="c1", configuration="bogus")]
        comments_rows = [_comment_row(comment_id="c1", analyst_key="gecer")]
        topics_path, comments_path = _write_inputs(tmp_path, topics_rows, comments_rows)
        with pytest.raises(ValueError, match="unexpected configuration"):
            backfill_topic_scope(topics_path, comments_path)

    def test_missing_analyst_lookup_raises(self, tmp_path: Path):
        topics_rows = [_topic_row(comment_id="c1", configuration="within_analyst")]
        comments_rows = [_comment_row(comment_id="c2", analyst_key="gecer")]  # no c1
        topics_path, comments_path = _write_inputs(tmp_path, topics_rows, comments_rows)
        with pytest.raises(ValueError, match="no matching row in comments.parquet"):
            backfill_topic_scope(topics_path, comments_path)

    def test_empty_topics_returns_empty(self, tmp_path: Path):
        topics_path = tmp_path / "topics.parquet"
        comments_path = tmp_path / "comments.parquet"
        write_parquet(pd.DataFrame(), topics_path)
        write_parquet(pd.DataFrame(), comments_path)
        result = backfill_topic_scope(topics_path, comments_path)
        assert result["topics"].empty
        assert result["report"]["n_rows_in"] == 0
