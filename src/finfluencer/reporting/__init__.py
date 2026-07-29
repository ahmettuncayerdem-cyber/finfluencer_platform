"""
finfluencer.reporting
=======================

Packaged, testable versions of the manuscript's shadow analysis
pipeline (previously a set of unpackaged root-level scripts).

Sprint 1 scope (complete): five modules, packaging every
repository-proven root-level script this package currently covers:

* :mod:`finfluencer.reporting.master_table` -- ``export_master_table.py``.
* :mod:`finfluencer.reporting.inferential` -- ``run_inferential_tests.py``
  (the E1/E1b/E2/E3/R1/R2/R3 inferential battery).
* :mod:`finfluencer.reporting.manuscript_data` -- the
  ``topic_category``-independent third of ``build_manuscript_data.py``
  (Table 1, fig1_data, fig3_data). The remaining, ``topic_category``-
  dependent artifacts (Table 3, fig2_data, topic_results_full,
  top_pos5/top_neg5) are deliberately excluded: that column has no
  provenance anywhere in this repository's git history -- see the
  Sprint 1A evidence report.
* :mod:`finfluencer.reporting.manuscript_figures` -- ``build_stats_figures.py``
  (Figures S1-S6).
* :mod:`finfluencer.reporting.manuscript_tables` -- ``build_stats_tables.py``
  (the ``finfluencer_tr_2025_inferential_stats.xlsx`` workbook).

Out of Sprint 1 scope, and not exported here: E5/E6/E7 and R4-R7 (no
packageable implementation identified yet), and ``pub_data_pull.py``
(different data contract). These may be addressed in a future sprint.
"""

from __future__ import annotations

from finfluencer.reporting.inferential import (
    E2_MIN_TOPIC_N,
    R3_MIN_VIDEO_COMMENTS,
    InferentialResults,
    load_master_table,
    run_all_inferential_tests,
    run_e1_cross_analyst_sentiment,
    run_e1b_cluster_robustness,
    run_e2_topic_sentiment,
    run_e3_messenger_vs_message,
    run_r1_trend_tests,
    run_r2_herding,
    run_r3_volume_sentiment,
    save_inferential_results,
)
from finfluencer.reporting.manuscript_data import (
    ANALYST_DISPLAY_NAMES,
    NEGLOG10_P_FLOOR,
    build_dataset_characteristics_table,
    build_sentiment_by_analyst_figure_data,
    build_topic_volcano_figure_data,
    save_dataset_characteristics_table,
    save_sentiment_by_analyst_figure_data,
    save_topic_volcano_figure_data,
)
from finfluencer.reporting.manuscript_figures import (
    ANALYST_COLORS,
    ANALYST_ORDER,
    OKABE_ITO_PALETTE,
    build_all_manuscript_figures,
    plot_cluster_robust_se_comparison,
    plot_herding_heatmap,
    plot_messenger_vs_message,
    plot_sentiment_violin_by_analyst,
    plot_topic_volcano,
    plot_volume_vs_sentiment,
)
from finfluencer.reporting.manuscript_tables import (
    build_inferential_stats_workbook,
    save_inferential_stats_workbook,
)
from finfluencer.reporting.master_table import (
    COMMENT_COLUMNS,
    POOLED_CONFIGURATION,
    SENTIMENT_COLUMNS,
    WITHIN_ANALYST_CONFIGURATION,
    build_master_table,
    save_master_table,
)

__all__ = [
    # master_table
    "build_master_table",
    "save_master_table",
    "COMMENT_COLUMNS",
    "SENTIMENT_COLUMNS",
    "POOLED_CONFIGURATION",
    "WITHIN_ANALYST_CONFIGURATION",
    # inferential
    "load_master_table",
    "run_e1_cross_analyst_sentiment",
    "run_e1b_cluster_robustness",
    "run_e2_topic_sentiment",
    "run_e3_messenger_vs_message",
    "run_r1_trend_tests",
    "run_r2_herding",
    "run_r3_volume_sentiment",
    "InferentialResults",
    "run_all_inferential_tests",
    "save_inferential_results",
    "E2_MIN_TOPIC_N",
    "R3_MIN_VIDEO_COMMENTS",
    # manuscript_data
    "build_dataset_characteristics_table",
    "save_dataset_characteristics_table",
    "build_sentiment_by_analyst_figure_data",
    "save_sentiment_by_analyst_figure_data",
    "build_topic_volcano_figure_data",
    "save_topic_volcano_figure_data",
    "ANALYST_DISPLAY_NAMES",
    "NEGLOG10_P_FLOOR",
    # manuscript_figures
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
    # manuscript_tables
    "build_inferential_stats_workbook",
    "save_inferential_stats_workbook",
]
