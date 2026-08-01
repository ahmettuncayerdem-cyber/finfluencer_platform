"""Composition root (BACKLOG.md T-012) -- the one module allowed to import across all six
layers for wiring purposes only.

Why this needs to exist and why it cannot live inside any of the six layers: every layer's own
forbidden-dependency rules (`PRODUCT_ARCHITECTURE.md` section 12.1) are written from the
perspective of *using* another layer at request time, not *constructing* one at startup --
Application may depend on "Infrastructure-defined interfaces only (never a concrete
Infrastructure class)" (line 828), and the API Layer is forbidden from importing Infrastructure
or Persistence at all (line 821). Read literally and completely, no layer is allowed to
construct the concrete objects an orchestrator needs injected. Every strict-DI-inversion
architecture has exactly one such exception -- a startup/wiring script, not a business-logic
module -- and `PRODUCT_ARCHITECTURE.md` section 12.2 line 865 already names this pattern
explicitly: "Injected into Infrastructure adapters at startup... via dependency injection."
This module is that startup point, made concrete. It contains zero business logic (no `if`
branching on domain state, no sequencing decisions) -- only object construction and route
registration -- and it is not one of the six layers, so `scripts/check_layer_dependencies.py`'s
IG-001 checker (which only walks `presentation`/`api`/`domain`) never inspects it and is not
being silently evaded by its placement.

**In-memory repository stand-ins, not a Persistence Layer implementation.** `_InMemoryProject
Repository`/`_InMemoryCollectionRunRepository` below are the exact same shape as the
`FakeProjectRepository`/`FakeCollectionRunRepository` test doubles used throughout T-009/T-010/
T-011's own test suites, relocated from test code into a runnable composition root so the
Walking Skeleton has *something* satisfying `IProjectRepository`/`ICollectionRunRepository` to
inject. Non-durable (in-process Python dicts, lost on restart), single-process, no migrations,
no schema -- explicitly not `src/finfluencer/persistence/`'s eventual real implementation
(ADR-0001: PostgreSQL + SQLAlchemy 2.0). Operator constraint for T-012 ("No Persistence
implementation") is honored exactly: nothing durable is introduced here.

**Collection execution reuses T-010's adapter unmodified**, wired to `FixtureCollectionProvider`
(no live network -- same Sprint 0 scope T-010 itself carried) and a temp directory as
`base_root`, fresh each process start.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse

from finfluencer.api.routes.collection import router as collection_router
from finfluencer.api.routes.identity import router as identity_router
from finfluencer.application.orchestrators import (
    CreateProjectOrchestrator,
    StartCollectionRunOrchestrator,
)
from finfluencer.core.config import load_settings
from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.collection_run import CollectionRun
from finfluencer.domain.entities.project import Project
from finfluencer.infrastructure.collection import (
    CollectionEngineAdapter,
    FixtureCollectionProvider,
    fixture_transcript_fetcher,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_DEFAULT_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"
_WEB_INDEX = _REPO_ROOT / "web" / "index.html"


class _InMemoryProjectRepository:
    """Sprint 0 stand-in for `IProjectRepository` (T-009) -- see module docstring."""

    def __init__(self) -> None:
        self._saved: list[Project] = []

    def add(self, project: Project) -> None:
        self._saved.append(project)


class _InMemoryCollectionRunRepository:
    """Sprint 0 stand-in for `ICollectionRunRepository` (T-011) -- see module docstring."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[EntityId, str], CollectionRun] = {}

    def add(self, collection_run: CollectionRun, *, idempotency_key: str) -> None:
        self._by_key[(collection_run.dataset_id, idempotency_key)] = collection_run

    def get_by_idempotency_key(
        self, dataset_id: EntityId, idempotency_key: str
    ) -> CollectionRun | None:
        return self._by_key.get((dataset_id, idempotency_key))


def create_app(
    *,
    settings_path: Path = _DEFAULT_SETTINGS,
    analysts_path: Path = _DEFAULT_ANALYSTS,
    collection_base_root: Path | None = None,
    anon_salt: str = "sprint0-dev-salt",
) -> FastAPI:
    """Build the Walking Skeleton's FastAPI app: wire Sprint 0 stand-ins, construct both
    orchestrators, register routes.

    `collection_base_root` defaults to a fresh temp directory per call -- there is no
    persistence-layer decision here about where collected data should permanently live; that is
    explicitly out of scope (ADR-0001/Persistence Layer, not yet built).
    """
    cfg = load_settings(settings_path, analysts_path, validate_secrets=False)
    base_root = (
        Path(collection_base_root)
        if collection_base_root is not None
        else Path(tempfile.mkdtemp(prefix="finfluencer-walking-skeleton-"))
    )

    collection_engine = CollectionEngineAdapter(
        settings=cfg.settings,
        roster=cfg.roster,
        provider=FixtureCollectionProvider(),
        base_root=base_root,
        transcript_fetcher=fixture_transcript_fetcher,
        anon_salt=anon_salt,
    )

    project_repository = _InMemoryProjectRepository()
    collection_run_repository = _InMemoryCollectionRunRepository()

    app = FastAPI(
        title="Finfluencer Research Platform -- Walking Skeleton (Sprint 0)",
        version="0.1.0-sprint0",
    )
    app.state.create_project_orchestrator = CreateProjectOrchestrator(
        project_repository=project_repository
    )
    app.state.start_collection_run_orchestrator = StartCollectionRunOrchestrator(
        collection_run_repository=collection_run_repository,
        collection_engine=collection_engine,
    )

    app.include_router(identity_router)
    app.include_router(collection_router)

    @app.get("/", include_in_schema=False)
    def _serve_dev_ui() -> Any:
        # A single static HTML+vanilla-JS page (web/index.html) -- deliberately NOT the
        # ADR-0001-decided React+TypeScript frontend, which needs its own package.json and a
        # monorepo-layout decision ADR-0001 itself left open. This is a Sprint 0-only,
        # same-origin developer page proving the Walking Skeleton end to end; full React
        # adoption is deferred to a dedicated future frontend task.
        return FileResponse(_WEB_INDEX)

    return app


def _new_dataset_id() -> str:
    """Convenience for manual/local testing -- the Walking Skeleton has no `CreateDataset`
    command yet (out of T-012's scope, per BACKLOG.md), so there is no real way to obtain a
    `dataset_id` other than generating one client-side. Not imported by any route -- exists only
    so a developer running this app locally has an obvious, documented way to get a valid UUID
    to type into the frontend's "Dataset ID" field.
    """
    return str(uuid.uuid4())


__all__ = ["create_app"]
