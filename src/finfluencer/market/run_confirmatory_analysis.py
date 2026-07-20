"""
finfluencer.market.run_confirmatory_analysis
================================================

CLI orchestrator for the minimal, publication-scoped market-integration
analysis: pooled sentiment index vs. BIST100 daily return. Produces
exactly four artefacts and nothing else: descriptive statistics table,
OLS regression table, Granger causality table, one figure.

Usage
-----
    python -m finfluencer.market.run_confirmatory_analysis \\
        --sentiment-path data/processed/sentiment.parquet \\
        --comments-path data/raw/comments.parquet \\
        --market-data-path data/market/market_data.parquet \\
        --output-dir outputs/market

Requires ``data/market/market_data.parquet`` to already exist (built by
``finfluencer.market.collect_market_data`` if network access is
available, or ``finfluencer.market.ingest_manual_bist100`` from a
manually-downloaded file otherwise).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from finfluencer.core.logging import get_logger
from finfluencer.market.confirmatory_analysis import (
    build_analysis_panel,
    descriptive_table,
    granger_table,
    regression_table,
    run_confirmatory_analysis,
)
from finfluencer.market.figures import plot_sentiment_vs_bist100
from finfluencer.market.sentiment_index import build_pooled_sentiment_index
from finfluencer.utils.io import write_csv, write_json

_log = get_logger(__name__)


def main(
    *,
    comments_path: Path = Path("data/raw/comments.parquet"),
    sentiment_path: Path = Path("data/processed/sentiment.parquet"),
    market_data_path: Path = Path("data/market/market_data.parquet"),
    sentiment_index_path: Path = Path("data/processed/market_sentiment/sentiment_index_daily.parquet"),
    output_dir: Path = Path("outputs/market"),
) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    build_pooled_sentiment_index(
        comments_path=comments_path, sentiment_path=sentiment_path,
        market_data_path=market_data_path, output_path=sentiment_index_path,
    )
    panel = build_analysis_panel(
        sentiment_index_path=sentiment_index_path, market_data_path=market_data_path,
    )

    desc = descriptive_table(panel)
    results = run_confirmatory_analysis(panel)
    reg = regression_table(results)
    granger = granger_table(results)

    write_csv(desc, output_dir / "Table1_descriptive_statistics.csv")
    write_csv(reg, output_dir / "Table2_OLS_regression.csv")
    write_csv(granger, output_dir / "Table3_granger_causality.csv")
    write_json(
        {k: v for k, v in results.items() if k != "granger"},
        output_dir / "confirmatory_analysis_summary.json",
    )
    fig_path = plot_sentiment_vs_bist100(
        panel, output_path=output_dir / "Figure_sentiment_vs_bist100.png",
    )

    _log.info(
        "confirmatory_analysis_complete",
        n_obs=results["n_obs"], output_dir=str(output_dir), figure=str(fig_path),
    )
    print(f"n_obs = {results['n_obs']}")
    print("\n--- Table 1: Descriptive statistics ---")
    print(desc.to_string(index=False))
    print("\n--- Table 2: OLS regression (+ correlations) ---")
    print(reg.to_string(index=False))
    print("\n--- Table 3: Granger causality (both directions, lags 1-5) ---")
    print(granger.to_string(index=False))
    print(f"\nFigure saved to {fig_path}")
    return results


def _cli() -> None:
    p = argparse.ArgumentParser(description="Minimal sentiment vs. BIST100 confirmatory analysis.")
    p.add_argument("--comments-path", type=Path, default=Path("data/raw/comments.parquet"))
    p.add_argument("--sentiment-path", type=Path, default=Path("data/processed/sentiment.parquet"))
    p.add_argument("--market-data-path", type=Path, default=Path("data/market/market_data.parquet"))
    p.add_argument("--output-dir", type=Path, default=Path("outputs/market"))
    args = p.parse_args()
    main(
        comments_path=args.comments_path, sentiment_path=args.sentiment_path,
        market_data_path=args.market_data_path, output_dir=args.output_dir,
    )


if __name__ == "__main__":
    _cli()
