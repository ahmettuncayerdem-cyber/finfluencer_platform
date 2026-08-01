#!/usr/bin/env python3
"""T-017 manual live-network interruption test -- BACKLOG.md T-017's own Verification line,
the half that requires real network egress and real, variable timing (not the deterministic,
stub-network half already proven by `tests/integration/test_t017_live_interruption.py`).

Not a pytest test (deliberately -- it spends real YouTube Data API quota, requires a real
`YT_API_KEY`, and sends a real `SIGKILL` to a real subprocess; it must never run automatically in
CI). Run manually, once, in an environment with real network egress to `googleapis.com`:

    python scripts/t017_live_interruption_manual.py

Requires `YT_API_KEY` and `ANON_SALT` set (via `.env` or the environment). Targets only
`config/analysts.yaml`'s pilot analyst (`satiroglu`) -- same quota-minimization decision as
T-015/T-016.

This script could NOT be run to completion in the sandbox this task was implemented in: that
sandbox's outbound network proxy returns `403` on `CONNECT` to `googleapis.com` (confirmed
independently in T-015 via direct `curl` and a real `httplib2.socks.HTTPError`, and not
re-verified here since nothing about that constraint changed). This is an environment constraint,
not a code defect -- see `docs/implementation/BACKLOG.md`'s T-017 entry for the full account. Run
this script yourself in an environment with real egress to complete the actual live-network half
of T-017's verification.

What it does:
1. Launches `tests/integration/_t017_worker.py` as a real subprocess with `stub_network=0` --
   the real, unstubbed `YouTubePlatformProvider`, real network, real (variable) API latency.
2. Waits for the channels-stage checkpoint to appear on disk, then sends a real `SIGKILL`.
3. Verifies the partial checkpoint state left behind.
4. Resumes the run through `StartCollectionRunOrchestrator` (T-011) against a freshly
   constructed, real (unstubbed) live-wired adapter (`build_live_collection_engine`, T-015).
5. Prints the final outcome and row counts.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from finfluencer.application.orchestrators import (  # noqa: E402
    StartCollectionRunCommand,
    StartCollectionRunOrchestrator,
)
from finfluencer.core.config import load_settings  # noqa: E402
from finfluencer.core.contracts import AnalystRoster  # noqa: E402
from finfluencer.domain.entities._common import EntityId  # noqa: E402
from finfluencer.domain.entities.collection_run import CollectionRun  # noqa: E402
from finfluencer.infrastructure.collection import build_live_collection_engine  # noqa: E402

_WORKER = _REPO_ROOT / "tests" / "integration" / "_t017_worker.py"
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"

_POLL_INTERVAL_SECONDS = 0.2
_POLL_TIMEOUT_SECONDS = 60.0
# Real API latency provides its own variable timing; a small extra delay before the videos
# stage just widens the window so this script doesn't need to race a fast response.
_WORKER_DELAY_SECONDS = 1.0


class _RepoStub:
    def __init__(self) -> None:
        self._by_key: dict[tuple, CollectionRun] = {}

    def add(self, collection_run: CollectionRun, *, idempotency_key: str) -> None:
        self._by_key[(collection_run.dataset_id, idempotency_key)] = collection_run

    def get_by_idempotency_key(self, dataset_id, idempotency_key):
        return self._by_key.get((dataset_id, idempotency_key))


def _wait_for_record_count(records_path: Path, count: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if records_path.exists():
            lines = [ln for ln in records_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if len(lines) >= count:
                return
        time.sleep(_POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"{records_path} did not reach {count} records within {timeout}s")


def main() -> int:
    run_uuid = uuid.uuid4()
    run_id = str(run_uuid)
    base_root = Path(tempfile.mkdtemp(prefix="t017-live-"))
    print(f"base_root: {base_root}")
    print(f"run_id: {run_id}")

    # --- Phase 1: real subprocess, real network, real SIGKILL --------------------------
    proc = subprocess.Popen(
        [
            sys.executable,
            str(_WORKER),
            str(base_root),
            run_id,
            str(_SETTINGS),
            str(_ANALYSTS),
            "",  # anon_salt: empty -> worker falls back to ANON_SALT env var, same as production
            str(_WORKER_DELAY_SECONDS),
            "0",  # stub_network=0 -- real googleapiclient, real network
            "0",  # fail_first_n_calls -- irrelevant when stub_network=0
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    channels_records = base_root / run_id / "checkpoints" / "collect_channels.jsonl"
    print("Waiting for the channels stage to checkpoint...")
    try:
        _wait_for_record_count(channels_records, 1, _POLL_TIMEOUT_SECONDS)
        time.sleep(0.2)
    finally:
        print("Sending SIGKILL...")
        proc.send_signal(signal.SIGKILL)
        proc.wait(timeout=10)

    print(f"Worker returncode: {proc.returncode} (expect {-signal.SIGKILL})")
    stderr_tail = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    if stderr_tail.strip():
        print(f"Worker stderr (last output before kill):\n{stderr_tail}")

    checkpoint_root = base_root / run_id / "checkpoints"
    lines = [ln for ln in channels_records.read_text(encoding="utf-8").splitlines() if ln.strip()]
    print(f"Channels checkpoint records: {len(lines)} -> {[json.loads(ln) for ln in lines]}")
    print(f"collect_channels.done exists: {(checkpoint_root / 'collect_channels.done').exists()}")
    print(f"collect_videos.done exists: {(checkpoint_root / 'collect_videos.done').exists()}")

    # --- Phase 2: resume through the orchestrator, real network -------------------------
    print("Resuming through StartCollectionRunOrchestrator...")
    repo = _RepoStub()
    dataset_id = EntityId(uuid.uuid4())
    idempotency_key = "t017-manual-resume-key"

    failed_run = CollectionRun(dataset_id=dataset_id, entity_id=EntityId(run_uuid))
    failed_run.start()
    failed_run.fail()
    repo.add(failed_run, idempotency_key=idempotency_key)

    cfg = load_settings(_SETTINGS, _ANALYSTS, validate_secrets=True)
    cfg.roster = AnalystRoster(analysts=[a for a in cfg.roster.analysts if a.key == "satiroglu"])

    engine, quota = build_live_collection_engine(cfg, base_root)
    orchestrator = StartCollectionRunOrchestrator(collection_run_repository=repo, collection_engine=engine)
    result = orchestrator.execute(
        StartCollectionRunCommand(dataset_id=dataset_id, idempotency_key=idempotency_key),
    )

    print(f"Final status: {result.status}")
    print(f"Final row counts: {result.stage_row_counts}")
    print(f"Quota remaining: {quota.remaining if quota is not None else 'n/a'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
