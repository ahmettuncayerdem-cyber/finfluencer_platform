"""
finfluencer.reporting.replication
====================================

Sprint 2.5: replication-package assembly.

Extracted, behavior-preserving, from ``reporting/main.py``'s ``export``
command (Sprint 2.3 inline implementation) into its own module, exactly
as that module's own docstring said it eventually would be: "this
command's inline implementation may be extracted there unchanged once
that module exists." Nothing about the logic changed in the move --
same dependency check, same destination naming, same overwrite/force
semantics, same return shape -- only its location and, since it is now
a standalone public API rather than a CLI-private helper, its name
(``_build_replication_package`` -> :func:`build_replication_package`)
and docstring detail.

Scope
-----
This module still only assembles a local filesystem snapshot of the
current report-stage outputs (manuscript, figures, tables, reports)
under ``output.paths.replication`` -- the same minimal scope Sprint
2.3 deliberately chose over building out full archival/versioning/
Zenodo-deposition logic prematurely. That larger scope (e.g. honoring
``replication.target``/``replication.zenodo`` from ``settings.yaml``,
which exist in the schema but are not read anywhere in ``src/`` yet)
remains a candidate for a future step, not part of this extraction.

Public API
----------
:func:`build_replication_package`
    Pure(ish) function of a loaded config: reads
    ``output.paths.{manuscript,figures,tables,reports}``, validates
    they are non-empty, and either reports what it would do
    (``dry_run=True``) or copies them into a fresh, timestamped
    directory under ``output.paths.replication`` (optionally
    overwriting an existing one with ``force=True``).

Not implemented here
---------------------
* Any CLI concerns (argument parsing, ``--json``/human-readable
  output formatting, exit codes) -- those stay in
  :mod:`finfluencer.reporting.main`, which is now a thin dispatcher
  over this function for the ``export`` command.
* :class:`AnalysisJob` (deferred to Sprint 2.6, per ADR-Sprint2-01).
* Real archival/versioning/Zenodo deposition (see Scope above).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from finfluencer.core.config import LoadedConfig
from finfluencer.core.logging import get_logger
from finfluencer.core.reproducibility import generate_run_id

_log = get_logger(__name__)

#: The four report-stage output directories staged into a replication
#: snapshot, keyed by the sub-directory name used inside the snapshot.
EXPORT_SOURCES: tuple[str, ...] = ("manuscript", "figures", "tables", "reports")


def _resolve_sources(cfg: LoadedConfig) -> dict[str, Path]:
    """Map each :data:`EXPORT_SOURCES` name to its concrete
    ``output.paths.*`` location for this config."""
    paths = cfg.settings.output.paths
    by_name = {
        "manuscript": paths.manuscript,
        "figures": paths.figures,
        "tables": paths.tables,
        "reports": paths.reports,
    }
    return {name: Path(str(by_name[name])) for name in EXPORT_SOURCES}


def build_replication_package(
    cfg: LoadedConfig,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Stage the current report-stage outputs into a timestamped
    replication snapshot.

    Copies ``output.paths.manuscript``, ``.figures``, ``.tables``, and
    ``.reports`` into a fresh directory named with a freshly generated
    run ID (:func:`finfluencer.core.reproducibility.generate_run_id`)
    under ``output.paths.replication``, each preserved as its own
    identically-named sub-directory.

    Parameters
    ----------
    cfg
        Result of :func:`finfluencer.core.config.load_settings`.
    dry_run
        If ``True``, validate that every source directory exists and
        is non-empty, then return the destination path and source
        locations without copying anything.
    force
        If ``True`` and the destination directory already exists
        (only possible if two calls somehow land on the same run ID),
        remove it first rather than raising.

    Returns
    -------
    dict[str, Any]
        If ``dry_run``: ``{"would_export_to": Path, "sources": dict[str, str]}``.
        Otherwise: ``{"exported_to": Path, "n_items": int}`` -- the
        snapshot directory and the number of files it now contains.

    Raises
    ------
    FileNotFoundError
        Any of the four source directories does not exist or is empty
        (i.e. the ``report`` stages have not been run yet).
    FileExistsError
        The destination directory already exists and ``force`` is
        ``False``.
    """
    sources = _resolve_sources(cfg)
    missing = [name for name, d in sources.items() if not d.exists() or not any(d.iterdir())]
    if missing:
        raise FileNotFoundError(
            f"Cannot export: no output found for {missing}; run 'report' first.",
        )

    dest = Path(str(cfg.settings.output.paths.replication)) / generate_run_id()

    if dry_run:
        _log.info("replication_dry_run", would_export_to=str(dest))
        return {"would_export_to": dest, "sources": {k: str(v) for k, v in sources.items()}}

    if dest.exists():
        if not force:
            raise FileExistsError(f"{dest} already exists; pass --force to overwrite")
        shutil.rmtree(dest)

    dest.mkdir(parents=True)
    for name, src in sources.items():
        shutil.copytree(src, dest / name)

    n_items = sum(1 for f in dest.rglob("*") if f.is_file())
    _log.info("replication_package_built", dest=str(dest), n_items=n_items)
    return {"exported_to": dest, "n_items": n_items}


__all__ = ["build_replication_package", "EXPORT_SOURCES"]
