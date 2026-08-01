"""Shared Domain-entity primitives (PRODUCT_ARCHITECTURE.md section 10.1).

Deliberately minimal and standard-library-only. PRODUCT_ARCHITECTURE.md section 12.1's Domain
Layer rule is explicit and has no carve-out: "Forbidden dependencies: everything outside itself
-- Application, Presentation, API, Infrastructure, Persistence, and any external SDK (AI provider
client, HTTP client, database driver, queue client) -- no exceptions" (lines 837-838). A
validation library such as Pydantic -- already used elsewhere in this repository, e.g.
``finfluencer.core.contracts`` -- is exactly the kind of external SDK this rule forbids inside
Domain. Entities in this package therefore use only ``dataclasses``/plain classes, ``enum``, and
``uuid`` from the standard library, and enforce their own invariants in hand-written methods
rather than delegating to a third-party validation framework.
"""

from __future__ import annotations

import uuid
from typing import NewType

#: Every Domain entity in this package is identified by a UUID. A `NewType` (not a bare
#: `uuid.UUID` alias) so that, e.g., a `TenantId` and a `ProjectId` are not silently
#: interchangeable to a type checker even though both are UUIDs underneath.
EntityId = NewType("EntityId", uuid.UUID)


def new_entity_id() -> EntityId:
    """Generate a fresh, globally-unique entity identifier."""
    return EntityId(uuid.uuid4())


class DomainInvariantViolation(Exception):
    """Raised when calling code attempts to violate an invariant that
    PRODUCT_ARCHITECTURE.md section 10.1 states as non-negotiable for a specific entity --
    e.g. mutating a `CollectionRun` after it has completed (section 10.1, line 568: "Immutable
    once `completed`. This is what makes it a valid reproducibility anchor."), or archiving an
    already-archived `Project`.

    Deliberately a distinct exception type from `ValueError` (used for ordinary input
    validation, e.g. an empty name) so calling code can distinguish "you gave me bad input" from
    "you asked me to break an architectural invariant."
    """
