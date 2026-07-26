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


def _make_provider(client: Any = None) -> YouTubePlatformProvider:
    """Construct a provider with no real API key requirement and a stub
    client_factory that returns `client` (or a bare sentinel if the test
    doesn't need one, e.g. resolve_channel's legacy-URL short-circuit)."""
    return YouTubePlatformProvider(
        api_key="fake-key-for-tests",
        client_factory=lambda _api_key: client if client is not None else object(),
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
        provider = _make_provider()
        req = _RaisingRequest(_FakeHttpError(403, "commentsDisabled: The video has disabled comments."))
        with pytest.raises(ResourceNotFoundError):
            provider._execute(req)

    def test_403_rate_limited(self):
        provider = _make_provider()
        req = _RaisingRequest(_FakeHttpError(403, "User rate limit exceeded."))
        with pytest.raises(RateLimitError):
            provider._execute(req)

    def test_403_other_reason_is_generic_collection_error(self):
        provider = _make_provider()
        req = _RaisingRequest(_FakeHttpError(403, "accessNotConfigured: API not enabled."))
        with pytest.raises(CollectionError):
            provider._execute(req)

    def test_429_rate_limited(self):
        provider = _make_provider()
        req = _RaisingRequest(_FakeHttpError(429, "Too Many Requests"))
        with pytest.raises(RateLimitError):
            provider._execute(req)

    def test_404_resource_not_found(self):
        provider = _make_provider()
        req = _RaisingRequest(_FakeHttpError(404, "Not Found"))
        with pytest.raises(ResourceNotFoundError):
            provider._execute(req)

    def test_5xx_is_network_error(self):
        provider = _make_provider()
        req = _RaisingRequest(_FakeHttpError(503, "Service Unavailable"))
        with pytest.raises(NetworkError):
            provider._execute(req)

    def test_unknown_status_is_generic_collection_error(self):
        provider = _make_provider()
        # No `.resp` attribute at all -> status resolves to None.
        req = _RaisingRequest(RuntimeError("totally unexpected failure"))
        with pytest.raises(CollectionError):
            provider._execute(req)
