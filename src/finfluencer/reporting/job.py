"""
finfluencer.reporting.job
============================

Sprint 2.6: the GUI-facing orchestration adapter decided in
ADR-Sprint2-01 -- a lightweight, stateful wrapper over the pure
functional engine (:func:`finfluencer.reporting.orchestrator.run_reporting_pipeline`),
never a reimplementation of it.

ADR-Sprint2-01 recap
----------------------
The hybrid API decision: ``run_reporting_pipeline()`` stays the
canonical pure-function engine (used directly by the CLI and by every
Sprint 1/2.1 test, unchanged); :class:`AnalysisJob` composes over it
rather than duplicating any of its orchestration logic, modeled after
the existing :class:`~finfluencer.core.checkpoint.CheckpointManager`
(stateful) vs. :func:`~finfluencer.core.reproducibility.build_provenance`
(pure) coexistence pattern already in the codebase.

What this module is
---------------------
A **state-management layer only**. :class:`AnalysisJob`:

* delegates execution exclusively to a single call of
  :func:`run_reporting_pipeline` -- it never calls
  :mod:`~finfluencer.reporting.master_table`,
  :mod:`~finfluencer.reporting.inferential`,
  :mod:`~finfluencer.reporting.manuscript_data`,
  :mod:`~finfluencer.reporting.manuscript_figures`, or
  :mod:`~finfluencer.reporting.manuscript_tables` directly, and
  contains no statistical logic of its own;
* runs that call on a background daemon thread by default (so a GUI
  event loop is never blocked), while exposing thread-safe
  ``status``/``current_stage``/``progress``/``outputs`` snapshots a UI
  can poll at any time;
* turns the orchestrator's ``on_progress`` callback and cooperative
  ``cancel_event`` (both already part of ``run_reporting_pipeline``'s
  contract, unchanged) into a structured, timestamped event timeline
  and a simple ``cancel()`` method.

One job, one stage selector, one call
----------------------------------------
Each :class:`AnalysisJob` wraps exactly **one** call to
``run_reporting_pipeline`` with the ``stage`` value given at
construction -- any single stage name from
:data:`~finfluencer.reporting.orchestrator.STAGE_ORDER`, or ``"all"``
for every stage. This is deliberately *not* the CLI's ``analyze``/
``report`` stage-grouping convention (:mod:`finfluencer.reporting.main`,
which loops over a stage subset across multiple
``run_reporting_pipeline`` calls) -- ``AnalysisJob`` is a lower-level
adapter a GUI can use however it wants (one job per stage, or one job
for the whole pipeline), and one job maps onto exactly one underlying
manifest-producing pipeline invocation.

``run_id`` is the job's own external identifier
--------------------------------------------------
``run_reporting_pipeline`` generates its own internal run ID for its
manifest filename but does not return it to the caller (and
``orchestrator.py`` is frozen, so this cannot be changed). Each
``AnalysisJob`` therefore generates its **own** run ID at construction
time via :func:`finfluencer.core.reproducibility.generate_run_id` --
the same generator the orchestrator itself uses -- as a stable,
job-local correlation identifier for GUI/timeline purposes. It is not
guaranteed to equal the orchestrator's own internal manifest run ID
for the same execution; nothing in this module reads or depends on
that internal ID.

Not implemented here
---------------------
* Any statistical or file-I/O logic (all of that stays inside the
  Sprint 1 modules and the orchestrator, both unmodified).
* Persistence across process restarts -- an ``AnalysisJob`` is an
  in-memory handle to one in-process execution, not a durable job
  queue (the on-disk run manifest system already covers durable,
  cross-process history).
* Any CLI or GUI code itself -- this is the adapter layer beneath
  such code, not the code.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from finfluencer.core.config import LoadedConfig
from finfluencer.core.logging import get_logger
from finfluencer.core.reproducibility import generate_run_id
from finfluencer.reporting.orchestrator import (
    STAGE_ORDER,
    PipelineCancelledError,
    run_reporting_pipeline,
)
from finfluencer.utils.time import format_iso8601, now_utc

_log = get_logger(__name__)


class JobStatus(str, Enum):
    """Lifecycle status of one :class:`AnalysisJob`.

    ``pending`` -> ``running`` -> exactly one of ``success``/
    ``failed``/``cancelled``. Never transitions backward; ``start()``
    raises if called when not ``pending``.
    """

    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


#: Terminal statuses -- once in one of these, a job never changes state again.
_TERMINAL_STATUSES = frozenset({JobStatus.success, JobStatus.failed, JobStatus.cancelled})


@dataclass(frozen=True)
class JobEvent:
    """One entry in a job's structured event timeline.

    ``stage`` is ``None`` for job-level events (``job_created``,
    ``job_started``, ``job_succeeded``, ``job_failed``,
    ``job_cancelled``, ``cancel_requested``) and the stage name for
    stage-level events forwarded from the orchestrator's own
    ``on_progress`` callback (``start``/``done``/``skipped``).
    """

    timestamp: str
    stage: str | None
    event: str
    detail: str | None = None


def _json_safe(value: Any) -> Any:
    """Recursively convert ``Path`` objects to strings so a job's
    ``outputs``/``summary()`` can be passed to ``json.dumps`` directly,
    without requiring callers to remember ``default=str`` themselves."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


