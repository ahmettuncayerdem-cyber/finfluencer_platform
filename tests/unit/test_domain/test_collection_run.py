"""Tests for the CollectionRun entity (BACKLOG.md T-007; PRODUCT_ARCHITECTURE.md section 10.1,
lines 563-571) -- especially the "Immutable once `completed`" invariant (line 568), the single
most safety-critical rule in the Sprint 0 subset.
"""

from __future__ import annotations

import uuid

import pytest

from finfluencer.domain.entities import (
    CollectionRun,
    CollectionRunStatus,
    DomainInvariantViolation,
    EntityId,
)


def _dataset_id() -> EntityId:
    return EntityId(uuid.uuid4())


def test_create_requires_dataset_id() -> None:
    with pytest.raises(ValueError):
        CollectionRun(dataset_id=None)  # type: ignore[arg-type]


def test_create_is_queued_by_default() -> None:
    run = CollectionRun(dataset_id=_dataset_id())
    assert run.status is CollectionRunStatus.QUEUED
    assert run.is_completed is False


def test_start_transitions_queued_to_running() -> None:
    run = CollectionRun(dataset_id=_dataset_id())
    run.start()
    assert run.status is CollectionRunStatus.RUNNING


def test_start_from_running_raises() -> None:
    run = CollectionRun(dataset_id=_dataset_id())
    run.start()
    with pytest.raises(DomainInvariantViolation):
        run.start()


def test_start_from_failed_raises_use_resume_instead() -> None:
    run = CollectionRun(dataset_id=_dataset_id())
    run.start()
    run.fail()
    with pytest.raises(DomainInvariantViolation):
        run.start()


def test_resume_from_failed_transitions_to_running() -> None:
    # line 567: "resumable from a `failed`/interrupted state"
    run = CollectionRun(dataset_id=_dataset_id())
    run.start()
    run.fail()
    run.resume()
    assert run.status is CollectionRunStatus.RUNNING


def test_resume_from_queued_raises() -> None:
    run = CollectionRun(dataset_id=_dataset_id())
    with pytest.raises(DomainInvariantViolation):
        run.resume()


def test_complete_from_running_transitions_to_completed() -> None:
    run = CollectionRun(dataset_id=_dataset_id())
    run.start()
    run.complete()
    assert run.status is CollectionRunStatus.COMPLETED
    assert run.is_completed is True


def test_complete_from_queued_raises() -> None:
    run = CollectionRun(dataset_id=_dataset_id())
    with pytest.raises(DomainInvariantViolation):
        run.complete()


def test_fail_from_running_transitions_to_failed() -> None:
    run = CollectionRun(dataset_id=_dataset_id())
    run.start()
    run.fail()
    assert run.status is CollectionRunStatus.FAILED


def test_fail_from_queued_raises() -> None:
    run = CollectionRun(dataset_id=_dataset_id())
    with pytest.raises(DomainInvariantViolation):
        run.fail()


@pytest.mark.parametrize("method_name", ["start", "resume", "complete", "fail"])
def test_completed_run_rejects_every_transition(method_name: str) -> None:
    # line 568: "Immutable once `completed`." -- the literal T-007 acceptance criterion for
    # this entity: no method may mutate a completed CollectionRun, full stop.
    run = CollectionRun(dataset_id=_dataset_id())
    run.start()
    run.complete()
    method = getattr(run, method_name)
    with pytest.raises(DomainInvariantViolation):
        method()
    assert run.status is CollectionRunStatus.COMPLETED


def test_two_runs_have_distinct_ids() -> None:
    a = CollectionRun(dataset_id=_dataset_id())
    b = CollectionRun(dataset_id=_dataset_id())
    assert a.id != b.id
