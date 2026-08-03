"""Analysis Engine Infrastructure adapters (BACKLOG.md T-019, T-022; Release Blocker #4;
Release Blocker #6).

Two concrete `finfluencer.domain.analysis_engine.IAnalysisEngine` implementations, each wrapping
an existing, tested legacy pipeline unmodified, per IMPLEMENTATION_ROADMAP.md section 3's
"Wrapper required" classification for the Analysis Engine:
- `TopicsAnalysisAdapter` wraps `finfluencer.topics.pipeline.run_topics` (T-019).
- `SentimentAnalysisAdapter` wraps `finfluencer.sentiment.pipeline.run_sentiment` (T-022) --
  added specifically to prove this plugin pattern generalizes beyond the one implementation it
  was built against.

Plus two non-`IAnalysisEngine` adapters, each producing a prerequisite input the two engines
above need, not a citable analysis result of its own -- see each one's own class docstring for
why it deliberately does not implement `IAnalysisEngine`:
- `EmbeddingsEngineAdapter` wraps `finfluencer.embeddings.pipeline.run_embeddings` unmodified
  (Release Blocker #4, `RELEASE_BLOCKING_ASSESSMENT.md` item #4) -- produces the
  `embeddings_index_path` `TopicsAnalysisAdapter` requires as a caller-supplied input.
- `PreprocessEngineAdapter` wraps `finfluencer.preprocess.pipeline.run_preprocessing` unmodified
  (Release Blocker #6) -- populates `comments.parquet`'s `text_clean` column both real engines
  require, in place.

Plus two composite `IAnalysisEngine` implementations (Release Blocker #6,
`RB6_ANALYSIS_DISPATCH_READINESS_REVIEW.md`) that sequence the above into the real (non-demo)
analysis paths `StartAnalysisRun` can dispatch to:
- `RealTopicsAnalysisEngine`: preprocess -> embeddings -> topics.
- `RealSentimentAnalysisEngine`: preprocess -> sentiment.

See `CONTEXT_PACK.md` (topics + embeddings) and `CONTEXT_PACK_SENTIMENT.md` (sentiment, T-022) in
this directory (IMPLEMENTATION_PLAYBOOK.md Part B.2).
"""

from __future__ import annotations

from finfluencer.infrastructure.analysis.embeddings_adapter import (
    EmbeddingsEngineAdapter,
    EmbeddingsOutcome,
)
from finfluencer.infrastructure.analysis.preprocess_adapter import (
    PreprocessEngineAdapter,
    PreprocessOutcome,
)
from finfluencer.infrastructure.analysis.real_sentiment_engine import RealSentimentAnalysisEngine
from finfluencer.infrastructure.analysis.real_topics_engine import RealTopicsAnalysisEngine
from finfluencer.infrastructure.analysis.sentiment_adapter import SentimentAnalysisAdapter
from finfluencer.infrastructure.analysis.topics_adapter import TopicsAnalysisAdapter

__all__ = [
    "EmbeddingsEngineAdapter",
    "EmbeddingsOutcome",
    "PreprocessEngineAdapter",
    "PreprocessOutcome",
    "RealSentimentAnalysisEngine",
    "RealTopicsAnalysisEngine",
    "SentimentAnalysisAdapter",
    "TopicsAnalysisAdapter",
]
