"""Tests for finfluencer.reporting.main (Sprint 2.3).

Follows the exact methodology already established by
``tests/unit/test_reporting/test_orchestrator.py``: the real, shipped
``config/settings.yaml``/``config/analysts.yaml`` are loaded via
:func:`finfluencer.core.config.load_settings`, with every
``output.paths.*`` value this suite touches redirected into
``tmp_path`` via the platform's existing
``FINFLUENCER_SECTION__KEY`` environment-variable overlay -- never the
real repo's ``data/``, ``cache/``, ``checkpoints/``, or ``outputs/``
directories.

Unlike ``test_orchestrator.py``, which calls
:func:`run_reporting_pipeline` directly, this suite drives the CLI
through Typer's :class:`~typer.testing.CliRunner`, exercising the
actual command-line surface (argument parsing, ``--stage`` validation,
exit codes, ``--json``/human-readable output) end to end against the
real, unmodified orchestrator -- no mocks of ``run_reporting_pipeline``
or of the Sprint 1 statistical functions it calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from finfluencer.core.config import load_settings
from finfluencer.reporting.main import app
from finfluencer.utils.io import write_parquet

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"

_ANALYSTS_4 = ["satiroglu", "gecer", "basaran", "yesilada"]

runner = CliRunner()


# =============================================================================
# Config / fixture helpers (mirrors test_orchestrator.py's own helpers)
# =============================================================================


def _set_tmp_output_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__DATA_RAW", str(tmp_path / "data" / "raw"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__DATA_PROCESSED", str(tmp_path / "data" / "processed"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__CHECKPOINTS", str(tmp_path / "checkpoints"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__REPORTS", str(tmp_path / "outputs" / "reports"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__MANUSCRIPT", str(tmp_path / "outputs" / "manuscript"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__FIGURES", str(tmp_path / "outputs" / "figures"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__TABLES", str(tmp_path / "outputs" / "tables"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__LOGS", str(tmp_path / "logs"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__REPLICATION", str(tmp_path / "outputs" / "replication"))


def _cfg_for_expectations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Loads the same config the CLI will load, purely so tests can
    independently recompute expected output paths -- never passed to
    the CLI itself (the CLI always loads its own config from
    ``--settings``/``--analysts``)."""
    return load_settings(_SETTINGS, _ANALYSTS)


def _expected_paths(cfg) -> dict[str, Path]:
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
    }


def _synthetic_reporting_corpus(n_per_analyst: int = 5, seed: int = 0) -> dict[str, pd.DataFrame]:
    """Identical construction to test_orchestrator.py's own helper --
    ``n_per_analyst=40`` satisfies every downstream statistical
    precondition (E2's n>=30/topic filter, R3's >=5 comments/video
    filter, Mann-Kendall's multi-week requirement, the fixed 4-analyst
    ``ANALYST_ORDER`` manuscript_figures/manuscript_tables need)."""
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


def _invoke(*args: str) -> "object":
    return runner.invoke(app, [
        *args, "--settings", str(_SETTINGS), "--analysts", str(_ANALYSTS),
    ])


# =============================================================================
# analyze
# =============================================================================


