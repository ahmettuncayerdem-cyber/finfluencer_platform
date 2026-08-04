"""
finfluencer.reporting.manuscript_figures
===========================================

Packaged version of the root-level ``build_stats_figures.py`` script:
the six supplementary manuscript figures (Figures S1-S6) built from
Sprint 1A's reporting outputs (``master_table.csv``,
``inferential_results.json``, and its four side-CSVs).

Pipeline
--------
* **Figure S1** -- violin plot of ``sentiment_prob`` by analyst, with
  Dunn's post-hoc significance brackets.
* **Figure S2** -- naive vs. video-clustered standard errors (E1b).
* **Figure S3** -- topic-level volcano plot (E2: Cohen's h vs.
  -log10 FDR-adjusted p).
* **Figure S4** -- messenger-vs-message R-squared decomposition (E3).
* **Figure S5** -- video-level comment volume vs. mean sentiment,
  with a log-linear fit (R3).
* **Figure S6** -- cross-analyst weekly sentiment correlation heatmap
  (R2).

One function per figure, each taking already-loaded data (not a file
path) and writing a PNG + SVG pair -- matching
:func:`finfluencer.market.figures.plot_sentiment_vs_bist100`'s
"data in, ``Path`` out" convention rather than
:mod:`finfluencer.reporting.manuscript_data`'s "path in, DataFrame
out" convention (that module's functions are the load step; these are
the presentation step, and the two are kept separate exactly as
``market/confirmatory_analysis.py`` vs. ``market/figures.py`` already
does in this codebase).
:func:`build_all_manuscript_figures` is the lightweight orchestrator:
it loads every input once and calls each ``plot_*`` function in turn.

Deliberate packaging adaptations (behavior of the *rendered figures*
is unchanged; only how the module behaves when merely imported changes)
---------------------------------------------------------------------
* The original script calls ``matplotlib.use("Agg")`` at module level,
  forcing a non-interactive backend for the whole process. A packaged
  library module should not silently override its importer's
  matplotlib backend choice as a side effect of import --
  ``market/figures.py`` (this project's own established figure-module
  template) does not do this either, so this module follows that
  precedent and omits it.
* The original script calls ``plt.rcParams.update({...})`` once at
  module level, mutating global matplotlib state for the rest of the
  process merely by being imported. This module applies the exact
  same rcParams values, but does so inside each ``plot_*`` call rather
  than at import time, so that importing this module has no global
  side effect and the styling is still applied identically whenever a
  figure is actually produced.

Every hardcoded annotation from the original script (Figure S1's
title stats and significance brackets, "n=17,566 comments, 250
videos" in Figure S2's title, "n=120 topics" in Figure S3's title,
"n=11 common weeks" in Figure S6's title) is preserved as a literal
constant, not recomputed from the passed-in data -- this is not new
statistical logic, and the original script's own fragility (these
strings can silently go stale if the underlying statistics change) is
inherited unchanged, per the Sprint 1B rule to preserve existing
behavior rather than improve on it.

This module does not fabricate, simulate, or otherwise substitute for
missing input data: every ``plot_*`` function raises
:class:`~finfluencer.core.exceptions.CorpusValidationError` if given
an empty DataFrame.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.typing import RcKeyType

from finfluencer.core.exceptions import CorpusValidationError
from finfluencer.core.logging import get_logger
from finfluencer.utils.io import ensure_dir, read_json

_log = get_logger(__name__)

#: Okabe-Ito colourblind-safe palette. Matches build_stats_figures.py's
#: ``OI`` dict exactly (also the palette used by market/figures.py).
OKABE_ITO_PALETTE = {
    "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73", "yellow": "#F0E442",
    "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7", "black": "#000000",
}

#: Canonical analyst display order for multi-analyst figures (S1, S6).
#: Matches build_stats_figures.py's ``order`` list exactly.
ANALYST_ORDER = ["satiroglu", "gecer", "basaran", "yesilada"]

#: Per-analyst bar/violin colors, in ``ANALYST_ORDER`` order. Matches
#: build_stats_figures.py's ``colors`` list exactly.
ANALYST_COLORS = [
    OKABE_ITO_PALETTE["blue"], OKABE_ITO_PALETTE["green"],
    OKABE_ITO_PALETTE["orange"], OKABE_ITO_PALETTE["vermillion"],
]

#: rcParams applied by every plot_* call. Matches build_stats_figures.py's
#: module-level ``plt.rcParams.update({...})`` values exactly; applied
#: per-call rather than at import time -- see module docstring.
#:
#: Typed as ``dict[RcKeyType, Any]`` (matplotlib >=3.11's own key-literal
#: type for ``RcParams``), not a plain ``dict[str, float]`` -- without
#: this, mypy widens the dict literal's keys to ``str``, which
#: ``RcParams.update()`` (inherited from ``dict[RcKeyType, Any]``,
#: `matplotlib/typing.py`'s ``RcKeyType`` being a large ``Literal[...]``
#: of every valid rcParam name) then rejects at each of the six call
#: sites below -- a real type mismatch, not a false positive: a plain
#: ``str`` key is not verified to be a valid rcParam name. Annotating
#: with ``RcKeyType`` directly makes mypy check each literal key here
#: against matplotlib's own known-valid set (catching typos), which is
#: strictly more type-safe than the plain-``dict`` form it replaces, not
#: a suppression of anything.
_RC_PARAMS: dict[RcKeyType, Any] = {
    "font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "savefig.dpi": 300,
}


def _require_nonempty(df: pd.DataFrame, *, name: str) -> None:
    """Raise :class:`CorpusValidationError` if ``df`` has zero rows."""
    if df.empty:
        raise CorpusValidationError(
            f"{name} is empty; cannot plot a figure from an empty source.", name=name,
        )


def _save_figure(fig: Figure, name: str, *, output_dir: Path) -> list[Path]:
    """Save a completed figure as both PNG (300dpi) and SVG, matching
    build_stats_figures.py's ``save()`` helper exactly, then close it."""
    out = ensure_dir(output_dir)
    png_path = out / f"{name}.png"
    svg_path = out / f"{name}.svg"
    fig.savefig(png_path, bbox_inches="tight", dpi=300)
    fig.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)
    return [png_path, svg_path]


