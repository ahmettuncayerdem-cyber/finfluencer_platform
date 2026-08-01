"""Integration test for the full Sprint 0 ownership chain (BACKLOG.md T-007).

Exercises the exact chain the forensic evidence review of PRODUCT_ARCHITECTURE.md established:
Tenant -(indirect, via TenantMembership -- out of scope)-> Project -(owns)-> Dataset
-(owns)-> CollectionRun, with Tenant deliberately holding no direct `projects` collection
(section 10.1, line 486).
"""

from __future__ import annotations

from finfluencer.domain.entities import CollectionRun, Dataset, Project, Tenant


def test_full_ownership_chain_wires_together_correctly() -> None:
    tenant = Tenant(name="Acme Research Lab")

    project = Project(tenant_id=tenant.id, name="Financial Influencer Study")
    assert project.tenant_id == tenant.id

    dataset = Dataset(project_id=project.id, name="YouTube Comments, Jan-Jun 2026")
    project.add_dataset(dataset)
    assert dataset.project_id == project.id
    assert dataset in project.datasets

    run = CollectionRun(dataset_id=dataset.id)
    dataset.add_collection_run(run)
    assert run.dataset_id == dataset.id
    assert run in dataset.collection_runs

    # Tenant does not, and must not, expose a direct `projects` collection -- ownership is
    # indirect through TenantMembership, out of Sprint 0 scope (line 486).
    assert not hasattr(tenant, "projects")


def test_collection_run_becomes_a_valid_reproducibility_anchor_once_completed() -> None:
    # line 568: a completed CollectionRun is what "makes it a valid reproducibility anchor" --
    # the property a future AnalysisRun (not yet implemented) will pin to.
    tenant = Tenant(name="Acme Research Lab")
    project = Project(tenant_id=tenant.id, name="Study")
    dataset = Dataset(project_id=project.id, name="Comments")
    project.add_dataset(dataset)
    run = CollectionRun(dataset_id=dataset.id)
    dataset.add_collection_run(run)

    assert run.is_completed is False
    run.start()
    run.complete()
    assert run.is_completed is True
