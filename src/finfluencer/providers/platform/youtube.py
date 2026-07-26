"""
finfluencer.providers.platform.youtube
=======================================

YouTube Data API v3 provider — concrete implementation of PlatformProvider.

Design decisions
----------------
* **Client injection.** The googleapiclient service is built via a
  ``client_factory`` argument (default: ``googleapiclient.discovery.build``).
  Tests inject a stub factory; production code lets the default run.
  No monkey-patching of googleapiclient is ever required.
* **Anonymisation at ingest.** Commenter identifiers are HMAC-hashed
  in :meth:`fetch_top_level_comments` BEFORE the record leaves the method.
  Raw ``authorChannelId`` values never appear in returned :class:`CommentRecord`.
* **Quota accounting.** Every API call is bracketed by
  ``quota.ensure_capacity`` (pre-flight) and ``quota.spend`` (post-success).
  Quota bookkeeping is the provider's responsibility; the caller only
  supplies the tracker.
* **Retry policy.** Only transient errors (RateLimit, NetworkError) are
  retried; ``QuotaExhaustedError`` and ``ResourceNotFoundError`` propagate.
* **Day-truncation.** Comment ``posted_date`` is truncated to
  ``YYYY-MM-DD`` at ingest (Methods §3.11 ethics compliance).
"""

from __future__ import annotations

import os
from typing import Any, Callable, Iterable

from finfluencer.core.budgets import QuotaTracker
from finfluencer.core.contracts import CommentRecord, VideoRecord
from finfluencer.core.exceptions import (
    AuthenticationError,
    CollectionError,
    NetworkError,
    QuotaExhaustedError,
    RateLimitError,
    ResourceNotFoundError,
)
from finfluencer.core.logging import get_logger
from finfluencer.core.registry import register
from finfluencer.utils.hashing import hash_identifier
from finfluencer.utils.time import (
    iso8601_duration_to_seconds,
    parse_iso8601,
    truncate_to_day,
)


_log = get_logger(__name__)


#: Unit costs per YouTube Data API v3 pricing (Google reference).
_UNIT_COSTS: dict[str, int] = {
    "channels_list": 1,
    "playlistItems_list": 1,
    "videos_list": 1,
    "commentThreads_list": 1,
    "search_list": 100,  # intentionally not used; documented for auditability
}


def _default_client_factory(api_key: str) -> Any:
    """Default client factory: build the real googleapiclient service.

    Isolated in its own function so tests can substitute a stub without
    monkey-patching module-level imports.
    """
    from googleapiclient.discovery import build

    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


