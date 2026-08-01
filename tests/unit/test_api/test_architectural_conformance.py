"""Architectural conformance tests for the API Layer (BACKLOG.md T-012).

`scripts/check_layer_dependencies.py`'s IG-001 checker already mechanically enforces
`api` -> not importing `infrastructure`/`persistence` (its `FORBIDDEN_IMPORTS` rule set). It does
NOT check `api` -> not importing `domain` (see the script's own docstring: IG-001 "verbatim"
only names infrastructure/persistence for `api`) -- `PRODUCT_ARCHITECTURE.md` section 12.1 line
821 forbids it textually regardless. Same discipline as every other mechanically-uncovered edge
this engagement has found (Application in T-009/T-010/T-011, Infrastructure in T-010).

`bootstrap.py` is deliberately exempt from all of this -- it is documented, in its own module
docstring, as the one composition-root file outside the six layers, and IG-001's checker never
walks it (it only walks `presentation`/`api`/`domain` directories). This test suite proves the
*routes* honor the boundary, not that the composition root does (it can't, by definition, and
says so).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from finfluencer.api.routes import collection as collection_routes
from finfluencer.api.routes import identity as identity_routes


def _imported_module_names(module: object) -> list[str]:
    tree = ast.parse(inspect.getsource(module))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_identity_route_module_imports_only_application_and_presentation() -> None:
    imported = _imported_module_names(identity_routes)
    assert not any(m.startswith("finfluencer.domain") for m in imported)
    assert not any(m.startswith("finfluencer.infrastructure") for m in imported)
    assert not any(m.startswith("finfluencer.persistence") for m in imported)


def test_collection_route_module_imports_only_application_and_presentation() -> None:
    imported = _imported_module_names(collection_routes)
    assert not any(m.startswith("finfluencer.domain") for m in imported)
    assert not any(m.startswith("finfluencer.infrastructure") for m in imported)
    assert not any(m.startswith("finfluencer.persistence") for m in imported)


def test_deps_module_imports_only_application_types() -> None:
    from finfluencer.api import deps as deps_module

    imported = _imported_module_names(deps_module)
    assert not any(m.startswith("finfluencer.domain") for m in imported)
    assert not any(m.startswith("finfluencer.infrastructure") for m in imported)
    assert not any(m.startswith("finfluencer.persistence") for m in imported)


def test_check_layer_dependencies_script_is_clean() -> None:
    # Direct, redundant proof (in addition to the ast-based checks above) that the mechanical
    # IG-001 checker itself reports no violations with the real api/ tree on disk.
    import subprocess
    import sys

    repo_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "check_layer_dependencies.py")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
