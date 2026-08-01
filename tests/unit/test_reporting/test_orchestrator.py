"""Tests for finfluencer.reporting.orchestrator (Sprint 2.1).

Follows the exact methodology already established by
``tests/unit/test_collect/test_run_pipeline_manifest.py``: the real,
shipped ``config/settings.yaml``/``config/analysts.yaml`` are loaded
via :func:`finfluencer.core.config.load_settings`, with every
``output.paths.*`` value this test suite touches redirected into
``tmp_path`` via the platform's existing
``FINFLUENCER_SECTION__KEY`` environment-variable overlay -- never the
real repo's ``data/``, ``cache/``, ``checkpoints/``, or ``outputs/``
directories. :func:`run_reporting_pipeline` is called directly, never
through a CLI (there is none yet -- Sprint 2.1 is the orchestration
engine only).

No statistical result is mocked: every stage that actually executes
runs the real, unmodified Sprint 1 functions (``build_master_table``,
``run_all_inferential_tests``, etc.) against small, real synthetic
Parquet/CSV fixtures. This means most tests deliberately exercise only
the cheapest stage (``master_table``, three tiny Parquet files, no
statistics) to test orchestration mechanics (skip/force/resume/
cancellation/manifest/progress) in isolation -- Sprint 1's own 97
tests already prove the statistics are correct, this suite proves the
coordination around them is correct. One larger integration test
(``TestFullPipelineHappyPath``) runs ``stage="all"`` end to end against
a synthetic corpus sized to satisfy every downstream stage's real
statistical preconditions (E2's n>=30 topic filter, R3's >=5
comments/video filter, Mann-Kendall's need for multiple weekly points,
4 distinct analysts for E1/manuscript_figures/manuscript_tables' fixed
``ANALYST_ORDER``), proving the full DAG wiring end to end.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.config import load_settings
from finfluencer.reporting.orchestrator import (
    STAGE_ORDER,
    PipelineCancelledError,
    run_reporting_pipeline,
)
from finfluencer.utils.io import write_parquet

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"

_ANALYSTS_4 = ["satiroglu", "gecer", "basaran", "yesilada"]


# =============================================================================
# Config / fixture helpers
# =============================================================================


def _load_cfg_with_tmp_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Real config, with every output path redirected into ``tmp_path``
    so nothing is ever written to the real repo. Matches
    ``test_run_pipeline_manifest.py``'s own helper, extended with the
    four reporting-relevant output directories."""
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__DATA_RAW", str(tmp_path / "data" / "raw"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__DATA_PROCESSED", str(tmp_path / "data" / "processed"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__CHECKPOINTS", str(tmp_path / "checkpoints"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__REPORTS", str(tmp_path / "outputs" / "reports"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__MANUSCRIPT", str(tmp_path / "outputs" / "manuscript"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__FIGURES", str(tmp_path / "outputs" / "figures"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__TABLES", str(tmp_path / "outputs" / "tables"))
    return load_settings(_SETTINGS, _ANALYSTS)


def _expected_paths(cfg) -> dict[str, Path]:
    """Independently recomputes the same layout
    :func:`finfluencer.reporting.orchestrator._resolve_paths` should
    produce -- deliberately not importing that private function, so
    this test suite verifies the orchestrator's path resolution
    against an independent expectation rather than trivially agreeing
    with itself."""
    paths = cfg.settings.output.paths
    data_raw = Path(str(paths.data_raw))
    data_processed = Path(str(paths.data_processed))
    reports_dir = Path(str(paths.reports))
    manuscript_dir = Path(str(paths.manuscript))
    figures_dir = Path(str(paths.figures))
    tables_dir = Path(str(paths.tables))
    return {
        "comments": data_raw / "comments.parquet",
        "videos": data_raw / "videos.parquet",
        "topics": data_processed / "topics.parquet",
        "sentiment": data_processed / "sentiment.parquet",
        "master_table": data_processed / "master_table.csv",
        "reports_dir": reports_dir,
        "manuscript_dir": manuscript_dir,
        "figures_dir": figures_dir,
        "tables_dir": tables_dir,
        "inferential_results": reports_dir / "inferential_results.json",
        "topic_level_results": reports_dir / "topic_level_test_results.csv",
        "dunn_posthoc_matrix": reports_dir / "dunn_posthoc_matrix.csv",
        "weekly_sentiment_by_analyst": reports_dir / "weekly_sentiment_by_analyst.csv",
        "video_level_results": reports_dir / "video_level_volume_sentiment.csv",
        "workbook": tables_dir / f"{cfg.settings.study.name}_inferential_stats.xlsx",
    }


def _synthetic_reporting_corpus(n_per_analyst: int = 5, seed: int = 0) -> dict[str, pd.DataFrame]:
    """Raw comments/videos/topics/sentiment tables for all four
    analysts. With ``n_per_analyst=40`` (used by the full-pipeline
    tests) this satisfies every downstream stage's real statistical
    precondition: E2's n>=30-per-topic filter (topic 1 gets 140 pooled
    rows, topic 2 stays at 20 and is correctly excluded, exercising the
    filter exactly as ``test_inferential.py``'s own synthetic fixture
    does), R3's >=5-comments/video filter (4 videos/analyst, 10
    comments each), Mann-Kendall's need for multiple weekly points (8
    distinct weeks), and manuscript_figures/manuscript_tables' fixed
    4-analyst ``ANALYST_ORDER``. Smaller values (used by the
    orchestration-only tests) skip all of this -- they only exercise
    the cheap ``master_table`` stage, which just needs non-empty,
    correctly-shaped Parquet.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-06", periods=8)  # 8 weeks of Mondays

    comment_rows: list[dict] = []
    sentiment_rows: list[dict] = []
    topic_rows: list[dict] = []
    video_rows: list[dict] = []
    seen_videos: set[str] = set()

    for i, analyst in enumerate(_ANALYSTS_4):
        mean_p = 0.2 + 0.2 * i  # 0.2, 0.4, 0.6, 0.8 -- well-separated by construction
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


def _manifest_dir(cfg) -> Path:
    return Path(str(cfg.settings.output.paths.checkpoints)) / "run_manifests"


def _manifests(cfg) -> list[dict]:
    manifest_dir = _manifest_dir(cfg)
    if not manifest_dir.exists():
        return []
    return [
        json.loads(f.read_text(encoding="utf-8"))
        for f in sorted(manifest_dir.glob("*.json"))
    ]


def _latest_manifest(cfg) -> dict:
    manifests = _manifests(cfg)
    assert manifests, "expected at least one run manifest to have been written"
    return manifests[-1]


# =============================================================================
# Stage validation
# =============================================================================


class TestStageValidation:
    def test_invalid_stage_raises_value_error(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        with pytest.raises(ValueError, match="stage must be one of"):
            run_reporting_pipeline(cfg, stage="not_a_real_stage")


# =============================================================================
# Dependency validation
# =============================================================================


class TestDependencyValidation:
    def test_master_table_stage_raises_when_inputs_missing(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        with pytest.raises(FileNotFoundError):
            run_reporting_pipeline(cfg, stage="master_table")

    def test_inferential_stage_raises_when_master_table_missing(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        with pytest.raises(FileNotFoundError):
            run_reporting_pipeline(cfg, stage="inferential")

    def test_manuscript_tables_stage_raises_when_inferential_outputs_missing(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        with pytest.raises(FileNotFoundError):
            run_reporting_pipeline(cfg, stage="manuscript_tables")


# =============================================================================
# Checkpoint: skip-if-unchanged, force rebuild, resume semantics
# =============================================================================


class TestMasterTableStageSkipAndForce:
    def test_first_run_executes_and_second_run_skips(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        ep = _expected_paths(cfg)

        events: list[tuple[str, str]] = []
        result1 = run_reporting_pipeline(
            cfg, stage="master_table", on_progress=lambda s, e: events.append((s, e)),
        )
        assert events == [("master_table", "start"), ("master_table", "done")]
        assert result1 == {"master_table": [ep["master_table"]]}
        assert ep["master_table"].exists()

        events.clear()
        result2 = run_reporting_pipeline(
            cfg, stage="master_table", on_progress=lambda s, e: events.append((s, e)),
        )
        assert events == [("master_table", "skipped")]
        assert result2 == {"master_table": [ep["master_table"]]}

    def test_force_rebuilds_even_when_inputs_unchanged(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        run_reporting_pipeline(cfg, stage="master_table")

        events: list[tuple[str, str]] = []
        run_reporting_pipeline(
            cfg, stage="master_table", force=True, on_progress=lambda s, e: events.append((s, e)),
        )
        assert events == [("master_table", "start"), ("master_table", "done")]

    def test_checkpoint_invalidated_when_input_content_changes(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=5, seed=0))
        run_reporting_pipeline(cfg, stage="master_table")

        # Different content (different seed/size) -> input file hashes
        # change -> checkpoint must recognise this as stale, WITHOUT force.
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=6, seed=1))
        events: list[tuple[str, str]] = []
        run_reporting_pipeline(
            cfg, stage="master_table", on_progress=lambda s, e: events.append((s, e)),
        )
        assert events == [("master_table", "start"), ("master_table", "done")]


class TestResumeAfterInterruption:
    def test_completed_stage_is_skipped_when_resuming_stage_all(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))

        # Simulate an interrupted run that only got through master_table.
        run_reporting_pipeline(cfg, stage="master_table")

        events: list[tuple[str, str]] = []
        run_reporting_pipeline(cfg, stage="all", on_progress=lambda s, e: events.append((s, e)))

        assert ("master_table", "skipped") in events
        assert ("master_table", "start") not in events
        assert ("inferential", "start") in events
        assert ("manuscript_tables", "done") in events


# =============================================================================
# Dry run
# =============================================================================


class TestDryRun:
    def test_blocked_when_inputs_missing(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        plan = run_reporting_pipeline(cfg, stage="master_table", dry_run=True)
        assert plan["master_table"].startswith("blocked")

    def test_would_run_then_up_to_date_then_forced(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())

        plan = run_reporting_pipeline(cfg, stage="master_table", dry_run=True)
        assert plan == {"master_table": "would_run"}

        run_reporting_pipeline(cfg, stage="master_table")

        plan2 = run_reporting_pipeline(cfg, stage="master_table", dry_run=True)
        assert plan2 == {"master_table": "up_to_date"}

        plan3 = run_reporting_pipeline(cfg, stage="master_table", dry_run=True, force=True)
        assert plan3 == {"master_table": "would_run (forced)"}

    def test_dry_run_does_not_execute_or_write_manifest(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())

        run_reporting_pipeline(cfg, stage="master_table", dry_run=True)

        assert not _expected_paths(cfg)["master_table"].exists()
        assert _manifests(cfg) == []

    def test_dry_run_does_not_delete_stale_checkpoint_marker(self, tmp_path, monkeypatch):
        """R8 / ADR-P2-004 regression test.

        Reproduces the exact real-world sequence: a stage completes,
        its input then changes on disk (making the checkpoint stale),
        and the caller previews with --dry-run before deciding whether
        to actually re-run. Before the fix, ``_build_dry_run_plan`` ->
        ``checkpoint.should_run()`` silently deleted the ``.done``
        marker as a side effect of merely answering "would this run?"
        -- despite that function's own docstring promising
        "Introspection-only: never touches disk". A dry run must be
        able to report "would_run" without destroying the record that
        the *previous* run actually completed.
        """
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=5, seed=0))
        run_reporting_pipeline(cfg, stage="master_table")

        marker = Path(str(cfg.settings.output.paths.checkpoints)) / "reporting_master_table.done"
        assert marker.exists()
        recorded_before = marker.read_text(encoding="utf-8")

        # Change input content -> config_slice hash changes -> checkpoint
        # is now stale, exactly the condition that made should_run()
        # delete the marker.
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=6, seed=1))

        plan = run_reporting_pipeline(cfg, stage="master_table", dry_run=True)

        assert plan == {"master_table": "would_run"}, (
            "the plan must still correctly report staleness"
        )
        assert marker.exists(), (
            "dry_run must not delete the marker for a stage it only "
            "previewed -- this is the destructive side effect ADR-P2-004 "
            "fixes"
        )
        assert marker.read_text(encoding="utf-8") == recorded_before, (
            "marker content must be untouched, not just 'still present'"
        )

        # And the real run afterward must still correctly detect
        # staleness and re-execute -- proving should_run()'s own
        # (unchanged, still-mutating) contract for real runs still works.
        events: list[tuple[str, str]] = []
        run_reporting_pipeline(
            cfg, stage="master_table", on_progress=lambda s, e: events.append((s, e)),
        )
        assert events == [("master_table", "start"), ("master_table", "done")]


# =============================================================================
# Cancellation
# =============================================================================


class TestCancellation:
    def test_preset_cancel_event_raises_before_execution(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        cancel = threading.Event()
        cancel.set()

        with pytest.raises(PipelineCancelledError):
            run_reporting_pipeline(cfg, stage="master_table", cancel_event=cancel)

        assert not _expected_paths(cfg)["master_table"].exists()

    def test_cancellation_writes_failed_manifest_with_cancelled_flag(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        cancel = threading.Event()
        cancel.set()

        with pytest.raises(PipelineCancelledError):
            run_reporting_pipeline(cfg, stage="master_table", cancel_event=cancel)

        manifest = _latest_manifest(cfg)
        assert manifest["status"] == "FAILED"
        assert manifest["error"]["type"] == "PipelineCancelledError"
        assert manifest["extras"]["cancelled"] is True

    def test_unset_cancel_event_does_not_block_execution(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        cancel = threading.Event()  # never set

        result = run_reporting_pipeline(cfg, stage="master_table", cancel_event=cancel)
        assert result["master_table"][0].exists()


# =============================================================================
# Run manifest integration (Architecture v1.0 SS10)
# =============================================================================


class TestRunManifestIntegration:
    def test_success_writes_manifest_with_expected_shape(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        run_reporting_pipeline(cfg, stage="master_table")

        manifest = _latest_manifest(cfg)
        assert manifest["status"] == "SUCCESS"
        assert manifest["stage"] == "reporting.master_table"
        assert manifest["extras"]["stages_run"] == ["master_table"]
        assert "config_hashes" in manifest
        assert "environment" in manifest

    def test_failure_writes_failed_manifest_with_error_details(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        with pytest.raises(FileNotFoundError):
            run_reporting_pipeline(cfg, stage="master_table")

        manifest = _latest_manifest(cfg)
        assert manifest["status"] == "FAILED"
        assert manifest["error"]["type"] == "FileNotFoundError"
        assert manifest["extras"]["stages_run"] == []


# =============================================================================
# Progress callback robustness
# =============================================================================


class TestProgressCallbackRobustness:
    def test_callback_exception_does_not_break_the_pipeline(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())

        def bad_callback(stage: str, event: str) -> None:
            raise RuntimeError("boom")

        result = run_reporting_pipeline(cfg, stage="master_table", on_progress=bad_callback)
        assert result["master_table"][0].exists()

    def test_on_progress_none_is_the_default_and_works(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus())
        result = run_reporting_pipeline(cfg, stage="master_table")
        assert result["master_table"][0].exists()


# =============================================================================
# Full pipeline integration (real statistics, all five stages)
# =============================================================================


class TestFullPipelineHappyPath:
    def test_stage_all_runs_every_stage_and_produces_expected_files(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))

        events: list[tuple[str, str]] = []
        result = run_reporting_pipeline(cfg, stage="all", on_progress=lambda s, e: events.append((s, e)))

        assert set(result.keys()) == set(STAGE_ORDER)
        assert len(result["master_table"]) == 1
        assert len(result["inferential"]) == 5
        assert len(result["manuscript_data"]) == 3
        assert len(result["manuscript_figures"]) == 12
        assert len(result["manuscript_tables"]) == 1

        for stage_name, produced in result.items():
            for p in produced:
                assert p.exists(), f"{stage_name} output {p} was not created"

        started_in_order = [s for s, e in events if e == "start"]
        assert started_in_order == list(STAGE_ORDER)

        manifest = _latest_manifest(cfg)
        assert manifest["status"] == "SUCCESS"
        assert manifest["stage"] == "reporting.all"
        assert manifest["extras"]["stages_run"] == list(STAGE_ORDER)

    def test_second_run_skips_every_stage(self, tmp_path, monkeypatch):
        cfg = _load_cfg_with_tmp_paths(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))
        run_reporting_pipeline(cfg, stage="all")

        events: list[tuple[str, str]] = []
        run_reporting_pipeline(cfg, stage="all", on_progress=lambda s, e: events.append((s, e)))

        assert events == [(name, "skipped") for name in STAGE_ORDER]
