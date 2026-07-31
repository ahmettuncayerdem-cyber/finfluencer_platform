"""
finfluencer.reporting.replication
====================================

Sprint 2.5: replication-package assembly.
Sprint 2 (Product Engineering): publication-grade package enhancement.

Extracted, behavior-preserving, from ``reporting/main.py``'s ``export``
command (Sprint 2.3 inline implementation) into its own module, exactly
as that module's own docstring said it eventually would be: "this
command's inline implementation may be extracted there unchanged once
that module exists." Nothing about the original copy logic changed in
the move -- same dependency check, same destination naming, same
overwrite/force semantics, same return shape -- only its location and,
since it is now a standalone public API rather than a CLI-private
helper, its name (``_build_replication_package`` -> :func:`build_replication_package`)
and docstring detail.

Sprint 2 scope (this update)
-----------------------------
:func:`build_replication_package` now assembles a publication-grade
package rather than a bare directory copy: an embedded run manifest
(:func:`_build_export_manifest`), an automatically generated codebook
(:func:`generate_codebook`, data-driven -- introspects the files
actually present rather than relying on ``core/contracts.py`` field
descriptions, which do not cover this package's contents and are not
touched here), a human-readable ``README.md``
(:func:`_render_readme`), a ``sha256sum``-compatible checksum manifest
(:func:`compute_checksums` / :func:`write_checksums_file`), a
self-validation pass (:func:`validate_replication_package`), and a
deterministically-constructed zip archive (:func:`create_archive`).

Reproducibility contract
-------------------------
Rebuilding a package from the same, already-generated report outputs
reproduces byte-identical contents for every generated file *except*
``MANIFEST.json``, whose ``export_provenance.run_id``,
``.timestamp_utc``, and ``.extras`` fields are unique per export by
design (see :func:`finfluencer.core.reproducibility.generate_run_id`).
``MANIFEST.json``'s ``export_provenance.environment``, ``.git``, and
``.config_hashes`` fields are *not* treated as volatile -- they are
reproducible given an unchanged environment, and a difference there is
a real signal, not noise. This distinction is stated explicitly in
every package's own generated ``README.md``, not left implicit.

This guarantee covers packaging only, not the upstream reporting
pipeline: the figures/tables files copied into a package were produced
by an earlier, separate ``finfluencer report`` run, and whether *that*
run is itself byte-reproducible across two independent executions is
a property of :mod:`finfluencer.reporting.manuscript_figures` /
:mod:`finfluencer.reporting.manuscript_tables` (both out of this
sprint's scope), not of this module.

Scope
-----
This module still only assembles a local filesystem snapshot (now
enriched as above) of the current report-stage outputs (manuscript,
figures, tables, reports) under ``output.paths.replication``.
``replication.stage`` is read and enforced (reusing existing,
already-tested :mod:`finfluencer.core.reproducibility` infrastructure
for the ``submission``/``publication`` stages -- no new reproducibility
logic is introduced here). ``replication.target``/``replication.zenodo``
are read and embedded into ``MANIFEST.json`` for record-keeping, but no
network call to Zenodo or any other deposit target is made -- real
archival/versioning/deposition logic remains a candidate for a future
step, exactly as before this update.
``replication.include_model_weights`` is read, but **not yet wired** to
stage ``output.paths.cache`` into the package: this environment has no
populated cache directory to verify size/content characteristics
against (Sprint 2 Phase 4 risk assessment), so wiring it now would be
an unverified behavior change. A warning is logged when this flag is
set, naming the gap explicitly rather than silently ignoring it.

Public API
----------
:func:`build_replication_package`
    Orchestrates every step above. Pure(ish) function of a loaded
    config plus whatever is currently on disk under
    ``output.paths.{manuscript,figures,tables,reports}``.
:func:`generate_codebook`, :func:`compute_checksums`,
:func:`write_checksums_file`, :func:`create_archive`,
:func:`validate_replication_package`
    Individually callable building blocks -- each usable standalone
    (e.g. :func:`validate_replication_package` against a package
    re-extracted from an OSF/Zenodo deposit, independent of this
    module having built it).

Not implemented here
---------------------
* Any CLI concerns (argument parsing, ``--json``/human-readable
  output formatting, exit codes) -- those stay in
  :mod:`finfluencer.reporting.main`, which is a thin dispatcher over
  this module for the ``export`` command.
* :class:`AnalysisJob` (deferred to Sprint 2.6, per ADR-Sprint2-01).
* Real archival/versioning/Zenodo deposition, and staging
  ``output.paths.cache`` for ``include_model_weights`` (see Scope
  above).
"""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from finfluencer.core.config import LoadedConfig
from finfluencer.core.contracts import ReplicationStage
from finfluencer.core.exceptions import ReproducibilityError
from finfluencer.core.logging import get_logger
from finfluencer.core.reproducibility import (
    build_provenance,
    enforce_clean_tree,
    generate_run_id,
    get_git_state,
)
from finfluencer.utils.hashing import hash_file
from finfluencer.utils.io import write_json

