"""Tests for ResultSnapshotAdapter (BACKLOG.md T-025)."""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pandas as pd
import pytest

from finfluencer.infrastructure.reporting import ResultSnapshotAdapter
from finfluencer.utils.io import write_parquet


def _write_topics_output(base_root: Path, analysis_run_id: str) -> None:
    df = pd.DataFrame([
        {"comment_id": "c1", "topic_id": 0, "topic_label": "enflasyon"},
        {"comment_id": "c2", "topic_id": 1, "topic_label": "faiz"},
    ])
    path = base_root / analysis_run_id / "data_processed" / "topics.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(df, path)


def _write_sentiment_output(base_root: Path, analysis_run_id: str) -> None:
    df = pd.DataFrame([
        {"comment_id": "c1", "sentiment_class": "positive", "sentiment_prob": 0.9},
        {"comment_id": "c2", "sentiment_class": "negative", "sentiment_prob": 0.1},
    ])
    path = base_root / analysis_run_id / "data_processed" / "sentiment.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(df, path)


def test_read_returns_json_records_of_topics_output(tmp_path: Path) -> None:
    _write_topics_output(tmp_path, "ar-topics-1")
    adapter = ResultSnapshotAdapter(base_root=tmp_path)

    content = adapter.read("ar-topics-1")

    records = json.loads(content)
    assert len(records) == 2
    assert records[0]["comment_id"] == "c1"
    assert records[0]["topic_label"] == "enflasyon"


def test_read_returns_json_records_of_sentiment_output(tmp_path: Path) -> None:
    _write_sentiment_output(tmp_path, "ar-sentiment-1")
    adapter = ResultSnapshotAdapter(base_root=tmp_path)

    content = adapter.read("ar-sentiment-1")

    records = json.loads(content)
    assert len(records) == 2
    assert records[0]["sentiment_class"] == "positive"


def test_read_raises_file_not_found_when_no_known_output_exists(tmp_path: Path) -> None:
    adapter = ResultSnapshotAdapter(base_root=tmp_path)
    with pytest.raises(FileNotFoundError):
        adapter.read("ar-missing")


def test_read_raises_value_error_when_both_known_outputs_exist(tmp_path: Path) -> None:
    _write_topics_output(tmp_path, "ar-ambiguous")
    _write_sentiment_output(tmp_path, "ar-ambiguous")
    adapter = ResultSnapshotAdapter(base_root=tmp_path)
    with pytest.raises(ValueError):
        adapter.read("ar-ambiguous")


def test_read_rejects_empty_analysis_run_id(tmp_path: Path) -> None:
    adapter = ResultSnapshotAdapter(base_root=tmp_path)
    with pytest.raises(ValueError):
        adapter.read("")


def test_adapter_module_does_not_import_presentation_or_api() -> None:
    import finfluencer.infrastructure.reporting.snapshot_adapter as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)
