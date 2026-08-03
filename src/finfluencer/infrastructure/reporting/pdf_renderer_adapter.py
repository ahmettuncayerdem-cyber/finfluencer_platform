"""PdfRendererAdapter (PRODUCT_ARCHITECTURE.md section 8.4, section 10.1 lines 603-609;
BACKLOG.md T-027).

Implements `IPdfRenderer` (`domain/reporting_engine.py`) using `reportlab` (ADR-0003) --
genuinely new code, no existing tested code wrapped. Renders already-resolved citation content
(`CitationSnapshot` rows, built by `GenerateExportOrchestrator`) into a PDF file via reportlab's
own Platypus flowable API. Deliberately minimal layout -- title, metadata, one section per
citation with its raw content verbatim -- per T-027's own Migration Risk Checklist scope
decision (publication-quality layout deferred as a fast-follow, not built here).
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from finfluencer.domain.reporting_engine import CitationSnapshot

_styles = getSampleStyleSheet()


def _escape(text: str) -> str:
    """reportlab's `Paragraph` interprets a minimal XML-like markup -- escape the four
    characters that would otherwise be misread as markup rather than literal content.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class PdfRendererAdapter:
    """Implements `IPdfRenderer` via `reportlab.platypus.SimpleDocTemplate`."""

    def render(
        self,
        report_id: str,
        report_version: int,
        citations: list[CitationSnapshot],
        output_path: str,
    ) -> int:
        if not report_id or not report_id.strip():
            raise ValueError("PdfRendererAdapter.render() requires a non-empty report_id.")
        if report_version < 1:
            raise ValueError("PdfRendererAdapter.render() requires report_version >= 1.")
        if not citations:
            raise ValueError(
                "PdfRendererAdapter.render() requires at least one citation -- a Report with "
                "no citations has nothing to render (section 10.1, InterpretationRecord)."
            )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        story = [
            Paragraph(
                _escape(f"Report {report_id} (v{report_version})"), _styles["Title"],
            ),
            Paragraph(
                _escape(
                    f"{len(citations)} citation(s) -- raw result snapshot(s) only, no AI "
                    "interpretation."
                ),
                _styles["Normal"],
            ),
            Spacer(1, 12),
        ]
        for citation in citations:
            story.append(
                Paragraph(
                    _escape(f"Citation {citation['record_id']}"), _styles["Heading2"],
                ),
            )
            story.append(
                Paragraph(
                    _escape(
                        f"AnalysisRun: {citation['analysis_run_id']} | "
                        f"kind: {citation['kind']} | selector: {citation['selector']}"
                    ),
                    _styles["Normal"],
                ),
            )
            story.append(Spacer(1, 4))
            story.append(Paragraph(_escape(citation["content"]), _styles["Code"]))
            story.append(Spacer(1, 12))

        doc.build(story)
        return doc.page


__all__ = ["PdfRendererAdapter"]
