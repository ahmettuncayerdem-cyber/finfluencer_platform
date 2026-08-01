"""Tests for finfluencer.providers.platform.youtube (Commit 1.2 hardening).

These tests EXIST TO GUARD three specific hardening behaviours introduced
in Commit 1.2, replacing an earlier debug-print-based error path:

1. A malformed ``commentThreads`` API response item (missing/short-shaped
   ``snippet.topLevelComment.snippet``) is skipped via ``continue`` rather
   than raising and aborting the whole page.
2. Legacy YouTube URL formats (``/c/...``, ``/user/...``) are rejected
   with a clear :class:`ResourceNotFoundError` in ``resolve_channel``,
   instead of being silently mistreated as a garbage ``@handle``.
3. ``_execute`` classifies HTTP error responses into the correct typed
   exception (403 quota / 403 rate-limit / 403 comments-disabled /
   403 other / 429 / 404 / 5xx / unknown), matching the exception
   hierarchy in ``core.exceptions``.

No real network or googleapiclient calls are made anywhere in this file:
the provider is always constructed with a stub ``client_factory``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from finfluencer.core.exceptions import (
    CollectionError,
    CommentsDisabledError,
    NetworkError,
    QuotaExhaustedError,
    RateLimitError,
    ResourceNotFoundError,
)
from finfluencer.providers.platform.youtube import YouTubePlatformProvider


# ============================================================================
# Shared stubs
# ============================================================================


class _FakeHttpError(Exception):
    """Mimics the shape of googleapiclient.errors.HttpError closely enough
    for `_execute`'s error mapping: a `.resp.status` int and a message."""

    def __init__(self, status: int | None, message: str) -> None:
        super().__init__(message)
        if status is not None:
            self.resp = SimpleNamespace(status=status)


def _make_provider(client: Any = None, **retry_kwargs: Any) -> YouTubePlatformProvider:
    """Construct a provider with no real API key requirement and a stub
    client_factory that returns `client` (or a bare sentinel if the test
    doesn't need one, e.g. resolve_channel's legacy-URL short-circuit).

    `retry_kwargs` (T-016) lets retry tests override `retry_max_attempts` /
    `retry_wait_initial_sec` / `retry_wait_max_sec` -- e.g. to keep retry
    tests fast (near-zero wait) without changing the class's own
    production-conservative defaults.
    """
    return YouTubePlatformProvider(
        api_key="fake-key-for-tests",
        client_factory=lambda _api_key: client if client is not None else object(),
        **retry_kwargs,
    )


# ============================================================================
# (a) Malformed comment-thread response shape -> skipped, not fatal
# ============================================================================


class _StubCommentThreadsClient:
    """Stub googleapiclient service exposing only commentThreads().list()."""

    def __init__(self, response: dict) -> None:
        self._response = response

    def commentThreads(self) -> "_StubCommentThreadsClient":
        return self

    def list(self, **kwargs: Any) -> "_StubCommentThreadsClient":
        return self

    def execute(self) -> dict:
        return self._response


class TestMalformedCommentThreadIsSkipped:
    def test_malformed_items_are_skipped_well_formed_item_is_kept(self):
        response = {
            "items": [
                {
                    "id": "thread-good",
                    "snippet": {
                        "topLevelComment": {
                            "snippet": {
                                "publishedAt": "2025-06-15T12:00:00Z",
                                "textDisplay": "merhaba dunya",
                                "authorChannelId": {"value": "UCauthor000000000000000"},
                                "likeCount": 3,
                            },
                        },
                    },
                },
                # Missing topLevelComment entirely.
                {"id": "thread-missing-toplevel", "snippet": {}},
                # Missing snippet entirely (e.g. a deleted/moderated thread
                # surfaced with a truncated payload).
                {"id": "thread-no-snippet"},
                # topLevelComment present but its own snippet is missing.
                {
                    "id": "thread-missing-inner-snippet",
                    "snippet": {"topLevelComment": {}},
                },
            ],
            # Single page.
        }
        provider = _make_provider(_StubCommentThreadsClient(response))

        results = provider.fetch_top_level_comments(
            "video123",
            analyst_key="satiroglu",
            salt="unit-test-salt",
            window_start_iso="2025-01-01",
            window_end_iso="2025-12-31",
        )

        # Only the well-formed thread survives; the three malformed shapes
        # were skipped via `continue`, not raised.
        assert len(results) == 1
        assert results[0].comment_id == "thread-good"
        assert results[0].text_raw == "merhaba dunya"
        assert results[0].likes == 3
        # Anonymisation happened: the raw author id must not leak through.
        assert "UCauthor000000000000000" not in results[0].commenter_hash


# ============================================================================
# (b) Legacy /c/ and /user/ URL formats -> ResourceNotFoundError
# ============================================================================


