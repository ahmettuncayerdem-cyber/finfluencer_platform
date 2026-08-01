"""`api.routes.collection` -- `StartCollectionRun` (PRODUCT_ARCHITECTURE.md section 11.2,
Collection Service, line 683; section 11.3, line 778: `POST /datasets/{id}/collection-runs` <-
`StartCollectionRun`, "Async (202 Accepted + polling/event)").

BACKLOG.md T-012 scope: this one route only, reusing T-011's `StartCollectionRunOrchestrator`
completely unmodified.

**Deliberate, flagged deviation from section 11.3's literal response contract, not a silent
one:** `StartCollectionRunOrchestrator.execute()` (T-011) runs synchronously to completion today
-- a Sprint 0 simplification already recorded in `application/orchestrators/CONTEXT_PACK.md`
("no `IJobDispatcher` exists yet"). By the time this route's call to `execute()` returns, the
`CollectionRun`'s status is `completed`/`failed`, never `queued`. `CollectionRunAccepted`
(T-008) hard-locks its `status` field to the literal `"queued"` specifically because it models
the *immediate* response of a true async dispatch -- constructing it with a `"completed"` value
would fail Pydantic validation, and forcing it to `"queued"` while the run has, in fact, already
finished would be actively misleading, not merely an omission. This route therefore returns
`GetCollectionRunResponse` (section 11.2 line 684's query response shape, which legitimately
covers the full status range) instead of `CollectionRunAccepted` -- an honest reflection of
today's synchronous reality, not a claim that the async contract is implemented. Restructuring
`StartCollectionRunOrchestrator` itself to support a genuine early return is explicitly out of
scope here (operator instruction: "reuse existing orchestrators," "do not expand the
architecture") and is deferred to whichever future task introduces `IJobDispatcher`.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from finfluencer.api.deps import get_start_collection_run_orchestrator
from finfluencer.application.orchestrators import (
    StartCollectionRunCommand,
    StartCollectionRunOrchestrator,
)
from finfluencer.presentation.dto import GetCollectionRunResponse, StartCollectionRunRequest

router = APIRouter(tags=["collection"])


@router.post(
    "/datasets/{dataset_id}/collection-runs",
    response_model=GetCollectionRunResponse,
    status_code=200,
)
def start_collection_run(
    dataset_id: UUID,
    request: StartCollectionRunRequest,
    orchestrator: StartCollectionRunOrchestrator = Depends(get_start_collection_run_orchestrator),
) -> GetCollectionRunResponse:
    # The path parameter (section 11.3 line 778's REST derivation) is authoritative; the body
    # also carries `dataset_id` for schema self-description (StartCollectionRunRequest's own
    # docstring). A mismatch between the two is a client error, not silently resolved either way.
    if dataset_id != request.dataset_id:
        raise HTTPException(
            status_code=400,
            detail="Path dataset_id does not match request body dataset_id.",
        )

    command = StartCollectionRunCommand(
        dataset_id=request.dataset_id, idempotency_key=request.idempotency_key
    )
    result = orchestrator.execute(command)
    return GetCollectionRunResponse(
        id=result.id,
        dataset_id=result.dataset_id,
        status=result.status,  # type: ignore[arg-type]
    )
