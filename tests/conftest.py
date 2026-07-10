"""
Shared pytest fixtures for the Finfluencer Research Platform.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure src/ is on the Python path when running from repo root.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture
def strong_salt() -> str:
    """A syntactically valid strong salt for hashing tests."""
    return "a" * 32


@pytest.fixture
def tmp_checkpoint_root(tmp_path: Path) -> Path:
    return tmp_path / "checkpoints"


@pytest.fixture
def tmp_cache_root(tmp_path: Path) -> Path:
    return tmp_path / "cache"


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    """Empty the provider registry between tests to prevent cross-test leaks.
    Re-import the language subpackage after clearing so tests that rely on the
    Turkish provider still find it (import runs @register).
    """
    from finfluencer.core.registry import clear_registry
    clear_registry()
    yield
    clear_registry()
