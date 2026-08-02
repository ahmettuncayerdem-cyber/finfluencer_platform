"""Tests for GenerateReportOrchestrator (BACKLOG.md T-025).

Exercises Application -> Domain -> (Domain-owned `IResultSnapshotReader`/repository interfaces)
-> the real T-025 `ResultSnapshotAdapter` -> real parquet fixtures, end to end -- not mocks
standing in for the whole chain. Only the three repositories are fakes (Persistence remains
abstract), same discipline as `test_start_analysis_run_orchestrator.py` (T-020).

Central integration proof (BACKLOG.md T-025's own Verification line): "topic + sentiment
AnalysisRun -> Report" -- covered by
`test_two_analysis_runs_of_different_types_cite_into_the_same_report`.
"""

from __future__ import annotations

import ast
import inspect
import uuid
from pathlib import Path

import pandas as pd
import pytest

from finfluencer.application.orchestrators import (
    GenerateReportCommand,
    GenerateReportOrchestrator,
)
from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.analysis_run import AnalysisRun, AnalysisRunStatus
from finfluencer.domain.entities.interpretation_record import InterpretationRecord
from finfluencer.domain.entities.report import Report
from finfluencer.infrastructure.reporting import ResultSnapshotAdapter
from finfluencer.utils.io import write_parquet


class FakeAnalysisRunRepository:
    """In-memory `IAnalysisRunRepository` double -- self-contained, same convention every
    orchestrator test file in this repo already follows."""

    def __init__(self) -> None:
        self._by_id: dict[EntityId, AnalysisRun] = {}

    def add(self, analysis_run: AnalysisRun, *, idempotency_key: str) -> None:
        self._by_id[analysis_run.id] = analysis_run

    def get_by_idempotency_key(self, project_id: EntityId, idempotency_key: str):
        return None

    def get_by_id(self, project_id: EntityId, analysis_run_id: EntityId) -> AnalysisRun | None:
        run = self._by_id.get(analysis_run_id)
        if run is None or run.project_id != project_id:
            return None
        return run


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
        self.added: list[InterpretationRecord] = []

    def add(self, record: InterpretationRecord) -> None:
        self.added.append(record)


def _project_id() -> EntityId:
    return EntityId(uuid.uuid4())


def _write_topics_output(base_root: Path, analysis_run_id: str) -> None:
    df = pd.DataFrame([{"comment_id": "c1", "topic_id": 0, "topic_label": "enflasyon"}])
    path = base_root / analysis_run_id / "data_processed" / "topics.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(df, path)


def _write_sentiment_output(base_root: Path, analysis_run_id: str) -> None:
    df = pd.DataFrame([{"comment_id": "c1", "sentiment_class": "positive", "sentiment_prob": 0.9}])
    path = base_root / analysis_run_id / "data_processed" / "sentiment.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(df, path)


def _completed_run(project_id: EntityId) -> AnalysisRun:
    run = AnalysisRun(
        project_id=project_id,
        collection_run_id=EntityId(uuid.uuid4()),
        analysis_type_id=EntityId(uuid.uuid4()),
        analysis_type_version="1.0.0",
    )
    run.start()
    run.complete()
    return run


def _make_orchestrator(base_root: Path, *, analysis_run_repository=None, report_repository=None):
    return GenerateReportOrchestrator(
        analysis_run_repository=analysis_run_repository or FakeAnalysisRunRepository(),
        report_repository=report_repository or FakeReportRepository(),
        interpretation_record_repository=FakeInterpretationRecordRepository(),
        snapshot_reader=ResultSnapshotAdapter(base_root=base_root),
    )


def test_execute_creates_a_new_report_from_a_completed_topics_run(tmp_path: Path) -> None:
    project_id = _project_id()
    run = _completed_run(project_id)
    _write_topics_output(tmp_path, str(run.id))

    ar_repo = FakeAnalysisRunRepository()
    ar_repo.add(run, idempotency_key="unused")
    orchestrator = _make_orchestrator(tmp_path, analysis_run_repository=ar_repo)

    result = orchestrator.execute(
        GenerateReportCommand(project_id=project_id, analysis_run_id=run.id),
    )

    assert result.project_id == project_id
    assert result.status == "draft"
    assert result.citation_count == 1


