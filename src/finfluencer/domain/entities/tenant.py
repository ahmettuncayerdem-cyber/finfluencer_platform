"""Tenant entity (PRODUCT_ARCHITECTURE.md section 10.1, lines 483-491).

Sprint 0 scope note (BACKLOG.md T-007): only the fields and behavior PRODUCT_ARCHITECTURE.md
section 10.1 explicitly specifies for Tenant are implemented here.

Architectural note carried forward from this repository's forensic evidence review of
PRODUCT_ARCHITECTURE.md: Tenant's relationship to Project is explicitly INDIRECT --

    "owns many `Project` (indirectly, through `TenantMembership` -> `Project` ownership --
    see Project below for the actual aggregate boundary)."
    (PRODUCT_ARCHITECTURE.md section 10.1, line 486)

`Tenant` therefore does NOT hold an in-memory collection of `Project`s in this implementation.
Ownership is expressed on `Project`'s side (`Project.tenant_id`), and the actual
membership/authorization mechanism (`TenantMembership`) is out of scope for Sprint 0. Giving
`Tenant` a `projects` list here would fabricate a direct ownership relationship the architecture
explicitly does not describe -- the real one requires `TenantMembership`, which does not exist
yet (see TODO below).
"""

from __future__ import annotations

from enum import Enum

from finfluencer.domain.entities._common import (
    DomainInvariantViolation,
    EntityId,
    new_entity_id,
)


class TenantStatus(str, Enum):
    """PRODUCT_ARCHITECTURE.md section 10.1, line 487:

    "active indefinitely; suspendable (non-payment) or closable (account deletion) -- both are
    state transitions, not deletions."
    """

    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class Tenant:
    """"the billing and access boundary -- one university department, research center, or
    individual researcher account." (section 10.1, line 484)
    """

    def __init__(self, name: str, *, entity_id: EntityId | None = None) -> None:
        if not name or not name.strip():
            raise ValueError(
                "Tenant.name must be non-empty; section 10.1 does not define an anonymous "
                "Tenant."
            )
        self._id = entity_id if entity_id is not None else new_entity_id()
        self._name = name
        # Lifecycle: "created at sign-up (SCR-AUTH-02); active indefinitely" (line 487).
        self._status = TenantStatus.ACTIVE

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, User, lines 493-501): Tenant "owns many
        # `User` (via `TenantMembership`)" (line 486). Not implemented in Sprint 0 -- User
        # arrives with future Identity Service work (BACKLOG.md EPIC-01, not yet ticketed by
        # task number for this specific entity).

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, TenantMembership, lines 503-511): the
        # actual Tenant -> Project ownership mechanism referenced at line 486. Also not
        # implemented -- see the module docstring above for why Tenant has no `projects` field
        # as a result.

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, Subscription, lines 613-621): Tenant "owns
        # zero-or-one `Subscription`" (line 486). Deferred to v1.x per section 10.1's own
        # `(v1.x)` tag on the Subscription entity itself.

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, AuditLogEntry, lines 623-631, and section
        # 12.2, line 864): "tenant-level changes (plan, ownership transfer, suspension) are
        # logged... a separate, smaller trail from the Project-scoped one" (line 490). This
        # entity deliberately does NOT write audit entries itself -- per section 12.2 line 864,
        # `IAuditWriter` is "called by Application orchestrators after a Domain state transition
        # succeeds (again, not by Domain entities themselves)". Audit writing is a future
        # Application-layer responsibility, not a gap in this entity.

    @property
    def id(self) -> EntityId:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> TenantStatus:
        return self._status

    def rename(self, new_name: str) -> None:
        """Tenant is "Mutable (name, plan, settings change over time)" (line 488)."""
        if not new_name or not new_name.strip():
            raise ValueError("Tenant.name must be non-empty.")
        self._name = new_name

    def suspend(self) -> None:
        """"suspendable (non-payment)... [a] state transition, not deletion[]" (line 487)."""
        if self._status is TenantStatus.CLOSED:
            raise DomainInvariantViolation(
                "Cannot suspend a closed Tenant. Section 10.1 does not specify a reopening "
                "rule for a closed Tenant (data-retention policy is explicitly flagged as an "
                "open item at line 487); treating `closed` as terminal is the conservative "
                "reading pending that policy, not an inferred business rule."
            )
        self._status = TenantStatus.SUSPENDED

    def close(self) -> None:
        """"closable (account deletion)... [a] state transition, not a deletion" (line 487).

        Section 10.1 does not state whether a `suspended` or `active` Tenant may close
        directly, or whether `closed` can ever transition elsewhere -- both are left as
        explicit open items (data-retention policy, line 487) rather than guessed at here.
        This method allows closing from either `active` or `suspended`, and treats `closed` as
        terminal (no further transition method exists out of it).
        """
        if self._status is TenantStatus.CLOSED:
            raise DomainInvariantViolation("Tenant is already closed.")
        self._status = TenantStatus.CLOSED
