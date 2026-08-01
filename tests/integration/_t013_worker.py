"""T-013 subprocess worker — NOT production code, NOT imported by anything under `src/`.

Runs one `CollectionEngineAdapter.run(run_id)` call in its own OS process so the parent test
(`test_t013_interruption_and_resume.py`) can send it a real `SIGKILL` mid-run -- proving
`PRODUCT_ARCHITECTURE.md` section 1.2's reproducibility promise against a genuine process
crash, not a simulated in-process exception (which T-010/T-011's own tests already cover).

Invoked as: `python _t013_worker.py <base_root> <run_id> <settings_path> <analysts_path>
<anon_salt> <delay_seconds>`. Exits 0 on success; a non-zero/absent exit code combined with the
parent's own `SIGKILL` delivery is the expected "crash" outcome for this script's whole purpose.

`delay_seconds` inserts a real `time.sleep` between analysts inside a thin provider wrapper --
a test-timing device only, not a retry/backoff policy or anything resembling production Collection
Engine behavior. It exists solely so the parent process has a reliably observable window in which
to deliver `SIGKILL` after a known number of analysts have been checkpointed.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Defensive: guarantee `src/` is importable even if the parent didn't set PYTHONPATH for this
# subprocess's environment.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from finfluencer.core.config import load_settings  # noqa: E402
from finfluencer.infrastructure.collection import (  # noqa: E402
    CollectionEngineAdapter,
    FixtureCollectionProvider,
    fixture_transcript_fetcher,
)


class _SlowProvider:
    """Delegates to a real `FixtureCollectionProvider`, sleeping before every
    `resolve_channel` call after the first -- gives the parent process a wide, reliable
    window to observe N completed analysts on disk before the (N+1)th begins.
    """

    def __init__(self, delay_seconds: float) -> None:
        self._inner = FixtureCollectionProvider()
        self._delay_seconds = delay_seconds
        self._calls = 0
        self.key = self._inner.key
        self.unit_cost = self._inner.unit_cost

    def resolve_channel(self, handle_or_id: str) -> str:
        self._calls += 1
        if self._calls > 1:
            time.sleep(self._delay_seconds)
        return self._inner.resolve_channel(handle_or_id)

    def channel_metadata(self, channel_id: str):
        return self._inner.channel_metadata(channel_id)

    def enumerate_videos(self, uploads_ref: str, **kwargs):
        return self._inner.enumerate_videos(uploads_ref, **kwargs)

    def fetch_video_metadata(self, video_ids, **kwargs):
        return self._inner.fetch_video_metadata(video_ids, **kwargs)

    def fetch_top_level_comments(self, video_id: str, **kwargs):
        return self._inner.fetch_top_level_comments(video_id, **kwargs)


def main() -> int:
    base_root, run_id, settings_path, analysts_path, anon_salt, delay_seconds = sys.argv[1:7]

    cfg = load_settings(Path(settings_path), Path(analysts_path), validate_secrets=False)
    adapter = CollectionEngineAdapter(
        settings=cfg.settings,
        roster=cfg.roster,
        provider=_SlowProvider(float(delay_seconds)),
        base_root=Path(base_root),
        transcript_fetcher=fixture_transcript_fetcher,
        anon_salt=anon_salt,
    )
    adapter.run(run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
