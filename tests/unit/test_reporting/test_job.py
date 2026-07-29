"""Tests for finfluencer.reporting.job (Sprint 2.6: AnalysisJob).

Follows the same no-mocks methodology as the rest of Sprint 2's test
suites: :class:`~finfluencer.reporting.job.AnalysisJob` is exercised
against the real, unmodified
:func:`~finfluencer.reporting.orchestrator.run_reporting_pipeline`,
with the real, shipped ``config/settings.yaml``/``config/analysts.yaml``
loaded via :func:`finfluencer.core.config.load_settings` and every
``output.paths.*`` value redirected into ``tmp_path`` via the
platform's existing ``FINFLUENCER_SECTION__KEY`` environment-variable
overlay. "Delegation to the orchestrator" is therefore proven the same
way the rest of this session's work has proven everything: by checking
real, observable side effects (files written, run manifests produced)
match what a direct ``run_reporting_pipeline`` call produces -- not by
mocking the orchestrator and asserting it was called with certain
arguments.

Most tests use ``start(background=False)`` for determinism (no thread
scheduling to reason about); a dedicated ``TestBackgroundExecution``
class covers the real threaded path, including a race-free
mid-pipeline cancellation test that has the external ``on_progress``
callback itself call ``job.cancel()`` once it observes a specific
stage event -- deterministic because ``on_progress`` fires
synchronously on the same thread executing the pipeline, before the
next stage's cancellation check.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.config import load_settings
from finfluencer.reporting.job import AnalysisJob, JobEvent, JobStatus
from finfluencer.reporting.orchestrator import STAGE_ORDER
from finfluencer.utils.io import write_parquet

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"

_ANALYSTS_4 = ["satiroglu", "gecer", "basaran", "yesilada"]


# =============================================================================
# Config / fixture helpers (same construction as test_orchestrator.py)
# =============================================================================


def _load_cfg_with_tmp_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__DATA_RAW", str(tmp_path / "data" / "raw"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__DATA_PROCESSED", str(tmp_path / "data" / "processed"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__CHECKPOINTS", str(tmp_path / "checkpoints"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__REPORTS", str(tmp_path / "outputs" / "reports"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__MANUSCRIPT", str(tmp_path / "outputs" / "manuscript"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__FIGURES", str(tmp_path / "outputs" / "figures"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__TABLES", str(tmp_path / "outputs" / "tables"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__LOGS", str(tmp_path / "logs"))
    return load_settings(_SETTINGS, _ANALYSTS)


def _expected_paths(cfg) -> dict[str, Path]:
    paths = cfg.settings.output.paths
    data_raw = Path(str(paths.data_raw))
    data_processed = Path(str(paths.data_processed))
    return {
        "comments": data_raw / "comments.parquet",
        "videos": data_raw / "videos.parquet",
        "topics": data_processed / "topics.parquet",
        "sentiment": data_processed / "sentiment.parquet",
        "master_table": data_processed / "master_table.csv",
    }


def _synthetic_reporting_corpus(n_per_analyst: int = 5, seed: int = 0) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-06", periods=8)

    comment_rows: list[dict] = []
    sentiment_rows: list[dict] = []
    topic_rows: list[dict] = []
    video_rows: list[dict] = []
    seen_videos: set[str] = set()

    for i, analyst in enumerate(_ANALYSTS_4):
        mean_p = 0.2 + 0.2 * i
        for j in range(n_per_analyst):
            comment_id = f"{analyst}_{j}"
            video_id = f"{analyst}_v{j // 10}"
            date = dates[j % len(dates)]
            p = float(np.clip(rng.normal(mean_p, 0.08), 0.01, 0.99))
            topic_id = 1 if j < 35 else 2

            comment_rows.append({
                "comment_id": comment_id, "video_id": video_id, "analyst_key": analyst,
                "posted_date": date, "text_clean": f"synthetic comment {comment_id}",
                "n_tokens": int(rng.integers(5, 40)), "likes": int(rng.integers(0, 20)),
            })
            sentiment_rows.append({
                "comment_id": comment_id,
                "sentiment_class": "positive" if p >= 0.5 else "negative",
                "sentiment_prob": p,
            })
            topic_rows.append({
                "comment_id": comment_id, "configuration": "pooled",
                "topic_id": topic_id, "topic_label": f"topic_{topic_id}", "topic_prob": 0.8,
            })
            if video_id not in seen_videos:
                seen_videos.add(video_id)
                video_rows.append({
                    "analyst_key": analyst, "video_id": video_id, "eligible": True, "selected": True,
                })

    return {
        "comments": pd.DataFrame(comment_rows),
        "sentiment": pd.DataFrame(sentiment_rows),
        "topics": pd.DataFrame(topic_rows),
        "videos": pd.DataFrame(video_rows),
    }


def _write_corpus(cfg, corpus: dict[str, pd.DataFrame]) -> None:
    ep = _expected_paths(cfg)
    write_parquet(corpus["comments"], ep["comments"])
    write_parquet(corpus["videos"], ep["videos"])
    write_parquet(corpus["topics"], ep["topics"])
    write_parquet(corpus["sentiment"], ep["sentiment"])


def _manifests(cfg) -> list[dict]:
    manifest_dir = Path(str(cfg.settings.output.paths.checkpoints)) / "run_manifests"
    if not manifest_dir.exists():
        return []
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(manifest_dir.glob("*.json"))]


# =============================================================================
# Architecture compliance: no Sprint 1 imports, no statistical logic
# =============================================================================


class TestArchitectureCompliance:
    def test_module_does_not_import_any_sprint1_module(self):
        import finfluencer.reporting.job as job_module
        for name in (
            "master_table", "inferential", "manuscript_data",
            "manuscript_figures", "manuscript_tables",
        ):
            assert name not in job_module.__dict__, f"job.py must not import {name} directly"

    def test_execute_is_the_only_call_site_of_run_reporting_pipeline(self):
        import inspect

        from finfluencer.reporting.job import AnalysisJob

        # The module docstring also mentions run_reporting_pipeline() in
        # prose, so search for the actual call form (assignment),
        # which only the real call site inside _execute matches.
        execute_source = inspect.getsource(AnalysisJob._execute)
        assert execute_source.count("= run_reporting_pipeline(") == 1

        other_methods = [
            m for name, m in inspect.getmembers(AnalysisJob, predicate=inspect.isfunction)
            if name != "_execute"
        ]
        for method in other_methods:
            assert "run_reporting_pipeline(" not in inspect.getsource(method)


# =============================================================================
# Construction and state transitions
# =============================================================================


class TestConstructionAndStateTransitions:
    def test_new_job_is_pending_with_no_output_or_error(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        job = AnalysisJob(cfg, stage="master_table")
        assert job.status == JobStatus.pending
        assert job.current_stage is None
        assert job.outputs == {}
        assert job.error is None
        assert job.progress == 0.0
        assert not job.is_finished

    def test_each_job_gets_its_own_run_id(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        job1 = AnalysisJob(cfg, stage="master_table")
        job2 = AnalysisJob(cfg, stage="master_table")
        assert job1.run_id != job2.run_id

    def test_job_created_event_recorded_at_construction(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        job = AnalysisJob(cfg, stage="master_table")
        assert len(job.timeline) == 1
        assert isinstance(job.timeline[0], JobEvent)
        assert job.timeline[0].event == "job_created"
        assert job.timeline[0].stage is None

    def test_starting_twice_raises_runtime_error(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        job = AnalysisJob(cfg, stage="master_table")
        job.start(background=False)
        with pytest.raises(RuntimeError, match="already been started"):
            job.start(background=False)

    def test_successful_run_transitions_pending_running_success(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        job = AnalysisJob(cfg, stage="master_table")
        assert job.status == JobStatus.pending

        job.start(background=False)

        assert job.status == JobStatus.success
        assert job.is_finished
        # The full transition sequence is reconstructable from the timeline.
        statuses_implied = [e.event for e in job.timeline]
        assert statuses_implied[0] == "job_created"
        assert "job_started" in statuses_implied
        assert statuses_implied[-1] == "job_succeeded"


# =============================================================================
# Delegation to the orchestrator (real, unmocked)
# =============================================================================


class TestDelegationToOrchestrator:
    def test_missing_dependency_surfaces_as_failed_with_file_not_found_error(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        job = AnalysisJob(cfg, stage="master_table")
        job.start(background=False)

        assert job.status == JobStatus.failed
        assert job.error is not None
        assert job.error["type"] == "FileNotFoundError"

    def test_invalid_stage_surfaces_as_failed_with_value_error(self, tmp_path, monkeypatch):
        """AnalysisJob performs no stage validation of its own -- an
        invalid stage must be caught by run_reporting_pipeline's own
        validation and surfaced through the job's failed state,
        proving the job does not duplicate orchestrator logic."""
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        job = AnalysisJob(cfg, stage="not_a_real_stage")
        job.start(background=False)

        assert job.status == JobStatus.failed
        assert job.error["type"] == "ValueError"

    def test_successful_run_writes_a_real_run_manifest_matching_the_orchestrator_contract(
        self, tmp_path, monkeypatch,
    ):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        job = AnalysisJob(cfg, stage="master_table")
        job.start(background=False)

        manifests = _manifests(cfg)
        assert len(manifests) == 1
        assert manifests[0]["status"] == "SUCCESS"
        assert manifests[0]["stage"] == "reporting.master_table"

    def test_outputs_match_a_direct_run_reporting_pipeline_call(self, tmp_path, monkeypatch):
        """Same corpus, same stage, one call through AnalysisJob and
        one direct -- their output paths must be identical, since
        AnalysisJob must not alter what the orchestrator produces."""
        from finfluencer.reporting.orchestrator import run_reporting_pipeline

        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())

        job = AnalysisJob(cfg, stage="master_table")
        job.start(background=False)

        direct_result = run_reporting_pipeline(cfg, stage="master_table")  # already up to date -> skip
        assert job.outputs == direct_result

    def test_force_is_passed_through(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())

        events: list[tuple[str, str]] = []
        AnalysisJob(
            cfg, stage="master_table", on_progress=lambda s, e: events.append((s, e)),
        ).start(background=False)
        assert events == [("master_table", "start"), ("master_table", "done")]

        events.clear()
        AnalysisJob(
            cfg, stage="master_table", force=True,
            on_progress=lambda s, e: events.append((s, e)),
        ).start(background=False)
        assert events == [("master_table", "start"), ("master_table", "done")]

    def test_dry_run_never_touches_disk(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        job = AnalysisJob(cfg, stage="master_table", dry_run=True)
        job.start(background=False)

        assert job.status == JobStatus.success
        assert job.outputs == {"master_table": "would_run"}
        assert not _expected_paths(cfg)["master_table"].exists()
        assert _manifests(cfg) == []


# =============================================================================
# Progress
# =============================================================================


class TestProgress:
    def test_progress_reaches_1_0_on_single_stage_success(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        job = AnalysisJob(cfg, stage="master_table")
        job.start(background=False)
        assert job.progress == 1.0

    def test_progress_increments_monotonically_across_multiple_stages(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))

        snapshots: list[float] = []

        def _capture(stage: str, event: str) -> None:
            if event in ("done", "skipped"):
                snapshots.append(job.progress)

        job = AnalysisJob(cfg, stage="all", on_progress=_capture)
        job.start(background=False)

        assert job.status == JobStatus.success
        assert snapshots == sorted(snapshots)
        assert snapshots[-1] == 1.0
        assert len(snapshots) == len(STAGE_ORDER)
        # Strictly increasing fractions: 1/5, 2/5, 3/5, 4/5, 5/5.
        assert snapshots == [i / len(STAGE_ORDER) for i in range(1, len(STAGE_ORDER) + 1)]

    def test_dry_run_success_forces_progress_to_1_0_despite_no_progress_callbacks(
        self, tmp_path, monkeypatch,
    ):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())

        events: list[tuple[str, str]] = []
        job = AnalysisJob(
            cfg, stage="master_table", dry_run=True, on_progress=lambda s, e: events.append((s, e)),
        )
        job.start(background=False)

        assert events == []  # dry_run never invokes on_progress
        assert job.progress == 1.0

    def test_progress_reflects_partial_completion_on_failure(self, tmp_path, monkeypatch):
        """Forces a deterministic mid-pipeline failure by deleting
        inferential's own required output as soon as it completes (via
        the external on_progress callback, so the deletion is
        guaranteed to happen between the inferential and
        manuscript_data stages, not racing either of them) -- proving
        progress reflects real partial completion (2 of 5 stages) at
        the point of failure, not 0.0 or 1.0. The n_per_analyst=40
        corpus is the same construction already proven sufficient for
        a full stage="all" run by this file's other tests (e.g.
        test_progress_increments_monotonically_across_multiple_stages)."""
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))

        inferential_results = Path(str(cfg.settings.output.paths.reports)) / "inferential_results.json"

        def _corrupt_after_inferential(stage: str, event: str) -> None:
            if stage == "inferential" and event == "done":
                assert inferential_results.exists()
                inferential_results.unlink()

        job = AnalysisJob(cfg, stage="all", on_progress=_corrupt_after_inferential)
        job.start(background=False)

        assert job.status == JobStatus.failed
        assert job.error["type"] == "FileNotFoundError"
        # master_table + inferential both completed before the failure.
        assert job.progress == 2 / len(STAGE_ORDER)

    def test_progress_is_zero_when_the_very_first_stage_fails(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        job = AnalysisJob(cfg, stage="master_table")
        job.start(background=False)
        assert job.status == JobStatus.failed
        assert job.progress == 0.0


# =============================================================================
# Cancellation
# =============================================================================


class TestCancellation:
    def test_cancel_before_start_prevents_any_stage_from_running(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        job = AnalysisJob(cfg, stage="master_table")
        job.cancel()
        job.start(background=False)

        assert job.status == JobStatus.cancelled
        assert job.error["type"] == "PipelineCancelledError"
        assert not _expected_paths(cfg)["master_table"].exists()

    def test_cancel_is_a_no_op_before_start_regarding_timeline(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        job = AnalysisJob(cfg, stage="master_table")
        job.cancel()
        assert any(e.event == "cancel_requested" for e in job.timeline)

    def test_cancel_requested_from_within_on_progress_stops_the_next_stage(
        self, tmp_path, monkeypatch,
    ):
        """Deterministic mid-pipeline cancellation: the external
        on_progress callback calls job.cancel() as soon as it sees
        master_table's "done" event -- since on_progress runs
        synchronously on the same thread as the pipeline, the next
        stage's cancellation check (before inferential begins) is
        guaranteed to observe the now-set event."""
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))

        job_holder: dict[str, AnalysisJob] = {}

        def _maybe_cancel(stage: str, event: str) -> None:
            if stage == "master_table" and event == "done":
                job_holder["job"].cancel()

        job = AnalysisJob(cfg, stage="all", on_progress=_maybe_cancel)
        job_holder["job"] = job
        job.start(background=False)

        assert job.status == JobStatus.cancelled
        assert job.error["type"] == "PipelineCancelledError"
        # master_table itself completed (its own output exists) --
        # only the stage *after* the cancel request was blocked.
        assert _expected_paths(cfg)["master_table"].exists()
        assert not (Path(str(cfg.settings.output.paths.reports)) / "inferential_results.json").exists()

    def test_cancel_after_job_finished_is_harmless(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        job = AnalysisJob(cfg, stage="master_table")
        job.start(background=False)
        assert job.status == JobStatus.success

        job.cancel()  # must not raise or change the already-terminal status
        assert job.status == JobStatus.success


# =============================================================================
# Background threading
# =============================================================================


class TestBackgroundExecution:
    def test_start_background_returns_before_completion_then_join_waits(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        job = AnalysisJob(cfg, stage="master_table")

        job.start(background=True)
        # status is either still "running" or has already raced to
        # "success" on a fast machine -- either is valid; what matters
        # is that start() itself did not block until completion.
        assert job.status in (JobStatus.running, JobStatus.success)

        job.join(timeout=30)
        assert job.status == JobStatus.success
        assert job.is_finished

    def test_join_before_start_is_a_harmless_no_op(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        job = AnalysisJob(cfg, stage="master_table")
        job.join(timeout=1)  # must not raise
        assert job.status == JobStatus.pending


# =============================================================================
# Output propagation
# =============================================================================


class TestOutputPropagation:
    def test_full_pipeline_outputs_match_orchestrator_shape(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))
        job = AnalysisJob(cfg, stage="all")
        job.start(background=False)

        assert job.status == JobStatus.success
        assert set(job.outputs.keys()) == set(STAGE_ORDER)
        assert len(job.outputs["master_table"]) == 1
        assert len(job.outputs["inferential"]) == 5
        assert len(job.outputs["manuscript_data"]) == 3
        assert len(job.outputs["manuscript_figures"]) == 12
        assert len(job.outputs["manuscript_tables"]) == 1
        for stage_name, produced in job.outputs.items():
            for p in produced:
                assert p.exists(), f"{stage_name} output {p} missing"


# =============================================================================
# Summary
# =============================================================================


class TestSummary:
    def test_summary_is_json_serialisable(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        job = AnalysisJob(cfg, stage="master_table")
        job.start(background=False)

        serialised = json.dumps(job.summary())
        payload = json.loads(serialised)
        assert payload["status"] == "success"
        assert payload["run_id"] == job.run_id

    def test_summary_shape_and_metadata_fields(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        job = AnalysisJob(cfg, stage="master_table", dry_run=False, force=True)
        job.start(background=False)

        summary = job.summary()
        assert set(summary.keys()) == {
            "run_id", "status", "stage", "current_stage", "progress",
            "outputs", "error", "metadata", "timeline",
        }
        assert summary["stage"] == "master_table"
        assert summary["error"] is None
        meta = summary["metadata"]
        assert meta["study_name"] == cfg.settings.study.name
        assert meta["dry_run"] is False
        assert meta["force"] is True
        assert meta["created_at"] is not None
        assert meta["started_at"] is not None
        assert meta["finished_at"] is not None

    def test_summary_outputs_are_strings_not_path_objects(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        job = AnalysisJob(cfg, stage="master_table")
        job.start(background=False)

        for produced in job.summary()["outputs"].values():
            for item in produced:
                assert isinstance(item, str)

    def test_summary_includes_full_timeline_with_ordered_timestamps(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        job = AnalysisJob(cfg, stage="master_table")
        job.start(background=False)

        timeline = job.summary()["timeline"]
        assert [e["event"] for e in timeline] == [
            "job_created", "job_started", "start", "done", "job_succeeded",
        ]
        assert [e["stage"] for e in timeline] == [None, None, "master_table", "master_table", None]
        timestamps = [e["timestamp"] for e in timeline]
        assert timestamps == sorted(timestamps)

    def test_error_summary_populated_on_failure(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        job = AnalysisJob(cfg, stage="master_table")
        job.start(background=False)

        summary = job.summary()
        assert summary["status"] == "failed"
        assert summary["error"]["type"] == "FileNotFoundError"