def plot_sentiment_violin_by_analyst(
    master_table: pd.DataFrame, *, output_dir: Path = Path("stats_figures"),
) -> list[Path]:
    """Figure S1: violin plot of ``sentiment_prob`` by analyst, with
    Dunn's post-hoc significance brackets (Holm-adjusted, hardcoded
    from the manuscript's already-computed E1/E1-post-hoc results,
    matching build_stats_figures.py exactly).

    ``master_table`` must have ``analyst_key`` and ``sentiment_prob``
    columns (e.g. :func:`finfluencer.reporting.master_table.build_master_table`'s
    output).
    """
    _require_nonempty(master_table, name="master_table")
    plt.rcParams.update(_RC_PARAMS)

    data = [master_table.loc[master_table["analyst_key"] == a, "sentiment_prob"].values
            for a in ANALYST_ORDER]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    # matplotlib-stubs' violinplot signature and its "bodies" return type are
    # both narrower than what it accepts/returns at runtime (a list of plain
    # numpy arrays here, always); both ignores are stub-precision issues, not
    # bugs in this code.
    parts = ax.violinplot(data, showmedians=True, widths=0.7)  # type: ignore[arg-type]
    for pc, c in zip(parts["bodies"], ANALYST_COLORS, strict=True):  # type: ignore[call-overload]
        pc.set_facecolor(c)
        pc.set_alpha(0.6)
    ax.set_xticks(range(1, 5))
    ax.set_xticklabels(ANALYST_ORDER)
    ax.set_ylabel("Sentiment probability (P[positive])")
    ax.set_title("Figure S1. Sentiment score distribution by analyst\n"
                 "(Kruskal-Wallis H=990.6, p<.001, ε²=0.056)")

    # Significance brackets: all pairs except basaran-yesilada are "***",
    # that one pair is "*". Hardcoded from Dunn's Holm-adjusted post-hoc
    # (E1), matching build_stats_figures.py's ``pairs`` list exactly.
    pairs = [(1, 3, "***"), (2, 3, "***"), (3, 4, "***"), (1, 2, "***"), (2, 4, "***"), (1, 4, "*")]
    ymax = 1.02
    step = 0.09
    for i, (a, b, sig) in enumerate(pairs):
        y = ymax + i * step
        ax.plot([a, a, b, b], [y, y + 0.02, y + 0.02, y], color="black", linewidth=0.8)
        ax.text((a + b) / 2, y + 0.025, sig, ha="center", fontsize=9)
    ax.set_ylim(0, 1.6)

    paths = _save_figure(fig, "figS1_sentiment_violin_by_analyst", output_dir=output_dir)
    _log.info("figure_saved", figure="S1", paths=[str(p) for p in paths])
    return paths


