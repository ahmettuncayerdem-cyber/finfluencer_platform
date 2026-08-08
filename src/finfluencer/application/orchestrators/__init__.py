"""Application orchestrators (PRODUCT_ARCHITECTURE.md section 12.1, line 830:
"`application.orchestrators.*` (one per command -- full mapping in section 12.3)...").

BACKLOG.md T-009 scope: ``CreateProjectOrchestrator`` -- the first orchestrator this package
held. BACKLOG.md T-011 adds ``StartCollectionRunOrchestrator``, the first orchestrator that
reaches all the way down to an Infrastructure adapter (T-010) and the Legacy Collection Engine.
BACKLOG.md T-020 adds ``StartAnalysisRunOrchestrator``, the Analysis-side equivalent -- reuses
T-011's idempotent-dispatch shape, but a duplicate dispatch onto a failed run creates a new
`AnalysisRun` rather than resuming in place (section 10.1 line 577; no `resume()` exists for
`AnalysisRun`). BACKLOG.md T-025 adds ``GenerateReportOrchestrator`` -- the Reporting-side
equivalent, turning a completed `AnalysisRun` into a citable `InterpretationRecord` and a
`Report`; zero AI interpretation logic anywhere in it (kind=`raw_result_snapshot` only).
BACKLOG.md T-026 adds ``ExportReportTableOrchestrator`` -- resolves a `Report`'s citations back
to their source `AnalysisRun`s/`CollectionRun` and exports the joined table via
`reporting.master_table` (wrapped unmodified); constructs no Domain `Export` entity (section
10.1 restricts `Export` to PDF/Word). BACKLOG.md T-027 adds ``FinalizeReportOrchestrator`` (the
previously-unbuilt `FinalizeReport` command, section 11.2 line 722) and
``GenerateExportOrchestrator`` -- the first orchestrator that DOES construct an `Export` (T-024,
unused until now), rendering a finalized `Report`'s citations to PDF via `IPdfRenderer`
(`reportlab`, ADR-0003). BACKLOG.md T-028 adds ``GetReportOrchestrator`` -- the previously-unbuilt
`GetReport` query (section 11.2 line 723), the first pure read this package exposes on its own
rather than as a side effect inside a larger command. BACKLOG.md EPIC-10 adds
``GenerateChartOrchestrator`` -- structurally a near-duplicate of `ExportReportTableOrchestrator`
(same citation-to-CollectionRun resolution), rendering a chart via `IChartRenderer` instead of
exporting a table via `ITableExporter`; constructs no Domain `Export` entity, same reasoning as
`ExportReportTableOrchestrator`. Grows one module per command as each vertical slice needs it,
not designed speculatively ahead of time. See `CONTEXT_PACK.md` for T-011's
orchestration-sequence diagram and IG-001 walkthrough.
"""

from __future__ import annotations

from finfluencer.application.orchestrators.create_project import (
    CreateProjectCommand,
    CreateProjectOrchestrator,
    CreateProjectResult,
)
from finfluencer.application.orchestrators.export_report_table import (
    ExportReportTableCommand,
    ExportReportTableOrchestrator,
    ExportReportTableResult,
)
from finfluencer.application.orchestrators.finalize_report import (
    FinalizeReportCommand,
    FinalizeReportOrchestrator,
    FinalizeReportResult,
)
from finfluencer.application.orchestrators.generate_chart import (
    GenerateChartCommand,
    GenerateChartOrchestrator,
    GenerateChartResult,
)
from finfluencer.application.orchestrators.generate_export import (
    GenerateExportCommand,
    GenerateExportOrchestrator,
    GenerateExportResult,
)
from finfluencer.application.orchestrators.generate_report import (
    GenerateReportCommand,
    GenerateReportOrchestrator,
    GenerateReportResult,
)
from finfluencer.application.orchestrators.get_report import (
    GetReportCommand,
    GetReportOrchestrator,
    GetReportResult,
)
from finfluencer.application.orchestrators.start_analysis_run import (
    StartAnalysisRunCommand,
    StartAnalysisRunOrchestrator,
    StartAnalysisRunResult,
)
from finfluencer.application.orchestrators.start_collection_run import (
    StartCollectionRunCommand,
    StartCollectionRunOrchestrator,
    StartCollectionRunResult,
)

__all__ = [
    "CreateProjectCommand",
    "CreateProjectOrchestrator",
    "CreateProjectResult",
    "ExportReportTableCommand",
    "ExportReportTableOrchestrator",
    "ExportReportTableResult",
    "FinalizeReportCommand",
    "FinalizeReportOrchestrator",
    "FinalizeReportResult",
    "GenerateChartCommand",
    "GenerateChartOrchestrator",
    "GenerateChartResult",
    "GenerateExportCommand",
    "GenerateExportOrchestrator",
    "GenerateExportResult",
    "GenerateReportCommand",
    "GenerateReportOrchestrator",
    "GenerateReportResult",
    "GetReportCommand",
    "GetReportOrchestrator",
    "GetReportResult",
    "StartAnalysisRunCommand",
    "StartAnalysisRunOrchestrator",
    "StartAnalysisRunResult",
    "StartCollectionRunCommand",
    "StartCollectionRunOrchestrator",
    "StartCollectionRunResult",
]
