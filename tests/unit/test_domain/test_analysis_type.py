"""Tests for the AnalysisType entity (BACKLOG.md T-018; PRODUCT_ARCHITECTURE.md section 10.1,
lines 533-541).
"""

from __future__ import annotations

import pytest

from finfluencer.domain.entities import AnalysisType


def test_create_requires_non_empty_key() -> None:
    with pytest.raises(ValueError):
        AnalysisType(key="", version="1.0.0")


def test_create_requires_non_empty_version() -> None:
    with pytest.raises(ValueError):
        AnalysisType(key="topic_modeling", version="")


def test_create_stores_key_and_version() -> None:
    analysis_type = AnalysisType(key="topic_modeling", version="1.0.0")
    assert analysis_type.key == "topic_modeling"
    assert analysis_type.version == "1.0.0"


def test_two_instances_have_distinct_ids() -> None:
    a = AnalysisType(key="topic_modeling", version="1.0.0")
    b = AnalysisType(key="sentiment", version="1.0.0")
    assert a.id != b.id
