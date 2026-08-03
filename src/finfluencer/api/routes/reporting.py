"""`api.routes.reporting` -- the Reporting Service's `GenerateReport` (`CreateReport`+
`AddCitation` folded, section 11.2 line 722), `GetReport` (line 723), `FinalizeReport` (line
722), and `GenerateExport` (line 722; section 11.3 line 782: `POST /reports/{id}/exports`)
operations, plus table export (T-026's own capability, no section 11.2 command name -- see
`presentation/dto/reporting.py`'s own docstring).

BACKLOG.md T-028 scope: five routes, reusing T-025/T-026/T-027's four orchestrators and this
task's own new `GetReportOrchestrator` completely unmodified -- the first Presentation/API
exposure of any Reporting Service operation.

**Path shape reconciles two precedents, not invented from scratch.** Section 11.3's own
"representative" table (line 782) shows `POST /reports/{id}/exports`, with no `project_id` in
the path. But every orchestrator these routes call requires `project_id` for cross-project
isolation (`IReportRepository.get_by_id(project_id, report_id)`, unchanged since T-025), and
`StartCollectionRun`'s own already-implemented route already established the precedent of
carrying the parent-scoping id in the path (`/datasets/{dataset_id}/collection-runs`). Routes
here follow that concrete precedent: `/projects/{project_id}/reports/...`.

**Export routes return raw file bytes directly in the response body, not a JSON DTO.** No
`IJobDispatcher` exists (same gap `collection.py` already documents for `StartCollectionRun`),
so both `GenerateExportOrchestrator` and `ExportReportTableOrchestrator` run synchronously here;
returning the actual file content is simpler and more honest than a JSON envelope pointing at a
separate download endpoint this task does not otherwise need. `GenerateExport`'s deterministic,
version-and-format-keyed output path (`exports_root/{report_id}-v{version}.pdf`) is what makes a
second call to an already-exported `Report` (which `GenerateExportOrchestrator`'s own
idempotency logic does not re-render) still able to return real bytes -- the file from the first
call is still on disk at the same path.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from finfluencer.api.deps import (
    get_export_report_table_orchestrator,
    get_exports_root,
    get_finalize_report_orchestrator,
    get_generate_export_orchestrator,
    get_generate_report_orchestrator,
    get_get_report_orchestrator,
)
from finfluencer.application.orchestrators import (
    ExportReportTableCommand,
    ExportReportTableOrchestrator,
    FinalizeReportCommand,
    FinalizeReportOrchestrator,
    GenerateExportCommand,
    GenerateExportOrchestrator,
    GenerateReportCommand,
    GenerateReportOrchestrator,
    GetReportCommand,
    GetReportOrchestrator,
)
from finfluencer.presentation.dto import GenerateReportRequest, ReportFinalized, ReportView

# `EntityId` is `NewType("EntityId", uuid.UUID)` -- a plain `uuid.UUID` (what every
# Pydantic-validated path/body field below already is) satisfies it at runtime without
# importing `finfluencer.domain` into this module (forbidden, section 12.1 line 821;
# `test_architectural_conformance.py` proves it ast-statically).

router = APIRouter(tags=["reporting"])


@router.post("/projects/{project_id}/reports", response_model=ReportView, status_code=200)
def generate_report(
    project_id: UUID,
    request: GenerateReportRequest,
    orchestrator: GenerateReportOrchestrator = Depends(get_generate_report_orchestrator),
) -> ReportView:
    command = GenerateReportCommand(
        project_id=project_id,  # type: ignore[arg-type]
        analysis_run_id=request.analysis_run_id,  # type: ignore[arg-type]
        existing_report_id=request.existing_report_id,  # type: ignore[arg-type]
    )
    try:
        result = orchestrator.execute(command)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReportView(
        id=result.report_id, project_id=result.project_id,
        status=result.status,  # type: ignore[arg-type]
        citation_count=result.citation_count,
    )


@router.get("/projects/{project_id}/reports/{report_id}", response_model=ReportView)
def get_report(
    project_id: UUID,
    report_id: UUID,
    orchestrator: GetReportOrchestrator = Depends(get_get_report_orchestrator),
) -> ReportView:
    try:
        result = orchestrator.execute(
            GetReportCommand(project_id=project_id, report_id=report_id),  # type: ignore[arg-type]
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReportView(
        id=result.report_id, project_id=result.project_id, version=result.version,
        status=result.status,  # type: ignore[arg-type]
        citation_count=result.citation_count,
    )


@router.post(
    "/projects/{project_id}/reports/{report_id}/finalize", response_model=ReportFinalized,
)
def finalize_report(
    project_id: UUID,
    report_id: UUID,
    orchestrator: FinalizeReportOrchestrator = Depends(get_finalize_report_orchestrator),
) -> ReportFinalized:
    try:
        result = orchestrator.execute(
            FinalizeReportCommand(project_id=project_id, report_id=report_id),  # type: ignore[arg-type]
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReportFinalized(id=result.report_id, status=result.status)  # type: ignore[arg-type]


@router.post("/projects/{project_id}/reports/{report_id}/exports")
def generate_export(
    project_id: UUID,
    report_id: UUID,
    orchestrator: GenerateExportOrchestrator = Depends(get_generate_export_orchestrator),
    exports_root: Path = Depends(get_exports_root),
) -> Response:
    # Deterministic, (report_id, format)-keyed path -- see this module's own docstring for why:
    # a repeat call that hits GenerateExportOrchestrator's idempotent-replay branch (no
    # re-render) must still find real bytes here from the first call.
    output_path = exports_root / f"{report_id}.pdf"
    try:
        orchestrator.execute(
            GenerateExportCommand(
                project_id=project_id,  # type: ignore[arg-type]
                report_id=report_id,  # type: ignore[arg-type]
                output_path=str(output_path),
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not output_path.exists():
        # Idempotent-replay branch returned without this route's own call having rendered
        # anything, and no prior call in this process ever wrote the file either.
        raise HTTPException(
            status_code=409,
            detail="Export was already generated in a way this process has no record of "
            "(no file at the expected path). Not possible via this route alone, since it "
            "always writes to the same deterministic path before returning.",
        )
    return Response(
        content=output_path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{report_id}.pdf"'},
    )


@router.get("/projects/{project_id}/reports/{report_id}/table")
def export_report_table(
    project_id: UUID,
    report_id: UUID,
    orchestrator: ExportReportTableOrchestrator = Depends(get_export_report_table_orchestrator),
    exports_root: Path = Depends(get_exports_root),
) -> Response:
    output_path = exports_root / f"{report_id}.csv"
    try:
        result = orchestrator.execute(
            ExportReportTableCommand(
                project_id=project_id,  # type: ignore[arg-type]
                report_id=report_id,  # type: ignore[arg-type]
                output_path=str(output_path),
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        # A Report citing only one AnalysisType cannot be table-exported yet -- known,
        # documented limitation (T-026's own Context Pack "Known technical debt"), not a bug.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return Response(
        content=output_path.read_bytes(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{report_id}.csv"',
            "X-Row-Count": str(result.row_count),
        },
    )
