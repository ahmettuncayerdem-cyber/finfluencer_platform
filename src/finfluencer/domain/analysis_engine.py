"""Analysis Engine port (PRODUCT_ARCHITECTURE.md section 12.1, same pattern as
`domain/collection_engine.py`'s `ICollectionEngine`: Domain states the shape of "run an
analysis," Infrastructure supplies the implementation, and nothing above Infrastructure needs to
know or care that the implementation happens to be `topics/` (BERTopic) under the hood.

BACKLOG.md T-019 scope: this interface is what T-019's own acceptance criterion requires ("the
Application-layer contract wrapping T-019" -- T-020 -- needs something to depend on) -- it did
not exist before this task, and creating it is this task's job, not a new abstraction invented
beyond what the architecture calls for. No concrete implementation lives here -- see
`finfluencer.infrastructure.analysis`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AnalysisOutcome:
    """Domain-safe summary of one analysis run.

    Deliberately plain (str, int) -- no pandas DataFrame crosses this boundary, mirroring
    `CollectionOutcome`'s own reasoning (section 12.1's "no external SDK" rule for Domain).
    """

    analysis_run_id: str
    row_count: int
    topic_count: int


class IAnalysisEngine(Protocol):
    """Domain- and Application-owned interface (section 12.1 line 831 pattern, applied here to
    the Analysis Engine instead of the Collection Engine).
    """

    def run(self, analysis_run_id: str, collection_run_id: str) -> AnalysisOutcome:
        """Run (or resume) analysis for the given ``analysis_run_id`` against the data
        collected by ``collection_run_id`` -- the pinning relationship section 10.1 requires of
        every `AnalysisRun` (T-018).

        Calling this again with the same ``analysis_run_id`` is the resume/re-verify path -- an
        already-completed analysis's cost is a fast cache-hit re-read (Tier-2/Tier-3 caching
        already implemented inside the wrapped `topics.pipeline.run_topics`), not a re-fit, per
        the legacy pipeline's own caching discipline (unchanged by this interface).
        """
        ...


__all__ = ["AnalysisOutcome", "IAnalysisEngine"]