def plot_cluster_robust_se_comparison(
    e1b_cluster_robustness: dict[str, Any], *, output_dir: Path = Path("stats_figures"),
) -> list[Path]:
    """Figure S2: naive vs. video-clustered standard errors (E1b).

    ``e1b_cluster_robustness`` must be
    ``inferential_results["E1b_cluster_robustness"]`` (Sprint 1A's
    :func:`finfluencer.reporting.inferential.run_e1b_cluster_robustness`
    output).
    """
    plt.rcParams.update(_RC_PARAMS)

    e1b = e1b_cluster_robustness
    coefs = list(e1b["naive_se"].keys())
    naive = [e1b["naive_se"][c] for c in coefs]
    clust = [e1b["cluster_se"][c] for c in coefs]
    labels = [c.replace("C(analyst_key)[T.", "").replace("]", "") for c in coefs]
    x = np.arange(len(coefs))

    fig, ax = plt.subplots(figsize=(7, 4))
    w = 0.35
    ax.bar(x - w / 2, naive, width=w, label="Naive SE (i.i.d. assumption)", color=OKABE_ITO_PALETTE["sky"])
    ax.bar(x + w / 2, clust, width=w, label="Cluster-robust SE (by video_id)", color=OKABE_ITO_PALETTE["vermillion"])
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15)
    ax.set_ylabel("Standard error")
    ax.set_title("Figure S2. Naive vs. video-clustered standard errors\n"
                 "(logistic model, n=17,566 comments, 250 videos)")
    ax.legend(frameon=False)

    paths = _save_figure(fig, "figS2_cluster_robust_se", output_dir=output_dir)
    _log.info("figure_saved", figure="S2", paths=[str(p) for p in paths])
    return paths


def plot_topic_volcano(
    topic_level_results: pd.DataFrame, *, output_dir: Path = Path("stats_figures"),
) -> list[Path]:
    """Figure S3: topic-level volcano plot (E2).

    ``topic_level_results`` must have ``cohens_h``, ``p_fdr``, and
    ``significant_fdr`` columns (e.g.
    ``topic_level_test_results.csv``, Sprint 1A's
    :func:`finfluencer.reporting.inferential.run_e2_topic_sentiment`
    side-output).
    """
    _require_nonempty(topic_level_results, name="topic_level_results")
    plt.rcParams.update(_RC_PARAMS)

    topic_df = topic_level_results
    sig = topic_df["significant_fdr"]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(topic_df.loc[~sig, "cohens_h"], -np.log10(topic_df.loc[~sig, "p_fdr"].clip(lower=1e-300)),
               color="grey", alpha=0.5, s=25, label="Not significant (FDR)")
    ax.scatter(topic_df.loc[sig, "cohens_h"], -np.log10(topic_df.loc[sig, "p_fdr"].clip(lower=1e-300)),
               color=OKABE_ITO_PALETTE["vermillion"], alpha=0.7, s=25, label="Significant (BH-FDR < .05)")
    ax.axhline(-np.log10(0.05), color="black", linestyle="--", linewidth=0.8)
    ax.set_xlabel("Cohen's h (effect size vs. pooled baseline positive ratio)")
    ax.set_ylabel("−log10(FDR-adjusted p)")
    ax.set_title("Figure S3. Topic-level sentiment deviation from baseline\n"
                 "(n=120 topics with ≥30 comments, pooled config)")
    ax.legend(frameon=False, loc="upper center")

    paths = _save_figure(fig, "figS3_topic_volcano", output_dir=output_dir)
    _log.info("figure_saved", figure="S3", paths=[str(p) for p in paths])
    return paths


