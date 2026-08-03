"""Analysis Engine Infrastructure adapters (BACKLOG.md T-019, T-022; Release Blocker #4).

Two concrete `finfluencer.domain.analysis_engine.IAnalysisEngine` implementations, each wrapping
an existing, tested legacy pipeline unmodified, per IMPLEMENTATION_ROADMAP.md section 3's
"Wrapper required" classification for the Analysis Engine:
- `TopicsAnalysisAdapter` wraps `finfluencer.topics.pipeline.run_topics` (T-019).
- `SentimentAnalysisAdapter` wraps `finfluencer.sentiment.pipeline.run_sentiment` (T-022) --
  added specifically to prove this plugin pattern generalizes beyond the one implementation it
  was built against.

Plus one non-`IAnalysisEngine` adapter, `EmbeddingsEngineAdapter`, wrapping
`finfluencer.embeddings.pipeline.run_embeddings` unmodified (Release Blocker #4,
`RELEASE_BLOCKING_ASSESSMENT.md` item #4) -- produces the `embeddings_index_path`
`TopicsAnalysisAdapter` requires as a caller-supplied input. See its own class docstring for why
it deliberately does not implement `IAnalysisEngine`.

See `CONTEXT_PACK.md` (topics + embeddings) and `CONTEXT_PACK_SENTIMENT.md` (sentiment, T-022) in
this directory (IMPLEMENTATION_PLAYBOOK.md Part B.2).
"""

from __future__ import annotations

from finfluencer.infrastructure.analysis.embeddings_adapter import (
    EmbeddingsEngineAdapter,
    EmbeddingsOutcome,
)
from finfluencer.infrastructure.analysis.sentiment_adapter import SentimentAnalysisAdapter
from finfluencer.infrastructure.analysis.topics_adapter import TopicsAnalysisAdapter

__all__ = [
    "EmbeddingsEngineAdapter",
    "EmbeddingsOutcome",
    "SentimentAnalysisAdapter",
    "TopicsAnalysisAdapter",
]
