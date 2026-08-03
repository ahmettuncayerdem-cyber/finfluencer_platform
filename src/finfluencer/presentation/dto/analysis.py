"""DTOs for the Analysis Service's `StartAnalysisRun` command (BACKLOG.md T-028 -- the first
Presentation/API exposure of any Analysis Service operation; T-020 built the orchestrator, T-028
is the first caller).

PRODUCT_ARCHITECTURE.md section 11.2, Analysis Service:
    "Commands: `StartAnalysisRun(collectionRunId, analysisTypeId, params)` -- pinned to a
    `CollectionRun` ID, never a loose `Dataset` reference." (line 696)
    "Idempotency: `StartAnalysisRun` requires an idempotency key." (line 701)
    "Sync vs Async: **asynchronous** -- compute-bound (topic modeling, sentiment)." (line 702)

REST derivation, section 11.3, line 779: `POST /collection-runs/{id}/analysis-runs` <-
`StartAnalysisRun` command -- "path shape itself encodes the CollectionRun-pinning rule
(section 10.1) at the API surface, not just in documentation." Matched exactly here, not
invented.

Same deliberate, flagged deviation from the literal async contract that `collection.py`'s own
DTOs already document for `StartCollectionRun`: `StartAnalysisRunOrchestrator` (T-020) runs
synchronously to completion, so this route returns the full current-state shape
(`AnalysisRunStarted`, covering the whole `AnalysisRunStatus` range) rather than a narrower
"queued" acceptance shape.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StartAnalysisRunRequest(BaseModel):
    """Request DTO for `StartAnalysisRun`.

    `collection_run_id`: "belongs to exactly one `CollectionRun`" is `AnalysisRun`'s own pinning
    invariant (section 10.1, line 576) -- carried in the path (REST derivation, above) and
    repeated here for schema self-description, same reasoning `StartCollectionRunRequest`
    already documents for its own `dataset_id`. `project_id`: `AnalysisRun` "belongs to exactly
    one `Project`" (section 10.1, line 576) -- not part of section 11.3 line 779's own
    representative path shape, so carried in the body only, same as `StartAnalysisRunCommand`
    (T-020) already requires it. `analysis_type_id`/`analysis_type_version` are trusted as
    given, same permissiveness `StartAnalysisRunCommand` (T-020) already has toward its own
    caller (no `AnalysisType` catalog/repository exists to validate against yet).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: UUID
    collection_run_id: UUID
    analysis_type_id: UUID
    analysis_type_version: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class AnalysisRunStarted(BaseModel):
    """Response DTO for `StartAnalysisRun`.

    `status` covers the full `AnalysisRunStatus` range (section 10.1, line 577:
    "`queued -> running -> completed | failed`") -- unlike `CollectionRunAccepted`'s
    deliberately narrower "queued"-only shape, because (as with `GetCollectionRunResponse`) this
    route's synchronous-in-practice implementation means the caller always sees the final state
    immediately, never a transient `queued`.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    collection_run_id: UUID
    status: Literal["queued", "running", "completed", "failed"]
    row_count: int | None
    topic_count: int | None
