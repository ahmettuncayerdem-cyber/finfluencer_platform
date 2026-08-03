"""Tests for `api.routes.analysis` (BACKLOG.md T-028).

Proves `StartAnalysisRun` is reachable over real HTTP for the first time -- T-020's own
orchestrator was fully tested at the Application layer, but never called through a route before
this task. Uses the same real fixture-backed `CollectionEngineAdapter` chain
`test_routes_collection.py` already proves, then analyzes its real output via bootstrap's demo
`IAnalysisEngine` stand-in (not a mock -- see `bootstrap.py`'s own docstring for why it exists).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from finfluencer.bootstrap import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def _start_collection_run(client: TestClient) -> str:
    dataset_id = str(uuid.uuid4())
    response = client.post(
        f"/datasets/{dataset_id}/collection-runs",
        json={"dataset_id": dataset_id, "idempotency_key": str(uuid.uuid4())},
    )
    assert response.status_code == 200
    return response.json()["id"]  # type: ignore[no-any-return]


def test_start_analysis_run_completes_against_real_fixture_collected_data(
    client: TestClient,
) -> None:
    collection_run_id = _start_collection_run(client)
    project_id = str(uuid.uuid4())

    response = client.post(
        f"/collection-runs/{collection_run_id}/analysis-runs",
        json={
            "project_id": project_id, "collection_run_id": collection_run_id,
            "analysis_type_id": str(uuid.uuid4()), "analysis_type_version": "1.0.0",
            "idempotency_key": "a-1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert body["collection_run_id"] == collection_run_id
    assert body["status"] == "completed"
    assert body["row_count"] == 8  # matches test_routes_collection.py's own known fixture total
    assert body["topic_count"] and body["topic_count"] > 0
    uuid.UUID(body["id"])


def test_path_and_body_collection_run_id_mismatch_is_a_client_error(client: TestClient) -> None:
    collection_run_id = _start_collection_run(client)
    other_id = str(uuid.uuid4())
    response = client.post(
        f"/collection-runs/{collection_run_id}/analysis-runs",
        json={
            "project_id": str(uuid.uuid4()), "collection_run_id": other_id,
            "analysis_type_id": str(uuid.uuid4()), "analysis_type_version": "1.0.0",
            "idempotency_key": "a-2",
        },
    )
    assert response.status_code == 400


def test_duplicate_dispatch_returns_the_same_run(client: TestClient) -> None:
    collection_run_id = _start_collection_run(client)
    body = {
        "project_id": str(uuid.uuid4()), "collection_run_id": collection_run_id,
        "analysis_type_id": str(uuid.uuid4()), "analysis_type_version": "1.0.0",
        "idempotency_key": "a-dup",
    }
    first = client.post(f"/collection-runs/{collection_run_id}/analysis-runs", json=body)
    second = client.post(f"/collection-runs/{collection_run_id}/analysis-runs", json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_start_analysis_run_rejects_unknown_fields(client: TestClient) -> None:
    collection_run_id = _start_collection_run(client)
    response = client.post(
        f"/collection-runs/{collection_run_id}/analysis-runs",
        json={
            "project_id": str(uuid.uuid4()), "collection_run_id": collection_run_id,
            "analysis_type_id": str(uuid.uuid4()), "analysis_type_version": "1.0.0",
            "idempotency_key": "a-3", "extra": "nope",
        },
    )
    assert response.status_code == 422
