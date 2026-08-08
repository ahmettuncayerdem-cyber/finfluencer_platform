"""FinalizeReportOrchestrator (PRODUCT_ARCHITECTURE.md section 10.1 lines 593-601, section 11.2
Reporting Service line 722; BACKLOG.md T-027).

Implements the `FinalizeReport` command named but not previously built by any prior task --
T-027's `GenerateExportOrchestrator` structurally depends on a `finalized` `Report` (section
10.1 line 597: "a finalized `Report` is what `Export` renders from"), so this is the minimal,
necessary prerequisite this task discovered it needed (same "add exactly the gap the current
task needs" discipline as T-025's `get_by_id` addition).

Provides section 11.2 line 727's idempotency contract ("`FinalizeReport` is naturally idempotent
-- finalizing twice is a no-op") at the Application layer: `Report.finalize()` itself
(T-024, Domain) raises `DomainInvariantViolation` on a second call by design -- a terminal-state
guard, left unchanged here. This orchestrator checks `report.status` *before* calling
`finalize()`, returning the already-finalized result as a no-op instead of ever invoking the
Domain method a second time -- idempotency is layered on top of the guard, not a relaxation of
it (same idempotent-dispatch pattern T-011/T-020 already established for
`StartCollectionRun`/`StartAnalysisRun`).

Deliberately does NOT auto-finalize from `GenerateExportOrchestrator` -- a PI may still want to
add citations before locking a Report; folding the two together would silently remove that
choice. A separate, explicit call is required.
"""

from __future__ import annotations

from dataclasses import dataclass

from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.report import ReportStatus
from finfluencer.domain.repositories import IReportRepository


@dataclass(frozen=True)
class FinalizeReportCommand:
    """Application's own input shape for `FinalizeReport` -- deliberately independent of any
    future `finfluencer.presentation.dto.reporting` DTO, same reasoning as
    `GenerateReportCommand`.
    """

    project_id: EntityId
    report_id: EntityId


@dataclass(frozen=True)
class FinalizeReportResult:
    """Application's own output shape -- deliberately minimal, same discipline as
    `GenerateReportResult`.
    """

    report_id: EntityId
    status: str


class FinalizeReportOrchestrator:
    """T-027's orchestrator: transition a `draft` `Report` to `finalized`, idempotently."""

    def __init__(self, *, report_repository: IReportRepository) -> None:
        self._report_repository = report_repository

    def execute(self, command: FinalizeReportCommand) -> FinalizeReportResult:
        report = self._report_repository.get_by_id(command.project_id, command.report_id)
        if report is None:
            raise ValueError(
                f"No Report found for project_id={command.project_id!r} "
                f"report_id={command.report_id!r}."
            )

        if report.status is not ReportStatus.FINALIZED:
            report.finalize()
            self._report_repository.save(report)

        return FinalizeReportResult(report_id=report.id, status=report.status.value)


__all__ = ["FinalizeReportCommand", "FinalizeReportOrchestrator", "FinalizeReportResult"]
