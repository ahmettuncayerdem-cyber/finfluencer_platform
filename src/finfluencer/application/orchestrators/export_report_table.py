"""ExportReportTableOrchestrator (PRODUCT_ARCHITECTURE.md section 8.4, section 11.2 Reporting
Service; BACKLOG.md T-026).

Resolves a `Report`'s cited `InterpretationRecord`s back to their source `AnalysisRun`s, verifies
they all pin to the same `CollectionRun` (a joined master table has no meaning otherwise -- each
row is one comment, and comments only exist under one `CollectionRun`), and exports the joined
table via `ITableExporter` (T-026's `MasterTableExportAdapter`, wrapping
`reporting.master_table.build_master_table` unmodified).

Does NOT construct a Domain `Export` entity -- section 10.1 line 604 restricts `Export`/
`ExportFormat` to "PDF or Word"; this is the separate "manuscript-ready table objects...
available for in-app viewing before export" capability section 8.4 names (T-026's own Readiness
Review finding). No Domain Model extension was made for this task.

Implementation principles honored here (same discipline as T-011/T-020/T-025):
- Application owns orchestration: the citation-to-CollectionRun resolution and the
  same-CollectionRun invariant check are the only business logic this task adds.
- Domain owns invariants: `Report.citation_ids` is read, never mutated; no entity transition
  happens in this orchestrator at all (export is read-only with respect to the Domain Model).
- Infrastructure executes the actual join/write: this module depends on `ITableExporter`
  (Domain-owned Protocol) abstractly -- it never imports `finfluencer.infrastructure.*` or
  `pandas`.
- Persistence remains abstract: depends on `IReportRepository`, `IInterpretationRecordRepository`,
  `IAnalysisRunRepository` (Domain-owned Protocols) abstractly.
"""

from __future__ import annotations

from dataclasses import dataclass

from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.reporting_engine import ITableExporter
from finfluencer.domain.repositories import (
    IAnalysisRunRepository,
    IInterpretationRecordRepository,
    IReportRepository,
)


@dataclass(frozen=True)
class ExportReportTableCommand:
    """Application's own input shape for `ExportReportTable` -- deliberately independent of any
    future `finfluencer.presentation.dto.reporting` DTO, same reasoning as
    `GenerateReportCommand`.
    """

    project_id: EntityId
    report_id: EntityId
    output_path: str


@dataclass(frozen=True)
class ExportReportTableResult:
    """Application's own output shape -- deliberately minimal, same discipline as
    `GenerateReportResult`.
    """

    report_id: EntityId
    row_count: int
    output_path: str


class ExportReportTableOrchestrator:
    """T-026's orchestrator: export a `Report`'s cited `AnalysisRun` data as one joined table."""

    def __init__(
        self,
        *,
        report_repository: IReportRepository,
        interpretation_record_repository: IInterpretationRecordRepository,
        analysis_run_repository: IAnalysisRunRepository,
        table_exporter: ITableExporter,
    ) -> None:
        self._report_repository = report_repository
        self._interpretation_record_repository = interpretation_record_repository
        self._analysis_run_repository = analysis_run_repository
        self._table_exporter = table_exporter

    def execute(self, command: ExportReportTableCommand) -> ExportReportTableResult:
        report = self._report_repository.get_by_id(command.project_id, command.report_id)
        if report is None:
            raise ValueError(
                f"No Report found for project_id={command.project_id!r} "
                f"report_id={command.report_id!r}."
            )
        if not report.citation_ids:
            raise ValueError(
                f"Report {command.report_id!r} has no citations -- nothing to export."
            )

        collection_run_id: EntityId | None = None
        analysis_run_ids: list[EntityId] = []
        for citation_id in report.citation_ids:
            record = self._interpretation_record_repository.get_by_id(citation_id)
            if record is None:
                raise ValueError(
                    f"Report {command.report_id!r} cites InterpretationRecord "
                    f"{citation_id!r}, but no such record was found."
                )
            run = self._analysis_run_repository.get_by_id(
                command.project_id, record.analysis_run_id,
            )
            if run is None:
                raise ValueError(
                    f"InterpretationRecord {citation_id!r} references AnalysisRun "
                    f"{record.analysis_run_id!r}, but no such run was found for "
                    f"project_id={command.project_id!r}."
                )
            if collection_run_id is None:
                collection_run_id = run.collection_run_id
            elif collection_run_id != run.collection_run_id:
                raise ValueError(
                    f"Report {command.report_id!r} cites AnalysisRuns from more than one "
                    "CollectionRun -- a joined master table requires every cited AnalysisRun "
                    f"to pin to the same CollectionRun (found {collection_run_id!r} and "
                    f"{run.collection_run_id!r})."
                )
            analysis_run_ids.append(run.id)

        assert collection_run_id is not None  # guaranteed non-empty citation_ids above

        row_count = self._table_exporter.export(
            collection_run_id=str(collection_run_id),
            analysis_run_ids=[str(run_id) for run_id in analysis_run_ids],
            output_path=command.output_path,
        )

        return ExportReportTableResult(
            report_id=report.id, row_count=row_count, output_path=command.output_path,
        )


__all__ = [
    "ExportReportTableCommand",
    "ExportReportTableOrchestrator",
    "ExportReportTableResult",
]
