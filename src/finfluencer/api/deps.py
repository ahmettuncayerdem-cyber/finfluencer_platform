"""FastAPI dependency-provider functions (BACKLOG.md T-012).

Reads already-constructed orchestrator instances off `Request.app.state` -- populated once, at
startup, by `finfluencer.bootstrap.create_app()`. This module never constructs a concrete
Infrastructure/Persistence object itself; it only type-hints against
`finfluencer.application.orchestrators.*`, matching this package's own import-discipline rule
(see `api/routes/__init__.py`).
"""

from __future__ import annotations

from fastapi import Request

from finfluencer.application.orchestrators import (
    CreateProjectOrchestrator,
    StartCollectionRunOrchestrator,
)


def get_create_project_orchestrator(request: Request) -> CreateProjectOrchestrator:
    return request.app.state.create_project_orchestrator  # type: ignore[no-any-return]


def get_start_collection_run_orchestrator(request: Request) -> StartCollectionRunOrchestrator:
    return request.app.state.start_collection_run_orchestrator  # type: ignore[no-any-return]
