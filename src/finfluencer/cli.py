"""finfluencer.cli
==================

Packaging entry point for the ``finfluencer`` console script
(``pyproject.toml``'s ``[tool.poetry.scripts]``: ``finfluencer =
"finfluencer.cli:app"``).

The Typer application object itself still lives in
:mod:`finfluencer.collect.main` (its own ``run`` command is defined
there, unchanged, and stays directly invocable via ``python -m
finfluencer.collect.main run`` exactly as before) — this module
preserves the pre-Sprint-2 invariant that every entry point resolves
to the exact same ``app`` object, not independently maintained CLIs.

Sprint 2.4 composition
-----------------------
This module is now also where the reporting CLI
(:mod:`finfluencer.reporting.main` -- ``analyze``, ``report``,
``validate``, ``export``) is mounted onto that same ``app``, as flat
siblings of ``run`` (not nested under a ``reporting`` sub-group), so
both the data-collection and reporting surfaces are reachable directly
under ``finfluencer <command>``:

    finfluencer run ...          # data collection (unchanged)
    finfluencer analyze ...      # reporting: master_table, inferential
    finfluencer report ...       # reporting: manuscript_data/figures/tables
    finfluencer validate ...
    finfluencer export ...

Neither ``collect.main`` nor ``reporting.main`` is modified to do
this: each reporting command is a plain, already-fully-specified
Typer command function (its ``typer.Option(...)`` parameter defaults
and docstring — used as its ``--help`` text — are defined once, in
``reporting/main.py``). Registering that same function object a
second time on ``app`` via ``app.command()`` is the standard Typer
pattern for composing commands defined elsewhere onto a shared CLI;
it does not mutate the function, and ``reporting.main.app`` (the
reporting CLI's own standalone Typer instance, still directly usable
via ``python -m finfluencer.reporting.main``) is completely
unaffected.
"""

from __future__ import annotations

from finfluencer.collect.main import app
from finfluencer.reporting.main import analyze, export, report, validate

app.command(name="analyze")(analyze)
app.command(name="report")(report)
app.command(name="validate")(validate)
app.command(name="export")(export)

__all__ = ["app"]


def main() -> None:
    """Module entry point (``python -m finfluencer.cli``)."""
    app()


if __name__ == "__main__":
    main()