def plot_messenger_vs_message(
    e3_messenger_vs_message: dict[str, Any], *, output_dir: Path = Path("stats_figures"),
) -> list[Path]:
    """Figure S4: messenger-vs-message R-squared decomposition (E3).

    ``e3_messenger_vs_message`` must be
    ``inferential_results["E3_messenger_vs_message"]`` (Sprint 1A's
    :func:`finfluencer.reporting.inferential.run_e3_messenger_vs_message`
    output).
    """
    plt.rcParams.update(_RC_PARAMS)

    e3 = e3_messenger_vs_message
    bars = ["Analyst only\n(messenger)", "Topic only\n(message)", "Both\n(full model)"]
    vals = [e3["r2_analyst_only"], e3["r2_topic_only"], e3["r2_full"]]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.bar(bars, vals, color=[OKABE_ITO_PALETTE["orange"], OKABE_ITO_PALETTE["blue"], OKABE_ITO_PALETTE["green"]],
           width=0.55)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.005, f"{v:.3f}", ha="center", fontsize=10)
    ax.set_ylabel("R² (variance in sentiment_prob explained)")
    ax.set_title("Figure S4. Messenger vs. message: variance explained\n"
                 "(OLS, sentiment_prob ~ analyst / topic)")

    paths = _save_figure(fig, "figS4_messenger_vs_message", output_dir=output_dir)
    _log.info("figure_saved", figure="S4", paths=[str(p) for p in paths])
    return paths


def plot_volume_vs_sentiment(
    video_level_results: pd.DataFrame,
    r3_volume_sentiment: dict[str, Any],
    *, output_dir: Path = Path("stats_figures"),
) -> list[Path]:
    """Figure S5: video-level comment volume vs. mean sentiment, with a
    log-linear fit (R3).

    ``video_level_results`` must have ``n_comments`` and
    ``mean_sentiment`` columns (e.g.
    ``video_level_volume_sentiment.csv``, Sprint 1A's
    :func:`finfluencer.reporting.inferential.run_r3_volume_sentiment`
    side-output). ``r3_volume_sentiment`` must be
    ``inferential_results["R3_volume_sentiment"]``.
    """
    _require_nonempty(video_level_results, name="video_level_results")
    plt.rcParams.update(_RC_PARAMS)

    vl = video_level_results
    r3 = r3_volume_sentiment

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.scatter(vl["n_comments"], vl["mean_sentiment"], alpha=0.4, s=20, color=OKABE_ITO_PALETTE["blue"])
    z = np.polyfit(np.log(vl["n_comments"]), vl["mean_sentiment"], 1)
    xs = np.linspace(vl["n_comments"].min(), vl["n_comments"].max(), 100)
    ax.plot(xs, np.polyval(z, np.log(xs)), color=OKABE_ITO_PALETTE["vermillion"], linewidth=2, label="Log-linear fit")
    ax.set_xscale("log")
    ax.set_xlabel("Comments per video (log scale)")
    ax.set_ylabel("Mean sentiment probability")
    ax.set_title(
        f"Figure S5. Comment volume vs. mean sentiment per video\n"
        f"(Spearman ρ={r3['spearman_rho']:.3f}, p={r3['p']:.4f}, n={r3['n_videos']})"
    )
    ax.legend(frameon=False)

    paths = _save_figure(fig, "figS5_volume_vs_sentiment", output_dir=output_dir)
    _log.info("figure_saved", figure="S5", paths=[str(p) for p in paths])
    return paths


