"""
finfluencer.reporting.manuscript_data
========================================

Packaged version of the category-independent portion of the root-level
``build_manuscript_data.py`` script.

Scope note (Sprint 1B.1)
--------------------------
``build_manuscript_data.py`` produces seven artifacts. A column-by-
column reading of that script shows only three of them never touch a
``topic_category`` column: the per-analyst dataset-characteristics
table (``table1``), the sentiment-by-analyst figure data
(``fig1_data``), and the topic volcano-plot figure data
(``fig3_data``). This module packages exactly those three,
implemented here as :func:`build_dataset_characteristics_table`,
:func:`build_sentiment_by_analyst_figure_data`, and
:func:`build_topic_volcano_figure_data`.

The remaining four artifacts (Table 3, ``fig2_data``,
``topic_results_full``, ``top_pos5``/``top_neg5``) all read a
``topic_category`` column produced by a transformation with no
provenance anywhere in this repository's git history (exhaustive
``git log -S`` / ``--follow`` search, zero matches -- see the Sprint 1A
evidence report). Per the same rule applied throughout Sprint 1A, this
module does not invent replacement logic for that transformation and
does not implement those four artifacts.

Pipeline
--------
* :func:`build_dataset_characteristics_table` reads only
  ``videos.parquet`` and ``comments.parquet`` (raw); it never
  references the categorized master table at all, even in the
  original script.
* :func:`build_sentiment_by_analyst_figure_data` reads
  ``analyst_key``/``sentiment_prob`` from a master table. The
  original script reads these two columns from
  ``master_table_with_category.csv``; this function reads them from
  :func:`finfluencer.reporting.master_table.build_master_table`'s
  plain ``master_table.csv`` instead. This is not an assumption of
  equivalence: ``topic_category_map.csv`` has exactly one row per
  ``topic_id_pooled`` (verified), so joining it onto the master table
  adds a column without changing row count or any existing column's
  values -- and the original script's own sanity check
  (``len(df)==17566``) already implies the categorized table has the
  same row count Sprint 1A's differential test independently proved
  for the plain ``master_table.csv``.
* :func:`build_topic_volcano_figure_data` reads only
  ``inferential_results.json``'s ``E2_topic_sentiment.topic_results``
  -- entirely Sprint 1A's own output, with zero dependency on the
  categorized table.

This module does not fabricate, simulate, or otherwise substitute for
missing input data: every ``build_*`` function raises
:class:`~finfluencer.core.exceptions.CorpusValidationError` if its
source is empty.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from finfluencer.core.exceptions import CorpusValidationError
from finfluencer.core.logging import get_logger
from finfluencer.utils.io import ensure_parent, read_json, read_parquet

_log = get_logger(__name__)

#: analyst_key -> human-readable display name. Matches
#: build_manuscript_data.py's ``display_names`` dict exactly.
ANALYST_DISPLAY_NAMES = {
    "satiroglu": "Tunç Şatıroğlu",
    "yesilada": "Atilla Yeşilada",
    "basaran": "Mert Başaran",
    "gecer": "Selçuk Geçer",
}

#: Floor applied before -log10(p_fdr), to avoid -inf when p_fdr == 0.
#: Matches build_manuscript_data.py's fig3_data computation exactly.
NEGLOG10_P_FLOOR = 1e-300


def _require_nonempty(df: pd.DataFrame, *, name: str, path: Path) -> None:
    """Raise :class:`CorpusValidationError` if ``df`` has zero rows."""
    if df.empty:
        raise CorpusValidationError(
            f"{name} is empty; cannot build manuscript data from an empty source.",
            path=str(path), name=name,
        )


def _save_csv_utf8(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to CSV as plain UTF-8, ``index=False``.

    Deliberately does not use :func:`finfluencer.utils.io.write_csv`,
    for the same reason documented in
    :func:`finfluencer.reporting.master_table.save_master_table`:
    that helper writes UTF-8 *with a BOM* (``utf-8-sig``), whereas
    ``build_manuscript_data.py``'s own ``to_csv`` calls use plain
    UTF-8 throughout. Preserving the original script's exact encoding
    takes priority over reusing ``utils.io.write_csv`` here.
    """
    ensure_parent(path)
    df.to_csv(path, index=False, encoding="utf-8")


def build_dataset_characteristics_table(
    *,
    videos_path: Path = Path("data/raw/videos.parquet"),
    comments_path: Path = Path("data/raw/comments.parquet"),
) -> pd.DataFrame:
    """Build Table 1 (manuscript): per-analyst dataset characteristics.

    Behavior-preserving packaging of ``build_manuscript_data.py``'s
    Table 1 block: video-level counts (collected/eligible/selected)
    merged with comment-level counts (final videos, comments, date
    range, token/like statistics), one row per analyst, sorted by
    comment count descending, with a ``display_name`` column mapped
    from :data:`ANALYST_DISPLAY_NAMES`.

    Raises
    ------
    CorpusValidationError
        If either source table is empty.
    """
    videos = read_parquet(videos_path)
    _require_nonempty(videos, name="videos", path=videos_path)

    comments = read_parquet(comments_path)
    _require_nonempty(comments, name="comments", path=comments_path)

    vfun = videos.groupby("analyst_key").agg(
        n_collected=("video_id", "count"),
        n_eligible=("eligible", "sum"),
        n_selected=("selected", "sum"),
    ).reset_index()
    cfun = comments.groupby("analyst_key").agg(
        n_videos_final=("video_id", "nunique"),
        n_comments=("comment_id", "count"),
        date_min=("posted_date", "min"),
        date_max=("posted_date", "max"),
        mean_tokens=("n_tokens", "mean"),
        median_tokens=("n_tokens", "median"),
        mean_likes=("likes", "mean"),
    ).reset_index()

    table1 = vfun.merge(cfun, on="analyst_key")
    table1 = table1.sort_values("n_comments", ascending=False)
    table1["display_name"] = table1["analyst_key"].map(ANALYST_DISPLAY_NAMES)

    _log.info("dataset_characteristics_table_built", n_analysts=len(table1))
    return table1


