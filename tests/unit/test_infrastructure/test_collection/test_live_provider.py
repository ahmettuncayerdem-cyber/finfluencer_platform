"""Tests for `build_live_collection_engine` (BACKLOG.md T-015).

Proves the *new* code this task adds -- wiring the real, registry-resolved
`YouTubePlatformProvider` (via `collect.main.build_provider_and_quota`, reused unmodified) into
the real, unmodified `CollectionEngineAdapter` (T-010). The only thing stubbed is
`googleapiclient.discovery.build` -- the actual network boundary -- so everything else in the
chain (registry lookup, `YouTubePlatformProvider` construction, `QuotaTracker`, the adapter, and
every `collect/*.py` stage function) runs for real, exactly as it would against the live API.
`YouTubePlatformProvider`'s own correctness (error mapping, pagination, anonymization) is already
covered by `tests/unit/test_providers/test_youtube.py` and is not re-tested here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from finfluencer.core.config import load_settings
from finfluencer.core.contracts import AnalystRoster
from finfluencer.infrastructure.collection import build_live_collection_engine

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"

_CHANNEL_ID = "UCGBytjbMXiF1nbe6HD7iORQ"  # satiroglu's real, verified channel_id
_VIDEO_ID = "t015LiveWiringVideo1"
_COMMENT_ID = "t015LiveWiringComment1"
_UPLOADS_REF = "UUt015LiveWiring"


class _StubExecutable:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def execute(self) -> dict[str, Any]:
        return self._response


class _StubYouTubeService:
    """Minimal stand-in for the real googleapiclient YouTube v3 service -- just enough
    surface (`channels`, `playlistItems`, `videos`, `commentThreads`, each `.list(**kwargs)
    .execute()`) to drive one channel / one video / one comment through the real
    `YouTubePlatformProvider` + `CollectionEngineAdapter`.
    """

    def channels(self) -> "_StubYouTubeService":
        return self

    def playlistItems(self) -> "_StubYouTubeService":
        return self

    def videos(self) -> "_StubYouTubeService":
        return self

    def commentThreads(self) -> "_StubYouTubeService":
        return self

    def list(self, **kwargs: Any) -> _StubExecutable:
        if "forHandle" in kwargs:
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
                                "title": "T-015 live-wiring stub video",
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
            # channels().list(part="snippet,contentDetails,statistics", id=...) -- metadata call
            return _StubExecutable(
                {
                    "items": [
                        {
                            "snippet": {
                                "title": "Tunç Şatıroğlu (live-wiring stub)",
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
                                        "textDisplay": "canli baglanti testi",
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


def _stub_transcript_fetcher(video_id: str, *, preferred_languages: list[str]) -> dict[str, Any]:
    return {"available": False, "text": "", "language": None, "reason": "stubbed for wiring test"}


@pytest.fixture()
def _stub_google_build(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "googleapiclient.discovery.build",
        lambda *_args, **_kwargs: _StubYouTubeService(),
    )


@pytest.fixture(autouse=True)
def _ensure_youtube_provider_registered(_reset_registry: None) -> None:
    """`tests/conftest.py`'s own `_reset_registry` (autouse) clears the provider registry
    before every test and re-imports only the `language` subpackage -- `platform:youtube`
    needs the same treatment here, since this test file is the first to actually exercise
    the registry-based `platform` lookup path (`build_provider_and_quota`). Depends on
    `_reset_registry` by name so pytest runs the clear before this re-registers, regardless
    of fixture-discovery order between `conftest.py` and this module.
    """
    from finfluencer.core.registry import register
    from finfluencer.providers.platform.youtube import YouTubePlatformProvider

    register("platform", "youtube")(YouTubePlatformProvider)


def test_build_live_collection_engine_wires_the_real_youtube_provider_end_to_end(
    tmp_path: Path, _stub_google_build: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YT_API_KEY", "stub-key-not-a-real-secret")
    monkeypatch.setenv("ANON_SALT", "t015-wiring-test-salt")

    cfg = load_settings(_SETTINGS, _ANALYSTS, validate_secrets=True)
    # Trim to the pilot analyst only, matching scripts/t015_live_smoke_test.py's own choice --
    # a genuine "small real channel", not the full four-analyst roster.
    cfg.roster = AnalystRoster(
        analysts=[a for a in cfg.roster.analysts if a.key == "satiroglu"],
    )

    adapter, quota = build_live_collection_engine(
        cfg, tmp_path, transcript_fetcher=_stub_transcript_fetcher
    )
    outcome = adapter.run("t015-wiring-run")

    assert outcome.stage_row_counts == {
        "channels": 1,
        "videos": 1,
        "comments": 1,
        "transcripts": 1,
    }
    assert quota is not None
    assert quota.remaining < quota.daily_units  # real quota accounting actually ran

    channels_df = pd.read_parquet(tmp_path / "t015-wiring-run" / "data_raw" / "channels.parquet")
    assert channels_df.iloc[0]["analyst_key"] == "satiroglu"
    assert channels_df.iloc[0]["channel_id"] == _CHANNEL_ID


def test_build_live_collection_engine_returns_a_real_youtube_provider_instance(
    tmp_path: Path, _stub_google_build: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from finfluencer.providers.platform.youtube import YouTubePlatformProvider

    monkeypatch.setenv("YT_API_KEY", "stub-key-not-a-real-secret")
    monkeypatch.setenv("ANON_SALT", "t015-wiring-test-salt")
    cfg = load_settings(_SETTINGS, _ANALYSTS, validate_secrets=True)

    adapter, quota = build_live_collection_engine(cfg, tmp_path)

    assert isinstance(adapter._provider, YouTubePlatformProvider)  # noqa: SLF001
    assert quota.service == "youtube_data_api_v3"
