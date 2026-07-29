"""Tests for finfluencer.reporting.manuscript_figures.

Three tiers, matching test_manuscript_data.py:

* Unit tests exercise each ``plot_*`` function against small synthetic
  data, checking that the expected filenames are produced and that
  empty input raises.
* Differential tests compare every text string embedded in the
  packaged function's output SVG against the real, pre-existing
  ``stats_figures/*.svg`` this repository's root-level
  ``build_stats_figures.py`` script produced. Skipped automatically if
  those files (or their real data sources) are absent.
* An acceptance test verifies ``build_all_manuscript_figures``
  reproduces the full, published set of twelve output files (six
  figures x PNG+SVG) with their exact original filenames.

Why SVG text comparison, not pixel comparison
------------------------------------------------
Matplotlib's default ``svg.fonttype`` is ``"path"`` -- text is
rendered as vector outlines, not literal SVG ``<text>`` elements.
Verified directly in this environment (matplotlib 3.10.9) that
matplotlib nonetheless embeds the original literal string as an XML
comment immediately before each glyph group, e.g.
``<!-- Figure S1. Sentiment score distribution by analyst -->``. This
is present regardless of font-rendering differences across
environments (it is the literal source string, not a rendered
glyph), so it gives an exact, environment-independent way to verify
every title, axis label, legend entry, and text annotation is
preserved -- without the flakiness of comparing rendered pixels
across matplotlib/OS/font versions. Confirmed empirically before
writing these tests: running the packaged functions against the real
data in this environment and diffing the full ordered list of text
comments against the real reference SVGs for all six figures produces
zero differences.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.exceptions import CorpusValidationError
from finfluencer.reporting.manuscript_figures import (
    ANALYST_ORDER,
    build_all_manuscript_figures,
    plot_cluster_robust_se_comparison,
    plot_herding_heatmap,
    plot_messenger_vs_message,
    plot_sentiment_violin_by_analyst,
    plot_topic_volcano,
    plot_volume_vs_sentiment,
)

# =============================================================================
# Real-data fixture locations (repo root), for differential/acceptance tests.
# =============================================================================

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_MASTER_TABLE = _REPO_ROOT / "master_table.csv"
_REAL_INFERENTIAL_RESULTS = _REPO_ROOT / "inferential_results.json"
_REAL_TOPIC_LEVEL_RESULTS = _REPO_ROOT / "topic_level_test_results.csv"
_REAL_VIDEO_LEVEL_RESULTS = _REPO_ROOT / "video_level_volume_sentiment.csv"
_REAL_WEEKLY_BY_ANALYST = _REPO_ROOT / "weekly_sentiment_by_analyst.csv"
_REAL_STATS_FIGURES_DIR = _REPO_ROOT / "stats_figures"

_ALL_REAL_INPUTS_PRESENT = all(p.exists() for p in (
    _REAL_MASTER_TABLE, _REAL_INFERENTIAL_RESULTS, _REAL_TOPIC_LEVEL_RESULTS,
    _REAL_VIDEO_LEVEL_RESULTS, _REAL_WEEKLY_BY_ANALYST, _REAL_STATS_FIGURES_DIR,
))
_SKIP_REASON = (
    "Real master_table.csv / inferential_results.json / side-CSVs / "
    "stats_figures/ reference not present in this environment (gitignored, "
    "regenerable research artifacts) -- differential/acceptance test skipped."
)

_FIGURE_NAMES = [
    "figS1_sentiment_violin_by_analyst",
    "figS2_cluster_robust_se",
    "figS3_topic_volcano",
    "figS4_messenger_vs_message",
    "figS5_volume_vs_sentiment",
    "figS6_herding_heatmap",
]


def _svg_text_comments(path: Path) -> list[str]:
    """Extract every ``<!-- ... -->`` XML comment (matplotlib's literal
    text strings under ``svg.fonttype='path'``) from an SVG file, in
    document order."""
    return re.findall(r"<!--\s*(.*?)\s*-->", path.read_text(encoding="utf-8"))


# =============================================================================
# Synthetic fixtures
# =============================================================================


def _synthetic_master_table() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = []
    for analyst in ANALYST_ORDER:
        for _ in range(20):
            rows.append({"analyst_key": analyst, "sentiment_prob": float(rng.uniform(0, 1))})
    return pd.DataFrame(rows)


def _synthetic_e1b() -> dict:
    return {
        "naive_se": {"C(analyst_key)[T.gecer]": 0.05, "C(analyst_key)[T.basaran]": 0.06},
        "cluster_se": {"C(analyst_key)[T.gecer]": 0.09, "C(analyst_key)[T.basaran]": 0.11},
    }


def _synthetic_topic_level_results() -> pd.DataFrame:
    return pd.DataFrame({
        "topic_id": [1, 2, 3],
        "cohens_h": [0.5, -0.3, 0.1],
        "p_fdr": [0.001, 0.2, 0.5],
        "significant_fdr": [True, False, False],
    })


def _synthetic_e3() -> dict:
    return {"r2_analyst_only": 0.02, "r2_topic_only": 0.2, "r2_full": 0.25}


def _synthetic_video_level_results() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = np.arange(5, 55, 5)
    return pd.DataFrame({
        "n_comments": n,
        "mean_sentiment": 0.5 + 0.001 * n + rng.normal(0, 0.02, size=len(n)),
    })


def _synthetic_r3() -> dict:
    return {"spearman_rho": 0.15, "p": 0.01, "n_videos": 40}


def _synthetic_weekly_by_analyst() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    weeks = pd.date_range("2025-01-05", periods=12, freq="W")
    data = {a: rng.uniform(0.3, 0.7, size=len(weeks)) for a in ANALYST_ORDER}
    return pd.DataFrame(data, index=weeks)


class TestPlotSentimentViolinByAnalyst:
    def test_produces_expected_filenames(self, tmp_path):
        paths = plot_sentiment_violin_by_analyst(_synthetic_master_table(), output_dir=tmp_path)
        names = {p.name for p in paths}
        assert names == {"figS1_sentiment_violin_by_analyst.png", "figS1_sentiment_violin_by_analyst.svg"}
        assert all(p.exists() and p.stat().st_size > 0 for p in paths)

    def test_raises_on_empty_master_table(self, tmp_path):
        with pytest.raises(CorpusValidationError):
            plot_sentiment_violin_by_analyst(pd.DataFrame(columns=["analyst_key", "sentiment_prob"]), output_dir=tmp_path)


class TestPlotClusterRobustSeComparison:
    def test_produces_expected_filenames(self, tmp_path):
        paths = plot_cluster_robust_se_comparison(_synthetic_e1b(), output_dir=tmp_path)
        names = {p.name for p in paths}
        assert names == {"figS2_cluster_robust_se.png", "figS2_cluster_robust_se.svg"}


class TestPlotTopicVolcano:
    def test_produces_expected_filenames(self, tmp_path):
        paths = plot_topic_volcano(_synthetic_topic_level_results(), output_dir=tmp_path)
        names = {p.name for p in paths}
        assert names == {"figS3_topic_volcano.png", "figS3_topic_volcano.svg"}

    def test_raises_on_empty_topic_level_results(self, tmp_path):
        with pytest.raises(CorpusValidationError):
            plot_topic_volcano(pd.DataFrame(columns=["cohens_h", "p_fdr", "significant_fdr"]), output_dir=tmp_path)


class TestPlotMessengerVsMessage:
    def test_produces_expected_filenames(self, tmp_path):
        paths = plot_messenger_vs_message(_synthetic_e3(), output_dir=tmp_path)
        names = {p.name for p in paths}
        assert names == {"figS4_messenger_vs_message.png", "figS4_messenger_vs_message.svg"}


class TestPlotVolumeVsSentiment:
    def test_produces_expected_filenames(self, tmp_path):
        paths = plot_volume_vs_sentiment(_synthetic_video_level_results(), _synthetic_r3(), output_dir=tmp_path)
        names = {p.name for p in paths}
        assert names == {"figS5_volume_vs_sentiment.png", "figS5_volume_vs_sentiment.svg"}

    def test_raises_on_empty_video_level_results(self, tmp_path):
        with pytest.raises(CorpusValidationError):
            plot_volume_vs_sentiment(
                pd.DataFrame(columns=["n_comments", "mean_sentiment"]), _synthetic_r3(), output_dir=tmp_path,
            )


class TestPlotHerdingHeatmap:
    def test_produces_expected_filenames(self, tmp_path):
        paths = plot_herding_heatmap(_synthetic_weekly_by_analyst(), output_dir=tmp_path)
        names = {p.name for p in paths}
        assert names == {"figS6_herding_heatmap.png", "figS6_herding_heatmap.svg"}

    def test_raises_on_empty_weekly_by_analyst(self, tmp_path):
        with pytest.raises(CorpusValidationError):
            plot_herding_heatmap(pd.DataFrame(columns=ANALYST_ORDER), output_dir=tmp_path)


# =============================================================================
# Differential tests: packaged figures vs. the real, checked-in reference SVGs.
# =============================================================================


@pytest.mark.skipif(not _ALL_REAL_INPUTS_PRESENT, reason=_SKIP_REASON)
class TestDifferentialAgainstRealReferenceFigures:
    @classmethod
    @pytest.fixture(scope="class")
    def generated_dir(cls, tmp_path_factory):
        out_dir = tmp_path_factory.mktemp("stats_figures_new")
        build_all_manuscript_figures(
            master_table_path=_REAL_MASTER_TABLE,
            inferential_results_path=_REAL_INFERENTIAL_RESULTS,
            topic_level_results_path=_REAL_TOPIC_LEVEL_RESULTS,
            video_level_results_path=_REAL_VIDEO_LEVEL_RESULTS,
            weekly_sentiment_by_analyst_path=_REAL_WEEKLY_BY_ANALYST,
            output_dir=out_dir,
        )
        return out_dir

    @pytest.mark.parametrize("figure_name", _FIGURE_NAMES)
    def test_svg_text_content_matches_exactly(self, generated_dir, figure_name):
        real_svg = _REAL_STATS_FIGURES_DIR / f"{figure_name}.svg"
        new_svg = generated_dir / f"{figure_name}.svg"
        assert new_svg.exists()

        real_texts = _svg_text_comments(real_svg)
        new_texts = _svg_text_comments(new_svg)
        assert new_texts == real_texts

    @pytest.mark.parametrize("figure_name", _FIGURE_NAMES)
    def test_png_and_svg_are_nontrivially_sized(self, generated_dir, figure_name):
        for ext in ("png", "svg"):
            p = generated_dir / f"{figure_name}.{ext}"
            assert p.stat().st_size > 1000  # sanity floor -- not an empty/corrupt render


# =============================================================================
# Acceptance test: reproduce the full, published figure set.
# =============================================================================


@pytest.mark.skipif(not _ALL_REAL_INPUTS_PRESENT, reason=_SKIP_REASON)
class TestManuscriptReproduction:
    def test_reproduces_all_twelve_published_figure_files(self, tmp_path):
        """Sprint 1B.2 acceptance criterion: build_all_manuscript_figures
        must reproduce the exact, published set of output files -- same
        six figures, same PNG+SVG pairing, same filenames as
        build_stats_figures.py's real output (stats_figures/)."""
        paths = build_all_manuscript_figures(
            master_table_path=_REAL_MASTER_TABLE,
            inferential_results_path=_REAL_INFERENTIAL_RESULTS,
            topic_level_results_path=_REAL_TOPIC_LEVEL_RESULTS,
            video_level_results_path=_REAL_VIDEO_LEVEL_RESULTS,
            weekly_sentiment_by_analyst_path=_REAL_WEEKLY_BY_ANALYST,
            output_dir=tmp_path,
        )

        produced_names = {p.name for p in paths}
        real_names = {p.name for p in _REAL_STATS_FIGURES_DIR.iterdir() if p.suffix in (".png", ".svg")}
        assert produced_names == real_names
        assert len(paths) == 12