_log = get_logger(__name__)

#: The four report-stage output directories staged into a replication
#: snapshot, keyed by the sub-directory name used inside the snapshot.
EXPORT_SOURCES: tuple[str, ...] = ("manuscript", "figures", "tables", "reports")

#: Schema version of the ``MANIFEST.json`` wrapper this module writes.
#: Bump this if the wrapper's own shape (not ``build_provenance()``'s,
#: which is versioned independently) changes in a way a future
#: validator needs to branch on.
MANIFEST_SCHEMA_VERSION: str = "1.0"

#: Files this module writes at the package root, in addition to the
#: four :data:`EXPORT_SOURCES` sub-directories. Excluded from
#: :func:`generate_codebook`'s own introspection (a codebook describing
#: the package's own scaffolding would be circular) and used by
#: :func:`validate_replication_package` as its required-file list.
_PACKAGE_SCAFFOLDING_FILES: tuple[str, ...] = (
    "MANIFEST.json",
    "README.md",
    "CODEBOOK.md",
    "codebook.json",
    "CHECKSUMS.sha256",
)

#: Fixed zip entry timestamp (1980-01-01, zip's own minimum
#: representable date) used by :func:`create_archive` instead of the
#: real export timestamp, so the archive's internal layout is
#: reproducible across builds regardless of when they ran.
_ZIP_FIXED_DATE_TIME: tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0)

_README_TEMPLATE = """\
# Replication Package -- {study_name} (v{study_version})

Assembled by `finfluencer.reporting.replication.build_replication_package`.

## Contents

{contents_list}

## Provenance and reproducibility

Full provenance (run ID, timestamp, git commit, resolved config hashes,
package versions) is recorded in `MANIFEST.json`, under
`export_provenance`. Historical per-stage run manifests from the
`analyze`/`report` runs that produced this package's inputs are
included verbatim under `historical_run_manifests`.

**This package's assembly step is deterministic.** Rebuilding it from
the same, already-generated report outputs reproduces byte-identical
contents for every file in this package *except* `MANIFEST.json`
itself -- whose `export_provenance.run_id`, `.timestamp_utc`, and
`.extras` fields are unique per export by design. By contrast,
`export_provenance.environment`, `.git`, and `.config_hashes` are
reproducible given an unchanged environment; a difference there
reflects a real environment change, not packaging noise.

**Scope boundary.** This guarantee covers packaging only. The figures
and tables copied into this package were produced by an earlier,
separate pipeline run (`finfluencer report`). Whether that run is
itself byte-reproducible across two independent executions is a
property of the upstream reporting pipeline, not of this packaging
step, and is not asserted here.

## Verifying integrity

Every file in this package other than `README.md` and
`CHECKSUMS.sha256` itself is checksummed in `CHECKSUMS.sha256`, in
standard `sha256sum` format:

    sha256sum -c CHECKSUMS.sha256

## Codebook

See `CODEBOOK.md` (human-readable) or `codebook.json`
(machine-readable) for a per-file, per-column description of every
tabular artifact in this package, generated automatically from each
file's own structure.
"""


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


def _gate_publication_stage(cfg: LoadedConfig) -> None:
    """Enforce ``replication.stage``'s reproducibility requirements
    before any export work happens, reusing existing, already-tested
    :mod:`finfluencer.core.reproducibility` checks unchanged -- no new
    reproducibility logic is introduced by this function."""
    if cfg.settings.replication.stage in (ReplicationStage.submission, ReplicationStage.publication):
        enforce_clean_tree(get_git_state())


