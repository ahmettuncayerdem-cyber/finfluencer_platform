"""Tests for `api.routes.collection` (BACKLOG.md T-012).

Proves the Walking Skeleton's most important remaining claim through the real HTTP boundary,
not just in-process object graphs (T-011's own tests already proved the orchestrator level):
`StartCollectionRun` over HTTP actually runs the real T-010 `CollectionEngineAdapter` against
fixture data end to end, and idempotent dispatch (T-011) survives being reached via a route.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from finfluencer.bootstrap import create_app

_EXPECTED_COUNTS_TOTAL_ROWS = 4 + 4 + 8 + 4  # channels + videos + comments + transcripts


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def test_start_collection_run_completes_and_returns_get_collection_run_shape(
    client: TestClient,
) -> None:
    dataset_id = str(uuid.uuid4())
    response = client.post(
        f"/datasets/{dataset_id}/collection-runs",
        json={"dataset_id": dataset_id, "idempotency_key": "run-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dataset_id"] == dataset_id
    assert body["status"] == "completed"
    uuid.UUID(body["id"])


def test_path_and_body_dataset_id_mismatch_is_a_client_error(client: TestClient) -> None:
    dataset_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    response = client.post(
        f"/datasets/{dataset_id}/collection-runs",
        json={"dataset_id": other_id, "idempotency_key": "run-2"},
    )
    assert response.status_code == 400


def test_duplicate_dispatch_through_http_returns_the_same_run_and_does_not_recollect(
    client: TestClient,
) -> None:
    dataset_id = str(uuid.uuid4())
    body = {"dataset_id": dataset_id, "idempotency_key": "run-dup"}

    first = client.post(f"/datasets/{dataset_id}/collection-runs", json=body)
    second = client.post(f"/datasets/{dataset_id}/collection-runs", json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["status"] == "completed"


def test_different_idempotency_keys_create_distinct_runs(client: TestClient) -> None:
    dataset_id = str(uuid.uuid4())
    first = client.post(
        f"/datasets/{dataset_id}/collection-runs",
        json={"dataset_id": dataset_id, "idempotency_key": "run-a"},
    )
    second = client.post(
        f"/datasets/{dataset_id}/collection-runs",
        json={"dataset_id": dataset_id, "idempotency_key": "run-b"},
    )
    assert first.json()["id"] != second.json()["id"]


def test_start_collection_run_rejects_unknown_fields(client: TestClient) -> None:
    dataset_id = str(uuid.uuid4())
    response = client.post(
        f"/datasets/{dataset_id}/collection-runs",
        json={"dataset_id": dataset_id, "idempotency_key": "run-x", "extra": "nope"},
    )
    assert response.status_code == 422
