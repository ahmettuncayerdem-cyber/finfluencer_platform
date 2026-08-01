"""Fixture `PlatformProvider` implementation (BACKLOG.md T-010).

Implements `finfluencer.providers.platform.base.PlatformProvider` exactly -- same method
signatures, same typed-exception contract (`ResourceNotFoundError` for an unknown lookup) -- but
answers from `fixture_data.py`'s canned dataset instead of a live YouTube API call. This is what
makes BACKLOG.md T-010 "no live network dependency yet": `CollectionEngineAdapter`
(`collection_engine_adapter.py`) never imports the network-calling `youtube.py` provider or
anything from `googleapiclient`; it only depends on the `PlatformProvider` Protocol, and this
fixture is the concrete instance injected for this task. Swapping in a real, network-backed
provider later (a separate, not-yet-numbered task) requires zero change to
`CollectionEngineAdapter` -- only a different constructor argument.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable

from finfluencer.core.contracts import CommentRecord, VideoRecord
from finfluencer.core.exceptions import ResourceNotFoundError
from finfluencer.infrastructure.collection.fixture_data import (
    CHANNEL_LOOKUP_TO_ID,
    CHANNEL_METADATA,
    COMMENTS_BY_VIDEO,
    TRANSCRIPTS_BY_VIDEO,
    UPLOADS_TO_VIDEO_IDS,
    VIDEO_METADATA,
)


class FixtureCollectionProvider:
    """A `PlatformProvider` (structurally, via `@runtime_checkable`) backed entirely by
    `fixture_data.py`'s canned dataset -- no network access anywhere in this class.
    """

    key: str = "fixture"
    unit_cost: dict[str, int] = {
        "resolve_channel": 0,
        "channel_metadata": 0,
        "enumerate_videos": 0,
        "fetch_video_metadata": 0,
        "fetch_top_level_comments": 0,
    }

    # -- Channel resolution ----------------------------------------------

    def resolve_channel(self, handle_or_id: str) -> str:
        try:
            return CHANNEL_LOOKUP_TO_ID[handle_or_id]
        except KeyError as exc:
            raise ResourceNotFoundError(
                f"Fixture has no channel for lookup {handle_or_id!r}",
            ) from exc

    def channel_metadata(self, channel_id: str) -> dict[str, Any]:
        try:
            return dict(CHANNEL_METADATA[channel_id])
        except KeyError as exc:
            raise ResourceNotFoundError(
                f"Fixture has no channel_metadata for {channel_id!r}",
            ) from exc

    # -- Video enumeration & metadata ------------------------------------

    def enumerate_videos(
        self,
        uploads_ref: str,
        *,
        window_start_iso: str,
        window_end_iso: str,
    ) -> Iterable[str]:
        video_ids = UPLOADS_TO_VIDEO_IDS.get(uploads_ref, [])
        in_window = [
            vid
            for vid in video_ids
            if window_start_iso <= VIDEO_METADATA[vid]["published_at"][:10] <= window_end_iso
        ]
        # Real providers enumerate newest-first (per PlatformProvider's contract) -- fixture
        # data is already stored newest-first per channel, so no re-sort is needed here.
        return in_window

    def fetch_video_metadata(
        self,
        video_ids: list[str],
        *,
        analyst_key: str,
    ) -> list[VideoRecord]:
        records: list[VideoRecord] = []
        for vid in video_ids:
            meta = VIDEO_METADATA.get(vid)
            if meta is None:
                # PlatformProvider's contract: videos that no longer exist are silently
                # omitted, not raised -- matches the real provider's documented behavior.
                continue
            records.append(VideoRecord(analyst_key=analyst_key, **meta))
        return records

    # -- Comments --------------------------------------------------------

    def fetch_top_level_comments(
        self,
        video_id: str,
        *,
        analyst_key: str,
        salt: str,
        window_start_iso: str,
        window_end_iso: str,
    ) -> list[CommentRecord]:
        raw_comments = COMMENTS_BY_VIDEO.get(video_id, [])
        records: list[CommentRecord] = []
        for raw in raw_comments:
            posted_date = raw["posted_date"]
            if not (window_start_iso[:10] <= posted_date <= window_end_iso[:10]):
                continue
            # Simplified anonymization for fixture purposes only -- proves the
            # salt-dependent-hash *shape* CommentRecord.commenter_hash expects; does not
            # claim to reproduce the real provider's exact anonymization algorithm, which
            # this fixture never touches or needs to.
            commenter_hash = hashlib.sha256(
                f"{salt}:{raw['comment_id']}".encode("utf-8")
            ).hexdigest()[:16]
            records.append(
                CommentRecord(
                    analyst_key=analyst_key,
                    video_id=video_id,
                    comment_id=raw["comment_id"],
                    commenter_hash=commenter_hash,
                    posted_date=posted_date,
                    text_raw=raw["text"],
                    text_clean="",
                    tokens=[],
                    n_tokens=0,
                    emojis=[],
                    likes=0,
                )
            )
        return records


def fixture_transcript_fetcher(video_id: str, *, preferred_languages: list[str]) -> dict[str, Any]:
    """A `fetcher` callable matching `finfluencer.collect.transcripts`'s documented signature
    and return shape exactly (`available`/`text`/`language`/`reason`), answering from
    `fixture_data.TRANSCRIPTS_BY_VIDEO` instead of `youtube-transcript-api`. `preferred_languages`
    is accepted for signature compatibility but unused -- the fixture has exactly one canned
    transcript per video, so there is no language choice to make.
    """
    return dict(
        TRANSCRIPTS_BY_VIDEO.get(
            video_id,
            {"available": False, "text": "", "language": None, "reason": "not_in_fixture"},
        )
    )


__all__ = ["FixtureCollectionProvider", "fixture_transcript_fetcher"]
