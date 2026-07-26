"""Tests for :mod:`finfluencer.core.checkpoint`."""

from __future__ import annotations

import pytest
from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.exceptions import (
    CheckpointCorruptedError,
    CheckpointInvalidatedError,
)


class TestShouldRun:
    def test_first_run_returns_true(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        assert cm.should_run("stage", {"k": 1}) is True

    def test_after_mark_done_returns_false(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        cfg = {"k": 1}
        assert cm.should_run("stage", cfg) is True
        cm.mark_done("stage", cfg)
        assert cm.should_run("stage", cfg) is False

    def test_config_change_reruns(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        cm.mark_done("stage", {"k": 1})
        # Changed config → should_run True again
        assert cm.should_run("stage", {"k": 2}) is True

    def test_corrupted_marker_raises(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        # Write garbage instead of a valid JSON marker.
        marker = cm._marker_path("stage")
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("not-json-{{{")
        with pytest.raises(CheckpointCorruptedError):
            cm.should_run("stage", {"k": 1})


class TestRecords:
    def test_append_and_completed_ids(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        for i in range(3):
            cm.append_record("stage", {"id": f"v{i}"})
        assert cm.completed_ids("stage") == {"v0", "v1", "v2"}

    def test_read_records_iterates_all(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        for i in range(3):
            cm.append_record("stage", {"id": f"v{i}", "n": i})
        recs = list(cm.read_records("stage"))
        assert len(recs) == 3


class TestCache:
    def test_cache_path_is_sharded(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        p = cm.cache_path("emb", "abcd1234", ".npy")
        # Assert via Path.parts so the check is platform-independent
        # (Windows uses \, POSIX uses /).
        assert p.parts[-2:] == ("ab", "abcd1234.npy")
        assert p.parent.exists()

    def test_cache_has(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        p = cm.cache_path("emb", "abcd1234", ".npy")
        assert not cm.cache_has("emb", "abcd1234", ".npy")
        p.write_bytes(b"x")
        assert cm.cache_has("emb", "abcd1234", ".npy")

    def test_empty_hash_rejected(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        with pytest.raises(ValueError):
            cm.cache_path("emb", "")


class TestAllMarkers:
    def test_empty_when_no_markers(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        assert cm.all_markers() == {}

    def test_returns_all_stage_payloads(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        cm.mark_done("channels", {"k": 1})
        cm.mark_done("videos", {"k": 2}, extras={"n_rows": 10})
        markers = cm.all_markers()
        assert set(markers) == {"channels", "videos"}
        assert markers["videos"]["extras"] == {"n_rows": 10}
        assert "config_slice_sha256" in markers["channels"]

    def test_corrupted_marker_is_skipped_not_raised(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        cm.mark_done("channels", {"k": 1})
        bad = cm._marker_path("videos")
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("not-json-{{{")
        # Must not raise, and must still return the good marker.
        markers = cm.all_markers()
        assert set(markers) == {"channels"}


class TestRequireDone:
    def test_raises_when_not_done(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        with pytest.raises(CheckpointInvalidatedError):
            cm.require_done("upstream", {"k": 1})

    def test_ok_when_done(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        cm.mark_done("upstream", {"k": 1})
        cm.require_done("upstream", {"k": 1})  # must not raise
