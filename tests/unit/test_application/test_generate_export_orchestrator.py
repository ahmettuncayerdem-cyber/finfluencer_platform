"""Tests for GenerateExportOrchestrator (BACKLOG.md T-027).

Exercises Application -> Domain -> the real T-027 `PdfRendererAdapter` end to end for the happy
path (not a mock standing in for the whole chain), same discipline as
`test_export_report_table_orchestrator.py` (T-026). A counting fake renderer proves the
idempotency contract (no second render on a repeat call) without needing to inspect PDF bytes
for that assertion.
"""

from __future__ import annotations

import ast
import inspect
import uuid
from pathlib import Path

import pytest

from finfluencer.application.orchestrators import (
    GenerateExportCommand,
    GenerateExportOrchestrator,
)
from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.export import Export, ExportFormat
from finfluencer.domain.entities.interpretation_record import (
    InterpretationRecord,
    InterpretationRecordKind,
)
from finfluencer.domain.entities.report import Report
from finfluencer.infrastructure.reporting import PdfRendererAdapter


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


class FakeInterpretationRecordRepository:
    def __init__(self) -> None:
        self._by_id: dict[EntityId, InterpretationRecord] = {}

    def add(self, record: InterpretationRecord) -> None:
        self._by_id[record.id] = record

    def get_by_id(self, record_id: EntityId) -> InterpretationRecord | None:
        return self._by_id.get(record_id)


class FakeExportRepository:
    def __init__(self) -> None:
        self._exports: list[Export] = []

    def add(self, export: Export) -> None:
        self._exports.append(export)

    def get_by_report_version_and_format(
        self, report_id: EntityId, report_version: int, format: ExportFormat,
    ) -> Export | None:
        for export in self._exports:
            if (
                export.report_id == report_id
                and export.report_version == report_version
                and export.format == format
            ):
                return export
        return None


class CountingPdfRenderer:
    """Spy renderer -- proves `GenerateExportOrchestrator` never re-renders once an Export for
    the same `(report_id, report_version, format)` already exists.
    """

    def __init__(self) -> None:
        self.call_count = 0

    def render(
        self, report_id: str, report_version: int, citations: list, output_path: str,
    ) -> int:
        self.call_count += 1
        Path(output_path).write_bytes(b"%PDF-1.4 fake")
        return 1


def _project_id() -> EntityId:
    return EntityId(uuid.uuid4())


def _record() -> InterpretationRecord:
    return InterpretationRecord(
        analysis_run_id=EntityId(uuid.uuid4()), kind=InterpretationRecordKind.RAW_RESULT_SNAPSHOT,
        selector="full_result", content='{"topic_label": "enflasyon"}',
    )


def test_execute_generates_a_real_pdf_for_a_finalized_report_with_citations(
    tmp_path: Path,
) -> None:
    project_id = _project_id()
    report = Report(project_id=project_id)
    record = _record()
    report.add_citation(record)
    report.finalize()

    report_repo = FakeReportRepository()
    report_repo.add(report)
    record_repo = FakeInterpretationRecordRepository()
    record_repo.add(record)
    export_repo = FakeExportRepository()

    orchestrator = GenerateExportOrchestrator(
        report_repository=report_repo,
        interpretation_record_repository=record_repo,
        export_repository=export_repo,
        pdf_renderer=PdfRendererAdapter(),
    )
    output_path = tmp_path / "report.pdf"

    result = orchestrator.execute(
        GenerateExportCommand(
            project_id=project_id, report_id=report.id, output_path=str(output_path),
        ),
    )

    assert output_path.exists()
    assert result.page_count is not None and result.page_count >= 1
    assert len(export_repo._exports) == 1
    persisted = export_repo._exports[0]
    assert persisted.report_id == report.id
    assert persisted.report_version == report.version
    assert persisted.format is ExportFormat.PDF


