"""T-017 -- Real-world interruption test against a live run (BACKLOG.md T-017).

`PRODUCT_ARCHITECTURE.md` section 7.2 line 258: "a partial or interrupted collection is
resumable, not restarted, exactly as the existing engine already guarantees." T-013 proved this
against `FixtureCollectionProvider`. This module proves the same guarantee holds when the injected
provider is the *real* live-provider chain (T-015's `build_provider_and_quota`, T-016's
retry-wrapped `YouTubePlatformProvider`) instead of the fixture -- with only the network transport
boundary (`googleapiclient.discovery.build`) stubbed, exactly as
`test_live_provider.py` (T-015) already established. This keeps the test deterministic and
CI-safe while exercising every other real component: the registry, `YouTubePlatformProvider`
(including T-016's retry loop), `QuotaTracker`, `CollectionEngineAdapter`, `CheckpointManager`,
and every real `collect/*.py` stage function.

Two properties proven here that T-013 could not (T-013 predates T-015/T-016):
1. A real `SIGKILL` mid-run, against the live-wired adapter, still leaves correct partial
   checkpoint state and still resumes cleanly through `StartCollectionRunOrchestrator` (T-011).
2. A transient (429) failure on the very first network call still lets the whole run complete,
   proving T-016's retry logic operates correctly when run through this full subprocess/
   adapter/checkpoint chain, not just in an isolated unit test.

Genuine real-network, real-timing verification (as opposed to real-code-path-with-stubbed-
transport) remains out of this file's reach in this sandbox -- confirmed blocked in T-015 (proxy
returns 403 on CONNECT to googleapis.com) and not re-verified here, since nothing about that
constraint changed. See `scripts/t017_live_interruption_manual.py` for the human-operator half of
this task's Verification line, run in an environment with real egress.

Scope note carried over from T-013 unchanged: the repository record showing this run as `failed`
is pre-seeded directly (test double stands in for Persistence). Single analyst (`satiroglu`) is
used throughout, same quota-minimization decision as T-015/T-016 -- this makes the "no duplicate
rows" assertion after resume correct but less redundant than T-013's 4-analyst version (which had
more rows to prove non-duplication across).
"""

from __future__ import annotations

import json
import os
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
from finfluencer.infrastructure.collection import build_live_collection_engine

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _t017_worker import (  # noqa: E402
    _CHANNEL_ID,
    _install_stub_network,
    _stub_transcript_fetcher,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"
_WORKER = Path(__file__).resolve().parent / "_t017_worker.py"

_POLL_INTERVAL_SECONDS = 0.02
_POLL_TIMEOUT_SECONDS = 10.0
_WORKER_DELAY_SECONDS = 0.2

_STUB_ENV = {
    **os.environ,
    "YT_API_KEY": "stub-key-not-a-real-secret",
    "ANON_SALT": "t017-stub-salt",
}


@pytest.fixture(autouse=True)
def _ensure_youtube_provider_registered(_reset_registry: None) -> None:
    """Same workaround as `test_live_provider.py` (T-015): `tests/conftest.py`'s own
    `_reset_registry` (autouse) clears the provider registry before every test and only
    re-imports `language`, not `platform` -- this test's in-process resume phase calls
    `build_live_collection_engine` -> `build_provider_and_quota`, which needs `platform:youtube`
    registered. Depends on `_reset_registry` by name so pytest clears first."""
    from finfluencer.core.registry import register
    from finfluencer.providers.platform.youtube import YouTubePlatformProvider

    register("platform", "youtube")(YouTubePlatformProvider)


class FakeCollectionRunRepository:
    """Same in-memory test double T-011/T-013 already use -- not a Persistence Layer
    implementation."""

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
        "worker either finished too fast or never started.",
    )


def _run_worker(
    *, base_root: Path, run_id: str, delay_seconds: float, stub_network: str, fail_first_n: int
) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            str(_WORKER),
            str(base_root),
            run_id,
            str(_SETTINGS),
            str(_ANALYSTS),
            "t017-stub-salt",
            str(delay_seconds),
            stub_network,
            str(fail_first_n),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_STUB_ENV,
    )


