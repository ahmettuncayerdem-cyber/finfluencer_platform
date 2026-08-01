"""Analysis Engine Infrastructure adapter (BACKLOG.md T-019).

Implements `finfluencer.domain.analysis_engine.IAnalysisEngine` by wrapping the existing, tested
`finfluencer.topics.pipeline.run_topics` (and its `BERTopicRunner`) unmodified, behind one
adapter class, per IMPLEMENTATION_ROADMAP.md section 3's "Wrapper required" classification for
the Analysis Engine.

See `CONTEXT_PACK.md` in this directory (IMPLEMENTATION_PLAYBOOK.md Part B.2).
"""

from __future__ import annotations

from finfluencer.infrastructure.analysis.topics_adapter import TopicsAnalysisAdapter

__all__ = ["TopicsAnalysisAdapter"]
