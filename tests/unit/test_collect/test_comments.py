"""Tests for finfluencer.collect.comments (ADR-P2-002 / R2).

Case 4 of R2's four required behavioural demonstrations lives here: one
invalid video (404) inside a batch must be logged and skipped, with the
remaining videos still collected -- collect_comments' loop, not the
provider, is what's under test. Cases 1-3 (comments enabled / disabled /
video deleted) are provider-level and live in
tests/unit/test_providers/test_youtube.py.

Before this fix, ``fetch_top_level_comments`` never raised
``ResourceNotFoundError`` in practice (it silently swallowed 404s as an
empty list), so ``collect_comments``'s loop -- which has no ``except``
clause around the provider call -- never needed one. This suite proves
the new ``except ResourceNotFoundError`` clause (mirroring
``collect/channels.py``'s already-established pattern) does its job:
one bad video must not abort collection for the rest of the batch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from finfluencer.collect.comments import collect_comments
from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.config import load_settings
from finfluencer.core.contracts import CommentRecord
from finfluencer.core.exceptions import ResourceNotFoundError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"


# ============================================================================
# Shared helpers
# ============================================================================


def _comment(video_id: str, comment_id: str, text: str = "yorum") -> CommentRecord:
    return CommentRecord(
        analyst_key="satiroglu",
        video_id=video_id,
        comment_id=comment_id,
        commenter_hash="a" * 16,
        posted_date="2025-06-15",
        text_raw=text,
        text_clean="",
        tokens=[],
        n_tokens=0,
        emojis=[],
        likes=0,
    )


class _StubProvider:
    """Duck-typed stand-in for PlatformProvider -- collect_comments only
    calls .fetch_top_level_comments(...), so that's all this implements.
    ``behavior`` maps video_id -> either a list[CommentRecord] to return,
    or an Exception instance to raise."""

    def __init__(self, behavior: dict[str, Any]) -> None:
        self._behavior = behavior
        self.calls: list[str] = []

    def fetch_top_level_comments(
        self, video_id: str, *, analyst_key: str, salt: str,
        window_start_iso: str, window_end_iso: str,
    ) -> list[CommentRecord]:
        self.calls.append(video_id)
        outcome = self._behavior[video_id]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _videos_df(video_ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame({
        "analyst_key": ["satiroglu"] * len(video_ids),
        "video_id": video_ids,
        "selected": [True] * len(video_ids),
    })


# ============================================================================
# Case 4: one invalid video inside a batch -> logged, skipped, rest continue
# ============================================================================


class TestOneInvalidVideoInBatchDoesNotAbortTheRest:
    def test_middle_video_404_skipped_others_still_collected(self, tmp_path):
        checkpoint = CheckpointManager(tmp_path / "checkpoints", tmp_path / "cache")
        cfg = load_settings(_SETTINGS, _ANALYSTS)

        provider = _StubProvider({
            "v1": [_comment("v1", "c1")],
            "v2": ResourceNotFoundError(
                "YouTube resource not found", status_code=404, video_id="v2",
            ),
            "v3": [_comment("v3", "c3")],
        })
        videos_df = _videos_df(["v1", "v2", "v3"])

        with structlog.testing.capture_logs() as captured:
            df = collect_comments(
                cfg.settings, videos_df, provider, checkpoint,
                output_path=tmp_path / "comments.parquet",
                salt="a" * 32,
            )

        # All three videos were attempted -- the loop did not abort after
        # v2's failure, unlike before this fix (no except clause existed).
        assert provider.calls == ["v1", "v2", "v3"]

        # v2 contributed no rows; v1 and v3 did.
        assert set(df["video_id"]) == {"v1", "v3"}
        assert len(df) == 2

        # The failure was logged, not silently dropped.
        error_events = [c for c in captured if c.get("log_level") == "error"]
        assert any(
            c.get("event") == "video_not_found" and c.get("video_id") == "v2"
            for c in error_events
        ), f"expected a video_not_found error log for v2, got: {error_events}"

    def test_all_videos_failing_yields_empty_but_does_not_raise(self, tmp_path):
        """Every video 404s -> collection completes with zero rows rather
        than raising on the first failure (the pre-fix behaviour would
        have propagated the exception from video 1 immediately)."""
        checkpoint = CheckpointManager(tmp_path / "checkpoints", tmp_path / "cache")
        cfg = load_settings(_SETTINGS, _ANALYSTS)

        provider = _StubProvider({
            "v1": ResourceNotFoundError("not found", status_code=404),
            "v2": ResourceNotFoundError("not found", status_code=404),
        })
        videos_df = _videos_df(["v1", "v2"])

        df = collect_comments(
            cfg.settings, videos_df, provider, checkpoint,
            output_path=tmp_path / "comments.parquet",
            salt="a" * 32,
        )

        assert provider.calls == ["v1", "v2"]
        assert len(df) == 0

    def test_non_resource_not_found_exceptions_still_propagate(self, tmp_path):
        """Constraint check: the new except clause must be narrow. A
        different CollectionError (e.g. quota exhaustion) must still
        abort the run -- that is correct, expected behaviour (quota
        exhaustion is non-recoverable within the day; retrying the next
        video would just fail again), and must not be silently caught
        by an overly broad handler."""
        from finfluencer.core.exceptions import QuotaExhaustedError

        checkpoint = CheckpointManager(tmp_path / "checkpoints", tmp_path / "cache")
        cfg = load_settings(_SETTINGS, _ANALYSTS)

        provider = _StubProvider({
            "v1": QuotaExhaustedError("daily quota exhausted"),
        })
        videos_df = _videos_df(["v1"])

        import pytest
        with pytest.raises(QuotaExhaustedError):
            collect_comments(
                cfg.settings, videos_df, provider, checkpoint,
                output_path=tmp_path / "comments.parquet",
                salt="a" * 32,
            )
