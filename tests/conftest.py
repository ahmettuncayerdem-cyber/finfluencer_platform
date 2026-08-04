"""
Shared pytest fixtures for the Finfluencer Research Platform.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

# Ensure src/ is on the Python path when running from repo root.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def pytest_configure(config: pytest.Config) -> None:
    """Force a deterministic, non-interactive matplotlib backend for the
    entire test session, before any test module can import
    ``matplotlib.pyplot``.

    Rationale (PE-03): ``reporting/manuscript_figures.py`` and
    ``market/figures.py`` deliberately do not call ``matplotlib.use(...)`` at
    import time -- a packaged library module should not silently override its
    importer's backend choice. That means the *importer* is responsible for
    selecting a backend, and for a test session the importer is the test
    suite itself. ``pytest_configure`` is the earliest pytest hook that runs
    before test collection (which is what triggers the module-level
    ``import matplotlib.pyplot`` in the figure modules), so setting the
    backend here -- rather than in an autouse fixture, which only fires per
    test *after* collection -- guarantees the backend is fixed before any
    test module can resolve a GUI backend (e.g. TkAgg) and hit a headless
    ``TclError``.

    This only affects the pytest process. It does not change
    ``reporting/manuscript_figures.py``, ``market/figures.py``, or any
    production import path, and does not alter what those modules render --
    Agg produces pixel/text-identical output to other non-interactive
    backends for the PNG/SVG assertions in this suite.

    If something already imported ``matplotlib.pyplot`` before this hook
    ran (e.g. an external plugin with its own early import), the backend
    switch may not take effect. That is a sequencing anomaly, not a
    guaranteed failure, so it is surfaced as a warning rather than aborting
    the session -- see PE-03 Phase 4/5 risk assessment.

    This hook is a no-op when ``matplotlib`` is not installed at all --
    e.g. CI's "Layer Dependency Conformance (IG-001)" job (``ci.yml``),
    which deliberately runs a stdlib-only ``pytest`` invocation (``pip
    install pytest`` only, no ``poetry install --sync``) so it doesn't
    share the lint/test jobs' dependency-stack failure modes. No test
    collected in that job imports ``matplotlib.pyplot`` either, so there
    is no backend to fix -- failing pytest startup there would be
    enforcing a dependency this hook's own job doesn't need, not
    protecting anything.
    """
    try:
        import matplotlib
    except ModuleNotFoundError:
        return

    if "matplotlib.pyplot" in sys.modules:
        warnings.warn(
            "matplotlib.pyplot was already imported before "
            "tests/conftest.py:pytest_configure ran; the Agg backend "
            "override may not take effect. This likely indicates an early "
            "import (an external pytest plugin, conftest load order, or "
            "a '-p' preload) bypassed the intended initialization point. "
            "If Tk-related test failures reappear, investigate what "
            "imported matplotlib.pyplot first.",
            stacklevel=2,
        )

    matplotlib.use("Agg")


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
