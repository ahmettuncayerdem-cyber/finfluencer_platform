"""
finfluencer.providers.platform.base
====================================

Protocol for platform-specific data collection.

A ``PlatformProvider`` is the abstraction over a comment-generating
platform (YouTube for MVP-B; X/Twitter, TikTok, Reddit as future
plugins). It exposes the operations that Phase-2 collection modules
need without leaking platform-API details into the pipeline.

MVP-B: YouTube is the only concrete implementation, delivered in Phase 2.
"""

from __future__ import annotations

from typing import Any, Iterable, Protocol, runtime_checkable

from finfluencer.core.contracts import CommentRecord, VideoRecord


@runtime_checkable
class PlatformProvider(Protocol):
    """Structural interface for platform-specific collection operations.

    Instances are constructed by the collection layer with credentials
    and a :class:`QuotaTracker`. Method contracts:

    * All methods raise :class:`finfluencer.core.exceptions.CollectionError`
      subclasses on failure. Transient errors are retried inside the
      implementation before propagating.
    * Methods that consume quota MUST call ``quota_tracker.ensure_capacity``
      before the API call and ``quota_tracker.spend`` after success.
    * Anonymisation of user identifiers is the provider's responsibility
      at the point of ingest (per Methods §3.11).
    """

    #: Registry key, e.g. ``"youtube"``.
    key: str

    #: Quota units for a single call to each method. Populated by
    #: the concrete provider so :class:`QuotaTracker` can pre-flight
    #: accurately.
    unit_cost: dict[str, int]

    # -- Channel resolution ----------------------------------------------

    def resolve_channel(self, handle_or_id: str) -> str:
        """Return the canonical channel identifier.

        Accepts a handle (``@name``), a channel URL, or a canonical ID.
        """
        ...

    def channel_metadata(self, channel_id: str) -> dict[str, Any]:
        """Return channel metadata (name, subscriber count, uploads
        playlist ID, verified status).

        Fields are platform-specific but must include ``uploads_ref``
        (an opaque token consumed by :meth:`enumerate_videos`).
        """
        ...

    # -- Video enumeration & metadata ------------------------------------

    def enumerate_videos(
        self,
        uploads_ref: str,
        *,
        window_start_iso: str,
        window_end_iso: str,
    ) -> Iterable[str]:
        """Yield video IDs published within the observation window.

        Ordered newest-first; implementation may stop early once it
        encounters a video older than ``window_start_iso``.
        """
        ...

    def fetch_video_metadata(
        self,
        video_ids: list[str],
        *,
        analyst_key: str,
    ) -> list[VideoRecord]:
        """Return :class:`VideoRecord` for each of ``video_ids``.

        Batches requests where the platform API supports it. Videos
        that no longer exist are silently omitted from the return set;
        the caller may detect this by comparing input and output sizes.
        """
        ...

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
        """Return all top-level comments within the window, anonymised.

        Anonymisation (SHA-256 salted hash) is applied at ingest before
        the record is returned; raw usernames never appear in the
        return value.

        Comments outside the window are filtered out. Replies are
        excluded (per Methods §3.2.4). If the video has comments
        disabled, returns an empty list without raising.
        """
        ...


__all__ = ["PlatformProvider"]
