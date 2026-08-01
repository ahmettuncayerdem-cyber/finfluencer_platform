"""Tests for the AnalysisRun entity (BACKLOG.md T-018; PRODUCT_ARCHITECTURE.md section 10.1,
lines 573-581) -- especially the "Immutable once `completed`" invariant (line 578), same
reasoning as `CollectionRun` (line 568), and the absence of a `resume()` method: unlike
`CollectionRun`, a failed `AnalysisRun` is retried by constructing a new instance, never by
resuming the old one (line 577).
"""

from __future__ import annotations

import uuid

import pytest

from finfluencer.domain.entities import (
    AnalysisRun,
    AnalysisRunStatus,
    DomainInvariantViolation,
    EntityId,
)


def _project_id() -> EntityId:
    return EntityId(uuid.uuid4())


def _collection_run_id() -> EntityId:
    return EntityId(uuid.uuid4())


def _analysis_type_id() -> EntityId:
    return EntityId(uuid.uuid4())


def _make_run(**overrides) -> AnalysisRun:
    kwargs = {
        "project_id": _project_id(),
        "collection_run_id": _collection_run_id(),
        "analysis_type_id": _analysis_type_id(),
        "analysis_type_version": "1.0.0",
    }
    kwargs.update(overrides)
    return AnalysisRun(**kwargs)


def test_create_requires_project_id() -> None:
    with pytest.raises(ValueError):
        _make_run(project_id=None)


def test_create_requires_collection_run_id() -> None:
    with pytest.raises(ValueError):
        _make_run(collection_run_id=None)


def test_create_requires_analysis_type_id() -> None:
    with pytest.raises(ValueError):
        _make_run(analysis_type_id=None)


def test_create_requires_non_empty_analysis_type_version() -> None:
    with pytest.raises(ValueError):
        _make_run(analysis_type_version="")


def test_create_is_queued_by_default() -> None:
    run = _make_run()
    assert run.status is AnalysisRunStatus.QUEUED
    assert run.is_completed is False


def test_start_transitions_queued_to_running() -> None:
    run = _make_run()
    run.start()
    assert run.status is AnalysisRunStatus.RUNNING


def test_start_from_running_raises() -> None:
    run = _make_run()
    run.start()
    with pytest.raises(DomainInvariantViolation):
        run.start()


def test_start_from_failed_raises() -> None:
    # Unlike CollectionRun, AnalysisRun has no resume() -- a failed run stays failed; retrying
    # means constructing a brand new AnalysisRun (section 10.1, line 577).
    run = _make_run()
    run.start()
    run.fail()
    with pytest.raises(DomainInvariantViolation):
        run.start()


def test_analysis_run_has_no_resume_method() -> None:
    run = _make_run()
    assert not hasattr(run, "resume")


def test_complete_from_running_transitions_to_completed() -> None:
    run = _make_run()
    run.start()
    run.complete()
    assert run.status is AnalysisRunStatus.COMPLETED
    assert run.is_completed is True


def test_complete_from_queued_raises() -> None:
    run = _make_run()
    with pytest.raises(DomainInvariantViolation):
        run.complete()


def test_fail_from_running_transitions_to_failed() -> None:
    run = _make_run()
    run.start()
    run.fail()
    assert run.status is AnalysisRunStatus.FAILED


def test_fail_from_queued_raises() -> None:
    run = _make_run()
    with pytest.raises(DomainInvariantViolation):
        run.fail()


@pytest.mark.parametrize("method_name", ["start", "complete", "fail"])
def test_completed_run_rejects_every_transition(method_name: str) -> None:
    # line 578: "Immutable once `completed`." -- T-018's own explicit acceptance criterion:
    # "a test that attempts to mutate a completed AnalysisRun and confirms it fails."
    run = _make_run()
    run.start()
    run.complete()
    method = getattr(run, method_name)
    with pytest.raises(DomainInvariantViolation):
        method()
    assert run.status is AnalysisRunStatus.COMPLETED


def test_two_runs_have_distinct_ids() -> None:
    a = _make_run()
    b = _make_run()
    assert a.id != b.id


def test_collection_run_id_is_not_settable_after_construction() -> None:
    # section 10.1, line 576: pinning to a specific CollectionRun, "not a moving target" --
    # there is deliberately no setter; this test documents that as an explicit contract, not
    # an accident of omission. (T-021 covers the fuller pinning-verification pass separately.)
    run = _make_run()
    with pytest.raises(AttributeError):
        run.collection_run_id = _collection_run_id()  # type: ignore[misc]
