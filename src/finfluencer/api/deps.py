"""FastAPI dependency-provider functions (BACKLOG.md T-012).

Reads already-constructed orchestrator instances off `Request.app.state` -- populated once, at
startup, by `finfluencer.bootstrap.create_app()`. This module never constructs a concrete
Infrastructure/Persistence object itself; it only type-hints against
`finfluencer.application.orchestrators.*`, matching this package's own import-discipline rule
(see `api/routes/__init__.py`).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Request

from finfluencer.application.orchestrators import (
    CreateProjectOrchestrator,
    ExportReportTableOrchestrator,
    FinalizeReportOrchestrator,
    GenerateExportOrchestrator,
    GenerateReportOrchestrator,
    GetReportOrchestrator,
    StartAnalysisRunOrchestrator,
    StartCollectionRunOrchestrator,
)


def get_create_project_orchestrator(request: Request) -> CreateProjectOrchestrator:
    return request.app.state.create_project_orchestrator  # type: ignore[no-any-return]


def get_start_collection_run_orchestrator(request: Request) -> StartCollectionRunOrchestrator:
    return request.app.state.start_collection_run_orchestrator  # type: ignore[no-any-return]


def get_start_analysis_run_orchestrator(request: Request) -> StartAnalysisRunOrchestrator:
    return request.app.state.start_analysis_run_orchestrator  # type: ignore[no-any-return]


def get_generate_report_orchestrator(request: Request) -> GenerateReportOrchestrator:
    return request.app.state.generate_report_orchestrator  # type: ignore[no-any-return]


def get_get_report_orchestrator(request: Request) -> GetReportOrchestrator:
    return request.app.state.get_report_orchestrator  # type: ignore[no-any-return]


def get_finalize_report_orchestrator(request: Request) -> FinalizeReportOrchestrator:
    return request.app.state.finalize_report_orchestrator  # type: ignore[no-any-return]


def get_generate_export_orchestrator(request: Request) -> GenerateExportOrchestrator:
    return request.app.state.generate_export_orchestrator  # type: ignore[no-any-return]


def get_export_report_table_orchestrator(request: Request) -> ExportReportTableOrchestrator:
    return request.app.state.export_report_table_orchestrator  # type: ignore[no-any-return]


def get_exports_root(request: Request) -> Path:
    """The directory `GenerateExport`/table-export routes write rendered files to before
    reading them back for the HTTP response -- not an Infrastructure concern (`pathlib.Path` is
    stdlib), just request-scoped plumbing read off `Request.app.state`, same pattern as every
    orchestrator getter above.
    """
    return request.app.state.exports_root  # type: ignore[no-any-return]
