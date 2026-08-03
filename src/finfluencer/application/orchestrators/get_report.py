"""GetReportOrchestrator (PRODUCT_ARCHITECTURE.md section 11.2 Reporting Service line 723
`GetReport` query; BACKLOG.md T-028).

The previously-unbuilt `GetReport` query -- §11.2 names it alongside `ListReportsForProject`/
`GetExport`, but no task before T-028 needed to read a `Report` back through the Application
layer (T-025/T-026/T-027 only ever read one indirectly, via their own `IReportRepository
.get_by_id()` calls inside a larger command). T-028's Presentation/API layer needs a pure query
of its own to expose -- API must not depend on a Domain-owned repository interface directly
(section 12.1's Application/Domain-owns-the-interfaces rule; also honored by
`api/CONTEXT_PACK.md`'s own "no business logic in routes" guardrail). This orchestrator adds no
business logic beyond that one indirection -- a single `IReportRepository.get_by_id()` call.
"""

from __future__ import annotations

from dataclasses import dataclass

from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.repositories import IReportRepository


@dataclass(frozen=True)
class GetReportCommand:
    """Application's own input shape for `GetReport` -- deliberately independent of any future
    `finfluencer.presentation.dto.reporting` DTO, same reasoning as every other command in this
    package.
    """

    project_id: EntityId
    report_id: EntityId


@dataclass(frozen=True)
class GetReportResult:
    """Application's own output shape -- mirrors `GenerateReportResult`'s fields exactly, since
    both describe the same `Report` shape from two different entry points.
    """

    report_id: EntityId
    project_id: EntityId
    version: int
    status: str
    citation_count: int


class GetReportOrchestrator:
    """T-028's orchestrator: read one `Report` back by id, scoped to its `Project`."""

    def __init__(self, *, report_repository: IReportRepository) -> None:
        self._report_repository = report_repository

    def execute(self, command: GetReportCommand) -> GetReportResult:
        report = self._report_repository.get_by_id(command.project_id, command.report_id)
        if report is None:
            raise ValueError(
                f"No Report found for project_id={command.project_id!r} "
                f"report_id={command.report_id!r}."
            )
        return GetReportResult(
            report_id=report.id,
            project_id=report.project_id,
            version=report.version,
            status=report.status.value,
            citation_count=len(report.citation_ids),
        )


__all__ = ["GetReportCommand", "GetReportOrchestrator", "GetReportResult"]