@register("platform", "youtube")
class YouTubePlatformProvider:
    """Concrete YouTube implementation of :class:`PlatformProvider`."""

    key: str = "youtube"
    unit_cost: dict[str, int] = dict(_UNIT_COSTS)

    def __init__(
        self,
        *,
        api_key: str | None = None,
        quota_tracker: QuotaTracker | None = None,
        shorts_max_duration_sec: int = 60,
        promo_keywords: Iterable[str] | None = None,
        client_factory: Callable[[str], Any] = _default_client_factory,
    ) -> None:
        api_key = api_key or os.environ.get("YT_API_KEY", "")
        if not api_key:
            raise AuthenticationError(
                "YouTube API key not provided; set YT_API_KEY env or pass api_key=",
            )
        self._client = client_factory(api_key)
        self.quota = quota_tracker
        self.shorts_max_duration_sec = shorts_max_duration_sec
        self.promo_keywords = tuple((k or "").lower() for k in (promo_keywords or ()))

    # -- quota helpers ----------------------------------------------------

    def _ensure_quota(self, op: str) -> None:
        if self.quota is not None:
            self.quota.ensure_capacity(_UNIT_COSTS[op])

    def _spend_quota(self, op: str) -> None:
        if self.quota is not None:
            self.quota.spend(_UNIT_COSTS[op])

    # -- HTTP execution with typed error mapping --------------------------

    def _execute(self, request: Any) -> Any:
        """Execute a googleapiclient request and map HttpError → typed exceptions."""
        try:
            return request.execute()
        except Exception as e:  # noqa: BLE001
            status = getattr(getattr(e, "resp", None), "status", None)
            msg = str(e)
            lower_msg = msg.lower()

            _log.debug("youtube_api_error", status=status, message=msg)

            if status == 403:
                if (
                    "commentsdisabled" in lower_msg
                    or "has disabled comments" in lower_msg
                    or "disabled comments" in lower_msg
                ):
                    raise ResourceNotFoundError(
                        "Comments disabled for this video",
                        status_code=status,
                    ) from e
                if (
                    "quota" in lower_msg
                    or "dailylimit" in lower_msg
                    or "quotaexceeded" in lower_msg
                ):
                    raise QuotaExhaustedError(
                        "YouTube API quota exhausted",
                        status_code=status,
                    ) from e
                if "ratelimit" in lower_msg or "rate limit" in lower_msg:
                    raise RateLimitError(
                        "YouTube API rate-limited (403)", status_code=status,
                    ) from e
                raise CollectionError(msg, status_code=status) from e
            if status == 429:
                raise RateLimitError(
                    "YouTube API rate-limited (429)", status_code=status,
                ) from e
            if status == 404:
                raise ResourceNotFoundError(
                    "YouTube resource not found", status_code=status,
                ) from e
            if status is not None and 500 <= status < 600:
                raise NetworkError(
                    f"YouTube server error {status}", status_code=status,
                ) from e
            # Unknown error → re-raise as generic collection error
            raise CollectionError(f"YouTube API error: {msg}") from e

    # -- Channel resolution ----------------------------------------------

    def resolve_channel(self, handle_or_id: str) -> str:
        """Return the canonical UC... channel ID.

        Accepts a raw ID (``UC...``), a handle (``@name`` or ``name``),
        or a channel URL (``https://youtube.com/@name`` or ``/channel/UC...``).
        """
        h = handle_or_id.strip()
        if not h:
            raise ResourceNotFoundError("Empty channel identifier")

        # URL forms
        if h.startswith("http"):
            if "/channel/" in h:
                return h.split("/channel/")[-1].split("/")[0].split("?")[0]
            if "/@" in h:
                h = "@" + h.split("/@")[-1].split("/")[0].split("?")[0]
            elif "/c/" in h or "/user/" in h:
                # Legacy custom-URL / username forms are not resolvable via
                # forHandle (that API only accepts @handles); resolving them
                # would need a different lookup path. Fail clearly instead
                # of silently treating the raw URL as a garbage handle.
                raise ResourceNotFoundError(
                    f"Unsupported YouTube URL format (legacy /c/ or /user/ "
                    f"custom URL): {handle_or_id!r}. Use the channel's "
                    f"@handle or /channel/UC... URL instead.",
                    handle=handle_or_id,
                )

        # Direct UC... ID
        if h.startswith("UC") and len(h) == 24:
            return h

        # Handle lookup
        handle = h if h.startswith("@") else "@" + h
        self._ensure_quota("channels_list")
        req = self._client.channels().list(part="id", forHandle=handle)
        resp = self._execute(req)
        self._spend_quota("channels_list")

        items = resp.get("items") or []
        if not items:
            raise ResourceNotFoundError(
                f"YouTube channel not found for handle {handle!r}",
                handle=handle,
            )
        return items[0]["id"]

    def channel_metadata(self, channel_id: str) -> dict[str, Any]:
        """Return channel metadata including uploads playlist ID."""
        self._ensure_quota("channels_list")
        req = self._client.channels().list(
            part="snippet,contentDetails,statistics",
            id=channel_id,
        )
        resp = self._execute(req)
        self._spend_quota("channels_list")

        items = resp.get("items") or []
        if not items:
            raise ResourceNotFoundError(
                f"Channel not found: {channel_id}", channel_id=channel_id,
            )
        item = items[0]
        snippet = item["snippet"]
        stats = item.get("statistics", {})
        return {
            "channel_id": channel_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "published_at": snippet.get("publishedAt", ""),
            "uploads_ref": item["contentDetails"]["relatedPlaylists"]["uploads"],
            "subscriber_count": int(stats.get("subscriberCount", 0) or 0),
            "video_count": int(stats.get("videoCount", 0) or 0),
            "view_count": int(stats.get("viewCount", 0) or 0),
        }

    # -- Video enumeration ------------------------------------------------

    def enumerate_videos(
        self,
        uploads_ref: str,
        *,
        window_start_iso: str,
        window_end_iso: str,
    ) -> Iterable[str]:
        """Yield video IDs published within the window (newest-first).

        Uses playlistItems.list on the uploads playlist which is
        chronologically ordered newest-first. Stops early when a video
        older than window_start is encountered.
        """
        start_dt = parse_iso8601(window_start_iso if "T" in window_start_iso
                                 else window_start_iso + "T00:00:00Z")
        end_dt = parse_iso8601(window_end_iso if "T" in window_end_iso
                               else window_end_iso + "T23:59:59Z")
        page_token: str | None = None
        while True:
            self._ensure_quota("playlistItems_list")
            req = self._client.playlistItems().list(
                part="contentDetails",
                playlistId=uploads_ref,
                maxResults=50,
                pageToken=page_token,
            )
            resp = self._execute(req)
            self._spend_quota("playlistItems_list")

            for item in resp.get("items") or []:
                cd = item.get("contentDetails", {})
                vid = cd.get("videoId")
                published = cd.get("videoPublishedAt", "")
                if not vid or not published:
                    continue
                try:
                    pub_dt = parse_iso8601(published)
                except ValueError:
                    continue
                if pub_dt < start_dt:
                    # Playlist is newest-first; the rest is out of window.
                    return
                if pub_dt <= end_dt:
                    yield vid
            page_token = resp.get("nextPageToken")
            if not page_token:
                return

    # -- Video metadata batch fetch --------------------------------------

    def fetch_video_metadata(
        self,
        video_ids: list[str],
        *,
        analyst_key: str,
    ) -> list[VideoRecord]:
        """Fetch VideoRecord for each of ``video_ids`` (50 per API call)."""
        records: list[VideoRecord] = []
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            self._ensure_quota("videos_list")
            req = self._client.videos().list(
                part="snippet,contentDetails,statistics,status",
                id=",".join(batch),
            )
            resp = self._execute(req)
            self._spend_quota("videos_list")
            for item in resp.get("items") or []:
                records.append(self._to_video_record(item, analyst_key))
        return records

    def _to_video_record(self, item: dict[str, Any], analyst_key: str) -> VideoRecord:
        snippet = item.get("snippet", {})
        content = item.get("contentDetails", {})
        stats = item.get("statistics", {})
        status = item.get("status", {})

        title = snippet.get("title", "")
        description = snippet.get("description", "")
        duration_sec = iso8601_duration_to_seconds(content.get("duration", ""))
        made_for_kids = bool(status.get("madeForKids", False))

        # Apply eligibility rules
        eligible = True
        reason = ""
        if 0 < duration_sec <= self.shorts_max_duration_sec:
            eligible = False
            reason = "shorts"
        elif made_for_kids:
            eligible = False
            reason = "made_for_kids"
        elif self._contains_promo(title + " " + description):
            eligible = False
            reason = "promo"

        likes_raw = stats.get("likeCount")
        return VideoRecord(
            analyst_key=analyst_key,
            video_id=item["id"],
            published_at=snippet.get("publishedAt", ""),
            title=title,
            description=description,
            duration_sec=duration_sec,
            views=int(stats.get("viewCount", 0) or 0),
            likes=int(likes_raw) if likes_raw is not None else None,
            comment_count=int(stats.get("commentCount", 0) or 0),
            made_for_kids=made_for_kids,
            category_id=snippet.get("categoryId", ""),
            eligible=eligible,
            exclusion_reason=reason,
            selected=False,  # sampler decides later
        )

    def _contains_promo(self, text: str) -> bool:
        if not self.promo_keywords:
            return False
        lower = text.lower()
        return any(kw and kw in lower for kw in self.promo_keywords)

    # -- Comments (anonymised at ingest) ---------------------------------

    def fetch_top_level_comments(
        self,
        video_id: str,
        *,
        analyst_key: str,
        salt: str,
        window_start_iso: str,
        window_end_iso: str,
    ) -> list[CommentRecord]:
        """Fetch all top-level comments within window, anonymised at ingest."""
        if not salt:
            raise ValueError("fetch_top_level_comments requires a non-empty salt")

        start_dt = parse_iso8601(window_start_iso if "T" in window_start_iso
                                 else window_start_iso + "T00:00:00Z")
        end_dt = parse_iso8601(window_end_iso if "T" in window_end_iso
                               else window_end_iso + "T23:59:59Z")

        results: list[CommentRecord] = []
        page_token: str | None = None
        while True:
            self._ensure_quota("commentThreads_list")
            req = self._client.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=100,
                textFormat="plainText",
                pageToken=page_token,
            )
            try:
                resp = self._execute(req)
            except ResourceNotFoundError:
                # Comments disabled → empty result, not an error.
                return results
            except CollectionError as e:
                # commentsDisabled surfaces as 403 with specific reason
                if "commentsDisabled" in str(e) or "disabled" in str(e).lower():
                    return results
                raise
            self._spend_quota("commentThreads_list")

            for thread in resp.get("items") or []:
                top = (
                    thread.get("snippet", {})
                    .get("topLevelComment", {})
                    .get("snippet")
                )
                if top is None:
                    # Malformed/unexpected shape for this one record; skip
                    # it rather than let a single bad item abort the run.
                    _log.warning("comment_thread_malformed", video_id=video_id,
                                 thread_id=thread.get("id"))
                    continue
                published = top.get("publishedAt", "")
                if not published:
                    continue
                try:
                    pub_dt = parse_iso8601(published)
                except ValueError:
                    continue
                if pub_dt < start_dt or pub_dt > end_dt:
                    continue

                raw_author = top.get("authorChannelId", {}).get("value", "") or ""
                commenter_hash = hash_identifier(raw_author, salt)
                text = top.get("textDisplay", "") or ""

                results.append(
                    CommentRecord(
                        analyst_key=analyst_key,
                        video_id=video_id,
                        comment_id=thread["id"],
                        commenter_hash=commenter_hash,
                        posted_date=truncate_to_day(published),
                        text_raw=text,
                        text_clean="",  # populated in preprocessing
                        tokens=[],  # populated in preprocessing
                        n_tokens=0,
                        emojis=[],
                        likes=int(top.get("likeCount", 0) or 0),
                    ),
                )
            page_token = resp.get("nextPageToken")
            if not page_token:
                return results


__all__ = ["YouTubePlatformProvider"]
