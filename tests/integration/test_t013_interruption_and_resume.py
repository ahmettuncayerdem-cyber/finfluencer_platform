"""T-013 -- Prove interruption and checkpoint resume (BACKLOG.md T-013).

`IMPLEMENTATION_ROADMAP.md` line 63: "Sprint 0's seven artifacts, then Milestone 1: create a
Project, run a Collection against a canned fixture dataset, prove interruption and checkpoint
resume end to end." `PRODUCT_ARCHITECTURE.md` section 1.2's reproducibility promise is the
architectural grounding BACKLOG.md's own T-013 entry cites.

Distinct from T-010's and T-011's own interruption/resume tests: those simulate a crash with an
in-process Python exception. This test kills a real OS process with `SIGKILL` mid-run --
`SIGKILL` cannot be caught or handled, so this is a genuine, uncontrolled interruption, not a
cooperative one. Two things are proven, at the two levels the Walking Skeleton actually spans:

1. Infrastructure level: the real, killed subprocess leaves correct, uncorrupted partial
   checkpoint state on disk -- no data loss, nothing half-written.
2. Application level (Walking Skeleton): `StartCollectionRunOrchestrator` (T-011), given a
   repository record showing this run already `failed`, resumes it via `CollectionRun.resume()`
   (Domain, T-007) and the same `run_id` -- reusing exactly the on-disk state the real crash
   produced -- and completes with the correct, non-duplicated final data.

No new Domain/Application/Infrastructure abstraction is introduced by this task: every class
used here (`CollectionEngineAdapter`, `StartCollectionRunOrchestrator`, `CollectionRun`,
`FixtureCollectionProvider`) already existed before this test was written. The only new artifact
is `_t013_worker.py`, a test-only subprocess entry point -- not `src/finfluencer` code.

Scope note, flagged rather than silently assumed: the repository record showing this run as
`failed` is pre-seeded directly (the same "test double stands in for Persistence" pattern used
throughout T-009/T-010/T-011), modeling a real system in which the orchestrator/API process
(holding the Persistence-backed `CollectionRun` record) stays alive while a separate *worker*
process actually executes collection and is what crashes (`PRODUCT_ARCHITECTURE.md` section
12.2's `IJobDispatcher`/worker model). This test does not prove the orchestrator's *own* process
surviving a real kill -- that would require a real Persistence implementation, which remains out
of Sprint 0 scope and is not introduced here.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pandas as pd
import pytest

from finfluencer.application.orchestrators import (
    StartCollectionRunCommand,
    StartCollectionRunOrchestrator,
)
from finfluencer.core.config import load_settings
from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.collection_run import CollectionRun, CollectionRunStatus
from finfluencer.infrastructure.collection import (
    CollectionEngineAdapter,
    FixtureCollectionProvider,
    fixture_transcript_fetcher,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"
_WORKER = Path(__file__).resolve().parent / "_t013_worker.py"

_EXPECTED_COUNTS = {"channels": 4, "videos": 4, "comments": 8, "transcripts": 4}
_ANALYST_KEYS = {"satiroglu", "yesilada", "basaran", "gecer"}

_POLL_INTERVAL_SECONDS = 0.02
_POLL_TIMEOUT_SECONDS = 10.0
_WORKER_DELAY_SECONDS = 0.2


class FakeCollectionRunRepository:
    """Same in-memory test double as `test_start_collection_run_orchestrator.py` (T-011) --
    not a Persistence Layer implementation.
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[EntityId, str], CollectionRun] = {}

    def add(self, collection_run: CollectionRun, *, idempotency_key: str) -> None:
        self._by_key[(collection_run.dataset_id, idempotency_key)] = collection_run

    def get_by_idempotency_key(
        self, dataset_id: EntityId, idempotency_key: str
    ) -> CollectionRun | None:
        return self._by_key.get((dataset_id, idempotency_key))


