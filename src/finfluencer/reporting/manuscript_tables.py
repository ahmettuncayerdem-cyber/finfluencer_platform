"""
finfluencer.reporting.manuscript_tables
==========================================

Packaged version of the root-level ``build_stats_tables.py`` script:
the ``.xlsx`` supplementary-statistics workbook
(``finfluencer_tr_2025_inferential_stats.xlsx``) built from Sprint 1A's
reporting outputs (``inferential_results.json`` and two of its
side-CSVs).

Pipeline
--------
Five worksheets, created in this exact order (matching the original
script):

* **Summary** -- one-row-per-analysis overview table (E1, E1b, E2, E3,
  R1 x2, R2, R3) plus a methodology note.
* **E1_CrossAnalyst** -- omnibus tests, group descriptives, and Dunn's
  post-hoc matrix for the cross-analyst sentiment comparison.
* **E1b_ClusterRobust** -- naive vs. video-clustered standard errors.
* **E2_TopicSentiment** -- full per-topic volcano-plot table
  (topic id, label, n, effect size, FDR-adjusted p, significance
  flag), frozen header row.
* **E3_MessengerVsMessage** -- nested-model R-squared comparison and
  incremental F-tests.

One builder function per worksheet (matching the "one function per
output artifact" convention already used for
:mod:`finfluencer.reporting.manuscript_figures`'s six ``plot_*``
functions), plus a lightweight orchestrator,
:func:`build_inferential_stats_workbook`, that loads every input once
and calls each ``_build_*_sheet`` function in turn -- mirroring
:func:`finfluencer.reporting.manuscript_figures.build_all_manuscript_figures`.
Workbook construction (:func:`build_inferential_stats_workbook`) and
workbook saving (:func:`save_inferential_stats_workbook`) are kept as
separate pure-input/pure-output steps, matching the calculate/save
separation already used throughout this package (e.g.
``master_table.build_master_table`` / ``save_master_table``).

Preserved-as-observed quirks
-----------------------------
The original script does not build individual detail sheets for R1,
R2, or R3 -- only their one-row Summary entries exist; the workbook
has five worksheets total, not eight. This module does not add the
missing detail sheets: doing so would be new functionality, not
packaging, and no such worksheet-building logic exists anywhere in
this repository's history to package.

The original script also reads ``weekly_sentiment_by_analyst.csv``
(``wk = pd.read_csv(...)``) but never references the resulting
DataFrame in any worksheet. Unlike ``run_e3_messenger_vs_message``'s
genuinely-unused ``m_null`` model in
:mod:`finfluencer.reporting.inferential` (dropped there because it has
*zero* observable effect), this read is not a no-op: if the file were
absent, the original script would fail before ever reaching
``wb.save(...)``. :func:`build_inferential_stats_workbook` therefore
still performs this read (and discards the result), preserving the
original script's fail-fast dependency on that file's presence exactly.

This module does not fabricate, simulate, or otherwise substitute for
missing input data: :func:`build_inferential_stats_workbook` raises
:class:`~finfluencer.core.exceptions.CorpusValidationError` if the
loaded results dict or either loaded DataFrame is empty.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from finfluencer.core.exceptions import CorpusValidationError
from finfluencer.core.logging import get_logger
from finfluencer.utils.io import ensure_parent, read_json

_log = get_logger(__name__)

#: Workbook-wide styling constants. Match build_stats_tables.py's
#: module-level FONT/HFILL/HFONT/BFONT/BOLDF/NOTEF/THIN/BORDER exactly.
_FONT_NAME = "Arial"
_HFILL = PatternFill("solid", fgColor="1F4E78")
_HFONT = Font(name=_FONT_NAME, bold=True, color="FFFFFF", size=10)
_BFONT = Font(name=_FONT_NAME, size=10)
_BOLDF = Font(name=_FONT_NAME, bold=True, size=10)
_NOTEF = Font(name=_FONT_NAME, italic=True, size=8, color="595959")
_THIN = Side(style="thin", color="BFBFBF")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

#: Analyst iteration order used by the E1 group-descriptives block.
#: Matches build_stats_tables.py's inline list literal exactly.
_E1_ANALYST_ORDER = ["satiroglu", "gecer", "basaran", "yesilada"]


def _require_nonempty(data: Any, *, name: str, path: Path) -> None:
    """Raise :class:`CorpusValidationError` if ``data`` is an empty
    DataFrame or an empty/falsy dict."""
    is_empty = data.empty if isinstance(data, pd.DataFrame) else not data
    if is_empty:
        raise CorpusValidationError(
            f"{name} is empty; cannot build the inferential stats workbook from an empty source.",
            path=str(path), name=name,
        )


def _header(ws: Worksheet, row: int, headers: list[str]) -> None:
    """Write a styled header row. Matches build_stats_tables.py's
    ``header()`` helper exactly."""
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = _HFONT
        cell.fill = _HFILL
        cell.border = _BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _body(ws: Worksheet, row: int, vals: Sequence[Any], *, bold: bool = False) -> None:
    """Write a styled body row. Matches build_stats_tables.py's
    ``body()`` helper exactly."""
    for c, v in enumerate(vals, start=1):
        cell = ws.cell(row=row, column=c, value=v)
        cell.font = _BOLDF if bold else _BFONT
        cell.border = _BORDER


def _autosize(ws: Worksheet, widths: list[float]) -> None:
    """Set fixed column widths. Matches build_stats_tables.py's
    ``autosize()`` helper exactly (not a content-based autosize despite
    the name -- preserved as-is)."""
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _note(ws: Worksheet, row: int, text: str, ncols: int, *, height: int = 70) -> None:
    """Write a merged, wrapped italic footnote row. Matches
    build_stats_tables.py's ``note()`` helper exactly."""
    ws.cell(row=row, column=1, value=text).font = _NOTEF
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[row].height = height


