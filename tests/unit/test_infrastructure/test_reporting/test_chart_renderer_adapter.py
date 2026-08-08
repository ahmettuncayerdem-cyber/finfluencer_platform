"""Tests for ChartRendererAdapter (BACKLOG.md EPIC-10).

Mirrors `test_table_export_adapter.py`'s own fixture shape exactly (same file layout
convention: `base_root/{run_id}/data_raw|data_processed/*.parquet`) -- the two adapters resolve
input identically, per `chart_renderer_adapter.py`'s own docstring.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pandas as pd
import pytest

from finfluencer.infrastructure.reporting import ChartRendererAdapter
from finfluencer.utils.io import write_parquet


def _write_fixture(
    base_root: Path, *, collection_run_id: str, topics_run_id: str, sentiment_run_id: str,
) -> None:
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
        {
            "comment_id": "c3", "video_id": "v1", "analyst_key": "gecer",
            "posted_date": "2026-01-03", "text_clean": "yine kotu bir haber",
            "n_tokens": 4, "likes": 0,
        },
    ])
    comments_path = base_root / collection_run_id / "data_raw" / "comments.parquet"
    comments_path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(comments_df, comments_path)

    topics_df = pd.DataFrame([
        {"comment_id": "c1", "configuration": "pooled", "topic_id": 0, "topic_label": "enflasyon", "topic_prob": 0.9},
        {"comment_id": "c2", "configuration": "pooled", "topic_id": 1, "topic_label": "faiz", "topic_prob": 0.8},
        {"comment_id": "c3", "configuration": "pooled", "topic_id": 1, "topic_label": "faiz", "topic_prob": 0.7},
        {"comment_id": "c1", "configuration": "within_analyst", "topic_id": 0, "topic_label": "enflasyon"},
        {"comment_id": "c2", "configuration": "within_analyst", "topic_id": 1, "topic_label": "faiz"},
        {"comment_id": "c3", "configuration": "within_analyst", "topic_id": 1, "topic_label": "faiz"},
    ])
    topics_path = base_root / topics_run_id / "data_processed" / "topics.parquet"
    topics_path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(topics_df, topics_path)

    sentiment_df = pd.DataFrame([
        {"comment_id": "c1", "sentiment_class": "positive", "sentiment_prob": 0.9},
        {"comment_id": "c2", "sentiment_class": "negative", "sentiment_prob": 0.1},
        {"comment_id": "c3", "sentiment_class": "negative", "sentiment_prob": 0.2},
    ])
    sentiment_path = base_root / sentiment_run_id / "data_processed" / "sentiment.parquet"
    sentiment_path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(sentiment_df, sentiment_path)


def _fixture_ids() -> tuple[str, str, str]:
    return "cr-1", "ar-topics-1", "ar-sentiment-1"


def test_render_topics_chart_produces_a_real_png(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    collection_run_id, topics_run_id, sentiment_run_id = _fixture_ids()
    _write_fixture(
        base_root, collection_run_id=collection_run_id,
        topics_run_id=topics_run_id, sentiment_run_id=sentiment_run_id,
    )

    adapter = ChartRendererAdapter(base_root=base_root)
    output_path = tmp_path / "topics.png"
    byte_count = adapter.render(
        collection_run_id=collection_run_id,
        analysis_run_ids=[topics_run_id, sentiment_run_id],
        chart_type="topics",
        output_path=str(output_path),
    )

    assert byte_count > 0
    assert output_path.exists()
    assert output_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"  # real PNG magic bytes


def test_render_sentiment_chart_produces_a_real_png(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    collection_run_id, topics_run_id, sentiment_run_id = _fixture_ids()
    _write_fixture(
        base_root, collection_run_id=collection_run_id,
        topics_run_id=topics_run_id, sentiment_run_id=sentiment_run_id,
    )

    adapter = ChartRendererAdapter(base_root=base_root)
    output_path = tmp_path / "sentiment.png"
    byte_count = adapter.render(
        collection_run_id=collection_run_id,
        analysis_run_ids=[topics_run_id, sentiment_run_id],
        chart_type="sentiment",
        output_path=str(output_path),
    )

    assert byte_count > 0
    assert output_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_respects_configured_dpi(tmp_path: Path) -> None:
    """`settings.output.figures.dpi` must actually reach matplotlib's `savefig()` -- verified by
    asserting a higher DPI produces a larger file than the default, not just that no error is
    raised (a silently-ignored setting would still pass a weaker test)."""
    base_root = tmp_path / "runs"
    collection_run_id, topics_run_id, sentiment_run_id = _fixture_ids()
    _write_fixture(
        base_root, collection_run_id=collection_run_id,
        topics_run_id=topics_run_id, sentiment_run_id=sentiment_run_id,
    )

    class _FakeFigureOutput:
        dpi = 600
        formats = ["png"]
        style = "publication"
        colourblind_safe = True

    class _FakeOutputConfig:
        figures = _FakeFigureOutput()

    class _FakeSettings:
        output = _FakeOutputConfig()

    low_dpi_adapter = ChartRendererAdapter(base_root=base_root)
    low_dpi_path = tmp_path / "topics_default_dpi.png"
    low_dpi_adapter.render(
        collection_run_id=collection_run_id,
        analysis_run_ids=[topics_run_id, sentiment_run_id],
        chart_type="topics",
        output_path=str(low_dpi_path),
    )

    high_dpi_adapter = ChartRendererAdapter(base_root=base_root, settings=_FakeSettings())  # type: ignore[arg-type]
    high_dpi_path = tmp_path / "topics_600dpi.png"
    high_dpi_adapter.render(
        collection_run_id=collection_run_id,
        analysis_run_ids=[topics_run_id, sentiment_run_id],
        chart_type="topics",
        output_path=str(high_dpi_path),
    )

    assert high_dpi_path.stat().st_size > low_dpi_path.stat().st_size


def test_render_rejects_unsupported_chart_type(tmp_path: Path) -> None:
    adapter = ChartRendererAdapter(base_root=tmp_path)
    with pytest.raises(ValueError):
        adapter.render(
            collection_run_id="cr-1", analysis_run_ids=["ar-1"],
            chart_type="not-a-real-type", output_path=str(tmp_path / "out.png"),
        )


def test_render_raises_file_not_found_when_sentiment_output_missing(tmp_path: Path) -> None:
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

    adapter = ChartRendererAdapter(base_root=base_root)
    with pytest.raises(FileNotFoundError):
        adapter.render(
            collection_run_id=collection_run_id, analysis_run_ids=[topics_run_id],
            chart_type="topics", output_path=str(tmp_path / "out.png"),
        )


def test_render_rejects_empty_collection_run_id(tmp_path: Path) -> None:
    adapter = ChartRendererAdapter(base_root=tmp_path)
    with pytest.raises(ValueError):
        adapter.render(
            collection_run_id="", analysis_run_ids=["ar-1"],
            chart_type="topics", output_path="out.png",
        )


def test_render_rejects_empty_analysis_run_ids(tmp_path: Path) -> None:
    adapter = ChartRendererAdapter(base_root=tmp_path)
    with pytest.raises(ValueError):
        adapter.render(
            collection_run_id="cr-1", analysis_run_ids=[],
            chart_type="topics", output_path="out.png",
        )


def test_adapter_module_does_not_import_presentation_or_api() -> None:
    import finfluencer.infrastructure.reporting.chart_renderer_adapter as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)
