"""Tests for :mod:`finfluencer.core.reproducibility`."""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path

import pytest
from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.config import load_settings
from finfluencer.core.contracts import ReplicationStage
from finfluencer.core.exceptions import (
    DirtyWorkingTreeError,
    EnvironmentMismatchError,
    ReproducibilityError,
)
from finfluencer.core.reproducibility import (
    RunStatus,
    build_provenance,
    capture_environment,
    derive_seed,
    enforce_clean_tree,
    enforce_publication_reproducibility,
    generate_run_id,
    get_git_state,
    verify_environment,
)

# Anchor for the shipped-with-repo config files, matching test_config.py's
# own convention (real config, not a hand-built fixture).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"

_RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z_[0-9a-f]{6}$")


class TestDeriveSeed:
    def test_deterministic(self):
        assert derive_seed(42, "sentiment") == derive_seed(42, "sentiment")

    def test_stage_variance(self):
        assert derive_seed(42, "sentiment") != derive_seed(42, "topics")

    def test_root_variance(self):
        assert derive_seed(42, "sentiment") != derive_seed(43, "sentiment")

    def test_in_uint31_range(self):
        s = derive_seed(42, "sentiment")
        assert 0 <= s <= 2**31 - 1

    def test_negative_root_rejected(self):
        with pytest.raises(ValueError):
            derive_seed(-1, "sentiment")


class TestCaptureEnvironment:
    def test_has_python_and_packages(self):
        env = capture_environment()
        assert "python_version" in env
        assert "packages" in env
        # Core packages must be listed (they are installed as dependencies)
        assert "pydantic" in env["packages"]


def test_git_state_always_returns_dict():
    # In or out of a git repo, the function must not raise.
    st = get_git_state()
    assert "available" in st


class TestGenerateRunId:
    def test_matches_expected_format(self):
        assert _RUN_ID_RE.match(generate_run_id())

    def test_no_colons(self):
        # Must be a safe path component on Windows as well as POSIX.
        assert ":" not in generate_run_id()

    def test_unique_across_calls(self):
        ids = {generate_run_id() for _ in range(20)}
        assert len(ids) == 20


class TestBuildProvenanceRunManifest:
    def _cfg(self):
        return load_settings(_SETTINGS, _ANALYSTS)

    def test_run_id_auto_generated_when_omitted(self):
        prov = build_provenance(self._cfg())
        assert _RUN_ID_RE.match(prov["run_id"])

    def test_run_id_passed_through_unchanged(self):
        prov = build_provenance(self._cfg(), run_id="fixed_id_123")
        assert prov["run_id"] == "fixed_id_123"

    def test_default_status_is_success(self):
        prov = build_provenance(self._cfg())
        assert prov["status"] == "SUCCESS"

    def test_running_status(self):
        prov = build_provenance(self._cfg(), status=RunStatus.running)
        assert prov["status"] == "RUNNING"

    def test_no_checkpoints_key_when_checkpoint_omitted(self):
        prov = build_provenance(self._cfg())
        assert "checkpoints" not in prov

    def test_checkpoints_folded_in_when_given(self, tmp_checkpoint_root, tmp_cache_root):
        cm = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        cm.mark_done("channels", {"k": 1})
        prov = build_provenance(self._cfg(), checkpoint=cm)
        assert "checkpoints" in prov
        assert "channels" in prov["checkpoints"]
        assert "config_slice_sha256" in prov["checkpoints"]["channels"]

    def test_error_included_only_on_failed_status(self):
        err = {"type": "FileNotFoundError", "message": "comments.parquet missing"}
        failed = build_provenance(self._cfg(), status=RunStatus.failed, error=err)
        assert failed["error"] == err

        success = build_provenance(self._cfg(), status=RunStatus.success, error=err)
        assert "error" not in success

    def test_same_run_id_across_lifecycle_calls(self):
        cfg = self._cfg()
        run_id = generate_run_id()
        running = build_provenance(cfg, run_id=run_id, status=RunStatus.running)
        success = build_provenance(cfg, run_id=run_id, status=RunStatus.success)
        assert running["run_id"] == success["run_id"] == run_id
        assert running["status"] != success["status"]


class TestVerifyEnvironment:
    def test_matching_snapshot_does_not_raise(self):
        pinned = capture_environment()
        verify_environment(pinned, strict=True)

    def test_python_version_mismatch_raises_in_strict_mode(self):
        pinned = capture_environment()
        pinned["python_version"] = "0.0.0"
        with pytest.raises(EnvironmentMismatchError):
            verify_environment(pinned, strict=True)

    def test_python_version_mismatch_raises_even_in_non_strict_mode(self):
        # Python-version mismatches are never tolerated, regardless of strict.
        pinned = capture_environment()
        pinned["python_version"] = "0.0.0"
        with pytest.raises(EnvironmentMismatchError):
            verify_environment(pinned, strict=False)

    def test_package_mismatch_raises_in_strict_mode(self):
        pinned = capture_environment()
        pinned["packages"] = dict(pinned["packages"])
        pinned["packages"]["pydantic"] = "0.0.0"
        with pytest.raises(EnvironmentMismatchError):
            verify_environment(pinned, strict=True)

    def test_package_mismatch_tolerated_in_non_strict_mode(self):
        pinned = capture_environment()
        pinned["packages"] = dict(pinned["packages"])
        pinned["packages"]["pydantic"] = "0.0.0"
        verify_environment(pinned, strict=False)  # must not raise


# =============================================================================
# get_git_state() success/exception path — GitPython is NOT installed in
# this environment (verified: `import git` raises ModuleNotFoundError), so
# these branches are exercised by injecting a fake `git` module into
# sys.modules for the duration of each test. This is a standard technique
# for testing an optional-dependency code path without requiring the
# dependency to actually be installed; the code under test is otherwise
# fully portable.
# =============================================================================


