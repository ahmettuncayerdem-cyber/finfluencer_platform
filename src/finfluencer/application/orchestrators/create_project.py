"""CreateProjectOrchestrator (PRODUCT_ARCHITECTURE.md section 11.2, Identity Service, line 657;
section 12.3, "CreateProjectOrchestrator" row).

BACKLOG.md T-009 scope, operator-constrained (2026-08-01): Application orchestrates only.
- No persistence implementation: depends on ``IProjectRepository`` (an interface Domain
  defines, section 12.1 line 831) abstractly. No concrete Infrastructure/Persistence
  implementation is wired in by this task -- callers supply any object satisfying the
  Protocol (an in-memory test double today; a real Persistence-layer repository once one
  exists).
- No authentication logic: this orchestrator does not validate a session or token.
- No authorization logic: no ``AuthorizationPolicy``/``CheckAuthorization`` call exists here
  yet -- section 12.1's full orchestrator shape ("verify..., check AuthorizationPolicy,
  create the entity, persist it, dispatch...", line 827) is deliberately narrowed to only
  what T-009 needs.
- Synchronous: ``CreateProject`` is synchronous (section 11.2 line 663), so there is no job
  to dispatch and no ``IJobDispatcher`` dependency here.

Deliberately does not import anything from ``finfluencer.presentation`` -- Application's
forbidden dependencies explicitly include Presentation and API (section 12.1 line 829: "never
calls upward"), even though ``scripts/check_layer_dependencies.py``'s IG-001 checker does not
currently encode a rule for the ``application`` layer (the script's own comment: "layers with
no entry here (application, infrastructure, persistence) are not constrained by IG-001"). This
module honors the textual architectural rule rather than relying on the absence of a mechanical
check for it -- "no shortcuts around IG-001" per operator instruction, read as the underlying
dependency-direction principle IG-001 exists to protect, not merely the literal coverage of
today's checker implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

from finfluencer.domain.entities import EntityId, Project
from finfluencer.domain.repositories import IProjectRepository


@dataclass(frozen=True)
class CreateProjectCommand:
    """Application's own input shape for ``CreateProject`` -- deliberately independent of
    ``finfluencer.presentation.dto.identity.CreateProjectRequest`` (see this module's
    docstring on why Application never imports Presentation).

    ``idempotency_key`` (section 11.2 line 662) is deliberately NOT a field here:
    idempotency-key deduplication is an API Layer responsibility (section 12.1 line 819,
    "idempotency-key deduplication"), not an Application concern. This command only carries
    what Domain's ``Project`` constructor actually needs.

    TODO(PRODUCT_ARCHITECTURE.md section 12.1, line 819; section 11.2, line 662):
    idempotency-key deduplication belongs in a future ``api.middleware.idempotency`` -- not
    implemented here, since the API Layer is out of T-009's scope.
    """

    tenant_id: EntityId
    name: str


@dataclass(frozen=True)
class CreateProjectResult:
    """Application's own output shape -- deliberately not
    ``presentation.dto.identity.ProjectCreated``, for the same reason
    ``CreateProjectCommand`` is not ``CreateProjectRequest``. Whatever calls this
    orchestrator (today: a test; eventually: an API route) maps this onto ``ProjectCreated``
    at the Presentation boundary -- this orchestrator has no knowledge that a
    ``ProjectCreated`` DTO even exists.
    """

    id: EntityId
    tenant_id: EntityId
    name: str
    status: str


class CreateProjectOrchestrator:
    """T-009's one orchestrator: construct a ``Project`` and persist it via the repository
    interface. No re-validation of what Domain's ``Project`` constructor already guards
    (empty name, missing tenant) -- BKG-001 places that rule in Domain, and re-checking it
    here would duplicate, not add, business logic.
    """

    def __init__(self, project_repository: IProjectRepository) -> None:
        self._project_repository = project_repository

    def execute(self, command: CreateProjectCommand) -> CreateProjectResult:
        project = Project(tenant_id=command.tenant_id, name=command.name)
        self._project_repository.add(project)
        return CreateProjectResult(
            id=project.id,
            tenant_id=project.tenant_id,
            name=project.name,
            status=project.status.value,
        )