def _warn_if_model_weights_not_wired(cfg: LoadedConfig) -> None:
    if cfg.settings.replication.include_model_weights:
        _log.warning(
            "include_model_weights_not_wired",
            note=(
                "replication.include_model_weights=True, but this build does "
                "not stage output.paths.cache into the package -- its size/"
                "content characteristics are unverified in this environment "
                "(Sprint 2 Phase 4 risk assessment). Not silently ignored: "
                "flagged here so the gap is visible, not assumed away."
            ),
        )


# =============================================================================
# Embedded run manifest
# =============================================================================


def _build_export_manifest(cfg: LoadedConfig) -> dict[str, Any]:
    """Build the ``MANIFEST.json`` wrapper: this export's own
    provenance (:func:`build_provenance`, unmodified) plus every
    historical per-stage run manifest already on disk under
    ``output.paths.checkpoints/run_manifests/``, read in sorted
    (deterministic) order. A manifest that fails to parse is recorded
    as a warning, not raised -- one corrupt historical file must not
    abort the export."""
    provenance = build_provenance(cfg, stage="export")
    replication_cfg = cfg.settings.replication
    provenance["extras"] = {
        **provenance.get("extras", {}),
        "replication_target": replication_cfg.target.value,
        "replication_zenodo": {
            "community": replication_cfg.zenodo.community,
            "sandbox": replication_cfg.zenodo.sandbox,
            "embargo_until": str(replication_cfg.zenodo.embargo_until)
            if replication_cfg.zenodo.embargo_until
            else None,
        },
    }

    historical: list[dict[str, Any]] = []
    manifests_dir = Path(str(cfg.settings.output.paths.checkpoints)) / "run_manifests"
    if manifests_dir.is_dir():
        for p in sorted(manifests_dir.glob("*.json")):
            try:
                historical.append(json.loads(p.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError) as exc:
                _log.warning("historical_manifest_unreadable", path=str(p), reason=type(exc).__name__)

    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "export_provenance": provenance,
        "historical_run_manifests": historical,
    }


# =============================================================================
# Codebook (data-driven -- introspects package contents, not contracts.py)
# =============================================================================


def _describe_dataframe(df: pd.DataFrame, *, fmt: str) -> dict[str, Any]:
    columns: list[dict[str, Any]] = []
    for col in df.columns:
        series = df[col]
        entry: dict[str, Any] = {
            "name": str(col),
            "dtype": str(series.dtype),
            "non_null": int(series.notna().sum()),
            "n_unique": int(series.nunique(dropna=True)),
        }
        if entry["n_unique"] <= 12:
            entry["values"] = sorted(str(v) for v in series.dropna().unique())
        columns.append(entry)
    return {"format": fmt, "n_rows": int(len(df)), "n_columns": int(len(df.columns)), "columns": columns}


