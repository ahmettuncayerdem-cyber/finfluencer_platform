"""Tests for finfluencer.cli (Sprint 2.4: root CLI composition).

Verifies that mounting the reporting commands (``analyze``, ``report``,
``validate``, ``export`` -- from :mod:`finfluencer.reporting.main`,
unmodified) onto the same Typer ``app`` object as
:mod:`finfluencer.collect.main`'s own ``run`` command:

* preserves ``run`` exactly as it was (same options, same ``--stage``
  validation, same exit codes);
* registers all four reporting commands as flat siblings of ``run``
  (not nested under a sub-group);
* does not leak into ``finfluencer.collect.main``'s own standalone
  entry point (``python -m finfluencer.collect.main``) when
  ``finfluencer.cli`` has never been imported in that process --
  verified via a real subprocess, since within a single test process
  the two modules' ``app`` objects are (by design, see ``cli.py``'s
  docstring) literally the same object;
* is reachable via ``python -m finfluencer.cli``.

No mocks: every command's own logic is exercised for real (through
Typer's :class:`~typer.testing.CliRunner` for in-process checks, and a
real subprocess for the module-entry-point / non-leakage checks),
following the same methodology as
``tests/unit/test_reporting/test_main.py``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

import finfluencer.cli as cli_module
import finfluencer.collect.main as collect_main_module
import finfluencer.reporting.main as reporting_main_module

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"

runner = CliRunner(mix_stderr=False)


def _set_tmp_output_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same env-var overlay used throughout Sprint 2's own test suites
    -- redirects every output location into tmp_path so nothing is
    ever written to the real repo."""
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