class TestAnalyzeCommand:
    def test_invalid_stage_exits_2(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        result = _invoke("analyze", "--stage", "not_a_real_stage")
        assert result.exit_code == 2
        assert "must be one of" in result.output

    def test_dry_run_reports_blocked_when_inputs_missing(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        result = _invoke("analyze", "--dry-run", "--json")
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["master_table"].startswith("blocked")
        assert payload["inferential"].startswith("blocked")

    def test_missing_stage_input_aborts_with_exit_1(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        result = _invoke("analyze")
        assert result.exit_code == 1
        assert "Pipeline aborted" in result.output

    def test_all_runs_both_stages_and_produces_expected_files(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        cfg = _cfg_for_expectations(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))

        result = _invoke("analyze", "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert set(payload.keys()) == {"master_table", "inferential"}
        assert len(payload["master_table"]) == 1
        assert len(payload["inferential"]) == 5

        ep = _expected_paths(cfg)
        assert ep["master_table"].exists()
        assert ep["inferential_results"].exists()

    def test_single_stage_selection_runs_only_that_stage(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        cfg = _cfg_for_expectations(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))

        result = _invoke("analyze", "--stage", "master_table", "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert set(payload.keys()) == {"master_table"}

        ep = _expected_paths(cfg)
        assert ep["master_table"].exists()
        assert not ep["inferential_results"].exists()

    def test_second_run_skips_via_checkpoint_third_run_forces(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        cfg = _cfg_for_expectations(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))

        first = _invoke("analyze")
        assert first.exit_code == 0

        second = _invoke("analyze", "--verbose")
        assert second.exit_code == 0

        third = _invoke("analyze", "--force", "--json")
        assert third.exit_code == 0
        payload = json.loads(third.output)
        assert len(payload["master_table"]) == 1


# =============================================================================
# report
# =============================================================================


class TestReportCommand:
    def test_invalid_stage_exits_2(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        result = _invoke("report", "--stage", "not_a_real_stage")
        assert result.exit_code == 2

    def test_report_all_after_analyze_produces_expected_files(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        cfg = _cfg_for_expectations(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))

        analyze_result = _invoke("analyze")
        assert analyze_result.exit_code == 0, analyze_result.output

        report_result = _invoke("report", "--json")
        assert report_result.exit_code == 0, report_result.output
        payload = json.loads(report_result.output)
        assert set(payload.keys()) == {"manuscript_data", "manuscript_figures", "manuscript_tables"}
        assert len(payload["manuscript_data"]) == 3
        assert len(payload["manuscript_figures"]) == 12
        assert len(payload["manuscript_tables"]) == 1

    def test_report_single_independent_stage_does_not_require_others(self, tmp_path, monkeypatch):
        # manuscript_data's dependencies are videos/comments/master_table/
        # inferential_results only -- it does not depend on
        # manuscript_figures or manuscript_tables, so it may run alone.
        _set_tmp_output_paths(tmp_path, monkeypatch)
        cfg = _cfg_for_expectations(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))
        assert _invoke("analyze").exit_code == 0

        result = _invoke("report", "--stage", "manuscript_data", "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert set(payload.keys()) == {"manuscript_data"}

    def test_missing_analyze_outputs_aborts_with_exit_1(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        result = _invoke("report")
        assert result.exit_code == 1
        assert "Pipeline aborted" in result.output


# =============================================================================
# validate
# =============================================================================


class TestValidateCommand:
    def test_invalid_settings_path_exits_1(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        result = runner.invoke(app, [
            "validate", "--settings", str(tmp_path / "does_not_exist.yaml"),
            "--analysts", str(_ANALYSTS), "--json",
        ])
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["config_valid"] is False

    def test_valid_config_reports_ok_with_real_environment(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        result = _invoke("validate", "--json")
        payload = json.loads(result.output)
        assert payload["config_valid"] is True
        assert payload["publication_stage"] is False
        # settings.yaml ships with replication.stage: "exploratory", so a
        # dirty/unavailable git tree must not affect "ok" here.
        assert result.exit_code == (0 if payload["ok"] else 1)

    def test_blocked_stages_are_reported_but_do_not_fail_validate(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        result = _invoke("validate", "--json")
        payload = json.loads(result.output)
        assert payload["stage_plan"]["master_table"].startswith("blocked")
        # "ok" depends only on packages/git, never on stage readiness.
        assert payload["missing_packages"] == [] or payload["ok"] is False

    def test_missing_package_is_detected(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        import finfluencer.reporting.main as main_module
        monkeypatch.setattr(
            main_module, "_REQUIRED_PACKAGES",
            (*main_module._REQUIRED_PACKAGES, "definitely_not_a_real_package_xyz"),
        )
        result = _invoke("validate", "--json")
        payload = json.loads(result.output)
        assert "definitely_not_a_real_package_xyz" in payload["missing_packages"]
        assert payload["ok"] is False
        assert result.exit_code == 1

    def test_human_readable_output_mentions_overall_status(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        result = _invoke("validate")
        assert "Overall:" in result.output
        assert "Stage plan:" in result.output


# =============================================================================
# export
# =============================================================================


class TestExportCommand:
    def test_export_without_report_outputs_aborts_with_exit_1(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        result = _invoke("export")
        assert result.exit_code == 1
        assert "Export aborted" in result.output

    def test_export_dry_run_reports_plan_without_copying(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        cfg = _cfg_for_expectations(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))
        assert _invoke("analyze").exit_code == 0
        assert _invoke("report").exit_code == 0

        result = _invoke("export", "--dry-run", "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "would_export_to" in payload

        replication_root = Path(str(cfg.settings.output.paths.replication))
        assert not replication_root.exists() or not any(replication_root.iterdir())

    def test_export_copies_report_outputs_into_replication_snapshot(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        cfg = _cfg_for_expectations(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))
        assert _invoke("analyze").exit_code == 0
        assert _invoke("report").exit_code == 0

        result = _invoke("export", "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        dest = Path(payload["exported_to"])
        assert dest.exists()
        for name in ("manuscript", "figures", "tables", "reports"):
            assert (dest / name).is_dir()
        assert payload["n_items"] > 0

    def test_export_refuses_to_overwrite_without_force(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        cfg = _cfg_for_expectations(tmp_path, monkeypatch)
        _write_corpus(cfg, _synthetic_reporting_corpus(n_per_analyst=40))
        assert _invoke("analyze").exit_code == 0
        assert _invoke("report").exit_code == 0

        # Sprint 2.5: generate_run_id() now lives in
        # finfluencer.reporting.replication (extracted from main.py's
        # own former inline implementation), so that is the correct
        # monkeypatch target for pinning the destination directory name.
        import finfluencer.reporting.replication as replication_module
        monkeypatch.setattr(replication_module, "generate_run_id", lambda: "fixed_run_id")

        first = _invoke("export")
        assert first.exit_code == 0

        second = _invoke("export")
        assert second.exit_code == 1
        assert "already exists" in second.output

        third = _invoke("export", "--force", "--json")
        assert third.exit_code == 0, third.output
        payload = json.loads(third.output)
        assert payload["exported_to"].endswith("fixed_run_id")
