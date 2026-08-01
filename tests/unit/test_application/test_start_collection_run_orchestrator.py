"""Tests for StartCollectionRunOrchestrator (BACKLOG.md T-011).

The first Walking Skeleton use case: these tests exercise Application -> Domain ->
(Domain-owned `ICollectionEngine`/`ICollectionRunRepository` interfaces) -> a real T-010
`CollectionEngineAdapter` -> the real Legacy Collection Engine, end to end -- not mocks standing
in for the whole chain. Only the repository is a fake (Persistence remains abstract, per operator
instruction); everything from the orchestrator down to `collect/*` is the genuine article.
"""

from __future__ import annotations

import ast
import inspect
import uuid
from pathlib import Path
from typing import Any

import pytest

from finfluencer.application.orchestrators import (
    StartCollectionRunCommand,
    StartCollectionRunOrchestrator,
    StartCollectionRunResult,
)
from finfluencer.core.config import load_settings
from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.collection_run import CollectionRun, CollectionRunStatus
from finfluencer.infrastructure.collection import (
    CollectionEngineAdapter,
    FixtureCollectionProvider,
    fixture_transcript_fetcher,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"

_EXPECTED_COUNTS = {"channels": 4, "videos": 4, "comments": 8, "transcripts": 4}


class FakeCollectionRunRepository:
    """In-memory test double for `ICollectionRunRepository` -- not a Persistence Layer
    implementation. Lives in test code, never under `src/finfluencer/persistence/`.

    Stores `idempotency_key` as its own bookkeeping alongside the `CollectionRun` object
    reference, exactly as this interface's docstring describes -- the `CollectionRun`'s own
    public shape is untouched.
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[EntityId, str], CollectionRun] = {}
        self.add_calls = 0

    def add(self, collection_run: CollectionRun, *, idempotency_key: str) -> None:
        self.add_calls += 1
        self._by_key[(collection_run.dataset_id, idempotency_key)] = collection_run

    def get_by_idempotency_key(
        self, dataset_id: EntityId, idempotency_key: str
    ) -> CollectionRun | None:
        return self._by_key.get((dataset_id, idempotency_key))


class _CountingProvider:
    """Delegates to a real `FixtureCollectionProvider`, optionally raising after a fixed
    number of `resolve_channel` calls -- same pattern as T-010's own adapter tests, reused
    here to prove the *orchestrator* (not just the adapter in isolation) handles a mid-run
    crash correctly: `run.fail()`, exception propagation, and a genuine resume.
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


def _make_engine(base_root: Path, provider: Any = None) -> CollectionEngineAdapter:
    cfg = load_settings(_SETTINGS, _ANALYSTS, validate_secrets=False)
    return CollectionEngineAdapter(
        settings=cfg.settings,
        roster=cfg.roster,
        provider=provider if provider is not None else FixtureCollectionProvider(),
        base_root=base_root,
        transcript_fetcher=fixture_transcript_fetcher,
        anon_salt="fixture-test-salt",
    )


def _dataset_id() -> EntityId:
    return EntityId(uuid.uuid4())


# ---------------------------------------------------------------------------
# Happy path / Walking Skeleton proof
# ---------------------------------------------------------------------------


def test_execute_runs_collection_end_to_end_and_completes(tmp_path: Path) -> None:
    repo = FakeCollectionRunRepository()
    orchestrator = StartCollectionRunOrchestrator(
        collection_run_repository=repo, collection_engine=_make_engine(tmp_path)
    )
    dataset_id = _dataset_id()

    result = orchestrator.execute(
        StartCollectionRunCommand(dataset_id=dataset_id, idempotency_key="key-1")
    )

    assert isinstance(result, StartCollectionRunResult)
    assert result.dataset_id == dataset_id
    assert result.status == "completed"
    assert result.stage_row_counts == _EXPECTED_COUNTS
    assert repo.add_calls == 1


def test_execute_uses_the_collection_runs_own_id_as_the_engine_run_id(tmp_path: Path) -> None:
    # Constraint #7: "Every CollectionRun must own its own checkpoint_root exactly as defined
    # by ADR-0002" -- proven by checking the adapter actually created a checkpoint_root
    # subtree named after the CollectionRun's own id, not some other identifier.
    repo = FakeCollectionRunRepository()
    orchestrator = StartCollectionRunOrchestrator(
        collection_run_repository=repo, collection_engine=_make_engine(tmp_path)
    )

    result = orchestrator.execute(
        StartCollectionRunCommand(dataset_id=_dataset_id(), idempotency_key="key-checkpoint")
    )

    checkpoint_root = tmp_path / str(result.id) / "checkpoints"
    assert checkpoint_root.exists()
    assert (checkpoint_root / "collect_channels.done").exists()


# ---------------------------------------------------------------------------
# Idempotency / duplicate-dispatch (BACKLOG.md T-011 Verification: "duplicate-dispatch test")
# ---------------------------------------------------------------------------


def test_duplicate_dispatch_with_same_key_does_not_create_a_second_run(tmp_path: Path) -> None:
    repo = FakeCollectionRunRepository()
    provider = _CountingProvider()
    orchestrator = StartCollectionRunOrchestrator(
        collection_run_repository=repo,
        collection_engine=_make_engine(tmp_path, provider=provider),
    )
    dataset_id = _dataset_id()
    command = StartCollectionRunCommand(dataset_id=dataset_id, idempotency_key="dup-key")

    first = orchestrator.execute(command)
    second = orchestrator.execute(command)

    assert first.id == second.id
    assert repo.add_calls == 1  # only ever persisted once
    assert second.status == "completed"
    # The engine was never re-invoked for the duplicate dispatch: no additional
    # resolve_channel calls beyond the first, real execution.
    assert len(provider.resolve_channel_calls) == 4


def test_duplicate_dispatch_with_different_keys_creates_two_distinct_runs(tmp_path: Path) -> None:
    repo = FakeCollectionRunRepository()
    orchestrator = StartCollectionRunOrchestrator(
        collection_run_repository=repo, collection_engine=_make_engine(tmp_path)
    )
    dataset_id = _dataset_id()

    a = orchestrator.execute(
        StartCollectionRunCommand(dataset_id=dataset_id, idempotency_key="key-a")
    )
    b = orchestrator.execute(
        StartCollectionRunCommand(dataset_id=dataset_id, idempotency_key="key-b")
    )

    assert a.id != b.id
    assert repo.add_calls == 2


def test_same_idempotency_key_different_datasets_do_not_collide(tmp_path: Path) -> None:
    # ICollectionRunRepository is keyed on (dataset_id, idempotency_key), not the key alone.
    repo = FakeCollectionRunRepository()
    orchestrator = StartCollectionRunOrchestrator(
        collection_run_repository=repo, collection_engine=_make_engine(tmp_path)
    )

    a = orchestrator.execute(
        StartCollectionRunCommand(dataset_id=_dataset_id(), idempotency_key="shared-key")
    )
    b = orchestrator.execute(
        StartCollectionRunCommand(dataset_id=_dataset_id(), idempotency_key="shared-key")
    )

    assert a.id != b.id
    assert repo.add_calls == 2


# ---------------------------------------------------------------------------
# Failure propagation and resume
# ---------------------------------------------------------------------------


def test_execute_marks_the_run_failed_and_reraises_on_a_mid_run_crash(tmp_path: Path) -> None:
    repo = FakeCollectionRunRepository()
    flaky_provider = _CountingProvider(fail_after=2)
    orchestrator = StartCollectionRunOrchestrator(
        collection_run_repository=repo,
        collection_engine=_make_engine(tmp_path, provider=flaky_provider),
    )
    dataset_id = _dataset_id()

    with pytest.raises(RuntimeError, match="simulated mid-run crash"):
        orchestrator.execute(
            StartCollectionRunCommand(dataset_id=dataset_id, idempotency_key="will-fail")
        )

    stored = repo.get_by_idempotency_key(dataset_id, "will-fail")
    assert stored is not None
    assert stored.status is CollectionRunStatus.FAILED


def test_duplicate_dispatch_of_a_failed_run_resumes_via_domain_resume_and_completes(
    tmp_path: Path,
) -> None:
    # Interruption/resume test, exercised through the orchestrator (not the adapter directly):
    # first dispatch crashes partway; a second dispatch with the SAME idempotency key must
    # call CollectionRun.resume() (Domain), reuse the same run_id/checkpoint_root (ADR-0002),
    # and finish successfully without reprocessing already-checkpointed analysts.
    repo = FakeCollectionRunRepository()
    flaky_provider = _CountingProvider(fail_after=2)
    dataset_id = _dataset_id()
    command = StartCollectionRunCommand(dataset_id=dataset_id, idempotency_key="resume-key")

    orchestrator_one = StartCollectionRunOrchestrator(
        collection_run_repository=repo,
        collection_engine=_make_engine(tmp_path, provider=flaky_provider),
    )
    with pytest.raises(RuntimeError, match="simulated mid-run crash"):
        orchestrator_one.execute(command)

    failed_run = repo.get_by_idempotency_key(dataset_id, "resume-key")
    assert failed_run is not None
    assert failed_run.status is CollectionRunStatus.FAILED

    # A fresh orchestrator instance (simulating a new process/request), same repository (same
    # backing store) and a working provider standing in for "the transient failure is gone."
    working_provider = _CountingProvider()
    orchestrator_two = StartCollectionRunOrchestrator(
        collection_run_repository=repo,
        collection_engine=_make_engine(tmp_path, provider=working_provider),
    )
    result = orchestrator_two.execute(command)

    assert result.id == failed_run.id
    assert result.status == "completed"
    assert result.stage_row_counts == _EXPECTED_COUNTS
    # Only the two analysts not yet checkpointed before the crash were recontacted.
    assert len(working_provider.resolve_channel_calls) == 2
    assert repo.add_calls == 1  # never created a second CollectionRun


# ---------------------------------------------------------------------------
# Architectural conformance (IG-001, honored textually where the checker script is silent)
# ---------------------------------------------------------------------------


def test_orchestrator_module_does_not_import_presentation_api_or_infrastructure() -> None:
    # Application's forbidden dependencies (section 12.1 lines 828-829) include Presentation,
    # API, and any concrete Infrastructure class -- not currently encoded in
    # scripts/check_layer_dependencies.py's IG-001 checker for the `application` layer. Same
    # ast-based enforcement discipline as T-009's equivalent test.
    import finfluencer.application.orchestrators.start_collection_run as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)
    assert not any(m.startswith("finfluencer.infrastructure") for m in imported_modules)
    assert not any(m.startswith("finfluencer.collect") for m in imported_modules)
