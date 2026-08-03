"""Tests for FinalizeReportOrchestrator (BACKLOG.md T-027)."""

from __future__ import annotations

import ast
import inspect
import uuid

import pytest

from finfluencer.application.orchestrators import (
    FinalizeReportCommand,
    FinalizeReportOrchestrator,
)
from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.report import Report, ReportStatus


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


def test_execute_finalizes_a_draft_report() -> None:
    project_id = _project_id()
    report = Report(project_id=project_id)
    repo = FakeReportRepository()
    repo.add(report)
    orchestrator = FinalizeReportOrchestrator(report_repository=repo)

    result = orchestrator.execute(
        FinalizeReportCommand(project_id=project_id, report_id=report.id),
    )

    assert result.status == ReportStatus.FINALIZED.value
    assert report.status is ReportStatus.FINALIZED


def test_execute_is_idempotent_for_an_already_finalized_report() -> None:
    project_id = _project_id()
    report = Report(project_id=project_id)
    report.finalize()
    repo = FakeReportRepository()
    repo.add(report)
    orchestrator = FinalizeReportOrchestrator(report_repository=repo)

    result = orchestrator.execute(
        FinalizeReportCommand(project_id=project_id, report_id=report.id),
    )

    assert result.status == ReportStatus.FINALIZED.value


def test_execute_called_twice_does_not_raise() -> None:
    project_id = _project_id()
    report = Report(project_id=project_id)
    repo = FakeReportRepository()
    repo.add(report)
    orchestrator = FinalizeReportOrchestrator(report_repository=repo)
    command = FinalizeReportCommand(project_id=project_id, report_id=report.id)

    orchestrator.execute(command)
    result = orchestrator.execute(command)  # no-op, must not raise DomainInvariantViolation

    assert result.status == ReportStatus.FINALIZED.value


def test_execute_rejects_unknown_report_id() -> None:
    orchestrator = FinalizeReportOrchestrator(report_repository=FakeReportRepository())

    with pytest.raises(ValueError, match="No Report found"):
        orchestrator.execute(
            FinalizeReportCommand(project_id=_project_id(), report_id=EntityId(uuid.uuid4())),
        )


def test_orchestrator_module_never_imports_infrastructure_or_reportlab() -> None:
    import finfluencer.application.orchestrators.finalize_report as module

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
    assert "reportlab" not in imported_modules
