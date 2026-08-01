"""TopicsAnalysisAdapter (BACKLOG.md T-019): Infrastructure implementation of
`finfluencer.domain.analysis_engine.IAnalysisEngine`, wrapping the existing, tested
`finfluencer.topics.pipeline.run_topics` (and `BERTopicRunner`) unmodified.

Mirrors `infrastructure.collection.CollectionEngineAdapter`'s (T-010) own shape: a thin adapter
that derives an isolated `(checkpoint_root, cache_root, output_path)` triple per run id (here,
`analysis_run_id`) and calls straight into the legacy, already-tested pipeline function.

Constraint, same as T-010's own: this module must never modify `finfluencer.topics.*` -- it only
imports and calls it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import Settings
from finfluencer.domain.analysis_engine import AnalysisOutcome
from finfluencer.topics.bertopic_runner import BERTopicRunner
from finfluencer.topics.pipeline import RunnerFactory, run_topics


class TopicsAnalysisAdapter:
    """Implements `IAnalysisEngine` (`finfluencer.domain.analysis_engine`).

    `embeddings_index_path` is a required, caller-supplied input, not derived by this adapter --
    `run_topics()` already requires it as a parameter, and no task in this backlog wraps
    `finfluencer.embeddings.pipeline` yet (T-019's Readiness Review, Assumption 1). Wrapping the
    embeddings stage is a separate, not-yet-ticketed concern, not invented here.

    `comments_path` is resolved from `base_root / collection_run_id / "data_raw" /
    "comments.parquet"` -- reusing, not inventing, the directory partitioning
    `CollectionEngineAdapter` (T-010) already established for exactly this data.

    Analysis-side checkpoint/cache/output artifacts are isolated per `analysis_run_id` under
    their own subtree of `base_root`, mirroring ADR-0002's per-`run_id` partitioning discipline
    (Roadmap Risk R-1) applied to Analysis instead of Collection.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        base_root: Path,
        embeddings_index_path: Path,
        runner_factory: RunnerFactory | None = None,
        model_loader: Callable[[Path], Any] | None = None,
    ) -> None:
        self._settings = settings
        self._base_root = Path(base_root)
        self._embeddings_index_path = Path(embeddings_index_path)
        self._runner_factory = runner_factory
        self._model_loader = model_loader if model_loader is not None else BERTopicRunner.load_model

    def _paths_for(self, analysis_run_id: str, collection_run_id: str) -> tuple[Path, Path, Path, Path]:
        """Derive this run's isolated `(comments_path, checkpoint_root, cache_root,
        output_path)`. `comments_path` comes from the pinned `collection_run_id`'s own
        subtree (T-010's existing convention); the rest are freshly partitioned per
        `analysis_run_id`, never shared with any other analysis run.
        """
        comments_path = self._base_root / collection_run_id / "data_raw" / "comments.parquet"
        analysis_root = self._base_root / analysis_run_id
        return (
            comments_path,
            analysis_root / "checkpoints",
            analysis_root / "cache",
            analysis_root / "data_processed" / "topics.parquet",
        )

    def run(self, analysis_run_id: str, collection_run_id: str) -> AnalysisOutcome:
        if not analysis_run_id or not analysis_run_id.strip():
            raise ValueError("analysis_run_id must be non-empty")
        if not collection_run_id or not collection_run_id.strip():
            raise ValueError("collection_run_id must be non-empty")

        comments_path, checkpoint_root, cache_root, output_path = self._paths_for(
            analysis_run_id, collection_run_id,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint = CheckpointManager(checkpoint_root=checkpoint_root, cache_root=cache_root)

        topics_df = run_topics(
            self._settings,
            comments_path,
            self._embeddings_index_path,
            checkpoint,
            output_path=output_path,
            runner_factory=self._runner_factory,
            model_loader=self._model_loader,
        )

        distinct_topics = topics_df["topic_id"].nunique() if not topics_df.empty else 0
        return AnalysisOutcome(
            analysis_run_id=analysis_run_id,
            row_count=len(topics_df),
            topic_count=int(distinct_topics),
        )


__all__ = ["TopicsAnalysisAdapter"]
