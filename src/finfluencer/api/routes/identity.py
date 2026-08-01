"""`api.routes.identity` -- `CreateProject` (PRODUCT_ARCHITECTURE.md section 11.2, Identity
Service, line 657; section 11.3, line 776: `POST /projects` <- `CreateProject`, Sync).

BACKLOG.md T-012 scope: this one route only. Translates the wire DTO (`CreateProjectRequest`,
T-008) into Application's own command (`CreateProjectCommand`, T-009) and back -- the
Application layer never sees a Presentation DTO, per T-009's own docstring; this route is the
one and only place that translation happens, exactly as `PRODUCT_ARCHITECTURE.md` section 12.1
line 820 describes ("Presentation Layer... DTO translation").

`idempotency_key` (required by `CreateProjectRequest`, section 11.2 line 662) is accepted here
but not yet acted upon -- `CreateProjectCommand` (T-009) deliberately has no such field, and no
`api.middleware.idempotency` exists yet (section 12.1 line 819's stated API-layer
responsibility). This is the same, already-flagged deferred item from T-009, now visible one
layer higher: duplicate `CreateProject` submissions are not yet deduplicated at this boundary.
Not a new gap this task introduces -- `StartCollectionRun`, below, does not have this gap, since
T-011's own orchestrator already performs idempotent dispatch internally.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from finfluencer.api.deps import get_create_project_orchestrator
from finfluencer.application.orchestrators import CreateProjectCommand, CreateProjectOrchestrator
from finfluencer.presentation.dto import CreateProjectRequest, ProjectCreated

router = APIRouter(tags=["identity"])


@router.post("/projects", response_model=ProjectCreated, status_code=201)
def create_project(
    request: CreateProjectRequest,
    orchestrator: CreateProjectOrchestrator = Depends(get_create_project_orchestrator),
) -> ProjectCreated:
    command = CreateProjectCommand(tenant_id=request.tenant_id, name=request.name)
    result = orchestrator.execute(command)
    return ProjectCreated(
        id=result.id,
        tenant_id=result.tenant_id,
        name=result.name,
        status=result.status,  # type: ignore[arg-type]
    )