def test_a_real_sigkill_mid_run_against_the_live_wired_adapter_resumes_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_uuid = uuid.uuid4()
    run_id = str(run_uuid)
    base_root = tmp_path

    # --- Phase 1: real subprocess, real SIGKILL, live-wired (stub-network) adapter -------
    proc = _run_worker(
        base_root=base_root,
        run_id=run_id,
        delay_seconds=_WORKER_DELAY_SECONDS,
        stub_network="1",
        fail_first_n=0,
    )

    channels_records = base_root / run_id / "checkpoints" / "collect_channels.jsonl"
    try:
        _wait_for_record_count(channels_records, 1, _POLL_TIMEOUT_SECONDS)
        # Channels stage (single analyst) checkpoints and marks itself done fast; our
        # delay gates `enumerate_videos` (start of the videos stage) instead -- give the
        # sleep a moment to actually be entered before killing.
        time.sleep(0.05)
    finally:
        proc.send_signal(signal.SIGKILL)
        proc.wait(timeout=5)

    # Proof this was a genuine, uncontrolled kill, not a graceful exit.
    assert proc.returncode == -signal.SIGKILL

    # --- Assert correct, uncorrupted partial state on disk --------------------------------
    checkpoint_root = base_root / run_id / "checkpoints"
    lines = [ln for ln in channels_records.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    recorded = json.loads(lines[0])  # raises if malformed
    assert recorded["analyst_key"] == "satiroglu"
    assert (checkpoint_root / "collect_channels.done").exists()  # whole stage completed
    assert not (checkpoint_root / "collect_videos.done").exists()  # videos never finished
    assert not (base_root / run_id / "data_raw" / "videos.parquet").exists()

    # --- Phase 2: Walking Skeleton resume, through the orchestrator (T-011), live-wired ---
    import googleapiclient.discovery as discovery_module

    original_build = discovery_module.build
    try:
        _install_stub_network(fail_first_n_resolve_calls=0)

        repo = FakeCollectionRunRepository()
        dataset_id = EntityId(uuid.uuid4())
        idempotency_key = "t017-resume-key"

        failed_run = CollectionRun(dataset_id=dataset_id, entity_id=EntityId(run_uuid))
        failed_run.start()
        failed_run.fail()
        repo.add(failed_run, idempotency_key=idempotency_key)

        monkeypatch.setenv("YT_API_KEY", "stub-key-not-a-real-secret")
        monkeypatch.setenv("ANON_SALT", "t017-stub-salt")
        cfg = load_settings(_SETTINGS, _ANALYSTS, validate_secrets=True)
        from finfluencer.core.contracts import AnalystRoster

        cfg.roster = AnalystRoster(
            analysts=[a for a in cfg.roster.analysts if a.key == "satiroglu"],
        )

        engine, _quota = build_live_collection_engine(
            cfg, base_root, transcript_fetcher=_stub_transcript_fetcher,
        )
        orchestrator = StartCollectionRunOrchestrator(
            collection_run_repository=repo, collection_engine=engine,
        )

        result = orchestrator.execute(
            StartCollectionRunCommand(dataset_id=dataset_id, idempotency_key=idempotency_key),
        )
    finally:
        discovery_module.build = original_build

    assert result.id == run_uuid
    assert result.status == "completed"
    assert result.stage_row_counts == {
        "channels": 1,
        "videos": 1,
        "comments": 1,
        "transcripts": 1,
    }
    resumed_run = repo.get_by_idempotency_key(dataset_id, idempotency_key)
    assert resumed_run is not None
    assert resumed_run.status is CollectionRunStatus.COMPLETED

    # --- No data loss, no duplication ------------------------------------------------------
    data_raw = base_root / run_id / "data_raw"
    channels_df = pd.read_parquet(data_raw / "channels.parquet")
    assert len(channels_df) == 1  # not duplicated by the resume
    assert channels_df.iloc[0]["channel_id"] == _CHANNEL_ID


def test_run_completes_despite_a_transient_error_on_the_first_network_call(
    tmp_path: Path,
) -> None:
    """T-016's retry logic, proven through the full subprocess/adapter/checkpoint chain, not
    just an isolated unit test: the very first network call (channel resolution) fails once
    with a 429, and the run still completes -- no interruption involved in this test."""
    run_id = str(uuid.uuid4())
    proc = subprocess.run(
        [
            sys.executable,
            str(_WORKER),
            str(tmp_path),
            run_id,
            str(_SETTINGS),
            str(_ANALYSTS),
            "t017-stub-salt",
            "0.0",  # no interruption window needed for this test
            "1",  # stub_network
            "1",  # fail_first_n_calls
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_STUB_ENV,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    data_raw = tmp_path / run_id / "data_raw"
    channels_df = pd.read_parquet(data_raw / "channels.parquet")
    assert len(channels_df) == 1


@pytest.mark.parametrize("_unused", [None])
def test_worker_script_succeeds_on_its_own_without_interruption(
    tmp_path: Path, _unused: None,
) -> None:
    # Sanity control, same role as T-013's equivalent: isolates "the kill/resume test failed"
    # from "the worker script itself is broken."
    run_id = str(uuid.uuid4())
    proc = subprocess.run(
        [
            sys.executable,
            str(_WORKER),
            str(tmp_path),
            run_id,
            str(_SETTINGS),
            str(_ANALYSTS),
            "t017-stub-salt",
            "0.0",
            "1",
            "0",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_STUB_ENV,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    data_raw = tmp_path / run_id / "data_raw"
    channels_df = pd.read_parquet(data_raw / "channels.parquet")
    assert len(channels_df) == 1
