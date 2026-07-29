"""
finfluencer.reporting.inferential
====================================

Packaged version of the root-level ``run_inferential_tests.py`` script:
the internal-data-only inferential statistics battery run against
:func:`finfluencer.reporting.master_table.build_master_table`'s output
(``master_table.csv``). No external data (prices, FX, gold, macro
series) is used — every test below is computable from columns already
present in the master table.

Pipeline
--------
Seven analyses, run in this exact order (matching the original script):

* **E1** — Cross-analyst sentiment comparison: chi-square test of
  independence + Cramer's V, Kruskal-Wallis H + epsilon-squared, Dunn's
  post-hoc (Holm-adjusted), Shapiro-Wilk normality check on a fixed
  subsample.
* **E1b** — Cluster-robust logistic regression: naive vs. video-
  clustered standard errors, to check whether E1's group comparison is
  inflated by within-video comment nesting.
* **E2** — Topic-sentiment association: per-topic one-sample
  proportion z-test vs. the baseline positive rate, Cohen's h,
  Benjamini-Hochberg FDR correction across topics.
* **E3** — Messenger-vs-message variance partitioning: nested OLS
  models (analyst-only, topic-only, full) with incremental F-tests and
  partial R-squared.
* **R1** — Mann-Kendall weekly trend test on pooled sentiment and the
  top topic's weekly frequency.
* **R2** — Cross-analyst weekly sentiment co-movement ("herding"):
  Pearson/Spearman correlation matrices.
* **R3** — Video-level comment volume vs. mean sentiment (Spearman).

Scope note (Sprint 1A)
-----------------------
This module packages ``run_inferential_tests.py`` only. It does not
implement anything from ``build_manuscript_data.py`` (Table 3, fig2,
fig3), which additionally requires a ``topic_category`` column with no
provenance anywhere in this repository's history — see the Sprint 1A
evidence report. ``build_manuscript_data.py`` reads THIS module's own
JSON output (``inferential_results.json`` -> ``E2_topic_sentiment`` ->
``topic_results``), so the true dependency order is
``master_table -> inferential -> (out of scope) manuscript tables``,
not the reverse.

This module does not fabricate, simulate, or otherwise substitute for
missing input data: :func:`load_master_table` raises
:class:`~finfluencer.core.exceptions.CorpusValidationError` if the
loaded table has zero usable (non-null-sentiment) rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pymannkendall as mk
import scikit_posthocs as sp
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

from finfluencer.core.exceptions import CorpusValidationError
from finfluencer.core.logging import get_logger
from finfluencer.utils.io import ensure_dir, write_json

_log = get_logger(__name__)

#: Minimum per-topic comment count for inclusion in the E2 battery.
#: Matches run_inferential_tests.py's ``if n_g < 30: continue`` filter.
E2_MIN_TOPIC_N = 30

#: random_state for the Shapiro-Wilk normality subsample (E1). Fixed to
#: match run_inferential_tests.py exactly, for bit-for-bit reproducibility
#: of the subsample drawn.
E1_SHAPIRO_RANDOM_STATE = 42

#: Max subsample size for the Shapiro-Wilk test (scipy's implementation
#: is unreliable/slow well above a few thousand observations).
E1_SHAPIRO_MAX_N = 5000

#: Minimum comments-per-video for inclusion in R3.
R3_MIN_VIDEO_COMMENTS = 5


def load_master_table(*, path: Path = Path("master_table.csv")) -> pd.DataFrame:
    """Load and prepare the master table exactly as ``run_inferential_tests.py``
    did: parse ``posted_date``, drop rows with missing sentiment, add
    an ``is_positive`` indicator column.

    Raises
    ------
    CorpusValidationError
        If the table has zero rows after dropping missing-sentiment rows.
    """
    df = pd.read_csv(path, parse_dates=["posted_date"])
    df = df.dropna(subset=["sentiment_class", "sentiment_prob"]).copy()
    df["is_positive"] = (df["sentiment_class"] == "positive").astype(int)
    if df.empty:
        raise CorpusValidationError(
            "master table has zero rows with non-null sentiment; "
            "cannot run the inferential statistics battery on an empty corpus.",
            path=str(path),
        )
    _log.info("master_table_loaded_for_inference", n_rows=len(df), path=str(path))
    return df


def run_e1_cross_analyst_sentiment(df: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    """E1: cross-analyst sentiment comparison.

    Returns ``(result, dunn_posthoc_matrix)`` where ``result`` matches
    the original ``RESULTS["E1_cross_analyst_sentiment"]`` dict exactly.
    """
    ct = pd.crosstab(df["analyst_key"], df["sentiment_class"])
    chi2, p_chi2, _dof, _exp = stats.chi2_contingency(ct)
    n = ct.values.sum()
    k = min(ct.shape) - 1
    cramers_v = np.sqrt(chi2 / (n * k))

    groups = [g["sentiment_prob"].values for _, g in df.groupby("analyst_key")]
    h_stat, p_kw = stats.kruskal(*groups)
    n_total = len(df)
    k_groups = df["analyst_key"].nunique()
    epsilon_sq = (h_stat - k_groups + 1) / (n_total - k_groups)

    dunn = sp.posthoc_dunn(df, val_col="sentiment_prob", group_col="analyst_key", p_adjust="holm")

    sh_stat, sh_p = stats.shapiro(
        df["sentiment_prob"].sample(min(E1_SHAPIRO_MAX_N, len(df)), random_state=E1_SHAPIRO_RANDOM_STATE)
    )

    result: dict[str, Any] = {
        "chi2": float(chi2), "p": float(p_chi2), "cramers_v": float(cramers_v),
        "kruskal_H": float(h_stat), "kruskal_p": float(p_kw), "epsilon_sq": float(epsilon_sq),
        "shapiro_W": float(sh_stat), "shapiro_p": float(sh_p),
        "dunn_holm_pvalues": dunn.round(6).to_dict(),
        "group_medians": df.groupby("analyst_key")["sentiment_prob"].median().to_dict(),
        "group_n": df.groupby("analyst_key").size().to_dict(),
    }
    return result, dunn


def run_e1b_cluster_robustness(df: pd.DataFrame) -> dict[str, Any]:
    """E1b: cluster-robust logistic regression (``video_id`` clustering check).

    Matches ``RESULTS["E1b_cluster_robustness"]`` exactly.
    """
    d = df.copy()
    d["analyst_key"] = d["analyst_key"].astype("category")
    model = smf.logit("is_positive ~ C(analyst_key)", data=d).fit(disp=0)
    robust = smf.logit("is_positive ~ C(analyst_key)", data=d).fit(
        disp=0, cov_type="cluster", cov_kwds={"groups": d["video_id"]},
    )
    n_videos = d["video_id"].nunique()
    return {
        "naive_se": model.bse.to_dict(),
        "cluster_se": robust.bse.to_dict(),
        "se_inflation_ratio": (robust.bse / model.bse).to_dict(),
        "n_videos": int(n_videos), "n_comments": int(len(d)),
    }


def run_e2_topic_sentiment(df: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    """E2: topic-sentiment association with Benjamini-Hochberg FDR correction.

    Returns ``(result, topic_level_results)``. ``result["topic_results"]``
    is the exact records list ``build_manuscript_data.py`` (out of
    Sprint 1A's scope) reads from ``inferential_results.json`` to build
    its Table 3 -- preserved here unchanged even though that consumer
    is not itself packaged this sprint.
    """
    dft = df.dropna(subset=["topic_id_pooled"]).copy()
    baseline_pos_rate = dft["is_positive"].mean()

    topic_ct = pd.crosstab(dft["topic_id_pooled"], dft["sentiment_class"])
    chi2_t, p_t, _dof_t, _ = stats.chi2_contingency(topic_ct)
    n_t = topic_ct.values.sum()
    k_t = min(topic_ct.shape) - 1
    cramers_v_topic = np.sqrt(chi2_t / (n_t * k_t))

    topic_stats: list[dict[str, Any]] = []
    for tid, g in dft.groupby("topic_id_pooled"):
        n_g = len(g)
        if n_g < E2_MIN_TOPIC_N:
            continue
        x = g["is_positive"].sum()
        p_hat = x / n_g
        se = np.sqrt(baseline_pos_rate * (1 - baseline_pos_rate) / n_g)
        z = (p_hat - baseline_pos_rate) / se
        p_val = 2 * (1 - stats.norm.cdf(abs(z)))
        h = 2 * np.arcsin(np.sqrt(p_hat)) - 2 * np.arcsin(np.sqrt(baseline_pos_rate))
        label = g["topic_label_pooled"].iloc[0]
        topic_stats.append({
            # pandas-stubs types a groupby key as a broad Hashable-like union
            # (it cannot statically narrow from the grouped column name);
            # topic_id_pooled is always numeric at runtime.
            "topic_id": int(tid),  # type: ignore[arg-type]
            "topic_label": label, "n": n_g,
            "pos_ratio": p_hat, "z": z, "p": p_val, "cohens_h": h,
        })

    topic_df = pd.DataFrame(topic_stats)
    rej, p_adj, _, _ = sm.stats.multipletests(topic_df["p"], method="fdr_bh")[:4]
    topic_df["p_fdr"] = p_adj
    topic_df["significant_fdr"] = rej
    topic_df = topic_df.sort_values("cohens_h")
    n_sig = topic_df["significant_fdr"].sum()

    result: dict[str, Any] = {
        "overall_chi2": float(chi2_t), "overall_p": float(p_t), "cramers_v": float(cramers_v_topic),
        "baseline_pos_rate": float(baseline_pos_rate),
        "n_topics_tested": int(len(topic_df)), "n_significant_fdr": int(n_sig),
        "topic_results": topic_df.to_dict("records"),
    }
    return result, topic_df


def run_e3_messenger_vs_message(df: pd.DataFrame) -> dict[str, Any]:
    """E3: messenger (analyst) vs. message (topic) variance partitioning.

    Matches ``RESULTS["E3_messenger_vs_message"]`` exactly. The
    original script also fit a null (intercept-only) model
    (``m_null``) but never used its result in ``RESULTS`` or any printed
    output; it is omitted here as a no-op with zero effect on observable
    behavior.
    """
    d3 = df.dropna(subset=["topic_id_pooled"]).copy()
    d3["analyst_key"] = d3["analyst_key"].astype("category")
    d3["topic_id_pooled"] = d3["topic_id_pooled"].astype(int).astype("category")

    m_analyst = smf.ols("sentiment_prob ~ C(analyst_key)", data=d3).fit()
    m_topic = smf.ols("sentiment_prob ~ C(topic_id_pooled)", data=d3).fit()
    m_full = smf.ols("sentiment_prob ~ C(analyst_key) + C(topic_id_pooled)", data=d3).fit()

    f_test_analyst_given_topic = m_full.compare_f_test(m_topic)
    f_test_topic_given_analyst = m_full.compare_f_test(m_analyst)

    partial_r2_analyst = m_full.rsquared - m_topic.rsquared
    partial_r2_topic = m_full.rsquared - m_analyst.rsquared

    return {
        "r2_analyst_only": float(m_analyst.rsquared),
        "r2_topic_only": float(m_topic.rsquared),
        "r2_full": float(m_full.rsquared),
        "partial_r2_analyst_over_topic": float(partial_r2_analyst),
        "partial_r2_topic_over_analyst": float(partial_r2_topic),
        "f_test_analyst_given_topic": {
            "F": float(f_test_analyst_given_topic[0]), "p": float(f_test_analyst_given_topic[1]),
        },
        "f_test_topic_given_analyst": {
            "F": float(f_test_topic_given_analyst[0]), "p": float(f_test_topic_given_analyst[1]),
        },
    }


def run_r1_trend_tests(df: pd.DataFrame) -> dict[str, Any]:
    """R1: Mann-Kendall weekly trend test (pooled sentiment + top-topic frequency).

    Matches ``RESULTS["R1_trend_tests"]`` exactly.
    """
    dfw = df.set_index("posted_date").sort_index()
    weekly_sent = dfw["sentiment_prob"].resample("W").mean().dropna()
    mk_sent = mk.original_test(weekly_sent.values)

    top_topic_id = df["topic_id_pooled"].value_counts().index[0]
    top_topic_series = (
        dfw[dfw["topic_id_pooled"] == top_topic_id]
        .resample("W").size()
        .reindex(weekly_sent.index, fill_value=0)
    )
    mk_topic = mk.original_test(top_topic_series.values)

    return {
        "n_weeks": int(len(weekly_sent)),
        "pooled_sentiment_trend": {
            "trend": mk_sent.trend, "p": float(mk_sent.p),
            "tau": float(mk_sent.Tau), "sen_slope": float(mk_sent.slope),
        },
        "top_topic_id": int(top_topic_id),
        "top_topic_freq_trend": {
            "trend": mk_topic.trend, "p": float(mk_topic.p), "tau": float(mk_topic.Tau),
        },
    }


def run_r2_herding(df: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    """R2: cross-analyst weekly sentiment co-movement ("herding" check).

    Returns ``(result, weekly_sentiment_by_analyst)``. ``result``
    matches ``RESULTS["R2_herding"]`` exactly.
    """
    dfw = df.set_index("posted_date").sort_index()
    weekly_by_analyst = dfw.groupby("analyst_key")["sentiment_prob"].resample("W").mean().unstack(level=0)
    weekly_by_analyst = weekly_by_analyst.dropna(how="all")
    corr_pearson = weekly_by_analyst.corr(method="pearson")
    corr_spearman = weekly_by_analyst.corr(method="spearman")

    result: dict[str, Any] = {
        "pearson_corr": corr_pearson.round(4).to_dict(),
        "spearman_corr": corr_spearman.round(4).to_dict(),
        "n_weeks_total": int(len(weekly_by_analyst)),
    }
    return result, weekly_by_analyst


def run_r3_volume_sentiment(df: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    """R3: video-level comment volume vs. mean sentiment (Spearman).

    Returns ``(result, video_level_volume_sentiment)``. ``result``
    matches ``RESULTS["R3_volume_sentiment"]`` exactly.
    """
    video_level = df.groupby("video_id").agg(
        n_comments=("comment_id", "size"), mean_sentiment=("sentiment_prob", "mean"),
    ).reset_index()
    video_level = video_level[video_level["n_comments"] >= R3_MIN_VIDEO_COMMENTS]
    rho, p_rho = stats.spearmanr(video_level["n_comments"], video_level["mean_sentiment"])

    result: dict[str, Any] = {
        "n_videos": int(len(video_level)), "spearman_rho": float(rho), "p": float(p_rho),
    }
    return result, video_level


@dataclass
class InferentialResults:
    """Bundle of every output the original ``run_inferential_tests.py`` produced.

    ``results`` mirrors the script's ``RESULTS`` dict exactly (same
    seven keys, same nested structure) and is what
    :func:`save_inferential_results` writes to
    ``inferential_results.json``. The four DataFrame fields mirror the
    script's four side-CSV outputs.
    """

    results: dict[str, Any]
    topic_level_results: pd.DataFrame
    dunn_posthoc_matrix: pd.DataFrame
    weekly_sentiment_by_analyst: pd.DataFrame
    video_level_volume_sentiment: pd.DataFrame


def run_all_inferential_tests(df: pd.DataFrame) -> InferentialResults:
    """Run the full E1 / E1b / E2 / E3 / R1 / R2 / R3 inferential battery.

    ``df`` must already be prepared via :func:`load_master_table`
    (parsed dates, sentiment-null rows dropped, ``is_positive`` present).

    Behavior-preserving packaging of ``run_inferential_tests.py``: same
    seven analyses, same order, same statistics, same fixed
    ``random_state`` (E1 Shapiro-Wilk subsample) -- see
    ``tests/unit/test_reporting/test_inferential.py`` for a differential
    test against the real ``inferential_results.json``.
    """
    e1_result, dunn = run_e1_cross_analyst_sentiment(df)
    e1b_result = run_e1b_cluster_robustness(df)
    e2_result, topic_df = run_e2_topic_sentiment(df)
    e3_result = run_e3_messenger_vs_message(df)
    r1_result = run_r1_trend_tests(df)
    r2_result, weekly_by_analyst = run_r2_herding(df)
    r3_result, video_level = run_r3_volume_sentiment(df)

    results: dict[str, Any] = {
        "E1_cross_analyst_sentiment": e1_result,
        "E1b_cluster_robustness": e1b_result,
        "E2_topic_sentiment": e2_result,
        "E3_messenger_vs_message": e3_result,
        "R1_trend_tests": r1_result,
        "R2_herding": r2_result,
        "R3_volume_sentiment": r3_result,
    }
    _log.info("inferential_battery_completed", n_comments=len(df))
    return InferentialResults(
        results=results,
        topic_level_results=topic_df,
        dunn_posthoc_matrix=dunn,
        weekly_sentiment_by_analyst=weekly_by_analyst,
        video_level_volume_sentiment=video_level,
    )


def save_inferential_results(inferential: InferentialResults, *, output_dir: Path = Path(".")) -> None:
    """Write the five output files, with the original script's exact filenames.

    Matches ``run_inferential_tests.py``'s own encoding/index choices
    for each file individually rather than uniformly reusing
    :mod:`finfluencer.utils.io`'s CSV helper: ``utils.io.write_csv``
    always writes UTF-8 *with a BOM* (``utf-8-sig``) and always passes
    ``index=False``, but the original script's four ``to_csv`` calls
    used plain UTF-8 throughout, and two of them (the Dunn matrix, the
    weekly-by-analyst table) deliberately keep their DataFrame index
    (analyst_key labels / week-ending dates) while the other two do
    not. ``utils.io.write_json`` IS reused as-is for the JSON output,
    with ``sort_keys=False`` to match the original ``json.dump`` call's
    key order exactly.
    """
    out = Path(output_dir)
    ensure_dir(out)

    write_json(inferential.results, out / "inferential_results.json", sort_keys=False)
    inferential.topic_level_results.to_csv(
        out / "topic_level_test_results.csv", index=False, encoding="utf-8",
    )
    inferential.dunn_posthoc_matrix.to_csv(
        out / "dunn_posthoc_matrix.csv", encoding="utf-8",
    )
    inferential.weekly_sentiment_by_analyst.to_csv(
        out / "weekly_sentiment_by_analyst.csv", encoding="utf-8",
    )
    inferential.video_level_volume_sentiment.to_csv(
        out / "video_level_volume_sentiment.csv", index=False, encoding="utf-8",
    )
    _log.info("inferential_results_saved", output_dir=str(out))


__all__ = [
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
]
