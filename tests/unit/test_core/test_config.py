"""Tests for :mod:`finfluencer.core.config`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from finfluencer.core.config import (
    _apply_env_overlay,
    _coerce_env_value,
    is_placeholder_revision,
    load_settings,
)
from finfluencer.core.contracts import ReplicationStage
from finfluencer.core.exceptions import (
    ConfigFileNotFoundError,
    ConfigSchemaMismatchError,
    ConfigValidationError,
    UnpinnedRevisionError,
)


# Anchor for the shipped-with-repo config files.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"


def _load_real_settings_dict() -> dict:
    return yaml.safe_load(_SETTINGS.read_text(encoding="utf-8"))


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

    def test_unknown_top_level_key_raises_schema_mismatch(self, tmp_path):
        # An otherwise-fully-valid document plus one unrecognized key
        # produces ONLY extra_forbidden errors, which load_settings()
        # distinguishes from general validation failures.
        raw = _load_real_settings_dict()
        raw["not_a_real_top_level_key"] = "unexpected_value"
        bad = tmp_path / "settings.yaml"
        bad.write_text(yaml.safe_dump(raw), encoding="utf-8")
        with pytest.raises(ConfigSchemaMismatchError):
            load_settings(bad, _ANALYSTS)

    def test_empty_roster_raises_config_validation_error(self, tmp_path):
        bad = tmp_path / "analysts.yaml"
        bad.write_text("analysts: []\n", encoding="utf-8")
        with pytest.raises(ConfigValidationError):
            load_settings(_SETTINGS, bad)


class TestIsPlaceholderRevision:
    def test_matches_placeholder_pattern(self):
        assert is_placeholder_revision("REPLACE_WITH_HF_COMMIT_SHA") is True

    def test_real_sha_is_not_a_placeholder(self):
        assert is_placeholder_revision("a" * 40) is False


class TestCoerceEnvValue:
    def test_true_and_false(self):
        assert _coerce_env_value("true") is True
        assert _coerce_env_value("FALSE") is False

    def test_integer(self):
        assert _coerce_env_value("42") == 42
        assert _coerce_env_value("-7") == -7

    def test_float(self):
        assert _coerce_env_value("3.14") == pytest.approx(3.14)

    def test_non_numeric_string_falls_through_unchanged(self):
        assert _coerce_env_value("hello") == "hello"


class TestApplyEnvOverlay:
    def test_path_through_existing_scalar_leaf_breaks_early(self, monkeypatch):
        # "study.name" is a string leaf in real settings; a deeper env-var
        # path trying to descend past it must break rather than crash or
        # silently overwrite the scalar with a dict.
        data = {"study": {"name": "example_string"}}
        monkeypatch.setenv("FINFLUENCER_STUDY__NAME__EXTRA__DEEPER", "ignored")

        result = _apply_env_overlay(data)

        assert result["study"]["name"] == "example_string"

    def test_env_overlay_false_skips_overlay_entirely(self, monkeypatch):
        monkeypatch.setenv("FINFLUENCER_STUDY__NAME", "should_be_ignored")
        cfg = load_settings(_SETTINGS, _ANALYSTS, env_overlay=False)
        assert cfg.settings.study.name == "finfluencer_tr_2025"


class TestEnforceStagePolicy:
    def _write_settings(self, tmp_path, raw: dict) -> Path:
        path = tmp_path / "settings.yaml"
        path.write_text(yaml.safe_dump(raw), encoding="utf-8")
        return path

    def test_publication_stage_with_placeholder_revisions_raises(self, tmp_path):
        # Real settings.yaml ships with REPLACE_WITH_HF_COMMIT_SHA
        # placeholders and stage="exploratory"; bumping only the stage
        # must trigger the publication-stage unpinned-revision gate.
        raw = _load_real_settings_dict()
        raw["replication"]["stage"] = "publication"
        settings_path = self._write_settings(tmp_path, raw)

        with pytest.raises(UnpinnedRevisionError):
            load_settings(settings_path, _ANALYSTS)

    def test_publication_stage_with_pinned_revisions_does_not_raise(self, tmp_path):
        raw = _load_real_settings_dict()
        raw["replication"]["stage"] = "publication"
        raw["sentiment"]["primary_model"]["revision"] = "a" * 40
        raw["sentiment"]["target_of_affect"]["base_revision"] = "b" * 40
        raw["topics"]["embedding_model"]["revision"] = "c" * 40
        settings_path = self._write_settings(tmp_path, raw)

        cfg = load_settings(settings_path, _ANALYSTS)

        assert cfg.settings.replication.stage == ReplicationStage.publication


class TestSaltValidation:
    def test_validate_secrets_false_skips_salt_check_entirely(self, monkeypatch):
        monkeypatch.delenv("ANON_SALT", raising=False)
        cfg = load_settings(_SETTINGS, _ANALYSTS, validate_secrets=False)
        assert cfg is not None

    def test_anon_salt_set_non_strict_for_exploratory_stage(self, monkeypatch, strong_salt):
        # Real settings.yaml stage is "exploratory" -> non-strict validation.
        monkeypatch.setenv("ANON_SALT", strong_salt)
        cfg = load_settings(_SETTINGS, _ANALYSTS)
        assert cfg is not None

    def test_anon_salt_set_strict_for_submission_stage(self, tmp_path, monkeypatch, strong_salt):
        raw = _load_real_settings_dict()
        raw["replication"]["stage"] = "submission"
        settings_path = tmp_path / "settings.yaml"
        settings_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
        monkeypatch.setenv("ANON_SALT", strong_salt)

        cfg = load_settings(settings_path, _ANALYSTS)

        assert cfg.settings.replication.stage == ReplicationStage.submission
