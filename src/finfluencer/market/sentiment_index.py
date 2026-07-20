"""
finfluencer.market.sentiment_index
=====================================

Pooled daily sentiment index construction - the single input series
required by the minimal confirmatory analysis (see
``finfluencer.market.confirmatory_analysis``).

This module reads ``data/raw/comments.parquet`` and
``data/processed/sentiment.parquet`` READ-ONLY (existing NLP pipeline
outputs; never modified) and writes exactly one new artefact:

    data/processed/market_sentiment/sentiment_index_daily.parquet

Index definition
-----------------
For each comment, ``sentiment_prob`` (P(positive), in [0, 1]; the same
continuous variable already used for Table 1 / Figure 1 / E1 elsewhere
in this manuscript) is pooled UNWEIGHTED across all four analysts and
averaged within a trading day. "Pooled unweighted" is the pre-specified
confirmatory index (design doc Section 1.6) - engagement-weighted and
analyst-specific indices remain exploratory/future-research and are
NOT built here.

Calendar alignment
--------------------
Comments posted on a non-trading day (weekend/holiday) are assigned
forward to the NEXT trading day present in ``market_data.parquet``,
consistent with the pre-committed alignment rule in the design doc
(Section 2.1): a comment posted on a Saturday is attributed to the
following Monday's (or next trading day's) sentiment index, not
dropped and not attributed backward. This is a forward-only mapping,
so it introduces no look-ahead leakage into the resulting index.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from finfluencer.core.exceptions import DataError
from finfluencer.core.logging import get_logger
from finfluencer.utils.io import ensure_parent, read_parquet, write_parquet

_log = get_logger(__name__)


def _map_to_next_trading_day(dates: pd.Series, trading_days: pd.Series) -> pd.Series:
    """Map each date in ``dates`` to the smallest trading day >= that date.

    Implemented via a sorted-merge ("merge_asof", direction="forward")
    rather than a per-row search, so this scales to the full comment
    corpus without a Python-level loop.
    """
    trading_days_sorted = pd.Series(sorted(pd.to_datetime(trading_days).unique()))
    left = pd.DataFrame({"posted_date": pd.to_datetime(dates)}).sort_values("posted_date")
    right = pd.DataFrame({"trading_date": trading_days_sorted}).sort_values("trading_date")
    mapped = pd.merge_asof(
        left, right, left_on="posted_date", right_on="trading_date", direction="forward",
    )
    return mapped.set_index(left.index)["trading_date"]


def build_pooled_sentiment_index(
    *,
    comments_path: Path = Path("data/raw/comments.parquet"),
    sentiment_path: Path = Path("data/processed/sentiment.parquet"),
    market_data_path: Path = Path("data/market/market_data.parquet"),
    output_path: Path = Path("data/processed/market_sentiment/sentiment_index_daily.parquet"),
) -> pd.DataFrame:
    """Build and persist the pooled, unweighted daily sentiment index.

    Returns the DataFrame (also written to ``output_path``) with
    columns: ``trading_date``, ``sentiment_index``, ``n_comments``.

    Requires ``market_data_path`` to already exist (its ``date`` column
    supplies the trading calendar used for forward-mapping). This keeps
    the trading calendar as a single source of truth (the real,
    provider-observed set of trading days) rather than a second,
    potentially-inconsistent calendar definition.
    """
    comments = read_parquet(comments_path)
    for col in ("comment_id", "posted_date"):
        if col not in comments.columns:
            raise DataError(
                f"comments.parquet missing required column {col!r}",
                path=str(comments_path), columns=list(comments.columns),
            )

    sentiment = read_parquet(sentiment_path)
    for col in ("comment_id", "sentiment_prob"):
        if col not in sentiment.columns:
            raise DataError(
                f"sentiment.parquet missing required column {col!r}",
                path=str(sentiment_path), columns=list(sentiment.columns),
            )

    merged = comments[["comment_id", "posted_date"]].merge(
        sentiment[["comment_id", "sentiment_prob"]], on="comment_id", how="inner",
    )
    if len(merged) != len(comments):
        _log.warning(
            "sentiment_comment_join_incomplete",
            n_comments=len(comments), n_matched=len(merged),
        )
    if merged.empty:
        raise DataError("No comments matched a sentiment score; cannot build index")

    market_data_path = Path(market_data_path)
    if not market_data_path.exists():
        raise DataError(
            "market_data.parquet not found; the trading calendar it supplies is "
            "required to forward-map comment dates to trading days. Run "
            "finfluencer.market.collect_market_data first.",
            path=str(market_data_path),
        )
    market_data = read_parquet(market_data_path)
    if "date" not in market_data.columns:
        raise DataError("market_data.parquet missing 'date' column", path=str(market_data_path))

    merged["trading_date"] = _map_to_next_trading_day(merged["posted_date"], market_data["date"])
    n_unmapped = merged["trading_date"].isna().sum()
    if n_unmapped:
        _log.warning(
            "comments_after_last_trading_day_dropped",
            n_dropped=int(n_unmapped),
            note="Comments posted after the last available trading day have no "
                 "forward trading day to map to and are excluded from the index.",
        )
        merged = merged.dropna(subset=["trading_date"])

    daily = (
        merged.groupby("trading_date")["sentiment_prob"]
        .agg(sentiment_index="mean", n_comments="count")
        .reset_index()
        .sort_values("trading_date")
    )

    ensure_parent(output_path)
    write_parquet(daily, output_path)
    _log.info(
        "sentiment_index_built",
        n_trading_days=len(daily), n_comments_used=int(merged.shape[0]),
        date_min=str(daily["trading_date"].min().date()) if not daily.empty else None,
        date_max=str(daily["trading_date"].max().date()) if not daily.empty else None,
    )
    return daily


__all__ = ["build_pooled_sentiment_index"]
