"""Tests for scripts/check_layer_dependencies.py (IG-001, IMPLEMENTATION_PLAYBOOK.md section 0).

Loads the checker by file path rather than as an installed package, since `scripts/` is a
standalone tooling directory, not part of the `finfluencer` distribution (pyproject.toml's `src`
layout only packages `finfluencer` itself).

This suite is BACKLOG.md T-005's own acceptance criterion, in the literal sense the task
describes: "write it, confirm red, revert, confirm green." test_violation_then_revert below does
exactly that against one fixture, and the surrounding tests establish the rule's precise
boundary -- what IG-001 actually forbids, and just as importantly, what it does not.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "check_layer_dependencies.py"
_spec = importlib.util.spec_from_file_location("check_layer_dependencies", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
check_layer_dependencies = importlib.util.module_from_spec(_spec)
sys.modules["check_layer_dependencies"] = check_layer_dependencies
_spec.loader.exec_module(check_layer_dependencies)

check_layers = check_layer_dependencies.check_layers


def _write(root: Path, relative: str, source: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_no_violations_when_layer_directories_do_not_exist(tmp_path: Path) -> None:
    # T-006 hasn't scaffolded the six-layer skeleton at the point T-005 lands -- the checker must
    # treat "layer directory absent" as clean, not as an error.
    assert check_layers(tmp_path) == []


def test_clean_domain_module_passes(tmp_path: Path) -> None:
    _write(tmp_path, "domain/project.py", "from finfluencer.domain.base import Entity\n")
    assert check_layers(tmp_path) == []


def test_domain_importing_infrastructure_is_flagged(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "domain/project.py",
        "from finfluencer.infrastructure.youtube import YouTubeClient\n",
    )
    violations = check_layers(tmp_path)
    assert len(violations) == 1
    assert violations[0].layer == "domain"
    assert violations[0].imported == "finfluencer.infrastructure.youtube"


def test_presentation_importing_persistence_is_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "presentation/views.py", "import finfluencer.persistence.models\n")
    violations = check_layers(tmp_path)
    assert len(violations) == 1
    assert violations[0].layer == "presentation"


def test_api_importing_domain_is_allowed(tmp_path: Path) -> None:
    # IG-001 restricts presentation/api from infrastructure/persistence only -- api importing
    # domain is exactly the direction the architecture requires, not a violation.
    _write(tmp_path, "api/routes.py", "from finfluencer.domain.project import Project\n")
    assert check_layers(tmp_path) == []


def test_application_layer_is_not_checked(tmp_path: Path) -> None:
    # IG-001's text names presentation, api, and domain only. application/infrastructure/
    # persistence have no rule here -- inventing one would be governance this script has no
    # authority to add.
    _write(
        tmp_path,
        "application/orchestrator.py",
        "from finfluencer.infrastructure.youtube import YouTubeClient\n",
    )
    assert check_layers(tmp_path) == []


def test_violation_then_revert(tmp_path: Path) -> None:
    """The literal T-005 acceptance criterion: confirm red, revert, confirm green."""
    target = _write(
        tmp_path, "domain/collection_run.py", "from finfluencer.persistence.orm import Base\n"
    )

    red = check_layers(tmp_path)
    assert len(red) == 1
    assert red[0].imported == "finfluencer.persistence.orm"

    target.write_text("from finfluencer.domain.base import Entity\n", encoding="utf-8")
    green = check_layers(tmp_path)
    assert green == []


def test_main_exits_nonzero_on_violation(tmp_path: Path) -> None:
    _write(tmp_path, "domain/x.py", "from finfluencer.api.routes import router\n")
    assert check_layer_dependencies.main(["--root", str(tmp_path)]) == 1


def test_main_exits_zero_when_clean(tmp_path: Path) -> None:
    _write(tmp_path, "domain/x.py", "from finfluencer.domain.base import Entity\n")
    assert check_layer_dependencies.main(["--root", str(tmp_path)]) == 0
