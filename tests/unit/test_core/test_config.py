"""Tests for :mod:`finfluencer.core.config`."""

from __future__ import annotations

from pathlib import Path

import pytest
from finfluencer.core.config import load_settings
from finfluencer.core.exceptions import (
    ConfigFileNotFoundError,
    ConfigValidationError,
)


# Anchor for the shipped-with-repo config files.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"


class TestLoadRealConfig:
    def test_full_load(self):
        cfg = load_settings(_SETTINGS, _ANALYSTS)
        assert cfg.settings.study.name == "finfluencer_tr_2025"
        assert cfg.settings.study.root_seed == 42
        assert len(cfg.roster.analysts) == 4

    def test_pilot_analyst_present(self):
        cfg = load_settings(_SETTINGS, _ANALYSTS)
        pilots = [a for a in cfg.roster.analysts if a.pilot]
        assert len(pilots) == 1
        assert pilots[0].key == "satiroglu"

    def test_content_hashes_populated(self):
        cfg = load_settings(_SETTINGS, _ANALYSTS)
        assert len(cfg.settings_sha256) == 64
        assert len(cfg.analysts_sha256) == 64


class TestLoadErrors:
    def test_missing_settings_file(self, tmp_path):
        with pytest.raises(ConfigFileNotFoundError):
            load_settings(tmp_path / "missing.yaml", _ANALYSTS)

    def test_invalid_yaml(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("study:\n  name: [unclosed")
        with pytest.raises(ConfigValidationError):
            load_settings(bad, _ANALYSTS)

    def test_schema_violation(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        # Missing required 'study' section entirely.
        bad.write_text("providers:\n  language: turkish\n  platform: youtube")
        with pytest.raises(ConfigValidationError):
            load_settings(bad, _ANALYSTS)
