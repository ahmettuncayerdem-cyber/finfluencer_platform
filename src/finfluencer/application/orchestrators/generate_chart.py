"""GenerateChartOrchestrator (PRODUCT_ARCHITECTURE.md section 3.1, section 11.2 Reporting
Service; BACKLOG.md EPIC-10).

Resolves a `Report`'s cited `InterpretationRecord`s back to their source `AnalysisRun`s, verifies
they all pin to the same `CollectionRun`, and renders a chart via `IChartRenderer` (EPIC-10's
`ChartRendererAdapter`, wrapping `reporting.master_table.build_master_table` unmodified).

Deliberately structured as a near-duplicate of `ExportReportTableOrchestrator` (T-026) rather
than a shared base class: the citation-resolution and same-CollectionRun-invariant logic is
identical, but the two orchestrators depend on different Domain Protocols (`IChartRenderer` vs
`ITableExporter`) and this is only the second orchestrator with this exact shape -- extracting a
shared base class now would be exactly the premature-abstraction-from-two-examples this
codebase's own established discipline avoids (see `table_export_adapter.py`'s and
`snapshot_adapter.py`'s own docstrings making the identical call for adapters).

Does NOT construct a Domain `Export` entity -- identical reasoning `ExportReportTableOrchestrator`
already documents (section 10.1 line 604 restricts `Export`/`ExportFormat` to "PDF or Word"; a
rendered chart is the same kind of read-only, non-`Export` capability table export already is).

Implementation principles honored here (same discipline as T-011/T-020/T-025/T-026):
- Application owns orchestration: the citation-to-CollectionRun resolution and the
  same-CollectionRun invariant check are the only business logic this task adds.
- Domain owns invariants: `Report.citation_ids` is read, never mutated; no entity transition
  happens in this orchestrator at all (chart rendering is read-only with respect to the Domain
  Model, identical to table export).
- Infrastructure executes the actual render: this module depends on `IChartRenderer`
  (Domain-owned Protocol) abstractly -- it never imports `finfluencer.infrastructure.*`,
  `matplotlib`, or `pandas`.
- Persistence remains abstract: depends on `IReportRepository`, `IInterpretationRecordRepository`,
  `IAnalysisRunRepository` (Domain-owned Protocols) abstractly.
"""

from __future__ import annotations

from dataclasses import dataclass

from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.reporting_engine import IChartRenderer
from finfluencer.domain.repositories import (
    IAnalysisRunRepository,
    IInterpretationRecordRepository,
    IReportRepository,
)


@dataclass(frozen=True)
class GenerateChartCommand:
    """Application's own input shape for `GenerateChart` -- deliberately independent of any
    future `finfluencer.presentation.dto.reporting` DTO, same reasoning as
    `ExportReportTableCommand`.
    """

    project_id: EntityId
    report_id: EntityId
    chart_type: str
    output_path: str


@dataclass(frozen=True)
class GenerateChartResult:
    """Application's own output shape -- deliberately minimal, same discipline as
    `ExportReportTableResult`.
    """

    report_id: EntityId
    chart_type: str
    output_path: str
    byte_count: int


class GenerateChartOrchestrator:
    """EPIC-10's orchestrator: render one chart from a `Report`'s cited `AnalysisRun` data."""

    def __init__(
        self,
        *,
        report_repository: IReportRepository,
        interpretation_record_repository: IInterpretationRecordRepository,
        analysis_run_repository: IAnalysisRunRepository,
        chart_renderer: IChartRenderer,
    ) -> None:
        self._report_repository = report_repository
        self._interpretation_record_repository = interpretation_record_repository
        self._analysis_run_repository = analysis_run_repository
        self._chart_renderer = chart_renderer

    def execute(self, command: GenerateChartCommand) -> GenerateChartResult:
        report = self._report_repository.get_by_id(command.project_id, command.report_id)
        if report is None:
            raise ValueError(
                f"No Report found for project_id={command.project_id!r} "
                f"report_id={command.report_id!r}."
            )
        if not report.citation_ids:
            raise ValueError(
                f"Report {command.report_id!r} has no citations -- nothing to chart."
            )

        # Identical citation-to-CollectionRun resolution as ExportReportTableOrchestrator
        # (T-026) -- see this module's own docstring for why this is a deliberate, small
        # duplication rather than a shared base class at this point.
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
                    "CollectionRun -- a chart requires every cited AnalysisRun to pin to the "
                    f"same CollectionRun (found {collection_run_id!r} and "
                    f"{run.collection_run_id!r})."
                )
            analysis_run_ids.append(run.id)

        assert collection_run_id is not None  # guaranteed non-empty citation_ids above

        byte_count = self._chart_renderer.render(
            collection_run_id=str(collection_run_id),
            analysis_run_ids=[str(run_id) for run_id in analysis_run_ids],
            chart_type=command.chart_type,
            output_path=command.output_path,
        )

        return GenerateChartResult(
            report_id=report.id,
            chart_type=command.chart_type,
            output_path=command.output_path,
            byte_count=byte_count,
        )


__all__ = ["GenerateChartCommand", "GenerateChartOrchestrator", "GenerateChartResult"]
