"""T-017 subprocess worker — NOT production code, NOT imported by anything under `src/`.

Runs one `CollectionEngineAdapter.run(run_id)` call wired to the *real* live-provider chain (T-015's
`build_provider_and_quota`, T-016's retry-wrapped `YouTubePlatformProvider`) instead of T-013's
`FixtureCollectionProvider`, in its own OS process so the parent test
(`test_t017_live_interruption.py`) can send it a real `SIGKILL` mid-run — the live-data equivalent
of T-013's fixture-data proof.

Two independent, orthogonal things this script can be told to do via CLI args:

- `stub_network` ("1"/"0"): "1" replaces `googleapiclient.discovery.build` with an in-process stub
  (same technique `test_live_provider.py`, T-015, already established) so the test suite stays
  deterministic and CI-safe. "0" leaves the real network path in place, for a human operator
  running this in an environment with real egress to `googleapis.com` — see
  `scripts/t017_live_interruption_manual.py`.
- `fail_first_n_calls`: makes the stub's very first `channels().list(forHandle=...)` call (the
  first network call the whole pipeline makes) raise a transient 429 this many times before
  succeeding — proves T-016's retry logic survives being run through this whole
  subprocess/adapter/checkpoint chain, not just an isolated unit test. Only meaningful when
  `stub_network=1`; ignored otherwise (a real API is not told to fail on command).

`delay_seconds` inserts a real `time.sleep` before the videos stage begins (wrapping
`enumerate_videos`) — a test-timing device only, giving the parent process a reliably observable
window in which to deliver `SIGKILL` after the channels stage has checkpointed but before the
videos stage starts. Not a retry/backoff policy or anything resembling production behavior.

Invoked as: `python _t017_worker.py <base_root> <run_id> <settings_path> <analysts_path>
<anon_salt> <delay_seconds> <stub_network> <fail_first_n_calls>`. Exits 0 on success.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

# Defensive: guarantee `src/` is importable even if the parent didn't set PYTHONPATH for this
# subprocess's environment.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from finfluencer.collect.main import build_provider_and_quota  # noqa: E402
from finfluencer.core.config import load_settings  # noqa: E402
from finfluencer.core.contracts import AnalystRoster  # noqa: E402
from finfluencer.infrastructure.collection import CollectionEngineAdapter  # noqa: E402

# satiroglu's real, verified channel_id -- same pilot target as T-015/T-016.
_CHANNEL_ID = "UCGBytjbMXiF1nbe6HD7iORQ"
_VIDEO_ID = "t017LiveInterruptionVideo1"
_COMMENT_ID = "t017LiveInterruptionComment1"
_UPLOADS_REF = "UUt017LiveInterruption"


class _FakeHttpError(Exception):
    """Mimics googleapiclient.errors.HttpError closely enough for `_execute_once`'s error
    mapping: a `.resp.status` int and a message. Same shape as
    tests/unit/test_providers/test_youtube.py's `_FakeHttpError`."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        from types import SimpleNamespace

        self.resp = SimpleNamespace(status=status)


class _RaisingExecutable:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def execute(self) -> Any:
        raise self._error


class _StubExecutable:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def execute(self) -> dict[str, Any]:
        return self._response


class _StubYouTubeService:
    """Minimal stand-in for the real googleapiclient YouTube v3 service -- same technique as
    `tests/unit/test_infrastructure/test_collection/test_live_provider.py` (T-015), extended
    with an optional transient-failure injection on the first `fail_first_n_resolve_calls`
    channel-resolution calls (T-017's retry-survives-the-real-chain proof)."""

    def __init__(self, *, fail_first_n_resolve_calls: int = 0) -> None:
        self._resolve_call_count = 0
        self._fail_first_n_resolve_calls = fail_first_n_resolve_calls

    def channels(self) -> "_StubYouTubeService":
        return self

    def playlistItems(self) -> "_StubYouTubeService":
        return self

    def videos(self) -> "_StubYouTubeService":
        return self

    def commentThreads(self) -> "_StubYouTubeService":
        return self

    def list(self, **kwargs: Any) -> Any:
        if "forHandle" in kwargs:
            self._resolve_call_count += 1
            if self._resolve_call_count <= self._fail_first_n_resolve_calls:
                return _RaisingExecutable(_FakeHttpError(429, "Too Many Requests"))
            return _StubExecutable({"items": [{"id": _CHANNEL_ID}]})
        if "playlistId" in kwargs:
            return _StubExecutable(
                {
                    "items": [
                        {
                            "contentDetails": {
                                "videoId": _VIDEO_ID,
                                "videoPublishedAt": "2025-06-01T12:00:00Z",
                            },
                        },
                    ],
                },
            )
        if kwargs.get("part", "").startswith("snippet,contentDetails,statistics,status"):
            return _StubExecutable(
                {
                    "items": [
                        {
                            "id": _VIDEO_ID,
                            "snippet": {
                                "title": "T-017 live-interruption stub video",
                                "description": "no promo keywords here",
                                "publishedAt": "2025-06-01T12:00:00Z",
                                "categoryId": "25",
                            },
                            "contentDetails": {"duration": "PT5M0S"},
                            "statistics": {
                                "viewCount": "1000",
                                "likeCount": "10",
                                "commentCount": "1",
                            },
                            "status": {"madeForKids": False},
                        },
                    ],
                },
            )
        if "id" in kwargs and kwargs.get("part", "").startswith("snippet,contentDetails,statistics"):
            return _StubExecutable(
                {
                    "items": [
                        {
                            "snippet": {
                                "title": "Tunc Satiroglu (live-interruption stub)",
                                "description": "stub channel metadata",
                                "publishedAt": "2018-01-01T00:00:00Z",
                            },
                            "contentDetails": {
                                "relatedPlaylists": {"uploads": _UPLOADS_REF},
                            },
                            "statistics": {
                                "subscriberCount": "100000",
                                "videoCount": "1",
                                "viewCount": "1000000",
                            },
                        },
                    ],
                },
            )
        if "videoId" in kwargs:
            return _StubExecutable(
                {
                    "items": [
                        {
                            "id": _COMMENT_ID,
                            "snippet": {
                                "topLevelComment": {
                                    "snippet": {
                                        "publishedAt": "2025-06-02T09:00:00Z",
                                        "textDisplay": "kesinti testi",
                                        "authorChannelId": {"value": "UCstubauthor00000000000"},
                                        "likeCount": 1,
                                    },
                                },
                            },
                        },
                    ],
                },
            )
        raise AssertionError(f"Unexpected stub call: {kwargs}")


