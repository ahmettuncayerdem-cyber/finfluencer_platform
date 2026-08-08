"""ChartRendererAdapter (BACKLOG.md EPIC-10): Infrastructure implementation of
`finfluencer.domain.reporting_engine.IChartRenderer`, reusing `reporting.master_table.
build_master_table` unmodified -- the same reuse target `MasterTableExportAdapter` (T-026)
already established, and for the identical reason: this is the one function in the codebase that
already joins `comments.parquet`/`topics.parquet`/`sentiment.parquet` into the row shape a chart
needs (`topic_label_pooled`, `sentiment_class`, etc.), already tested
(`tests/unit/test_reporting/test_master_table.py`).

Resolves `topics_path`/`sentiment_path`/`comments_path` via the identical filesystem convention
`MasterTableExportAdapter`/`ResultSnapshotAdapter` already use -- accepted here as the same kind
of small, independent duplication those two adapters' own docstrings already justify (not yet a
pattern worth extracting a shared base class for).

Two chart types in v1, matching `PRODUCT_ARCHITECTURE.md` section 3.1's exact naming
("Topic/Sentiment Visualization"):
- `"topics"`: bar chart of comment counts per `topic_label_pooled` (the cross-analyst BERTopic
  configuration -- the one `MasterTableExportAdapter`'s own docstring notes is the default join
  granularity most callers want).
- `"sentiment"`: bar chart of comment counts per `sentiment_class`.

Both read `output.figures` from `Settings` when given (`dpi`, `colourblind_safe`) -- same
opt-in-via-`settings=None` convention `MasterTableExportAdapter` established for its own
provenance columns, so behavior with `settings=None` is deterministic and does not depend on
`config/settings.yaml` being loadable in a test context that doesn't need it.

Uses `matplotlib` only (already a `pyproject.toml` dependency, per the EPIC-10 readiness audit)
-- no new dependency introduced. The Okabe-Ito colourblind-safe palette matches
`market/figures.py`'s own existing use of the same palette for visual consistency across any
figures this platform produces, without importing that (legacy, single-purpose, pre-six-layer)
module itself.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: this adapter runs inside a request handler, never a GUI.

import matplotlib.pyplot as plt

from finfluencer.core.contracts import Settings
from finfluencer.core.exceptions import DataError
from finfluencer.reporting.master_table import build_master_table

#: Result filenames this adapter knows how to resolve, by presence -- mirrors
#: `MasterTableExportAdapter`'s own `_TOPICS_FILENAME`/`_SENTIMENT_FILENAME` (T-026).
_TOPICS_FILENAME = "topics.parquet"
_SENTIMENT_FILENAME = "sentiment.parquet"

#: Okabe-Ito colourblind-safe palette, matching `market/figures.py`'s existing choice.
_PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#F0E442", "#56B4E9", "#E69F00", "#000000"]

_SUPPORTED_CHART_TYPES = ("topics", "sentiment")


class ChartRendererAdapter:
    """Implements `IChartRenderer` (`finfluencer.domain.reporting_engine`)."""

    def __init__(self, *, base_root: Path, settings: Settings | None = None) -> None:
        self._base_root = Path(base_root)
        self._settings = settings

    def _resolve_topics_and_sentiment_paths(
        self, analysis_run_ids: list[str],
    ) -> tuple[Path | None, Path | None]:
        # Identical resolution logic to `MasterTableExportAdapter._resolve_topics_and_
        # sentiment_paths` -- duplicated, not imported, per this module's own docstring
        # (small, independent duplication, same call T-026 already made for the same reason).
        topics_path: Path | None = None
        sentiment_path: Path | None = None
        for run_id in analysis_run_ids:
            data_processed = self._base_root / run_id / "data_processed"
            candidate_topics = data_processed / _TOPICS_FILENAME
            candidate_sentiment = data_processed / _SENTIMENT_FILENAME
            if candidate_topics.exists():
                topics_path = candidate_topics
            if candidate_sentiment.exists():
                sentiment_path = candidate_sentiment
        return topics_path, sentiment_path

    def render(
        self,
        collection_run_id: str,
        analysis_run_ids: list[str],
        chart_type: str,
        output_path: str,
    ) -> int:
        if not collection_run_id or not collection_run_id.strip():
            raise ValueError("collection_run_id must be non-empty")
        if not analysis_run_ids:
            raise ValueError("analysis_run_ids must be non-empty")
        if chart_type not in _SUPPORTED_CHART_TYPES:
            raise ValueError(
                f"chart_type={chart_type!r} is not supported -- must be one of "
                f"{_SUPPORTED_CHART_TYPES}."
            )

        comments_path = self._base_root / collection_run_id / "data_raw" / "comments.parquet"
        topics_path, sentiment_path = self._resolve_topics_and_sentiment_paths(analysis_run_ids)

        # build_master_table() requires all three source tables; a chart conceptually only
        # needs the one relevant to chart_type, but reusing the exact same tested join (rather
        # than a second, narrower data path) is deliberate -- see module docstring's reuse
        # rationale. This does mean both a topics- and a sentiment-shaped AnalysisRun must be
        # cited for either chart to render, the same documented limitation
        # `MasterTableExportAdapter`/`/table` already carries (T-026's own "Known technical
        # debt"), surfaced identically here rather than solved differently for charts alone.
        if topics_path is None or sentiment_path is None:
            raise FileNotFoundError(
                f"Could not resolve both a topics.parquet and a sentiment.parquet among "
                f"analysis_run_ids={analysis_run_ids!r} under {self._base_root} -- chart "
                f"rendering reuses build_master_table(), which requires both (found "
                f"topics={topics_path}, sentiment={sentiment_path})."
            )

        master_df = build_master_table(
            comments_path=comments_path, topics_path=topics_path, sentiment_path=sentiment_path,
        )

        dpi = 300
        if self._settings is not None:
            dpi = self._settings.output.figures.dpi

        if chart_type == "topics":
            counts = master_df["topic_label_pooled"].value_counts().sort_values(ascending=False)
            title = "Comment Count by Topic"
            xlabel = "Topic"
        else:
            counts = master_df["sentiment_class"].value_counts().sort_values(ascending=False)
            title = "Comment Count by Sentiment"
            xlabel = "Sentiment"

        if counts.empty:
            raise DataError(
                f"No non-null {chart_type} values found among analysis_run_ids="
                f"{analysis_run_ids!r} -- nothing to chart."
            )

        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.bar(
            counts.index.astype(str), counts.values,
            color=[_PALETTE[i % len(_PALETTE)] for i in range(len(counts))],
        )
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Comment count")
        fig.autofmt_xdate(rotation=30)
        fig.tight_layout()

        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path_obj, dpi=dpi)
        plt.close(fig)

        return output_path_obj.stat().st_size


__all__ = ["ChartRendererAdapter"]
