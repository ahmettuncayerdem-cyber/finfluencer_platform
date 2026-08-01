"""AnalysisRun entity (PRODUCT_ARCHITECTURE.md section 10.1, lines 573-581).

Deliberately mirrors `CollectionRun`'s "immutable once completed" discipline (same reasoning,
line 578), but is NOT a copy-paste of its lifecycle: section 10.1 line 577 is explicit that
"re-run creates a new `AnalysisRun`, never mutates an existing one" -- unlike `CollectionRun`,
which is "resumable from a `failed`/interrupted state" (line 567). This entity therefore has no
`resume()` method; a failed AnalysisRun is retried by constructing a new instance, not by
resuming the old one. Getting this distinction wrong (adding a `resume()` here) would silently
contradict the architecture rather than extend it.
"""

from __future__ import annotations

from enum import Enum

from finfluencer.domain.entities._common import (
    DomainInvariantViolation,
    EntityId,
    new_entity_id,
)


class AnalysisRunStatus(str, Enum):
    """PRODUCT_ARCHITECTURE.md section 10.1, line 577: "`queued -> running -> completed |
    failed`; re-run creates a new `AnalysisRun`, never mutates an existing one."
    """

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisRun:
    """"one execution of a specific `AnalysisType` against a specific `CollectionRun`'s data
    state." (section 10.1, line 574)
    """

    def __init__(
        self,
        project_id: EntityId,
        collection_run_id: EntityId,
        analysis_type_id: EntityId,
        analysis_type_version: str,
        *,
        entity_id: EntityId | None = None,
    ) -> None:
        if project_id is None:
            raise ValueError(
                "AnalysisRun.project_id is required: 'belongs to exactly one `Project`' "
                "(section 10.1, line 576)."
            )
        if collection_run_id is None:
            raise ValueError(
                "AnalysisRun.collection_run_id is required: 'references exactly one "
                "`CollectionRun` (not a loosely-scoped `Dataset` reference)' -- pinning to a "
                "specific `CollectionRun` is section 10.1's tightened reproducibility rule "
                "(line 576)."
            )
        if analysis_type_id is None:
            raise ValueError(
                "AnalysisRun.analysis_type_id is required: 'references exactly one "
                "`AnalysisType` (pinned version)' (section 10.1, line 576)."
            )
        if not analysis_type_version or not analysis_type_version.strip():
            raise ValueError(
                "AnalysisRun.analysis_type_version is required: 'an AnalysisRun records which "
                "AnalysisType version produced it' (section 10.1, line 539)."
            )
        self._id = entity_id if entity_id is not None else new_entity_id()
        self._project_id = project_id
        self._collection_run_id = collection_run_id
        self._analysis_type_id = analysis_type_id
        self._analysis_type_version = analysis_type_version
        self._status = AnalysisRunStatus.QUEUED

        # NOTE (was a TODO; resolved by BACKLOG.md T-024): "owns many `InterpretationRecord`"
        # (line 576). `InterpretationRecord` is now implemented (`interpretation_record.py`)
        # and pins to this entity's `id` via its own `analysis_run_id` field -- no change was
        # needed here, exactly as anticipated (this entity's `id` was already a stable,
        # immutable-once-`completed` identifier, same pattern `CollectionRun` established).

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, line 579): "keyed by its manifest hash
        # (Reproducibility & Experiment Tracking, section 8.3)". Manifest-hash computation is
        # not this task's job (T-018 scopes only the Domain entity) -- a future Infrastructure/
        # Application concern, tracked here rather than invented speculatively.

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, AuditLogEntry, lines 623-631, and section
        # 12.2, line 864): "`Project`-scoped `AuditLogEntry` on start, completion, and failure"
        # (line 580). Not written by this entity -- Application-layer responsibility, same
        # reasoning as `CollectionRun`.

    @property
    def id(self) -> EntityId:
        return self._id

    @property
    def project_id(self) -> EntityId:
        return self._project_id

    @property
    def collection_run_id(self) -> EntityId:
        return self._collection_run_id

    @property
    def analysis_type_id(self) -> EntityId:
        return self._analysis_type_id

    @property
    def analysis_type_version(self) -> str:
        return self._analysis_type_version

    @property
    def status(self) -> AnalysisRunStatus:
        return self._status

    @property
    def is_completed(self) -> bool:
        """"Immutable once `completed`" (line 578) -- the property a future
        `InterpretationRecord`-creating caller should check before citing this run's results.
        """
        return self._status is AnalysisRunStatus.COMPLETED

    def _reject_if_completed(self) -> None:
        if self._status is AnalysisRunStatus.COMPLETED:
            raise DomainInvariantViolation(
                "AnalysisRun is immutable once completed (section 10.1, line 578) -- no "
                "further state transition is permitted. Re-run by constructing a new "
                "AnalysisRun (line 577), not by mutating this one."
            )

    def start(self) -> None:
        """`queued -> running` (line 577)."""
        self._reject_if_completed()
        if self._status is not AnalysisRunStatus.QUEUED:
            raise DomainInvariantViolation(
                f"Cannot start an AnalysisRun from status '{self._status.value}'; only "
                "'queued' may transition to 'running' via start()."
            )
        self._status = AnalysisRunStatus.RUNNING

    def complete(self) -> None:
        """`running -> completed` (line 577). Terminal: once this succeeds, every other
        method on this instance that would mutate state raises `DomainInvariantViolation`.
        """
        self._reject_if_completed()
        if self._status is not AnalysisRunStatus.RUNNING:
            raise DomainInvariantViolation(
                f"Cannot complete an AnalysisRun from status '{self._status.value}'; only "
                "'running' may transition to 'completed'."
            )
        self._status = AnalysisRunStatus.COMPLETED

    def fail(self) -> None:
        """`running -> failed` (line 577). Unlike `CollectionRun`, there is no `resume()` from
        this state -- section 10.1 line 577 specifies a failed run is retried by creating a new
        `AnalysisRun`, not by resuming this one.
        """
        self._reject_if_completed()
        if self._status is not AnalysisRunStatus.RUNNING:
            raise DomainInvariantViolation(
                f"Cannot fail an AnalysisRun from status '{self._status.value}'; only "
                "'running' may transition to 'failed'."
            )
        self._status = AnalysisRunStatus.FAILED


__all__ = ["AnalysisRun", "AnalysisRunStatus"]
