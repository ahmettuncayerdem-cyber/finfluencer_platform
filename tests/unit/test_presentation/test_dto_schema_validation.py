"""Schema validation tests for the T-008 API Contract DTOs (BACKLOG.md T-008).

T-008's own Verification line: "schema validates against a sample request/response." Each DTO
is checked two ways: (1) `Model.model_validate()` against a sample payload -- the schema
actually validates real request/response data, accepting valid samples and rejecting invalid
ones; and (2) a direct assertion on `Model.model_json_schema()`'s structure -- proving a real,
inspectable JSON Schema document exists (required fields, closed object shape, enum/const
values), not merely "whatever Pydantic happens to accept" as an implicit, unexamined side
effect.

Deliberately does NOT import the third-party `jsonschema` package: it is present in this
sandbox's base image but is not a declared project dependency (`pip show jsonschema` here
reports `Location: /usr/lib/python3/dist-packages`, `Required-by:` empty -- an OS-level
package, not something `poetry install` would provide in a real environment). Depending on it
directly in committed test code would silently pass here and fail on a clean install elsewhere,
the same category of sandbox-vs-real-environment gap already flagged for `PYTHONPATH=src` vs a
true editable install. `pydantic` (this file's only import beyond stdlib) is already a declared
dependency (`pyproject.toml`, `pydantic = "^2.5"`) and is what `model_json_schema()` itself
comes from, so validating through it directly is not a weaker check -- it is validating through
the actual source of the schema, with no additional undeclared dependency introduced.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import BaseModel, ValidationError

from finfluencer.presentation.dto import (
    CollectionRunAccepted,
    CreateProjectRequest,
    GetCollectionRunRequest,
    GetCollectionRunResponse,
    ProjectCreated,
    StartCollectionRunRequest,
)


def _assert_valid(model_cls: type[BaseModel], payload: dict) -> None:
    model_cls.model_validate(payload)


def _assert_invalid(model_cls: type[BaseModel], payload: dict) -> None:
    with pytest.raises(ValidationError):
        model_cls.model_validate(payload)


# ---------------------------------------------------------------------------
# Schema-shape checks: prove a genuine JSON Schema document exists per DTO,
# with the closed-object / required-fields shape core/contracts.py's own
# convention establishes (extra="forbid" -> additionalProperties: false).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model_cls", "expected_required"),
    [
        (CreateProjectRequest, {"tenant_id", "name", "idempotency_key"}),
        (ProjectCreated, {"id", "tenant_id", "name", "status"}),
        (StartCollectionRunRequest, {"dataset_id", "idempotency_key"}),
        (CollectionRunAccepted, {"id", "dataset_id", "status"}),
        (GetCollectionRunRequest, {"collection_run_id"}),
        (GetCollectionRunResponse, {"id", "dataset_id", "status"}),
    ],
)
def test_schema_is_a_closed_object_with_expected_required_fields(
    model_cls: type[BaseModel], expected_required: set[str]
) -> None:
    schema = model_cls.model_json_schema()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == expected_required


def test_project_created_status_schema_is_the_two_value_enum() -> None:
    # section 10.1 line 547: Project lifecycle names only active/archived.
    schema = ProjectCreated.model_json_schema()
    assert schema["properties"]["status"]["enum"] == ["active", "archived"]


def test_collection_run_accepted_status_schema_is_locked_to_queued() -> None:
    # section 11.2 line 689: StartCollectionRun always returns `queued`.
    schema = CollectionRunAccepted.model_json_schema()
    assert schema["properties"]["status"]["const"] == "queued"


def test_get_collection_run_response_status_schema_is_the_four_value_enum() -> None:
    # section 10.1 line 567: the full CollectionRunStatus range.
    schema = GetCollectionRunResponse.model_json_schema()
    assert schema["properties"]["status"]["enum"] == [
        "queued",
        "running",
        "completed",
        "failed",
    ]


# ---------------------------------------------------------------------------
# 1. CreateProject (Identity Service, PRODUCT_ARCHITECTURE.md section 11.2 line 657)
# ---------------------------------------------------------------------------


def test_create_project_request_sample_is_valid() -> None:
    sample = {
        "tenant_id": str(uuid.uuid4()),
        "name": "Financial Influencer Study",
        "idempotency_key": "req-2026-08-01-0001",
    }
    _assert_valid(CreateProjectRequest, sample)


def test_create_project_request_missing_idempotency_key_is_invalid() -> None:
    # line 662: "CreateTenant/CreateProject require a client idempotency key."
    sample = {"tenant_id": str(uuid.uuid4()), "name": "Study"}
    _assert_invalid(CreateProjectRequest, sample)


def test_create_project_request_rejects_unknown_field() -> None:
    sample = {
        "tenant_id": str(uuid.uuid4()),
        "name": "Study",
        "idempotency_key": "k1",
        "unexpected_field": "should be rejected",
    }
    _assert_invalid(CreateProjectRequest, sample)


def test_create_project_request_rejects_non_uuid_tenant_id() -> None:
    sample = {"tenant_id": "not-a-uuid", "name": "Study", "idempotency_key": "k1"}
    _assert_invalid(CreateProjectRequest, sample)


def test_project_created_response_sample_is_valid() -> None:
    sample = {
        "id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "name": "Financial Influencer Study",
        "status": "active",
    }
    _assert_valid(ProjectCreated, sample)


def test_project_created_response_rejects_unknown_status() -> None:
    sample = {
        "id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "name": "Study",
        "status": "deleted",
    }
    _assert_invalid(ProjectCreated, sample)


# ---------------------------------------------------------------------------
# 2. StartCollectionRun (Collection Service, section 11.2 line 683)
# ---------------------------------------------------------------------------


def test_start_collection_run_request_sample_is_valid() -> None:
    sample = {
        "dataset_id": str(uuid.uuid4()),
        "idempotency_key": "req-2026-08-01-0002",
    }
    _assert_valid(StartCollectionRunRequest, sample)


def test_start_collection_run_request_missing_idempotency_key_is_invalid() -> None:
    # line 688: "StartCollectionRun requires an idempotency key."
    sample = {"dataset_id": str(uuid.uuid4())}
    _assert_invalid(StartCollectionRunRequest, sample)


def test_collection_run_accepted_response_sample_is_valid() -> None:
    sample = {
        "id": str(uuid.uuid4()),
        "dataset_id": str(uuid.uuid4()),
        "status": "queued",
    }
    _assert_valid(CollectionRunAccepted, sample)


def test_collection_run_accepted_rejects_non_queued_status() -> None:
    # line 689: StartCollectionRun "returns a CollectionRun in `queued` state immediately" --
    # CollectionRunAccepted's status is locked to that one literal.
    sample = {
        "id": str(uuid.uuid4()),
        "dataset_id": str(uuid.uuid4()),
        "status": "running",
    }
    _assert_invalid(CollectionRunAccepted, sample)


# ---------------------------------------------------------------------------
# 3. GetCollectionRun (Collection Service, section 11.2 line 684)
# ---------------------------------------------------------------------------


def test_get_collection_run_request_sample_is_valid() -> None:
    sample = {"collection_run_id": str(uuid.uuid4())}
    _assert_valid(GetCollectionRunRequest, sample)


@pytest.mark.parametrize("status", ["queued", "running", "completed", "failed"])
def test_get_collection_run_response_sample_is_valid_for_every_status(status: str) -> None:
    # section 10.1 line 567: the full CollectionRunStatus range.
    sample = {
        "id": str(uuid.uuid4()),
        "dataset_id": str(uuid.uuid4()),
        "status": status,
    }
    _assert_valid(GetCollectionRunResponse, sample)


def test_get_collection_run_response_rejects_unknown_status() -> None:
    sample = {
        "id": str(uuid.uuid4()),
        "dataset_id": str(uuid.uuid4()),
        "status": "archived",  # a Project status, not a CollectionRun status
    }
    _assert_invalid(GetCollectionRunResponse, sample)


def test_get_collection_run_response_rejects_non_uuid_id() -> None:
    sample = {
        "id": "not-a-uuid",
        "dataset_id": str(uuid.uuid4()),
        "status": "queued",
    }
    _assert_invalid(GetCollectionRunResponse, sample)
