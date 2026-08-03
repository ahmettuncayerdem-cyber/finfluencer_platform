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

BACKLOG.md T-025 adds `get_by_id` to `IAnalysisRunRepository` (a genuine, minimal gap found
during T-025's Readiness Review: `GenerateReportOrchestrator` receives an `analysis_run_id`
directly, not an idempotency key, and no existing method could look one up by id), plus two new
Protocols -- `IReportRepository`, `IInterpretationRecordRepository` -- exactly the methods
`GenerateReportOrchestrator` needs, same minimal-surface discipline as every repository above.

BACKLOG.md T-026 adds `get_by_id` to `IInterpretationRecordRepository` -- `ExportReportTableOrchestrator`
needs to resolve a Report's citations back to their source AnalysisRuns' CollectionRun, same
"add the exact method the current task needs" discipline as every repository extension above.

BACKLOG.md T-027 adds `IExportRepository` -- `add`, `get_by_report_version_and_format` (the
natural-key idempotency lookup `GenerateExportOrchestrator` uses in place of a separate
caller-supplied idempotency token, Readiness Review Q8), same minimal-surface discipline as
every repository above.

No concrete implementation exists anywhere in this repository yet. BACKLOG.md T-009/T-011/T-020
explicitly exclude Persistence Layer work ("No persistence implementation yet," operator
instruction, 2026-08-01). A test double implementing any of these `Protocol`s (as used in
`tests/unit/test_application/test_create_project_orchestrator.py`,
`test_start_collection_run_orchestrator.py`, `test_start_analysis_run_orchestrator.py`, and
`test_generate_report_orchestrator.py`) is an ordinary test fixture, not a Persistence-layer
implementation -- it never touches `src/finfluencer/persistence/`.
"""

from __future__ import annotations

from typing import Protocol

from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.analysis_run import AnalysisRun
from finfluencer.domain.entities.collection_run import CollectionRun
from finfluencer.domain.entities.export import Export, ExportFormat
from finfluencer.domain.entities.interpretation_record import InterpretationRecord
from finfluencer.domain.entities.project import Project
from finfluencer.domain.entities.report import Report


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

    def get_by_id(self, project_id: EntityId, analysis_run_id: EntityId) -> AnalysisRun | None:
        """Look up a specific, already-known AnalysisRun by its own id (BACKLOG.md T-025).

        Unlike `get_by_idempotency_key`, the caller here already knows exactly which
        AnalysisRun it wants (e.g. `GenerateReportOrchestrator`'s command carries an
        `analysis_run_id` directly, not an idempotency key). Returns `None` on no match, or if
        `analysis_run_id` does not belong to `project_id` -- callers must not be able to read
        another Project's AnalysisRun by guessing its id.
        """
        ...


class IReportRepository(Protocol):
    """Domain- and Application-owned interface, per section 12.1 lines 831/839 above.

    Two methods only -- exactly what `GenerateReportOrchestrator` (T-025) needs. No `update`
    method: a `Report`'s in-memory state (citations, `finalize()`) mutates the same object
    reference the orchestrator already holds, same reasoning `ICollectionRunRepository` already
    documents for `CollectionRun`.
    """

    def add(self, report: Report) -> None:
        """Persist a newly created Report."""
        ...

    def get_by_id(self, project_id: EntityId, report_id: EntityId) -> Report | None:
        """Look up a specific Report by its own id, scoped to `project_id` (same
        cross-Project-isolation reasoning as `IAnalysisRunRepository.get_by_id`). Returns
        `None` on no match -- the orchestrator's signal that `GenerateReportCommand`'s optional
        `existing_report_id` does not resolve to a real, accessible Report.
        """
        ...


class IInterpretationRecordRepository(Protocol):
    """Domain- and Application-owned interface, per section 12.1 lines 831/839 above.

    `add()` only, until BACKLOG.md T-026: `InterpretationRecord` is immutable and T-025's own
    orchestrator never looked one back up (once cited into a Report, only the Report's own
    `citation_ids` were read again). T-026 adds `get_by_id` -- exactly the "whichever future
    task first needs to read one back directly" case T-025's own docstring anticipated, needed
    here to resolve a Report's citations back to their source AnalysisRuns for table export.
    """

    def add(self, record: InterpretationRecord) -> None:
        """Persist a newly created InterpretationRecord."""
        ...

    def get_by_id(self, record_id: EntityId) -> InterpretationRecord | None:
        """Look up a specific InterpretationRecord by its own id.

        No `project_id` scoping parameter -- `InterpretationRecord` itself carries no
        `project_id` field (only `analysis_run_id`, section 10.1 line 586); cross-project
        isolation is enforced one level down, by the caller's own subsequent
        `IAnalysisRunRepository.get_by_id(project_id, record.analysis_run_id)` call returning
        `None` for a record whose AnalysisRun belongs to another project.
        """
        ...


class IExportRepository(Protocol):
    """Domain- and Application-owned interface, per section 12.1 lines 831/839 above.

    Two methods only -- exactly what `GenerateExportOrchestrator` (T-027) needs. No `update`
    method: `Export` (section 10.1, lines 603-609) is immutable by construction -- there is
    nothing to mutate once persisted, same reasoning `IInterpretationRecordRepository` already
    documents for `InterpretationRecord`.
    """

    def add(self, export: Export) -> None:
        """Persist a newly created Export."""
        ...

    def get_by_report_version_and_format(
        self, report_id: EntityId, report_version: int, format: ExportFormat,
    ) -> Export | None:
        """Look up a previously-generated Export by its natural key.

        Returns `None` on no match -- `GenerateExportOrchestrator`'s signal to actually render
        a new one. A match is the natural-key equivalent of section 11.2 line 727's "re-request
        returns the existing Export, no duplicate render" -- `(report_id, report_version,
        format)` already uniquely determines an Export in this synchronous, single-process
        implementation, so no separate caller-supplied idempotency token is introduced (Readiness
        Review Q8, flagged design note).
        """
        ...
