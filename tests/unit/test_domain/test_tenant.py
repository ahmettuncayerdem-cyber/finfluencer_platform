"""Tests for the Tenant entity (BACKLOG.md T-007; PRODUCT_ARCHITECTURE.md section 10.1,
lines 483-491). Each test cites the exact line its invariant comes from.
"""

from __future__ import annotations

import pytest

from finfluencer.domain.entities import DomainInvariantViolation, Tenant, TenantStatus


def test_create_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        Tenant(name="")


def test_create_rejects_whitespace_only_name() -> None:
    with pytest.raises(ValueError):
        Tenant(name="   ")


def test_create_is_active_by_default() -> None:
    # line 487: "created at sign-up (SCR-AUTH-02); active indefinitely"
    tenant = Tenant(name="Acme Research Lab")
    assert tenant.status is TenantStatus.ACTIVE


def test_two_tenants_have_distinct_ids() -> None:
    a = Tenant(name="Lab A")
    b = Tenant(name="Lab B")
    assert a.id != b.id


def test_rename_updates_name() -> None:
    # line 488: "Mutable (name, plan, settings change over time)."
    tenant = Tenant(name="Old Name")
    tenant.rename("New Name")
    assert tenant.name == "New Name"


def test_rename_rejects_empty_name() -> None:
    tenant = Tenant(name="Lab")
    with pytest.raises(ValueError):
        tenant.rename("")


def test_suspend_transitions_status() -> None:
    # line 487: "suspendable (non-payment)... a state transition, not deletion[]"
    tenant = Tenant(name="Lab")
    tenant.suspend()
    assert tenant.status is TenantStatus.SUSPENDED


def test_suspend_is_a_state_transition_not_a_deletion() -> None:
    # The entity must still exist, with identity and name intact, after suspend().
    tenant = Tenant(name="Lab")
    tenant_id = tenant.id
    tenant.suspend()
    assert tenant.id == tenant_id
    assert tenant.name == "Lab"


def test_close_transitions_status() -> None:
    # line 487: "closable (account deletion)... a state transition, not a deletion"
    tenant = Tenant(name="Lab")
    tenant.close()
    assert tenant.status is TenantStatus.CLOSED


def test_close_is_a_state_transition_not_a_deletion() -> None:
    tenant = Tenant(name="Lab")
    tenant_id = tenant.id
    tenant.close()
    assert tenant.id == tenant_id
    assert tenant.name == "Lab"


def test_close_from_suspended_is_allowed() -> None:
    tenant = Tenant(name="Lab")
    tenant.suspend()
    tenant.close()
    assert tenant.status is TenantStatus.CLOSED


def test_close_twice_raises() -> None:
    tenant = Tenant(name="Lab")
    tenant.close()
    with pytest.raises(DomainInvariantViolation):
        tenant.close()


def test_suspend_a_closed_tenant_raises() -> None:
    # Closed is treated as terminal pending the data-retention policy the document itself
    # flags as an open item (line 487) -- see tenant.py's suspend() docstring.
    tenant = Tenant(name="Lab")
    tenant.close()
    with pytest.raises(DomainInvariantViolation):
        tenant.suspend()


def test_no_reactivate_method_exists() -> None:
    # Deliberate: section 10.1 never names a reactivation transition, so none is implemented
    # (see the "Do not infer behavior" scope boundary in tenant.py's suspend() docstring).
    tenant = Tenant(name="Lab")
    assert not hasattr(tenant, "reactivate")


def test_tenant_has_no_projects_collection() -> None:
    # Architectural invariant from the forensic evidence review: Tenant's ownership of
    # Project is indirect, through TenantMembership (line 486). Tenant must not expose an
    # in-memory `projects` collection that would fabricate a direct relationship.
    tenant = Tenant(name="Lab")
    assert not hasattr(tenant, "projects")
