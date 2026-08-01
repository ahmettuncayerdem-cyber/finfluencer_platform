"""Tests for the Project entity -- the root aggregate (BACKLOG.md T-007;
PRODUCT_ARCHITECTURE.md section 10.1, lines 543-551).
"""

from __future__ import annotations

import uuid

import pytest

from finfluencer.domain.entities import (
    Dataset,
    DomainInvariantViolation,
    EntityId,
    Project,
    ProjectStatus,
)


def _tenant_id() -> EntityId:
    return EntityId(uuid.uuid4())


def test_create_requires_tenant_id() -> None:
    with pytest.raises(ValueError):
        Project(tenant_id=None, name="Financial Influencer Study")  # type: ignore[arg-type]


def test_create_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        Project(tenant_id=_tenant_id(), name="")


def test_create_is_active_by_default() -> None:
    project = Project(tenant_id=_tenant_id(), name="Study")
    assert project.status is ProjectStatus.ACTIVE


def test_create_has_no_datasets_initially() -> None:
    project = Project(tenant_id=_tenant_id(), name="Study")
    assert project.datasets == ()


def test_rename_while_active_updates_name() -> None:
    # line 548: "Mutable while active (roster, config)"
    project = Project(tenant_id=_tenant_id(), name="Old")
    project.rename("New")
    assert project.name == "New"


def test_rename_rejects_empty_name() -> None:
    project = Project(tenant_id=_tenant_id(), name="Study")
    with pytest.raises(ValueError):
        project.rename("")


def test_add_dataset_appends() -> None:
    # line 546: "owns many `Dataset`"
    project = Project(tenant_id=_tenant_id(), name="Study")
    dataset = Dataset(project_id=project.id, name="Comments")
    project.add_dataset(dataset)
    assert project.datasets == (dataset,)


def test_add_dataset_rejects_mismatched_project_id() -> None:
    project = Project(tenant_id=_tenant_id(), name="Study")
    other_project = Project(tenant_id=_tenant_id(), name="Other Study")
    foreign_dataset = Dataset(project_id=other_project.id, name="Comments")
    with pytest.raises(ValueError):
        project.add_dataset(foreign_dataset)


def test_archive_transitions_status() -> None:
    # line 548: "the `active -> archived` transition is a one-way state change"
    project = Project(tenant_id=_tenant_id(), name="Study")
    project.archive()
    assert project.status is ProjectStatus.ARCHIVED


def test_archive_twice_raises() -> None:
    project = Project(tenant_id=_tenant_id(), name="Study")
    project.archive()
    with pytest.raises(DomainInvariantViolation):
        project.archive()


def test_rename_after_archive_raises() -> None:
    # "freezes everything inside the aggregate" (line 548) -- Project's own mutators must
    # refuse once archived.
    project = Project(tenant_id=_tenant_id(), name="Study")
    project.archive()
    with pytest.raises(DomainInvariantViolation):
        project.rename("New Name")


def test_add_dataset_after_archive_raises() -> None:
    project = Project(tenant_id=_tenant_id(), name="Study")
    project.archive()
    dataset = Dataset(project_id=project.id, name="Comments")
    with pytest.raises(DomainInvariantViolation):
        project.add_dataset(dataset)


def test_no_unarchive_or_reactivate_method_exists() -> None:
    # "one-way state change" (line 548) is explicit, not merely implied -- no un-archive
    # method is implemented.
    project = Project(tenant_id=_tenant_id(), name="Study")
    assert not hasattr(project, "unarchive")
    assert not hasattr(project, "reactivate")


def test_datasets_already_added_survive_archival_readable() -> None:
    # Archival freezes further *mutation*; it must not delete data already owned by the
    # aggregate (section 10.1 explicitly distinguishes archival from deletion for every
    # entity it discusses, e.g. Tenant line 487).
    project = Project(tenant_id=_tenant_id(), name="Study")
    dataset = Dataset(project_id=project.id, name="Comments")
    project.add_dataset(dataset)
    project.archive()
    assert project.datasets == (dataset,)


def test_two_projects_have_distinct_ids() -> None:
    a = Project(tenant_id=_tenant_id(), name="A")
    b = Project(tenant_id=_tenant_id(), name="B")
    assert a.id != b.id
