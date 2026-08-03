"""Reporting Engine ports (PRODUCT_ARCHITECTURE.md section 10.0, section 8.4, section 11.2
Reporting Service; BACKLOG.md T-025, T-026, T-027).

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

BACKLOG.md T-027 scope: rendering a `finalized` `Report`'s cited content to PDF -- the first task
that DOES produce an `Export` (T-024, unused until now). Unlike `IResultSnapshotReader`/
`ITableExporter`, `IPdfRenderer.render()` cannot resolve its own input by filesystem convention:
`InterpretationRecord.content` lives behind a repository, not a `topics.parquet`/
`sentiment.parquet`-style path this adapter could derive from an id alone. `CitationSnapshot`
carries the already-resolved fields `GenerateExportOrchestrator` (Application) reads from each
cited `InterpretationRecord` before calling this port -- a plain data shape, not a new business
abstraction (Readiness Review Q6/Q8).
"""

from __future__ import annotations

from typing import Protocol, TypedDict


class CitationSnapshot(TypedDict):
    """Plain, Domain-safe data shape for one cited `InterpretationRecord`'s content, passed from
    `GenerateExportOrchestrator` to `IPdfRenderer.render()`. Every value is already a primitive
    string -- no `InterpretationRecord` instance crosses this boundary, same reasoning
    `AnalysisOutcome`/`IResultSnapshotReader.read()` were kept plain for.
    """

    record_id: str
    analysis_run_id: str
    kind: str
    selector: str
    content: str


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


class IPdfRenderer(Protocol):
    """Domain- and Application-owned interface (section 12.1 line 831 pattern), applied here to
    the `GenerateExport` command (section 11.2 line 722) for `format: pdf` -- BACKLOG.md T-027.
    """

    def render(
        self,
        report_id: str,
        report_version: int,
        citations: list[CitationSnapshot],
        output_path: str,
    ) -> int:
        """Render a `finalized` `Report`'s cited content to a PDF file at `output_path`,
        returning the number of pages written.

        `citations` must be non-empty -- callers are responsible for that (same permissiveness
        `IResultSnapshotReader.read()`/`ITableExporter.export()` already have toward their own
        callers); this Protocol does not itself re-verify `Report.status` or citation count.
        """
        ...


__all__ = ["CitationSnapshot", "IPdfRenderer", "IResultSnapshotReader", "ITableExporter"]
