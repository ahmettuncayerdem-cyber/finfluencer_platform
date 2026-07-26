"""Tests for :mod:`finfluencer.scope` (Migration Step 3.1).

``resolve_scope()``/``persist_scope()`` are new and not yet called by
any pipeline stage - these tests exercise the module directly, the same
way ``tests/unit/test_migration/test_backfill_entity_model.py`` tests
``backfill_entity_model()`` in isolation before anything downstream
consumes it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from finfluencer.core.contracts import AnalysisScopeType
from finfluencer.scope import persist_scope, resolve_scope


class TestResolveScopeDeterminism:
    def test_scope_id_deterministic_for_identical_definition(self):
        s1 = resolve_scope(["c1", "c2"], scope_type=AnalysisScopeType.global_, criteria_version="v1")
        s2 = resolve_scope(["c1", "c2"], scope_type=AnalysisScopeType.global_, criteria_version="v1")
        assert s1.scope_id == s2.scope_id

    def test_resolved_hash_order_independent(self):
        s1 = resolve_scope(["c1", "c2", "c3"], scope_type=AnalysisScopeType.global_)
        s2 = resolve_scope(["c3", "c1", "c2"], scope_type=AnalysisScopeType.global_)
        assert s1.resolved_comment_ids_hash == s2.resolved_comment_ids_hash

    def test_resolved_hash_deduplicates(self):
        s1 = resolve_scope(["c1", "c2"], scope_type=AnalysisScopeType.global_)
        s2 = resolve_scope(["c1", "c1", "c2", "c2"], scope_type=AnalysisScopeType.global_)
        assert s1.resolved_comment_ids_hash == s2.resolved_comment_ids_hash

    def test_different_scope_type_different_scope_id(self):
        s1 = resolve_scope(["c1"], scope_type=AnalysisScopeType.global_)
        s2 = resolve_scope(["c1"], scope_type=AnalysisScopeType.entity, entity_keys=["gecer"])
        assert s1.scope_id != s2.scope_id

    def test_different_entity_keys_different_scope_id(self):
        s1 = resolve_scope(["c1"], scope_type=AnalysisScopeType.entity, entity_keys=["gecer"])
        s2 = resolve_scope(["c1"], scope_type=AnalysisScopeType.entity, entity_keys=["basaran"])
        assert s1.scope_id != s2.scope_id

    def test_entity_keys_order_does_not_affect_scope_id(self):
        s1 = resolve_scope(["c1"], scope_type=AnalysisScopeType.entity_set, entity_keys=["a", "b"])
        s2 = resolve_scope(["c1"], scope_type=AnalysisScopeType.entity_set, entity_keys=["b", "a"])
        assert s1.scope_id == s2.scope_id

    def test_different_filter_params_different_scope_id(self):
        s1 = resolve_scope(["c1"], scope_type=AnalysisScopeType.filtered, filter_params={"kw": "a"})
        s2 = resolve_scope(["c1"], scope_type=AnalysisScopeType.filtered, filter_params={"kw": "b"})
        assert s1.scope_id != s2.scope_id

    def test_membership_drift_same_scope_id_different_resolved_hash(self):
        """Same scope definition, more comments resolved later (e.g. new
        collection run) - scope_id must stay stable, resolved hash must not."""
        s1 = resolve_scope(["c1", "c2"], scope_type=AnalysisScopeType.global_, criteria_version="v1")
        s2 = resolve_scope(["c1", "c2", "c3"], scope_type=AnalysisScopeType.global_, criteria_version="v1")
        assert s1.scope_id == s2.scope_id
        assert s1.resolved_comment_ids_hash != s2.resolved_comment_ids_hash

    def test_empty_comment_ids_does_not_raise(self):
        scope = resolve_scope([], scope_type=AnalysisScopeType.global_)
        assert scope.resolved_comment_ids_hash  # still a valid, non-empty hash


class TestPersistScope:
    def test_creates_new_file(self, tmp_path: Path):
        scope = resolve_scope(["c1"], scope_type=AnalysisScopeType.global_)
        out = tmp_path / "analysis_scope.parquet"
        persist_scope(scope, out)
        assert out.exists()
        df = pd.read_parquet(out)
        assert len(df) == 1
        assert df.iloc[0]["scope_id"] == scope.scope_id

    def test_upserts_same_scope_id_not_duplicate_row(self, tmp_path: Path):
        out = tmp_path / "analysis_scope.parquet"
        s1 = resolve_scope(["c1", "c2"], scope_type=AnalysisScopeType.global_, criteria_version="v1")
        s2 = resolve_scope(["c1", "c2", "c3"], scope_type=AnalysisScopeType.global_, criteria_version="v1")
        persist_scope(s1, out)
        persist_scope(s2, out)
        df = pd.read_parquet(out)
        assert len(df) == 1
        assert df.iloc[0]["resolved_comment_ids_hash"] == s2.resolved_comment_ids_hash

    def test_distinct_scope_ids_produce_distinct_rows(self, tmp_path: Path):
        out = tmp_path / "analysis_scope.parquet"
        s1 = resolve_scope(["c1"], scope_type=AnalysisScopeType.global_)
        s2 = resolve_scope(["c1"], scope_type=AnalysisScopeType.entity, entity_keys=["gecer"])
        persist_scope(s1, out)
        persist_scope(s2, out)
        df = pd.read_parquet(out)
        assert len(df) == 2
        assert set(df["scope_id"]) == {s1.scope_id, s2.scope_id}

    def test_empty_filter_params_does_not_break_parquet_write(self, tmp_path: Path):
        """Regression guard: PyArrow cannot write a struct-typed column
        whose only observed value is an empty dict ({}) - filter_params
        is stored as a JSON string specifically to avoid this."""
        out = tmp_path / "analysis_scope.parquet"
        scope = resolve_scope(["c1"], scope_type=AnalysisScopeType.global_)  # filter_params={}
        persist_scope(scope, out)  # must not raise
        df = pd.read_parquet(out)
        assert json.loads(df.iloc[0]["filter_params"]) == {}

    def test_non_empty_filter_params_round_trips(self, tmp_path: Path):
        out = tmp_path / "analysis_scope.parquet"
        scope = resolve_scope(
            ["c1"], scope_type=AnalysisScopeType.filtered, filter_params={"keyword": "borsa"},
        )
        persist_scope(scope, out)
        df = pd.read_parquet(out)
        assert json.loads(df.iloc[0]["filter_params"]) == {"keyword": "borsa"}