def save_dataset_characteristics_table(
    df: pd.DataFrame, *, output_path: Path = Path("manuscript_table1.csv"),
) -> None:
    """Write Table 1 to CSV (plain UTF-8, ``index=False``).

    Default path is repo-root-relative, matching this package's own
    convention (e.g. ``master_table.py``'s ``Path("master_table.csv")``)
    rather than the original script's hardcoded ``/tmp/manuscript_table1.csv``,
    which was that researcher's own scratch-directory convention, not
    meaningful behavior to preserve.
    """
    _save_csv_utf8(df, Path(output_path))
    _log.info("dataset_characteristics_table_saved", path=str(output_path), n_rows=len(df))


def build_sentiment_by_analyst_figure_data(
    *, master_table_path: Path = Path("master_table.csv"),
) -> pd.DataFrame:
    """Build fig1_data (manuscript): per-comment analyst/sentiment pairs.

    Behavior-preserving packaging of ``build_manuscript_data.py``'s
    ``fig1_data = df[['analyst_key','sentiment_prob']].copy()`` --
    see the module docstring for why reading these two columns from
    the plain ``master_table.csv`` (Sprint 1A's output) rather than
    the categorized table is evidence-supported, not assumed.

    Raises
    ------
    CorpusValidationError
        If the master table is empty.
    """
    master = pd.read_csv(master_table_path, usecols=["analyst_key", "sentiment_prob"])
    _require_nonempty(master, name="master_table", path=master_table_path)

    fig1_data = master[["analyst_key", "sentiment_prob"]].copy()
    _log.info("sentiment_by_analyst_figure_data_built", n_rows=len(fig1_data))
    return fig1_data


def save_sentiment_by_analyst_figure_data(
    df: pd.DataFrame, *, output_path: Path = Path("manuscript_fig1_data.csv"),
) -> None:
    """Write fig1_data to CSV (plain UTF-8, ``index=False``). See
    :func:`save_dataset_characteristics_table` for the default-path
    rationale (repo-root-relative, not the original's ``/tmp/`` path)."""
    _save_csv_utf8(df, Path(output_path))
    _log.info("sentiment_by_analyst_figure_data_saved", path=str(output_path), n_rows=len(df))


def build_topic_volcano_figure_data(
    *, inferential_results_path: Path = Path("inferential_results.json"),
) -> pd.DataFrame:
    """Build fig3_data (manuscript): per-topic volcano-plot data.

    Behavior-preserving packaging of ``build_manuscript_data.py``'s
    fig3 block. Reads only ``inferential_results.json``'s
    ``E2_topic_sentiment.topic_results`` (Sprint 1A's own
    :func:`finfluencer.reporting.inferential.run_e2_topic_sentiment`
    output) -- no ``topic_category`` dependency at all.

    Raises
    ------
    CorpusValidationError
        If ``topic_results`` is empty.
    """
    inf = read_json(inferential_results_path)
    topic_results = pd.DataFrame(inf["E2_topic_sentiment"]["topic_results"])
    _require_nonempty(topic_results, name="topic_results", path=inferential_results_path)

    topic_results = topic_results.copy()
    topic_results["neglog10_p_fdr"] = -np.log10(topic_results["p_fdr"].clip(lower=NEGLOG10_P_FLOOR))
    fig3_data = topic_results[
        ["topic_id", "topic_label", "cohens_h", "p_fdr", "neglog10_p_fdr", "significant_fdr", "n"]
    ].copy()

    _log.info("topic_volcano_figure_data_built", n_topics=len(fig3_data))
    return fig3_data


def save_topic_volcano_figure_data(
    df: pd.DataFrame, *, output_path: Path = Path("manuscript_fig3_data.csv"),
) -> None:
    """Write fig3_data to CSV (plain UTF-8, ``index=False``). See
    :func:`save_dataset_characteristics_table` for the default-path
    rationale (repo-root-relative, not the original's ``/tmp/`` path)."""
    _save_csv_utf8(df, Path(output_path))
    _log.info("topic_volcano_figure_data_saved", path=str(output_path), n_rows=len(df))


__all__ = [
    "build_dataset_characteristics_table",
    "save_dataset_characteristics_table",
    "build_sentiment_by_analyst_figure_data",
    "save_sentiment_by_analyst_figure_data",
    "build_topic_volcano_figure_data",
    "save_topic_volcano_figure_data",
    "ANALYST_DISPLAY_NAMES",
    "NEGLOG10_P_FLOOR",
]
