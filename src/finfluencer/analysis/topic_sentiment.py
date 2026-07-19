"""
finfluencer.analysis.topic_sentiment
=======================================

Phase 2.4: topic x sentiment cross-analysis.
``topics.parquet`` + ``sentiment.parquet`` -> ``topic_sentiment.parquet``
(TopicSentimentRecord schema).

No checkpointing
-----------------
Unlike the topics/sentiment stages themselves (expensive model
fits/inference, hence Tier-2/Tier-3 checkpointed), this is a cheap,
deterministic pandas aggregation over two already-computed outputs.
Re-running always recomputes from scratch; there is nothing to cache.

Scope
-----
Purely descriptive counts/ratios per ``(configuration, topic_id[,
analyst_key])`` group:

* ``pooled`` rows are grouped by ``topic_id`` only (``analyst_key`` is
  always ``None`` — pooled is cross-analyst by definition, matching
  :mod:`finfluencer.topics.pipeline`'s own convention).
* ``within_analyst`` rows are grouped by ``(analyst_key, topic_id)``
  when ``comments.parquet`` is available to resolve ``analyst_key``;
  degrades to ``topic_id``-only grouping (with ``analyst_key=None``)
  if it is not.

Formal significance testing (chi-square, Bonferroni/FDR correction)
belongs to the later statistics module (``StatisticsConfig``) and is
out of scope here.

Migration Step 3.4 — ``scope_id``
----------------------------------
``scope_id`` (``TopicSentimentRecord``, additive since Step 3.1) is now
populated on every output row, carried through from ``topics_path``'s
own already-populated ``scope_id`` column (set by
:mod:`finfluencer.topics.pipeline`'s ``run_topics()`` — see Step 3.2)
rather than re-derived here. This module never calls
:func:`finfluencer.scope.resolve_scope` itself; it only reads a value
that already exists on the joined frame, consistent with the
"resolve once, persist, never re-derive" principle the rest of Phase 3
established. ``configuration``/``analyst_key`` are unchanged and still
populated exactly as before — this is additive, not a breaking change.
If ``topics_path``'s frame has no ``scope_id`` column at all (a
``topics.parquet`` predating Step 3.2), ``scope_id`` degrades
gracefully to ``None`` on every row, the same way ``analyst_key``
already degrades when ``comments.parquet`` is unavailable.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from finfluencer.core.contracts import SentimentClass, TopicSentimentRecord
from finfluencer.core.logging import get_logger
from finfluencer.utils.io import read_parquet, write_parquet

_log = get_logger(__name__)
_INDEX_COLUMNS: list[str] = list(TopicSentimentRecord.model_fields.keys())
_DEFAULT_OUTPUT = Path("data/processed/topic_sentiment.parquet")


def _empty_index() -> pd.DataFrame:
    return pd.DataFrame(columns=_INDEX_COLUMNS)


def _topic_label_of(group: pd.DataFrame) -> str | None:
    if "topic_label" not in group.columns or group.empty:
        return None
    value = group["topic_label"].iloc[0]
    return None if pd.isna(value) else value


def _scope_id_of(group: pd.DataFrame) -> str | None:
    """Read this group's already-resolved ``scope_id`` from ``topics_df``
    (carried through the merge in :func:`run_topic_sentiment`). Never
    re-derives a scope - mirrors :func:`_topic_label_of`'s pattern of
    taking a representative value from the group rather than
    validating every row agrees (the group is already partitioned by
    ``configuration``[, ``analyst_key``], so every row should share one
    ``scope_id`` by construction). Degrades to ``None`` if the source
    frame predates Step 3.2 and has no ``scope_id`` column."""
    if "scope_id" not in group.columns or group.empty:
        return None
    value = group["scope_id"].iloc[0]
    return None if pd.isna(value) else value


def _aggregate_group(group: pd.DataFrame) -> dict:
    n_comments = len(group)
    n_positive = int((group["sentiment_class"] == SentimentClass.positive.value).sum())
    n_negative = int((group["sentiment_class"] == SentimentClass.negative.value).sum())
    n_pseudo_neutral = int(group["sentiment_pseudo_neutral"].sum())
    denom = n_positive + n_negative
    positive_ratio = (n_positive / denom) if denom > 0 else None
    mean_sentiment_prob = (
        float(group["sentiment_prob"].mean()) if n_comments > 0 else None
    )
    return {
        "n_comments": n_comments,
        "n_positive": n_positive,
        "n_negative": n_negative,
        "n_pseudo_neutral": n_pseudo_neutral,
        "positive_ratio": positive_ratio,
        "mean_sentiment_prob": mean_sentiment_prob,
    }


def _pooled_rows(joined: pd.DataFrame) -> list[dict]:
    pooled = joined.loc[joined["configuration"] == "pooled"]
    records: list[dict] = []
    for topic_id, group in pooled.groupby("topic_id"):
        records.append({
            "configuration": "pooled",
            "analyst_key": None,
            "scope_id": _scope_id_of(group),
            "topic_id": topic_id,
            "topic_label": _topic_label_of(group),
            **_aggregate_group(group),
        })
    return records


def _within_analyst_rows(joined: pd.DataFrame, *, has_analyst_key: bool) -> list[dict]:
    within = joined.loc[joined["configuration"] == "within_analyst"]
    records: list[dict] = []
    if within.empty:
        return records

    if has_analyst_key:
        for (analyst_key, topic_id), group in within.groupby(["analyst_key", "topic_id"]):
            records.append({
                "configuration": "within_analyst",
                "analyst_key": analyst_key,
                "scope_id": _scope_id_of(group),
                "topic_id": topic_id,
                "topic_label": _topic_label_of(group),
                **_aggregate_group(group),
            })
    else:
        for topic_id, group in within.groupby("topic_id"):
            records.append({
                "configuration": "within_analyst",
                "analyst_key": None,
                "scope_id": _scope_id_of(group),
                "topic_id": topic_id,
                "topic_label": _topic_label_of(group),
                **_aggregate_group(group),
            })
    return records


def run_topic_sentiment(
    comments_path: Path | str,
    topics_path: Path | str,
    sentiment_path: Path | str,
    *,
    output_path: Path | str | None = None,
) -> pd.DataFrame:
    """Join topics + sentiment on ``comment_id`` and aggregate descriptively.

    Parameters
    ----------
    comments_path
        Source ``comments.parquet``; only ``analyst_key`` is used, to
        resolve the ``within_analyst`` breakdown. Missing/empty
        degrades gracefully (see :func:`_within_analyst_rows`).
    topics_path
        ``topics.parquet`` from :mod:`finfluencer.topics.pipeline`.
    sentiment_path
        ``sentiment.parquet`` from :mod:`finfluencer.sentiment.pipeline`.
    output_path
        Destination. Defaults to ``data/processed/topic_sentiment.parquet``.
    """
    comments_path = Path(comments_path)
    topics_path = Path(topics_path)
    sentiment_path = Path(sentiment_path)
    output_path = Path(output_path) if output_path is not None else _DEFAULT_OUTPUT

    topics_df = read_parquet(topics_path)
    sentiment_df = read_parquet(sentiment_path)

    if (
        topics_df.empty or sentiment_df.empty
        or "topic_id" not in topics_df.columns
        or "comment_id" not in sentiment_df.columns
    ):
        _log.warning("topic_sentiment_no_input_available")
        empty = _empty_index()
        write_parquet(empty, output_path)
        return empty

    joined = topics_df.merge(
        sentiment_df[
            ["comment_id", "sentiment_class", "sentiment_prob", "sentiment_pseudo_neutral"]
        ],
        on="comment_id", how="inner",
    )
    if joined.empty:
        _log.warning("topic_sentiment_no_matching_rows")
        empty = _empty_index()
        write_parquet(empty, output_path)
        return empty

    comments_df = read_parquet(comments_path)
    has_analyst_key = not comments_df.empty and "analyst_key" in comments_df.columns
    if has_analyst_key:
        joined = joined.merge(
            comments_df[["comment_id", "analyst_key"]], on="comment_id", how="left",
        )

    records = _pooled_rows(joined) + _within_analyst_rows(joined, has_analyst_key=has_analyst_key)

    result_df = (
        pd.DataFrame.from_records(records, columns=_INDEX_COLUMNS)
        if records else _empty_index()
    )
    write_parquet(result_df, output_path)
    _log.info("topic_sentiment_stage_summary", n_rows_out=len(result_df))
    return result_df


__all__ = ["run_topic_sentiment"]