def _build_summary_sheet(wb: Workbook, r: dict[str, Any]) -> Worksheet:
    """Build the ``Summary`` worksheet: one row per analysis (E1, E1b,
    E2, E3, R1 x2, R2, R3) plus a methodology footnote. This becomes
    the workbook's active/first sheet, matching ``wb.active`` in the
    original script.
    """
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Inferential statistics battery — finfluencer_tr_2025 (internal-data only, no external market data)"
    ws["A1"].font = Font(name=_FONT_NAME, bold=True, size=12)
    ws.merge_cells("A1:H1")
    headers = ["ID", "Analysis", "Tier", "Test", "Statistic", "p-value", "Effect size", "Result"]
    _header(ws, 3, headers)
    rows = [
        ("E1", "Cross-analyst sentiment (categorical)", "Essential", "Chi-square independence",
         f"chi2={r['E1_cross_analyst_sentiment']['chi2']:.1f}, df=3", "<.001",
         f"Cramer's V={r['E1_cross_analyst_sentiment']['cramers_v']:.3f}", "Significant, moderate assoc."),
        ("E1", "Cross-analyst sentiment (continuous)", "Essential", "Kruskal-Wallis H",
         f"H={r['E1_cross_analyst_sentiment']['kruskal_H']:.1f}, df=3", "<.001",
         f"epsilon^2={r['E1_cross_analyst_sentiment']['epsilon_sq']:.3f}", "Significant, small-moderate"),
        ("E1b", "Video-clustering robustness check", "Essential", "Cluster-robust logit (video_id)",
         "SE ratio 1.35x-2.51x naive", "n/a", "SE inflation factor", "Clustering materially matters"),
        ("E2", "Topic-sentiment association (128 topics)", "Essential", "Chi-square + BH-FDR per-topic z-test",
         f"chi2={r['E2_topic_sentiment']['overall_chi2']:.1f}", "<.001",
         f"Cramer's V={r['E2_topic_sentiment']['cramers_v']:.3f}",
         f"{r['E2_topic_sentiment']['n_significant_fdr']}/{r['E2_topic_sentiment']['n_topics_tested']} topics sig. (FDR)"),
        ("E3", "Messenger vs. message variance partition", "Essential", "Nested OLS + incremental F-test",
         f"F(analyst|topic)={r['E3_messenger_vs_message']['f_test_analyst_given_topic']['F']:.1f}", "<.001",
         f"Partial R2: analyst={r['E3_messenger_vs_message']['partial_r2_analyst_over_topic']:.3f}, "
         f"topic={r['E3_messenger_vs_message']['partial_r2_topic_over_analyst']:.3f}",
         "Topic (message) dominates analyst (messenger)"),
        ("R1", "Pooled weekly sentiment trend", "Recommended", "Mann-Kendall trend test",
         f"tau={r['R1_trend_tests']['pooled_sentiment_trend']['tau']:.3f}",
         f"{r['R1_trend_tests']['pooled_sentiment_trend']['p']:.3f}",
         f"Sen's slope={r['R1_trend_tests']['pooled_sentiment_trend']['sen_slope']:.5f}/wk", "No significant trend"),
        ("R1", "Top pooled topic weekly frequency trend", "Recommended", "Mann-Kendall trend test",
         f"tau={r['R1_trend_tests']['top_topic_freq_trend']['tau']:.3f}",
         f"{r['R1_trend_tests']['top_topic_freq_trend']['p']:.3f}",
         "n/a", "No significant trend"),
        ("R2", "Cross-analyst weekly sentiment correlation", "Recommended (exploratory)",
         "Pearson correlation, n=11 weeks", "r range -0.61 to +0.36", "1/6 pairs p<.05", "r (Pearson)",
         "Underpowered — no herding evidence"),
        ("R3", "Comment volume vs. video-level sentiment", "Recommended", "Spearman rank correlation",
         f"rho={r['R3_volume_sentiment']['spearman_rho']:.3f}", f"{r['R3_volume_sentiment']['p']:.4f}",
         "rho (Spearman)", "Significant, small positive effect"),
    ]
    for i, row in enumerate(rows):
        _body(ws, 4 + i, row)
    _note(
        ws, 4 + len(rows) + 1,
        "All tests computed on master_table.csv (17,566 comments, comment-level sentiment_prob/sentiment_class "
        "joined to pooled-configuration BERTopic assignments). No external data (prices, FX, gold, macro series) "
        "used. See individual sheets for full statistics, assumptions, and post-hoc results. Source: "
        "data/raw/comments.parquet, data/processed/{sentiment,topics}.parquet, validated 2026-07-14.",
        8, height=55,
    )
    _autosize(ws, [6, 34, 16, 30, 22, 12, 26, 30])
    return ws


