"""
finfluencer.reporting.main
=============================

Sprint 2.3: the Reporting CLI.

A Typer application exposing four commands over the unmodified
:func:`finfluencer.reporting.orchestrator.run_reporting_pipeline`
engine, following ``finfluencer.collect.main``'s own CLI conventions
exactly (``--settings``/``--analysts``/``--stage``/``--dry-run``/
``--verbose`` options, ``load_settings`` -> ``configure(log_dir=...)`` ->
pipeline-call sequencing, ``try/except (FileNotFoundError,
FinfluencerError)`` -> ``typer.echo(..., err=True)`` -> ``typer.Exit(1)``
error handling, ``def main(): app()`` module entry point).

Commands
--------
``analyze``
    Runs the statistical computation stages: ``master_table``,
    ``inferential`` (the first two entries of
    :data:`~finfluencer.reporting.orchestrator.STAGE_ORDER`).
``report``
    Runs the manuscript output stages: ``manuscript_data``,
    ``manuscript_figures``, ``manuscript_tables`` (the remaining three
    entries of ``STAGE_ORDER``). These three stages are mutually
    independent (none of them depend on each other's outputs -- see
    ``orchestrator._STAGE_SPECS``), so ``report --stage <name>`` may
    select any single one of them directly.
``validate``
    Non-mutating diagnostics: config validity, required-package
    importability, per-stage readiness (reusing the orchestrator's own
    ``dry_run=True`` plan across all five stages), and -- when
    ``replication.stage == "publication"`` -- git working-tree
    cleanliness. Never executes a stage or writes a run manifest.
``export``
    Stages the current ``report``-stage outputs (manuscript, figures,
    tables, reports) into a timestamped snapshot under
    ``output.paths.replication``. The packaging logic itself lives in
    :func:`finfluencer.reporting.replication.build_replication_package`
    (Sprint 2.5, extracted unchanged from this module's own Sprint 2.3
    inline implementation) -- this command is now a thin dispatcher:
    parse options, load config, call that function, format the
    result. True archival/versioning/Zenodo deposition logic remains
    out of scope for both modules (see ``replication.py``'s own
    docstring).

Command-group "all" vs. the orchestrator's "all"
--------------------------------------------------
:func:`run_reporting_pipeline`'s own ``stage="all"`` means "every one
of the five stages". ``analyze --stage all`` and ``report --stage
all`` are a *different*, narrower concept: "every stage in this
command's own group" (2 stages for ``analyze``, 3 for ``report``).
Since ``orchestrator.py`` is frozen and has no notion of a sub-group
"all", each selected stage is passed to :func:`run_reporting_pipeline`
in its own call, and the (already namespaced, per-stage) results and
run manifests are simply accumulated -- so ``analyze --stage all``
produces two run manifests (``reporting.master_table``,
``reporting.inferential``), not one combined
``reporting.analyze`` manifest. This is a deliberate scope adaptation,
not an oversight: it keeps ``orchestrator.py`` unmodified while still
giving each stage its own precise, independently-auditable
provenance record.

Not implemented here
---------------------
* :class:`AnalysisJob` (deferred to Sprint 2.6, per ADR-Sprint2-01).
* Mounting these commands onto the root ``finfluencer`` CLI
  (``cli.py``, deferred to Sprint 2.4) -- ``finfluencer run`` is
  untouched and this module is not yet wired into it.
* ``cancel_event`` as a CLI flag -- cooperative cancellation is a
  GUI-facing concern (Sprint 2.6); the CLI's required option surface
  per Sprint 2.3 is ``--settings``/``--dry-run``/``--force``/
  ``--verbose``/``--json`` only.

Usage
-----
    python -m finfluencer.reporting.main analyze
    python -m finfluencer.reporting.main analyze --stage inferential --force
    python -m finfluencer.reporting.main report --dry-run
    python -m finfluencer.reporting.main validate --json
    python -m finfluencer.reporting.main export
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import typer

from finfluencer.core.config import LoadedConfig, load_settings
from finfluencer.core.contracts import ReplicationStage
from finfluencer.core.exceptions import FinfluencerError
from finfluencer.core.logging import configure, get_logger
from finfluencer.core.reproducibility import get_git_state
from finfluencer.reporting.orchestrator import STAGE_ORDER, run_reporting_pipeline
from finfluencer.reporting.replication import build_replication_package

_log = get_logger(__name__)

app = typer.Typer(add_completion=False, help="Finfluencer reporting CLI.")

#: The two statistical-computation stages, in dependency order.
_ANALYZE_STAGES: tuple[str, ...] = STAGE_ORDER[:2]
#: The three manuscript-output stages (mutually independent siblings).
_REPORT_STAGES: tuple[str, ...] = STAGE_ORDER[2:]

#: Import names (not pip/dist names) of every package the reporting
#: pipeline needs. Checked directly with ``importlib.util.find_spec``
#: rather than importing (side-effect-free) -- this is precisely the
#: failure class the pymannkendall/scikit-posthocs incident fell into:
#: a package declared and installed somewhere, but not importable in
#: the interpreter actually running the CLI. Deliberately independent
#: of ``core.reproducibility``'s own provenance package list rather
#: than extending it, since that is shared core infrastructure outside
#: this module's Sprint 2.3 scope.
_REQUIRED_PACKAGES: tuple[str, ...] = (
    "pandas", "numpy", "scipy", "statsmodels", "openpyxl", "matplotlib",
    "pymannkendall", "scikit_posthocs",
)


# =============================================================================
# Shared helpers
# =============================================================================


def _configure_logging(cfg: LoadedConfig, *, verbose: bool) -> None:
    log_dir = Path(str(cfg.settings.output.paths.logs))
    log_dir.mkdir(parents=True, exist_ok=True)
    configure(log_dir=log_dir, verbose=verbose)


def _run_stage_group(
    stage_names: tuple[str, ...],
    *,
    stage: str,
    settings: Path,
    analysts: Path,
    force: bool,
    dry_run: bool,
    verbose: bool,
) -> dict[str, Any]:
    """Validate ``stage`` against ``stage_names`` (this command's own
    group, plus ``"all"``), then call
    :func:`run_reporting_pipeline` once per selected stage, merging the
    per-call results into one flat ``dict``. See the module docstring
    for why this loop -- not a single ``stage="all"`` call -- is
    correct here."""
    valid = (*stage_names, "all")
    if stage not in valid:
        typer.echo(f"Error: --stage must be one of {valid}, got {stage!r}", err=True)
        raise typer.Exit(code=2)
    selected = stage_names if stage == "all" else (stage,)

    try:
        cfg = load_settings(settings, analysts)
        _configure_logging(cfg, verbose=verbose)

        combined: dict[str, Any] = {}
        for name in selected:
            combined.update(run_reporting_pipeline(cfg, stage=name, dry_run=dry_run, force=force))
        return combined
    except (FileNotFoundError, FinfluencerError, ValueError) as e:
        typer.echo(f"Pipeline aborted: {e}", err=True)
        raise typer.Exit(code=1) from e


def _echo_result(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps(payload, indent=2, default=str))
        return
    for name, value in payload.items():
        if isinstance(value, list):
            typer.echo(f"{name}: {len(value)} file(s)")
            for item in value:
                typer.echo(f"  - {item}")
        else:
            typer.echo(f"{name}: {value}")


# =============================================================================
# analyze / report
# =============================================================================


@app.command()
def analyze(
    settings: Path = typer.Option(
        Path("config/settings.yaml"), "--settings", "-s", help="Path to settings.yaml",
    ),
    analysts: Path = typer.Option(
        Path("config/analysts.yaml"), "--analysts", "-a", help="Path to analysts.yaml",
    ),
    stage: str = typer.Option(
        "all", "--stage", help=f"Stage to run: one of {(*_ANALYZE_STAGES, 'all')}",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Report what would run without executing anything",
    ),
    force: bool = typer.Option(
        False, "--force", help="Ignore checkpoint state and re-run even if inputs are unchanged",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Human-readable console logging (default: JSON to stderr)",
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Print machine-readable JSON instead of human-readable text",
    ),
) -> None:
    """Run the statistical computation stages: master_table, inferential."""
    result = _run_stage_group(
        _ANALYZE_STAGES, stage=stage, settings=settings, analysts=analysts,
        force=force, dry_run=dry_run, verbose=verbose,
    )
    _echo_result(result, json_output=json_output)


@app.command()
def report(
    settings: Path = typer.Option(
        Path("config/settings.yaml"), "--settings", "-s", help="Path to settings.yaml",
    ),
    analysts: Path = typer.Option(
        Path("config/analysts.yaml"), "--analysts", "-a", help="Path to analysts.yaml",
    ),
    stage: str = typer.Option(
        "all", "--stage", help=f"Stage to run: one of {(*_REPORT_STAGES, 'all')}",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Report what would run without executing anything",
    ),
    force: bool = typer.Option(
        False, "--force", help="Ignore checkpoint state and re-run even if inputs are unchanged",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Human-readable console logging (default: JSON to stderr)",
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Print machine-readable JSON instead of human-readable text",
    ),
) -> None:
    """Run the manuscript output stages: manuscript_data, manuscript_figures, manuscript_tables."""
    result = _run_stage_group(
        _REPORT_STAGES, stage=stage, settings=settings, analysts=analysts,
        force=force, dry_run=dry_run, verbose=verbose,
    )
    _echo_result(result, json_output=json_output)


# =============================================================================
# validate
# =============================================================================


def _check_required_packages() -> list[str]:
    return [name for name in _REQUIRED_PACKAGES if importlib.util.find_spec(name) is None]


@app.command()
def validate(
    settings: Path = typer.Option(
        Path("config/settings.yaml"), "--settings", "-s", help="Path to settings.yaml",
    ),
    analysts: Path = typer.Option(
        Path("config/analysts.yaml"), "--analysts", "-a", help="Path to analysts.yaml",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Accepted for CLI consistency; validate never executes a stage regardless of this flag",
    ),
    force: bool = typer.Option(
        False, "--force",
        help="Accepted for CLI consistency; validate never executes a stage regardless of this flag",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Human-readable console logging (default: JSON to stderr)",
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Print machine-readable JSON instead of human-readable text",
    ),
) -> None:
    """Check config validity, required-package availability, per-stage
    readiness, and (publication stage only) git working-tree
    cleanliness -- without executing or modifying anything.

    Exit code reflects genuine problems only (invalid config, missing
    packages, a dirty tree when ``replication.stage == "publication"``
    requires a clean one) -- stages reported as "blocked" because their
    inputs have not been produced yet are informational, not failures.
    """
    try:
        cfg = load_settings(settings, analysts)
    except (FileNotFoundError, FinfluencerError) as e:
        if json_output:
            typer.echo(json.dumps({"config_valid": False, "error": str(e)}, indent=2))
        else:
            typer.echo(f"Config invalid: {e}", err=True)
        raise typer.Exit(code=1) from e

    _configure_logging(cfg, verbose=verbose)

    missing_packages = _check_required_packages()
    stage_plan = run_reporting_pipeline(cfg, stage="all", dry_run=True)

    git_state = get_git_state()
    publication_stage = cfg.settings.replication.stage == ReplicationStage.publication
    git_clean = bool(git_state.get("available")) and not git_state.get("dirty", True)

    ok = not missing_packages and (not publication_stage or git_clean)

    report_dict: dict[str, Any] = {
        "config_valid": True,
        "missing_packages": missing_packages,
        "stage_plan": stage_plan,
        "git_available": git_state.get("available"),
        "git_dirty": git_state.get("dirty"),
        "publication_stage": publication_stage,
        "ok": ok,
    }

    if json_output:
        typer.echo(json.dumps(report_dict, indent=2, default=str))
    else:
        typer.echo(f"Config: valid ({settings})")
        if missing_packages:
            typer.echo(f"Missing packages: {', '.join(missing_packages)}")
        else:
            typer.echo("Required packages: all importable")
        typer.echo("Stage plan:")
        for name, status in stage_plan.items():
            typer.echo(f"  {name}: {status}")
        if publication_stage:
            typer.echo(
                f"Git working tree: {'clean' if git_clean else 'dirty or unavailable'} "
                f"(required -- replication.stage=publication)",
            )
        typer.echo(f"Overall: {'OK' if ok else 'ISSUES FOUND'}")

    raise typer.Exit(code=0 if ok else 1)


# =============================================================================
# export
# =============================================================================
#
# Business logic lives in finfluencer.reporting.replication
# (build_replication_package) -- this command is a thin dispatcher:
# parse options, load config, call it, format the result. See that
# module's docstring for the packaging logic itself.


@app.command()
def export(
    settings: Path = typer.Option(
        Path("config/settings.yaml"), "--settings", "-s", help="Path to settings.yaml",
    ),
    analysts: Path = typer.Option(
        Path("config/analysts.yaml"), "--analysts", "-a", help="Path to analysts.yaml",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Report what would be exported without copying anything",
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite the destination directory if it already exists",
    ),
    no_archive: bool = typer.Option(
        False, "--no-archive", help="Skip building the deterministic zip archive of the package",
    ),
    no_validate: bool = typer.Option(
        False, "--no-validate", help="Skip self-validating the package after it is built",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Human-readable console logging (default: JSON to stderr)",
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Print machine-readable JSON instead of human-readable text",
    ),
) -> None:
    """Stage the report-stage outputs (manuscript, figures, tables,
    reports) into a timestamped, publication-grade replication package
    (embedded manifest, codebook, README, checksums, zip archive)
    under output.paths.replication."""
    try:
        cfg = load_settings(settings, analysts)
        _configure_logging(cfg, verbose=verbose)
        result = build_replication_package(
            cfg, dry_run=dry_run, force=force, archive=not no_archive, validate=not no_validate,
        )
    except (OSError, FinfluencerError) as e:
        typer.echo(f"Export aborted: {e}", err=True)
        raise typer.Exit(code=1) from e

    if json_output:
        typer.echo(json.dumps(result, indent=2, default=str))
    else:
        for key, value in result.items():
            typer.echo(f"{key}: {value}")


def main() -> None:
    """Module entry point (``python -m finfluencer.reporting.main``)."""
    app()


if __name__ == "__main__":
    main()
