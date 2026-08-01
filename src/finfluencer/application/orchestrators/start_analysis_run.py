"""StartAnalysisRunOrchestrator (PRODUCT_ARCHITECTURE.md section 8.2, section 10.1's `AnalysisRun`
spec; BACKLOG.md T-020).

Mirrors `StartCollectionRunOrchestrator`'s (T-011) proven idempotent-dispatch shape as closely as
the two entities' actual specs allow -- see `docs/implementation/
T-020_ARCHITECTURE_EXECUTION_READINESS_REVIEW.md` for the full reused-vs-must-differ analysis.
The one behavioral divergence that matters: `AnalysisRun` has no `resume()` (section 10.1 line
577 -- "re-run creates a new `AnalysisRun`, never mutates an existing one"), so a duplicate
dispatch onto a `FAILED` run constructs and dispatches a **new** `AnalysisRun` here, rather than
resuming the existing one in place.

Implementation principles honored here (same discipline as T-011):
- Application owns orchestration: the create-vs-replay-vs-retry decision below is the only
  business logic this task adds, and it lives here.
- Domain owns invariants: `AnalysisRun`'s own state machine (`start`/`complete`/`fail`, section
  10.1 line 577) is called, never re-implemented or bypassed.
- Infrastructure executes analysis: this module depends on `IAnalysisEngine` (Domain-owned
  Protocol, T-019) abstractly -- it never imports `finfluencer.infrastructure.*` or
  `finfluencer.topics.*`.
- Persistence remains abstract: depends on `IAnalysisRunRepository` (Domain-owned Protocol,
  T-020) abstractly -- no concrete implementation is wired in here.

Deliberately does not import anything from `finfluencer.presentation` or `finfluencer.api`, same
enforcement discipline as `start_collection_run.py` -- see this module's own `ast`-based test in
`tests/unit/test_application/test_start_analysis_run_orchestrator.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from finfluencer.domain.analysis_engine import IAnalysisEngine
from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.analysis_run import AnalysisRun, AnalysisRunStatus
from finfluencer.domain.repositories import IAnalysisRunRepository


@dataclass(frozen=True)
class StartAnalysisRunCommand:
    """Application's own input shape for `StartAnalysisRun` -- deliberately independent of any
    future `finfluencer.presentation.dto.analysis` DTO, same reasoning as
    `StartCollectionRunCommand`.

    `collection_run_id` is trusted as given -- this orchestrator does not verify it against a
    real, `COMPLETED` `CollectionRun` (no `ICollectionRunRepository` lookup here). A genuine
    pinning-validity check is BACKLOG.md T-021's explicit job, not this task's (Readiness Review,
    Assumption 1).
    """

    project_id: EntityId
    collection_run_id: EntityId
    analysis_type_id: EntityId
    analysis_type_version: str
    idempotency_key: str


@dataclass(frozen=True)
class StartAnalysisRunResult:
    """Application's own output shape -- mirrors `StartCollectionRunResult`'s reasoning: not a
    Presentation DTO, and `row_count`/`topic_count` are `None` on an idempotent replay of an
    already-`completed` run (no `AnalysisOutcome` is persisted alongside `AnalysisRun`, same
    minimal-interface discipline as T-011).
    """

    id: EntityId
    project_id: EntityId
    status: str
    row_count: int | None
    topic_count: int | None


class StartAnalysisRunOrchestrator:
    """T-020's orchestrator: create (or safely re-dispatch/retry) an `AnalysisRun` and run it
    through to completion via `IAnalysisEngine`.

    Does not load or validate `AnalysisType`'s catalog entry -- the command's
    `analysis_type_id`/`analysis_type_version` are trusted as given, same permissiveness T-011
    already has for `dataset_id` (Readiness Review, section 2).
    """

    def __init__(
        self,
        *,
        analysis_run_repository: IAnalysisRunRepository,
        analysis_engine: IAnalysisEngine,
    ) -> None:
        self._analysis_run_repository = analysis_run_repository
        self._analysis_engine = analysis_engine

    def execute(self, command: StartAnalysisRunCommand) -> StartAnalysisRunResult:
        existing = self._analysis_run_repository.get_by_idempotency_key(
            command.project_id, command.idempotency_key,
        )

        if existing is None:
            run = self._new_run(command)
            self._analysis_run_repository.add(run, idempotency_key=command.idempotency_key)
            return self._start_and_run(run, command.collection_run_id)

        if existing.status is AnalysisRunStatus.COMPLETED:
            # Idempotent replay: a duplicate dispatch of an already-finished run must not
            # re-analyze. See StartCollectionRunResult's identical reasoning.
            return StartAnalysisRunResult(
                id=existing.id,
                project_id=existing.project_id,
                status=existing.status.value,
                row_count=None,
                topic_count=None,
            )

        if existing.status is AnalysisRunStatus.FAILED:
            # Retry path -- deliberately NOT existing.resume() (no such method): section 10.1
            # line 577 requires a new AnalysisRun, pinned to the same inputs the caller asked
            # for again. The repository re-points this idempotency_key's mapping to it.
            retry_run = self._new_run(command)
            self._analysis_run_repository.add(retry_run, idempotency_key=command.idempotency_key)
            return self._start_and_run(retry_run, command.collection_run_id)

        # QUEUED or RUNNING: same defensive, non-mutating fallback as T-011 -- this synchronous,
        # single-process orchestrator has no code path that returns while leaving a run in
        # either state, so a duplicate dispatch should never observe this branch in practice.
        return StartAnalysisRunResult(
            id=existing.id,
            project_id=existing.project_id,
            status=existing.status.value,
            row_count=None,
            topic_count=None,
        )

    def _new_run(self, command: StartAnalysisRunCommand) -> AnalysisRun:
        return AnalysisRun(
            project_id=command.project_id,
            collection_run_id=command.collection_run_id,
            analysis_type_id=command.analysis_type_id,
            analysis_type_version=command.analysis_type_version,
        )

    def _start_and_run(
        self, run: AnalysisRun, collection_run_id: EntityId,
    ) -> StartAnalysisRunResult:
        run.start()
        try:
            outcome = self._analysis_engine.run(str(run.id), str(collection_run_id))
        except Exception:
            run.fail()
            raise
        run.complete()
        return StartAnalysisRunResult(
            id=run.id,
            project_id=run.project_id,
            status=run.status.value,
            row_count=outcome.row_count,
            topic_count=outcome.topic_count,
        )


__all__ = [
    "StartAnalysisRunCommand",
    "StartAnalysisRunOrchestrator",
    "StartAnalysisRunResult",
]
