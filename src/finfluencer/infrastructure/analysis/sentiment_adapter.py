"""SentimentAnalysisAdapter (BACKLOG.md T-022): Infrastructure implementation of
`finfluencer.domain.analysis_engine.IAnalysisEngine`, wrapping the existing, tested
`finfluencer.sentiment.pipeline.run_sentiment` unmodified.

Second concrete `IAnalysisEngine` implementation, added specifically to prove the plugin
pattern generalizes beyond `TopicsAnalysisAdapter` (T-019) -- not a one-off built for sentiment
specifically. Mirrors `TopicsAnalysisAdapter`'s shape as closely as the two legacy pipelines'
actual signatures allow: derives an isolated `(checkpoint_root, cache_root, output_path)` triple
per run id (`analysis_run_id`), resolves `comments_path` via the same T-010 directory convention,
and calls straight into the legacy, already-tested pipeline function.

Constraint, same as T-019's own: this module must never modify `finfluencer.sentiment.*` -- it
only imports and calls it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import Settings
from finfluencer.domain.analysis_engine import AnalysisOutcome
from finfluencer.sentiment.base import SentimentProvider
from finfluencer.sentiment.pipeline import run_sentiment
from finfluencer.sentiment.transformer_classifier import TransformerSentimentClassifier


class SentimentAnalysisAdapter:
    """Implements `IAnalysisEngine` (`finfluencer.domain.analysis_engine`).

    `comments_path` is resolved from `base_root / collection_run_id / "data_raw" /
    "comments.parquet"` -- the same T-010 convention `TopicsAnalysisAdapter` already reuses, not
    a new resolution mechanism invented here.

    Unlike `TopicsAnalysisAdapter`'s `embeddings_index_path` (a required constructor argument),
    `run_sentiment()` needs no caller-supplied artifact beyond `comments_path` itself -- there is
    nothing analogous to wrap or flag here.

    The `SentimentProvider` this adapter runs against is resolved lazily, once per `run()` call,
    never eagerly at construction time -- same discipline `TopicsAnalysisAdapter` already applies
    to `model_loader`/`runner_factory` (heavy-dependency imports stay deferred until an analysis
    actually executes; `transformer_classifier.py`'s own module docstring establishes this same
    rule for `transformers`/`torch`). Tests inject a `provider` directly; production callers may
    supply one explicitly or let this adapter construct the default `TransformerSentimentClassifier`
    from `settings.sentiment.primary_model`.

    Analysis-side checkpoint/cache/output artifacts are isolated per `analysis_run_id` under their
    own subtree of `base_root`, mirroring ADR-0002's per-`run_id` partitioning discipline (Roadmap
    Risk R-1), same as `TopicsAnalysisAdapter` already does.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        base_root: Path,
        provider: SentimentProvider | None = None,
        provider_factory: Callable[[], SentimentProvider] | None = None,
    ) -> None:
        self._settings = settings
        self._base_root = Path(base_root)
        self._provider = provider
        self._provider_factory = (
            provider_factory if provider_factory is not None else self._default_provider_factory
        )

    def _default_provider_factory(self) -> SentimentProvider:
        model_ref = self._settings.sentiment.primary_model
        return TransformerSentimentClassifier(model_name=model_ref.name, revision=model_ref.revision)

    def _resolve_provider(self) -> SentimentProvider:
        return self._provider if self._provider is not None else self._provider_factory()

    def _paths_for(self, analysis_run_id: str, collection_run_id: str) -> tuple[Path, Path, Path, Path]:
        """Derive this run's isolated `(comments_path, checkpoint_root, cache_root,
        output_path)`. `comments_path` comes from the pinned `collection_run_id`'s own subtree
        (T-010's existing convention, reused verbatim from `TopicsAnalysisAdapter`); the rest are
        freshly partitioned per `analysis_run_id`, never shared with any other analysis run --
        including a `TopicsAnalysisAdapter` run against the same `collection_run_id`, since each
        `analysis_run_id` is itself already globally unique per T-018's `AnalysisRun` entity.
        """
        comments_path = self._base_root / collection_run_id / "data_raw" / "comments.parquet"
        analysis_root = self._base_root / analysis_run_id
        return (
            comments_path,
            analysis_root / "checkpoints",
            analysis_root / "cache",
            analysis_root / "data_processed" / "sentiment.parquet",
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
        provider = self._resolve_provider()

        sentiment_df = run_sentiment(
            self._settings,
            comments_path,
            checkpoint,
            provider=provider,
            output_path=output_path,
        )

        # `AnalysisOutcome.topic_count` is a topic-modeling-named field reused here, not renamed
        # (IAnalysisEngine/AnalysisOutcome are frozen T-019 contracts -- out of this task's
        # scope). For sentiment, populated as the count of distinct `sentiment_class` values
        # produced (0, 1, or 2) -- the same "nunique() of the categorical output column" shape
        # `TopicsAnalysisAdapter` already uses for `topic_id`, applied to `sentiment_class`
        # instead. This naming fit (a topic-specific field name reused for a non-topic
        # AnalysisType) is flagged explicitly for T-023's own generalization review, not silently
        # resolved -- see CONTEXT_PACK_SENTIMENT.md's Gotchas section.
        distinct_classes = (
            sentiment_df["sentiment_class"].nunique() if not sentiment_df.empty else 0
        )
        return AnalysisOutcome(
            analysis_run_id=analysis_run_id,
            row_count=len(sentiment_df),
            topic_count=int(distinct_classes),
        )


__all__ = ["SentimentAnalysisAdapter"]
