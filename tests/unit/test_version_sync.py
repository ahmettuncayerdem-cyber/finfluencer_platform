"""
tests.unit.test_version_sync
==============================

Sprint 2.7A (Versioning, TD-10) regression guard: ``finfluencer.__version__``
must always equal ``pyproject.toml``'s ``[tool.poetry].version``. These are
the same axis (the software package's SemVer version) expressed in two
places for two different consumers (import-time introspection vs. package
metadata) and must never be allowed to drift, as they silently did before
this test existed (``__version__`` was accidentally bumped to match
``CITATION.cff``'s unrelated research/citation version while
``pyproject.toml`` stayed unchanged). See ``docs/VERSIONING.md`` for the
full policy, including why ``CITATION.cff`` is a deliberately separate
axis this test does not touch.
"""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11 dev-tooling fallback; the
    # project's own supported range (>=3.11) always has tomllib in the
    # standard library, so this branch is not exercised in CI.
    import tomli as tomllib  # type: ignore[no-redef]

import finfluencer

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _pyproject_version() -> str:
    pyproject = _REPO_ROOT / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    return str(data["tool"]["poetry"]["version"])


class TestVersionSync:
    def test_dunder_version_matches_pyproject_toml(self) -> None:
        assert finfluencer.__version__ == _pyproject_version(), (
            "finfluencer.__version__ (src/finfluencer/__init__.py) has drifted "
            "from pyproject.toml's [tool.poetry].version -- see docs/VERSIONING.md. "
            "Update __version__ to match pyproject.toml; never the reverse, and "
            "never copy CITATION.cff's version here -- that is a separate axis."
        )
