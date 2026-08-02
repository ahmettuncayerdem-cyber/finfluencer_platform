"""Reporting Engine port (PRODUCT_ARCHITECTURE.md section 10.0, section 11.2 Reporting Service;
BACKLOG.md T-025).

Mirrors `domain/analysis_engine.py`'s own shape (`IAnalysisEngine`/`AnalysisOutcome`, T-019):
Domain states the shape of "read one AnalysisRun's own result for citation," Infrastructure
supplies the implementation, and nothing above Infrastructure needs to know or care how the
result is actually stored on disk.

BACKLOG.md T-025 scope: `raw_result_snapshot` only -- reading a `completed` AnalysisRun's own
output and turning it into `InterpretationRecord.content` (an opaque, Domain-safe string; no
pandas DataFrame crosses this boundary, same reasoning `AnalysisOutcome` was kept plain for).
"""

from __future__ import annotations

from typing import Protocol


class IResultSnapshotReader(Protocol):
    """Domain- and Application-owned interface (section 12.1 line 831 pattern, applied here to
    the Reporting Service's `CreateRawSnapshot` command, section 11.2 line 722).
    """

    def read(self, analysis_run_id: str) -> str:
        """Return a frozen, Domain-safe string snapshot of the given, already-`completed`
        `AnalysisRun`'s own result -- the content a new `InterpretationRecord` (kind=
        `raw_result_snapshot`) is constructed from.

        Callers are responsible for only invoking this against a `completed` AnalysisRun
        (section 10.1 line 578) -- this Protocol does not itself re-verify status, the same
        permissiveness `IAnalysisEngine.run()` already has toward its own callers.
        """
        ...


__all__ = ["IResultSnapshotReader"]
