"""Tests for Report entity (BACKLOG.md T-024).

Central acceptance criterion (BACKLOG.md T-024's own line): "a test asserting a Report's
citations are frozen snapshots, not live references." Covered two ways here: structurally (an
ast-based check that `report.py` never imports `AnalysisRun` at all) and behaviorally (citations
are stored as immutable `InterpretationRecord` ids, exposed only as a read-only tuple).
"""

from __future__ import annotations

import ast
import inspect
import uuid

import pytest

from finfluencer.domain.entities import (
    DomainInvariantViolation,
    EntityId,
    InterpretationRecord,
    InterpretationRecordKind,
    Report,
    ReportStatus,
)


def _project_id() -> EntityId:
    return EntityId(uuid.uuid4())


def _make_record() -> InterpretationRecord:
    return InterpretationRecord(
        analysis_run_id=EntityId(uuid.uuid4()),
        kind=InterpretationRecordKind.RAW_RESULT_SNAPSHOT,
        selector="sentiment.summary",
        content='{"positive": 12, "negative": 4}',
    )


def test_construction_succeeds_and_starts_in_draft() -> None:
    report = Report(project_id=_project_id())
    assert report.status is ReportStatus.DRAFT
    assert report.version == 1
    assert report.citation_ids == ()


def test_cannot_construct_without_project_id() -> None:
    with pytest.raises(ValueError, match="project_id"):
        Report(project_id=None)


def test_cannot_construct_with_version_below_one() -> None:
    with pytest.raises(ValueError, match="version"):
        Report(project_id=_project_id(), version=0)


def test_add_citation_stores_only_the_interpretation_record_id() -> None:
    report = Report(project_id=_project_id())
    record = _make_record()
    report.add_citation(record)
    assert report.citation_ids == (record.id,)


def test_add_citation_rejects_none() -> None:
    report = Report(project_id=_project_id())
    with pytest.raises(ValueError):
        report.add_citation(None)


def test_citation_ids_is_a_read_only_snapshot() -> None:
    report = Report(project_id=_project_id())
    report.add_citation(_make_record())
    ids = report.citation_ids
    assert isinstance(ids, tuple)
    with pytest.raises((AttributeError, TypeError)):
        ids.append(EntityId(uuid.uuid4()))  # type: ignore[attr-defined]
    # Mutating the returned tuple (impossible, above) must not be needed to prove isolation --
    # confirm a second call returns a value equal to the first, not a live view either.
    assert report.citation_ids == ids


def test_finalize_transitions_draft_to_finalized() -> None:
    report = Report(project_id=_project_id())
    report.finalize()
    assert report.status is ReportStatus.FINALIZED


def test_finalized_report_rejects_further_citation_and_refinalize() -> None:
    report = Report(project_id=_project_id())
    report.add_citation(_make_record())
    report.finalize()

    with pytest.raises(DomainInvariantViolation):
        report.add_citation(_make_record())
    with pytest.raises(DomainInvariantViolation):
        report.finalize()

    # Citations captured before finalization survive untouched.
    assert len(report.citation_ids) == 1


def test_report_has_no_unfinalize_method() -> None:
    report = Report(project_id=_project_id())
    assert not hasattr(Report, "unfinalize")
    assert not hasattr(report, "unfinalize")


def test_report_module_never_imports_analysisrun() -> None:
    # Section 10.0's own rule, verified structurally, not just by convention: "Report only
    # ever references InterpretationRecord entities, never a live AnalysisRun pointer."
    import finfluencer.domain.entities.report as module

    tree = ast.parse(inspect.getsource(module))
    imported_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_names.append(node.module)
            imported_names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported_names.extend(alias.name for alias in node.names)

    assert not any("analysis_run" in name.lower() for name in imported_names), (
        "report.py must never import AnalysisRun -- citations are InterpretationRecord ids "
        "only (section 10.0, line 479)"
    )


def test_report_has_no_analysis_run_id_attribute() -> None:
    report = Report(project_id=_project_id())
    assert not hasattr(report, "analysis_run_id")
