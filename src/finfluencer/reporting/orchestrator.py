"""
finfluencer.reporting.orchestrator
=====================================

Sprint 2.1: the reporting pipeline's functional orchestration engine.

Coordinates the five Sprint 1 reporting modules -- :mod:`master_table`,
:mod:`inferential`, :mod:`manuscript_data`, :mod:`manuscript_figures`,
:mod:`manuscript_tables` -- in their proven dependency order, reusing
the platform's existing collection-pipeline infrastructure exactly as
:func:`finfluencer.collect.main.run_pipeline` already does for the
4-stage collection pipeline (Sprint 2 architecture proposal, approved):

* :class:`finfluencer.core.checkpoint.CheckpointManager` for
  skip-if-unchanged and resume-after-failure (Tier-2 ``.done`` markers).
* :mod:`finfluencer.core.reproducibility` for the run-manifest system
  (Architecture v1.0 SS10): ``RunStatus`` written ``RUNNING`` before any
  stage executes, then updated in place to ``SUCCESS``/``FAILED``.
* :mod:`finfluencer.core.logging` structured event names
  (``stage_start``/``stage_done``/``stage_skipped``/``pipeline_complete``),
  matching ``collect.main``'s own vocabulary exactly.
* :func:`finfluencer.core.config.load_settings`'s ``Settings.output.paths``
  for every input/output location -- no new configuration surface is
  introduced (Sprint 2 architecture SS3).

This module contains ONLY orchestration. It performs zero statistical
computation of its own: every ``build_*``/``run_*``/``save_*`` call
below invokes an unmodified Sprint 1 public function exactly as
documented in that module's own docstring. Per ADR-Sprint2-01,
:class:`AnalysisJob` (the stateful GUI-facing wrapper) is explicitly
deferred to Sprint 2.6 -- this module exposes only the pure functional
engine, :func:`run_reporting_pipeline`.

Why ``config_slice`` is built from input-file hashes, not ``Settings``
------------------------------------------------------------------------
:class:`~finfluencer.core.checkpoint.CheckpointManager` invalidates a
stage's ``.done`` marker when a config-slice hash changes. Sprint 1's
five reporting modules are pure functions of their *input file
contents* -- none of them accept a ``Settings`` object at all, only
explicit ``Path`` keyword arguments (a deliberate Sprint 1 design
choice, preserved here unmodified). The correct signal for "should this
stage re-run" is therefore the SHA-256 of each of the stage's declared
dependency files (:func:`finfluencer.utils.hashing.hash_file`), not a
``Settings`` sub-section -- if an upstream Parquet/CSV/JSON changes on
disk without any ``settings.yaml`` edit, the stage must still be
recognised as stale.

Stage <-> output-directory mapping
------------------------------------
Every output location is read from ``Settings.output.paths``, all of
which already exist in the schema (no new fields added):

=====================  =========================================  ==============================
Stage                  Output(s)                                  ``output.paths`` field
=====================  =========================================  ==============================
``master_table``       ``master_table.csv``                        ``data_processed``
``inferential``        ``inferential_results.json`` + 4 side CSVs  ``reports``
``manuscript_data``    3 manuscript CSVs                           ``manuscript``
``manuscript_figures`` 12 figure files (S1-S6, PNG+SVG)             ``figures``
``manuscript_tables``  1 ``.xlsx`` workbook                        ``tables``
=====================  =========================================  ==============================

The workbook filename is derived from ``Settings.study.name`` (e.g.
``"finfluencer_tr_2025"`` -> ``finfluencer_tr_2025_inferential_stats.xlsx``,
byte-identical to Sprint 1's own hardcoded default for the shipped
``config/settings.yaml``) rather than hardcoded, since ``study.name``
already exists in the schema specifically to parameterise output
filenames (see its own docstring in ``config/settings.yaml``).

Cancellation
------------
Cancellation is cooperative and stage-boundary-only: Sprint 1's
functions are not modified to accept a cancellation hook, so
``cancel_event`` is checked once before each stage begins, never
mid-stage. A set event raises :class:`PipelineCancelledError` (a new,
minimal :class:`~finfluencer.core.exceptions.FinfluencerError`
subclass, defined here rather than in ``core.exceptions`` since it is
specific to this orchestration layer) and the run manifest is written
as ``FAILED`` with ``extras["cancelled"] = True``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.config import LoadedConfig
from finfluencer.core.exceptions import FinfluencerError
from finfluencer.core.logging import get_logger
from finfluencer.core.reproducibility import (
    RunStatus,
    build_provenance,
    generate_run_id,
    write_provenance,
)
from finfluencer.utils.hashing import hash_file

from finfluencer.reporting.inferential import (
    load_master_table,
    run_all_inferential_tests,
    save_inferential_results,
)
from finfluencer.reporting.manuscript_data import (
    build_dataset_characteristics_table,
    build_sentiment_by_analyst_figure_data,
    build_topic_volcano_figure_data,
    save_dataset_characteristics_table,
    save_sentiment_by_analyst_figure_data,
    save_topic_volcano_figure_data,
)
from finfluencer.reporting.manuscript_figures import build_all_manuscript_figures
from finfluencer.reporting.manuscript_tables import (
    build_inferential_stats_workbook,
    save_inferential_stats_workbook,
)
from finfluencer.reporting.master_table import build_master_table, save_master_table

_log = get_logger(__name__)


class PipelineCancelledError(FinfluencerError):
    """Raised when ``cancel_event`` is set before a stage would start."""


#: Dependency order. "all" is accepted by :func:`run_reporting_pipeline`
#: as shorthand for "every stage below, in this order" -- matching
#: ``collect.main``'s own ``_VALID_STAGES`` convention.
STAGE_ORDER: tuple[str, ...] = (
    "master_table", "inferential", "manuscript_data", "manuscript_figures", "manuscript_tables",
)
VALID_STAGES: tuple[str, ...] = (*STAGE_ORDER, "all")


# =============================================================================
# Path resolution -- Settings.output.paths -> concrete file locations
# =============================================================================


@dataclass(frozen=True)
class _ReportingPaths:
    """Every input/output path a reporting stage needs, resolved once
    per :func:`run_reporting_pipeline` call from ``cfg.settings``."""

    comments: Path
    videos: Path
    topics: Path
    sentiment: Path
    master_table: Path
    reports_dir: Path
    manuscript_dir: Path
    figures_dir: Path
    tables_dir: Path
    inferential_results: Path
    topic_level_results: Path
    dunn_posthoc_matrix: Path
    weekly_sentiment_by_analyst: Path
    video_level_results: Path
    workbook_path: Path


def _resolve_paths(cfg: LoadedConfig) -> _ReportingPaths:
    paths = cfg.settings.output.paths
    data_raw = Path(str(paths.data_raw))
    data_processed = Path(str(paths.data_processed))
    reports_dir = Path(str(paths.reports))
    manuscript_dir = Path(str(paths.manuscript))
    figures_dir = Path(str(paths.figures))
    tables_dir = Path(str(paths.tables))

    return _ReportingPaths(
        comments=data_raw / "comments.parquet",
        videos=data_raw / "videos.parquet",
        topics=data_processed / "topics.parquet",
        sentiment=data_processed / "sentiment.parquet",
        master_table=data_processed / "master_table.csv",
        reports_dir=reports_dir,
        manuscript_dir=manuscript_dir,
        figures_dir=figures_dir,
        tables_dir=tables_dir,
        inferential_results=reports_dir / "inferential_results.json",
        topic_level_results=reports_dir / "topic_level_test_results.csv",
        dunn_posthoc_matrix=reports_dir / "dunn_posthoc_matrix.csv",
        weekly_sentiment_by_analyst=reports_dir / "weekly_sentiment_by_analyst.csv",
        video_level_results=reports_dir / "video_level_volume_sentiment.csv",
        workbook_path=tables_dir / f"{cfg.settings.study.name}_inferential_stats.xlsx",
    )


def _build_checkpoint_manager(cfg: LoadedConfig) -> CheckpointManager:
    """Matches ``collect.main.build_checkpoint_manager`` exactly, defined
    locally rather than imported so ``finfluencer.reporting`` does not
    depend on ``finfluencer.collect``."""
    return CheckpointManager(
        checkpoint_root=cfg.settings.output.paths.checkpoints,
        cache_root=cfg.settings.output.paths.cache,
    )


# =============================================================================
# Stage specifications -- table-driven, one row per Sprint 1 module
# =============================================================================


@dataclass(frozen=True)
class _StageSpec:
    """One reporting stage's coordination metadata.

    ``dependencies``/``outputs``/``execute`` are pure functions of
    :class:`_ReportingPaths` only -- no stage-specific control flow
    lives outside this table, so :func:`_execute_stage` (the single
    generic runner below) is the only place skip/force/manifest/
    logging/progress logic is implemented, once, for all five stages.
    """

    name: str
    dependencies: Callable[[_ReportingPaths], list[Path]]
    outputs: Callable[[_ReportingPaths], list[Path]]
    execute: Callable[[_ReportingPaths], list[Path]]


def _master_table_execute(p: _ReportingPaths) -> list[Path]:
    df = build_master_table(comments_path=p.comments, topics_path=p.topics, sentiment_path=p.sentiment)
    save_master_table(df, output_path=p.master_table)
    return [p.master_table]


def _inferential_outputs(p: _ReportingPaths) -> list[Path]:
    return [
        p.inferential_results, p.topic_level_results, p.dunn_posthoc_matrix,
        p.weekly_sentiment_by_analyst, p.video_level_results,
    ]


def _inferential_execute(p: _ReportingPaths) -> list[Path]:
    df = load_master_table(path=p.master_table)
    results = run_all_inferential_tests(df)
    save_inferential_results(results, output_dir=p.reports_dir)
    return _inferential_outputs(p)


def _manuscript_data_outputs(p: _ReportingPaths) -> list[Path]:
    return [
        p.manuscript_dir / "manuscript_table1.csv",
        p.manuscript_dir / "manuscript_fig1_data.csv",
        p.manuscript_dir / "manuscript_fig3_data.csv",
    ]


def _manuscript_data_execute(p: _ReportingPaths) -> list[Path]:
    table1_path, fig1_path, fig3_path = _manuscript_data_outputs(p)

    table1 = build_dataset_characteristics_table(videos_path=p.videos, comments_path=p.comments)
    save_dataset_characteristics_table(table1, output_path=table1_path)

    fig1 = build_sentiment_by_analyst_figure_data(master_table_path=p.master_table)
    save_sentiment_by_analyst_figure_data(fig1, output_path=fig1_path)

    fig3 = build_topic_volcano_figure_data(inferential_results_path=p.inferential_results)
    save_topic_volcano_figure_data(fig3, output_path=fig3_path)

    return [table1_path, fig1_path, fig3_path]


def _manuscript_figures_outputs(p: _ReportingPaths) -> list[Path]:
    """Used only for skip/dry-run reporting (when the stage does NOT
    execute). Globs rather than hardcodes the 12 filenames so this
    function never needs updating if Sprint 1B.2 ever adds a figure."""
    if not p.figures_dir.exists():
        return []
    return sorted(p.figures_dir.glob("*.png")) + sorted(p.figures_dir.glob("*.svg"))


def _manuscript_figures_execute(p: _ReportingPaths) -> list[Path]:
    return build_all_manuscript_figures(
        master_table_path=p.master_table,
        inferential_results_path=p.inferential_results,
        topic_level_results_path=p.topic_level_results,
        video_level_results_path=p.video_level_results,
        weekly_sentiment_by_analyst_path=p.weekly_sentiment_by_analyst,
        output_dir=p.figures_dir,
    )


def _manuscript_tables_execute(p: _ReportingPaths) -> list[Path]:
    wb = build_inferential_stats_workbook(
        inferential_results_path=p.inferential_results,
        topic_level_results_path=p.topic_level_results,
        dunn_posthoc_matrix_path=p.dunn_posthoc_matrix,
        weekly_sentiment_by_analyst_path=p.weekly_sentiment_by_analyst,
    )
    save_inferential_stats_workbook(wb, output_path=p.workbook_path)
    return [p.workbook_path]


_STAGE_SPECS: dict[str, _StageSpec] = {
    "master_table": _StageSpec(
        name="master_table",
        dependencies=lambda p: [p.comments, p.topics, p.sentiment],
        outputs=lambda p: [p.master_table],
        execute=_master_table_execute,
    ),
    "inferential": _StageSpec(
        name="inferential",
        dependencies=lambda p: [p.master_table],
        outputs=_inferential_outputs,
        execute=_inferential_execute,
    ),
    "manuscript_data": _StageSpec(
        name="manuscript_data",
        dependencies=lambda p: [p.videos, p.comments, p.master_table, p.inferential_results],
        outputs=_manuscript_data_outputs,
        execute=_manuscript_data_execute,
    ),
    "manuscript_figures": _StageSpec(
        name="manuscript_figures",
        dependencies=lambda p: [
            p.master_table, p.inferential_results, p.topic_level_results,
            p.video_level_results, p.weekly_sentiment_by_analyst,
        ],
        outputs=_manuscript_figures_outputs,
        execute=_manuscript_figures_execute,
    ),
    "manuscript_tables": _StageSpec(
        name="manuscript_tables",
        dependencies=lambda p: [
            p.inferential_results, p.topic_level_results,
            p.dunn_posthoc_matrix, p.weekly_sentiment_by_analyst,
        ],
        outputs=lambda p: [p.workbook_path],
        execute=_manuscript_tables_execute,
    ),
}


# =============================================================================
# Generic stage execution
# =============================================================================


def _checkpoint_name(stage: str) -> str:
    """Namespaced so a shared ``checkpoint_root`` never collides with
    ``finfluencer.collect.main``'s own stage markers (e.g. a stage
    literally named ``"topics"`` exists on both sides)."""
    return f"reporting_{stage}"


def _config_slice(spec: _StageSpec, paths: _ReportingPaths) -> dict[str, str]:
    """SHA-256 of every declared dependency file -- see module docstring
    for why this, not a ``Settings`` slice, is the correct staleness
    signal for these Settings-agnostic, pure Sprint 1 functions."""
    return {str(dep): hash_file(dep) for dep in spec.dependencies(paths)}


def _check_dependencies(spec: _StageSpec, paths: _ReportingPaths) -> None:
    missing = [dep for dep in spec.dependencies(paths) if not dep.exists()]
    if missing:
        raise FileNotFoundError(
            f"reporting stage {spec.name!r} is missing required input(s): "
            f"{[str(m) for m in missing]}; run the stage(s) that produce them first."
        )


def _check_cancelled(cancel_event: threading.Event | None, stage: str) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise PipelineCancelledError(
            f"Pipeline cancelled before stage {stage!r} started.", stage=stage,
        )


def _emit_progress(
    on_progress: Callable[[str, str], None] | None, stage: str, event: str,
) -> None:
    """Never lets a caller-supplied callback's own exception break the
    pipeline -- matching ``collect.main``'s best-effort philosophy for
    anything that is not the pipeline's own core work (see
    ``_write_manifest_safe`` there)."""
    if on_progress is None:
        return
    try:
        on_progress(stage, event)
    except Exception as exc:
        # NOTE: structlog's BoundLogger methods take the log event name as
        # their own first positional argument (itself internally called
        # "event") -- a keyword argument literally named ``event`` here
        # collides with it ("got multiple values for argument 'event'").
        # Named ``progress_event`` instead to avoid the collision.
        _log.warning(
            "on_progress_callback_failed",
            stage=stage, progress_event=event, reason=type(exc).__name__,
        )


def _execute_stage(
    spec: _StageSpec,
    checkpoint: CheckpointManager,
    paths: _ReportingPaths,
    *,
    force: bool,
    on_progress: Callable[[str, str], None] | None,
    cancel_event: threading.Event | None,
) -> list[Path]:
    """Run (or skip) one stage. The only place skip/force/checkpoint/
    manifest-relevant/logging/progress logic exists for all five stages."""
    _check_cancelled(cancel_event, spec.name)
    _check_dependencies(spec, paths)

    ckpt_name = _checkpoint_name(spec.name)
    if force:
        checkpoint.invalidate(ckpt_name)

    config_slice = _config_slice(spec, paths)
    if not checkpoint.should_run(ckpt_name, config_slice):
        _log.info("stage_skipped", stage=spec.name, reason="checkpoint_up_to_date")
        _emit_progress(on_progress, spec.name, "skipped")
        return spec.outputs(paths)

    _log.info("stage_start", stage=spec.name)
    _emit_progress(on_progress, spec.name, "start")
    produced = spec.execute(paths)
    checkpoint.mark_done(ckpt_name, config_slice, extras={"n_outputs": len(produced)})
    _log.info("stage_done", stage=spec.name, n_outputs=len(produced))
    _emit_progress(on_progress, spec.name, "done")
    return produced


# =============================================================================
# Dry run
# =============================================================================


def _build_dry_run_plan(
    checkpoint: CheckpointManager,
    paths: _ReportingPaths,
    selected: tuple[str, ...],
    *,
    force: bool,
) -> dict[str, str]:
    """Introspection-only: never touches disk, never calls a Sprint 1
    function. One of ``"blocked: ..."``, ``"would_run"``,
    ``"would_run (forced)"``, or ``"up_to_date"`` per selected stage --
    the GUI-preparation "visibility before execution" requirement from
    the Sprint 2 architecture proposal (SS4)."""
    plan: dict[str, str] = {}
    for name in selected:
        spec = _STAGE_SPECS[name]
        missing = [dep for dep in spec.dependencies(paths) if not dep.exists()]
        if missing:
            plan[name] = f"blocked: missing {[str(m) for m in missing]}"
            continue
        if force:
            plan[name] = "would_run (forced)"
            continue
        config_slice = _config_slice(spec, paths)
        ckpt_name = _checkpoint_name(name)
        # has_valid_marker(), not should_run(): this function's own
        # docstring promises "never touches disk", but should_run()
        # deletes a stale marker as a side effect (ADR-P2-004 / R8).
        # has_valid_marker() answers the identical question read-only.
        plan[name] = (
            "up_to_date" if checkpoint.has_valid_marker(ckpt_name, config_slice)
            else "would_run"
        )
    return plan


# =============================================================================
# Run manifest (Architecture v1.0 SS10) -- matches collect.main exactly
# =============================================================================


def _run_manifest_path(cfg: LoadedConfig, run_id: str) -> Path:
    return Path(str(cfg.settings.output.paths.checkpoints)) / "run_manifests" / f"{run_id}.json"


def _write_manifest_safe(
    cfg: LoadedConfig,
    checkpoint: CheckpointManager,
    run_id: str,
    *,
    stage: str,
    status: RunStatus,
    error: dict[str, str] | None = None,
    extras: dict[str, Any] | None = None,
) -> None:
    """Best-effort; must never raise, must never mask the pipeline's own
    exception. Identical policy to ``collect.main._write_manifest_safe``."""
    try:
        provenance = build_provenance(
            cfg, stage=stage, run_id=run_id, status=status,
            checkpoint=checkpoint, error=error, extras=extras,
        )
        write_provenance(provenance, _run_manifest_path(cfg, run_id))
    except Exception as exc:
        _log.warning(
            "run_manifest_write_failed",
            run_id=run_id, status=status.value, reason=type(exc).__name__,
        )


# =============================================================================
# Public API
# =============================================================================


def run_reporting_pipeline(
    cfg: LoadedConfig,
    *,
    stage: str = "all",
    dry_run: bool = False,
    force: bool = False,
    on_progress: Callable[[str, str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Run one or all reporting stages, in dependency order.

    Behavior-preserving coordination of Sprint 1's five reporting
    modules -- no statistical logic lives in this function. See the
    module docstring for the full stage <-> output-directory mapping
    and the checkpoint/manifest/cancellation design.

    Parameters
    ----------
    cfg
        Result of :func:`finfluencer.core.config.load_settings`.
    stage
        One of ``"master_table"``, ``"inferential"``,
        ``"manuscript_data"``, ``"manuscript_figures"``,
        ``"manuscript_tables"``, or ``"all"`` (default). Selecting a
        single stage still validates that its dependencies exist
        first, exactly as running the full DAG does.
    dry_run
        If ``True``, resolve paths and consult the checkpoint state for
        every selected stage without executing or writing a run
        manifest. Returns ``dict[str, str]`` (a plan), not output paths
        -- see Returns below.
    force
        If ``True``, invalidate each selected stage's checkpoint marker
        before deciding whether to run it, guaranteeing re-execution
        even if its inputs are unchanged.
    on_progress
        Optional ``(stage_name, event) -> None`` callback, called for
        ``"start"``, ``"done"``, and ``"skipped"`` events. A raised
        exception inside this callback is caught and logged, never
        propagated -- see :func:`_emit_progress`.
    cancel_event
        Optional cooperative cancellation flag, checked once before
        each stage begins. If already set, :class:`PipelineCancelledError`
        is raised before that stage's dependencies are even checked.

    Returns
    -------
    dict[str, Any]
        If ``dry_run``: ``dict[str, str]`` mapping stage name to one of
        ``"blocked: ..."``/``"would_run"``/``"would_run (forced)"``/
        ``"up_to_date"``. Otherwise: ``dict[str, list[Path]]`` mapping
        stage name to the list of output files it produced (whether
        freshly built this run or already up to date and skipped).

    Raises
    ------
    ValueError
        ``stage`` is not one of the valid values.
    FileNotFoundError
        A selected stage's required input file(s) do not exist.
    PipelineCancelledError
        ``cancel_event`` was set before a selected stage began.

    Run manifest
    ------------
    Every non-dry-run invocation writes a run manifest (Architecture
    v1.0 SS10) to ``<checkpoints>/run_manifests/<run_id>.json``, with
    ``stage`` recorded as ``f"reporting.{stage}"`` (namespaced against
    ``finfluencer.collect.main``'s manifests, which share the same
    directory but use undotted stage names).
    """
    if stage not in VALID_STAGES:
        raise ValueError(f"stage must be one of {VALID_STAGES}, got {stage!r}")

    paths = _resolve_paths(cfg)
    checkpoint = _build_checkpoint_manager(cfg)
    selected = STAGE_ORDER if stage == "all" else (stage,)
    manifest_stage = f"reporting.{stage}"

    if dry_run:
        plan = _build_dry_run_plan(checkpoint, paths, selected, force=force)
        _log.info("dry_run_plan", plan=plan)
        return plan

    run_id = generate_run_id()
    _write_manifest_safe(cfg, checkpoint, run_id, stage=manifest_stage, status=RunStatus.running)

    results: dict[str, list[Path]] = {}
    try:
        for name in selected:
            spec = _STAGE_SPECS[name]
            results[name] = _execute_stage(
                spec, checkpoint, paths,
                force=force, on_progress=on_progress, cancel_event=cancel_event,
            )
        _log.info("pipeline_complete", stages_run=list(results.keys()))
    except PipelineCancelledError as exc:
        _write_manifest_safe(
            cfg, checkpoint, run_id, stage=manifest_stage, status=RunStatus.failed,
            error={"type": type(exc).__name__, "message": str(exc)},
            extras={"stages_run": list(results.keys()), "cancelled": True},
        )
        raise
    except Exception as exc:
        _write_manifest_safe(
            cfg, checkpoint, run_id, stage=manifest_stage, status=RunStatus.failed,
            error={"type": type(exc).__name__, "message": str(exc)},
            extras={"stages_run": list(results.keys())},
        )
        raise

    _write_manifest_safe(
        cfg, checkpoint, run_id, stage=manifest_stage, status=RunStatus.success,
        extras={"stages_run": list(results.keys())},
    )
    return results


__all__ = [
    "run_reporting_pipeline",
    "PipelineCancelledError",
    "STAGE_ORDER",
    "VALID_STAGES",
]