class _FakeCommit:
    def __init__(self, hexsha: str) -> None:
        self.hexsha = hexsha


class _FakeActiveBranch:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeHead:
    def __init__(self, commit: _FakeCommit, is_detached: bool) -> None:
        self.commit = commit
        self.is_detached = is_detached


class _FakeRepo:
    """Stand-in for ``git.Repo``."""

    def __init__(
        self,
        *args,
        commit_hexsha: str = "a" * 40,
        branch_name: str = "main",
        detached: bool = False,
        dirty: bool = False,
        untracked: bool = False,
        **kwargs,
    ) -> None:
        self.head = _FakeHead(_FakeCommit(commit_hexsha), detached)
        self._branch_name = branch_name
        self._dirty = dirty
        self.untracked_files = ["new_file.py"] if untracked else []

    @property
    def active_branch(self) -> _FakeActiveBranch:
        return _FakeActiveBranch(self._branch_name)

    def is_dirty(self, untracked_files: bool = False) -> bool:
        return self._dirty


def _install_fake_git(monkeypatch, factory) -> None:
    """Inject a fake ``git`` module so ``import git`` succeeds inside
    get_git_state(); ``factory`` is called as ``git.Repo(...)``."""
    fake_module = types.ModuleType("git")
    fake_module.Repo = factory
    monkeypatch.setitem(sys.modules, "git", fake_module)


class TestGetGitStateSuccessPath:
    def test_clean_repo(self, monkeypatch):
        _install_fake_git(
            monkeypatch,
            lambda *a, **kw: _FakeRepo(commit_hexsha="deadbeef" * 5, branch_name="main"),
        )
        st = get_git_state()
        assert st["available"] is True
        assert st["commit"] == "deadbeef" * 5
        assert st["short_commit"] == ("deadbeef" * 5)[:12]
        assert st["branch"] == "main"
        assert st["dirty"] is False
        assert st["untracked"] is False

    def test_dirty_repo_with_untracked_files(self, monkeypatch):
        _install_fake_git(
            monkeypatch, lambda *a, **kw: _FakeRepo(dirty=True, untracked=True),
        )
        st = get_git_state()
        assert st["dirty"] is True
        assert st["untracked"] is True

    def test_detached_head_reports_branch_none(self, monkeypatch):
        _install_fake_git(monkeypatch, lambda *a, **kw: _FakeRepo(detached=True))
        st = get_git_state()
        assert st["available"] is True
        assert st["branch"] is None

    def test_exception_during_repo_construction_returns_unavailable(self, monkeypatch):
        def _raise(*a, **kw):
            raise ValueError("not a git repository")

        _install_fake_git(monkeypatch, _raise)
        st = get_git_state()
        assert st["available"] is False
        assert st["reason"] == "ValueError"


class TestEnforceCleanTree:
    def test_unavailable_git_raises(self):
        with pytest.raises(DirtyWorkingTreeError):
            enforce_clean_tree({"available": False, "reason": "gitpython_not_installed"})

    def test_dirty_tree_raises(self):
        with pytest.raises(DirtyWorkingTreeError):
            enforce_clean_tree({"available": True, "dirty": True, "short_commit": "abc123"})

    def test_clean_available_tree_does_not_raise(self):
        enforce_clean_tree({"available": True, "dirty": False})


class TestEnforcePublicationReproducibility:
    def _cfg(self):
        return load_settings(_SETTINGS, _ANALYSTS)

    def test_non_publication_stage_is_noop(self):
        cfg = self._cfg()
        cfg.settings.replication.stage = ReplicationStage.exploratory
        cfg.settings.ethics.strict_reproducibility = True
        # Provenance deliberately invalid (dirty, no package) - must not be
        # inspected at all since the stage check short-circuits first.
        provenance = {
            "git": {"available": True, "dirty": True},
            "environment": {"packages": {}},
        }
        enforce_publication_reproducibility(cfg, provenance=provenance)

    def test_publication_stage_but_not_strict_is_noop(self):
        cfg = self._cfg()
        cfg.settings.replication.stage = ReplicationStage.publication
        cfg.settings.ethics.strict_reproducibility = False
        provenance = {
            "git": {"available": True, "dirty": True},
            "environment": {"packages": {}},
        }
        enforce_publication_reproducibility(cfg, provenance=provenance)

    def test_publication_strict_dirty_tree_raises(self):
        cfg = self._cfg()
        cfg.settings.replication.stage = ReplicationStage.publication
        cfg.settings.ethics.strict_reproducibility = True
        provenance = {
            "git": {"available": True, "dirty": True, "short_commit": "abc123"},
            "environment": {"packages": {"finfluencer-platform": "1.0.0"}},
        }
        with pytest.raises(DirtyWorkingTreeError):
            enforce_publication_reproducibility(cfg, provenance=provenance)

    def test_publication_strict_clean_missing_package_raises(self):
        cfg = self._cfg()
        cfg.settings.replication.stage = ReplicationStage.publication
        cfg.settings.ethics.strict_reproducibility = True
        provenance = {
            "git": {"available": True, "dirty": False},
            "environment": {"packages": {}},
        }
        with pytest.raises(ReproducibilityError):
            enforce_publication_reproducibility(cfg, provenance=provenance)

    def test_publication_strict_clean_with_package_succeeds(self):
        cfg = self._cfg()
        cfg.settings.replication.stage = ReplicationStage.publication
        cfg.settings.ethics.strict_reproducibility = True
        provenance = {
            "git": {"available": True, "dirty": False},
            "environment": {"packages": {"finfluencer-platform": "1.0.0"}},
        }
        enforce_publication_reproducibility(cfg, provenance=provenance)
