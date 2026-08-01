"""Tests for `api.routes.identity` (BACKLOG.md T-012).

Exercises `POST /projects` through a real HTTP request/response cycle (FastAPI's `TestClient`,
in-process ASGI transport -- no real network socket, but a real HTTP request line, real JSON
(de)serialization, and real routing/dependency-injection, not a direct Python function call).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from finfluencer.bootstrap import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def test_create_project_returns_201_with_project_created_shape(client: TestClient) -> None:
    tenant_id = str(uuid.uuid4())
    response = client.post(
        "/projects",
        json={"tenant_id": tenant_id, "name": "Study", "idempotency_key": "k-1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == tenant_id
    assert body["name"] == "Study"
    assert body["status"] == "active"
    uuid.UUID(body["id"])  # a real, well-formed UUID was generated


def test_create_project_rejects_empty_name(client: TestClient) -> None:
    # Domain's own invariant (Project.__init__, T-007), reached through the full HTTP stack --
    # FastAPI/Pydantic reject an empty string at the DTO layer (CreateProjectRequest requires
    # min_length=1), before the orchestrator is even called.
    response = client.post(
        "/projects",
        json={"tenant_id": str(uuid.uuid4()), "name": "", "idempotency_key": "k-2"},
    )
    assert response.status_code == 422


def test_create_project_rejects_unknown_fields(client: TestClient) -> None:
    # CreateProjectRequest's `extra="forbid"` (T-008) reached through the real HTTP boundary.
    response = client.post(
        "/projects",
        json={
            "tenant_id": str(uuid.uuid4()),
            "name": "Study",
            "idempotency_key": "k-3",
            "not_a_real_field": "x",
        },
    )
    assert response.status_code == 422


def test_two_create_project_calls_produce_distinct_projects(client: TestClient) -> None:
    # T-012 does not implement api.middleware.idempotency (flagged, deferred) -- a duplicate
    # idempotency_key at this route does not yet deduplicate, unlike StartCollectionRun's own
    # orchestrator-level idempotency (T-011). This test documents today's actual behavior, not
    # an aspiration.
    tenant_id = str(uuid.uuid4())
    first = client.post(
        "/projects", json={"tenant_id": tenant_id, "name": "A", "idempotency_key": "same-key"}
    )
    second = client.post(
        "/projects", json={"tenant_id": tenant_id, "name": "B", "idempotency_key": "same-key"}
    )
    assert first.json()["id"] != second.json()["id"]