def _build_e1_sheet(wb: Workbook, r: dict[str, Any], dunn: pd.DataFrame) -> Worksheet:
    """Build the ``E1_CrossAnalyst`` worksheet: omnibus tests, group
    descriptives, and Dunn's post-hoc matrix."""
    ws1 = wb.create_sheet("E1_CrossAnalyst")
    ws1["A1"] = "E1. Cross-analyst sentiment comparison — full results"
    ws1["A1"].font = Font(name=_FONT_NAME, bold=True, size=12)
    ws1.merge_cells("A1:E1")

    ws1["A3"] = "Omnibus tests"
    ws1["A3"].font = _BOLDF
    _header(ws1, 4, ["Test", "Statistic", "df", "p-value", "Effect size"])
    e1 = r["E1_cross_analyst_sentiment"]
    _body(ws1, 5, ["Chi-square (sentiment_class x analyst_key)", round(e1["chi2"], 2), 3, e1["p"],
                   f"Cramer's V = {e1['cramers_v']:.4f}"])
    _body(ws1, 6, ["Kruskal-Wallis H (sentiment_prob by analyst)", round(e1["kruskal_H"], 2), 3, e1["kruskal_p"],
                   f"epsilon^2 = {e1['epsilon_sq']:.4f}"])
    _body(ws1, 7, ["Shapiro-Wilk normality (n=5000 subsample)", round(e1["shapiro_W"], 4), "-", e1["shapiro_p"],
                   "Non-normal (justifies Kruskal-Wallis)"])

    ws1["A9"] = "Group descriptives"
    ws1["A9"].font = _BOLDF
    _header(ws1, 10, ["Analyst", "n", "Median sentiment_prob"])
    for i, a in enumerate(_E1_ANALYST_ORDER):
        _body(ws1, 11 + i, [a, e1["group_n"][a], round(e1["group_medians"][a], 4)])

    ws1["A16"] = "Dunn's post-hoc pairwise comparisons (Holm-adjusted p)"
    ws1["A16"].font = _BOLDF
    _header(ws1, 17, ["Analyst"] + list(dunn.columns))
    for i, (idx, row) in enumerate(dunn.iterrows()):
        _body(ws1, 18 + i, [idx] + [round(v, 6) for v in row.values])

    _note(
        ws1, 23,
        "Assumptions: chi-square requires expected cell counts >=5 (satisfied, n=17566 across 4x2 table); "
        "Kruskal-Wallis assumes similarly-shaped distributions across groups (approximately met — all "
        "right-skewed). Interpretation: analyst identity is significantly associated with sentiment (both "
        "tests p<.001), but effect size is small-to-moderate (epsilon^2=0.056, Cramer's V=0.21) — analyst "
        "explains a real but limited share of sentiment variance. All pairwise comparisons are significant "
        "after Holm correction except basaran-yesilada (p=.013, still significant at alpha=.05 but weakest "
        "pair).",
        6, height=70,
    )
    _autosize(ws1, [38, 14, 14, 14, 30])
    return ws1


