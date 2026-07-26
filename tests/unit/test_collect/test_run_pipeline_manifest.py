"""Tests for the run-manifest wiring inside
:func:`finfluencer.collect.main.run_pipeline` (Architecture v1.0 §10).

Uses the real, shipped-with-repo ``config/settings.yaml`` /
``config/analysts.yaml`` (matching ``test_config.py``'s own convention),
with every ``output.paths.*`` value the exercised code path touches
redirected into ``tmp_path`` via the platform's existing
``FINFLUENCER_SECTION__KEY`` environment-variable overlay
(:func:`finfluencer.core.config.load_settings`) — never the real repo's
``data/``, ``cache/``, or ``checkpoints/`` directories.

``stage="topic_sentiment"`` is used deliberately: it is the only stage
that touches neither a platform/language provider nor any ML model
(no network, no torch/transformers/bertopic), so these tests stay fast
and fully isolated while still exercising the real, unmodified
``run_pipeline`` function end to end.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from finfluencer.collect.main import run_pipeline
from finfluencer.core.config import load_settings
from finfluencer.utils.io import write_parquet

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"


def _load_cfg_with_tmp_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Real config, with every path this test path touches redirected
    into ``tmp_path`` so nothing is ever written to the real repo."""
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__DATA_RAW", str(tmp_path / "data" / "raw"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__DATA_PROCESSED", str(tmp_path / "data" / "processed"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__CHECKPOINTS", str(tmp_path / "checkpoints"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__CACHE", str(tmp_path / "cache"))
    return load_settings(_SETTINGS, _ANALYSTS)


def _topics_df() -> pd.DataFrame:
    return pd.DataFrame([
        dict(comment_id="c1", topic_id=0, topic_prob=0.9, topic_tier=None,
             configuration="pooled", topic_label="0_altin_gm_ons"),
        dict(comment_id="c2", topic_id=0, topic_prob=0.8, topic_tier=None,
             configuration="pooled", topic_label="0_altin_gm_ons"),
    ])


def _sentiment_df() -> pd.DataFrame:
    return pd.DataFrame([
        dict(comment_id="c1", sentiment_prob=0.9, sentiment_class="positive",
             sentiment_pseudo_neutral=False, sentiment_target=None, sentiment_market_directed=None),
        dict(comment_id="c2", sentiment_prob=0.1, sentiment_class="negative",
             sentiment_pseudo_neutral=False, sentiment_target=None, sentiment_market_directed=None),
    ])


def _comments_df() -> pd.DataFrame:
    return pd.DataFrame([
        dict(comment_id="c1", analyst_key="satiroglu"),
        dict(comment_id="c2", analyst_key="satiroglu"),
    ])


def _manifest_dir(cfg) -> Path:
    return Path(str(cfg.settings.output.paths.checkpoints)) / "run_manifests"


def _read_only_manifest(cfg) -> dict:
    files = list(_manifest_dir(cfg).glob("*.json"))
    assert len(files) == 1, f"expected exactly one manifest file, found {len(files)}"
    return json.loads(files[0].read_text(encoding="utf-8"))


class TestRunPipelineManifestFailure:
    """stage='topic_sentiment' with no topics.parquet present -> the
    pipeline's own, pre-existing FileNotFoundError guard clause fires."""

    def test_failed_manifest_written_and_exception_still_raised(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)

        with pytest.raises(FileNotFoundError, match="topics.parquet not found"):
            run_pipeline(cfg, stage="topic_sentiment")

        manifest = _read_only_manifest(cfg)
        assert manifest["status"] == "FAILED"
        assert manifest["error"]["type"] == "FileNotFoundError"
        assert "topics.parquet" in manifest["error"]["message"]
        assert manifest["stage"] == "topic_sentiment"

    def test_manifest_write_failure_does_not_mask_pipeline_exception(
        self, tmp_path, monkeypatch,
    ):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated manifest-system failure")

        monkeypatch.setattr("finfluencer.collect.main.write_provenance", _boom)

        # The ORIGINAL pipeline exception must still propagate unchanged,
        # never the manifest system's own RuntimeError.
        with pytest.raises(FileNotFoundError, match="topics.parquet not found"):
            run_pipeline(cfg, stage="topic_sentiment")

        # And no manifest file exists at all, since every write attempt failed.
        assert not _manifest_dir(cfg).exists() or not list(_manifest_dir(cfg).glob("*.json"))


class TestRunPipelineManifestSuccess:
    def test_success_manifest_written_with_checkpoints_and_run_id(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        data_raw = Path(str(cfg.settings.output.paths.data_raw))
        data_processed = Path(str(cfg.settings.output.paths.data_processed))
        write_parquet(_comments_df(), data_raw / "comments.parquet")
        write_parquet(_topics_df(), data_processed / "topics.parquet")
        write_parquet(_sentiment_df(), data_processed / "sentiment.parquet")

        results = run_pipeline(cfg, stage="topic_sentiment")

        assert "topic_sentiment" in results
        manifest = _read_only_manifest(cfg)
        assert manifest["status"] == "SUCCESS"
        assert manifest["stage"] == "topic_sentiment"
        assert manifest["extras"]["stages_run"] == ["topic_sentiment"]
        assert "run_id" in manifest and manifest["run_id"]
        assert manifest["config_hashes"]["settings_file_sha256"] == cfg.settings_sha256

    def test_dry_run_writes_no_manifest(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        result = run_pipeline(cfg, stage="topic_sentiment", dry_run=True)
        assert result == {}
        assert not _manifest_dir(cfg).exists()
