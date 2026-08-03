"""GenerateExportOrchestrator (PRODUCT_ARCHITECTURE.md section 8.4, section 10.1 lines 603-609,
section 11.2 Reporting Service line 722/727-728; BACKLOG.md T-027).

Renders a `finalized` `Report`'s cited `InterpretationRecord`s to PDF and constructs the first
real `Export` (T-024, unused until this task). Requires `report.status is ReportStatus.FINALIZED`
(section 10.1 line 597: "a finalized `Report` is what `Export` renders from") -- rejects a draft
Report rather than finalizing it on the caller's behalf; see `FinalizeReportOrchestrator`'s own
docstring for why that is a deliberate product-behavior choice, not just a technical gap-fill.

Provides section 11.2 line 727's idempotency contract ("`GenerateExport` requires an idempotency
key... re-request returns the existing Export, no duplicate render") via the natural
`(report_id, report_version, format)` key through `IExportRepository
.get_by_report_version_and_format`, rather than a separate caller-supplied token -- flagged
design note, Readiness Review Q8: in this synchronous, single-process implementation the natural
key already provides an equivalent guarantee, the same MVP-stage simplification already
established for `StartAnalysisRunOrchestrator` (architecturally async, section 11.2 line 702;
implemented synchronously).

Only `ExportFormat.PDF` is supported -- `ExportFormat.WORD` does not exist yet (T-024's own
TODO); a `format` other than `PDF` is rejected explicitly rather than silently mis-rendered.

Implementation principles honored here (same discipline as T-011/T-020/T-025/T-026):
- Application owns orchestration: the finalized-check, idempotency lookup, and citation
  resolution are the only business logic this task adds.
- Domain owns invariants: `Export` is constructed via its own constructor (which enforces
  `report_version >= 1` and non-None `format`), never bypassed.
- Infrastructure executes the actual render: this module depends on `IPdfRenderer` (Domain-owned
  Protocol) abstractly -- it never imports `finfluencer.infrastructure.*` or `reportlab`.
- Persistence remains abstract: depends on `IReportRepository`,
  `IInterpretationRecordRepository`, `IExportRepository` (Domain-owned Protocols) abstractly.
"""

from __future__ import annotations

from dataclasses import dataclass

from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.export import Export, ExportFormat
from finfluencer.domain.entities.report import ReportStatus
from finfluencer.domain.reporting_engine import CitationSnapshot, IPdfRenderer
from finfluencer.domain.repositories import (
    IExportRepository,
    IInterpretationRecordRepository,
    IReportRepository,
)


@dataclass(frozen=True)
class GenerateExportCommand:
    """Application's own input shape for `GenerateExport` -- deliberately independent of any
    future `finfluencer.presentation.dto.reporting` DTO, same reasoning as
    `ExportReportTableCommand`.
    """

    project_id: EntityId
    report_id: EntityId
    output_path: str
    format: ExportFormat = ExportFormat.PDF


@dataclass(frozen=True)
class GenerateExportResult:
    """Application's own output shape -- deliberately minimal, same discipline as
    `ExportReportTableResult`.
    """

    export_id: EntityId
    report_id: EntityId
    output_path: str
    page_count: int | None


class GenerateExportOrchestrator:
    """T-027's orchestrator: render a `finalized` `Report`'s citations to PDF and persist the
    resulting `Export`.
    """

    def __init__(
        self,
        *,
        report_repository: IReportRepository,
        interpretation_record_repository: IInterpretationRecordRepository,
        export_repository: IExportRepository,
        pdf_renderer: IPdfRenderer,
    ) -> None:
        self._report_repository = report_repository
        self._interpretation_record_repository = interpretation_record_repository
        self._export_repository = export_repository
        self._pdf_renderer = pdf_renderer

    def execute(self, command: GenerateExportCommand) -> GenerateExportResult:
        if command.format is not ExportFormat.PDF:
            raise ValueError(
                f"GenerateExport only supports ExportFormat.PDF in this implementation "
                f"(got {command.format!r}) -- Word rendering (section 8.4 line 299, v1.x) is "
                "not yet built."
            )

        report = self._report_repository.get_by_id(command.project_id, command.report_id)
        if report is None:
            raise ValueError(
                f"No Report found for project_id={command.project_id!r} "
                f"report_id={command.report_id!r}."
            )
        if report.status is not ReportStatus.FINALIZED:
            raise ValueError(
                f"Report {command.report_id!r} is not finalized (status="
                f"{report.status.value!r}) -- GenerateExport requires a finalized Report, per "
                "section 10.1 line 597 ('a finalized Report is what Export renders from'). "
                "Call FinalizeReport first."
            )
        if not report.citation_ids:
            raise ValueError(
                f"Report {command.report_id!r} has no citations -- nothing to render."
            )

        existing = self._export_repository.get_by_report_version_and_format(
            report.id, report.version, command.format,
        )
        if existing is not None:
            return GenerateExportResult(
                export_id=existing.id,
                report_id=report.id,
                output_path=command.output_path,
                page_count=None,
            )

        citations: list[CitationSnapshot] = []
        for citation_id in report.citation_ids:
            record = self._interpretation_record_repository.get_by_id(citation_id)
            if record is None:
                raise ValueError(
                    f"Report {command.report_id!r} cites InterpretationRecord "
                    f"{citation_id!r}, but no such record was found."
                )
            citations.append(
                CitationSnapshot(
                    record_id=str(record.id),
                    analysis_run_id=str(record.analysis_run_id),
                    kind=record.kind.value,
                    selector=record.selector,
                    content=record.content,
                ),
            )

        page_count = self._pdf_renderer.render(
            report_id=str(report.id),
            report_version=report.version,
            citations=citations,
            output_path=command.output_path,
        )

        export = Export(
            report_id=report.id, report_version=report.version, format=command.format,
        )
        self._export_repository.add(export)

        return GenerateExportResult(
            export_id=export.id,
            report_id=report.id,
            output_path=command.output_path,
            page_count=page_count,
        )


__all__ = ["GenerateExportCommand", "GenerateExportOrchestrator", "GenerateExportResult"]
