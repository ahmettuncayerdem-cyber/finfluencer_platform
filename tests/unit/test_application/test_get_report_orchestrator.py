"""Tests for GetReportOrchestrator (BACKLOG.md T-028)."""

from __future__ import annotations

import ast
import inspect
import uuid

import pytest

from finfluencer.application.orchestrators import GetReportCommand, GetReportOrchestrator
from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.report import Report, ReportStatus
from finfluencer.domain.entities.interpretation_record import (
    InterpretationRecord,
    InterpretationRecordKind,
)


class FakeReportRepository:
    def __init__(self) -> None:
        self._by_id: dict[EntityId, Report] = {}

    def add(self, report: Report) -> None:
        self._by_id[report.id] = report

    def get_by_id(self, project_id: EntityId, report_id: EntityId) -> Report | None:
        report = self._by_id.get(report_id)
        if report is None or report.project_id != project_id:
            return None
        return report


def _project_id() -> EntityId:
    return EntityId(uuid.uuid4())


def test_execute_returns_report_shape_matching_its_domain_state() -> None:
    project_id = _project_id()
    report = Report(project_id=project_id)
    record = InterpretationRecord(
        analysis_run_id=EntityId(uuid.uuid4()), kind=InterpretationRecordKind.RAW_RESULT_SNAPSHOT,
        selector="full_result", content='{"x": 1}',
    )
    report.add_citation(record)
    repo = FakeReportRepository()
    repo.add(report)
    orchestrator = GetReportOrchestrator(report_repository=repo)

    result = orchestrator.execute(GetReportCommand(project_id=project_id, report_id=report.id))

    assert result.report_id == report.id
    assert result.project_id == project_id
    assert result.version == 1
    assert result.status == ReportStatus.DRAFT.value
    assert result.citation_count == 1


def test_execute_reflects_finalized_status() -> None:
    project_id = _project_id()
    report = Report(project_id=project_id)
    report.finalize()
    repo = FakeReportRepository()
    repo.add(report)
    orchestrator = GetReportOrchestrator(report_repository=repo)

    result = orchestrator.execute(GetReportCommand(project_id=project_id, report_id=report.id))

    assert result.status == ReportStatus.FINALIZED.value


def test_execute_rejects_unknown_report_id() -> None:
    orchestrator = GetReportOrchestrator(report_repository=FakeReportRepository())

    with pytest.raises(ValueError, match="No Report found"):
        orchestrator.execute(
            GetReportCommand(project_id=_project_id(), report_id=EntityId(uuid.uuid4())),
        )


def test_execute_rejects_a_report_belonging_to_another_project() -> None:
    project_id = _project_id()
    other_project_id = _project_id()
    report = Report(project_id=project_id)
    repo = FakeReportRepository()
    repo.add(report)
    orchestrator = GetReportOrchestrator(report_repository=repo)

    with pytest.raises(ValueError, match="No Report found"):
        orchestrator.execute(
            GetReportCommand(project_id=other_project_id, report_id=report.id),
        )


def test_orchestrator_module_never_imports_infrastructure_presentation_or_api() -> None:
    import finfluencer.application.orchestrators.get_report as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.infrastructure") for m in imported_modules)
    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)
