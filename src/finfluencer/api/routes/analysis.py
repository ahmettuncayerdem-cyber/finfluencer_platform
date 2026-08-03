"""`api.routes.analysis` -- `StartAnalysisRun` (PRODUCT_ARCHITECTURE.md section 11.2, Analysis
Service, line 696; section 11.3, line 779: `POST /collection-runs/{id}/analysis-runs` <-
`StartAnalysisRun`, "path shape itself encodes the CollectionRun-pinning rule").

BACKLOG.md T-028 scope: this one route only, reusing T-020's `StartAnalysisRunOrchestrator`
completely unmodified -- the first Presentation/API exposure of any Analysis Service operation.
`bootstrap.py` wires this route to a deliberately lightweight, demo-only `IAnalysisEngine` stand-in
(not T-019's `TopicsAnalysisAdapter` -- see `bootstrap.py`'s own docstring for the full reasoning);
this route module itself has no idea which concrete engine is behind the orchestrator, same
"route doesn't know or care" separation `api/routes/collection.py` already established for
`CollectionEngineAdapter`/`FixtureCollectionProvider`.

Same deliberate, flagged deviation from section 11.2's literal "asynchronous" contract that
`collection.py` already documents for `StartCollectionRun`: `StartAnalysisRunOrchestrator`
(T-020) runs synchronously to completion today, so this route returns the full current-state
shape (`AnalysisRunStarted`) rather than a narrower "queued" acceptance shape.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from finfluencer.api.deps import get_start_analysis_run_orchestrator
from finfluencer.application.orchestrators import (
    StartAnalysisRunCommand,
    StartAnalysisRunOrchestrator,
)
from finfluencer.presentation.dto import AnalysisRunStarted, StartAnalysisRunRequest

router = APIRouter(tags=["analysis"])


@router.post(
    "/collection-runs/{collection_run_id}/analysis-runs",
    response_model=AnalysisRunStarted,
    status_code=200,
)
def start_analysis_run(
    collection_run_id: UUID,
    request: StartAnalysisRunRequest,
    orchestrator: StartAnalysisRunOrchestrator = Depends(get_start_analysis_run_orchestrator),
) -> AnalysisRunStarted:
    # Same path/body consistency discipline as `collection.py`'s own `dataset_id` check.
    if collection_run_id != request.collection_run_id:
        raise HTTPException(
            status_code=400,
            detail="Path collection_run_id does not match request body collection_run_id.",
        )

    # `EntityId` is `NewType("EntityId", uuid.UUID)` -- a plain `uuid.UUID` (what these
    # Pydantic-validated fields already are) satisfies it at runtime without importing
    # `finfluencer.domain` into this module (forbidden, section 12.1 line 821;
    # `test_architectural_conformance.py` proves it ast-statically).
    command = StartAnalysisRunCommand(
        project_id=request.project_id,  # type: ignore[arg-type]
        collection_run_id=request.collection_run_id,  # type: ignore[arg-type]
        analysis_type_id=request.analysis_type_id,  # type: ignore[arg-type]
        analysis_type_version=request.analysis_type_version,
        idempotency_key=request.idempotency_key,
    )
    result = orchestrator.execute(command)
    return AnalysisRunStarted(
        id=result.id,
        project_id=result.project_id,
        collection_run_id=request.collection_run_id,
        status=result.status,  # type: ignore[arg-type]
        row_count=result.row_count,
        topic_count=result.topic_count,
    )
