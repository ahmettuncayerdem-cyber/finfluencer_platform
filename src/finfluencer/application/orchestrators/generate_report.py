"""GenerateReportOrchestrator (PRODUCT_ARCHITECTURE.md section 8.4, section 10.0, section 11.2
Reporting Service; BACKLOG.md T-025).

Turns a `completed` `AnalysisRun` into a citable `InterpretationRecord` (kind=
`raw_result_snapshot`) and adds it to a `Report` -- creating a new draft `Report` if
`GenerateReportCommand.existing_report_id` is omitted, or citing into an already-existing draft
`Report` if given. This lets one `Report` accumulate citations from multiple `AnalysisRun`s over
several calls (BACKLOG.md T-025's own Verification line: "integration test, topic + sentiment
AnalysisRun -> Report") without inventing a separate `AddCitation` orchestrator ahead of when a
real need for one surfaces (section 11.2 line 722 names `AddCitation` as its own future command;
this orchestrator covers only the MVP path of generating a snapshot and citing it in one step).

Zero AI interpretation logic exists anywhere in this module -- `kind: ai_generated` is out of
scope until the AI Interpretation Layer (Roadmap Phase 2), per T-024's and T-025's own BACKLOG
lines. This orchestrator never calls an external AI provider and never could: it only depends on
`IResultSnapshotReader` (T-025, reads an existing AnalysisRun's own output) and the three
repository Protocols below.

Implementation principles honored here (same discipline as T-011/T-020):
- Application owns orchestration: the create-vs-cite-into-existing decision, and the "read
  snapshot then construct then cite" sequencing, are the only business logic this task adds.
- Domain owns invariants: `Report.add_citation()`/`Report.finalize()` are called, never
  re-implemented or bypassed; a non-`completed` `AnalysisRun` is rejected before any snapshot is
  read.
- Infrastructure executes the actual read: this module depends on `IResultSnapshotReader`
  (Domain-owned Protocol) abstractly -- it never imports `finfluencer.infrastructure.*` or
  `pandas`.
- Persistence remains abstract: depends on `IAnalysisRunRepository`, `IReportRepository`,
  `IInterpretationRecordRepository` (Domain-owned Protocols) abstractly -- no concrete
  implementation is wired in here.
"""

from __future__ import annotations

from dataclasses import dataclass

from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.interpretation_record import (
    InterpretationRecord,
    InterpretationRecordKind,
)
from finfluencer.domain.entities.report import Report
from finfluencer.domain.reporting_engine import IResultSnapshotReader
from finfluencer.domain.repositories import (
    IAnalysisRunRepository,
    IInterpretationRecordRepository,
    IReportRepository,
)

#: T-025's fixed selector value -- no partial-selector query language exists yet (Readiness
#: Review Q2/Q7); every snapshot is the AnalysisRun's complete result.
_FULL_RESULT_SELECTOR = "full_result"


@dataclass(frozen=True)
class GenerateReportCommand:
    """Application's own input shape for `GenerateReport` -- deliberately independent of any
    future `finfluencer.presentation.dto.reporting` DTO, same reasoning as
    `StartAnalysisRunCommand`.

    `analysis_run_id` is trusted as belonging to `project_id` only after `get_by_id` confirms
    it -- this orchestrator does not skip that check.
    """

    project_id: EntityId
    analysis_run_id: EntityId
    existing_report_id: EntityId | None = None


@dataclass(frozen=True)
class GenerateReportResult:
    """Application's own output shape -- deliberately minimal, same discipline as
    `StartAnalysisRunResult`.
    """

    report_id: EntityId
    project_id: EntityId
    status: str
    citation_count: int


class GenerateReportOrchestrator:
    """T-025's orchestrator: snapshot a completed `AnalysisRun`'s result and cite it into a
    `Report`, creating that `Report` if the caller didn't already have one in progress.
    """

    def __init__(
        self,
        *,
        analysis_run_repository: IAnalysisRunRepository,
        report_repository: IReportRepository,
        interpretation_record_repository: IInterpretationRecordRepository,
        snapshot_reader: IResultSnapshotReader,
    ) -> None:
        self._analysis_run_repository = analysis_run_repository
        self._report_repository = report_repository
        self._interpretation_record_repository = interpretation_record_repository
        self._snapshot_reader = snapshot_reader

    def execute(self, command: GenerateReportCommand) -> GenerateReportResult:
        run = self._analysis_run_repository.get_by_id(
            command.project_id, command.analysis_run_id,
        )
        if run is None:
            raise ValueError(
                f"No AnalysisRun found for project_id={command.project_id!r} "
                f"analysis_run_id={command.analysis_run_id!r}."
            )
        if not run.is_completed:
            raise ValueError(
                f"AnalysisRun {command.analysis_run_id!r} is not completed (status="
                f"{run.status.value!r}) -- GenerateReport requires a completed AnalysisRun, "
                "per section 10.1 line 578 ('Immutable once completed')."
            )

        content = self._snapshot_reader.read(str(run.id))
        record = InterpretationRecord(
            analysis_run_id=run.id,
            kind=InterpretationRecordKind.RAW_RESULT_SNAPSHOT,
            selector=_FULL_RESULT_SELECTOR,
            content=content,
        )
        self._interpretation_record_repository.add(record)

        if command.existing_report_id is not None:
            report = self._report_repository.get_by_id(
                command.project_id, command.existing_report_id,
            )
            if report is None:
                raise ValueError(
                    f"No Report found for project_id={command.project_id!r} "
                    f"report_id={command.existing_report_id!r}."
                )
        else:
            report = Report(project_id=command.project_id)
            self._report_repository.add(report)

        report.add_citation(record)

        return GenerateReportResult(
            report_id=report.id,
            project_id=report.project_id,
            status=report.status.value,
            citation_count=len(report.citation_ids),
        )


__all__ = ["GenerateReportCommand", "GenerateReportOrchestrator", "GenerateReportResult"]
