"""
finfluencer.reporting.master_table
=====================================

Packaged version of the root-level ``export_master_table.py`` script:
builds the comment-level master analysis table that
:mod:`finfluencer.reporting.inferential` (and, historically,
``run_inferential_tests.py``) reads as its sole input.

Pipeline
--------
1. Read ``comments.parquet`` (raw comment text/metadata),
   ``sentiment.parquet`` (per-comment sentiment class/probability), and
   ``topics.parquet`` (per-comment topic assignment, in two BERTopic
   configurations: ``pooled`` and ``within_analyst``).
2. Split the topic table into its two configurations and rename their
   columns with ``_pooled`` / ``_within`` suffixes so both can be
   left-joined onto the same comment row without a column collision.
3. Left-join sentiment and both topic configurations onto every raw
   comment, on ``comment_id``.

Scope note (Sprint 1A)
-----------------------
This module is a direct, behavior-preserving packaging of
``export_master_table.py`` only. It intentionally excludes the
downstream topic-category join performed by the untracked
``build_manuscript_data.py`` script (which reads a
``master_table_with_category.csv`` this module does not produce): a
repository-wide history search found no implementation of that
categorization step anywhere in git history, so Sprint 1A does not
reconstruct it. See the Sprint 1A evidence report for details.

This module does not fabricate, simulate, or otherwise substitute for
missing input data: :func:`build_master_table` raises
:class:`~finfluencer.core.exceptions.CorpusValidationError` if any of
the three required source tables is empty.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from finfluencer.core.exceptions import CorpusValidationError
from finfluencer.core.logging import get_logger
from finfluencer.utils.io import ensure_parent, read_parquet

_log = get_logger(__name__)

#: Comment-level columns carried through from the raw comments table.
#: Matches ``export_master_table.py`` line 21 exactly.
COMMENT_COLUMNS = [
    "comment_id", "video_id", "analyst_key", "posted_date",
    "text_clean", "n_tokens", "likes",
]

#: Sentiment columns joined onto each comment.
SENTIMENT_COLUMNS = ["comment_id", "sentiment_class", "sentiment_prob"]

#: Value of ``topics.parquet["configuration"]`` for the pooled (cross-analyst)
#: BERTopic run.
POOLED_CONFIGURATION = "pooled"

#: Value of ``topics.parquet["configuration"]`` for the within-analyst
#: BERTopic run.
WITHIN_ANALYST_CONFIGURATION = "within_analyst"


def _require_nonempty(df: pd.DataFrame, *, name: str, path: Path) -> None:
    """Raise :class:`CorpusValidationError` if ``df`` has zero rows."""
    if df.empty:
        raise CorpusValidationError(
            f"{name} is empty; cannot build the master table from an empty source.",
            path=str(path), name=name,
        )


def _pooled_topics(topics: pd.DataFrame) -> pd.DataFrame:
    """Extract and rename the ``pooled`` BERTopic configuration slice.

    Mirrors ``export_master_table.py`` lines 14-15 exactly.
    """
    pooled = topics[topics["configuration"] == POOLED_CONFIGURATION][
        ["comment_id", "topic_id", "topic_label", "topic_prob"]
    ]
    return pooled.rename(columns={
        "topic_id": "topic_id_pooled",
        "topic_label": "topic_label_pooled",
        "topic_prob": "topic_prob_pooled",
    })


def _within_analyst_topics(topics: pd.DataFrame) -> pd.DataFrame:
    """Extract and rename the ``within_analyst`` BERTopic configuration slice.

    Mirrors ``export_master_table.py`` lines 17-18 exactly. Note this
    configuration carries no ``topic_prob`` column, matching the
    original script (only ``topic_id``/``topic_label`` are kept).
    """
    within = topics[topics["configuration"] == WITHIN_ANALYST_CONFIGURATION][
        ["comment_id", "topic_id", "topic_label"]
    ]
    return within.rename(columns={
        "topic_id": "topic_id_within",
        "topic_label": "topic_label_within",
    })


def build_master_table(
    *,
    comments_path: Path = Path("data/raw/comments.parquet"),
    topics_path: Path = Path("data/processed/topics.parquet"),
    sentiment_path: Path = Path("data/processed/sentiment.parquet"),
) -> pd.DataFrame:
    """Build the comment-level master analysis table.

    Behavior-preserving packaging of ``export_master_table.py``:
    left-joins sentiment and both topic configurations (pooled,
    within-analyst) onto every raw comment, on ``comment_id``. Row
    count, column set, and values match the original script's
    ``master_table.csv`` output exactly — see the differential test in
    ``tests/unit/test_reporting/test_master_table.py``.

    Parameters
    ----------
    comments_path, topics_path, sentiment_path
        Paths to the three source Parquet files. Defaults match the
        paths the original script used implicitly (relative to the
        repository root).

    Returns
    -------
    pd.DataFrame
        One row per comment, with columns:
        ``comment_id, video_id, analyst_key, posted_date, text_clean,
        n_tokens, likes, sentiment_class, sentiment_prob,
        topic_id_pooled, topic_label_pooled, topic_prob_pooled,
        topic_id_within, topic_label_within``.

    Raises
    ------
    CorpusValidationError
        If any of the three source tables is empty.
    """
    comments = read_parquet(comments_path)
    _require_nonempty(comments, name="comments", path=comments_path)

    topics = read_parquet(topics_path)
    _require_nonempty(topics, name="topics", path=topics_path)

    sentiment = read_parquet(sentiment_path)
    _require_nonempty(sentiment, name="sentiment", path=sentiment_path)

    tp_pooled = _pooled_topics(topics)
    tp_within = _within_analyst_topics(topics)

    master = (
        comments[COMMENT_COLUMNS]
        .merge(sentiment[SENTIMENT_COLUMNS], on="comment_id", how="left")
        .merge(tp_pooled, on="comment_id", how="left")
        .merge(tp_within, on="comment_id", how="left")
    )

    _log.info(
        "master_table_built",
        n_rows=len(master),
        n_null_sentiment=int(master["sentiment_class"].isna().sum()),
        n_null_topic_pooled=int(master["topic_id_pooled"].isna().sum()),
    )
    return master


def save_master_table(df: pd.DataFrame, *, output_path: Path = Path("master_table.csv")) -> None:
    """Write the master table to CSV.

    Deliberately does **not** use :func:`finfluencer.utils.io.write_csv`:
    that helper writes UTF-8 *with a BOM* (``utf-8-sig``), whereas the
    original ``export_master_table.py`` writes plain UTF-8
    (``encoding="utf-8"``), and the sole downstream consumer —
    ``run_inferential_tests.py`` / :func:`finfluencer.reporting.inferential.load_master_table`
    — reads it back with ``pd.read_csv(..., parse_dates=["posted_date"])``
    and no ``encoding`` override. A BOM would silently corrupt the
    first column's name (``"comment_id"`` becomes ``"\\ufeffcomment_id"``)
    on that read. Preserving the original script's exact encoding takes
    priority over reusing ``utils.io.write_csv`` here, per the Sprint 1A
    rule to preserve existing behavior over infrastructure reuse when
    the two conflict.
    """
    p = Path(output_path)
    ensure_parent(p)
    df.to_csv(p, index=False, encoding="utf-8")
    _log.info("master_table_saved", path=str(p), n_rows=len(df))


__all__ = [
    "build_master_table",
    "save_master_table",
    "COMMENT_COLUMNS",
    "SENTIMENT_COLUMNS",
    "POOLED_CONFIGURATION",
    "WITHIN_ANALYST_CONFIGURATION",
]