def test_execute_is_idempotent_and_does_not_re_render(tmp_path: Path) -> None:
    project_id = _project_id()
    report = Report(project_id=project_id)
    record = _record()
    report.add_citation(record)
    report.finalize()

    report_repo = FakeReportRepository()
    report_repo.add(report)
    record_repo = FakeInterpretationRecordRepository()
    record_repo.add(record)
    export_repo = FakeExportRepository()
    renderer = CountingPdfRenderer()

    orchestrator = GenerateExportOrchestrator(
        report_repository=report_repo,
        interpretation_record_repository=record_repo,
        export_repository=export_repo,
        pdf_renderer=renderer,
    )
    command = GenerateExportCommand(
        project_id=project_id, report_id=report.id, output_path=str(tmp_path / "report.pdf"),
    )

    first = orchestrator.execute(command)
    second = orchestrator.execute(command)

    assert renderer.call_count == 1
    assert first.export_id == second.export_id
    assert len(export_repo._exports) == 1


def test_execute_rejects_a_draft_report(tmp_path: Path) -> None:
    project_id = _project_id()
    report = Report(project_id=project_id)
    report.add_citation(_record())
    report_repo = FakeReportRepository()
    report_repo.add(report)

    orchestrator = GenerateExportOrchestrator(
        report_repository=report_repo,
        interpretation_record_repository=FakeInterpretationRecordRepository(),
        export_repository=FakeExportRepository(),
        pdf_renderer=CountingPdfRenderer(),
    )

    with pytest.raises(ValueError, match="not finalized"):
        orchestrator.execute(
            GenerateExportCommand(
                project_id=project_id, report_id=report.id,
                output_path=str(tmp_path / "report.pdf"),
            ),
        )


def test_execute_rejects_a_finalized_report_with_no_citations(tmp_path: Path) -> None:
    project_id = _project_id()
    report = Report(project_id=project_id)
    report.finalize()
    report_repo = FakeReportRepository()
    report_repo.add(report)

    orchestrator = GenerateExportOrchestrator(
        report_repository=report_repo,
        interpretation_record_repository=FakeInterpretationRecordRepository(),
        export_repository=FakeExportRepository(),
        pdf_renderer=CountingPdfRenderer(),
    )

    with pytest.raises(ValueError, match="no citations"):
        orchestrator.execute(
            GenerateExportCommand(
                project_id=project_id, report_id=report.id,
                output_path=str(tmp_path / "report.pdf"),
            ),
        )


def test_execute_rejects_unknown_report_id(tmp_path: Path) -> None:
    orchestrator = GenerateExportOrchestrator(
        report_repository=FakeReportRepository(),
        interpretation_record_repository=FakeInterpretationRecordRepository(),
        export_repository=FakeExportRepository(),
        pdf_renderer=CountingPdfRenderer(),
    )

    with pytest.raises(ValueError, match="No Report found"):
        orchestrator.execute(
            GenerateExportCommand(
                project_id=_project_id(), report_id=EntityId(uuid.uuid4()),
                output_path=str(tmp_path / "report.pdf"),
            ),
        )


def test_execute_rejects_non_pdf_format(tmp_path: Path) -> None:
    project_id = _project_id()
    report = Report(project_id=project_id)
    report.add_citation(_record())
    report.finalize()
    report_repo = FakeReportRepository()
    report_repo.add(report)

    orchestrator = GenerateExportOrchestrator(
        report_repository=report_repo,
        interpretation_record_repository=FakeInterpretationRecordRepository(),
        export_repository=FakeExportRepository(),
        pdf_renderer=CountingPdfRenderer(),
    )

    class _FakeWordFormat:
        """Stand-in for a hypothetical non-PDF `ExportFormat` member -- none exists yet, so this
        proves the guard triggers on "anything that isn't PDF", not just a specific enum member.
        """

    with pytest.raises(ValueError, match="only supports ExportFormat.PDF"):
        orchestrator.execute(
            GenerateExportCommand(
                project_id=project_id, report_id=report.id,
                output_path=str(tmp_path / "report.pdf"),
                format=_FakeWordFormat(),  # type: ignore[arg-type]
            ),
        )


def test_orchestrator_module_never_imports_reportlab_or_infrastructure() -> None:
    import finfluencer.application.orchestrators.generate_export as module

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
