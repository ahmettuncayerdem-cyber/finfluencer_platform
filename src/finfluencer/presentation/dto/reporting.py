"""DTOs for the Reporting Service's `CreateReport`/`AddCitation` (folded into one `GenerateReport`
call, matching `GenerateReportOrchestrator`'s own T-025 scope), `GetReport`, `FinalizeReport`, and
`GenerateExport` operations (BACKLOG.md T-028 -- the first Presentation/API exposure of any
Reporting Service operation).

PRODUCT_ARCHITECTURE.md section 11.2, Reporting Service (line 719-730): commands
`CreateRawSnapshot`, `CreateReport`, `AddCitation`, `FinalizeReport`, `GenerateExport`; queries
`GetReport`, `ListReportsForProject`, `GetExport`.

REST derivation, section 11.3 line 782: `POST /reports/{id}/exports` <- `GenerateExport`,
matched exactly (nested here under `/projects/{project_id}/reports/{report_id}/exports`,
reconciling the abstract table with `StartCollectionRun`'s own already-implemented
parent-scoping-id-in-path precedent -- see `api/routes/reporting.py`'s own docstring).

`GenerateExport`'s response is **not** a JSON DTO -- the route returns the rendered PDF bytes
directly in the response body (`media_type="application/pdf"`), matching this task's own
Migration Risk Checklist idempotency/side-effects decision (no separate download endpoint).
Table export (`GET .../table`, wrapping T-026's `ExportReportTableOrchestrator`) is symmetric,
returning CSV bytes directly -- it has no section 11.2 command name at all (T-026's own finding:
table/CSV generation is the separate "manuscript-ready table objects" capability section 8.4
names, not a formal Reporting Service command), so no request/response DTO pair is declared for
it either.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GenerateReportRequest(BaseModel):
    """Request DTO for `GenerateReport` (folds `CreateReport`+`AddCitation` into one call, per
    `GenerateReportOrchestrator`'s own T-025 scope -- see that module's docstring for why a
    separate `AddCitation` orchestrator was not built ahead of a real need).

    `analysis_run_id`: the completed `AnalysisRun` to snapshot and cite. `existing_report_id`:
    omit to start a new draft `Report`; provide to cite into an already-existing draft one
    (accumulating citations across multiple calls, T-025's own Verification line).
    """

    model_config = ConfigDict(extra="forbid")

    analysis_run_id: UUID
    existing_report_id: UUID | None = None


class ReportView(BaseModel):
    """Response DTO for `GenerateReport` and `GetReport` -- both describe the same `Report`
    shape from two different entry points, mirrored here as one wire shape rather than two
    near-identical DTOs.

    `version`: `None` when this response comes from `GenerateReport` -- `GenerateReportResult`
    (T-025, frozen, not modified by this task) does not carry it. Populated with the real value
    when this response comes from `GetReport` (`GetReportOrchestrator`, T-028, does read it off
    the Domain entity). Not fabricated either way -- `Report.version` is always `1` in the
    current implementation (no version-bumping command exists yet, T-024's own TODO), so this
    is a real gap in one source DTO, not papered over with a guessed value.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    version: int | None = None
    status: Literal["draft", "finalized"]
    citation_count: int


class ReportFinalized(BaseModel):
    """Response DTO for `FinalizeReport` -- deliberately narrower than `ReportView`
    (`FinalizeReportResult`, T-027, carries only `report_id`/`status`; re-fetching `version`/
    `citation_count` would need a second `GetReport` call this route does not make, same
    narrow-response discipline `CollectionRunAccepted` already established relative to
    `GetCollectionRunResponse`).
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: Literal["draft", "finalized"]
