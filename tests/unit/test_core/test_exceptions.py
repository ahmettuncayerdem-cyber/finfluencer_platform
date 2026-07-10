"""Tests for :mod:`finfluencer.core.exceptions`."""

from __future__ import annotations

from finfluencer.core.exceptions import (
    CollectionError,
    ConfigValidationError,
    FinfluencerError,
    QuotaExhaustedError,
    RateLimitError,
)


class TestFinfluencerError:
    def test_bare_message(self):
        exc = FinfluencerError("failed")
        assert exc.message == "failed"
        assert exc.context == {}
        assert str(exc) == "failed"

    def test_message_and_context(self):
        exc = FinfluencerError("failed", stage="collection", used=42)
        assert exc.context == {"stage": "collection", "used": 42}
        # __str__ contains structured fields
        s = str(exc)
        assert "stage='collection'" in s
        assert "used=42" in s

    def test_repr_roundtrip_syntax(self):
        exc = FinfluencerError("x", a=1)
        r = repr(exc)
        assert r.startswith("FinfluencerError(")


class TestHierarchy:
    def test_root_inheritance(self):
        assert issubclass(CollectionError, FinfluencerError)
        assert issubclass(QuotaExhaustedError, CollectionError)
        assert issubclass(RateLimitError, CollectionError)
        assert issubclass(ConfigValidationError, FinfluencerError)

    def test_recoverable_vs_nonrecoverable_are_siblings(self):
        # Retry decorator dispatches on class identity — these must not
        # inherit from each other or the retry logic breaks.
        assert not issubclass(RateLimitError, QuotaExhaustedError)
        assert not issubclass(QuotaExhaustedError, RateLimitError)

    def test_catch_by_category(self):
        try:
            raise QuotaExhaustedError("x", quota_used=100)
        except CollectionError as exc:
            # Caught by the category base — the intended pattern.
            assert exc.context["quota_used"] == 100
