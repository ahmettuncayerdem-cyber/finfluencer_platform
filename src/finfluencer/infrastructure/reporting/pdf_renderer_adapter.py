"""PdfRendererAdapter (PRODUCT_ARCHITECTURE.md section 8.4, section 10.1 lines 603-609;
BACKLOG.md T-027).

Implements `IPdfRenderer` (`domain/reporting_engine.py`) using `reportlab` (ADR-0003) --
genuinely new code, no existing tested code wrapped. Renders already-resolved citation content
(`CitationSnapshot` rows, built by `GenerateExportOrchestrator`) into a PDF file via reportlab's
own Platypus flowable API. Deliberately minimal layout -- title, metadata, one section per
citation with its raw content verbatim -- per T-027's own Migration Risk Checklist scope
decision (publication-quality layout deferred as a fast-follow, not built here).

**Fix (T-029 live MVP sign-off, 2026-08-06): bounded content preview, not the full raw
snapshot.** `ResultSnapshotAdapter.read()` (`snapshot_adapter.py`) serializes an entire
`AnalysisRun`'s result parquet to JSON via `DataFrame.to_json(orient="records")` -- for real
data this is tens of thousands of records in one JSON-array string with no natural line breaks.
Every prior test/verification of this adapter (T-027's own tests, `t029_e2e_verification.py`)
used tiny fixture/demo citations (a handful of records), so embedding `citation["content"]`
verbatim into a single reportlab `Paragraph` was never exercised against real-scale content
until this delta's live run -- reportlab's `Paragraph` text-wrapping is known to become
impractically slow (effectively non-terminating for interactive purposes) on very large
single blocks of unbroken text; that is what actually happened, not a hang or crash.
`PRODUCT_ARCHITECTURE.md`'s own architecture already draws this line: manuscript-ready
*tables* (full data, §184/§297, this repository's `ExportReportTableOrchestrator`/`/table`
route) are a distinct capability from the PDF *render* (§184/§299) -- the PDF's job is a
readable, citation-identifying document, not a second copy of the full dataset. `_preview()`
below embeds a bounded number of records plus an explicit "N more rows -- see the table
export" note; the full data remains exactly and only where it already correctly lived: the
CSV/table export, unaffected by this change.
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from finfluencer.domain.reporting_engine import CitationSnapshot

_styles = getSampleStyleSheet()

#: Cap on how many JSON-array records of a citation's raw snapshot are embedded in the PDF.
#: See module docstring's "Fix" note -- the full data is the CSV/table export's job, not this
#: rendered document's.
_MAX_PREVIEW_ROWS = 20


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


def _preview(content: str, *, max_rows: int = _MAX_PREVIEW_ROWS) -> str:
    """Bound how much of a citation's raw content is embedded in the PDF.

    Only truncates content that parses as a JSON array (`ResultSnapshotAdapter`'s own output
    shape, `DataFrame.to_json(orient="records")`) with more than `max_rows` entries -- anything
    else (a JSON object, a plain string, malformed JSON) passes through completely unchanged,
    so this only ever affects the specific pathological case (a large raw-snapshot array), never
    any other citation kind/selector this adapter might see in the future.
    """
    try:
        records = json.loads(content)
    except (json.JSONDecodeError, TypeError, ValueError):
        return content
    if not isinstance(records, list) or len(records) <= max_rows:
        return content

    total = len(records)
    omitted = total - max_rows
    return (
        json.dumps(records[:max_rows])
        + f"\n... {omitted} more row(s) omitted ({total} total). "
        "See this report's CSV/table export for the complete data."
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
            story.append(Paragraph(_escape(_preview(citation["content"])), _styles["Code"]))
            story.append(Spacer(1, 12))

        doc.build(story)
        return doc.page


__all__ = ["PdfRendererAdapter"]