def _install_stub_network(*, fail_first_n_resolve_calls: int) -> None:
    """Replace `googleapiclient.discovery.build` with the in-process stub above -- the only
    thing this stubs is the network transport boundary, matching T-015's own test technique.
    Must run before `build_provider_and_quota` constructs the provider, since
    `youtube.py::_default_client_factory` resolves `googleapiclient.discovery.build` at call time.
    """
    import googleapiclient.discovery as discovery_module

    service = _StubYouTubeService(fail_first_n_resolve_calls=fail_first_n_resolve_calls)
    discovery_module.build = lambda *_args, **_kwargs: service


def _stub_transcript_fetcher(video_id: str, *, preferred_languages: list[str]) -> dict[str, Any]:
    return {"available": False, "text": "", "language": None, "reason": "stubbed for T-017"}


class _SlowLiveProvider:
    """Delegates to the real (or stub-network) `YouTubePlatformProvider`, sleeping before
    `enumerate_videos` -- gives the parent process a reliable window to observe the channels
    stage's checkpoint on disk before the videos stage begins. Test-timing device only, same
    role as T-013's `_SlowProvider`, just gating a different stage boundary (channels->videos
    instead of analyst N->N+1, since T-017 uses a single analyst to limit quota spend)."""

    def __init__(self, inner: Any, delay_seconds: float) -> None:
        self._inner = inner
        self._delay_seconds = delay_seconds
        self.key = inner.key
        self.unit_cost = inner.unit_cost

    def resolve_channel(self, handle_or_id: str) -> str:
        return self._inner.resolve_channel(handle_or_id)

    def channel_metadata(self, channel_id: str) -> dict[str, Any]:
        return self._inner.channel_metadata(channel_id)

    def enumerate_videos(self, uploads_ref: str, **kwargs: Any) -> Any:
        if self._delay_seconds > 0:
            time.sleep(self._delay_seconds)
        return self._inner.enumerate_videos(uploads_ref, **kwargs)

    def fetch_video_metadata(self, video_ids: list[str], **kwargs: Any) -> Any:
        return self._inner.fetch_video_metadata(video_ids, **kwargs)

    def fetch_top_level_comments(self, video_id: str, **kwargs: Any) -> Any:
        return self._inner.fetch_top_level_comments(video_id, **kwargs)


def main() -> int:
    (
        base_root,
        run_id,
        settings_path,
        analysts_path,
        anon_salt,
        delay_seconds,
        stub_network,
        fail_first_n_calls,
    ) = sys.argv[1:9]

    if stub_network == "1":
        _install_stub_network(fail_first_n_resolve_calls=int(fail_first_n_calls))

    cfg = load_settings(Path(settings_path), Path(analysts_path), validate_secrets=True)
    # Single analyst -- same quota-minimization decision T-015/T-016 already made.
    cfg.roster = AnalystRoster(
        analysts=[a for a in cfg.roster.analysts if a.key == "satiroglu"],
    )

    provider, _quota = build_provider_and_quota(cfg)
    wrapped_provider = _SlowLiveProvider(provider, float(delay_seconds))

    adapter = CollectionEngineAdapter(
        settings=cfg.settings,
        roster=cfg.roster,
        provider=wrapped_provider,
        base_root=Path(base_root),
        transcript_fetcher=_stub_transcript_fetcher,
        anon_salt=anon_salt,
    )
    adapter.run(run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
