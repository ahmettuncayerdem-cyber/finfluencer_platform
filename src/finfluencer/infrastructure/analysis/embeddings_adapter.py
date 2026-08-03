"""EmbeddingsEngineAdapter (Release Blocker #4, RELEASE_BLOCKING_ASSESSMENT.md item #4):
Infrastructure wrapper around the existing, tested `finfluencer.embeddings.pipeline.run_embeddings`
and `finfluencer.embeddings.sentence_transformer.SentenceTransformerProvider`, unmodified.

`IMPLEMENTATION_ROADMAP.md` section 3 already classifies `embeddings/` under the same
"Analysis Engine -- topic modeling and sentiment" reuse row as `topics/`/`sentiment/`, "Wrapper
required" -- this is not a new reuse decision. Mirrors `TopicsAnalysisAdapter`/
`SentimentAnalysisAdapter`'s own shape (T-019/T-022) as closely as the legacy signature allows.

Does **not** implement `finfluencer.domain.analysis_engine.IAnalysisEngine` -- see the class
docstring below for why this is a deliberate non-reuse of that Protocol, not an omission.

Constraint, same as every prior adapter in this package: this module must never modify
`finfluencer.embeddings.*` -- it only imports and calls it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import Settings
from finfluencer.embeddings.base import EmbeddingProvider
from finfluencer.embeddings.pipeline import run_embeddings
from finfluencer.embeddings.sentence_transformer import SentenceTransformerProvider


@dataclass(frozen=True)
class EmbeddingsOutcome:
    """Local return shape -- not a Domain type (see class docstring for why no `IEmbeddingsEngine`
    Domain port exists). Small and non-speculative: `index_path` is what
    `TopicsAnalysisAdapter(embeddings_index_path=...)` needs directly; `row_count` is for
    logging/verification, mirroring the observability `CollectionOutcome`/`AnalysisOutcome`
    already provide for their own adapters.
    """

    index_path: Path
    row_count: int


class EmbeddingsEngineAdapter:
    """Produces `embeddings_index.parquet` from a `CollectionRun`'s own `comments.parquet`, ready
    for `TopicsAnalysisAdapter(embeddings_index_path=...)` to consume.

    **Why this does not implement `IAnalysisEngine`.** That Protocol's `run(analysis_run_id,
    collection_run_id) -> AnalysisOutcome` shape models a full, independently-dispatchable
    `AnalysisRun` (`PRODUCT_ARCHITECTURE.md` section 10.1) -- topics and sentiment are each their
    own named `AnalysisType`, each producing their own citable result. Embeddings are neither: no
    `AnalysisType` named "embeddings" exists or is proposed, `embeddings_index.parquet` is never
    itself cited by a `Report` (only `topics.parquet`/`sentiment.parquet` are, per T-025/T-026),
    and section 11.2 names no `StartEmbeddings`-shaped command. Modeling this as an
    `IAnalysisEngine` would be exactly the kind of speculative interface the operator's own
    instruction forbids -- reusing a Protocol because its method signature happens to fit, not
    because the concept it represents fits. This adapter therefore exposes one plain method,
    `ensure_index()`, called directly by whichever future caller (a bootstrap.py wiring, or a
    `TopicsAnalysisAdapter` construction step) needs an `embeddings_index_path` before running
    real topic analysis -- no Domain port, no repository, no new abstraction beyond this one class.

    **Why isolation is per-`collection_run_id`, not per-`analysis_run_id`.** Unlike
    `TopicsAnalysisAdapter`/`SentimentAnalysisAdapter` (each `analysis_run_id` gets its own,
    never-shared checkpoint/cache/output subtree), embeddings are a property of the *collected
    comments themselves*, not of any one analysis attempt against them -- `run_embeddings()`'s own
    cache-first design exists precisely so the same text is never re-embedded across multiple
    topic-analysis attempts over the same `CollectionRun`. Partitioning by `analysis_run_id` here
    would silently defeat that caching and recompute embeddings on every retry. This is a
    deliberate divergence from the sibling adapters' own pattern, not an inconsistency.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        base_root: Path,
        provider: EmbeddingProvider | None = None,
        provider_factory: Callable[[], EmbeddingProvider] | None = None,
    ) -> None:
        self._settings = settings
        self._base_root = Path(base_root)
        self._provider = provider
        self._provider_factory = (
            provider_factory if provider_factory is not None else self._default_provider_factory
        )

    def _default_provider_factory(self) -> EmbeddingProvider:
        # TopicsConfig.embedding_model (T-019's own frozen contract) is the only settings field
        # naming an embedding model today -- embeddings exist to feed topic analysis, per
        # IMPLEMENTATION_ROADMAP.md section 3's own grouping, so reusing it here (rather than
        # inventing a new, separate settings field) is a wrapper decision, not a new one.
        model_ref = self._settings.topics.embedding_model
        return SentenceTransformerProvider(model_ref.name, revision=model_ref.revision)

    def _resolve_provider(self) -> EmbeddingProvider:
        return self._provider if self._provider is not None else self._provider_factory()

    def _paths_for(self, collection_run_id: str) -> tuple[Path, Path, Path, Path]:
        """Derive this `CollectionRun`'s isolated `(comments_path, checkpoint_root, cache_root,
        output_path)`. `comments_path` reuses T-010's existing directory convention verbatim,
        same as `TopicsAnalysisAdapter`/`SentimentAnalysisAdapter`. All embeddings artifacts for
        one `collection_run_id` live under that same run's own subtree, alongside (not colliding
        with) any `analysis_run_id` subtrees a topics/sentiment adapter creates there.
        """
        comments_path = self._base_root / collection_run_id / "data_raw" / "comments.parquet"
        embeddings_root = self._base_root / collection_run_id / "embeddings"
        return (
            comments_path,
            embeddings_root / "checkpoints",
            embeddings_root / "cache",
            embeddings_root / "embeddings_index.parquet",
        )

    def ensure_index(self, collection_run_id: str) -> EmbeddingsOutcome:
        """Idempotent: relies on `run_embeddings()`'s own Tier-2/Tier-3 checkpoint-and-cache
        discipline, unmodified -- a second call for the same `collection_run_id` re-derives the
        same paths and re-hits the same cache, never re-embedding already-cached text.
        """
        if not collection_run_id or not collection_run_id.strip():
            raise ValueError("collection_run_id must be non-empty")

        comments_path, checkpoint_root, cache_root, output_path = self._paths_for(
            collection_run_id,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint = CheckpointManager(checkpoint_root=checkpoint_root, cache_root=cache_root)
        provider = self._resolve_provider()

        index_df = run_embeddings(
            self._settings,
            comments_path,
            checkpoint,
            provider=provider,
            output_path=output_path,
        )

        return EmbeddingsOutcome(index_path=output_path, row_count=len(index_df))


__all__ = ["EmbeddingsEngineAdapter", "EmbeddingsOutcome"]
