"""Tests for CreateProjectOrchestrator (BACKLOG.md T-009).

This is the "integration test at the API boundary" T-009's Verification line calls for, scoped
to what actually exists this task: no real API route or Persistence implementation exists yet
(both explicitly out of scope, operator instruction 2026-08-01), so the "boundary" exercised
here is Application <-> Domain (via a fake repository standing in for Persistence) and
Application's result <-> Presentation's DTO shape (T-008), proven by actually constructing the
DTO from the orchestrator's output rather than merely asserting field names look similar.
"""

from __future__ import annotations

import ast
import inspect
import uuid

import pytest

from finfluencer.application.orchestrators import (
    CreateProjectCommand,
    CreateProjectOrchestrator,
    CreateProjectResult,
)
from finfluencer.domain.entities import EntityId, Project
from finfluencer.presentation.dto import ProjectCreated


class FakeProjectRepository:
    """An in-memory test double for `IProjectRepository` -- not a Persistence Layer
    implementation. Lives in test code, never under `src/finfluencer/persistence/`.
    """

    def __init__(self) -> None:
        self.saved: list[Project] = []

    def add(self, project: Project) -> None:
        self.saved.append(project)


def _tenant_id() -> EntityId:
    return EntityId(uuid.uuid4())


def test_execute_constructs_and_persists_a_project() -> None:
    repo = FakeProjectRepository()
    orchestrator = CreateProjectOrchestrator(project_repository=repo)
    tenant_id = _tenant_id()

    result = orchestrator.execute(CreateProjectCommand(tenant_id=tenant_id, name="Study"))

    assert len(repo.saved) == 1
    persisted = repo.saved[0]
    assert persisted.tenant_id == tenant_id
    assert persisted.name == "Study"
    assert result.id == persisted.id
    assert result.tenant_id == tenant_id
    assert result.name == "Study"


def test_execute_returns_active_status_for_a_freshly_created_project() -> None:
    # section 10.1 line 487/547 pattern: freshly created is always active.
    repo = FakeProjectRepository()
    orchestrator = CreateProjectOrchestrator(project_repository=repo)

    result = orchestrator.execute(CreateProjectCommand(tenant_id=_tenant_id(), name="Study"))

    assert result.status == "active"


def test_execute_propagates_domain_validation_error_for_empty_name() -> None:
    # BKG-001: the empty-name rule lives in Domain's Project.__init__ (already enforced by
    # T-007); the orchestrator must not swallow or re-wrap it.
    repo = FakeProjectRepository()
    orchestrator = CreateProjectOrchestrator(project_repository=repo)

    with pytest.raises(ValueError):
        orchestrator.execute(CreateProjectCommand(tenant_id=_tenant_id(), name=""))


def test_execute_does_not_persist_when_domain_validation_fails() -> None:
    repo = FakeProjectRepository()
    orchestrator = CreateProjectOrchestrator(project_repository=repo)

    with pytest.raises(ValueError):
        orchestrator.execute(CreateProjectCommand(tenant_id=_tenant_id(), name=""))

    assert repo.saved == []


def test_two_executions_produce_distinct_project_ids() -> None:
    repo = FakeProjectRepository()
    orchestrator = CreateProjectOrchestrator(project_repository=repo)

    a = orchestrator.execute(CreateProjectCommand(tenant_id=_tenant_id(), name="A"))
    b = orchestrator.execute(CreateProjectCommand(tenant_id=_tenant_id(), name="B"))

    assert a.id != b.id


def test_orchestrator_result_maps_onto_the_t008_presentation_dto() -> None:
    # T-009 acceptance criterion: "returns per T-008's schema." Proven by actually building
    # the DTO from the orchestrator's result, not by inspection alone.
    repo = FakeProjectRepository()
    orchestrator = CreateProjectOrchestrator(project_repository=repo)

    result: CreateProjectResult = orchestrator.execute(
        CreateProjectCommand(tenant_id=_tenant_id(), name="Financial Influencer Study")
    )

    dto = ProjectCreated.model_validate(
        {
            "id": result.id,
            "tenant_id": result.tenant_id,
            "name": result.name,
            "status": result.status,
        }
    )
    assert str(dto.id) == str(result.id)
    assert dto.name == result.name
    assert dto.status == "active"


def test_orchestrator_module_does_not_import_presentation() -> None:
    # Application's forbidden dependencies (section 12.1 line 829) include Presentation and
    # API -- not currently encoded in scripts/check_layer_dependencies.py's IG-001 checker
    # (application is absent from its FORBIDDEN_IMPORTS). This test enforces the textual
    # architectural rule directly, by inspecting actual import statements (not prose --
    # the module's own docstring legitimately discusses *why* it avoids importing
    # Presentation, which would trip a naive substring search).
    import finfluencer.application.orchestrators.create_project as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)
