"""CollectionRun entity (PRODUCT_ARCHITECTURE.md section 10.1, lines 563-571).

This is the single most safety-critical invariant in the Sprint 0 subset: a `CollectionRun`
"Immutable once `completed`. This is what makes it a valid reproducibility anchor -- a completed
`CollectionRun`'s resulting data snapshot never changes retroactively." (line 568). Every method
on this class exists to make that literally true in code, not merely documented.
"""

from __future__ import annotations

from enum import Enum

from finfluencer.domain.entities._common import (
    DomainInvariantViolation,
    EntityId,
    new_entity_id,
)


class CollectionRunStatus(str, Enum):
    """PRODUCT_ARCHITECTURE.md section 10.1, line 567:

    "`queued -> running -> completed | failed`; resumable from a `failed`/interrupted state
    (existing engine guarantee, carried into the product per section 7.2 stage 2)."
    """

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CollectionRun:
    """"one execution of the Collection Engine against a `Dataset` -- the "version/state"
    section 2.3 describes, and the concrete reproducibility anchor an `AnalysisRun` pins to."
    (section 10.1, line 564)
    """

    def __init__(self, dataset_id: EntityId, *, entity_id: EntityId | None = None) -> None:
        if dataset_id is None:
            raise ValueError(
                "CollectionRun.dataset_id is required: 'belongs to exactly one `Dataset`' "
                "(section 10.1, line 566)."
            )
        self._id = entity_id if entity_id is not None else new_entity_id()
        self._dataset_id = dataset_id
        self._status = CollectionRunStatus.QUEUED

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, AnalysisRun, lines 573-581): CollectionRun
        # is "referenced by many `AnalysisRun` (as the pinned input state)" (line 566).
        # AnalysisRun is not implemented in Sprint 0 (BACKLOG.md T-007 scopes only Tenant,
        # Project, Dataset, CollectionRun). This entity's `id` remains a stable,
        # immutable-once-`completed` identifier so a future `AnalysisRun.collection_run_id`
        # can pin to it exactly as section 10.1 describes, without any change needed here.

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, AuditLogEntry, lines 623-631, and section
        # 12.2, line 864): "Project-scoped `AuditLogEntry` on start, completion, and failure"
        # (line 570). Not written by this entity -- audit writing is an Application-layer
        # responsibility (`IAuditWriter`, section 12.2 line 864), never a Domain concern.

    @property
    def id(self) -> EntityId:
        return self._id

    @property
    def dataset_id(self) -> EntityId:
        return self._dataset_id

    @property
    def status(self) -> CollectionRunStatus:
        return self._status

    @property
    def is_completed(self) -> bool:
        """"Immutable once `completed`" (line 568) -- the property every future caller that
        needs to know whether this run is safe to pin an `AnalysisRun` against should check.
        """
        return self._status is CollectionRunStatus.COMPLETED

    def _reject_if_completed(self) -> None:
        if self._status is CollectionRunStatus.COMPLETED:
            raise DomainInvariantViolation(
                "CollectionRun is immutable once completed (section 10.1, line 568) -- no "
                "further state transition is permitted."
            )

    def start(self) -> None:
        """`queued -> running` (line 567)."""
        self._reject_if_completed()
        if self._status is not CollectionRunStatus.QUEUED:
            raise DomainInvariantViolation(
                f"Cannot start a CollectionRun from status '{self._status.value}'; only "
                "'queued' may transition to 'running' via start()."
            )
        self._status = CollectionRunStatus.RUNNING

    def resume(self) -> None:
        """"resumable from a `failed`/interrupted state" (line 567) -- kept as a distinct,
        explicitly-named method from `start()` rather than overloading `start()` for two
        semantically different transitions.
        """
        self._reject_if_completed()
        if self._status is not CollectionRunStatus.FAILED:
            raise DomainInvariantViolation(
                f"Cannot resume a CollectionRun from status '{self._status.value}'; only "
                "'failed' may transition to 'running' via resume()."
            )
        self._status = CollectionRunStatus.RUNNING

    def complete(self) -> None:
        """`running -> completed` (line 567). Terminal: once this succeeds, every other
        method on this instance that would mutate state raises `DomainInvariantViolation`.
        """
        self._reject_if_completed()
        if self._status is not CollectionRunStatus.RUNNING:
            raise DomainInvariantViolation(
                f"Cannot complete a CollectionRun from status '{self._status.value}'; only "
                "'running' may transition to 'completed'."
            )
        self._status = CollectionRunStatus.COMPLETED

    def fail(self) -> None:
        """`running -> failed` (line 567)."""
        self._reject_if_completed()
        if self._status is not CollectionRunStatus.RUNNING:
            raise DomainInvariantViolation(
                f"Cannot fail a CollectionRun from status '{self._status.value}'; only "
                "'running' may transition to 'failed'."
            )
        self._status = CollectionRunStatus.FAILED
