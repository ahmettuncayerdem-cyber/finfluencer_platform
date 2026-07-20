"""
finfluencer.market.figures
=============================

The single required figure for the minimal confirmatory market-
integration analysis: pooled sentiment index and BIST100 level over
time, twin y-axes, 300dpi. Matches the Okabe-Ito colourblind-safe
palette and typography already used for Figures 1-3 in the main
manuscript (``outputs/manuscript/figures/``) for visual consistency
across the paper.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from finfluencer.core.exceptions import DataError
from finfluencer.core.logging import get_logger

_log = get_logger(__name__)

# Okabe-Ito palette (colourblind-safe), matching the main manuscript figures.
_COLOR_SENTIMENT = "#0072B2"  # blue
_COLOR_MARKET = "#D55E00"     # vermillion


def plot_sentiment_vs_bist100(
    panel: pd.DataFrame,
    *,
    output_path: Path = Path("outputs/manuscript/figures/Figure_market_sentiment_vs_bist100.png"),
    dpi: int = 300,
) -> Path:
    """Twin-axis time series: pooled sentiment index (left) vs. BIST100
    close (right), both against trading-day date on the x-axis.

    ``panel`` must be the output of
    ``confirmatory_analysis.build_analysis_panel`` (columns: date,
    sentiment_index, xu100_close, xu100_return). Raises if empty.
    """
    if panel.empty:
        raise DataError("Cannot plot an empty analysis panel")
    required = {"date", "sentiment_index", "xu100_close"}
    missing = required - set(panel.columns)
    if missing:
        raise DataError(f"panel missing required columns: {sorted(missing)}", missing=sorted(missing))

    panel = panel.sort_values("date")

    fig, ax1 = plt.subplots(figsize=(9, 4.5))
    ax1.plot(panel["date"], panel["sentiment_index"], color=_COLOR_SENTIMENT,
             linewidth=1.3, label="Pooled sentiment index")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Pooled sentiment index (P(positive))", color=_COLOR_SENTIMENT)
    ax1.tick_params(axis="y", labelcolor=_COLOR_SENTIMENT)
    ax1.set_ylim(0, 1)

    ax2 = ax1.twinx()
    ax2.plot(panel["date"], panel["xu100_close"], color=_COLOR_MARKET,
              linewidth=1.3, label="BIST100 close")
    ax2.set_ylabel("BIST100 close", color=_COLOR_MARKET)
    ax2.tick_params(axis="y", labelcolor=_COLOR_MARKET)

    fig.autofmt_xdate()
    ax1.set_title("Pooled Sentiment Index and BIST100 Close, 2025")
    fig.tight_layout()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)
    _log.info("market_sentiment_figure_saved", path=str(output_path), n_points=len(panel))
    return output_path


__all__ = ["plot_sentiment_vs_bist100"]
