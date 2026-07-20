"""
finfluencer.market.confirmatory_analysis
===========================================

Minimal confirmatory market-integration analysis for publication
(Borsa Istanbul Review scope). ONE pair only: the pooled, unweighted
daily sentiment index vs. BIST100 daily log returns. No other market
series, no VAR/VECM/Johansen/GARCH, no multi-market system - a
deliberately narrow, pre-specified, publication-minimal test.

Pipeline
--------
1. Descriptive statistics for both series, plus ADF stationarity
   checks (a prerequisite sanity check for OLS/Granger validity on
   time series, not a "Stage A VAR-pipeline" in the earlier, shelved
   full-scope design - just enough due diligence to defend the
   regression against a spurious-regression objection).
2. Pearson correlation (linear association).
3. Spearman correlation (monotonic association, robust to outliers /
   the sentiment index's bounded [0, 1] support).
4. OLS: ``xu100_return_t ~ sentiment_index_t`` with HAC (Newey-West)
   standard errors (maxlags=5) - contemporaneous relationship, robust
   to residual autocorrelation, matching this project's established
   practice of never reporting naive OLS SEs on non-iid data (cf. E1b,
   E6, R7 in the main manuscript).
5. Granger causality, both directions, lags 1-5, via
   ``statsmodels.tsa.stattools.grangercausalitytests``. Lag 1 (next
   trading day) is the pre-specified confirmatory result; lags 2-5 are
   reported alongside as a robustness display, not as a separate
   multiple-comparison family requiring its own FDR correction (this
   is a single pre-specified pair, not the shelved exploratory family
   of the full-scope design).

Output tables
-------------
``regression_table()`` returns the correlation + OLS table (Pearson,
Spearman, OLS coefficients/R-squared). Granger causality is reported
in its own dedicated table (``results["granger"]``, all lags x both
directions) rather than folded into the regression table, matching
the four-artifact publication deliverable: descriptive table, OLS
regression table, Granger causality table, one figure.

This module does not fabricate, simulate, or otherwise substitute for
missing input data: every function raises if given empty/insufficient
real data. Callers are responsible for supplying genuine
sentiment_index_daily.parquet / market_data.parquet built from
Sections above.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.tsa.stattools import adfuller, grangercausalitytests

from finfluencer.core.exceptions import DataError
from finfluencer.core.logging import get_logger
from finfluencer.utils.io import read_parquet

_log = get_logger(__name__)

#: Granger causality lags reported (trading days). Lag 1 is the
#: pre-specified confirmatory horizon.
GRANGER_LAGS = (1, 2, 3, 4, 5)

#: Newey-West HAC lag truncation for the OLS regression.
HAC_MAXLAGS = 5


def build_analysis_panel(
    *,
    sentiment_index_path: Path = Path("data/processed/market_sentiment/sentiment_index_daily.parquet"),
    market_data_path: Path = Path("data/market/market_data.parquet"),
) -> pd.DataFrame:
    """Inner-join the sentiment index and BIST100 return onto trading days.

    Returns columns: ``date``, ``sentiment_index``, ``n_comments``,
    ``xu100_close``, ``xu100_return``. Rows with a missing return
    (e.g. the first trading day, which has no prior close to compute a
    return from) are dropped explicitly and the drop is logged.
    """
    idx = read_parquet(sentiment_index_path).rename(columns={"trading_date": "date"})
    mkt = read_parquet(market_data_path)
    for col in ("date", "xu100_close", "xu100_return"):
        if col not in mkt.columns:
            raise DataError(f"market_data.parquet missing required column {col!r}",
                             path=str(market_data_path), columns=list(mkt.columns))

    idx["date"] = pd.to_datetime(idx["date"])
    mkt["date"] = pd.to_datetime(mkt["date"])
    panel = idx.merge(mkt[["date", "xu100_close", "xu100_return"]], on="date", how="inner")
    panel = panel.sort_values("date").reset_index(drop=True)

    n_before = len(panel)
    panel = panel.dropna(subset=["sentiment_index", "xu100_return"])
    if len(panel) < n_before:
        _log.warning("analysis_panel_rows_dropped_for_na",
                      n_dropped=n_before - len(panel), n_remaining=len(panel))

    if len(panel) < 10:
        raise DataError(
            f"Analysis panel has only {len(panel)} usable trading days after merge/dropna; "
            "too few for a meaningful correlation/OLS/Granger analysis (need >= 10).",
            n_rows=len(panel),
        )
    return panel


def descriptive_table(panel: pd.DataFrame) -> pd.DataFrame:
    """One descriptive table: N, mean, SD, min, max, and an ADF stationarity
    check (statistic, p-value, decision at alpha=0.05) for each series."""
    rows = []
    for col, label in (("sentiment_index", "Pooled sentiment index"),
                        ("xu100_return", "BIST100 daily log return")):
        s = panel[col].dropna()
        adf_stat, adf_p, *_ = adfuller(s, autolag="AIC")
        rows.append({
            "series": label,
            "n": int(s.shape[0]),
            "mean": float(s.mean()),
            "sd": float(s.std(ddof=1)),
            "min": float(s.min()),
            "max": float(s.max()),
            "adf_statistic": float(adf_stat),
            "adf_p_value": float(adf_p),
            "stationary_at_5pct": bool(adf_p < 0.05),
        })
    return pd.DataFrame(rows)


def _granger_direction(panel: pd.DataFrame, *, effect_col: str, cause_col: str) -> list[dict[str, Any]]:
    """Run Granger causality: does ``cause_col`` Granger-cause ``effect_col``?

    ``statsmodels.tsa.stattools.grangercausalitytests`` takes a 2-column
    array and tests whether the SECOND column Granger-causes the FIRST.
    We therefore always pass ``[effect_col, cause_col]`` in that order.
    This exact convention is verified by a directional unit test
    (tests/unit/test_market/test_confirmatory_analysis.py) using a
    synthetic series with a known, constructed causal direction, to
    guard against silently reporting the reversed direction.
    """
    data = panel[[effect_col, cause_col]].to_numpy()
    results = grangercausalitytests(data, maxlag=max(GRANGER_LAGS), verbose=False)
    rows = []
    for lag in GRANGER_LAGS:
        f_test = results[lag][0]["ssr_ftest"]
        f_stat, f_p, df_denom, df_num = f_test
        rows.append({
            "direction": f"{cause_col} -> {effect_col}",
            "lag": lag,
            "f_statistic": float(f_stat),
            "p_value": float(f_p),
            "significant_5pct": bool(f_p < 0.05),
        })
    return rows


def run_confirmatory_analysis(panel: pd.DataFrame) -> dict[str, Any]:
    """Run Pearson, Spearman, OLS, and both-direction Granger causality.

    Returns a dict with keys: ``pearson``, ``spearman``, ``ols``
    (a dict of coef/se/t/p for const and sentiment_index, plus r2,
    nobs), and ``granger`` (a DataFrame, both directions x 5 lags).
    """
    x = panel["sentiment_index"].to_numpy()
    y = panel["xu100_return"].to_numpy()

    pearson_r, pearson_p = stats.pearsonr(x, y)
    spearman_rho, spearman_p = stats.spearmanr(x, y)

    X = sm.add_constant(panel[["sentiment_index"]])
    ols_model = sm.OLS(panel["xu100_return"], X).fit(
        cov_type="HAC", cov_kwds={"maxlags": HAC_MAXLAGS},
    )
    ols_summary = {
        "nobs": int(ols_model.nobs),
        "r_squared": float(ols_model.rsquared),
        "const_coef": float(ols_model.params["const"]),
        "const_se": float(ols_model.bse["const"]),
        "const_t": float(ols_model.tvalues["const"]),
        "const_p": float(ols_model.pvalues["const"]),
        "sentiment_coef": float(ols_model.params["sentiment_index"]),
        "sentiment_se": float(ols_model.bse["sentiment_index"]),
        "sentiment_t": float(ols_model.tvalues["sentiment_index"]),
        "sentiment_p": float(ols_model.pvalues["sentiment_index"]),
        "cov_type": "HAC (Newey-West)",
        "hac_maxlags": HAC_MAXLAGS,
    }

    granger_rows = (
        _granger_direction(panel, effect_col="xu100_return", cause_col="sentiment_index")
        + _granger_direction(panel, effect_col="sentiment_index", cause_col="xu100_return")
    )

    return {
        "pearson": {"r": float(pearson_r), "p_value": float(pearson_p)},
        "spearman": {"rho": float(spearman_rho), "p_value": float(spearman_p)},
        "ols": ols_summary,
        "granger": pd.DataFrame(granger_rows),
        "n_obs": int(len(panel)),
    }


def regression_table(results: dict[str, Any]) -> pd.DataFrame:
    """The correlation + OLS regression table: Pearson r, Spearman rho,
    and the OLS coefficients (const, sentiment_index, HAC SE) with
    R-squared. Granger causality is a separate dedicated table
    (``results["granger"]``), not folded in here."""
    rows = [
        {"statistic": "Pearson r", "value": results["pearson"]["r"],
         "p_value": results["pearson"]["p_value"], "n": results["n_obs"]},
        {"statistic": "Spearman rho", "value": results["spearman"]["rho"],
         "p_value": results["spearman"]["p_value"], "n": results["n_obs"]},
        {"statistic": "OLS: const (intercept)",
         "value": results["ols"]["const_coef"], "p_value": results["ols"]["const_p"],
         "n": results["ols"]["nobs"]},
        {"statistic": "OLS: sentiment_index coefficient (HAC SE)",
         "value": results["ols"]["sentiment_coef"], "p_value": results["ols"]["sentiment_p"],
         "n": results["ols"]["nobs"]},
        {"statistic": "OLS R-squared", "value": results["ols"]["r_squared"],
         "p_value": np.nan, "n": results["ols"]["nobs"]},
    ]
    return pd.DataFrame(rows)


def granger_table(results: dict[str, Any]) -> pd.DataFrame:
    """The dedicated Granger causality table: both directions x lags 1-5."""
    return results["granger"]


__all__ = [
    "GRANGER_LAGS", "HAC_MAXLAGS", "build_analysis_panel", "descriptive_table",
    "run_confirmatory_analysis", "regression_table", "granger_table",
]
