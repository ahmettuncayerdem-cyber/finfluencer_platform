"""FastAPI dependency-provider functions (BACKLOG.md T-012).

Reads already-constructed orchestrator instances off `Request.app.state` -- populated once, at
startup, by `finfluencer.bootstrap.create_app()`. This module never constructs a concrete
Infrastructure/Persistence object itself; it only type-hints against
`finfluencer.application.orchestrators.*`, matching this package's own import-discipline rule
(see `api/routes/__init__.py`).
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import Request

from finfluencer.application.orchestrators import (
    CreateProjectOrchestrator,
    ExportReportTableOrchestrator,
    FinalizeReportOrchestrator,
    GenerateChartOrchestrator,
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
    """Unchanged since T-028: the single demo-wired orchestrator, still the fallback for any
    `analysis_type_id` that doesn't match one of the two well-known ids below (Release Blocker
    #6; see `bootstrap.py`'s module docstring).
    """
    return request.app.state.start_analysis_run_orchestrator  # type: ignore[no-any-return]


def get_analysis_run_orchestrators_by_type(
    request: Request,
) -> dict[UUID, StartAnalysisRunOrchestrator]:
    """Release Blocker #6: the two fixed `AnalysisType` ids `bootstrap.py` mints
    (`TOPIC_MODELING_ANALYSIS_TYPE_ID`/`SENTIMENT_ANALYSIS_TYPE_ID`), mapped to real, non-demo
    `StartAnalysisRunOrchestrator` instances. Deliberately a plain dict, not a repository/catalog
    -- same in-memory "stand-in" discipline every other object in this module already follows.
    `api/routes/analysis.py` looks a request's `analysis_type_id` up here first and falls back to
    `get_start_analysis_run_orchestrator`'s demo-wired instance for anything not in this dict; an
    unrecognized id is never an error (`analysis_type_id` stays "trusted as given," same
    permissiveness `StartAnalysisRunOrchestrator` itself already documents).
    """
    return request.app.state.analysis_run_orchestrators_by_type  # type: ignore[no-any-return]


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


def get_generate_chart_orchestrator(request: Request) -> GenerateChartOrchestrator:
    return request.app.state.generate_chart_orchestrator  # type: ignore[no-any-return]


def get_exports_root(request: Request) -> Path:
    """The directory `GenerateExport`/table-export routes write rendered files to before
    reading them back for the HTTP response -- not an Infrastructure concern (`pathlib.Path` is
    stdlib), just request-scoped plumbing read off `Request.app.state`, same pattern as every
    orchestrator getter above.
    """
    return request.app.state.exports_root  # type: ignore[no-any-return]