def _sorted_files(package_dir: Path) -> list[Path]:
    """Every file under ``package_dir``, sorted by its POSIX-style
    relative path string.

    Deliberately *not* ``sorted(package_dir.rglob("*"))`` -- comparing
    :class:`~pathlib.Path` objects directly compares
    :class:`~pathlib.WindowsPath` case-insensitively on Windows but
    :class:`~pathlib.PosixPath` case-sensitively elsewhere, so the same
    package would sort into a different internal order (codebook key
    order, checksum-file line order, zip member order) depending on
    which OS built it -- a real cross-platform reproducibility break,
    not a cosmetic one. Sorting explicitly by the same
    ``.as_posix()`` string every caller already uses as the file's
    identity key is deterministic on every platform."""
    return sorted(
        (p for p in package_dir.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(package_dir).as_posix(),
    )


def _describe_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _describe_dataframe(pd.read_csv(path), fmt="csv")
    if suffix in (".xlsx", ".xls"):
        sheets = pd.read_excel(path, sheet_name=None)
        return {
            "format": "xlsx",
            "sheets": {name: _describe_dataframe(df, fmt="xlsx") for name, df in sorted(sheets.items())},
        }
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return _describe_dataframe(pd.DataFrame(data), fmt="json")
        return {
            "format": "json",
            "top_level_keys": sorted(data.keys()) if isinstance(data, dict) else None,
            "size_bytes": path.stat().st_size,
        }
    return {"format": suffix.lstrip(".") or "unknown", "size_bytes": path.stat().st_size}


def generate_codebook(package_dir: Path) -> dict[str, Any]:
    """Data-driven codebook: describes every file under ``package_dir``
    by introspecting its actual structure (columns/dtypes for
    CSV/XLSX/tabular-JSON; size and top-level keys otherwise). Never
    raises: a file that fails to parse gets a ``"format": "unknown"``
    entry noting the failure, rather than aborting the export.

    Deliberately does not read :mod:`finfluencer.core.contracts` --
    this package's current contents (manuscript/figures/tables/reports)
    are not raw entity-centric parquet files governed by those
    contracts, so a schema-reflection approach would not describe what
    is actually here."""
    entries: dict[str, Any] = {}
    for path in _sorted_files(package_dir):
        if path.name in _PACKAGE_SCAFFOLDING_FILES:
            continue
        rel = path.relative_to(package_dir).as_posix()
        try:
            entries[rel] = _describe_file(path)
        except Exception as exc:  # noqa: BLE001 -- one bad file must not abort the export
            entries[rel] = {"format": "unknown", "note": f"introspection failed: {type(exc).__name__}"}
    return entries


def _render_codebook_markdown(codebook: dict[str, Any]) -> str:
    lines = ["# Codebook", "", "Automatically generated from each file's own structure.", ""]
    for rel, entry in codebook.items():
        lines.append(f"## `{rel}`")
        lines.append("")
        fmt = entry.get("format", "unknown")
        if fmt in ("csv", "json") and "columns" in entry:
            lines.append(f"Format: {fmt}. {entry['n_rows']} rows x {entry['n_columns']} columns.")
            lines.append("")
            lines.append("| column | dtype | non-null | n unique |")
            lines.append("|---|---|---|---|")
            for col in entry["columns"]:
                lines.append(f"| {col['name']} | {col['dtype']} | {col['non_null']} | {col['n_unique']} |")
            lines.append("")
        elif fmt == "xlsx" and "sheets" in entry:
            for sheet_name, sheet in entry["sheets"].items():
                lines.append(f"**Sheet: {sheet_name}** -- {sheet['n_rows']} rows x {sheet['n_columns']} columns.")
                lines.append("")
                lines.append("| column | dtype | non-null | n unique |")
                lines.append("|---|---|---|---|")
                for col in sheet["columns"]:
                    lines.append(f"| {col['name']} | {col['dtype']} | {col['non_null']} | {col['n_unique']} |")
                lines.append("")
        else:
            lines.append(f"Format: {fmt}. {entry.get('size_bytes', '?')} bytes.")
            lines.append("")
    return "\n".join(lines)


# =============================================================================
# README
# =============================================================================


def _render_readme(cfg: LoadedConfig, package_dir: Path) -> str:
    contents = sorted(p.name for p in package_dir.iterdir())
    contents_list = "\n".join(f"- `{name}`" for name in contents)
    return _README_TEMPLATE.format(
        study_name=cfg.settings.study.name,
        study_version=cfg.settings.study.version,
        contents_list=contents_list,
    )


# =============================================================================
# Checksums
# =============================================================================


def compute_checksums(package_dir: Path) -> dict[str, str]:
    """SHA-256 (via :func:`finfluencer.utils.hashing.hash_file`) of
    every file under ``package_dir``, keyed by POSIX-style relative
    path, excluding ``CHECKSUMS.sha256`` itself. Iterates in sorted
    order so the resulting mapping's construction is deterministic
    regardless of filesystem directory-listing order."""
    checksums: dict[str, str] = {}
    for path in _sorted_files(package_dir):
        if path.name == "CHECKSUMS.sha256":
            continue
        rel = path.relative_to(package_dir).as_posix()
        checksums[rel] = hash_file(path)
    return checksums


def write_checksums_file(checksums: dict[str, str], package_dir: Path) -> Path:
    """Write ``checksums`` to ``CHECKSUMS.sha256`` in standard
    ``sha256sum``-compatible format (``<hex digest>  <relative path>``,
    two spaces), sorted by path -- verifiable with ``sha256sum -c``
    on any platform with that tool, not just this codebase."""
    dest = package_dir / "CHECKSUMS.sha256"
    lines = [f"{digest}  {rel}" for rel, digest in sorted(checksums.items())]
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


# =============================================================================
# Archive
# =============================================================================


def create_archive(package_dir: Path, *, fmt: str = "zip") -> Path:
    """Archive ``package_dir`` into a single deposit-ready file
    alongside it (``package_dir.zip``, not inside ``package_dir`` --
    an archive cannot sensibly contain itself).

    Only ``fmt="zip"`` is implemented. ``fmt`` is a **documented
    extension point**: the parameter exists so a future format (e.g.
    ``"tar.gz"``, should OSF/Zenodo tooling prefer it) can be added
    without changing this function's signature or its callers.
    Anything other than ``"zip"`` raises :class:`ValueError` today.

    Deterministic construction: every archived file's timestamp is
    pinned to :data:`_ZIP_FIXED_DATE_TIME` (1980-01-01, zip's own
    minimum representable date) rather than the real export time, and
    files are added in sorted path order with no OS-specific extra
    fields. This makes the archive's internal layout reproducible
    across builds. The archive's own overall hash still legitimately
    differs between builds -- an intentional design characteristic,
    not a defect -- because it contains ``MANIFEST.json``, whose
    ``run_id``/``timestamp_utc`` are unique per export by design (see
    this package's own ``README.md``).
    """
    if fmt != "zip":
        raise ValueError(f"create_archive: unsupported fmt {fmt!r} (only 'zip' is implemented)")

    archive_path = package_dir.parent / f"{package_dir.name}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in _sorted_files(package_dir):
            rel = path.relative_to(package_dir).as_posix()
            info = zipfile.ZipInfo(rel, date_time=_ZIP_FIXED_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            with path.open("rb") as f:
                zf.writestr(info, f.read())
    return archive_path


# =============================================================================
# Validation
# =============================================================================


@dataclass
class ValidationReport:
    """Result of :func:`validate_replication_package`."""

    ok: bool
    issues: list[str] = field(default_factory=list)


def validate_replication_package(package_dir: Path) -> ValidationReport:
    """Re-verify an already-built (or re-extracted) replication
    package: recomputes every checksum in ``CHECKSUMS.sha256`` and
    compares it against the file currently on disk, and confirms the
    package's required scaffolding files and the four report-stage
    sub-directories are present and non-empty.

    Callable standalone, independent of :func:`build_replication_package`
    having just built the package in this same process -- e.g. months
    later, against a package re-extracted from an OSF/Zenodo deposit,
    to confirm nothing was corrupted in storage or transit.
    """
    issues: list[str] = []

    for name in _PACKAGE_SCAFFOLDING_FILES:
        if not (package_dir / name).is_file():
            issues.append(f"{name}: missing")

    checksums_path = package_dir / "CHECKSUMS.sha256"
    if checksums_path.is_file():
        for line in checksums_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, _, rel = line.partition("  ")
            target = package_dir / rel
            if not target.is_file():
                issues.append(f"{rel}: listed in CHECKSUMS.sha256 but missing on disk")
                continue
            actual = hash_file(target)
            if actual != digest:
                issues.append(f"{rel}: checksum mismatch (expected {digest}, got {actual})")

    for name in EXPORT_SOURCES:
        d = package_dir / name
        if not d.is_dir() or not any(d.iterdir()):
            issues.append(f"{name}/: missing or empty")

    return ValidationReport(ok=not issues, issues=issues)


# =============================================================================
# Orchestration
# =============================================================================


def build_replication_package(
    cfg: LoadedConfig,
    *,
    dry_run: bool = False,
    force: bool = False,
    archive: bool = True,
    validate: bool = True,
) -> dict[str, Any]:
    """Stage the current report-stage outputs into a timestamped,
    publication-grade replication snapshot.

    Beyond the original copy of ``output.paths.{manuscript,figures,
    tables,reports}`` (unchanged), this now also writes an embedded
    run manifest (``MANIFEST.json``), an automatically generated
    codebook (``CODEBOOK.md`` / ``codebook.json``), a ``README.md``,
    and a ``CHECKSUMS.sha256`` file; self-validates the result
    (:func:`validate_replication_package`); and, by default, archives
    the whole package into a deterministic zip file alongside it.

    Parameters
    ----------
    cfg
        Result of :func:`finfluencer.core.config.load_settings`.
    dry_run
        If ``True``, validate inputs and return the planned destination
        without writing anything. Return shape unchanged from before
        this update: ``{"would_export_to": Path, "sources": dict}``.
    force
        If ``True`` and the destination already exists, remove it
        first rather than raising.
    archive
        If ``True`` (default), also produce a deterministic zip archive
        of the finished package (see :func:`create_archive`).
    validate
        If ``True`` (default), self-validate the finished package
        (see :func:`validate_replication_package`) before returning,
        raising :class:`~finfluencer.core.exceptions.ReproducibilityError`
        if validation fails rather than returning a package silently
        known to be inconsistent.

    Returns
    -------
    dict[str, Any]
        If ``dry_run``: unchanged, ``{"would_export_to": Path, "sources": dict[str, str]}``.
        Otherwise: ``{"exported_to", "n_items"}`` (unchanged keys) plus
        ``"manifest_path"``, ``"codebook_path"``, ``"readme_path"``,
        ``"checksums_path"``, and, if ``validate``, ``"validation"``
        (``{"ok": bool, "issues": list[str]}``), and, if ``archive``,
        ``"archive_path"``.

    Raises
    ------
    FileNotFoundError
        Any of the four source directories does not exist or is empty.
    FileExistsError
        The destination directory already exists and ``force`` is
        ``False``.
    ~finfluencer.core.exceptions.DirtyWorkingTreeError
        ``replication.stage`` is ``submission``/``publication`` and the
        git working tree is dirty or unavailable.
    ~finfluencer.core.exceptions.ReproducibilityError
        ``validate=True`` and the freshly built package fails its own
        self-validation.
    """
    sources = _resolve_sources(cfg)
    missing = [name for name, d in sources.items() if not d.exists() or not any(d.iterdir())]
    if missing:
        raise FileNotFoundError(
            f"Cannot export: no output found for {missing}; run 'report' first.",
        )

    _gate_publication_stage(cfg)
    _warn_if_model_weights_not_wired(cfg)

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

    manifest = _build_export_manifest(cfg)
    manifest_path = dest / "MANIFEST.json"
    write_json(manifest, manifest_path)

    codebook = generate_codebook(dest)
    codebook_json_path = dest / "codebook.json"
    write_json(codebook, codebook_json_path)
    codebook_md_path = dest / "CODEBOOK.md"
    codebook_md_path.write_text(_render_codebook_markdown(codebook), encoding="utf-8")

    readme_path = dest / "README.md"
    readme_path.write_text(_render_readme(cfg, dest), encoding="utf-8")

    checksums = compute_checksums(dest)
    checksums_path = write_checksums_file(checksums, dest)

    n_items = sum(1 for f in dest.rglob("*") if f.is_file())
    result: dict[str, Any] = {
        "exported_to": dest,
        "n_items": n_items,
        "manifest_path": manifest_path,
        "codebook_path": codebook_json_path,
        "readme_path": readme_path,
        "checksums_path": checksums_path,
    }

    if validate:
        report = validate_replication_package(dest)
        result["validation"] = {"ok": report.ok, "issues": report.issues}
        if not report.ok:
            raise ReproducibilityError(
                "Replication package failed self-validation",
                issues=report.issues,
                package_dir=str(dest),
            )

    if archive:
        result["archive_path"] = create_archive(dest, fmt="zip")

    _log.info("replication_package_built", dest=str(dest), n_items=n_items)
    return result


__all__ = [
    "EXPORT_SOURCES",
    "MANIFEST_SCHEMA_VERSION",
    "ValidationReport",
    "build_replication_package",
    "generate_codebook",
    "compute_checksums",
    "write_checksums_file",
    "create_archive",
    "validate_replication_package",
]