def _build_e1b_sheet(wb: Workbook, r: dict[str, Any]) -> Worksheet:
    """Build the ``E1b_ClusterRobust`` worksheet: naive vs.
    video-clustered standard errors."""
    ws1b = wb.create_sheet("E1b_ClusterRobust")
    ws1b["A1"] = "E1b. Video-clustering robustness check (logistic regression)"
    ws1b["A1"].font = Font(name=_FONT_NAME, bold=True, size=12)
    ws1b.merge_cells("A1:E1")
    e1b = r["E1b_cluster_robustness"]
    _header(ws1b, 3, ["Coefficient", "Naive SE", "Cluster-robust SE (video_id)", "Inflation ratio"])
    for i, k in enumerate(e1b["naive_se"].keys()):
        _body(ws1b, 4 + i, [k, round(e1b["naive_se"][k], 4), round(e1b["cluster_se"][k], 4),
                            round(e1b["se_inflation_ratio"][k], 3)])
    _note(
        ws1b, 9,
        f"n_videos={e1b['n_videos']}, n_comments={e1b['n_comments']} (avg "
        f"{e1b['n_comments'] / e1b['n_videos']:.1f} comments/video). Standard errors ignoring video-level "
        "nesting are understated by 1.35x-2.51x. All coefficients remain statistically significant under "
        "clustering, but every p-value reported elsewhere in this workbook and in the earlier manuscript "
        "draft should be treated as a lower bound on the true p-value unless computed with cluster-robust or "
        "mixed-effects methods. Recommend re-running E1/E2/E3 with video_id-clustered SEs before final "
        "submission.",
        4, height=70,
    )
    _autosize(ws1b, [30, 14, 26, 16])
    return ws1b


def _build_e2_sheet(wb: Workbook, topic_df: pd.DataFrame) -> Worksheet:
    """Build the ``E2_TopicSentiment`` worksheet: full per-topic volcano
    table, sorted by ``cohens_h``, frozen header row."""
    ws2 = wb.create_sheet("E2_TopicSentiment")
    ws2["A1"] = "E2. Topic-level sentiment deviation from pooled baseline (BH-FDR corrected)"
    ws2["A1"].font = Font(name=_FONT_NAME, bold=True, size=12)
    ws2.merge_cells("A1:H1")
    _header(ws2, 3, ["Topic ID", "Topic label", "n", "Pos. ratio", "Cohen's h", "z", "p (FDR-adj.)", "Significant"])
    topic_sorted = topic_df.sort_values("cohens_h")
    for i, (_, row) in enumerate(topic_sorted.iterrows()):
        _body(ws2, 4 + i, [int(row.topic_id), row.topic_label, int(row.n), round(row.pos_ratio, 4),
                           round(row.cohens_h, 4), round(row.z, 3), row.p_fdr, bool(row.significant_fdr)])
    _autosize(ws2, [10, 32, 8, 12, 12, 10, 14, 12])
    ws2.freeze_panes = "A4"
    return ws2


