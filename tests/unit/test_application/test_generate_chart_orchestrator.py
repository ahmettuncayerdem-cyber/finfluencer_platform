"""Tests for GenerateChartOrchestrator (BACKLOG.md EPIC-10).

Mirrors `test_export_report_table_orchestrator.py` exactly (same fixtures, same fake
repositories, same citation-resolution scenarios) -- the two orchestrators share identical
resolution logic; only the Infrastructure dependency and its output differ. Exercises
Application -> Domain -> the real `ChartRendererAdapter` -> real parquet fixtures, end to end --
not mocks standing in for the whole chain.
"""

from __future__ import annotations

import ast
import inspect
import uuid
from pathlib import Path

import pandas as pd
import pytest

from finfluencer.application.orchestrators import GenerateChartCommand, GenerateChartOrchestrator
from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.analysis_run import AnalysisRun
from finfluencer.domain.entities.interpretation_record import (
    InterpretationRecord,
    InterpretationRecordKind,
)
from finfluencer.domain.entities.report import Report
from finfluencer.infrastructure.reporting import ChartRendererAdapter
from finfluencer.utils.io import write_parquet


class FakeAnalysisRunRepository:
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

    def save(self, analysis_run: AnalysisRun) -> None:
        # No-op (EPIC-07'): shared object reference already keeps `_by_id` correct.
        pass


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

    def save(self, report: Report) -> None:
        # No-op (EPIC-07'): shared object reference already keeps `_by_id` correct.
        pass


class FakeInterpretationRecordRepository:
    def __init__(self) -> None:
        self._by_id: dict[EntityId, InterpretationRecord] = {}

    def add(self, record: InterpretationRecord) -> None:
        self._by_id[record.id] = record

    def get_by_id(self, record_id: EntityId) -> InterpretationRecord | None:
        return self._by_id.get(record_id)


def _project_id() -> EntityId:
    return EntityId(uuid.uuid4())


def _completed_run(project_id: EntityId, collection_run_id: EntityId) -> AnalysisRun:
    run = AnalysisRun(
        project_id=project_id, collection_run_id=collection_run_id,
        analysis_type_id=EntityId(uuid.uuid4()), analysis_type_version="1.0.0",
    )
    run.start()
    run.complete()
    return run


def _write_comments(base_root: Path, collection_run_id: str) -> None:
    df = pd.DataFrame([
        {
            "comment_id": "c1", "video_id": "v1", "analyst_key": "satiroglu",
            "posted_date": "2026-01-01", "text_clean": "harika", "n_tokens": 1, "likes": 0,
        },
    ])
    path = base_root / collection_run_id / "data_raw" / "comments.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(df, path)


def _write_topics(base_root: Path, analysis_run_id: str) -> None:
    df = pd.DataFrame([
        {"comment_id": "c1", "configuration": "pooled", "topic_id": 0, "topic_label": "x", "topic_prob": 0.9},
        {"comment_id": "c1", "configuration": "within_analyst", "topic_id": 0, "topic_label": "x"},
    ])
    path = base_root / analysis_run_id / "data_processed" / "topics.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(df, path)


def _write_sentiment(base_root: Path, analysis_run_id: str) -> None:
    df = pd.DataFrame([{"comment_id": "c1", "sentiment_class": "positive", "sentiment_prob": 0.9}])
    path = base_root / analysis_run_id / "data_processed" / "sentiment.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(df, path)


def _record_for(run: AnalysisRun) -> InterpretationRecord:
    return InterpretationRecord(
        analysis_run_id=run.id, kind=InterpretationRecordKind.RAW_RESULT_SNAPSHOT,
        selector="full_result", content='{"placeholder": true}',
    )


def _report_citing_topics_and_sentiment(
    tmp_path: Path,
) -> tuple[Path, EntityId, Report, FakeAnalysisRunRepository, FakeInterpretationRecordRepository, FakeReportRepository]:
    base_root = tmp_path / "runs"
    project_id = _project_id()
    collection_run_id = EntityId(uuid.uuid4())
    _write_comments(base_root, str(collection_run_id))

    topics_run = _completed_run(project_id, collection_run_id)
    sentiment_run = _completed_run(project_id, collection_run_id)
    _write_topics(base_root, str(topics_run.id))
    _write_sentiment(base_root, str(sentiment_run.id))

    ar_repo = FakeAnalysisRunRepository()
    ar_repo.add(topics_run, idempotency_key="unused")
    ar_repo.add(sentiment_run, idempotency_key="unused")

    ir_repo = FakeInterpretationRecordRepository()
    topics_record = _record_for(topics_run)
    sentiment_record = _record_for(sentiment_run)
    ir_repo.add(topics_record)
    ir_repo.add(sentiment_record)

    report = Report(project_id=project_id)
    report.add_citation(topics_record)
    report.add_citation(sentiment_record)
    report_repo = FakeReportRepository()
    report_repo.add(report)

    return base_root, project_id, report, ar_repo, ir_repo, report_repo


