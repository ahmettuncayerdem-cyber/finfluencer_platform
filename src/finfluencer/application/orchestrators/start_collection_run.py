"""StartCollectionRunOrchestrator (PRODUCT_ARCHITECTURE.md section 11.2, Collection Service,
line 683; section 12.3, "StartCollectionRunOrchestrator" row).

BACKLOG.md T-011 scope, operator-constrained (2026-08-01) -- the first Walking Skeleton use
case, reaching Presentation-adjacent input all the way down to the Legacy Collection Engine and
back. See this package's `CONTEXT_PACK.md` for the full orchestration-sequence diagram produced
before this module was written, and for the IG-001 edge-by-edge verification.

Implementation principles honored here (operator instruction):
- Application owns orchestration: the create-vs-resume-vs-replay decision below is the only
  business logic this task adds, and it lives here.
- Domain owns invariants: `CollectionRun`'s own state machine (`start`/`resume`/`complete`/
  `fail`, section 10.1 line 567) is called, never re-implemented or bypassed.
- Infrastructure executes collection: this module depends on `ICollectionEngine` (Domain-owned
  Protocol, T-010) abstractly -- it never imports `finfluencer.infrastructure.*`.
- Persistence remains abstract: depends on `ICollectionRunRepository` (Domain-owned Protocol,
  T-011) abstractly -- no concrete implementation is wired in here.
- Legacy Collection Engine remains untouched: this module never imports `finfluencer.collect.*`
  directly: only `ICollectionEngine.run()`, exactly like `CollectionEngineAdapter` (T-010) is the
  only thing that touches the legacy functions.
- Every CollectionRun owns its own checkpoint_root exactly as defined by ADR-0002: this
  orchestrator always passes `str(collection_run.id)` as `run_id`, so ADR-0002's per-`run_id`
  partitioning and per-`CollectionRun` ownership become the same guarantee.

Deliberately does not import anything from `finfluencer.presentation` or `finfluencer.api`, for
the identical reason and the identical enforcement discipline as
`create_project.py` (T-009) -- see that module's docstring, and this module's own `ast`-based
test in `tests/unit/test_application/test_start_collection_run_orchestrator.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from finfluencer.domain.collection_engine import ICollectionEngine
from finfluencer.domain.entities.collection_run import CollectionRun, CollectionRunStatus
from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.repositories import ICollectionRunRepository


@dataclass(frozen=True)
class StartCollectionRunCommand:
    """Application's own input shape for `StartCollectionRun` -- deliberately independent of
    `finfluencer.presentation.dto.collection.StartCollectionRunRequest` (see this module's
    docstring on why Application never imports Presentation).

    Unlike `CreateProjectCommand` (T-009), `idempotency_key` IS a field here: BACKLOG.md T-011's
    own acceptance criteria requires "idempotency key honored (duplicate calls are safe)" to be
    proven at this orchestrator's own level (its "duplicate-dispatch test"), which is a stronger
    requirement than T-009 carried. This does not contradict T-009's placement of
    idempotency-key *deduplication* at the API layer (section 12.1 line 819) -- that concern
    (returning a cached HTTP response for an exact duplicate request before ever reaching this
    orchestrator) is a distinct, complementary optimization from the guarantee this orchestrator
    itself provides (section 4/16.10: "at-least-once dispatch, idempotent handlers" -- this
    orchestrator's own `execute()` must be safe to call twice with the same key, regardless of
    whether an API-layer cache also exists).
    """

    dataset_id: EntityId
    idempotency_key: str


@dataclass(frozen=True)
class StartCollectionRunResult:
    """Application's own output shape -- deliberately not
    `presentation.dto.collection.CollectionRunAccepted`, for the same reason
    `StartCollectionRunCommand` is not `StartCollectionRunRequest`.

    `CollectionRunAccepted` (T-008) hard-locks `status` to `"queued"`, matching section 11.2's
    stated *asynchronous* contract (an immediate 202-style response before collection actually
    runs). This result type does not make that promise: see this package's `CONTEXT_PACK.md`,
    "Known technical debt", for why `execute()` currently runs synchronously to completion
    (no `IJobDispatcher` exists yet) and returns a `status` of `"completed"`/`"failed"` rather
    than `"queued"`. A future API route wiring the true-async version will map this
    orchestrator's eventual `"queued"`-returning form onto `CollectionRunAccepted`; it must not
    map today's synchronous result onto that DTO as if the contract were already asynchronous.
    """

    id: EntityId
    dataset_id: EntityId
    status: str
    stage_row_counts: dict[str, int] | None


class StartCollectionRunOrchestrator:
    """T-011's one orchestrator: create (or safely re-dispatch onto) a `CollectionRun` and run
    it through to completion via `ICollectionEngine`.

    Does not load or mutate a `Dataset` aggregate -- see `CONTEXT_PACK.md`'s "Known technical
    debt" on the deferred roster-vs-Dataset granularity question. `CollectionRun`'s own
    constructor already enforces "belongs to exactly one Dataset" (section 10.1 line 566) via
    its required `dataset_id`, which is all this task needs.
    """

    def __init__(
        self,
        *,
        collection_run_repository: ICollectionRunRepository,
        collection_engine: ICollectionEngine,
    ) -> None:
        self._collection_run_repository = collection_run_repository
        self._collection_engine = collection_engine

    def execute(self, command: StartCollectionRunCommand) -> StartCollectionRunResult:
        existing = self._collection_run_repository.get_by_idempotency_key(
            command.dataset_id, command.idempotency_key
        )

        if existing is None:
            run = CollectionRun(dataset_id=command.dataset_id)
            self._collection_run_repository.add(run, idempotency_key=command.idempotency_key)
            return self._start_and_run(run)

        if existing.status is CollectionRunStatus.COMPLETED:
            # Idempotent replay: a duplicate dispatch of an already-finished run must not
            # re-collect. No row counts are available to return here without re-running the
            # engine (CollectionOutcome is not persisted alongside CollectionRun, per this
            # module's minimal-interface discipline) -- callers needing the counts again should
            # query the collection's own output artifacts, not this orchestrator.
            return StartCollectionRunResult(
                id=existing.id,
                dataset_id=existing.dataset_id,
                status=existing.status.value,
                stage_row_counts=None,
            )

        if existing.status is CollectionRunStatus.FAILED:
            # Resume path: same run_id (str(existing.id)), so ADR-0002's checkpoint_root is
            # reused, not recreated -- CheckpointManager's own resumability (unchanged, T-010)
            # skips whatever already completed before the failure.
            existing.resume()
            return self._run_and_finish(existing)

        # QUEUED or RUNNING: this synchronous, single-process orchestrator has no code path
        # that returns while leaving a run in either state, so a duplicate dispatch should never
        # observe this branch in practice. Kept as a defensive, non-mutating fallback rather
        # than raising, in case a future concrete repository implementation is shared across
        # processes and this branch becomes reachable.
        return StartCollectionRunResult(
            id=existing.id,
            dataset_id=existing.dataset_id,
            status=existing.status.value,
            stage_row_counts=None,
        )

    def _start_and_run(self, run: CollectionRun) -> StartCollectionRunResult:
        run.start()
        return self._run_and_finish(run)

    def _run_and_finish(self, run: CollectionRun) -> StartCollectionRunResult:
        try:
            outcome = self._collection_engine.run(str(run.id))
        except Exception:
            run.fail()
            raise
        run.complete()
        return StartCollectionRunResult(
            id=run.id,
            dataset_id=run.dataset_id,
            status=run.status.value,
            stage_row_counts=outcome.stage_row_counts,
        )


__all__ = [
    "StartCollectionRunCommand",
    "StartCollectionRunOrchestrator",
    "StartCollectionRunResult",
]
