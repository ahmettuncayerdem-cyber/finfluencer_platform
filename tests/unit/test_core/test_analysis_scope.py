"""Tests for the ``AnalysisScope`` contract (Migration Step 3.1).

Covers: the new contract's own validation, the backward-compatible
``legacy_configuration_label()`` alias, and - the invariant this step is
explicitly required to preserve - that ``TopicRecord``/
``TopicSentimentRecord``/``TopicEvolutionRecord`` continue to construct
exactly as before when ``scope_id`` is omitted (existing pipeline code,
unchanged, never passes it).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from finfluencer.core.contracts import (
    AnalysisScope,
    AnalysisScopeType,
    TopicEvolutionRecord,
    TopicRecord,
    TopicSentimentRecord,
)


def _scope(**overrides) -> AnalysisScope:
    defaults = dict(
        scope_id="abc123",
        scope_type=AnalysisScopeType.global_,
        resolved_comment_ids_hash="deadbeef",
        resolved_at="2026-07-18T00:00:00Z",
        criteria_version="v1",
    )
    defaults.update(overrides)
    return AnalysisScope(**defaults)


class TestAnalysisScopeValidation:
    def test_minimal_construction(self):
        scope = _scope()
        assert scope.scope_id == "abc123"
        assert scope.entity_keys == []
        assert scope.filter_params == {}

    def test_rejects_unknown_fields(self):
        with pytest.raises(ValidationError):
            _scope(unexpected_field="nope")

    def test_rejects_empty_scope_id(self):
        with pytest.raises(ValidationError):
            _scope(scope_id="")

    def test_rejects_empty_resolved_hash(self):
        with pytest.raises(ValidationError):
            _scope(resolved_comment_ids_hash="")

    def test_rejects_empty_criteria_version(self):
        with pytest.raises(ValidationError):
            _scope(criteria_version="")

    def test_entity_set_and_filtered_scope_types_accepted(self):
        # New expressiveness this migration unlocks - not reachable from
        # any pipeline stage yet, but the contract itself must accept it.
        assert _scope(scope_type=AnalysisScopeType.entity_set).scope_type == (
            AnalysisScopeType.entity_set
        )
        assert _scope(scope_type=AnalysisScopeType.filtered).scope_type == (
            AnalysisScopeType.filtered
        )


class TestLegacyConfigurationLabel:
    def test_global_maps_to_pooled(self):
        assert _scope(scope_type=AnalysisScopeType.global_).legacy_configuration_label() == (
            "pooled"
        )

    def test_single_entity_maps_to_within_analyst(self):
        scope = _scope(scope_type=AnalysisScopeType.entity, entity_keys=["gecer"])
        assert scope.legacy_configuration_label() == "within_analyst"

    def test_entity_with_zero_keys_raises(self):
        scope = _scope(scope_type=AnalysisScopeType.entity, entity_keys=[])
        with pytest.raises(ValueError, match="no pre-migration"):
            scope.legacy_configuration_label()

    def test_entity_with_multiple_keys_raises(self):
        scope = _scope(scope_type=AnalysisScopeType.entity, entity_keys=["gecer", "basaran"])
        with pytest.raises(ValueError, match="no pre-migration"):
            scope.legacy_configuration_label()

    def test_entity_set_raises(self):
        scope = _scope(scope_type=AnalysisScopeType.entity_set, entity_keys=["gecer", "basaran"])
        with pytest.raises(ValueError, match="no pre-migration"):
            scope.legacy_configuration_label()

    def test_filtered_raises(self):
        scope = _scope(scope_type=AnalysisScopeType.filtered, filter_params={"keyword": "borsa"})
        with pytest.raises(ValueError, match="no pre-migration"):
            scope.legacy_configuration_label()


class TestBackwardCompatibleRecordConstruction:
    """The invariant Step 3.1 is required to preserve: existing pipeline
    code (topics/pipeline.py, analysis/topic_sentiment.py), which never
    passes ``scope_id``, must continue to construct these records
    exactly as it does today."""

    def test_topic_record_without_scope_id_unchanged(self):
        record = TopicRecord(
            comment_id="c1", topic_id=0, topic_prob=0.9, configuration="pooled",
        )
        assert record.scope_id is None
        assert record.configuration == "pooled"

    def test_topic_sentiment_record_without_scope_id_unchanged(self):
        record = TopicSentimentRecord(
            configuration="pooled", topic_id=0, n_comments=1,
            n_positive=1, n_negative=0, n_pseudo_neutral=0,
        )
        assert record.scope_id is None
        assert record.analyst_key is None

    def test_topic_evolution_record_without_scope_id_unchanged(self):
        record = TopicEvolutionRecord(
            configuration="pooled", topic_id=0, time_bin="2024-01-01T00:00:00Z", frequency=1,
        )
        assert record.scope_id is None

    def test_topic_record_scope_id_is_optional_settable(self):
        # Not exercised by any pipeline code yet (Step 3.1 status), but
        # the field must accept a value once a future step sets one.
        record = TopicRecord(
            comment_id="c1", topic_id=0, topic_prob=0.9,
            configuration="pooled", scope_id="abc123",
        )
        assert record.scope_id == "abc123"