def _wait_for_record_count(records_path: Path, count: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if records_path.exists():
            lines = [
                line
                for line in records_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if len(lines) >= count:
                return
        time.sleep(_POLL_INTERVAL_SECONDS)
    raise TimeoutError(
        f"{records_path} did not reach {count} records within {timeout}s -- "
        "worker either finished too fast or never started."
    )


def test_a_real_sigkill_mid_run_leaves_correct_partial_state_then_resumes_cleanly(
    tmp_path: Path,
) -> None:
    run_uuid = uuid.uuid4()
    run_id = str(run_uuid)
    base_root = tmp_path

    # --- Phase 1: real subprocess, real SIGKILL -----------------------------------------
    proc = subprocess.Popen(
        [
            sys.executable,
            str(_WORKER),
            str(base_root),
            run_id,
            str(_SETTINGS),
            str(_ANALYSTS),
            "t013-fixture-salt",
            str(_WORKER_DELAY_SECONDS),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    channels_records = base_root / run_id / "checkpoints" / "collect_channels.jsonl"
    try:
        _wait_for_record_count(channels_records, 2, _POLL_TIMEOUT_SECONDS)
    finally:
        # `Popen.kill()` is the portable form of an uncatchable hard kill: on POSIX it
        # sends SIGKILL; on Windows it calls TerminateProcess. Neither can be caught or
        # handled by the target process, so this preserves the "genuine, uncontrolled
        # interruption" guarantee this test's docstring describes, on both platforms.
        proc.kill()
        proc.wait(timeout=5)

    # Proof this was a genuine, uncontrolled kill, not a graceful exit. On POSIX, a process
    # terminated by a signal reports a negative returncode (-N for signal N). Windows has no
    # signal-based termination -- TerminateProcess never produces the worker's own (0-valued)
    # success exit code, so "non-zero" is the portable equivalent proof there.
    if sys.platform == "win32":
        assert proc.returncode != 0
    else:
        assert proc.returncode == -signal.SIGKILL

    # --- Assert correct, uncorrupted partial state on disk ------------------------------
    checkpoint_root = base_root / run_id / "checkpoints"
    assert channels_records.exists()
    lines = [ln for ln in channels_records.read_text(encoding="utf-8").splitlines() if ln.strip()]
    # Exactly 2 -- not corrupted/truncated mid-write, and no more than what the delay
    # window should have allowed through before the kill landed.
    assert len(lines) == 2
    recorded = [json.loads(ln) for ln in lines]  # raises if any line is malformed JSON
    recorded_keys = {r["analyst_key"] for r in recorded}
    assert recorded_keys.issubset(_ANALYST_KEYS)
    assert len(recorded_keys) == 2  # no duplicate analyst recorded twice
    assert not (checkpoint_root / "collect_channels.done").exists()
    # The stage never reached write_parquet -- no partial/corrupt channels.parquet exists.
    assert not (base_root / run_id / "data_raw" / "channels.parquet").exists()

    # --- Phase 2: Walking Skeleton resume, through the orchestrator (T-011) -------------
    repo = FakeCollectionRunRepository()
    dataset_id = EntityId(uuid.uuid4())
    idempotency_key = "t013-resume-key"

    # Pre-seed the repository record a real Persistence implementation would already hold
    # for this run: the worker process crashed, so this run's last known status is `failed`.
    failed_run = CollectionRun(dataset_id=dataset_id, entity_id=EntityId(run_uuid))
    failed_run.start()
    failed_run.fail()
    repo.add(failed_run, idempotency_key=idempotency_key)

    cfg = load_settings(_SETTINGS, _ANALYSTS, validate_secrets=False)
    engine = CollectionEngineAdapter(
        settings=cfg.settings,
        roster=cfg.roster,
        provider=FixtureCollectionProvider(),
        base_root=base_root,
        transcript_fetcher=fixture_transcript_fetcher,
        anon_salt="t013-fixture-salt",
    )
    orchestrator = StartCollectionRunOrchestrator(
        collection_run_repository=repo, collection_engine=engine
    )

    result = orchestrator.execute(
        StartCollectionRunCommand(dataset_id=dataset_id, idempotency_key=idempotency_key)
    )

    assert result.id == run_uuid
    assert result.status == "completed"
    assert result.stage_row_counts == _EXPECTED_COUNTS
    resumed_run = repo.get_by_idempotency_key(dataset_id, idempotency_key)
    assert resumed_run is not None
    assert resumed_run.status is CollectionRunStatus.COMPLETED

    # --- No data loss, no duplication: verified directly against the final artifacts ----
    data_raw = base_root / run_id / "data_raw"
    channels_df = pd.read_parquet(data_raw / "channels.parquet")
    videos_df = pd.read_parquet(data_raw / "videos.parquet")
    comments_df = pd.read_parquet(data_raw / "comments.parquet")
    transcripts_df = pd.read_parquet(data_raw / "transcripts.parquet")

    assert len(channels_df) == 4
    assert set(channels_df["analyst_key"]) == _ANALYST_KEYS
    assert channels_df["analyst_key"].is_unique  # no duplicate rows from the resume

    assert len(videos_df) == 4
    assert videos_df["video_id"].is_unique

    assert len(comments_df) == 8
    assert comments_df["comment_id"].is_unique

    assert len(transcripts_df) == 4
    assert transcripts_df["video_id"].is_unique


@pytest.mark.parametrize("_unused", [None])
def test_worker_script_succeeds_on_its_own_without_interruption(
    tmp_path: Path, _unused: None
) -> None:
    # Sanity control: the worker script itself (not the kill mechanics) produces a correct
    # completed run when left alone -- isolates "the kill/resume test failed" from "the
    # worker script itself is broken."
    run_id = str(uuid.uuid4())
    proc = subprocess.run(
        [
            sys.executable,
            str(_WORKER),
            str(tmp_path),
            run_id,
            str(_SETTINGS),
            str(_ANALYSTS),
            "t013-fixture-salt",
            "0.0",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    data_raw = tmp_path / run_id / "data_raw"
    channels_df = pd.read_parquet(data_raw / "channels.parquet")
    assert len(channels_df) == 4