class TestLegacyUrlFormatsRejected:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/c/SomeLegacyCustomName",
            "https://www.youtube.com/user/SomeUsername",
            "http://youtube.com/c/AnotherOne",
        ],
    )
    def test_legacy_url_raises_resource_not_found(self, url: str):
        # client_factory is never exercised: the legacy-URL branch raises
        # before any API call would be made.
        provider = _make_provider()

        with pytest.raises(ResourceNotFoundError) as exc_info:
            provider.resolve_channel(url)

        assert exc_info.value.context.get("handle") == url

    def test_modern_at_handle_url_is_not_affected(self):
        """Regression guard: the legacy-URL fix must not misfire on the
        modern @handle URL form, which takes a different, valid branch."""
        provider = _make_provider(
            client=_StubChannelsClient({"items": [{"id": "UCmodern0000000000000000"}]}),
        )
        channel_id = provider.resolve_channel("https://www.youtube.com/@somehandle")
        assert channel_id == "UCmodern0000000000000000"

    def test_channel_url_is_not_affected(self):
        provider = _make_provider()
        channel_id = provider.resolve_channel(
            "https://www.youtube.com/channel/UCdirect00000000000000",
        )
        assert channel_id == "UCdirect00000000000000"


class _StubChannelsClient:
    """Stub googleapiclient service exposing only channels().list()."""

    def __init__(self, response: dict) -> None:
        self._response = response

    def channels(self) -> "_StubChannelsClient":
        return self

    def list(self, **kwargs: Any) -> "_StubChannelsClient":
        return self

    def execute(self) -> dict:
        return self._response


# ============================================================================
# (c) _execute HTTP status -> typed exception classification
# ============================================================================


class _RaisingRequest:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def execute(self) -> Any:
        raise self._error


class TestExecuteErrorClassification:
    def test_403_quota_exceeded(self):
        provider = _make_provider()
        req = _RaisingRequest(_FakeHttpError(403, "The request cannot be completed because you have exceeded your quota."))
        with pytest.raises(QuotaExhaustedError):
            provider._execute(req)

    def test_403_comments_disabled(self):
        """ADR-P2-002 (R2): comments-disabled is a distinct, expected
        content state -- NOT a missing-resource error. Was asserted as
        ResourceNotFoundError before this fix, which is exactly the
        conflation R2 identified (a 404/deleted-video case mapped to
        the same type). Updated to the dedicated CommentsDisabledError
        introduced for this fix."""
        provider = _make_provider()
        req = _RaisingRequest(_FakeHttpError(403, "commentsDisabled: The video has disabled comments."))
        with pytest.raises(CommentsDisabledError):
            provider._execute(req)

    def test_403_rate_limited(self):
        # T-016: retry_max_attempts=1 keeps this test instant -- the retry
        # loop's own behavior (does it retry at all, and how many times) is
        # covered separately in TestRetryBehavior below; this test's job is
        # only the exception-type classification, unchanged.
        provider = _make_provider(retry_max_attempts=1)
        req = _RaisingRequest(_FakeHttpError(403, "User rate limit exceeded."))
        with pytest.raises(RateLimitError):
            provider._execute(req)

    def test_403_other_reason_is_generic_collection_error(self):
        provider = _make_provider()
        req = _RaisingRequest(_FakeHttpError(403, "accessNotConfigured: API not enabled."))
        with pytest.raises(CollectionError):
            provider._execute(req)

    def test_429_rate_limited(self):
        provider = _make_provider(retry_max_attempts=1)  # T-016: see note above
        req = _RaisingRequest(_FakeHttpError(429, "Too Many Requests"))
        with pytest.raises(RateLimitError):
            provider._execute(req)

    def test_404_resource_not_found(self):
        """ADR-P2-002 constraint: ResourceNotFoundError semantics are
        UNCHANGED by this fix -- it must continue to represent only
        genuinely missing resources. This test is unmodified from
        before R2; its continued, unmodified pass is itself part of the
        constraint's verification."""
        provider = _make_provider()
        req = _RaisingRequest(_FakeHttpError(404, "Not Found"))
        with pytest.raises(ResourceNotFoundError):
            provider._execute(req)

    def test_5xx_is_network_error(self):
        provider = _make_provider(retry_max_attempts=1)  # T-016: see note above
        req = _RaisingRequest(_FakeHttpError(503, "Service Unavailable"))
        with pytest.raises(NetworkError):
            provider._execute(req)

    def test_unknown_status_is_generic_collection_error(self):
        provider = _make_provider()
        # No `.resp` attribute at all -> status resolves to None.
        req = _RaisingRequest(RuntimeError("totally unexpected failure"))
        with pytest.raises(CollectionError):
            provider._execute(req)


# ============================================================================
# (c-2) T-016: retry policy -- transient errors retried, non-transient not
# ============================================================================


