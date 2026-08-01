"""DTOs for the Collection Service's `StartCollectionRun` command and `GetCollectionRun` query
(BACKLOG.md T-008).

PRODUCT_ARCHITECTURE.md section 11.2, Collection Service:
    "Commands: `CreateDataset`, `StartCollectionRun`, `ResumeCollectionRun`." (line 683)
    "Queries: `GetDataset`, `ListDatasets`, `ListCollectionRunsForDataset`, `GetCollectionRun`."
    (line 684)
    "Idempotency: `StartCollectionRun` requires an idempotency key -- a duplicate submission
    must not double-collect or double-spend quota." (line 688)
    "Sync vs Async: **asynchronous** -- a real, quota-bounded external collection can take
    minutes to hours; returns a `CollectionRun` in `queued` state immediately." (line 689)

REST derivation, section 11.3, line 778: `POST /datasets/{id}/collection-runs` <-
`StartCollectionRun` command, "Async (202 Accepted + polling/event)".

Naming note: BACKLOG.md T-008's own purpose line names this operation "GetCollectionRunStatus",
but section 11.2's actual, binding query name is `GetCollectionRun` (line 684) -- no
`GetCollectionRunStatus` query exists in the approved contract. `GetCollectionRunResponse`
below implements the query section 11.2 actually names; its response includes `status` among
the CollectionRun's wire-visible fields, which is what BACKLOG.md's shorthand name refers to.
This is a naming reconciliation, not a scope deviation -- flagged explicitly per this task's
"matches section 11.2... for this slice" acceptance criterion, not silently substituted.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StartCollectionRunRequest(BaseModel):
    """Request DTO for `StartCollectionRun`.

    `dataset_id`: "belongs to exactly one `Dataset`" is CollectionRun's own invariant (section
    10.1, line 566); the REST derivation (line 778) carries this in the path
    (`/datasets/{id}/collection-runs`) -- included here as an explicit DTO field as well so the
    schema is self-describing independent of routing. `idempotency_key`: required per line 688,
    above.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    dataset_id: UUID
    idempotency_key: str = Field(min_length=1)


class CollectionRunAccepted(BaseModel):
    """Response DTO for `StartCollectionRun`'s "202 Accepted" async response.

    `status` is locked to the single literal `"queued"` -- not the full CollectionRunStatus
    range -- because section 11.2 line 689 is explicit: `StartCollectionRun` "returns a
    `CollectionRun` in `queued` state immediately." Any other state is a `GetCollectionRun`
    concern (`GetCollectionRunResponse`, below), never something this response shape returns.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    dataset_id: UUID
    status: Literal["queued"]


class GetCollectionRunRequest(BaseModel):
    """Request DTO for `GetCollectionRun` (section 11.2, line 684).

    A GET query with a single path parameter in the REST derivation; represented here as a DTO
    for schema completeness and symmetry with the request/response pair pattern (section 12.1,
    line 811), not because a GET request carries a JSON body.
    """

    model_config = ConfigDict(extra="forbid")

    collection_run_id: UUID


class GetCollectionRunResponse(BaseModel):
    """Response DTO for `GetCollectionRun`.

    `status` covers the full CollectionRunStatus range: "`queued -> running -> completed |
    failed`; resumable from a `failed`/interrupted state" (section 10.1, line 567) -- unlike
    `CollectionRunAccepted`, which is deliberately narrower.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    dataset_id: UUID
    status: Literal["queued", "running", "completed", "failed"]
