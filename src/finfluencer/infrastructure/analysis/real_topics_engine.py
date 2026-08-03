"""RealTopicsAnalysisEngine (Release Blocker #6,
`docs/implementation/RB6_ANALYSIS_DISPATCH_READINESS_REVIEW.md` sections 5.2/5.3): the composite
`IAnalysisEngine` implementation that makes real (non-demo) topic analysis reachable through
`StartAnalysisRun`.

Sequences three already-built, already-tested pieces, none of them modified by this file:
`PreprocessEngineAdapter.ensure_clean()` -> `EmbeddingsEngineAdapter.ensure_index()` -> a freshly
constructed `TopicsAnalysisAdapter.run()`. This is not a new kind of abstraction -- every existing
adapter in this package already internally sequences checkpoint/cache steps behind one
`IAnalysisEngine.run()` call; this class does the same thing one level higher, composing adapters
instead of pipeline stages.

**Why `TopicsAnalysisAdapter` is constructed fresh inside `run()`, not once in `__init__`.** The
Readiness Review found `TopicsAnalysisAdapter.__init__`'s `embeddings_index_path` is a fixed
constructor argument, not re-derived per call the way `comments_path` already is -- built once
with one path, it cannot correctly serve more than one `CollectionRun`. Rather than modify that
adapter's own contract (frozen, already tested, T-019), this class constructs a fresh instance on
every `run()` call, passing the `embeddings_index_path` this call's own
`EmbeddingsEngineAdapter.ensure_index()` step just produced. `TopicsAnalysisAdapter` itself is
untouched -- zero lines changed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from finfluencer.core.contracts import Settings
from finfluencer.domain.analysis_engine import AnalysisOutcome
from finfluencer.infrastructure.analysis.embeddings_adapter import EmbeddingsEngineAdapter
from finfluencer.infrastructure.analysis.preprocess_adapter import PreprocessEngineAdapter
from finfluencer.infrastructure.analysis.topics_adapter import TopicsAnalysisAdapter
from finfluencer.topics.pipeline import RunnerFactory


class RealTopicsAnalysisEngine:
    """Implements `IAnalysisEngine`. `run(analysis_run_id, collection_run_id)` ensures clean text
    and a populated embeddings index exist for `collection_run_id`, then delegates to a real
    `TopicsAnalysisAdapter` for the actual topic assignment -- no shortcuts, no demo output.

    Injectable seams (`preprocess_engine`, `embeddings_engine`, `runner_factory`, `model_loader`)
    exist purely so tests can substitute fakes for the heavy real dependencies
    (`sentence-transformers`/`torch`/`bertopic`), the same discipline every adapter in this
    package already follows -- not new testing infrastructure invented for this class.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        base_root: Path,
        preprocess_engine: PreprocessEngineAdapter | None = None,
        embeddings_engine: EmbeddingsEngineAdapter | None = None,
        runner_factory: RunnerFactory | None = None,
        model_loader: Callable[[Path], Any] | None = None,
    ) -> None:
        self._settings = settings
        self._base_root = Path(base_root)
        self._preprocess_engine = preprocess_engine or PreprocessEngineAdapter(
            settings=settings, base_root=base_root,
        )
        self._embeddings_engine = embeddings_engine or EmbeddingsEngineAdapter(
            settings=settings, base_root=base_root,
        )
        self._runner_factory = runner_factory
        self._model_loader = model_loader

    def run(self, analysis_run_id: str, collection_run_id: str) -> AnalysisOutcome:
        if not analysis_run_id or not analysis_run_id.strip():
            raise ValueError("analysis_run_id must be non-empty")
        if not collection_run_id or not collection_run_id.strip():
            raise ValueError("collection_run_id must be non-empty")

        self._preprocess_engine.ensure_clean(collection_run_id)
        embeddings_outcome = self._embeddings_engine.ensure_index(collection_run_id)

        topics_engine = TopicsAnalysisAdapter(
            settings=self._settings,
            base_root=self._base_root,
            embeddings_index_path=embeddings_outcome.index_path,
            runner_factory=self._runner_factory,
            model_loader=self._model_loader,
        )
        return topics_engine.run(analysis_run_id, collection_run_id)


__all__ = ["RealTopicsAnalysisEngine"]
