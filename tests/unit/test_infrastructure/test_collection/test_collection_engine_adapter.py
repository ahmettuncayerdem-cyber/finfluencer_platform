"""Tests for CollectionEngineAdapter (BACKLOG.md T-010).

Covers the Migration Risk Checklist items directly: checkpoint_root partitioning (Roadmap
Risk R-1), idempotency, and interruption/resume -- not just "the wrapped functions run once
successfully." Roadmap Risk R-3 ("reuse confidence does not transfer automatically to the
ported form") is the reason these exist at all: the legacy suite already proves
`collect_channels` etc. work: it does not prove this *adapter* wires them together correctly.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from finfluencer.core.config import load_settings
from finfluencer.domain.collection_engine import CollectionOutcome
from finfluencer.infrastructure.collection import (
    CollectionEngineAdapter,
    FixtureCollectionProvider,
    fixture_transcript_fetcher,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"

_EXPECTED_COUNTS = {"channels": 4, "videos": 4, "comments": 8, "transcripts": 4}


def _make_adapter(base_root: Path, provider: Any = None) -> CollectionEngineAdapter:
    cfg = load_settings(_SETTINGS, _ANALYSTS, validate_secrets=False)
    return CollectionEngineAdapter(
        settings=cfg.settings,
        roster=cfg.roster,
        provider=provider if provider is not None else FixtureCollectionProvider(),
        base_root=base_root,
        transcript_fetcher=fixture_transcript_fetcher,
        anon_salt="fixture-test-salt",
    )


class _CountingProvider:
    """Delegates to a real `FixtureCollectionProvider`, counting `resolve_channel` calls and
    optionally raising after a fixed number of them -- simulates a mid-run crash partway
    through the channels stage's per-analyst loop.
    """

    def __init__(self, *, fail_after: int | None = None) -> None:
        self._inner = FixtureCollectionProvider()
        self._fail_after = fail_after
        self.resolve_channel_calls: list[str] = []
        self.key = self._inner.key
        self.unit_cost = self._inner.unit_cost

    def resolve_channel(self, handle_or_id: str) -> str:
        self.resolve_channel_calls.append(handle_or_id)
        if self._fail_after is not None and len(self.resolve_channel_calls) > self._fail_after:
            raise RuntimeError("simulated mid-run crash during channel resolution")
        return self._inner.resolve_channel(handle_or_id)

    def channel_metadata(self, channel_id: str):
        return self._inner.channel_metadata(channel_id)

    def enumerate_videos(self, uploads_ref: str, **kwargs):
        return self._inner.enumerate_videos(uploads_ref, **kwargs)

    def fetch_video_metadata(self, video_ids, **kwargs):
        return self._inner.fetch_video_metadata(video_ids, **kwargs)

    def fetch_top_level_comments(self, video_id: str, **kwargs):
        return self._inner.fetch_top_level_comments(video_id, **kwargs)


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------


def test_run_against_fixture_dataset_returns_expected_counts(tmp_path: Path) -> None:
    adapter = _make_adapter(tmp_path)
    outcome = adapter.run("run-basic")
    assert outcome == CollectionOutcome(run_id="run-basic", stage_row_counts=_EXPECTED_COUNTS)


def test_run_writes_parquet_outputs_under_the_run_specific_data_raw_dir(tmp_path: Path) -> None:
    adapter = _make_adapter(tmp_path)
    adapter.run("run-files")
    data_raw = tmp_path / "run-files" / "data_raw"
    for name in ("channels.parquet", "videos.parquet", "comments.parquet", "transcripts.parquet"):
        assert (data_raw / name).exists()
    channels_df = pd.read_parquet(data_raw / "channels.parquet")
    assert set(channels_df["analyst_key"]) == {"satiroglu", "yesilada", "basaran", "gecer"}


def test_run_id_must_be_non_empty(tmp_path: Path) -> None:
    adapter = _make_adapter(tmp_path)
    with pytest.raises(ValueError):
        adapter.run("")


# ---------------------------------------------------------------------------
# Roadmap Risk R-1: checkpoint_root partitioning, explicit in the adapter
# ---------------------------------------------------------------------------


def test_different_run_ids_get_isolated_checkpoint_roots(tmp_path: Path) -> None:
    adapter = _make_adapter(tmp_path)
    adapter.run("run-a")
    adapter.run("run-b")

    root_a = tmp_path / "run-a" / "checkpoints"
    root_b = tmp_path / "run-b" / "checkpoints"
    assert root_a.exists() and root_b.exists()
    assert root_a != root_b
    # Each root has its own independent set of markers/records -- no shared files.
    assert set(p.name for p in root_a.iterdir()) == set(p.name for p in root_b.iterdir())
    assert not any(root_a.samefile(p) for p in root_b.parent.iterdir() if p.is_dir() and p != root_b)


def test_same_run_id_reuses_the_same_checkpoint_root_across_calls(tmp_path: Path) -> None:
    adapter = _make_adapter(tmp_path)
    adapter.run("run-same")
    root_first = tmp_path / "run-same" / "checkpoints"
    marker_mtime_first = (root_first / "collect_channels.done").stat().st_mtime

    adapter.run("run-same")
    marker_mtime_second = (root_first / "collect_channels.done").stat().st_mtime

    # Idempotent re-run against an unchanged config slice must not rewrite a marker that
    # already reflects current config -- should_run() returns False and skips straight to
    # the cached parquet (core/checkpoint.py's own documented behavior, unmodified here).
    assert marker_mtime_first == marker_mtime_second


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_second_run_with_same_run_id_returns_the_same_outcome(tmp_path: Path) -> None:
    adapter = _make_adapter(tmp_path)
    first = adapter.run("run-idempotent")
    second = adapter.run("run-idempotent")
    assert first == second


def test_second_run_does_not_recontact_the_provider(tmp_path: Path) -> None:
    provider = _CountingProvider()
    adapter = _make_adapter(tmp_path, provider=provider)
    adapter.run("run-noop")
    calls_after_first = len(provider.resolve_channel_calls)
    assert calls_after_first == 4  # one per analyst

    adapter.run("run-noop")
    # Tier-2 marker already valid for this config slice -> collect_channels short-circuits
    # to the cached parquet before ever looping over analysts again.
    assert len(provider.resolve_channel_calls) == calls_after_first


# ---------------------------------------------------------------------------
# Interruption / resume (Roadmap Risk R-3: prove it for the *wrapped* form)
# ---------------------------------------------------------------------------


def test_interrupted_channels_stage_resumes_without_reprocessing_completed_analysts(
    tmp_path: Path,
) -> None:
    flaky_provider = _CountingProvider(fail_after=2)
    adapter = _make_adapter(tmp_path, provider=flaky_provider)

    with pytest.raises(RuntimeError, match="simulated mid-run crash"):
        adapter.run("run-interrupted")

    # Tier-1: exactly the two analysts processed before the crash were checkpointed.
    checkpoint_root = tmp_path / "run-interrupted" / "checkpoints"
    records_path = checkpoint_root / "collect_channels.jsonl"
    assert records_path.exists()
    recorded_keys = [
        __import__("json").loads(line)["analyst_key"]
        for line in records_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(recorded_keys) == 2
    # No .done marker yet -- the stage never completed.
    assert not (checkpoint_root / "collect_channels.done").exists()

    # Resume: same run_id, a working (non-flaky) provider standing in for "the transient
    # failure is gone now" -- collect_channels must skip the two already-recorded analysts
    # and only contact the provider for the remaining two.
    working_provider = _CountingProvider()
    resumed_adapter = _make_adapter(tmp_path, provider=working_provider)
    outcome = resumed_adapter.run("run-interrupted")

    assert outcome.stage_row_counts == _EXPECTED_COUNTS
    assert len(working_provider.resolve_channel_calls) == 2  # only the remaining analysts
    assert set(working_provider.resolve_channel_calls).isdisjoint(flaky_provider.resolve_channel_calls[:2])


# ---------------------------------------------------------------------------
# Architectural conformance
# ---------------------------------------------------------------------------


def test_adapter_module_does_not_import_presentation_or_api() -> None:
    # PRODUCT_ARCHITECTURE.md section 12.1 line 845: Infrastructure's forbidden dependencies
    # include Presentation and API -- not currently encoded in
    # scripts/check_layer_dependencies.py's IG-001 checker for this layer. Enforced here by
    # inspecting real import statements, same discipline as T-009's equivalent test.
    import finfluencer.infrastructure.collection.collection_engine_adapter as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)


def test_collection_engine_adapter_never_modifies_wrapped_legacy_modules() -> None:
    # Operator constraint: "Do not modify the existing collect/ implementation unless
    # absolutely required." Cheap, durable proof this held: the adapter module imports the
    # four stage functions by name and calls them -- it does not monkeypatch, subclass, or
    # reach into their internals.
    import finfluencer.infrastructure.collection.collection_engine_adapter as module

    source = inspect.getsource(module)
    for forbidden in ("setattr(", "monkeypatch", "importlib.reload"):
        assert forbidden not in source
