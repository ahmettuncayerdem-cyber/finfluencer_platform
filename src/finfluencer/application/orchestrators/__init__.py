"""Application orchestrators (PRODUCT_ARCHITECTURE.md section 12.1, line 830:
"`application.orchestrators.*` (one per command -- full mapping in section 12.3)...").

BACKLOG.md T-009 scope: ``CreateProjectOrchestrator`` -- the first orchestrator this package
held. BACKLOG.md T-011 adds ``StartCollectionRunOrchestrator``, the first orchestrator that
reaches all the way down to an Infrastructure adapter (T-010) and the Legacy Collection Engine.
BACKLOG.md T-020 adds ``StartAnalysisRunOrchestrator``, the Analysis-side equivalent -- reuses
T-011's idempotent-dispatch shape, but a duplicate dispatch onto a failed run creates a new
`AnalysisRun` rather than resuming in place (section 10.1 line 577; no `resume()` exists for
`AnalysisRun`). Grows one module per command as each vertical slice needs it, not designed
speculatively ahead of time. See `CONTEXT_PACK.md` for T-011's orchestration-sequence diagram and
IG-001 walkthrough.
"""

from __future__ import annotations

from finfluencer.application.orchestrators.create_project import (
    CreateProjectCommand,
    CreateProjectOrchestrator,
    CreateProjectResult,
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
    "StartAnalysisRunCommand",
    "StartAnalysisRunOrchestrator",
    "StartAnalysisRunResult",
    "StartCollectionRunCommand",
    "StartCollectionRunOrchestrator",
    "StartCollectionRunResult",
]
