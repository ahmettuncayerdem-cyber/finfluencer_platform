"""Tests for MasterTableExportAdapter (BACKLOG.md T-026).

Central proof this task's own Migration Risk Checklist requires: `build_master_table()`/
`save_master_table()` are called with zero behavioral deviation -- verified by a differential
test comparing this adapter's output against calling the wrapped functions directly on the same
fixture.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pandas as pd
import pytest

from finfluencer.core.contracts import ModelReference
from finfluencer.infrastructure.reporting import MasterTableExportAdapter
from finfluencer.reporting.master_table import build_master_table
from finfluencer.utils.io import read_parquet, write_parquet


class _FakeTopicsConfig:
    """Minimal stand-in carrying only what `MasterTableExportAdapter` reads
    (`.embedding_model.name`/`.revision`) -- avoids constructing the real,
    much heavier `TopicsConfig` (umap/hdbscan/configurations) for a test
    that only exercises this one field, same pattern
    `test_sentiment_adapter.py`'s own `_FakeSettings` already established."""

    def __init__(self, model: ModelReference) -> None:
        self.embedding_model = model


class _FakeSentimentConfig:
    def __init__(self, model: ModelReference) -> None:
        self.primary_model = model


class _FakeSettings:
    def __init__(self, *, topics_model: ModelReference, sentiment_model: ModelReference) -> None:
        self.topics = _FakeTopicsConfig(topics_model)
        self.sentiment = _FakeSentimentConfig(sentiment_model)


def _write_fixture(base_root: Path, *, collection_run_id: str, topics_run_id: str, sentiment_run_id: str) -> None:
    comments_df = pd.DataFrame([
        {
            "comment_id": "c1", "video_id": "v1", "analyst_key": "satiroglu",
            "posted_date": "2026-01-01", "text_clean": "harika bir gelisme",
            "n_tokens": 3, "likes": 5,
        },
        {
            "comment_id": "c2", "video_id": "v1", "analyst_key": "gecer",
            "posted_date": "2026-01-02", "text_clean": "kotu bir haber",
            "n_tokens": 3, "likes": 1,
        },
    ])
    comments_path = base_root / collection_run_id / "data_raw" / "comments.parquet"
    comments_path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(comments_df, comments_path)

    topics_df = pd.DataFrame([
        {"comment_id": "c1", "configuration": "pooled", "topic_id": 0, "topic_label": "enflasyon", "topic_prob": 0.9},
        {"comment_id": "c2", "configuration": "pooled", "topic_id": 1, "topic_label": "faiz", "topic_prob": 0.8},
        {"comment_id": "c1", "configuration": "within_analyst", "topic_id": 0, "topic_label": "enflasyon"},
        {"comment_id": "c2", "configuration": "within_analyst", "topic_id": 1, "topic_label": "faiz"},
    ])
    topics_path = base_root / topics_run_id / "data_processed" / "topics.parquet"
    topics_path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(topics_df, topics_path)

    sentiment_df = pd.DataFrame([
        {"comment_id": "c1", "sentiment_class": "positive", "sentiment_prob": 0.9},
        {"comment_id": "c2", "sentiment_class": "negative", "sentiment_prob": 0.1},
    ])
    sentiment_path = base_root / sentiment_run_id / "data_processed" / "sentiment.parquet"
    sentiment_path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(sentiment_df, sentiment_path)


def test_export_produces_output_identical_to_calling_build_master_table_directly(
    tmp_path: Path,
) -> None:
    base_root = tmp_path / "runs"
    collection_run_id = "cr-1"
    topics_run_id = "ar-topics-1"
    sentiment_run_id = "ar-sentiment-1"
    _write_fixture(
        base_root, collection_run_id=collection_run_id,
        topics_run_id=topics_run_id, sentiment_run_id=sentiment_run_id,
    )

    # Reference: call the wrapped functions directly.
    expected_df = build_master_table(
        comments_path=base_root / collection_run_id / "data_raw" / "comments.parquet",
        topics_path=base_root / topics_run_id / "data_processed" / "topics.parquet",
        sentiment_path=base_root / sentiment_run_id / "data_processed" / "sentiment.parquet",
    )

    adapter = MasterTableExportAdapter(base_root=base_root)
    output_path = tmp_path / "export.csv"
    row_count = adapter.export(
        collection_run_id=collection_run_id,
        analysis_run_ids=[topics_run_id, sentiment_run_id],
        output_path=str(output_path),
    )

    assert row_count == len(expected_df) == 2
    written_df = pd.read_csv(output_path, parse_dates=["posted_date"])
    expected_csv_df = expected_df.copy()
    expected_csv_df["posted_date"] = pd.to_datetime(expected_csv_df["posted_date"])
    pd.testing.assert_frame_equal(
        written_df.reset_index(drop=True), expected_csv_df.reset_index(drop=True),
    )


