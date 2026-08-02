"""Reporting Engine ports (PRODUCT_ARCHITECTURE.md section 10.0, section 8.4, section 11.2
Reporting Service; BACKLOG.md T-025, T-026).

Mirrors `domain/analysis_engine.py`'s own shape (`IAnalysisEngine`/`AnalysisOutcome`, T-019):
Domain states the shape of a Reporting capability, Infrastructure supplies the implementation,
and nothing above Infrastructure needs to know or care how the result is actually stored on
disk.

BACKLOG.md T-025 scope: `raw_result_snapshot` only -- reading a `completed` AnalysisRun's own
output and turning it into `InterpretationRecord.content` (an opaque, Domain-safe string; no
pandas DataFrame crosses this boundary, same reasoning `AnalysisOutcome` was kept plain for).

BACKLOG.md T-026 scope: joining multiple AnalysisRuns' output (via the existing
`reporting.master_table` module) into one exported table. Deliberately NOT modeled as producing
an `Export` Domain entity -- section 10.1 line 604 restricts `Export`/`ExportFormat` to "PDF or
Word"; table/CSV generation is the separate "manuscript-ready table objects... available for
in-app viewing before export" capability section 8.4 names, which needs no new entity.
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


class ITableExporter(Protocol):
    """Domain- and Application-owned interface (section 12.1 line 831 pattern), applied here to
    the "manuscript-ready table objects" capability section 8.4 names -- BACKLOG.md T-026.
    """

    def export(
        self, collection_run_id: str, analysis_run_ids: list[str], output_path: str,
    ) -> int:
        """Build and write a joined table from `collection_run_id`'s comments and the given
        `analysis_run_ids`' results, returning the number of rows written.

        `analysis_run_ids` must all belong to `collection_run_id` -- callers are responsible for
        that pinning (same permissiveness `IAnalysisEngine.run()`/`IResultSnapshotReader.read()`
        already have toward their own callers); this Protocol does not itself re-verify it.
        """
        ...


__all__ = ["IResultSnapshotReader", "ITableExporter"]
