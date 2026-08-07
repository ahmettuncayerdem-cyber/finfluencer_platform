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

import json
from pathlib import Path

import pytest

from finfluencer.core.config import load_settings
from finfluencer.core.exceptions import ReproducibilityError
from finfluencer.reporting.replication import (
    EXPORT_SOURCES,
    MANIFEST_SCHEMA_VERSION,
    build_replication_package,
    compute_checksums,
    create_archive,
    generate_codebook,
    validate_replication_package,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"

#: MANIFEST.json, README.md, CODEBOOK.md, codebook.json, CHECKSUMS.sha256 --
#: the package-scaffolding files build_replication_package writes at the
#: package root, in addition to the four EXPORT_SOURCES sub-directories.
_N_SCAFFOLDING_FILES = 5


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
    # This whole file's tests build/inspect a replication package in isolation and were never
    # meant to exercise stage-gating (that is `TestPublicationStageGate`'s own, narrower job) --
    # pin the stage explicitly rather than inherit whatever config/settings.yaml's real default
    # currently is. Needed as of the V1.0 Research Readiness freeze
    # (docs/implementation/V1.0_RESEARCH_READINESS_AUDIT.md section 8 item 3, 2026-08-07), which
    # raised that real default from "exploratory" to "submission" -- without this override, every
    # test below would start hitting `_gate_publication_stage`'s clean-git-tree requirement
    # (submission-stage, not just publication-stage) against this sandbox's real, routinely-dirty
    # working tree, for reasons having nothing to do with what each test actually verifies.
    monkeypatch.setenv("FINFLUENCER_REPLICATION__STAGE", "exploratory")
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
        # Sprint 2 (Product Engineering): n_items now also counts the five
        # package-scaffolding files build_replication_package writes at the
        # package root -- MANIFEST.json, README.md, CODEBOOK.md,
        # codebook.json, CHECKSUMS.sha256 -- in addition to the copied
        # source files, since n_items is a recursive file count under dest.
        assert result["n_items"] == 5 * len(EXPORT_SOURCES) + _N_SCAFFOLDING_FILES

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
        assert first["n_items"] == len(EXPORT_SOURCES) + _N_SCAFFOLDING_FILES

        _write_fake_report_outputs(cfg, n_files_per_dir=3)
        second = build_replication_package(cfg, force=True)
        assert second["exported_to"] == first["exported_to"]
        assert second["n_items"] == 3 * len(EXPORT_SOURCES) + _N_SCAFFOLDING_FILES


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


# =============================================================================
# Sprint 2 (Product Engineering): embedded manifest
# =============================================================================


class TestEmbeddedManifest:
    def test_manifest_json_written_with_schema_version(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        manifest = json.loads(result["manifest_path"].read_text(encoding="utf-8"))
        assert manifest["manifest_schema_version"] == MANIFEST_SCHEMA_VERSION
        assert "export_provenance" in manifest
        assert manifest["export_provenance"]["stage"] == "export"
        assert manifest["historical_run_manifests"] == []

    def test_manifest_embeds_replication_target_and_zenodo_config(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        manifest = json.loads(result["manifest_path"].read_text(encoding="utf-8"))
        extras = manifest["export_provenance"]["extras"]
        assert extras["replication_target"] == cfg.settings.replication.target.value
        assert "replication_zenodo" in extras


# =============================================================================
# Sprint 2 (Product Engineering): codebook
# =============================================================================


class TestCodebook:
    def test_codebook_describes_every_copied_file(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg, n_files_per_dir=2)
        result = build_replication_package(cfg)
        codebook = json.loads(result["codebook_path"].read_text(encoding="utf-8"))
        assert len(codebook) == 2 * len(EXPORT_SOURCES)
        for name in EXPORT_SOURCES:
            assert f"{name}/file_0.txt" in codebook

    def test_codebook_excludes_its_own_scaffolding_files(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        codebook = json.loads(result["codebook_path"].read_text(encoding="utf-8"))
        assert "MANIFEST.json" not in codebook
        assert "CHECKSUMS.sha256" not in codebook

    def test_generate_codebook_describes_csv_columns(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "table.csv").write_text("a,b\n1,x\n2,y\n3,x\n", encoding="utf-8")
        codebook = generate_codebook(pkg)
        entry = codebook["table.csv"]
        assert entry["format"] == "csv"
        assert entry["n_rows"] == 3
        names = [c["name"] for c in entry["columns"]]
        assert names == ["a", "b"]

    def test_generate_codebook_never_raises_on_unreadable_file(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "broken.csv").write_bytes(b"\x00\x01not,a,real\xffcsv")
        codebook = generate_codebook(pkg)
        assert "broken.csv" in codebook
        assert codebook["broken.csv"]["format"] in ("unknown", "csv")

    def test_codebook_markdown_rendered_alongside_json(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        md_path = result["exported_to"] / "CODEBOOK.md"
        assert md_path.is_file()
        assert "# Codebook" in md_path.read_text(encoding="utf-8")


# =============================================================================
# Sprint 2 (Product Engineering): checksums
# =============================================================================


class TestChecksums:
    def test_checksums_file_written_in_sha256sum_format(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        lines = result["checksums_path"].read_text(encoding="utf-8").splitlines()
        assert lines
        for line in lines:
            digest, _, rel = line.partition("  ")
            assert len(digest) == 64
            assert rel

    def test_compute_checksums_excludes_the_checksums_file_itself(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "a.txt").write_text("hello", encoding="utf-8")
        (pkg / "CHECKSUMS.sha256").write_text("stale content", encoding="utf-8")
        checksums = compute_checksums(pkg)
        assert "a.txt" in checksums
        assert "CHECKSUMS.sha256" not in checksums

    def test_readme_is_not_checksummed_against_itself_inconsistently(self, tmp_path, monkeypatch):
        # README.md IS checksummed (it's a real, meaningful file) -- this
        # test just confirms it round-trips correctly through validation.
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        assert "README.md" in {
            line.partition("  ")[2]
            for line in result["checksums_path"].read_text(encoding="utf-8").splitlines()
        }


# =============================================================================
# Sprint 2 (Product Engineering): archive
# =============================================================================


class TestArchive:
    def test_archive_created_alongside_not_inside_the_package(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        archive_path = result["archive_path"]
        assert archive_path.parent == result["exported_to"].parent
        assert archive_path.suffix == ".zip"

    def test_no_archive_flag_skips_archive_creation(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg, archive=False)
        assert "archive_path" not in result

    def test_create_archive_rejects_unsupported_format(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "a.txt").write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="tar.gz"):
            create_archive(pkg, fmt="tar.gz")

    def test_archive_contains_every_package_file(self, tmp_path, monkeypatch):
        import zipfile

        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        with zipfile.ZipFile(result["archive_path"]) as zf:
            names = set(zf.namelist())
        assert "README.md" in names
        assert "MANIFEST.json" in names
        assert f"{EXPORT_SOURCES[0]}/file_0.txt" in names


# =============================================================================
# Sprint 2 (Product Engineering): self-validation
# =============================================================================


class TestSelfValidation:
    def test_freshly_built_package_validates_ok(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        assert result["validation"]["ok"] is True
        assert result["validation"]["issues"] == []

    def test_no_validate_flag_skips_validation(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg, validate=False)
        assert "validation" not in result

    def test_validate_replication_package_detects_tampered_file(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        dest = result["exported_to"]

        tampered = dest / EXPORT_SOURCES[0] / "file_0.txt"
        tampered.write_text("TAMPERED", encoding="utf-8")

        report = validate_replication_package(dest)
        assert report.ok is False
        assert any(f"{EXPORT_SOURCES[0]}/file_0.txt" in issue for issue in report.issues)

    def test_validate_replication_package_detects_missing_required_file(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        dest = result["exported_to"]

        (dest / "README.md").unlink()

        report = validate_replication_package(dest)
        assert report.ok is False
        assert any("README.md" in issue for issue in report.issues)

    def test_build_raises_reproducibility_error_when_self_validation_fails(self, tmp_path, monkeypatch):
        """Forces the self-validation-failure path inside
        build_replication_package itself (not just validate_replication_package
        standalone, already covered above) by monkeypatching
        validate_replication_package to simulate a corrupted build."""
        import finfluencer.reporting.replication as replication_module

        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)

        monkeypatch.setattr(
            replication_module,
            "validate_replication_package",
            lambda package_dir: replication_module.ValidationReport(ok=False, issues=["simulated corruption"]),
        )
        with pytest.raises(ReproducibilityError, match="self-validation"):
            build_replication_package(cfg)

    def test_validate_replication_package_standalone_on_valid_package(self, tmp_path, monkeypatch):
        """Confirms validate_replication_package works independent of
        build_replication_package having just run in this same process
        -- e.g. against a package re-extracted elsewhere."""
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        report = validate_replication_package(result["exported_to"])
        assert report.ok is True


# =============================================================================
# Sprint 2 (Product Engineering): publication-stage gate
# =============================================================================


class TestPublicationStageGate:
    def test_exploratory_stage_does_not_require_clean_git_tree(self, tmp_path, monkeypatch):
        # `_cfg()` pins the stage to "exploratory" explicitly (see its own docstring/comment --
        # as of the V1.0 Research Readiness freeze, config/settings.yaml's real default is
        # "submission", not "exploratory"). At "exploratory", the sandbox/CI working tree being
        # routinely dirty during development must not raise.
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        assert result["exported_to"].exists()

    def test_submission_stage_requires_clean_git_tree(self, tmp_path, monkeypatch):
        """Closes a real coverage gap the V1.0 freeze's `replication.stage` change surfaced:
        nothing previously proved the gate actually fires when a stricter stage IS selected --
        only that it correctly stays out of the way at "exploratory". Mocks `get_git_state`
        (already unit-tested in isolation, `tests/unit/test_core/test_reproducibility.py`)
        rather than depending on this sandbox's actual, uncontrolled git state."""
        import finfluencer.reporting.replication as replication_module

        # Deliberately not using _cfg() here -- it pins stage to "exploratory", the opposite of
        # what this test needs. Same output-path setup, stage set to "submission" instead.
        _set_tmp_output_paths(tmp_path, monkeypatch)
        monkeypatch.setenv("FINFLUENCER_REPLICATION__STAGE", "submission")
        cfg = load_settings(_SETTINGS, _ANALYSTS)
        _write_fake_report_outputs(cfg)
        monkeypatch.setattr(
            replication_module, "get_git_state",
            lambda: {"available": True, "dirty": True, "short_commit": "deadbee"},
        )

        with pytest.raises(ReproducibilityError):
            build_replication_package(cfg)


# =============================================================================
# Sprint 2 (Product Engineering): reproducibility
# =============================================================================


class TestReproducibility:
    """Generating the package twice from identical, already-materialized
    report outputs must produce equivalent contents except for the
    explicitly documented volatile fields in MANIFEST.json (run_id,
    timestamp_utc, extras) -- Product Engineering Sprint 2's own
    reproducibility requirement."""

    def test_two_builds_from_identical_inputs_match_every_checksum_except_manifest(
        self, tmp_path, monkeypatch,
    ):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg, n_files_per_dir=2)

        first = build_replication_package(cfg)
        second = build_replication_package(cfg)

        first_checksums = compute_checksums(first["exported_to"])
        second_checksums = compute_checksums(second["exported_to"])

        assert set(first_checksums.keys()) == set(second_checksums.keys())

        differing = {
            rel for rel in first_checksums
            if first_checksums[rel] != second_checksums[rel]
        }
        assert differing == {"MANIFEST.json"}

    def test_manifest_environment_and_git_fields_match_across_builds(self, tmp_path, monkeypatch):
        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)

        first = build_replication_package(cfg)
        second = build_replication_package(cfg)

        first_manifest = json.loads(first["manifest_path"].read_text(encoding="utf-8"))
        second_manifest = json.loads(second["manifest_path"].read_text(encoding="utf-8"))

        for key in ("environment", "git", "config_hashes", "study"):
            assert first_manifest["export_provenance"][key] == second_manifest["export_provenance"][key], key

        assert first_manifest["export_provenance"]["run_id"] != second_manifest["export_provenance"]["run_id"]

    def test_archive_internal_file_order_is_sorted_and_deterministic(self, tmp_path, monkeypatch):
        import zipfile

        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        with zipfile.ZipFile(result["archive_path"]) as zf:
            names = zf.namelist()
        assert names == sorted(names)

    def test_archive_entries_use_fixed_timestamp_not_export_time(self, tmp_path, monkeypatch):
        import zipfile

        cfg = _cfg(tmp_path, monkeypatch)
        _write_fake_report_outputs(cfg)
        result = build_replication_package(cfg)
        with zipfile.ZipFile(result["archive_path"]) as zf:
            for info in zf.infolist():
                assert info.date_time == (1980, 1, 1, 0, 0, 0)
