"""Repository interfaces (PRODUCT_ARCHITECTURE.md section 12.1, line 839: Domain "defines but
never implements `IRepository<T>`..."; line 831: "Application and Domain jointly own these
interfaces; Infrastructure/Persistence only ever implement them.").

BACKLOG.md T-009 scope: `IProjectRepository` only, and only the one method `CreateProject`
needs (`add`). Grows per-epic exactly like the Domain Model (T-007) and the API Contract
(T-008) before it -- not designed speculatively ahead of what the current task needs.

BACKLOG.md T-011 adds `ICollectionRunRepository` -- exactly the two methods
`StartCollectionRunOrchestrator` needs (`add`, `get_by_idempotency_key`), same minimal-surface
discipline.

BACKLOG.md T-020 adds `IAnalysisRunRepository` for `StartAnalysisRunOrchestrator` -- same two
methods, same minimal-surface discipline, but keyed on `(project_id, idempotency_key)` (an
`AnalysisRun` belongs to a `Project`, section 10.1 line 576) rather than `(dataset_id, ...)`.
One genuine behavioral difference from `ICollectionRunRepository`, flagged here rather than
silently mirrored: `add()` may legitimately be called more than once for the same idempotency
key over an `AnalysisRun`'s retry lifetime, since `AnalysisRun` has no `resume()` (section 10.1
line 577: "re-run creates a new `AnalysisRun`, never mutates an existing one") -- each retry
after a `FAILED` attempt persists a *new* `AnalysisRun` and re-points the key's mapping, whereas
`ICollectionRunRepository.add()` is called exactly once per key because Collection resumes the
same instance in place instead.

No concrete implementation exists anywhere in this repository yet. BACKLOG.md T-009/T-011/T-020
explicitly exclude Persistence Layer work ("No persistence implementation yet," operator
instruction, 2026-08-01). A test double implementing any of these `Protocol`s (as used in
`tests/unit/test_application/test_create_project_orchestrator.py`,
`test_start_collection_run_orchestrator.py`, and `test_start_analysis_run_orchestrator.py`) is an
ordinary test fixture, not a Persistence-layer implementation -- it never touches
`src/finfluencer/persistence/`.
"""

from __future__ import annotations

from typing import Protocol

from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.analysis_run import AnalysisRun
from finfluencer.domain.entities.collection_run import CollectionRun
from finfluencer.domain.entities.project import Project


class IProjectRepository(Protocol):
    """Domain- and Application-owned interface, per section 12.1 lines 831/839 above."""

    def add(self, project: Project) -> None:
        """Persist a newly created Project.

        No `get`/`update`/`delete` method exists on this interface yet -- `CreateProject`
        (T-009) only ever adds a new Project. A fuller repository surface arrives with
        whichever future task first needs to read a Project back (e.g. `GetProject`,
        section 11.2 line 658).
        """
        ...


class ICollectionRunRepository(Protocol):
    """Domain- and Application-owned interface, per section 12.1 lines 831/839 above.

    Two methods only -- exactly what `StartCollectionRunOrchestrator` (T-011) needs. No
    `update`/`delete` method: a `CollectionRun`'s in-memory state transitions
    (`start`/`resume`/`complete`/`fail`) mutate the same object reference the orchestrator
    already holds; a real Persistence implementation re-saving that mutated state is that
    implementation's own concern, not part of this minimal interface yet.
    """

    def add(self, collection_run: CollectionRun, *, idempotency_key: str) -> None:
        """Persist a newly created CollectionRun, indexed for later idempotent lookup by
        `(collection_run.dataset_id, idempotency_key)`.

        `idempotency_key` is deliberately a separate parameter, not a `CollectionRun` field --
        `PRODUCT_ARCHITECTURE.md` section 10.1's `CollectionRun` entity spec (lines 563-571)
        does not name an `idempotency_key` property, so this interface keeps that Domain shape
        untouched and treats the key as repository-level (storage) bookkeeping, analogous to an
        `idempotency_key` column alongside a `collection_runs` table rather than a Domain
        attribute.
        """
        ...

    def get_by_idempotency_key(
        self, dataset_id: EntityId, idempotency_key: str
    ) -> CollectionRun | None:
        """Look up a previously-created CollectionRun by `(dataset_id, idempotency_key)`.

        Returns `None` on no match -- the orchestrator's signal to create a new CollectionRun.
        Section 11.2/16.10's idempotent-dispatch requirement for `StartCollectionRun` is what
        this method exists to satisfy.
        """
        ...


class IAnalysisRunRepository(Protocol):
    """Domain- and Application-owned interface, per section 12.1 lines 831/839 above.

    Two methods only -- exactly what `StartAnalysisRunOrchestrator` (T-020) needs. Keyed on
    `(project_id, idempotency_key)`, not `(dataset_id, ...)` -- `AnalysisRun` "belongs to
    exactly one `Project`" (section 10.1 line 576), unlike `CollectionRun`.
    """

    def add(self, analysis_run: AnalysisRun, *, idempotency_key: str) -> None:
        """Persist a newly created AnalysisRun, indexed for later idempotent lookup by
        `(analysis_run.project_id, idempotency_key)`.

        Unlike `ICollectionRunRepository.add()`, this method may legitimately be called more
        than once for the same `idempotency_key` over time: `AnalysisRun` has no `resume()`
        (section 10.1 line 577 -- "re-run creates a new `AnalysisRun`, never mutates an existing
        one"), so each retry after a `FAILED` attempt persists a *new* `AnalysisRun` and
        re-points this key's mapping to it, rather than mutating the failed instance in place.
        A conforming implementation must overwrite, not reject, a second `add()` for a key
        already in use.
        """
        ...

    def get_by_idempotency_key(
        self, project_id: EntityId, idempotency_key: str
    ) -> AnalysisRun | None:
        """Look up the most recently persisted AnalysisRun by `(project_id, idempotency_key)`.

        Returns `None` on no match -- the orchestrator's signal to create a new AnalysisRun.
        """
        ...