class AnalysisJob:
    """Stateful, GUI-facing wrapper around one
    :func:`~finfluencer.reporting.orchestrator.run_reporting_pipeline`
    call. See the module docstring for the full design rationale.
    """

    def __init__(
        self,
        cfg: LoadedConfig,
        *,
        stage: str = "all",
        dry_run: bool = False,
        force: bool = False,
        on_progress: Callable[[str, str], None] | None = None,
    ) -> None:
        self._cfg = cfg
        self._stage = stage
        self._dry_run = dry_run
        self._force = force
        self._external_on_progress = on_progress

        self.run_id: str = generate_run_id()

        self._lock = threading.RLock()
        self._status: JobStatus = JobStatus.pending
        self._current_stage: str | None = None
        self._outputs: dict[str, Any] = {}
        self._error: dict[str, str] | None = None
        self._stages_completed: set[str] = set()
        self._timeline: list[JobEvent] = []
        self._cancel_event = threading.Event()
        self._thread: threading.Thread | None = None

        self._selected_stages: tuple[str, ...] = STAGE_ORDER if stage == "all" else (stage,)

        self._metadata: dict[str, Any] = {
            "study_name": cfg.settings.study.name,
            "study_version": cfg.settings.study.version,
            "stage": stage,
            "dry_run": dry_run,
            "force": force,
            "created_at": format_iso8601(now_utc()),
            "started_at": None,
            "finished_at": None,
        }

        self._record_event(stage=None, event="job_created")

    def __repr__(self) -> str:  # pragma: no cover - debugging convenience only
        return (
            f"AnalysisJob(run_id={self.run_id!r}, stage={self._stage!r}, "
            f"status={self.status.value!r}, progress={self.progress:.2f})"
        )

    # =========================================================================
    # Read-only state -- thread-safe snapshots
    # =========================================================================

    @property
    def status(self) -> JobStatus:
        with self._lock:
            return self._status

    @property
    def current_stage(self) -> str | None:
        with self._lock:
            return self._current_stage

    @property
    def outputs(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._outputs)

    @property
    def error(self) -> dict[str, str] | None:
        with self._lock:
            return dict(self._error) if self._error is not None else None

    @property
    def timeline(self) -> list[JobEvent]:
        with self._lock:
            return list(self._timeline)

    @property
    def metadata(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._metadata)

    @property
    def is_finished(self) -> bool:
        return self.status in _TERMINAL_STATUSES

    @property
    def progress(self) -> float:
        """Fraction of the job's selected stage(s) completed, in
        ``[0.0, 1.0]``.

        A stage counts as completed when the orchestrator's own
        ``on_progress`` callback reports ``"done"`` or ``"skipped"``
        for it. Dry-run jobs never receive any ``on_progress`` calls
        at all (the orchestrator's ``dry_run`` mode returns a plan
        without touching any stage), so ``progress`` is forced to
        ``1.0`` on ``success`` regardless -- a successfully completed
        dry run has, by definition, finished the work it was asked to
        do. For ``failed``/``cancelled`` jobs, the fraction reflects
        real partial progress at the point of failure/cancellation.
        """
        with self._lock:
            if self._status == JobStatus.success:
                return 1.0
            if not self._selected_stages:
                return 1.0
            return len(self._stages_completed) / len(self._selected_stages)

    # =========================================================================
    # Execution
    # =========================================================================

    def start(self, *, background: bool = True) -> "AnalysisJob":
        """Begin execution.

        Parameters
        ----------
        background
            If ``True`` (default), runs on a daemon thread and returns
            immediately -- the intended GUI usage, so the caller's
            event loop is never blocked. If ``False``, runs
            synchronously on the calling thread and only returns once
            the job has reached a terminal status.

        Raises
        ------
        RuntimeError
            The job has already been started (status is not
            ``pending``) -- a job may only be started once.
        """
        with self._lock:
            if self._status != JobStatus.pending:
                raise RuntimeError(
                    f"AnalysisJob {self.run_id!r} has already been started "
                    f"(status={self._status.value!r}); a job may only be started once.",
                )
            self._status = JobStatus.running
        self._record_event(stage=None, event="job_started")

        if background:
            self._thread = threading.Thread(
                target=self._execute, daemon=True, name=f"AnalysisJob-{self.run_id}",
            )
            self._thread.start()
        else:
            self._execute()
        return self

    def join(self, timeout: float | None = None) -> None:
        """Block until a background-started job reaches a terminal
        status (or ``timeout`` elapses). A no-op if ``start()`` was
        called with ``background=False`` (already synchronous) or has
        not been called at all."""
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def cancel(self) -> None:
        """Request cooperative cancellation.

        Sets the same ``threading.Event`` passed to
        :func:`run_reporting_pipeline` as ``cancel_event`` -- checked
        by the orchestrator once before each stage begins, never
        mid-stage (see ``orchestrator.py``'s own cancellation design).
        Safe to call from any thread, at any time, including before
        ``start()`` or after the job has already finished (a no-op in
        the latter case)."""
        self._cancel_event.set()
        self._record_event(stage=self.current_stage, event="cancel_requested")

    def _execute(self) -> None:
        """Runs on the worker thread (or the caller's thread, if
        ``start(background=False)``). The only place this class calls
        ``run_reporting_pipeline`` -- exactly once, per the module
        docstring."""
        with self._lock:
            self._metadata["started_at"] = format_iso8601(now_utc())
        try:
            result = run_reporting_pipeline(
                self._cfg,
                stage=self._stage,
                dry_run=self._dry_run,
                force=self._force,
                on_progress=self._on_progress,
                cancel_event=self._cancel_event,
            )
            with self._lock:
                self._outputs = result
                self._status = JobStatus.success
            self._record_event(stage=None, event="job_succeeded")
        except PipelineCancelledError as exc:
            with self._lock:
                self._status = JobStatus.cancelled
                self._error = {"type": type(exc).__name__, "message": str(exc)}
            self._record_event(stage=self.current_stage, event="job_cancelled", detail=str(exc))
        except Exception as exc:
            # Deliberately broad: any orchestrator failure (ValueError for a bad stage, FileNotFoundError for
            # missing dependencies, or anything else) must become a
            # terminal "failed" status, never an unhandled exception on
            # the worker thread (which would otherwise be silently lost).
            with self._lock:
                self._status = JobStatus.failed
                self._error = {"type": type(exc).__name__, "message": str(exc)}
            self._record_event(stage=self.current_stage, event="job_failed", detail=str(exc))
        finally:
            with self._lock:
                self._metadata["finished_at"] = format_iso8601(now_utc())

    def _on_progress(self, stage: str, event: str) -> None:
        """Passed to ``run_reporting_pipeline`` as its ``on_progress``
        callback. Updates internal state, records a timeline entry,
        then forwards to the caller-supplied ``on_progress`` (if any)
        -- a failure in that external callback must never break the
        pipeline, matching ``orchestrator._emit_progress``'s own
        best-effort philosophy for callbacks it does not control."""
        with self._lock:
            self._current_stage = stage
            if event in ("done", "skipped"):
                self._stages_completed.add(stage)
        self._record_event(stage=stage, event=event)

        if self._external_on_progress is not None:
            try:
                self._external_on_progress(stage, event)
            except Exception as exc:
                # Matches orchestrator._emit_progress's own best-effort
                # philosophy: a failure in a caller-supplied callback must
                # never break the job's worker thread, but must not be
                # silently swallowed either.
                #
                # Deliberately WARNING, not DEBUG: a raising on_progress
                # callback signals a bug on the *caller's* (GUI) side, not
                # routine diagnostic noise -- it is worth an operator's
                # attention even though the pipeline itself is unaffected.
                # Kept at the same level as orchestrator._emit_progress's
                # identical scenario for consistency between the two
                # call-site behaviours this module deliberately mirrors.
                _log.warning(
                    "external_on_progress_callback_failed",
                    stage=stage, progress_event=event, reason=type(exc).__name__,
                )

    def _record_event(self, *, stage: str | None, event: str, detail: str | None = None) -> None:
        entry = JobEvent(timestamp=format_iso8601(now_utc()), stage=stage, event=event, detail=detail)
        with self._lock:
            self._timeline.append(entry)

    # =========================================================================
    # Summary
    # =========================================================================

    def summary(self) -> dict[str, Any]:
        """A single, JSON-serialisable snapshot of the job's full
        state -- suitable for a GUI status panel or an API response
        (``json.dumps(job.summary())`` works with no extra arguments;
        every ``Path`` is already converted to ``str``)."""
        with self._lock:
            return {
                "run_id": self.run_id,
                "status": self._status.value,
                "stage": self._stage,
                "current_stage": self._current_stage,
                "progress": self.progress,
                "outputs": _json_safe(self._outputs),
                "error": dict(self._error) if self._error is not None else None,
                "metadata": dict(self._metadata),
                "timeline": [
                    {"timestamp": e.timestamp, "stage": e.stage, "event": e.event, "detail": e.detail}
                    for e in self._timeline
                ],
            }


__all__ = ["AnalysisJob", "JobStatus", "JobEvent"]
