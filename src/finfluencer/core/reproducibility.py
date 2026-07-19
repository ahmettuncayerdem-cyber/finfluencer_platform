"""
finfluencer.core.reproducibility
=================================

Seed derivation, environment snapshotting, and provenance records.

Every pipeline run emits a ``provenance.json`` capturing exactly what
would need to hold for a re-run to be reproducible: git commit, config
hashes, package versions, Python version, and random seeds.

Seed derivation
---------------
The single ``root_seed`` from ``settings.yaml`` is expanded into
per-stage seeds via ``derive_seed(root_seed, stage_name)``. The mapping
is a deterministic HKDF-style hash: same root → same per-stage seed,
across runs and platforms.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import secrets
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.config import LoadedConfig
from finfluencer.core.exceptions import (
    DirtyWorkingTreeError,
    EnvironmentMismatchError,
    ReproducibilityError,
)
from finfluencer.utils.hashing import hash_config_dict, hash_string
from finfluencer.utils.io import write_json
from finfluencer.utils.time import now_utc


# =============================================================================
# Seed derivation
# =============================================================================


#: Maximum seed value passed to numpy/torch/random. Their APIs accept
#: uint32-range integers; larger values are safe but not portable.
_MAX_SEED: int = 2**31 - 1


def derive_seed(root_seed: int, stage_name: str) -> int:
    """Derive a deterministic per-stage seed from ``root_seed``.

    Deterministic across runs and platforms; the same ``(root_seed,
    stage_name)`` pair always yields the same integer.
    """
    if root_seed < 0:
        raise ValueError(f"derive_seed: root_seed must be >= 0, got {root_seed}")
    material = f"{root_seed}::{stage_name}".encode("utf-8")
    digest = hashlib.sha256(material).digest()
    # Take the first 4 bytes as a big-endian unsigned int, mask to uint31 range
    # so it is safe as a numpy/torch/random seed.
    return int.from_bytes(digest[:4], byteorder="big") & _MAX_SEED


# =============================================================================
# Environment snapshot
# =============================================================================


#: Packages whose exact version is captured in provenance. Not exhaustive;
#: only those whose behaviour materially affects analytical outputs.
_PROVENANCE_PACKAGES: tuple[str, ...] = (
    "finfluencer-platform",
    "pydantic",
    "pydantic-settings",
    "structlog",
    "numpy",
    "pandas",
    "pyarrow",
    "transformers",
    "sentence-transformers",
    "bertopic",
    "torch",
    "scipy",
    "statsmodels",
    "scikit-learn",
    "matplotlib",
    "langdetect",
)


def _get_package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def capture_environment() -> dict[str, Any]:
    """Snapshot the Python and package environment."""
    return {
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": {
            name: _get_package_version(name) for name in _PROVENANCE_PACKAGES
        },
    }


def verify_environment(pinned: dict[str, Any], *, strict: bool = True) -> None:
    """Compare the current environment against a pinned snapshot.

    Raises :class:`EnvironmentMismatchError` on mismatch when
    ``strict=True``. In non-strict mode, package-version mismatches
    are tolerated but Python-version mismatches still raise.
    """
    current = capture_environment()
    diffs: dict[str, tuple[Any, Any]] = {}

    if current["python_version"] != pinned.get("python_version"):
        diffs["python_version"] = (pinned.get("python_version"), current["python_version"])

    for pkg, pinned_ver in pinned.get("packages", {}).items():
        cur_ver = current["packages"].get(pkg)
        if cur_ver != pinned_ver:
            diffs[f"packages.{pkg}"] = (pinned_ver, cur_ver)

    if diffs and (strict or "python_version" in diffs):
        raise EnvironmentMismatchError(
            f"Environment differs from pinned snapshot: {list(diffs)}",
            differences=diffs,
        )


# =============================================================================
# Git state
# =============================================================================


def get_git_state(repo_root: Path | None = None) -> dict[str, Any]:
    """Return git commit hash and dirty flag for the working tree.

    Returns ``{"available": False}`` if not in a git repo or GitPython
    is missing. Never raises.
    """
    try:
        import git  # type: ignore[import-not-found]
    except ImportError:
        return {"available": False, "reason": "gitpython_not_installed"}

    try:
        repo = git.Repo(repo_root or ".", search_parent_directories=True)
        return {
            "available": True,
            "commit": repo.head.commit.hexsha,
            "short_commit": repo.head.commit.hexsha[:12],
            "branch": repo.active_branch.name if not repo.head.is_detached else None,
            "dirty": repo.is_dirty(untracked_files=False),
            "untracked": bool(repo.untracked_files),
        }
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": type(exc).__name__}


def enforce_clean_tree(git_state: dict[str, Any]) -> None:
    """Raise :class:`DirtyWorkingTreeError` if working tree is dirty.

    Publication-stage runs call this to guarantee that the code state
    which produced the outputs is exactly what has been committed.
    """
    if not git_state.get("available"):
        raise DirtyWorkingTreeError(
            "Publication-stage run requires git availability",
            reason=git_state.get("reason", "unknown"),
        )
    if git_state.get("dirty"):
        raise DirtyWorkingTreeError(
            "Publication-stage run requires a clean git working tree",
            commit=git_state.get("short_commit"),
        )


# =============================================================================
# Run manifest — identity and lifecycle status
# =============================================================================


class RunStatus(str, Enum):
    """Lifecycle status of one pipeline run's manifest.

    A manifest is written once when a run starts (``running``) and then
    updated *in place*, by ``run_id`` — never as a new file per
    transition — to ``success`` or ``failed`` when the run ends. A
    failed run is a first-class, valid outcome: callers must still
    write a manifest for it (Architecture v1.0 §10), not skip it.
    """

    running = "RUNNING"
    success = "SUCCESS"
    failed = "FAILED"


def generate_run_id() -> str:
    """Generate a human-readable, sortable, filename-safe run identifier.

    Format: ``<compact UTC timestamp>_<6 hex char suffix>``, e.g.
    ``20260718T192541Z_9f3a2b``. No colons, so it is safe as a path
    component on Windows as well as POSIX (this project already has to
    care about that — see the torch/pyarrow DLL-order note in
    :mod:`finfluencer.collect.main`). The timestamp alone is not
    guaranteed unique (two runs within the same second); the random
    suffix is what guarantees it in practice for this platform's
    current single-process usage pattern — a full collision-resistant
    scheme is not warranted at this scale.
    """
    ts = now_utc().strftime("%Y%m%dT%H%M%SZ")
    suffix = secrets.token_hex(3)
    return f"{ts}_{suffix}"


# =============================================================================
# Provenance record
# =============================================================================


def build_provenance(
    config: LoadedConfig,
    *,
    stage: str = "run",
    run_id: str | None = None,
    status: RunStatus = RunStatus.success,
    checkpoint: CheckpointManager | None = None,
    error: dict[str, str] | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the provenance dictionary for a pipeline run.

    Parameters
    ----------
    config
        Result of :func:`finfluencer.core.config.load_settings`.
    stage
        Name of the pipeline stage this provenance covers.
    run_id
        Stable identifier for this execution. Auto-generated via
        :func:`generate_run_id` if omitted. Passing the *same* run_id
        across multiple calls (e.g. ``RUNNING`` at start, then
        ``SUCCESS``/``FAILED`` at end) is how a caller updates one
        manifest file in place across a run's lifecycle rather than
        creating a new file per transition — see
        :func:`finfluencer.collect.main.run_pipeline`.
    status
        Lifecycle status of this manifest snapshot. Defaults to
        :attr:`RunStatus.success` for backward compatibility with the
        original single-shot call shape; real pipeline callers pass
        this explicitly at each lifecycle transition.
    checkpoint
        If given, folds every currently-on-disk Tier-2 stage marker
        (:meth:`finfluencer.core.checkpoint.CheckpointManager.all_markers`)
        into the manifest under a new ``"checkpoints"`` key, stitching
        per-stage ``config_slice_sha256`` values into one run-level
        record (Architecture v1.0 §10). Omitted entirely — no
        ``"checkpoints"`` key at all — if not given, matching this
        function's original behavior exactly.
    error
        For ``status=RunStatus.failed``: ``{"type": ..., "message":
        ...}`` describing the exception that ended the run. Ignored for
        any other status.
    extras
        Additional key/value pairs to embed (e.g. run duration,
        ``stages_run``).
    """
    settings_dict = config.settings.model_dump(mode="json")
    record: dict[str, Any] = {
        "run_id": run_id or generate_run_id(),
        "status": status.value,
        "timestamp_utc": now_utc().isoformat(),
        "stage": stage,
        "study": {
            "name": config.settings.study.name,
            "version": config.settings.study.version,
            "root_seed": config.settings.study.root_seed,
        },
        "config_hashes": {
            "settings_file_sha256": config.settings_sha256,
            "analysts_file_sha256": config.analysts_sha256,
            "settings_content_sha256": hash_config_dict(settings_dict),
        },
        "environment": capture_environment(),
        "git": get_git_state(),
        "extras": extras or {},
    }
    if checkpoint is not None:
        record["checkpoints"] = checkpoint.all_markers()
    if status == RunStatus.failed and error is not None:
        record["error"] = error
    return record


def write_provenance(provenance: dict[str, Any], path: Path | str) -> None:
    """Write a provenance record atomically to a JSON file."""
    write_json(provenance, path)


def enforce_publication_reproducibility(
    config: LoadedConfig,
    *,
    provenance: dict[str, Any],
) -> None:
    """Enforce all publication-stage reproducibility constraints.

    Called from CLI at the start of a ``stage: publication`` run.
    """
    from finfluencer.core.contracts import ReplicationStage

    if config.settings.replication.stage != ReplicationStage.publication:
        return
    if not config.settings.ethics.strict_reproducibility:
        return
    enforce_clean_tree(provenance["git"])
    if not provenance["environment"]["packages"].get("finfluencer-platform"):
        raise ReproducibilityError(
            "finfluencer-platform must be installed as a package "
            "(not just imported from src) for publication runs",
        )


__all__ = [
    "derive_seed",
    "capture_environment",
    "verify_environment",
    "get_git_state",
    "enforce_clean_tree",
    "RunStatus",
    "generate_run_id",
    "build_provenance",
    "write_provenance",
    "enforce_publication_reproducibility",
]