@pytest.mark.parametrize("chart_type", ["topics", "sentiment"])
def test_execute_renders_a_chart_for_a_report_citing_topics_and_sentiment_runs(
    tmp_path: Path, chart_type: str,
) -> None:
    base_root, project_id, report, ar_repo, ir_repo, report_repo = (
        _report_citing_topics_and_sentiment(tmp_path)
    )

    orchestrator = GenerateChartOrchestrator(
        report_repository=report_repo,
        interpretation_record_repository=ir_repo,
        analysis_run_repository=ar_repo,
        chart_renderer=ChartRendererAdapter(base_root=base_root),
    )
    output_path = tmp_path / f"{chart_type}.png"

    result = orchestrator.execute(
        GenerateChartCommand(
            project_id=project_id, report_id=report.id, chart_type=chart_type,
            output_path=str(output_path),
        ),
    )

    assert result.chart_type == chart_type
    assert result.byte_count > 0
    assert output_path.exists()
    assert output_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_execute_rejects_report_citing_two_different_collection_runs(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    project_id = _project_id()
    cr_a = EntityId(uuid.uuid4())
    cr_b = EntityId(uuid.uuid4())
    _write_comments(base_root, str(cr_a))
    _write_comments(base_root, str(cr_b))

    run_a = _completed_run(project_id, cr_a)
    run_b = _completed_run(project_id, cr_b)
    _write_topics(base_root, str(run_a.id))
    _write_sentiment(base_root, str(run_b.id))

    ar_repo = FakeAnalysisRunRepository()
    ar_repo.add(run_a, idempotency_key="unused")
    ar_repo.add(run_b, idempotency_key="unused")

    ir_repo = FakeInterpretationRecordRepository()
    record_a = _record_for(run_a)
    record_b = _record_for(run_b)
    ir_repo.add(record_a)
    ir_repo.add(record_b)

    report = Report(project_id=project_id)
    report.add_citation(record_a)
    report.add_citation(record_b)
    report_repo = FakeReportRepository()
    report_repo.add(report)

    orchestrator = GenerateChartOrchestrator(
        report_repository=report_repo,
        interpretation_record_repository=ir_repo,
        analysis_run_repository=ar_repo,
        chart_renderer=ChartRendererAdapter(base_root=base_root),
    )

    with pytest.raises(ValueError, match="more than one CollectionRun"):
        orchestrator.execute(
            GenerateChartCommand(
                project_id=project_id, report_id=report.id, chart_type="topics",
                output_path=str(tmp_path / "chart.png"),
            ),
        )


def test_execute_rejects_report_with_no_citations(tmp_path: Path) -> None:
    project_id = _project_id()
    report = Report(project_id=project_id)
    report_repo = FakeReportRepository()
    report_repo.add(report)

    orchestrator = GenerateChartOrchestrator(
        report_repository=report_repo,
        interpretation_record_repository=FakeInterpretationRecordRepository(),
        analysis_run_repository=FakeAnalysisRunRepository(),
        chart_renderer=ChartRendererAdapter(base_root=tmp_path),
    )

    with pytest.raises(ValueError, match="no citations"):
        orchestrator.execute(
            GenerateChartCommand(
                project_id=project_id, report_id=report.id, chart_type="topics",
                output_path=str(tmp_path / "chart.png"),
            ),
        )


def test_execute_rejects_unknown_report_id(tmp_path: Path) -> None:
    orchestrator = GenerateChartOrchestrator(
        report_repository=FakeReportRepository(),
        interpretation_record_repository=FakeInterpretationRecordRepository(),
        analysis_run_repository=FakeAnalysisRunRepository(),
        chart_renderer=ChartRendererAdapter(base_root=tmp_path),
    )

    with pytest.raises(ValueError, match="No Report found"):
        orchestrator.execute(
            GenerateChartCommand(
                project_id=_project_id(), report_id=EntityId(uuid.uuid4()), chart_type="topics",
                output_path=str(tmp_path / "chart.png"),
            ),
        )


def test_orchestrator_module_never_imports_pandas_or_infrastructure() -> None:
    import finfluencer.application.orchestrators.generate_chart as module

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