def plot_herding_heatmap(
    weekly_sentiment_by_analyst: pd.DataFrame, *, output_dir: Path = Path("stats_figures"),
) -> list[Path]:
    """Figure S6: cross-analyst weekly sentiment correlation heatmap (R2).

    ``weekly_sentiment_by_analyst`` must be indexed by week (e.g. read
    from ``weekly_sentiment_by_analyst.csv`` with ``index_col=0``) with
    one column per analyst -- Sprint 1A's
    :func:`finfluencer.reporting.inferential.run_r2_herding` side-output.
    Recomputes the Pearson correlation matrix from this weekly series
    directly, matching build_stats_figures.py exactly (which does not
    reuse ``inferential_results["R2_herding"]["pearson_corr"]`` for
    this figure, even though it is mathematically the same
    computation over the same data).
    """
    _require_nonempty(weekly_sentiment_by_analyst, name="weekly_sentiment_by_analyst")
    plt.rcParams.update(_RC_PARAMS)

    corr = weekly_sentiment_by_analyst.corr(method="pearson")
    corr_ordered = corr.loc[ANALYST_ORDER, ANALYST_ORDER]

    fig, ax = plt.subplots(figsize=(5, 4.5))
    im = ax.imshow(corr_ordered, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(4))
    ax.set_xticklabels(ANALYST_ORDER, rotation=30)
    ax.set_yticks(range(4))
    ax.set_yticklabels(ANALYST_ORDER)
    for i in range(4):
        for j in range(4):
            value = corr_ordered.values[i, j]
            ax.text(j, i, f"{value:.2f}", ha="center", va="center",
                    color="white" if abs(value) > 0.5 else "black")
    plt.colorbar(im, ax=ax, label="Pearson r")
    ax.set_title("Figure S6. Cross-analyst weekly sentiment correlation\n"
                 "(n=11 common weeks — exploratory, underpowered)")

    paths = _save_figure(fig, "figS6_herding_heatmap", output_dir=output_dir)
    _log.info("figure_saved", figure="S6", paths=[str(p) for p in paths])
    return paths


def build_all_manuscript_figures(
    *,
    master_table_path: Path = Path("master_table.csv"),
    inferential_results_path: Path = Path("inferential_results.json"),
    topic_level_results_path: Path = Path("topic_level_test_results.csv"),
    video_level_results_path: Path = Path("video_level_volume_sentiment.csv"),
    weekly_sentiment_by_analyst_path: Path = Path("weekly_sentiment_by_analyst.csv"),
    output_dir: Path = Path("stats_figures"),
) -> list[Path]:
    """Load every required input once and invoke each ``plot_*``
    function in turn, matching build_stats_figures.py's end-to-end
    behavior (same six figures, same order, same output directory
    default).

    This is a lightweight orchestrator only: it does not contain any
    plotting or statistical logic of its own -- see the individual
    ``plot_*`` functions for that.

    Returns
    -------
    list[Path]
        All twelve output files (PNG + SVG per figure), in figure order.
    """
    master_table = pd.read_csv(master_table_path)
    inferential_results = read_json(inferential_results_path)
    topic_level_results = pd.read_csv(topic_level_results_path)
    video_level_results = pd.read_csv(video_level_results_path)
    weekly_sentiment_by_analyst = pd.read_csv(weekly_sentiment_by_analyst_path, index_col=0)

    paths: list[Path] = []
    paths += plot_sentiment_violin_by_analyst(master_table, output_dir=output_dir)
    paths += plot_cluster_robust_se_comparison(
        inferential_results["E1b_cluster_robustness"], output_dir=output_dir,
    )
    paths += plot_topic_volcano(topic_level_results, output_dir=output_dir)
    paths += plot_messenger_vs_message(
        inferential_results["E3_messenger_vs_message"], output_dir=output_dir,
    )
    paths += plot_volume_vs_sentiment(
        video_level_results, inferential_results["R3_volume_sentiment"], output_dir=output_dir,
    )
    paths += plot_herding_heatmap(weekly_sentiment_by_analyst, output_dir=output_dir)

    _log.info("all_manuscript_figures_built", n_files=len(paths), output_dir=str(output_dir))
    return paths


__all__ = [
    "plot_sentiment_violin_by_analyst",
    "plot_cluster_robust_se_comparison",
    "plot_topic_volcano",
    "plot_messenger_vs_message",
    "plot_volume_vs_sentiment",
    "plot_herding_heatmap",
    "build_all_manuscript_figures",
    "OKABE_ITO_PALETTE",
    "ANALYST_ORDER",
    "ANALYST_COLORS",
]
