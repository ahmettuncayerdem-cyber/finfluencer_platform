"""Tests for finfluencer.reporting.manuscript_tables.

Three tiers, matching the established convention for this package
(``test_manuscript_data.py``, ``test_manuscript_figures.py``):

* Unit tests build the workbook from small synthetic inputs and check
  worksheet names/order, header rows, body values, and the styling
  invariants the module's private helpers are responsible for
  (``_header``'s center/wrap alignment, ``_note``'s wrap-text row).
* A differential test compares every cell's value and essential style
  (font, fill, border) against the real, pre-existing
  ``finfluencer_tr_2025_inferential_stats.xlsx`` this repository's
  root-level ``build_stats_tables.py`` script produced. Skipped
  automatically if the reference workbook or its real data sources are
  absent.
* An acceptance test verifies the workbook can be saved under its
  original filename with the original five worksheets.

Why alpha-channel-normalized style comparison, and why the real
reference file needed a LibreOffice round-trip to investigate
------------------------------------------------------------------
A first, naive structural diff against the checked-in reference
workbook showed differences on nearly every styled cell: border/font
color strings carried an ``"FF"`` alpha prefix in the reference file
but a ``"00"`` prefix in this module's freshly-generated output;
default (never explicitly set) cell alignment was materialized to
``('general', 'bottom', False)`` in the reference file but stayed
``None`` in fresh output; default row heights were materialized to
``15.0`` for every row in the reference file's ``E2_TopicSentiment``
sheet even though the original script never touches row height there;
and two adjacent equal-width columns were merged into a single
``<col min="4" max="5">`` XML range in the reference file.

This was investigated empirically (not assumed) by round-tripping
this module's own freshly-generated workbook through
``soffice --headless --convert-to xlsx`` (LibreOffice was available in
the verification environment) and re-diffing: every one of the above
differences disappeared. This proves the differences originate from a
LibreOffice resave applied to the reference file at some point after
``build_stats_tables.py`` produced it (LibreOffice's OOXML writer
normalizes colors, alignment, and row heights differently than
openpyxl's), not from any behavioral difference in this module's
output. Comparing colors by their final 6 hex digits (ignoring the
alpha byte) and comparing only style attributes the original script
actually sets explicitly (never raw ``alignment``/``row_dimensions``
against the reference, which reflect LibreOffice's resave defaults
rather than the original script's behavior) is therefore the correct,
evidence-based comparison -- not a weakening of the test.

After that round-trip, exactly one genuine content difference
remained: two adjacent rows in ``E2_TopicSentiment`` (topics 44 and
182) were transposed. This is not a new bug -- it is the same
tied-``cohens_h`` unstable-sort non-determinism already discovered and
documented for these two specific topics in Sprint 1A's
``test_inferential.py`` (``E2_topic_sentiment.topic_results``). The
workbook's E2 sheet sorts by the same ``cohens_h`` column, so the same
tie surfaces here. Handled the same way as Sprint 1A: an
order-independent comparison of the full row set, keyed by topic_id.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter

from finfluencer.core.exceptions import CorpusValidationError
from finfluencer.reporting.manuscript_tables import (
    build_inferential_stats_workbook,
    save_inferential_stats_workbook,
)

# =============================================================================
# Real-data fixture locations (repo root), for differential/acceptance tests.
# =============================================================================

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_INFERENTIAL_RESULTS = _REPO_ROOT / "inferential_results.json"
_REAL_TOPIC_LEVEL_RESULTS = _REPO_ROOT / "topic_level_test_results.csv"
_REAL_DUNN_MATRIX = _REPO_ROOT / "dunn_posthoc_matrix.csv"
_REAL_WEEKLY_BY_ANALYST = _REPO_ROOT / "weekly_sentiment_by_analyst.csv"
_REAL_WORKBOOK = _REPO_ROOT / "finfluencer_tr_2025_inferential_stats.xlsx"

_ALL_REAL_INPUTS_PRESENT = all(p.exists() for p in (
    _REAL_INFERENTIAL_RESULTS, _REAL_TOPIC_LEVEL_RESULTS, _REAL_DUNN_MATRIX,
    _REAL_WEEKLY_BY_ANALYST, _REAL_WORKBOOK,
))
_SKIP_REASON = (
    "Real inferential_results.json / side-CSVs / "
    "finfluencer_tr_2025_inferential_stats.xlsx reference not present in this "
    "environment (gitignored, regenerable research artifacts) -- "
    "differential/acceptance test skipped."
)

_EXPECTED_SHEET_NAMES = [
    "Summary", "E1_CrossAnalyst", "E1b_ClusterRobust", "E2_TopicSentiment", "E3_MessengerVsMessage",
]


def _style_tuple(cell) -> tuple:
    """(value, font-essentials, fill-essentials, border-essentials) for a
    cell, with color strings normalized to their final 6 hex digits
    (alpha-byte-independent) -- see module docstring."""
    def _rgb6(color):
        if color is None or not isinstance(color.rgb, str):
            return None
        return color.rgb[-6:]

    font = cell.font
    fill = cell.fill
    border = cell.border
    return (
        cell.value,
        (font.name, font.bold, font.italic, font.size, _rgb6(font.color)),
        (_rgb6(fill.fgColor), fill.patternType),
        tuple(
            (getattr(border, side).style, _rgb6(getattr(border, side).color))
            for side in ("left", "right", "top", "bottom")
        ),
    )


def _non_blank_cells(ws) -> dict[str, tuple]:
    """``{coordinate: _style_tuple(cell)}`` for every "content" cell.

    Treats an empty string the same as ``None`` (no cell): the four
    filler header cells the original script writes via
    ``header(ws3, 3, ["Model", "R-squared", "", ""])`` are written by
    openpyxl as genuine empty-string-valued cells, but the reference
    workbook's LibreOffice resave normalizes those to truly blank
    (valueless) cells -- confirmed directly against the reference
    file's raw XML (``<c r="C3" s="2"/>``, no ``<v>`` element at all).
    """
    return {
        c.coordinate: _style_tuple(c)
        for row in ws.iter_rows() for c in row
        if c.value not in (None, "")
    }


def _values_equal(a: Any, b: Any) -> bool:
    """Equal, with a relative-tolerance allowance for floats.

    Several raw (unrounded) p-values differ from the reference
    workbook by ~1e-15 relative magnitude -- e.g. real
    ``2.66228102843998e-175`` vs. freshly-generated
    ``2.662281028439982e-175``. This is Excel/OOXML's ~15-significant-
    digit float storage format losing the last 1-2 bits of a Python
    float64's full precision on the reference file's LibreOffice
    round-trip, not a computational difference -- the same class of
    floating-point serialization noise already documented and
    tolerance-handled for E3's OLS statistics in Sprint 1A's
    ``test_inferential.py``.

    Also normalizes another LibreOffice-resave artifact observed on
    ``E2_TopicSentiment``'s ``significant_fdr`` column: LibreOffice
    rewrites plain OOXML boolean cells (``t="b"``) as formula strings
    ``"=TRUE()"`` / ``"=FALSE()"`` rather than a literal boolean value.
    """
    _BOOL_FORMULAS = {"=TRUE()": True, "=FALSE()": False}
    if isinstance(a, str) and a in _BOOL_FORMULAS:
        a = _BOOL_FORMULAS[a]
    if isinstance(b, str) and b in _BOOL_FORMULAS:
        b = _BOOL_FORMULAS[b]
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-300)
    return a == b


def _cell_tuples_equal(t1: tuple, t2: tuple) -> bool:
    """``_style_tuple`` equality, with float-tolerant value comparison."""
    (v1, *rest1), (v2, *rest2) = t1, t2
    return _values_equal(v1, v2) and rest1 == rest2


def _resolved_col_widths(ws, *, ncols: int) -> dict[str, float]:
    """Column widths resolved per column index, expanding each
    ``ColumnDimension``'s ``min``/``max`` range explicitly.

    Neither ``ws.column_dimensions.get(letter)`` (plain dict lookup --
    misses columns inside a multi-column range that aren't the range's
    own dict key) nor ``ws.column_dimensions[letter]`` (subscript --
    empirically confirmed to *fabricate* a new, wrong-width dimension
    for a missing key rather than resolving the range) correctly
    recovers a column's width when a writer has merged contiguous
    equal-width columns into a single ``<col min="4" max="5" .../>``
    XML range, as the reference workbook's LibreOffice resave does for
    ``E2_TopicSentiment``'s columns D and E. Both were tried directly
    against the reference file and empirically ruled out before
    settling on this explicit range-expansion approach.
    """
    widths: dict[str, float] = {}
    for letter, dim in ws.column_dimensions.items():
        if dim.width is None:
            continue
        # A freshly-built (never round-tripped) workbook's per-letter
        # ColumnDimension objects have min=max=None (they were never
        # parsed from a min/max-bounded XML range) -- fall back to the
        # dict key's own column index in that case, rather than
        # defaulting to column 1 for every dimension.
        if dim.min is not None and dim.max is not None:
            lo, hi = dim.min, dim.max
        else:
            lo = hi = column_index_from_string(letter)
        for idx in range(lo, hi + 1):
            if idx <= ncols:
                widths[get_column_letter(idx)] = round(dim.width, 1)
    return widths


# =============================================================================
# Synthetic fixtures
# =============================================================================


def _synthetic_inferential_results() -> dict[str, Any]:
    return {
        "E1_cross_analyst_sentiment": {
            "chi2": 810.19, "p": 1.9e-214, "cramers_v": 0.2145,
            "kruskal_H": 990.63, "kruskal_p": 3.1e-214, "epsilon_sq": 0.0564,
            "shapiro_W": 0.9123, "shapiro_p": 1.2e-40,
            "group_medians": {"satiroglu": 0.61, "gecer": 0.55, "basaran": 0.48, "yesilada": 0.52},
            "group_n": {"satiroglu": 5000, "gecer": 4500, "basaran": 4000, "yesilada": 4066},
        },
        "E1b_cluster_robustness": {
            "naive_se": {"C(analyst_key)[T.gecer]": 0.044, "C(analyst_key)[T.basaran]": 0.0363},
            "cluster_se": {"C(analyst_key)[T.gecer]": 0.0996, "C(analyst_key)[T.basaran]": 0.081},
            "se_inflation_ratio": {"C(analyst_key)[T.gecer]": 2.263, "C(analyst_key)[T.basaran]": 2.231},
            "n_videos": 250, "n_comments": 17566,
        },
        "E2_topic_sentiment": {
            "overall_chi2": 1500.0, "overall_p": 0.0, "cramers_v": 0.19,
            "n_significant_fdr": 40, "n_topics_tested": 120,
        },
        "E3_messenger_vs_message": {
            "r2_analyst_only": 0.0163, "r2_topic_only": 0.2439, "r2_full": 0.2593,
            "partial_r2_analyst_over_topic": 0.0155, "partial_r2_topic_over_analyst": 0.2053,
            "f_test_analyst_given_topic": {"F": 121.25, "p": 1e-90},
            "f_test_topic_given_analyst": {"F": 38.05, "p": 1e-200},
        },
        "R1_trend_tests": {
            "pooled_sentiment_trend": {"tau": -0.053, "p": 0.581, "sen_slope": -0.0002},
            "top_topic_freq_trend": {"tau": 0.12, "p": 0.24},
        },
        "R2_herding": {"pearson_corr": {}, "spearman_corr": {}, "n_weeks_total": 11},
        "R3_volume_sentiment": {"n_videos": 200, "spearman_rho": 0.176, "p": 0.0073},
    }


def _synthetic_topic_level_results() -> pd.DataFrame:
    return pd.DataFrame({
        "topic_id": [1, 2, 3],
        "topic_label": ["1_alpha", "2_beta", "3_gamma"],
        "n": [50, 80, 120],
        "pos_ratio": [0.6, 0.4, 0.55],
        "cohens_h": [0.3, -0.2, 0.05],
        "z": [4.1, -3.2, 1.1],
        "p_fdr": [0.001, 0.01, 0.3],
        "significant_fdr": [True, True, False],
    })


def _synthetic_dunn_matrix() -> pd.DataFrame:
    analysts = ["satiroglu", "gecer", "basaran", "yesilada"]
    data = [[0.0, 0.001, 0.02, 0.5] if i == 0 else [0.001, 0.0, 0.03, 0.4] if i == 1
            else [0.02, 0.03, 0.0, 0.013] if i == 2 else [0.5, 0.4, 0.013, 0.0]
            for i in range(4)]
    return pd.DataFrame(data, index=analysts, columns=analysts)


def _write_synthetic_inputs(tmp_path: Path) -> dict[str, Path]:
    inferential_results_path = tmp_path / "inferential_results.json"
    inferential_results_path.write_text(json.dumps(_synthetic_inferential_results()), encoding="utf-8")

    topic_level_results_path = tmp_path / "topic_level_test_results.csv"
    _synthetic_topic_level_results().to_csv(topic_level_results_path, index=False, encoding="utf-8")

    dunn_posthoc_matrix_path = tmp_path / "dunn_posthoc_matrix.csv"
    _synthetic_dunn_matrix().to_csv(dunn_posthoc_matrix_path, encoding="utf-8")

    weekly_sentiment_by_analyst_path = tmp_path / "weekly_sentiment_by_analyst.csv"
    pd.DataFrame(
        {"satiroglu": [0.5, 0.6], "gecer": [0.4, 0.5], "basaran": [0.45, 0.55], "yesilada": [0.5, 0.5]},
        index=["2025-01-05", "2025-01-12"],
    ).to_csv(weekly_sentiment_by_analyst_path, encoding="utf-8")

    return {
        "inferential_results_path": inferential_results_path,
        "topic_level_results_path": topic_level_results_path,
        "dunn_posthoc_matrix_path": dunn_posthoc_matrix_path,
        "weekly_sentiment_by_analyst_path": weekly_sentiment_by_analyst_path,
    }


class TestBuildInferentialStatsWorkbook:
    def test_produces_expected_sheet_names_and_order(self, tmp_path):
        wb = build_inferential_stats_workbook(**_write_synthetic_inputs(tmp_path))
        assert wb.sheetnames == _EXPECTED_SHEET_NAMES

    def test_summary_sheet_header_and_row_count(self, tmp_path):
        wb = build_inferential_stats_workbook(**_write_synthetic_inputs(tmp_path))
        ws = wb["Summary"]
        headers = [ws.cell(row=3, column=c).value for c in range(1, 9)]
        assert headers == ["ID", "Analysis", "Tier", "Test", "Statistic", "p-value", "Effect size", "Result"]
        # 9 analysis rows (E1 x2, E1b, E2, E3, R1 x2, R2, R3), rows 4-12
        assert ws.cell(row=4, column=1).value == "E1"
        assert ws.cell(row=11, column=1).value == "R2"
        assert ws.cell(row=12, column=1).value == "R3"

    def test_header_cells_are_centered_and_wrapped(self, tmp_path):
        wb = build_inferential_stats_workbook(**_write_synthetic_inputs(tmp_path))
        ws = wb["Summary"]
        header_cell = ws.cell(row=3, column=1)
        assert header_cell.alignment.horizontal == "center"
        assert header_cell.alignment.vertical == "center"
        assert header_cell.alignment.wrap_text is True

    def test_note_row_is_wrapped_and_merged(self, tmp_path):
        wb = build_inferential_stats_workbook(**_write_synthetic_inputs(tmp_path))
        ws = wb["Summary"]
        note_row = 4 + 9 + 1  # 9 analysis rows + 1
        assert ws.cell(row=note_row, column=1).alignment.wrap_text is True
        assert any(str(r).startswith(f"A{note_row}:") for r in ws.merged_cells.ranges)

    def test_e1_sheet_has_dunn_matrix_and_group_descriptives(self, tmp_path):
        wb = build_inferential_stats_workbook(**_write_synthetic_inputs(tmp_path))
        ws1 = wb["E1_CrossAnalyst"]
        assert ws1.cell(row=10, column=1).value == "Analyst"
        assert [ws1.cell(row=11 + i, column=1).value for i in range(4)] == \
            ["satiroglu", "gecer", "basaran", "yesilada"]
        assert ws1.cell(row=17, column=1).value == "Analyst"
        assert ws1.cell(row=17, column=2).value == "satiroglu"

    def test_e1b_sheet_has_one_row_per_coefficient(self, tmp_path):
        wb = build_inferential_stats_workbook(**_write_synthetic_inputs(tmp_path))
        ws1b = wb["E1b_ClusterRobust"]
        assert ws1b.cell(row=4, column=1).value == "C(analyst_key)[T.gecer]"
        assert ws1b.cell(row=5, column=1).value == "C(analyst_key)[T.basaran]"

    def test_e2_sheet_sorted_by_cohens_h_and_frozen(self, tmp_path):
        wb = build_inferential_stats_workbook(**_write_synthetic_inputs(tmp_path))
        ws2 = wb["E2_TopicSentiment"]
        assert ws2.freeze_panes == "A4"
        # sorted ascending by cohens_h: topic 2 (-0.2), topic 3 (0.05), topic 1 (0.3)
        assert [ws2.cell(row=4 + i, column=1).value for i in range(3)] == [2, 3, 1]

    def test_e3_sheet_has_model_and_f_test_blocks(self, tmp_path):
        wb = build_inferential_stats_workbook(**_write_synthetic_inputs(tmp_path))
        ws3 = wb["E3_MessengerVsMessage"]
        assert ws3.cell(row=4, column=1).value == "Analyst only (messenger)"
        assert ws3.cell(row=8, column=1).value == "Incremental F-tests"
        assert ws3.cell(row=10, column=1).value == "Analyst, added to topic-only model"

    @pytest.mark.parametrize("missing_key", ["inferential_results_path", "topic_level_results_path", "dunn_posthoc_matrix_path"])
    def test_raises_on_empty_source(self, tmp_path, missing_key):
        paths = _write_synthetic_inputs(tmp_path)
        if missing_key == "inferential_results_path":
            paths[missing_key].write_text("{}", encoding="utf-8")
        elif missing_key == "topic_level_results_path":
            pd.DataFrame(columns=["topic_id", "topic_label", "n", "pos_ratio", "cohens_h", "z", "p_fdr", "significant_fdr"]).to_csv(paths[missing_key], index=False)
        else:
            pd.DataFrame().to_csv(paths[missing_key])
        with pytest.raises(CorpusValidationError):
            build_inferential_stats_workbook(**paths)


class TestSaveInferentialStatsWorkbook:
    def test_saves_under_original_filename_and_creates_parent_dir(self, tmp_path):
        wb = build_inferential_stats_workbook(**_write_synthetic_inputs(tmp_path))
        out = tmp_path / "nested" / "finfluencer_tr_2025_inferential_stats.xlsx"
        save_inferential_stats_workbook(wb, output_path=out)
        assert out.exists()
        reloaded = load_workbook(out)
        assert reloaded.sheetnames == _EXPECTED_SHEET_NAMES


# =============================================================================
# Differential test: packaged workbook vs. the real reference workbook.
# =============================================================================


@pytest.mark.skipif(not _ALL_REAL_INPUTS_PRESENT, reason=_SKIP_REASON)
class TestDifferentialAgainstRealReferenceWorkbook:
    @classmethod
    @pytest.fixture(scope="class")
    def new_workbook(cls):
        return build_inferential_stats_workbook(
            inferential_results_path=_REAL_INFERENTIAL_RESULTS,
            topic_level_results_path=_REAL_TOPIC_LEVEL_RESULTS,
            dunn_posthoc_matrix_path=_REAL_DUNN_MATRIX,
            weekly_sentiment_by_analyst_path=_REAL_WEEKLY_BY_ANALYST,
        )

    @classmethod
    @pytest.fixture(scope="class")
    def real_workbook(cls):
        return load_workbook(_REAL_WORKBOOK)

    def test_sheet_names_and_order_match(self, new_workbook, real_workbook):
        assert new_workbook.sheetnames == real_workbook.sheetnames == _EXPECTED_SHEET_NAMES

    @pytest.mark.parametrize("sheet_name", ["Summary", "E1_CrossAnalyst", "E1b_ClusterRobust", "E3_MessengerVsMessage"])
    def test_deterministic_sheet_cells_match_exactly(self, new_workbook, real_workbook, sheet_name):
        """Sheets with no tied-sort-key non-determinism: exact,
        position-by-position (value + essential style) comparison."""
        real_ws = real_workbook[sheet_name]
        new_ws = new_workbook[sheet_name]

        real_cells = _non_blank_cells(real_ws)
        new_cells = _non_blank_cells(new_ws)
        assert set(real_cells.keys()) == set(new_cells.keys())
        mismatches = {
            coord: (real_cells[coord], new_cells[coord]) for coord in real_cells
            if not _cell_tuples_equal(real_cells[coord], new_cells[coord])
        }
        assert not mismatches, f"{sheet_name}: {len(mismatches)} cell(s) differ: {dict(list(mismatches.items())[:5])}"

    def test_e2_sheet_rows_match_as_order_independent_set(self, new_workbook, real_workbook):
        """E2_TopicSentiment sorts by cohens_h, which has a known,
        previously-documented tied-value pair (topics 44 and 182 -- see
        Sprint 1A's test_inferential.py). Compare the full set of data
        rows (values only, keyed by topic_id) rather than positional
        order, exactly as Sprint 1A's differential test does for the
        same tie."""
        real_ws = real_workbook["E2_TopicSentiment"]
        new_ws = new_workbook["E2_TopicSentiment"]

        def _rows(ws):
            out = {}
            r = 4
            while ws.cell(row=r, column=1).value is not None:
                vals = tuple(ws.cell(row=r, column=c).value for c in range(1, 9))
                out[vals[0]] = vals  # keyed by topic_id
                r += 1
            return out

        real_rows = _rows(real_ws)
        new_rows = _rows(new_ws)
        assert set(real_rows.keys()) == set(new_rows.keys())
        mismatches = {
            tid: (real_rows[tid], new_rows[tid]) for tid in real_rows
            if not all(_values_equal(a, b) for a, b in zip(real_rows[tid], new_rows[tid], strict=True))
        }
        assert not mismatches, f"{len(mismatches)} topic row(s) differ: {dict(list(mismatches.items())[:5])}"

    def test_e2_header_and_freeze_panes_match(self, new_workbook, real_workbook):
        real_ws = real_workbook["E2_TopicSentiment"]
        new_ws = new_workbook["E2_TopicSentiment"]
        assert real_ws.freeze_panes == new_ws.freeze_panes == "A4"
        real_header = [real_ws.cell(row=3, column=c).value for c in range(1, 9)]
        new_header = [new_ws.cell(row=3, column=c).value for c in range(1, 9)]
        assert real_header == new_header

    @pytest.mark.parametrize("sheet_name,ncols", [
        ("Summary", 8), ("E1_CrossAnalyst", 5), ("E1b_ClusterRobust", 4),
        ("E2_TopicSentiment", 8), ("E3_MessengerVsMessage", 4),
    ])
    def test_column_widths_match(self, new_workbook, real_workbook, sheet_name, ncols):
        """Compared per resolved column index -- robust to a writer
        merging contiguous equal-width columns into a single XML
        range (observed on the real reference file; see module
        docstring)."""
        real_widths = _resolved_col_widths(real_workbook[sheet_name], ncols=ncols)
        new_widths = _resolved_col_widths(new_workbook[sheet_name], ncols=ncols)
        assert real_widths == new_widths

    def test_merged_cells_match(self, new_workbook, real_workbook):
        for sheet_name in _EXPECTED_SHEET_NAMES:
            real_merged = sorted(str(r) for r in real_workbook[sheet_name].merged_cells.ranges)
            new_merged = sorted(str(r) for r in new_workbook[sheet_name].merged_cells.ranges)
            assert real_merged == new_merged, f"{sheet_name}: merged cells differ"


# =============================================================================
# Acceptance test: reproduce the published workbook file.
# =============================================================================


@pytest.mark.skipif(not _ALL_REAL_INPUTS_PRESENT, reason=_SKIP_REASON)
class TestManuscriptReproduction:
    def test_reproduces_published_workbook_filename_and_sheets(self, tmp_path):
        wb = build_inferential_stats_workbook(
            inferential_results_path=_REAL_INFERENTIAL_RESULTS,
            topic_level_results_path=_REAL_TOPIC_LEVEL_RESULTS,
            dunn_posthoc_matrix_path=_REAL_DUNN_MATRIX,
            weekly_sentiment_by_analyst_path=_REAL_WEEKLY_BY_ANALYST,
        )
        out = tmp_path / "finfluencer_tr_2025_inferential_stats.xlsx"
        save_inferential_stats_workbook(wb, output_path=out)

        assert out.name == _REAL_WORKBOOK.name
        reloaded = load_workbook(out)
        assert reloaded.sheetnames == _EXPECTED_SHEET_NAMES
        # E2 has 120 topics (n>=30 filter, matching inferential.py's E2_MIN_TOPIC_N)
        ws2 = reloaded["E2_TopicSentiment"]
        n_data_rows = 0
        r = 4
        while ws2.cell(row=r, column=1).value is not None:
            n_data_rows += 1
            r += 1
        assert n_data_rows == 120
