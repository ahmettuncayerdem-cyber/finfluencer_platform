"""Tests for :mod:`finfluencer.analysis.topic_sentiment`."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from finfluencer.analysis.topic_sentiment import run_topic_sentiment
from finfluencer.utils.io import write_parquet


def _write(df: pd.DataFrame, path: Path) -> Path:
    write_parquet(df, path)
    return path


def _topics_df() -> pd.DataFrame:
    return pd.DataFrame([
        # pooled: topic 0 has c1 (pos), c2 (neg); topic 1 has c3 (pos)
        dict(comment_id="c1", topic_id=0, topic_prob=0.9, topic_tier=None,
             configuration="pooled", topic_label="0_altin_gm_ons"),
        dict(comment_id="c2", topic_id=0, topic_prob=0.8, topic_tier=None,
             configuration="pooled", topic_label="0_altin_gm_ons"),
        dict(comment_id="c3", topic_id=1, topic_prob=0.7, topic_tier=None,
             configuration="pooled", topic_label="1_borsa_faiz"),
        # within_analyst: satiroglu/topic0 has c1, c2; gecer/topic1 has c3
        dict(comment_id="c1", topic_id=0, topic_prob=0.9, topic_tier=None,
             configuration="within_analyst", topic_label="0_within_label"),
        dict(comment_id="c2", topic_id=0, topic_prob=0.8, topic_tier=None,
             configuration="within_analyst", topic_label="0_within_label"),
        dict(comment_id="c3", topic_id=1, topic_prob=0.7, topic_tier=None,
             configuration="within_analyst", topic_label="1_within_label"),
    ])


def _sentiment_df() -> pd.DataFrame:
    return pd.DataFrame([
        dict(comment_id="c1", sentiment_prob=0.9, sentiment_class="positive",
             sentiment_pseudo_neutral=False, sentiment_target=None, sentiment_market_directed=None),
        dict(comment_id="c2", sentiment_prob=0.1, sentiment_class="negative",
             sentiment_pseudo_neutral=False, sentiment_target=None, sentiment_market_directed=None),
        dict(comment_id="c3", sentiment_prob=0.55, sentiment_class="positive",
             sentiment_pseudo_neutral=True, sentiment_target=None, sentiment_market_directed=None),
    ])


def _comments_df() -> pd.DataFrame:
    return pd.DataFrame([
        dict(comment_id="c1", analyst_key="satiroglu"),
        dict(comment_id="c2", analyst_key="satiroglu"),
        dict(comment_id="c3", analyst_key="gecer"),
    ])


class TestRunTopicSentiment:
    def test_pooled_and_within_analyst_aggregation(self, tmp_path):
        comments_path = _write(_comments_df(), tmp_path / "comments.parquet")
        topics_path = _write(_topics_df(), tmp_path / "topics.parquet")
        sentiment_path = _write(_sentiment_df(), tmp_path / "sentiment.parquet")

        result = run_topic_sentiment(
            comments_path, topics_path, sentiment_path,
            output_path=tmp_path / "topic_sentiment.parquet",
        )

        pooled = result.loc[result["configuration"] == "pooled"].set_index("topic_id")
        assert pooled.loc[0, "n_comments"] == 2
        assert pooled.loc[0, "n_positive"] == 1
        assert pooled.loc[0, "n_negative"] == 1
        assert pooled.loc[0, "positive_ratio"] == 0.5
        assert pooled.loc[0, "topic_label"] == "0_altin_gm_ons"
        assert pooled.loc[0, "analyst_key"] is None

        assert pooled.loc[1, "n_comments"] == 1
        assert pooled.loc[1, "n_positive"] == 1
        assert pooled.loc[1, "n_pseudo_neutral"] == 1
        assert pooled.loc[1, "positive_ratio"] == 1.0

        within = result.loc[result["configuration"] == "within_analyst"]
        assert set(within["analyst_key"]) == {"satiroglu", "gecer"}
        satiroglu_row = within.loc[within["analyst_key"] == "satiroglu"].iloc[0]
        assert satiroglu_row["topic_id"] == 0
        assert satiroglu_row["n_comments"] == 2
        assert satiroglu_row["topic_label"] == "0_within_label"

    def test_within_analyst_degrades_gracefully_without_comments(self, tmp_path):
        topics_path = _write(_topics_df(), tmp_path / "topics.parquet")
        sentiment_path = _write(_sentiment_df(), tmp_path / "sentiment.parquet")
        empty_comments_path = _write(pd.DataFrame(), tmp_path / "comments.parquet")

        result = run_topic_sentiment(
            empty_comments_path, topics_path, sentiment_path,
            output_path=tmp_path / "topic_sentiment.parquet",
        )

        within = result.loc[result["configuration"] == "within_analyst"]
        assert not within.empty
        assert within["analyst_key"].isna().all()

    def test_empty_topics_is_handled(self, tmp_path):
        comments_path = _write(_comments_df(), tmp_path / "comments.parquet")
        topics_path = _write(pd.DataFrame(), tmp_path / "topics.parquet")
        sentiment_path = _write(_sentiment_df(), tmp_path / "sentiment.parquet")

        result = run_topic_sentiment(
            comments_path, topics_path, sentiment_path,
            output_path=tmp_path / "topic_sentiment.parquet",
        )
        assert result.empty

    def test_empty_sentiment_is_handled(self, tmp_path):
        comments_path = _write(_comments_df(), tmp_path / "comments.parquet")
        topics_path = _write(_topics_df(), tmp_path / "topics.parquet")
        sentiment_path = _write(pd.DataFrame(), tmp_path / "sentiment.parquet")

        result = run_topic_sentiment(
            comments_path, topics_path, sentiment_path,
            output_path=tmp_path / "topic_sentiment.parquet",
        )
        assert result.empty

    def test_no_matching_comment_ids_is_handled(self, tmp_path):
        comments_path = _write(_comments_df(), tmp_path / "comments.parquet")
        topics_path = _write(_topics_df(), tmp_path / "topics.parquet")
        mismatched_sentiment = pd.DataFrame([
            dict(comment_id="zzz", sentiment_prob=0.5, sentiment_class="positive",
                 sentiment_pseudo_neutral=False, sentiment_target=None, sentiment_market_directed=None),
        ])
        sentiment_path = _write(mismatched_sentiment, tmp_path / "sentiment.parquet")

        result = run_topic_sentiment(
            comments_path, topics_path, sentiment_path,
            output_path=tmp_path / "topic_sentiment.parquet",
        )
        assert result.empty

    def test_outlier_topic_id_included(self, tmp_path):
        topics_df = pd.DataFrame([
            dict(comment_id="c1", topic_id=-1, topic_prob=0.0, topic_tier=None,
                 configuration="pooled", topic_label=None),
        ])
        sentiment_df = pd.DataFrame([
            dict(comment_id="c1", sentiment_prob=0.4, sentiment_class="negative",
                 sentiment_pseudo_neutral=False, sentiment_target=None, sentiment_market_directed=None),
        ])
        comments_path = _write(_comments_df(), tmp_path / "comments.parquet")
        topics_path = _write(topics_df, tmp_path / "topics.parquet")
        sentiment_path = _write(sentiment_df, tmp_path / "sentiment.parquet")

        result = run_topic_sentiment(
            comments_path, topics_path, sentiment_path,
            output_path=tmp_path / "topic_sentiment.parquet",
        )
        assert set(result["topic_id"]) == {-1}
        assert result.iloc[0]["n_negative"] == 1

    def test_scope_id_defaults_to_none_without_source_column(self, tmp_path):
        """Step 3.4 regression guard: the existing _topics_df() fixture has
        no scope_id column (pre-Step-3.2 shape) - output must degrade
        gracefully to None, exactly like analyst_key already does when
        comments.parquet is unavailable, not raise."""
        comments_path = _write(_comments_df(), tmp_path / "comments.parquet")
        topics_path = _write(_topics_df(), tmp_path / "topics.parquet")
        sentiment_path = _write(_sentiment_df(), tmp_path / "sentiment.parquet")

        result = run_topic_sentiment(
            comments_path, topics_path, sentiment_path,
            output_path=tmp_path / "topic_sentiment.parquet",
        )
        assert "scope_id" in result.columns
        assert result["scope_id"].isna().all()

    def test_scope_id_populated_when_present_in_topics_df(self, tmp_path):
        """Step 3.4: scope_id is carried through from topics.parquet's own
        already-resolved value, per (configuration[, analyst_key]) group -
        never re-derived here. Mirrors real post-Step-3.2 topics.parquet
        shape, where every row in a given scope shares one scope_id."""
        topics_df = pd.DataFrame([
            dict(comment_id="c1", topic_id=0, topic_prob=0.9, topic_tier=None,
                 configuration="pooled", scope_id="scope_pooled_x", topic_label="0_altin_gm_ons"),
            dict(comment_id="c2", topic_id=0, topic_prob=0.8, topic_tier=None,
                 configuration="pooled", scope_id="scope_pooled_x", topic_label="0_altin_gm_ons"),
            dict(comment_id="c3", topic_id=1, topic_prob=0.7, topic_tier=None,
                 configuration="pooled", scope_id="scope_pooled_x", topic_label="1_borsa_faiz"),
            dict(comment_id="c1", topic_id=0, topic_prob=0.9, topic_tier=None,
                 configuration="within_analyst", scope_id="scope_satiroglu_x", topic_label="0_within_label"),
            dict(comment_id="c2", topic_id=0, topic_prob=0.8, topic_tier=None,
                 configuration="within_analyst", scope_id="scope_satiroglu_x", topic_label="0_within_label"),
            dict(comment_id="c3", topic_id=1, topic_prob=0.7, topic_tier=None,
                 configuration="within_analyst", scope_id="scope_gecer_x", topic_label="1_within_label"),
        ])
        comments_path = _write(_comments_df(), tmp_path / "comments.parquet")
        topics_path = _write(topics_df, tmp_path / "topics.parquet")
        sentiment_path = _write(_sentiment_df(), tmp_path / "sentiment.parquet")

        result = run_topic_sentiment(
            comments_path, topics_path, sentiment_path,
            output_path=tmp_path / "topic_sentiment.parquet",
        )

        pooled = result.loc[result["configuration"] == "pooled"]
        assert (pooled["scope_id"] == "scope_pooled_x").all()

        satiroglu_row = result.loc[
            (result["configuration"] == "within_analyst") & (result["analyst_key"] == "satiroglu")
        ].iloc[0]
        assert satiroglu_row["scope_id"] == "scope_satiroglu_x"

        gecer_row = result.loc[
            (result["configuration"] == "within_analyst") & (result["analyst_key"] == "gecer")
        ].iloc[0]
        assert gecer_row["scope_id"] == "scope_gecer_x"
