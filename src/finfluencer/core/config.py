"""
finfluencer.core.config
========================

Load, validate, and expose the platform's configuration.

The single entry point :func:`load_settings` returns a fully validated
:class:`Settings` object plus the analyst roster. Configuration
precedence (highest first):

    1. CLI ``--override key=value`` (applied by ``finfluencer.cli``)
    2. Environment variables ``FINFLUENCER_SECTION__KEY=value``
    3. YAML file contents
    4. Pydantic defaults

Placeholder detection
---------------------
When the study is in ``publication`` stage, unpinned model revisions
(``"REPLACE_WITH_HF_COMMIT_SHA"`` etc.) raise :class:`UnpinnedRevisionError`.
Earlier stages accept placeholders.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from finfluencer.core.contracts import (
    AnalystRoster,
    ReplicationStage,
    Settings,
)
from finfluencer.core.exceptions import (
    ConfigFileNotFoundError,
    ConfigSchemaMismatchError,
    ConfigValidationError,
    UnpinnedRevisionError,
)
from finfluencer.utils.hashing import hash_file, validate_salt


_PLACEHOLDER_RE = re.compile(r"^REPLACE_WITH_[A-Z_]+$")

#: Revision resolved at runtime when a ``ModelReference.revision`` is still a
#: placeholder (pre-publication stages only). "main" is HuggingFace Hub's
#: default branch - a deliberate, explicit fallback, never a silent None.
UNPINNED_REVISION_FALLBACK: str = "main"

_ENV_PREFIX = "FINFLUENCER_"
_ENV_SEP = "__"


def is_placeholder_revision(value: str) -> bool:
    """Return True iff ``value`` is an unpinned-revision placeholder.

    Single source of truth for the ``REPLACE_WITH_*`` convention, shared
    by :func:`_enforce_stage_policy` (publication-stage gate) and any
    provider-instantiation call site that needs to resolve a config
    revision to something an actual model loader can use (see
    :mod:`finfluencer.collect.main`).
    """
    return bool(_PLACEHOLDER_RE.match(value))


# =============================================================================
# YAML loading
# =============================================================================


def _load_yaml(path: Path) -> Any:
    if not path.exists():
        raise ConfigFileNotFoundError(
            f"Configuration file not found: {path}",
            path=str(path),
        )
    with path.open("r", encoding="utf-8") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigValidationError(
                f"YAML parse error in {path}: {e}",
                path=str(path),
            ) from e


# =============================================================================
# Environment-variable overlay
# =============================================================================


def _coerce_env_value(value: str) -> Any:
    """Coerce an env-var string to a JSON-typed value.

    ``"true"``/``"false"`` -> bool, digit-only -> int, decimal -> float,
    quoted-list -> list, else str.
    """
    v = value.strip()
    if v.lower() in {"true", "false"}:
        return v.lower() == "true"
    if v.lstrip("-").isdigit():
        return int(v)
    try:
        return float(v)
    except ValueError:
        pass
    return v


def _apply_env_overlay(data: dict[str, Any]) -> dict[str, Any]:
    """Overlay ``FINFLUENCER_SECTION__KEY`` env vars onto ``data``."""
    for env_name, env_value in os.environ.items():
        if not env_name.startswith(_ENV_PREFIX):
            continue
        path = env_name[len(_ENV_PREFIX):].lower().split(_ENV_SEP)
        if not path:
            continue
        node: Any = data
        for part in path[:-1]:
            if not isinstance(node, dict):
                break
            node = node.setdefault(part, {})
        if isinstance(node, dict):
            node[path[-1]] = _coerce_env_value(env_value)
    return data


# =============================================================================
# Placeholder / stage enforcement
# =============================================================================


def _iter_revision_fields(settings: Settings) -> list[tuple[str, str]]:
    """Yield ``(dotted_path, value)`` for every revision-bearing field."""
    return [
        ("sentiment.primary_model.revision", settings.sentiment.primary_model.revision),
        (
            "sentiment.target_of_affect.base_revision",
            settings.sentiment.target_of_affect.base_revision,
        ),
        ("topics.embedding_model.revision", settings.topics.embedding_model.revision),
    ]


def _enforce_stage_policy(settings: Settings) -> None:
    """Enforce publication-stage strictness (Methods Section 3.11)."""
    if settings.replication.stage != ReplicationStage.publication:
        return
    unpinned = [
        (path, val)
        for path, val in _iter_revision_fields(settings)
        if is_placeholder_revision(val)
    ]
    if unpinned:
        raise UnpinnedRevisionError(
            f"replication.stage='publication' but revisions are unpinned: "
            f"{[p for p, _ in unpinned]}",
            unpinned_paths=[p for p, _ in unpinned],
        )


# =============================================================================
# Public API
# =============================================================================


class LoadedConfig:
    """Bundle of validated configs and their content hashes.

    Content hashes flow into :mod:`finfluencer.core.reproducibility` to
    detect config drift between runs.
    """

    def __init__(
        self,
        settings: Settings,
        roster: AnalystRoster,
        settings_path: Path,
        analysts_path: Path,
    ) -> None:
        self.settings: Settings = settings
        self.roster: AnalystRoster = roster
        self.settings_path: Path = settings_path
        self.analysts_path: Path = analysts_path
        self.settings_sha256: str = hash_file(settings_path)
        self.analysts_sha256: str = hash_file(analysts_path)


def load_settings(
    settings_path: Path | str = Path("config/settings.yaml"),
    analysts_path: Path | str = Path("config/analysts.yaml"),
    *,
    env_overlay: bool = True,
    validate_secrets: bool = True,
) -> LoadedConfig:
    """Load and validate the platform configuration.

    Parameters
    ----------
    settings_path
        Path to ``settings.yaml``.
    analysts_path
        Path to ``analysts.yaml``.
    env_overlay
        If ``True`` (default), apply ``FINFLUENCER_*`` env-var overrides.
    validate_secrets
        If ``True`` (default), validate ``ANON_SALT`` from the
        environment for real production use.

    Returns
    -------
    LoadedConfig
        Validated settings, roster, and content hashes.

    Raises
    ------
    ConfigFileNotFoundError
        A YAML file is missing.
    ConfigValidationError
        YAML parse failure, or Pydantic validation failure.
    ConfigSchemaMismatchError
        Unknown keys in strict schema.
    UnpinnedRevisionError
        Publication-stage run with placeholder revisions.
    """
    settings_path = Path(settings_path)
    analysts_path = Path(analysts_path)

    raw_settings = _load_yaml(settings_path)
    raw_roster = _load_yaml(analysts_path)

    if env_overlay and isinstance(raw_settings, dict):
        raw_settings = _apply_env_overlay(raw_settings)

    # Validate settings
    try:
        settings = Settings.model_validate(raw_settings)
    except ValidationError as e:
        # Split "unknown key" errors (schema mismatch) from other errors.
        errors = e.errors()
        unknown = [err for err in errors if err.get("type") == "extra_forbidden"]
        if unknown and not any(err.get("type") != "extra_forbidden" for err in errors):
            raise ConfigSchemaMismatchError(
                f"Unknown keys in {settings_path.name}: "
                f"{[err['loc'] for err in unknown]}",
                path=str(settings_path),
                unknown_keys=[list(err['loc']) for err in unknown],
            ) from e
        raise ConfigValidationError(
            f"Validation failed for {settings_path.name}",
            path=str(settings_path),
            validation_errors=errors,
        ) from e

    # Validate roster
    try:
        roster = AnalystRoster.model_validate(raw_roster)
    except ValidationError as e:
        raise ConfigValidationError(
            f"Validation failed for {analysts_path.name}",
            path=str(analysts_path),
            validation_errors=e.errors(),
        ) from e

    _enforce_stage_policy(settings)

    # Salt validation (relies on environment)
    if validate_secrets:
        anon_salt = os.environ.get("ANON_SALT", "")
        if anon_salt:  # empty means not yet configured - dev mode
            strict = settings.replication.stage in (
                ReplicationStage.submission,
                ReplicationStage.publication,
            )
            validate_salt(anon_salt, strict=strict)

    return LoadedConfig(
        settings=settings,
        roster=roster,
        settings_path=settings_path,
        analysts_path=analysts_path,
    )


__all__ = [
    "LoadedConfig", "load_settings",
    "is_placeholder_revision", "UNPINNED_REVISION_FALLBACK",
]
