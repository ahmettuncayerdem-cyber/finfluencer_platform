"""Tests for InterpretationRecord entity (BACKLOG.md T-024)."""

from __future__ import annotations

import uuid

import pytest

from finfluencer.domain.entities import (
    EntityId,
    InterpretationRecord,
    InterpretationRecordKind,
)


def _analysis_run_id() -> EntityId:
    return EntityId(uuid.uuid4())


def _make_record(**overrides) -> InterpretationRecord:
    kwargs = dict(
        analysis_run_id=_analysis_run_id(),
        kind=InterpretationRecordKind.RAW_RESULT_SNAPSHOT,
        selector="topics.top_words[0]",
        content='{"topic_id": 0, "words": ["enflasyon", "faiz"]}',
    )
    kwargs.update(overrides)
    return InterpretationRecord(**kwargs)


def test_construction_succeeds_with_all_required_fields() -> None:
    record = _make_record()
    assert record.kind is InterpretationRecordKind.RAW_RESULT_SNAPSHOT
    assert record.selector == "topics.top_words[0]"
    assert record.content


def test_cannot_construct_without_analysis_run_id() -> None:
    with pytest.raises(ValueError, match="analysis_run_id"):
        _make_record(analysis_run_id=None)


def test_cannot_construct_without_kind() -> None:
    with pytest.raises(ValueError, match="kind"):
        _make_record(kind=None)


def test_cannot_construct_with_empty_selector() -> None:
    with pytest.raises(ValueError, match="selector"):
        _make_record(selector="")


def test_cannot_construct_with_empty_content() -> None:
    with pytest.raises(ValueError, match="content"):
        _make_record(content="")


def test_only_raw_result_snapshot_kind_exists() -> None:
    # section 10.0: `ai_generated` is deliberately not implemented in this task's scope.
    assert [k.value for k in InterpretationRecordKind] == ["raw_result_snapshot"]


def test_no_pinning_field_is_settable_after_construction() -> None:
    record = _make_record()
    for field_name in ("analysis_run_id", "kind", "selector", "content"):
        with pytest.raises(AttributeError):
            setattr(record, field_name, "anything")


def test_record_has_no_mutating_methods_at_all() -> None:
    # section 10.1, line 588: "No API path may update an existing InterpretationRecord" --
    # verified structurally: no public method other than the read-only properties exists.
    record = _make_record()
    public_callables = [
        name for name in dir(record)
        if not name.startswith("_") and callable(getattr(record, name))
    ]
    assert public_callables == []
