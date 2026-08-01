"""BACKLOG.md T-021 -- Verify AnalysisRun immutability and CollectionRun pinning.

"The first real test of section 10.1's pinning rule against actual code, not just Domain Model
theory." Every invariant exercised here is already implemented by T-018's `AnalysisRun` entity
(no new production code was written for T-021 -- see
`docs/implementation/T-021_ARCHITECTURE_INVARIANT_READINESS_REVIEW.md`); this file exists to
prove it exhaustively, not to add enforcement.

Complements, does not duplicate:
- `test_analysis_run.py` (T-018) -- general lifecycle/construction-validation coverage.
- `test_start_analysis_run_orchestrator.py` (T-020) -- proves the retry-creates-a-new-run
  behavior end to end through the real Infrastructure adapter.

This file's own angle: exhaustive, pinning-specific invariant coverage at the Domain layer alone
(no orchestrator, no Infrastructure), matching T-021's Effort-XS, verification-only scope.
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
    kwargs = dict(
        project_id=_project_id(),
        collection_run_id=_collection_run_id(),
        analysis_type_id=_analysis_type_id(),
        analysis_type_version="1.0.0",
    )
    kwargs.update(overrides)
    return AnalysisRun(**kwargs)


# ---------------------------------------------------------------------------
# "cannot be created without a valid CollectionRun reference"
# ---------------------------------------------------------------------------


def test_cannot_construct_without_a_collection_run_reference() -> None:
    with pytest.raises(ValueError, match="collection_run_id"):
        _make_run(collection_run_id=None)


@pytest.mark.parametrize(
    "missing_field", ["project_id", "collection_run_id", "analysis_type_id"],
)
def test_cannot_construct_with_any_pinning_reference_missing(missing_field: str) -> None:
    with pytest.raises(ValueError):
        _make_run(**{missing_field: None})


def test_cannot_construct_with_empty_analysis_type_version() -> None:
    # Not an EntityId reference, but still part of the AnalysisType pin (section 10.1 line 539:
    # "an AnalysisRun records which AnalysisType version produced it").
    with pytest.raises(ValueError, match="analysis_type_version"):
        _make_run(analysis_type_version="")


# ---------------------------------------------------------------------------
# "cannot be re-pointed after creation" -- no setter exists for any pinning field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field_name", ["project_id", "collection_run_id", "analysis_type_id", "analysis_type_version"],
)
def test_no_pinning_field_is_settable_after_construction(field_name: str) -> None:
    run = _make_run()
    with pytest.raises(AttributeError):
        setattr(run, field_name, "anything")


def test_pinning_fields_are_stable_across_every_lifecycle_transition() -> None:
    # The pin must not drift as a side effect of ordinary lifecycle methods -- proven by
    # capturing every pinning value before and after each transition.
    project_id = _project_id()
    collection_run_id = _collection_run_id()
    analysis_type_id = _analysis_type_id()
    run = AnalysisRun(
        project_id=project_id,
        collection_run_id=collection_run_id,
        analysis_type_id=analysis_type_id,
        analysis_type_version="1.0.0",
    )

    def _assert_pin_unchanged() -> None:
        assert run.project_id == project_id
        assert run.collection_run_id == collection_run_id
        assert run.analysis_type_id == analysis_type_id
        assert run.analysis_type_version == "1.0.0"

    _assert_pin_unchanged()
    run.start()
    _assert_pin_unchanged()
    run.complete()
    _assert_pin_unchanged()

    failed_run = _make_run()
    failed_run.start()
    failed_run.fail()
    assert failed_run.project_id is not None  # sanity: still constructed correctly
    assert failed_run.collection_run_id is not None


# ---------------------------------------------------------------------------
# "Immutable once completed" -- every field, not just status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method_name", ["start", "complete", "fail"])
def test_completed_run_rejects_every_transition_and_keeps_every_field(method_name: str) -> None:
    run = _make_run()
    project_id, collection_run_id = run.project_id, run.collection_run_id
    analysis_type_id, version = run.analysis_type_id, run.analysis_type_version

    run.start()
    run.complete()
    method = getattr(run, method_name)
    with pytest.raises(DomainInvariantViolation):
        method()

    assert run.status is AnalysisRunStatus.COMPLETED
    assert run.is_completed is True
    assert run.project_id == project_id
    assert run.collection_run_id == collection_run_id
    assert run.analysis_type_id == analysis_type_id
    assert run.analysis_type_version == version


# ---------------------------------------------------------------------------
# "Re-running analysis creates a new AnalysisRun rather than mutating an existing one"
# ---------------------------------------------------------------------------


def test_analysis_run_has_no_resume_method_at_all() -> None:
    # section 10.1 line 577: unlike CollectionRun, there is no resume path -- structurally
    # impossible to mutate a FAILED run back into RUNNING.
    run = _make_run()
    assert not hasattr(AnalysisRun, "resume")
    assert not hasattr(run, "resume")


def test_a_failed_run_stays_failed_forever_no_matter_what_is_called_on_it() -> None:
    run = _make_run()
    run.start()
    run.fail()

    for method_name in ("start", "fail"):
        with pytest.raises(DomainInvariantViolation):
            getattr(run, method_name)()
        assert run.status is AnalysisRunStatus.FAILED

    # complete() from FAILED is also rejected -- FAILED is not RUNNING.
    with pytest.raises(DomainInvariantViolation):
        run.complete()
    assert run.status is AnalysisRunStatus.FAILED


def test_retrying_after_failure_means_constructing_a_distinct_instance_with_the_same_pin() -> None:
    project_id = _project_id()
    collection_run_id = _collection_run_id()
    analysis_type_id = _analysis_type_id()

    failed_run = AnalysisRun(
        project_id=project_id, collection_run_id=collection_run_id,
        analysis_type_id=analysis_type_id, analysis_type_version="1.0.0",
    )
    failed_run.start()
    failed_run.fail()

    retry_run = AnalysisRun(
        project_id=project_id, collection_run_id=collection_run_id,
        analysis_type_id=analysis_type_id, analysis_type_version="1.0.0",
    )

    # A genuinely distinct instance/id ...
    assert retry_run.id != failed_run.id
    assert retry_run is not failed_run
    # ... pinned to the identical CollectionRun/AnalysisType the failed attempt was.
    assert retry_run.collection_run_id == failed_run.collection_run_id
    assert retry_run.analysis_type_id == failed_run.analysis_type_id
    assert retry_run.analysis_type_version == failed_run.analysis_type_version
    # The old instance is completely untouched by the new one's existence.
    assert failed_run.status is AnalysisRunStatus.FAILED
    retry_run.start()
    retry_run.complete()
    assert failed_run.status is AnalysisRunStatus.FAILED  # still, after the retry succeeds
