"""RealSentimentAnalysisEngine (Release Blocker #6,
`docs/implementation/RB6_ANALYSIS_DISPATCH_READINESS_REVIEW.md` sections 5.2/5.3): the composite
`IAnalysisEngine` implementation that makes real (non-demo) sentiment analysis reachable through
`StartAnalysisRun`.

Sequences two already-built, already-tested pieces, neither modified by this file:
`PreprocessEngineAdapter.ensure_clean()` -> `SentimentAnalysisAdapter.run()`. Simpler than
`RealTopicsAnalysisEngine`'s three-step chain because sentiment analysis has no embeddings
dependency -- `sentiment.pipeline.run_sentiment()` only ever needed `text_clean`.

**Why `SentimentAnalysisAdapter` is constructed once in `__init__`, unlike
`RealTopicsAnalysisEngine`'s per-call `TopicsAnalysisAdapter`.** `SentimentAnalysisAdapter`
already derives `comments_path` fresh from `collection_run_id` inside its own `run()` (unlike
`TopicsAnalysisAdapter`'s fixed `embeddings_index_path`) -- it has no equivalent staleness problem,
so one shared instance safely serves any number of `collection_run_id`s. Constructing it once
avoids unnecessary re-construction, not a stylistic inconsistency with the topics engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from finfluencer.core.contracts import Settings
from finfluencer.domain.analysis_engine import AnalysisOutcome
from finfluencer.infrastructure.analysis.preprocess_adapter import PreprocessEngineAdapter
from finfluencer.infrastructure.analysis.sentiment_adapter import SentimentAnalysisAdapter
from finfluencer.sentiment.base import SentimentProvider


class RealSentimentAnalysisEngine:
    """Implements `IAnalysisEngine`. `run(analysis_run_id, collection_run_id)` ensures clean text
    exists for `collection_run_id`, then delegates to a real `SentimentAnalysisAdapter` -- no
    shortcuts, no demo output.

    Injectable seams (`preprocess_engine`, `provider`, `provider_factory`) exist purely so tests
    can substitute fakes for the heavy real dependency (`transformers`/`torch`), the same
    discipline every adapter in this package already follows.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        base_root: Path,
        preprocess_engine: PreprocessEngineAdapter | None = None,
        provider: SentimentProvider | None = None,
        provider_factory: Callable[[], SentimentProvider] | None = None,
    ) -> None:
        self._preprocess_engine = preprocess_engine or PreprocessEngineAdapter(
            settings=settings, base_root=base_root,
        )
        self._sentiment_engine = SentimentAnalysisAdapter(
            settings=settings,
            base_root=base_root,
            provider=provider,
            provider_factory=provider_factory,
        )

    def run(self, analysis_run_id: str, collection_run_id: str) -> AnalysisOutcome:
        if not analysis_run_id or not analysis_run_id.strip():
            raise ValueError("analysis_run_id must be non-empty")
        if not collection_run_id or not collection_run_id.strip():
            raise ValueError("collection_run_id must be non-empty")

        self._preprocess_engine.ensure_clean(collection_run_id)
        return self._sentiment_engine.run(analysis_run_id, collection_run_id)


__all__ = ["RealSentimentAnalysisEngine"]