def _run_subprocess(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


# =============================================================================
# Composition invariants
# =============================================================================


class TestCompositionInvariants:
    def test_cli_app_is_the_same_object_as_collect_main_app(self):
        """Documented architecture decision (cli.py's own docstring):
        every entry point resolves to one canonical Typer app, not
        independently maintained CLIs."""
        assert cli_module.app is collect_main_module.app

    def test_reporting_main_app_is_a_separate_untouched_instance(self):
        """reporting.main.app must remain its own standalone Typer
        instance -- mounting its commands onto cli.app must not have
        mutated or replaced it."""
        assert cli_module.app is not reporting_main_module.app
        reporting_names = {
            c.name or c.callback.__name__ for c in reporting_main_module.app.registered_commands
        }
        assert reporting_names == {"analyze", "report", "validate", "export"}

    def test_root_app_registers_all_five_commands(self):
        names = {c.name or c.callback.__name__ for c in cli_module.app.registered_commands}
        assert names == {"run", "analyze", "report", "validate", "export"}


# =============================================================================
# --help surfaces every command
# =============================================================================


class TestRootHelp:
    def test_help_lists_all_five_commands(self):
        result = runner.invoke(cli_module.app, ["--help"])
        assert result.exit_code == 0
        for name in ("run", "analyze", "report", "validate", "export"):
            assert name in result.output

    def test_commands_are_flat_not_nested_under_a_subgroup(self):
        # A nested "reporting" group would show up as its own entry in
        # the Commands panel and require "finfluencer reporting analyze".
        result = runner.invoke(cli_module.app, ["--help"])
        assert "reporting" not in result.output.lower()
        # Directly invoking the flat command name must work with no group prefix.
        help_result = runner.invoke(cli_module.app, ["analyze", "--help"])
        assert help_result.exit_code == 0


# =============================================================================
# Existing collect command ("run") preserved exactly
# =============================================================================


class TestCollectRunCommandPreserved:
    def test_run_help_shows_original_options(self):
        result = runner.invoke(cli_module.app, ["run", "--help"])
        assert result.exit_code == 0
        for opt in ("--settings", "--analysts", "--stage", "--dry-run", "--verbose"):
            assert opt in result.output

    def test_run_invalid_stage_exits_2_unchanged(self):
        result = runner.invoke(cli_module.app, ["run", "--stage", "not_a_real_stage"])
        assert result.exit_code == 2
        assert "must be one of" in result.stderr

    def test_run_missing_upstream_input_aborts_with_exit_1(self, tmp_path, monkeypatch):
        # Real load_settings + run_pipeline call through the composed
        # app, proving the wiring doesn't change collect's own runtime
        # behaviour: videos needs channels.parquet, which does not
        # exist under a freshly redirected tmp output tree.
        _set_tmp_output_paths(tmp_path, monkeypatch)
        result = runner.invoke(
            cli_module.app,
            ["run", "--stage", "videos", "--settings", str(_SETTINGS), "--analysts", str(_ANALYSTS)],
        )
        assert result.exit_code == 1
        assert "Pipeline aborted" in result.stderr


# =============================================================================
# New reporting commands registered and functional through the composed app
# =============================================================================


class TestReportingCommandsRegistered:
    @pytest.mark.parametrize("name", ["analyze", "report", "validate", "export"])
    def test_help_works_for_each_reporting_command(self, name):
        result = runner.invoke(cli_module.app, [name, "--help"])
        assert result.exit_code == 0
        for opt in ("--settings", "--analysts", "--dry-run", "--force", "--verbose", "--json"):
            assert opt in result.output

    @pytest.mark.parametrize("name", ["analyze", "report"])
    def test_invalid_stage_exits_2_for_stage_bearing_commands(self, name):
        result = runner.invoke(cli_module.app, [name, "--stage", "not_a_real_stage"])
        assert result.exit_code == 2

    def test_validate_runs_end_to_end_through_the_composed_app(self, tmp_path, monkeypatch):
        """Not just presence -- actually executes reporting.main.validate's
        real logic (config load, package check, orchestrator dry-run
        plan) through the root app, proving option parsing and
        dispatch work end to end, not merely that the command exists."""
        _set_tmp_output_paths(tmp_path, monkeypatch)
        result = runner.invoke(
            cli_module.app,
            ["validate", "--settings", str(_SETTINGS), "--analysts", str(_ANALYSTS), "--json"],
        )
        payload = json.loads(result.output)
        assert payload["config_valid"] is True
        assert "stage_plan" in payload
        assert result.exit_code == (0 if payload["ok"] else 1)

    def test_export_without_report_outputs_aborts_with_exit_1(self, tmp_path, monkeypatch):
        _set_tmp_output_paths(tmp_path, monkeypatch)
        result = runner.invoke(
            cli_module.app,
            ["export", "--settings", str(_SETTINGS), "--analysts", str(_ANALYSTS)],
        )
        assert result.exit_code == 1
        assert "Export aborted" in result.stderr


# =============================================================================
# Standalone collect.main is unaffected unless finfluencer.cli is imported
# =============================================================================


class TestStandaloneCollectMainUnaffected:
    def test_python_dash_m_collect_main_help_has_no_reporting_commands(self):
        """A fresh subprocess that never imports finfluencer.cli must see
        collect.main.app exactly as authored -- single-command style
        (no 'Commands' subcommand panel), not the 5-command composed app."""
        proc = _run_subprocess("-m", "finfluencer.collect.main", "--help")
        assert proc.returncode == 0, proc.stderr
        for name in ("analyze", "report", "validate", "export"):
            assert name not in proc.stdout
        assert "Run the data-collection pipeline." in proc.stdout

    def test_python_dash_m_reporting_main_help_has_no_run_command(self):
        proc = _run_subprocess("-m", "finfluencer.reporting.main", "--help")
        assert proc.returncode == 0, proc.stderr
        assert "run" not in [w.strip() for w in proc.stdout.split()]
        for name in ("analyze", "report", "validate", "export"):
            assert name in proc.stdout


# =============================================================================
# Module entry point
# =============================================================================


class TestModuleEntryPoint:
    def test_python_dash_m_finfluencer_cli_help_exits_0_and_lists_all_commands(self):
        proc = _run_subprocess("-m", "finfluencer.cli", "--help")
        assert proc.returncode == 0, proc.stderr
        for name in ("run", "analyze", "report", "validate", "export"):
            assert name in proc.stdout

    def test_python_dash_m_finfluencer_cli_run_subcommand_help_works(self):
        proc = _run_subprocess("-m", "finfluencer.cli", "run", "--help")
        assert proc.returncode == 0, proc.stderr
        assert "Path to settings.yaml" in proc.stdout

    def test_python_dash_m_finfluencer_cli_analyze_subcommand_help_works(self):
        proc = _run_subprocess("-m", "finfluencer.cli", "analyze", "--help")
        assert proc.returncode == 0, proc.stderr
        assert "master_table" in proc.stdout
