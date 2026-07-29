"""Tests for finfluencer.reporting.replication (Sprint 2.5).

Unlike ``test_main.py``'s export tests (which drive the CLI end to
end, including a real ``analyze``+``report`` run to produce genuine
statistical outputs), this suite calls
:func:`~finfluencer.reporting.replication.build_replication_package`
directly and populates its four source directories with small,
synthetic placeholder files -- proving the module's own copy/
dry-run/overwrite logic in isolation, independent of both Typer and
the reporting pipeline's real statistics. Real, unmocked filesystem
operations throughout (no ``unittest.mock``); the only monkeypatching
used is pinning ``generate_run_id`` for deterministic destination
names in the overwrite tests, exactly as ``test_main.py`` already does
for its own equivalent CLI-level test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from finfluencer.core.config import load_settings
from finfluencer.reporting.replication import EXPORT_SOURCES, build_replication_package

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"


def _set_tmp_output_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__DATA_RAW", str(tmp_path / "data" / "raw"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__DATA_PROCESSED", str(tmp_path / "data" / "processed"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__CHECKPOINTS", str(tmp_path / "checkpoints"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__LOGS", str(tmp_path / "logs"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__REPORTS", str(tmp_path / "outputs" / "reports"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__MANUSCRIPT", str(tmp_path / "outputs" / "manuscript"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__FIGURES", str(tmp_path / "outputs" / "figures"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__TABLES", str(tmp_path / "outputs" / "tables"))
    monkeypatch.setenv("FINFLUENCER_OUTPUT__PATHS__REPLICATION", str(tmp_path / "outputs" / "replication"))


def _cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _set_tmp_output_paths(tmp_path, monkeypatch)
    return load_settings(_SETTINGS, _ANALYSTS)


def _write_fake_report_outputs(cfg, *, n_files_per_dir: int = 2) -> None:
    """Populates the four EXPORT_SOURCES directories with small,
    synthetic placeholder files -- standing in for real
    manuscript/figures/tables/reports output without needing to run
    the actual reporting pipeline."""
    paths = cfg.settings.output.paths
    for field_name in EXPORT_SOURCES:
        d = Path(str(getattr(paths, field_name)))
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n_files_per_dir):
            (d / f"file_{i}.txt").write_text(f"content {i}", encoding="utf-8")


# =============================================================================
# Public constant
# =============================================================================


class TestExportSourcesConstant:
    def test_matches_the_four_report_stage_output_directories(self):
        assert EXPORT_SOURCES == ("manuscript", "figures", "tables", "reports")


# =============================================================================
# Missing inputs
# =============================================================================


class TestMissingInputs:
    def test_raises_file_not_found_when_all_sources_missing(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        with pytest.raises(FileNotFoundError, match="run 'report' first"):
            build_replication_package(cfg)

    def test_raises_file_not_found_when_one_source_is_empty(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        tables_dir = Path(str(cfg.settings.output.paths.tables))
        for f in tables_dir.iterdir():
            f.unlink()

        with pytest.raises(FileNotFoundError, match="tables"):
            build_replication_package(cfg)

    def test_error_message_lists_every_missing_source(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        with pytest.raises(FileNotFoundError) as excinfo:
            build_replication_package(cfg)
        for name in EXPORT_SOURCES:
            assert name in str(excinfo.value)

    def test_dry_run_also_validates_inputs_first(self, tmp_path, monkeypatch):
        """dry_run must still catch missing inputs -- it is a plan for
        a real export, not a no-op that skips validation."""
        cfg = _cfg(tmp_path, monkeypatch)
        with pytest.raises(FileNotFoundError):
            build_replication_package(cfg, dry_run=True)


# =============================================================================
# Dry run
# =============================================================================


class TestDryRun:
    def test_returns_plan_without_copying_anything(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)

        result = build_replication_package(cfg, dry_run=True)
        assert set(result.keys()) == {"would_export_to", "sources"}
        assert set(result["sources"].keys()) == set(EXPORT_SOURCES)
        assert not result["would_export_to"].exists()

        replication_root = Path(str(cfg.settings.output.paths.replication))
        assert not replication_root.exists() or not any(replication_root.iterdir())

    def test_dry_run_sources_point_to_the_real_source_directories(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg, dry_run=True)
        for name, path_str in result["sources"].items():
            p = Path(path_str)
            assert p.is_dir()
            assert p == Path(str(getattr(cfg.settings.output.paths, name)))

    def test_dry_run_would_export_to_is_nested_under_replication_root(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg, dry_run=True)
        replication_root = Path(str(cfg.settings.output.paths.replication))
        assert result["would_export_to"].parent == replication_root


# =============================================================================
# Successful export
# =============================================================================


class TestSuccessfulExport:
    def test_copies_every_source_into_its_own_named_subdirectory(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg, n_files_per_dir=3)

        result = build_replication_package(cfg)
        dest = result["exported_to"]
        assert dest.exists()
        for name in EXPORT_SOURCES:
            sub = dest / name
            assert sub.is_dir()
            assert len(list(sub.iterdir())) == 3

    def test_n_items_matches_total_copied_file_count(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg, n_files_per_dir=5)
        result = build_replication_package(cfg)
        assert result["n_items"] == 5 * len(EXPORT_SOURCES)

    def test_file_contents_are_preserved_byte_for_byte(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg, n_files_per_dir=1)
        result = build_replication_package(cfg)
        dest = result["exported_to"]
        for name in EXPORT_SOURCES:
            copied = (dest / name / "file_0.txt").read_text(encoding="utf-8")
            assert copied == "content 0"

    def test_destination_is_nested_under_replication_root(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        replication_root = Path(str(cfg.settings.output.paths.replication))
        assert result["exported_to"].parent == replication_root

    def test_two_successive_exports_get_distinct_destinations(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        first = build_replication_package(cfg)
        second = build_replication_package(cfg)
        assert first["exported_to"] != second["exported_to"]
        assert first["exported_to"].exists()
        assert second["exported_to"].exists()

    def test_source_directories_are_untouched_after_export(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg, n_files_per_dir=2)
        build_replication_package(cfg)
        for name in EXPORT_SOURCES:
            d = Path(str(getattr(cfg.settings.output.paths, name)))
            assert len(list(d.iterdir())) == 2


# =============================================================================
# Overwrite semantics
# =============================================================================


class TestOverwriteSemantics:
    def test_raises_file_exists_error_without_force(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)

        import finfluencer.reporting.replication as replication_module
        monkeypatch.setattr(replication_module, "generate_run_id", lambda: "fixed_run_id")

        build_replication_package(cfg)
        with pytest.raises(FileExistsError, match="already exists"):
            build_replication_package(cfg)

    def test_force_overwrites_existing_destination_with_fresh_content(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg, n_files_per_dir=1)

        import finfluencer.reporting.replication as replication_module
        monkeypatch.setattr(replication_module, "generate_run_id", lambda: "fixed_run_id")

        first = build_replication_package(cfg)
        assert first["n_items"] == len(EXPORT_SOURCES)

        _write_fake_report_outputs(cfg, n_files_per_dir=3)
        second = build_replication_package(cfg, force=True)
        assert second["exported_to"] == first["exported_to"]
        assert second["n_items"] == 3 * len(EXPORT_SOURCES)


# =============================================================================
# Module independence (Sprint 2.5's own point)
# =============================================================================


class TestModuleIndependence:
    def test_replication_module_has_no_typer_or_cli_dependency(self):
        import finfluencer.reporting.replication as replication_module
        assert "typer" not in replication_module.__dict__

    def test_callable_directly_without_reporting_main_or_the_cli(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        assert result["exported_to"].exists()