def test_export_without_settings_adds_no_provenance_columns(tmp_path: Path) -> None:
    """`settings=None` (the default, and every pre-existing call site's behavior) must reproduce
    the exact prior column set -- the V1.0-freeze provenance columns are opt-in only."""
    base_root = tmp_path / "runs"
    collection_run_id = "cr-1"
    topics_run_id = "ar-topics-1"
    sentiment_run_id = "ar-sentiment-1"
    _write_fixture(
        base_root, collection_run_id=collection_run_id,
        topics_run_id=topics_run_id, sentiment_run_id=sentiment_run_id,
    )

    adapter = MasterTableExportAdapter(base_root=base_root)
    output_path = tmp_path / "export.csv"
    adapter.export(
        collection_run_id=collection_run_id,
        analysis_run_ids=[topics_run_id, sentiment_run_id],
        output_path=str(output_path),
    )

    written_df = pd.read_csv(output_path)
    for provenance_column in (
        "sentiment_analysis_run_id", "sentiment_model_name", "sentiment_model_revision",
        "topics_analysis_run_id", "topics_model_name", "topics_model_revision",
    ):
        assert provenance_column not in written_df.columns


def test_export_with_settings_stamps_provenance_columns_on_every_row(tmp_path: Path) -> None:
    """With `settings` given, every exported row must be traceable to the exact
    `analysis_run_id`/model+revision that produced it -- closes the gap
    `docs/implementation/V1.0_RESEARCH_READINESS_AUDIT.md` section 6 found: a reviewer could not
    previously determine which model/run produced a given CSV row without manually
    cross-referencing a separate `provenance.json`."""
    base_root = tmp_path / "runs"
    collection_run_id = "cr-3"
    topics_run_id = "ar-topics-3"
    sentiment_run_id = "ar-sentiment-3"
    _write_fixture(
        base_root, collection_run_id=collection_run_id,
        topics_run_id=topics_run_id, sentiment_run_id=sentiment_run_id,
    )
    settings = _FakeSettings(
        topics_model=ModelReference(name="paraphrase-multilingual-MiniLM-L12-v2", revision="e8f8c21"),
        sentiment_model=ModelReference(name="bert-base-turkish-sentiment-cased", revision="f607086"),
    )

    adapter = MasterTableExportAdapter(base_root=base_root, settings=settings)
    output_path = tmp_path / "export.csv"
    row_count = adapter.export(
        collection_run_id=collection_run_id,
        analysis_run_ids=[topics_run_id, sentiment_run_id],
        output_path=str(output_path),
    )

    written_df = pd.read_csv(output_path)
    assert row_count == len(written_df) == 2
    assert (written_df["topics_analysis_run_id"] == topics_run_id).all()
    assert (written_df["topics_model_name"] == "paraphrase-multilingual-MiniLM-L12-v2").all()
    assert (written_df["topics_model_revision"] == "e8f8c21").all()
    assert (written_df["sentiment_analysis_run_id"] == sentiment_run_id).all()
    assert (written_df["sentiment_model_name"] == "bert-base-turkish-sentiment-cased").all()
    assert (written_df["sentiment_model_revision"] == "f607086").all()


def test_export_raises_file_not_found_when_sentiment_output_missing(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    collection_run_id = "cr-2"
    topics_run_id = "ar-topics-2"
    comments_df = pd.DataFrame([{"comment_id": "c1"}])
    comments_path = base_root / collection_run_id / "data_raw" / "comments.parquet"
    comments_path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(comments_df, comments_path)
    topics_path = base_root / topics_run_id / "data_processed" / "topics.parquet"
    topics_path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(pd.DataFrame([{"comment_id": "c1"}]), topics_path)

    adapter = MasterTableExportAdapter(base_root=base_root)
    with pytest.raises(FileNotFoundError):
        adapter.export(
            collection_run_id=collection_run_id,
            analysis_run_ids=[topics_run_id],
            output_path=str(tmp_path / "export.csv"),
        )


def test_export_rejects_empty_collection_run_id(tmp_path: Path) -> None:
    adapter = MasterTableExportAdapter(base_root=tmp_path)
    with pytest.raises(ValueError):
        adapter.export(collection_run_id="", analysis_run_ids=["ar-1"], output_path="out.csv")


def test_export_rejects_empty_analysis_run_ids(tmp_path: Path) -> None:
    adapter = MasterTableExportAdapter(base_root=tmp_path)
    with pytest.raises(ValueError):
        adapter.export(collection_run_id="cr-1", analysis_run_ids=[], output_path="out.csv")


def test_adapter_module_does_not_import_presentation_or_api() -> None:
    import finfluencer.infrastructure.reporting.table_export_adapter as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)


def test_adapter_never_modifies_wrapped_legacy_module() -> None:
    import finfluencer.infrastructure.reporting.table_export_adapter as module

    source = inspect.getsource(module)
    for forbidden in ("setattr(", "monkeypatch", "importlib.reload"):
        assert forbidden not in source
