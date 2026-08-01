"""DTOs for the Identity Service's `CreateProject` command (BACKLOG.md T-008).

PRODUCT_ARCHITECTURE.md section 11.2, Identity Service:
    "Commands: `CreateTenant`, `CreateProject`, ..." (line 657)
    "Idempotency: `CreateTenant`/`CreateProject` require a client idempotency key." (line 662)
    "Sync vs Async: synchronous -- authorization sits on the critical path of every request."
    (line 663)

REST derivation, section 11.3, line 776: `POST /projects` <- `CreateProject` command, Sync.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateProjectRequest(BaseModel):
    """Request DTO for `CreateProject`.

    `tenant_id`: the owning Tenant -- "belongs to exactly one `Tenant`" (section 10.1, line
    546). `idempotency_key`: required per line 662, above.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: UUID
    name: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class ProjectCreated(BaseModel):
    """Response DTO for a successful synchronous `CreateProject` call.

    Mirrors the wire-visible fields of the `Project` entity (section 10.1, lines 543-551) --
    `id`, `tenant_id`, `name`, `status` -- without importing the Domain entity itself (section
    12.1, line 813: "a DTO must never import a Domain entity directly"). `status` is
    independently declared as a `Literal`, not imported from
    `finfluencer.domain.entities.ProjectStatus`, so the wire contract and the Domain Model can
    change independently, per the same line 813 rationale.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    name: str
    # "created (SCR-PROJ-01) -> active -> archived..." (section 10.1, line 547). A freshly
    # created Project is always `active` -- `archived` is included in the Literal for
    # response-shape completeness (the same DTO type may echo an existing Project's state
    # elsewhere later), not because CreateProject can return an archived Project.
    status: Literal["active", "archived"]
