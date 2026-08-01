"""Presentation-Layer DTOs (PRODUCT_ARCHITECTURE.md section 12.1, line 814:
"Primary modules: `presentation.dto.*`...").

BACKLOG.md T-008 scope: one DTO pair per section 11.2 command/query, for the skeleton slice
only -- `CreateProject` (Identity Service), `StartCollectionRun` and `GetCollectionRun`
(Collection Service). Everything else in section 11.2's service catalog grows this package
per-epic, exactly as the Domain Model (T-007) grows per-epic -- not designed speculatively
ahead of time.

Naming and validation conventions here reconcile with, rather than replace, the existing
`finfluencer.core.contracts` module: Pydantic `BaseModel` subclasses, snake_case field names,
`model_config = ConfigDict(extra="forbid")` on every model so an unrecognized field is a
validation error, not a silently ignored typo.
"""

from __future__ import annotations

from finfluencer.presentation.dto.collection import (
    CollectionRunAccepted,
    GetCollectionRunRequest,
    GetCollectionRunResponse,
    StartCollectionRunRequest,
)
from finfluencer.presentation.dto.identity import CreateProjectRequest, ProjectCreated

__all__ = [
    "CollectionRunAccepted",
    "CreateProjectRequest",
    "GetCollectionRunRequest",
    "GetCollectionRunResponse",
    "ProjectCreated",
    "StartCollectionRunRequest",
]
