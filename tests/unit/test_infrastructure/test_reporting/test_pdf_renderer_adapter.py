"""Tests for PdfRendererAdapter (BACKLOG.md T-027).

Includes the automated content-match half of T-027's own Verification line ("manual visual
review + automated content-match test"): render a PDF, read its text back out with `pypdf`
(dev-only dependency, ADR-0003), and assert every citation's own fields actually appear on the
page -- not just that a file of nonzero size was produced.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from pypdf import PdfReader

from finfluencer.domain.reporting_engine import CitationSnapshot
from finfluencer.infrastructure.reporting.pdf_renderer_adapter import PdfRendererAdapter


def _citation(**overrides: str) -> CitationSnapshot:
    base: CitationSnapshot = {
        "record_id": "record-1",
        "analysis_run_id": "run-1",
        "kind": "raw_result_snapshot",
        "selector": "full_result",
        "content": '{"comment_id": "c1", "topic_label": "enflasyon"}',
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def _extract_text(output_path: Path) -> str:
    reader = PdfReader(str(output_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_render_produces_a_pdf_containing_every_citations_content(tmp_path: Path) -> None:
    output_path = tmp_path / "report.pdf"
    citations = [
        _citation(
            record_id="record-topics", analysis_run_id="run-topics",
            selector="full_result", content='{"topic_label": "enflasyon"}',
        ),
        _citation(
            record_id="record-sentiment", analysis_run_id="run-sentiment",
            selector="full_result", content='{"sentiment_class": "positive"}',
        ),
    ]

    page_count = PdfRendererAdapter().render(
        report_id="report-1", report_version=1,
        citations=citations, output_path=str(output_path),
    )

    assert output_path.exists()
    assert page_count >= 1
    text = _extract_text(output_path)
    assert "report-1" in text
    assert "record-topics" in text
    assert "run-topics" in text
    assert "enflasyon" in text
    assert "record-sentiment" in text
    assert "run-sentiment" in text
    assert "positive" in text


def test_render_rejects_empty_citations(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one citation"):
        PdfRendererAdapter().render(
            report_id="report-1", report_version=1,
            citations=[], output_path=str(tmp_path / "report.pdf"),
        )


def test_render_rejects_empty_report_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="report_id"):
        PdfRendererAdapter().render(
            report_id="", report_version=1,
            citations=[_citation()], output_path=str(tmp_path / "report.pdf"),
        )


def test_render_rejects_invalid_report_version(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="report_version"):
        PdfRendererAdapter().render(
            report_id="report-1", report_version=0,
            citations=[_citation()], output_path=str(tmp_path / "report.pdf"),
        )


def test_render_escapes_markup_characters_in_content(tmp_path: Path) -> None:
    """reportlab's `Paragraph` reads a minimal XML-like markup -- unescaped `<`/`&` in real
    JSON content (which frequently contains both) must not raise or silently corrupt the render.
    """
    output_path = tmp_path / "report.pdf"
    citations = [_citation(content='{"text": "a <b> & \\"quoted\\" value"}')]

    PdfRendererAdapter().render(
        report_id="report-1", report_version=1,
        citations=citations, output_path=str(output_path),
    )

    assert output_path.exists()
    text = _extract_text(output_path)
    assert "quoted" in text


def test_adapter_module_imports_only_reportlab_pathlib_and_domain_reporting_engine() -> None:
    import finfluencer.infrastructure.reporting.pdf_renderer_adapter as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)
    assert not any(m.startswith("finfluencer.application") for m in imported_modules)
    assert not any(m.startswith("finfluencer.domain.repositories") for m in imported_modules)
    for module_name in imported_modules:
        assert module_name.startswith(
            ("reportlab", "pathlib", "finfluencer.domain.reporting_engine", "__future__"),
        ), f"unexpected import {module_name!r} in pdf_renderer_adapter.py"