def _build_e3_sheet(wb: Workbook, r: dict[str, Any]) -> Worksheet:
    """Build the ``E3_MessengerVsMessage`` worksheet: nested-model
    R-squared comparison and incremental F-tests."""
    ws3 = wb.create_sheet("E3_MessengerVsMessage")
    ws3["A1"] = "E3. Messenger (analyst) vs. message (topic) — nested model comparison"
    ws3["A1"].font = Font(name=_FONT_NAME, bold=True, size=12)
    ws3.merge_cells("A1:D1")
    e3 = r["E3_messenger_vs_message"]
    _header(ws3, 3, ["Model", "R-squared", "", ""])
    _body(ws3, 4, ["Analyst only (messenger)", round(e3["r2_analyst_only"], 4)])
    _body(ws3, 5, ["Topic only (message)", round(e3["r2_topic_only"], 4)])
    _body(ws3, 6, ["Both (full model)", round(e3["r2_full"], 4)])
    ws3["A8"] = "Incremental F-tests"
    ws3["A8"].font = _BOLDF
    _header(ws3, 9, ["Comparison", "F", "p-value", "Partial R2"])
    _body(ws3, 10, ["Analyst, added to topic-only model", round(e3["f_test_analyst_given_topic"]["F"], 2),
                    e3["f_test_analyst_given_topic"]["p"], round(e3["partial_r2_analyst_over_topic"], 4)])
    _body(ws3, 11, ["Topic, added to analyst-only model", round(e3["f_test_topic_given_analyst"]["F"], 2),
                    e3["f_test_topic_given_analyst"]["p"], round(e3["partial_r2_topic_over_analyst"], 4)])
    _note(
        ws3, 13,
        "Both factors are statistically significant (both p<.001, huge n=17,566), but the effect-size gap is "
        "the substantive finding: topic content explains roughly 13x more variance in sentiment than analyst "
        "identity alone (partial R2 0.205 vs 0.016). This favours a message-driven interpretation of audience "
        "sentiment over a pure source-credibility/messenger effect. Caveat: standard OLS SEs here are not "
        "video-clustered (see E1b) — the F-tests likely overstate significance somewhat, though the R2 "
        "magnitudes themselves are unaffected by clustering.",
        4, height=75,
    )
    _autosize(ws3, [34, 14, 14, 14])
    return ws3


def build_inferential_stats_workbook(
    *,
    inferential_results_path: Path = Path("inferential_results.json"),
    topic_level_results_path: Path = Path("topic_level_test_results.csv"),
    dunn_posthoc_matrix_path: Path = Path("dunn_posthoc_matrix.csv"),
    weekly_sentiment_by_analyst_path: Path = Path("weekly_sentiment_by_analyst.csv"),
) -> Workbook:
    """Build the five-worksheet inferential-statistics workbook.

    Behavior-preserving packaging of ``build_stats_tables.py``: same
    five worksheets, same order, same cell values, same styling, same
    column widths, same freeze panes. See the module docstring for two
    deliberately-preserved quirks: no R1/R2/R3 detail sheets, and an
    unused-but-still-performed read of
    ``weekly_sentiment_by_analyst_path``.

    Raises
    ------
    CorpusValidationError
        If the inferential results dict, the topic-level results
        table, or the Dunn post-hoc matrix is empty.
    """
    r = read_json(inferential_results_path)
    _require_nonempty(r, name="inferential_results", path=inferential_results_path)

    topic_df = pd.read_csv(topic_level_results_path)
    _require_nonempty(topic_df, name="topic_level_results", path=topic_level_results_path)

    dunn = pd.read_csv(dunn_posthoc_matrix_path, index_col=0)
    _require_nonempty(dunn, name="dunn_posthoc_matrix", path=dunn_posthoc_matrix_path)

    # Read but deliberately unused -- see module docstring
    # ("Preserved-as-observed quirks") for why this call is kept.
    pd.read_csv(weekly_sentiment_by_analyst_path, index_col=0)

    wb = Workbook()
    _build_summary_sheet(wb, r)
    _build_e1_sheet(wb, r, dunn)
    _build_e1b_sheet(wb, r)
    _build_e2_sheet(wb, topic_df)
    _build_e3_sheet(wb, r)

    _log.info("inferential_stats_workbook_built", n_sheets=len(wb.sheetnames))
    return wb


def save_inferential_stats_workbook(
    wb: Workbook, *, output_path: Path = Path("finfluencer_tr_2025_inferential_stats.xlsx"),
) -> None:
    """Save the workbook, with the original script's exact filename."""
    output_path = Path(output_path)
    ensure_parent(output_path)
    wb.save(output_path)
    _log.info("inferential_stats_workbook_saved", path=str(output_path), n_sheets=len(wb.sheetnames))


__all__ = [
    "build_inferential_stats_workbook",
    "save_inferential_stats_workbook",
]