def test_two_analysis_runs_of_different_types_cite_into_the_same_report(tmp_path: Path) -> None:
    project_id = _project_id()
    topics_run = _completed_run(project_id)
    sentiment_run = _completed_run(project_id)
    _write_topics_output(tmp_path, str(topics_run.id))
    _write_sentiment_output(tmp_path, str(sentiment_run.id))

    ar_repo = FakeAnalysisRunRepository()
    ar_repo.add(topics_run, idempotency_key="unused")
    ar_repo.add(sentiment_run, idempotency_key="unused")
    report_repo = FakeReportRepository()
    orchestrator = _make_orchestrator(
        tmp_path, analysis_run_repository=ar_repo, report_repository=report_repo,
    )

    first = orchestrator.execute(
        GenerateReportCommand(project_id=project_id, analysis_run_id=topics_run.id),
    )
    second = orchestrator.execute(
        GenerateReportCommand(
            project_id=project_id,
            analysis_run_id=sentiment_run.id,
            existing_report_id=first.report_id,
        ),
    )

    assert second.report_id == first.report_id
    assert second.citation_count == 2
    stored_report = report_repo.get_by_id(project_id, first.report_id)
    assert len(stored_report.citation_ids) == 2


def test_execute_rejects_a_non_completed_analysis_run(tmp_path: Path) -> None:
    project_id = _project_id()
    run = AnalysisRun(
        project_id=project_id,
        collection_run_id=EntityId(uuid.uuid4()),
        analysis_type_id=EntityId(uuid.uuid4()),
        analysis_type_version="1.0.0",
    )  # still QUEUED, never started/completed
    ar_repo = FakeAnalysisRunRepository()
    ar_repo.add(run, idempotency_key="unused")
    orchestrator = _make_orchestrator(tmp_path, analysis_run_repository=ar_repo)

    with pytest.raises(ValueError, match="not completed"):
        orchestrator.execute(
            GenerateReportCommand(project_id=project_id, analysis_run_id=run.id),
        )


def test_execute_rejects_unknown_analysis_run_id(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    with pytest.raises(ValueError, match="No AnalysisRun found"):
        orchestrator.execute(
            GenerateReportCommand(project_id=_project_id(), analysis_run_id=EntityId(uuid.uuid4())),
        )


def test_execute_rejects_cross_project_analysis_run_access(tmp_path: Path) -> None:
    owner_project_id = _project_id()
    other_project_id = _project_id()
    run = _completed_run(owner_project_id)
    _write_topics_output(tmp_path, str(run.id))
    ar_repo = FakeAnalysisRunRepository()
    ar_repo.add(run, idempotency_key="unused")
    orchestrator = _make_orchestrator(tmp_path, analysis_run_repository=ar_repo)

    with pytest.raises(ValueError, match="No AnalysisRun found"):
        orchestrator.execute(
            GenerateReportCommand(project_id=other_project_id, analysis_run_id=run.id),
        )


def test_execute_rejects_unknown_existing_report_id(tmp_path: Path) -> None:
    project_id = _project_id()
    run = _completed_run(project_id)
    _write_topics_output(tmp_path, str(run.id))
    ar_repo = FakeAnalysisRunRepository()
    ar_repo.add(run, idempotency_key="unused")
    orchestrator = _make_orchestrator(tmp_path, analysis_run_repository=ar_repo)

    with pytest.raises(ValueError, match="No Report found"):
        orchestrator.execute(
            GenerateReportCommand(
                project_id=project_id, analysis_run_id=run.id,
                existing_report_id=EntityId(uuid.uuid4()),
            ),
        )


def test_orchestrator_module_never_imports_pandas_or_infrastructure() -> None:
    import finfluencer.application.orchestrators.generate_report as module

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
    assert "pandas" not in imported_modules