class _FlakyRequest:
    """A request whose `.execute()` result/exception varies by call number --
    proves the retry loop actually retries (not just classifies), and that it
    stops retrying (or never starts) for the right exception types."""

    def __init__(self, outcomes: list[Exception | dict]) -> None:
        self._outcomes = outcomes
        self.call_count = 0

    def execute(self) -> Any:
        self.call_count += 1
        outcome = self._outcomes[self.call_count - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class TestRetryBehavior:
    def test_rate_limit_error_is_retried_then_succeeds(self):
        # Fails twice with a retryable error, succeeds on the third call.
        provider = _make_provider(retry_max_attempts=3, retry_wait_initial_sec=0.0)
        req = _FlakyRequest(
            [
                _FakeHttpError(429, "Too Many Requests"),
                _FakeHttpError(429, "Too Many Requests"),
                {"items": []},
            ],
        )
        result = provider._execute(req)
        assert result == {"items": []}
        assert req.call_count == 3

    def test_network_error_is_retried_then_succeeds(self):
        provider = _make_provider(retry_max_attempts=3, retry_wait_initial_sec=0.0)
        req = _FlakyRequest(
            [
                _FakeHttpError(503, "Service Unavailable"),
                {"items": []},
            ],
        )
        result = provider._execute(req)
        assert result == {"items": []}
        assert req.call_count == 2

    def test_rate_limit_error_still_raises_after_attempts_exhausted(self):
        provider = _make_provider(retry_max_attempts=2, retry_wait_initial_sec=0.0)
        req = _FlakyRequest(
            [
                _FakeHttpError(429, "Too Many Requests"),
                _FakeHttpError(429, "Too Many Requests"),
                _FakeHttpError(429, "Too Many Requests"),  # never reached
            ],
        )
        with pytest.raises(RateLimitError):
            provider._execute(req)
        assert req.call_count == 2  # stopped after retry_max_attempts, not 3

    def test_quota_exhausted_is_not_retried(self):
        provider = _make_provider(retry_max_attempts=3, retry_wait_initial_sec=0.0)
        req = _FlakyRequest(
            [
                _FakeHttpError(403, "The request cannot be completed because you have exceeded your quota."),
                {"items": []},  # would succeed if (incorrectly) retried
            ],
        )
        with pytest.raises(QuotaExhaustedError):
            provider._execute(req)
        assert req.call_count == 1  # propagated immediately, no retry attempted

    def test_resource_not_found_is_not_retried(self):
        provider = _make_provider(retry_max_attempts=3, retry_wait_initial_sec=0.0)
        req = _FlakyRequest(
            [
                _FakeHttpError(404, "Not Found"),
                {"items": []},
            ],
        )
        with pytest.raises(ResourceNotFoundError):
            provider._execute(req)
        assert req.call_count == 1


# ============================================================================
# (d) fetch_top_level_comments -- ADR-P2-002 (R2) behavioural cases 1-3
#
# Case 4 (one invalid video inside a batch -> logged, skipped, remaining
# videos continue) lives in tests/unit/test_collect/test_comments.py,
# since it is collect_comments' loop behaviour, not the provider's.
# ============================================================================


class _StubCommentThreadsRaisingClient:
    """Stub googleapiclient service whose commentThreads().list().execute()
    raises -- mirrors _StubCommentThreadsClient's shape but for the
    error-path tests below."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def commentThreads(self) -> "_StubCommentThreadsRaisingClient":
        return self

    def list(self, **kwargs: Any) -> "_StubCommentThreadsRaisingClient":
        return self

    def execute(self) -> dict:
        raise self._error


class TestFetchTopLevelCommentsBehaviouralCases:
    """Demonstrates the four cases required by ADR-P2-002 (1-3 here)."""

    def test_case_1_comments_enabled_returns_collected_comments(self):
        """Case 1: comments enabled -> comments collected."""
        response = {
            "items": [
                {
                    "id": "thread-1",
                    "snippet": {
                        "topLevelComment": {
                            "snippet": {
                                "publishedAt": "2025-06-15T12:00:00Z",
                                "textDisplay": "ilk yorum",
                                "authorChannelId": {"value": "UCauthor000000000000000"},
                                "likeCount": 1,
                            },
                        },
                    },
                },
            ],
        }
        provider = _make_provider(_StubCommentThreadsClient(response))

        results = provider.fetch_top_level_comments(
            "video_ok",
            analyst_key="satiroglu",
            salt="unit-test-salt",
            window_start_iso="2025-01-01",
            window_end_iso="2025-12-31",
        )

        assert len(results) == 1
        assert results[0].text_raw == "ilk yorum"

    def test_case_2_comments_disabled_returns_empty_list_not_error(self):
        """Case 2: comments disabled -> empty collection, exactly as
        intended (an expected content state, not a failure)."""
        provider = _make_provider(
            _StubCommentThreadsRaisingClient(
                _FakeHttpError(403, "commentsDisabled: The video has disabled comments."),
            ),
        )

        results = provider.fetch_top_level_comments(
            "video_disabled",
            analyst_key="satiroglu",
            salt="unit-test-salt",
            window_start_iso="2025-01-01",
            window_end_iso="2025-12-31",
        )

        assert results == []

    def test_case_3_video_deleted_raises_resource_not_found(self):
        """Case 3: video deleted/invalid (404) -> ResourceNotFoundError.

        This is the core R2 fix: before it, this case was silently
        swallowed as an empty list, indistinguishable from Case 2."""
        provider = _make_provider(
            _StubCommentThreadsRaisingClient(_FakeHttpError(404, "Not Found")),
        )

        with pytest.raises(ResourceNotFoundError):
            provider.fetch_top_level_comments(
                "video_deleted",
                analyst_key="satiroglu",
                salt="unit-test-salt",
                window_start_iso="2025-01-01",
                window_end_iso="2025-12-31",
            )


# ============================================================================
# (e) R1 (ADR-P2-001) -- behavioural-contract tests for the five previously
# 0%-covered methods: channel_metadata, enumerate_videos,
# fetch_video_metadata / _to_video_record, _contains_promo.
#
# Each method's tests are organised happy-path / boundary-condition /
# failure-path, per the approved packet. _to_video_record and
# _contains_promo are private helpers and are exercised only through
# fetch_video_metadata's public surface (their outputs are directly
# observable there), not called directly.
# ============================================================================


class _StubChannelMetadataClient:
    """Stub exposing channels().list().execute() -- reused shape from
    _StubChannelsClient above, kept separate for this section's own
    readability (channel_metadata's response shape differs from
    resolve_channel's id-only shape)."""

    def __init__(self, response: dict) -> None:
        self._response = response

    def channels(self) -> "_StubChannelMetadataClient":
        return self

    def list(self, **kwargs: Any) -> "_StubChannelMetadataClient":
        return self

    def execute(self) -> dict:
        return self._response


class TestChannelMetadata:
    """Contract: return a flat dict of channel metadata, coercing string
    statistics to int and defaulting missing/empty stats to 0; raise
    ResourceNotFoundError when the channel doesn't exist."""

    def test_happy_path_full_response_maps_every_field(self):
        response = {
            "items": [
                {
                    "snippet": {
                        "title": "Örnek Kanal",
                        "description": "Bir açıklama.",
                        "publishedAt": "2020-01-01T00:00:00Z",
                    },
                    "contentDetails": {
                        "relatedPlaylists": {"uploads": "UUuploads0000000000000"},
                    },
                    "statistics": {
                        "subscriberCount": "12345",
                        "videoCount": "67",
                        "viewCount": "890123",
                    },
                },
            ],
        }
        provider = _make_provider(_StubChannelMetadataClient(response))

        meta = provider.channel_metadata("UCtarget0000000000000000")

        assert meta == {
            "channel_id": "UCtarget0000000000000000",
            "title": "Örnek Kanal",
            "description": "Bir açıklama.",
            "published_at": "2020-01-01T00:00:00Z",
            "uploads_ref": "UUuploads0000000000000",
            "subscriber_count": 12345,
            "video_count": 67,
            "view_count": 890123,
        }

    def test_boundary_missing_statistics_default_to_zero(self):
        """A channel with statistics hidden (a real, documented YouTube
        API possibility) must not crash -- counts default to 0."""
        response = {
            "items": [
                {
                    "snippet": {"title": "Gizli İstatistik"},
                    "contentDetails": {
                        "relatedPlaylists": {"uploads": "UUhidden000000000000000"},
                    },
                    "statistics": {},
                },
            ],
        }
        provider = _make_provider(_StubChannelMetadataClient(response))

        meta = provider.channel_metadata("UChidden0000000000000000")

        assert meta["subscriber_count"] == 0
        assert meta["video_count"] == 0
        assert meta["view_count"] == 0
        # snippet.description was absent entirely -- must default to "",
        # not raise KeyError.
        assert meta["description"] == ""

    def test_failure_path_no_items_raises_resource_not_found(self):
        """A malformed/nonexistent channel_id must fail loudly, not
        return a garbage/empty dict."""
        provider = _make_provider(_StubChannelMetadataClient({"items": []}))

        with pytest.raises(ResourceNotFoundError) as exc_info:
            provider.channel_metadata("UCnonexistent00000000000")

        assert exc_info.value.context.get("channel_id") == "UCnonexistent00000000000"

    def test_quota_is_spent_on_success(self):
        """Observable side effect per the module's own documented
        contract ('quota accounting is the provider's responsibility'):
        a successful call must debit exactly its unit cost."""
        from finfluencer.core.budgets import QuotaTracker

        response = {
            "items": [
                {
                    "snippet": {"title": "X"},
                    "contentDetails": {"relatedPlaylists": {"uploads": "UUx"}},
                    "statistics": {},
                },
            ],
        }
        tracker = QuotaTracker(daily_units=10_000, safety_margin=100)
        provider = YouTubePlatformProvider(
            api_key="fake-key-for-tests",
            quota_tracker=tracker,
            client_factory=lambda _k: _StubChannelMetadataClient(response),
        )

        provider.channel_metadata("UCany0000000000000000000")

        assert tracker.used_units == 1  # channels_list unit cost per _UNIT_COSTS


# ----------------------------------------------------------------------


class _StubPlaylistItemsClient:
    """Stub exposing playlistItems().list().execute(), supporting
    multi-page responses keyed by pageToken and an optional injected
    failure on a specific page (for the failure-path test)."""

    def __init__(
        self,
        responses_by_token: dict[str | None, dict],
        *,
        error_on_token: str | None = "__never__",
        error: Exception | None = None,
    ) -> None:
        self._responses = responses_by_token
        self._error_on_token = error_on_token
        self._error = error
        self.requested_tokens: list[str | None] = []
        self._pending_token: str | None = None

    def playlistItems(self) -> "_StubPlaylistItemsClient":
        return self

    def list(self, **kwargs: Any) -> "_StubPlaylistItemsClient":
        self._pending_token = kwargs.get("pageToken")
        return self

    def execute(self) -> dict:
        token = self._pending_token
        self.requested_tokens.append(token)
        if token == self._error_on_token:
            raise self._error
        return self._responses[token]


class TestEnumerateVideos:
    """Contract: yield video IDs published within [window_start,
    window_end] from a newest-first playlist; stop as soon as an item
    older than window_start is seen (early exit, not a full scan);
    silently skip malformed items; paginate via nextPageToken."""

    def test_happy_path_single_page_within_window(self):
        response = {
            None: {
                "items": [
                    {
                        "contentDetails": {
                            "videoId": "v_in_window",
                            "videoPublishedAt": "2025-06-15T12:00:00Z",
                        },
                    },
                ],
            },
        }
        provider = _make_provider(_StubPlaylistItemsClient(response))

        ids = list(
            provider.enumerate_videos(
                "UUuploads",
                window_start_iso="2025-06-01",
                window_end_iso="2025-06-30",
            ),
        )

        assert ids == ["v_in_window"]

    def test_boundary_start_of_window_is_inclusive(self):
        """An item published at exactly window_start (00:00:00Z) must be
        yielded -- the comparison is `pub_dt < start_dt` to stop, so
        equality does not trigger early exit."""
        response = {
            None: {
                "items": [
                    {
                        "contentDetails": {
                            "videoId": "v_exact_start",
                            "videoPublishedAt": "2025-06-01T00:00:00Z",
                        },
                    },
                ],
            },
        }
        provider = _make_provider(_StubPlaylistItemsClient(response))

        ids = list(
            provider.enumerate_videos(
                "UUuploads",
                window_start_iso="2025-06-01",
                window_end_iso="2025-06-30",
            ),
        )

        assert ids == ["v_exact_start"]

    def test_boundary_end_of_window_is_inclusive_but_after_end_is_skipped_not_stopped(self):
        """A bare end date expands to 23:59:59Z end-of-day. An item at
        exactly that instant is yielded (`pub_dt <= end_dt`). An item
        one second past it is skipped via plain `continue` -- it does
        NOT trigger early exit, unlike an item before window_start.
        This distinction (skip vs. stop) is a real, easy-to-miss
        behavioural quirk worth pinning down explicitly."""
        response = {
            None: {
                "items": [
                    {
                        "contentDetails": {
                            "videoId": "v_after_end",
                            "videoPublishedAt": "2025-07-01T00:00:00Z",
                        },
                    },
                    {
                        "contentDetails": {
                            "videoId": "v_exact_end",
                            "videoPublishedAt": "2025-06-30T23:59:59Z",
                        },
                    },
                ],
            },
        }
        provider = _make_provider(_StubPlaylistItemsClient(response))

        ids = list(
            provider.enumerate_videos(
                "UUuploads",
                window_start_iso="2025-06-01",
                window_end_iso="2025-06-30",
            ),
        )

        # v_after_end was skipped (not yielded), but enumeration did NOT
        # stop because of it -- v_exact_end, listed after it, was still
        # reached and yielded.
        assert ids == ["v_exact_end"]

    def test_boundary_item_older_than_start_triggers_early_exit(self):
        """Playlist is newest-first: once an item older than
        window_start is seen, the rest of the (older) playlist is
        assumed out-of-window and enumeration stops immediately --
        items listed after it in the same page must NOT be yielded,
        even if one of them would otherwise be in-window."""
        response = {
            None: {
                "items": [
                    {
                        "contentDetails": {
                            "videoId": "v_within",
                            "videoPublishedAt": "2025-06-15T00:00:00Z",
                        },
                    },
                    {
                        "contentDetails": {
                            "videoId": "v_too_old",
                            "videoPublishedAt": "2025-01-01T00:00:00Z",
                        },
                    },
                    {
                        # Would be in-window on its own, but comes after
                        # the too-old item -- must never be reached.
                        "contentDetails": {
                            "videoId": "v_unreachable",
                            "videoPublishedAt": "2025-06-10T00:00:00Z",
                        },
                    },
                ],
                "nextPageToken": "would-be-page-2",
            },
        }
        client = _StubPlaylistItemsClient(response)
        provider = _make_provider(client)

        ids = list(
            provider.enumerate_videos(
                "UUuploads",
                window_start_iso="2025-06-01",
                window_end_iso="2025-06-30",
            ),
        )

        assert ids == ["v_within"]
        # Early exit means pagination itself must stop too -- only one
        # page was ever requested, despite a nextPageToken being present.
        assert client.requested_tokens == [None]

    def test_boundary_malformed_items_are_skipped_without_raising(self):
        """Items missing videoId or videoPublishedAt, or carrying an
        unparseable timestamp, must be silently skipped -- one bad item
        must not abort enumeration of the rest."""
        response = {
            None: {
                "items": [
                    {"contentDetails": {"videoPublishedAt": "2025-06-15T00:00:00Z"}},  # no videoId
                    {"contentDetails": {"videoId": "v_no_date"}},  # no videoPublishedAt
                    {
                        "contentDetails": {
                            "videoId": "v_bad_date",
                            "videoPublishedAt": "not-a-real-timestamp",
                        },
                    },
                    {
                        "contentDetails": {
                            "videoId": "v_good",
                            "videoPublishedAt": "2025-06-15T00:00:00Z",
                        },
                    },
                ],
            },
        }
        provider = _make_provider(_StubPlaylistItemsClient(response))

        ids = list(
            provider.enumerate_videos(
                "UUuploads",
                window_start_iso="2025-06-01",
                window_end_iso="2025-06-30",
            ),
        )

        assert ids == ["v_good"]

    def test_happy_path_pagination_across_multiple_pages(self):
        responses = {
            None: {
                "items": [
                    {
                        "contentDetails": {
                            "videoId": "v_page1",
                            "videoPublishedAt": "2025-06-20T00:00:00Z",
                        },
                    },
                ],
                "nextPageToken": "page2",
            },
            "page2": {
                "items": [
                    {
                        "contentDetails": {
                            "videoId": "v_page2",
                            "videoPublishedAt": "2025-06-10T00:00:00Z",
                        },
                    },
                ],
                # No nextPageToken -- last page.
            },
        }
        client = _StubPlaylistItemsClient(responses)
        provider = _make_provider(client)

        ids = list(
            provider.enumerate_videos(
                "UUuploads",
                window_start_iso="2025-06-01",
                window_end_iso="2025-06-30",
            ),
        )

        assert ids == ["v_page1", "v_page2"]
        assert client.requested_tokens == [None, "page2"]

    def test_failure_path_api_error_propagates_when_generator_is_consumed(self):
        """enumerate_videos is a generator -- the underlying HttpError
        must still surface as the correctly typed exception (via
        _execute) once the caller actually iterates it."""
        client = _StubPlaylistItemsClient(
            {},
            error_on_token=None,
            error=_FakeHttpError(403, "The request cannot be completed because you have exceeded your quota."),
        )
        provider = _make_provider(client)

        gen = provider.enumerate_videos(
            "UUuploads",
            window_start_iso="2025-06-01",
            window_end_iso="2025-06-30",
        )
        with pytest.raises(QuotaExhaustedError):
            list(gen)

    def test_quota_is_spent_per_page(self):
        from finfluencer.core.budgets import QuotaTracker

        responses = {
            None: {
                "items": [],
                "nextPageToken": "page2",
            },
            "page2": {"items": []},
        }
        tracker = QuotaTracker(daily_units=10_000, safety_margin=100)
        provider = YouTubePlatformProvider(
            api_key="fake-key-for-tests",
            quota_tracker=tracker,
            client_factory=lambda _k: _StubPlaylistItemsClient(responses),
        )

        list(
            provider.enumerate_videos(
                "UUuploads",
                window_start_iso="2025-06-01",
                window_end_iso="2025-06-30",
            ),
        )

        assert tracker.used_units == 2  # one playlistItems_list unit per page


# ----------------------------------------------------------------------


class _StubVideosClient:
    """Stub exposing videos().list().execute(). Returns one response per
    call, in the order supplied, so batching (multiple calls for >50
    IDs) is directly observable via `requested_id_batches`."""

    def __init__(self, responses: list[dict]) -> None:
        self._responses = responses
        self.requested_id_batches: list[str] = []
        self._pending_id = None

    def videos(self) -> "_StubVideosClient":
        return self

    def list(self, **kwargs: Any) -> "_StubVideosClient":
        self._pending_id = kwargs.get("id")
        return self

    def execute(self) -> dict:
        self.requested_id_batches.append(self._pending_id)
        idx = len(self.requested_id_batches) - 1
        return self._responses[idx]


class _StubVideosRaisingClient:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def videos(self) -> "_StubVideosRaisingClient":
        return self

    def list(self, **kwargs: Any) -> "_StubVideosRaisingClient":
        return self

    def execute(self) -> dict:
        raise self._error


def _video_item(
    video_id: str,
    *,
    duration: str = "PT10M",
    made_for_kids: bool = False,
    title: str = "Bir video",
    description: str = "",
    view_count: str | None = "100",
    like_count: str | None = "10",
    comment_count: str | None = "5",
) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    if view_count is not None:
        stats["viewCount"] = view_count
    if like_count is not None:
        stats["likeCount"] = like_count
    if comment_count is not None:
        stats["commentCount"] = comment_count
    return {
        "id": video_id,
        "snippet": {
            "title": title,
            "description": description,
            "publishedAt": "2025-06-01T12:00:00Z",
            "categoryId": "25",
        },
        "contentDetails": {"duration": duration},
        "statistics": stats,
        "status": {"madeForKids": made_for_kids},
    }


class TestFetchVideoMetadataBatching:
    """Contract: fetch VideoRecords for arbitrarily many video_ids, 50
    per API call (YouTube's own batch limit), preserving order and
    concatenating across batches."""

    def test_happy_path_single_batch_returns_one_record_per_item(self):
        client = _StubVideosClient([
            {"items": [_video_item("v1"), _video_item("v2")]},
        ])
        provider = _make_provider(client)

        records = provider.fetch_video_metadata(["v1", "v2"], analyst_key="satiroglu")

        assert [r.video_id for r in records] == ["v1", "v2"]
        assert client.requested_id_batches == ["v1,v2"]

    def test_boundary_empty_input_makes_zero_api_calls(self):
        client = _StubVideosClient([])
        provider = _make_provider(client)

        records = provider.fetch_video_metadata([], analyst_key="satiroglu")

        assert records == []
        assert client.requested_id_batches == []

    def test_boundary_51_ids_split_into_two_batches_of_50_and_1(self):
        video_ids = [f"v{i}" for i in range(51)]
        batch1_items = [_video_item(vid) for vid in video_ids[:50]]
        batch2_items = [_video_item(vid) for vid in video_ids[50:]]
        client = _StubVideosClient([
            {"items": batch1_items},
            {"items": batch2_items},
        ])
        provider = _make_provider(client)

        records = provider.fetch_video_metadata(video_ids, analyst_key="satiroglu")

        assert len(records) == 51
        assert [r.video_id for r in records] == video_ids
        # Batch boundary: first call carries exactly 50 ids, second call
        # carries exactly the 51st.
        assert client.requested_id_batches[0].count(",") == 49
        assert client.requested_id_batches[1] == "v50"

    def test_failure_path_api_error_propagates(self):
        client = _StubVideosRaisingClient(_FakeHttpError(404, "Not Found"))
        provider = _make_provider(client)

        with pytest.raises(ResourceNotFoundError):
            provider.fetch_video_metadata(["v1"], analyst_key="satiroglu")

    def test_analyst_key_is_stamped_onto_every_record(self):
        client = _StubVideosClient([{"items": [_video_item("v1")]}])
        provider = _make_provider(client)

        records = provider.fetch_video_metadata(["v1"], analyst_key="ozel_analist")

        assert records[0].analyst_key == "ozel_analist"


class TestToVideoRecordEligibilityRules:
    """Contract (exercised via fetch_video_metadata, its only caller):
    a video is ineligible for exactly one reason, decided by a fixed
    precedence -- shorts, then made_for_kids, then promo -- and eligible
    otherwise. This precedence, and the duration_sec==0 edge case below,
    are load-bearing behavioural details, not implementation trivia."""

    def _fetch_one(self, item: dict[str, Any], *, promo_keywords=None) -> Any:
        client = _StubVideosClient([{"items": [item]}])
        provider = YouTubePlatformProvider(
            api_key="fake-key-for-tests",
            promo_keywords=promo_keywords,
            client_factory=lambda _k: client,
        )
        return provider.fetch_video_metadata(["v1"], analyst_key="satiroglu")[0]

    def test_happy_path_ordinary_video_is_eligible(self):
        record = self._fetch_one(_video_item("v1", duration="PT10M"))
        assert record.eligible is True
        assert record.exclusion_reason == ""

    def test_boundary_duration_exactly_at_shorts_threshold_is_a_short(self):
        """shorts_max_duration_sec defaults to 60; the check is
        `0 < duration_sec <= shorts_max_duration_sec` -- exactly 60s is
        inclusive."""
        record = self._fetch_one(_video_item("v1", duration="PT60S"))
        assert record.eligible is False
        assert record.exclusion_reason == "shorts"

    def test_boundary_duration_one_second_over_threshold_is_not_a_short(self):
        record = self._fetch_one(_video_item("v1", duration="PT61S"))
        assert record.eligible is True
        assert record.exclusion_reason == ""

    def test_boundary_zero_duration_is_not_classified_as_a_short(self):
        """Documents a real, easy-to-miss edge case: a video with a
        missing/unparseable duration parses to duration_sec == 0, and
        the shorts check `0 < duration_sec <= cap` is FALSE at exactly
        0 -- so an unknown-duration video is NOT flagged as a short (it
        falls through to the made_for_kids/promo checks instead)."""
        record = self._fetch_one(_video_item("v1", duration=""))
        assert record.exclusion_reason != "shorts"

    def test_happy_path_made_for_kids_excludes_when_not_a_short(self):
        record = self._fetch_one(
            _video_item("v1", duration="PT10M", made_for_kids=True),
        )
        assert record.eligible is False
        assert record.exclusion_reason == "made_for_kids"

    def test_happy_path_promo_keyword_excludes_when_not_short_or_kids(self):
        record = self._fetch_one(
            _video_item("v1", duration="PT10M", title="Sponsorlu içerik: kod XYZ"),
            promo_keywords=["sponsorlu"],
        )
        assert record.eligible is False
        assert record.exclusion_reason == "promo"

    def test_boundary_shorts_takes_precedence_over_made_for_kids(self):
        """A video that is simultaneously a short AND made-for-kids must
        report 'shorts' -- the first branch in the elif chain wins."""
        record = self._fetch_one(
            _video_item("v1", duration="PT30S", made_for_kids=True),
        )
        assert record.exclusion_reason == "shorts"

    def test_boundary_made_for_kids_takes_precedence_over_promo(self):
        record = self._fetch_one(
            _video_item(
                "v1", duration="PT10M", made_for_kids=True,
                title="reklam ve tanitim",
            ),
            promo_keywords=["reklam"],
        )
        assert record.exclusion_reason == "made_for_kids"

    def test_boundary_missing_like_count_yields_none_not_zero(self):
        """likes has no `or 0` fallback in the source (unlike views and
        comment_count) -- a missing likeCount must surface as None, an
        explicit 'unknown', not be silently coerced to 0."""
        record = self._fetch_one(_video_item("v1", like_count=None))
        assert record.likes is None

    def test_boundary_present_like_count_is_coerced_to_int(self):
        record = self._fetch_one(_video_item("v1", like_count="42"))
        assert record.likes == 42

    def test_boundary_missing_view_and_comment_counts_default_to_zero(self):
        record = self._fetch_one(_video_item("v1", view_count=None, comment_count=None))
        assert record.views == 0
        assert record.comment_count == 0

    def test_failure_path_item_missing_required_id_raises(self):
        """A malformed API item missing the required `id` key must fail
        loudly (KeyError), not silently produce a corrupted/blank
        VideoRecord -- there is no `.get()` fallback for `item["id"]`
        by design."""
        malformed = _video_item("v1")
        del malformed["id"]
        client = _StubVideosClient([{"items": [malformed]}])
        provider = _make_provider(client)

        with pytest.raises(KeyError):
            provider.fetch_video_metadata(["v1"], analyst_key="satiroglu")


class TestContainsPromoKeywordMatching:
    """Contract (exercised via fetch_video_metadata + _to_video_record,
    the only caller of _contains_promo): case-insensitive substring
    match against title+description, gated entirely by
    promo_keywords -- empty/default keywords never match anything."""

    def _eligible_reason(self, *, title: str, description: str = "", promo_keywords) -> str:
        item = {
            "id": "v1",
            "snippet": {
                "title": title,
                "description": description,
                "publishedAt": "2025-06-01T12:00:00Z",
                "categoryId": "25",
            },
            "contentDetails": {"duration": "PT10M"},
            "statistics": {},
            "status": {"madeForKids": False},
        }
        client = _StubVideosClient([{"items": [item]}])
        provider = YouTubePlatformProvider(
            api_key="fake-key-for-tests",
            promo_keywords=promo_keywords,
            client_factory=lambda _k: client,
        )
        return provider.fetch_video_metadata(["v1"], analyst_key="satiroglu")[0].exclusion_reason

    def test_happy_path_no_keywords_configured_never_flags_promo(self):
        """Default construction (promo_keywords=None -> empty tuple):
        _contains_promo must short-circuit False regardless of content,
        not iterate an empty collection into an accidental match."""
        reason = self._eligible_reason(
            title="Bu bir reklam ve sponsorluk videosu",
            promo_keywords=None,
        )
        assert reason == ""

    def test_boundary_case_insensitive_substring_match_in_title(self):
        reason = self._eligible_reason(
            title="Bu SPONSORLU bir video",
            promo_keywords=["sponsorlu"],
        )
        assert reason == "promo"

    def test_boundary_match_in_description_not_just_title(self):
        reason = self._eligible_reason(
            title="Sıradan başlık",
            description="Bu video bir reklamdır.",
            promo_keywords=["reklam"],
        )
        assert reason == "promo"

    def test_boundary_keyword_absent_does_not_flag(self):
        reason = self._eligible_reason(
            title="Tamamen alakasız bir başlık",
            description="Alakasız açıklama.",
            promo_keywords=["sponsorlu"],
        )
        assert reason == ""

    def test_boundary_empty_string_keyword_never_matches(self):
        """`kw and kw in lower` guards against a configured empty-string
        keyword matching everything (an empty string is a substring of
        any string in Python)."""
        reason = self._eligible_reason(
            title="Herhangi bir başlık, herhangi bir içerik",
            promo_keywords=["", "gercekten_olmayan_kelime"],
        )
        assert reason == ""
