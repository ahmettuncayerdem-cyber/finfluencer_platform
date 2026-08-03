"""Tests for `api.routes.reporting` (BACKLOG.md T-028).

Proves the full Reporting Service flow (`GenerateReport` -> `GetReport` -> `FinalizeReport` ->
`GenerateExport`) is reachable over real HTTP for the first time, driven through the real
Collection -> demo-Analysis -> Reporting chain (not mocks standing in for the whole thing), same
discipline as `test_routes_collection.py`/`test_routes_analysis.py`.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from finfluencer.bootstrap import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def _real_analysis_run(client: TestClient, *, idempotency_key: str) -> tuple[str, str]:
    """Drive the real Collection -> demo-Analysis chain and return (project_id, analysis_run_id)
    for a genuinely `completed` `AnalysisRun`.
    """
    dataset_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    cr = client.post(
        f"/datasets/{dataset_id}/collection-runs",
        json={"dataset_id": dataset_id, "idempotency_key": str(uuid.uuid4())},
    )
    assert cr.status_code == 200
    collection_run_id = cr.json()["id"]

    ar = client.post(
        f"/collection-runs/{collection_run_id}/analysis-runs",
        json={
            "project_id": project_id, "collection_run_id": collection_run_id,
            "analysis_type_id": str(uuid.uuid4()), "analysis_type_version": "1.0.0",
            "idempotency_key": idempotency_key,
        },
    )
    assert ar.status_code == 200
    return project_id, ar.json()["id"]


def test_full_generate_get_finalize_export_flow(client: TestClient) -> None:
    project_id, analysis_run_id = _real_analysis_run(client, idempotency_key="flow-1")

    generated = client.post(
        f"/projects/{project_id}/reports", json={"analysis_run_id": analysis_run_id},
    )
    assert generated.status_code == 200
    report_id = generated.json()["id"]
    assert generated.json()["status"] == "draft"
    assert generated.json()["citation_count"] == 1

    fetched = client.get(f"/projects/{project_id}/reports/{report_id}")
    assert fetched.status_code == 200
    assert fetched.json()["version"] == 1
    assert fetched.json()["status"] == "draft"

    finalized = client.post(f"/projects/{project_id}/reports/{report_id}/finalize")
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "finalized"

    exported = client.post(f"/projects/{project_id}/reports/{report_id}/exports")
    assert exported.status_code == 200
    assert exported.headers["content-type"] == "application/pdf"
    assert len(exported.content) > 0
    assert exported.content[:4] == b"%PDF"


def test_export_before_finalize_is_rejected(client: TestClient) -> None:
    project_id, analysis_run_id = _real_analysis_run(client, idempotency_key="flow-2")
    generated = client.post(
        f"/projects/{project_id}/reports", json={"analysis_run_id": analysis_run_id},
    )
    report_id = generated.json()["id"]

    response = client.post(f"/projects/{project_id}/reports/{report_id}/exports")

    assert response.status_code == 404
    assert "not finalized" in response.json()["detail"]


def test_export_is_idempotent_and_returns_the_same_bytes_on_repeat_call(
    client: TestClient,
) -> None:
    project_id, analysis_run_id = _real_analysis_run(client, idempotency_key="flow-3")
    report_id = client.post(
        f"/projects/{project_id}/reports", json={"analysis_run_id": analysis_run_id},
    ).json()["id"]
    client.post(f"/projects/{project_id}/reports/{report_id}/finalize")

    first = client.post(f"/projects/{project_id}/reports/{report_id}/exports")
    second = client.post(f"/projects/{project_id}/reports/{report_id}/exports")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.content == second.content
    assert len(first.content) > 0


def test_table_export_succeeds_when_report_cites_two_different_analysis_run_ids_sharing_topics(
    client: TestClient,
) -> None:
    # The demo Analysis Engine only ever produces topics-shaped output (bootstrap.py's own
    # documented limitation) -- a genuine two-AnalysisType (topics + sentiment) table export
    # cannot be demonstrated through this HTTP surface without a real sentiment engine wired in,
    # which is out of this task's scope (see T-028_MIGRATION_RISK_CHECKLIST.md). This test
    # instead proves the *documented, expected* 422 for a topics-only Report -- the real
    # differential success path is already proven at the orchestrator/adapter level by
    # `test_export_report_table_orchestrator.py` (T-026) and
    # `test_table_export_adapter.py` (T-026), unmodified by this task.
    project_id, analysis_run_id = _real_analysis_run(client, idempotency_key="flow-4")
    report_id = client.post(
        f"/projects/{project_id}/reports", json={"analysis_run_id": analysis_run_id},
    ).json()["id"]
    client.post(f"/projects/{project_id}/reports/{report_id}/finalize")

    response = client.get(f"/projects/{project_id}/reports/{report_id}/table")

    assert response.status_code == 422
    assert "topics.parquet" in response.json()["detail"] or "sentiment" in response.json()["detail"]


def test_get_report_for_unknown_id_is_404(client: TestClient) -> None:
    response = client.get(f"/projects/{uuid.uuid4()}/reports/{uuid.uuid4()}")
    assert response.status_code == 404


def test_generate_report_for_unknown_analysis_run_is_404(client: TestClient) -> None:
    response = client.post(
        f"/projects/{uuid.uuid4()}/reports", json={"analysis_run_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def test_generate_report_rejects_unknown_fields(client: TestClient) -> None:
    project_id, analysis_run_id = _real_analysis_run(client, idempotency_key="flow-5")
    response = client.post(
        f"/projects/{project_id}/reports",
        json={"analysis_run_id": analysis_run_id, "extra": "nope"},
    )
    assert response.status_code == 422
