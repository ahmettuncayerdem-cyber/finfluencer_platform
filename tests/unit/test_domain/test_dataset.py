"""Tests for the Dataset entity (BACKLOG.md T-007; PRODUCT_ARCHITECTURE.md section 10.1,
lines 553-561).
"""

from __future__ import annotations

import uuid

import pytest

from finfluencer.domain.entities import CollectionRun, Dataset, EntityId


def _project_id() -> EntityId:
    return EntityId(uuid.uuid4())


def test_create_requires_project_id() -> None:
    with pytest.raises(ValueError):
        Dataset(project_id=None, name="Comments Jan-Jun")  # type: ignore[arg-type]


def test_create_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        Dataset(project_id=_project_id(), name="")


def test_create_has_no_collection_runs_initially() -> None:
    dataset = Dataset(project_id=_project_id(), name="Comments Jan-Jun")
    assert dataset.collection_runs == ()


def test_rename_updates_name() -> None:
    # line 558: "the `Dataset` record itself (name, description) is mutable"
    dataset = Dataset(project_id=_project_id(), name="Old")
    dataset.rename("New")
    assert dataset.name == "New"


def test_rename_rejects_empty_name() -> None:
    dataset = Dataset(project_id=_project_id(), name="Comments")
    with pytest.raises(ValueError):
        dataset.rename("")


def test_update_description() -> None:
    dataset = Dataset(project_id=_project_id(), name="Comments")
    dataset.update_description("Analyst Roster A, Jan-Jun 2026")
    assert dataset.description == "Analyst Roster A, Jan-Jun 2026"


def test_add_collection_run_appends() -> None:
    # line 556: "owns many `CollectionRun` (its version/state history...)"
    dataset = Dataset(project_id=_project_id(), name="Comments")
    run = CollectionRun(dataset_id=dataset.id)
    dataset.add_collection_run(run)
    assert dataset.collection_runs == (run,)


def test_add_collection_run_rejects_mismatched_dataset_id() -> None:
    dataset = Dataset(project_id=_project_id(), name="Comments")
    other_dataset = Dataset(project_id=_project_id(), name="Other")
    foreign_run = CollectionRun(dataset_id=other_dataset.id)
    with pytest.raises(ValueError):
        dataset.add_collection_run(foreign_run)


def test_collection_runs_view_is_a_tuple_not_the_live_list() -> None:
    # Mutating the returned view must not mutate the Dataset's internal state -- "content
    # only changes by adding a new `CollectionRun`" (line 558), through add_collection_run()
    # exclusively.
    dataset = Dataset(project_id=_project_id(), name="Comments")
    run = CollectionRun(dataset_id=dataset.id)
    dataset.add_collection_run(run)
    view = dataset.collection_runs
    assert isinstance(view, tuple)


def test_no_remove_or_replace_collection_run_method_exists() -> None:
    # line 558: content "is not directly mutable... never by editing existing collected data
    # in place." Enforced by omission: no removal/replacement method exists at all.
    dataset = Dataset(project_id=_project_id(), name="Comments")
    assert not hasattr(dataset, "remove_collection_run")
    assert not hasattr(dataset, "replace_collection_run")


def test_two_datasets_have_distinct_ids() -> None:
    a = Dataset(project_id=_project_id(), name="A")
    b = Dataset(project_id=_project_id(), name="B")
    assert a.id != b.id
