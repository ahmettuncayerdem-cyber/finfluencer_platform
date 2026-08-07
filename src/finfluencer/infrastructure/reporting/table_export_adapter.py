"""MasterTableExportAdapter (BACKLOG.md T-026): Infrastructure implementation of
`finfluencer.domain.reporting_engine.ITableExporter`, wrapping the existing, tested
`finfluencer.reporting.master_table.build_master_table`/`save_master_table` unmodified.

Resolves `comments_path` via the same T-010 directory convention every other adapter in this
package reuses (`base_root/collection_run_id/data_raw/comments.parquet`). Resolves
`topics_path`/`sentiment_path` by presence among the given `analysis_run_ids`, the same
convention `ResultSnapshotAdapter` (T-025) already established -- accepted here as a small,
independent duplication rather than extracting a shared base class prematurely (T-025's own
Context Pack made the identical call for the same reason: two adapters, not yet a pattern worth
generalizing).

Constraint, same as every prior adapter: this module must never modify `finfluencer.reporting.*`
-- it only imports and calls it.

**Provenance columns (V1.0 Research Readiness freeze, 2026-08-07).** `settings` is now an
optional constructor argument. When given, this adapter also records which `analysis_run_id`
resolved each of `topics.parquet`/`sentiment.parquet`, plus the currently-configured model
name/revision for each (`settings.topics.embedding_model`, `settings.sentiment.primary_model`),
as extra columns on every exported row -- see `master_table.build_master_table`'s own docstring
for the exact column names. This reflects the model **currently configured**, not a historical
per-run catalog (no `AnalysisType` catalog/repository exists anywhere in this codebase to resolve
an old run to whatever model produced it *then*, if the config has since changed -- a real,
separate, larger gap, not solved by this pass). `settings=None` (the default) preserves the
adapter's exact prior behavior with zero new columns, so no existing caller is affected.
"""

from __future__ import annotations

from pathlib import Path

from finfluencer.core.contracts import Settings
from finfluencer.reporting.master_table import build_master_table, save_master_table

#: Result filenames this adapter knows how to resolve, by presence -- mirrors
#: `infrastructure.reporting.snapshot_adapter._KNOWN_OUTPUT_FILENAMES` (T-025).
_TOPICS_FILENAME = "topics.parquet"
_SENTIMENT_FILENAME = "sentiment.parquet"


class MasterTableExportAdapter:
    """Implements `ITableExporter` (`finfluencer.domain.reporting_engine`)."""

    def __init__(self, *, base_root: Path, settings: Settings | None = None) -> None:
        self._base_root = Path(base_root)
        self._settings = settings

    def _resolve_topics_and_sentiment_paths(
        self, analysis_run_ids: list[str],
    ) -> tuple[Path, str | None, Path, str | None]:
        topics_path: Path | None = None
        topics_run_id: str | None = None
        sentiment_path: Path | None = None
        sentiment_run_id: str | None = None
        for run_id in analysis_run_ids:
            data_processed = self._base_root / run_id / "data_processed"
            candidate_topics = data_processed / _TOPICS_FILENAME
            candidate_sentiment = data_processed / _SENTIMENT_FILENAME
            if candidate_topics.exists():
                topics_path = candidate_topics
                topics_run_id = run_id
            if candidate_sentiment.exists():
                sentiment_path = candidate_sentiment
                sentiment_run_id = run_id

        if topics_path is None or sentiment_path is None:
            raise FileNotFoundError(
                f"Could not resolve both a topics.parquet and a sentiment.parquet among "
                f"analysis_run_ids={analysis_run_ids!r} under {self._base_root} -- "
                f"build_master_table() requires both (found topics={topics_path}, "
                f"sentiment={sentiment_path})."
            )
        return topics_path, topics_run_id, sentiment_path, sentiment_run_id

    def export(
        self, collection_run_id: str, analysis_run_ids: list[str], output_path: str,
    ) -> int:
        if not collection_run_id or not collection_run_id.strip():
            raise ValueError("collection_run_id must be non-empty")
        if not analysis_run_ids:
            raise ValueError("analysis_run_ids must be non-empty")

        comments_path = self._base_root / collection_run_id / "data_raw" / "comments.parquet"
        topics_path, topics_run_id, sentiment_path, sentiment_run_id = (
            self._resolve_topics_and_sentiment_paths(analysis_run_ids)
        )

        # `settings` is the single opt-in switch for the whole provenance-column feature (not
        # per-field): `settings=None` must reproduce the adapter's exact prior column set, so
        # the resolved run_ids are only forwarded when settings was also given, even though they
        # are technically available either way.
        provenance_kwargs: dict[str, str | None] = {}
        if self._settings is not None:
            provenance_kwargs = {
                "topics_analysis_run_id": topics_run_id,
                "topics_model_name": self._settings.topics.embedding_model.name,
                "topics_model_revision": self._settings.topics.embedding_model.revision,
                "sentiment_analysis_run_id": sentiment_run_id,
                "sentiment_model_name": self._settings.sentiment.primary_model.name,
                "sentiment_model_revision": self._settings.sentiment.primary_model.revision,
            }

        master_df = build_master_table(
            comments_path=comments_path,
            topics_path=topics_path,
            sentiment_path=sentiment_path,
            **provenance_kwargs,
        )
        save_master_table(master_df, output_path=Path(output_path))
        return len(master_df)


__all__ = ["MasterTableExportAdapter"]
