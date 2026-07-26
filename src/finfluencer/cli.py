"""finfluencer.cli
==================

Packaging entry point for the ``finfluencer`` console script
(``pyproject.toml``'s ``[tool.poetry.scripts]``: ``finfluencer =
"finfluencer.cli:app"``).

This module intentionally contains no logic of its own. The Typer
application lives in :mod:`finfluencer.collect.main`, which is also
directly invocable via ``python -m finfluencer.collect.main`` — both
paths must resolve to the exact same ``app`` object, not two
independently maintained CLIs.
"""

from __future__ import annotations

from finfluencer.collect.main import app

__all__ = ["app"]
