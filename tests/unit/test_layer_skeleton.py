"""Tests for the six-layer package skeleton (BACKLOG.md T-006).

Proves T-006's own acceptance criterion literally: "empty packages exist, import correctly, CI
(T-005) runs clean against them." No business logic is tested here because none exists yet by
design -- these packages are deliberately empty (PRODUCT_ARCHITECTURE.md section 12.1); the first
real content lands with BACKLOG.md T-007 (Domain Model) and T-010 (Infrastructure adapter).
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

LAYERS = ("presentation", "api", "application", "domain", "infrastructure", "persistence")


@pytest.mark.parametrize("layer", LAYERS)
def test_layer_package_exists_and_imports(layer: str) -> None:
    module = importlib.import_module(f"finfluencer.{layer}")
    assert module is not None


def test_layer_check_reports_clean_against_real_source_tree() -> None:
    """The literal T-006 verification: 'CI (T-005) runs clean against them.'"""
    import importlib.util
    import sys

    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_layer_dependencies.py"
    spec = importlib.util.spec_from_file_location("check_layer_dependencies", script_path)
    assert spec is not None and spec.loader is not None
    checker = importlib.util.module_from_spec(spec)
    sys.modules["check_layer_dependencies"] = checker
    spec.loader.exec_module(checker)

    src_root = Path(__file__).resolve().parents[2] / "src" / "finfluencer"
    violations = checker.check_layers(src_root)
    assert violations == [], f"IG-001 violations found against real source tree: {violations}"
