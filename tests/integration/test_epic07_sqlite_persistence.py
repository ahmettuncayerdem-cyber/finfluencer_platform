"""EPIC-07' integration test: real cross-`create_app()`-instance durability via `db_url`.

This is the test that would have caught the "add-once-then-mutate" gap this epic's own work
found (see `domain/repositories.py`'s module docstring and `ICollectionRunRepository`/
`IAnalysisRunRepository`/`IReportRepository`'s `save()` additions): it drives a full real HTTP
workflow (project -> collection run -> analysis run -> report -> finalize) through one
`create_app(db_url=...)` instance, then builds a **second, independent** `create_app()` instance
pointed at the **same** `db_url` and proves every piece of state -- including state that was
only ever reached via a mutate-after-`add()`/mutate-after-`get_by_id()` path, not a fresh
`add()` -- is visible there. Two separate `create_app()` calls only share state through the
database; nothing here relies on shared Python object references, unlike every existing
in-memory-repository test in this suite (T-013/T-017/T-029 etc.).

Also proves the *default* (`db_url=None`) behavior is unchanged: `create_app()` with no `db_url`
still gets fresh, non-durable in-memory repositories, exactly as it always did (existing tests,
e.g. `t029_e2e_verification.py` check 10a, already assert this and must keep passing unmodified).
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from finfluencer.bootstrap import create_app


def _real_db_url(tmp_path: Path) -> str:
    db_path = tmp_path / "epic07_persistence_test.db"
    return f"sqlite:///{db_path}"


def test_report_finalize_and_citations_survive_a_fresh_create_app_instance(
    tmp_path: Path,
) -> None:
    db_url = _real_db_url(tmp_path)
    base_root = Path(tempfile.mkdtemp(prefix="epic07-persistence-"))

    # ---- Instance A: build the full workflow up to a finalized, 1-citation Report. ----
    app_a = create_app(collection_base_root=base_root, db_url=db_url)
    client_a = TestClient(app_a)

    tenant_id = str(uuid.uuid4())
    r = client_a.post(
        "/projects",
        json={"tenant_id": tenant_id, "name": "EPIC-07 Persistence Test", "idempotency_key": str(uuid.uuid4())},
    )
    assert r.status_code in (200, 201), r.text
    project_id = r.json()["id"]

    dataset_id = str(uuid.uuid4())
    r = client_a.post(
        f"/datasets/{dataset_id}/collection-runs",
        json={"dataset_id": dataset_id, "idempotency_key": str(uuid.uuid4())},
    )
    assert r.status_code in (200, 201), r.text
    collection_run = r.json()
    collection_run_id = collection_run["id"]
    # This is the exact assertion that would have failed silently-wrong (status stuck at
    # "queued" in the DB) before save() was added to ICollectionRunRepository: the HTTP
    # response's status comes from the in-memory object the orchestrator already held, not
    # from a re-read of storage, so a missing save() would NOT have been caught here -- it is
    # caught below, when Instance B re-reads via a fresh repository instance instead.
    assert collection_run["status"] == "completed", collection_run

    r = client_a.post(
        f"/collection-runs/{collection_run_id}/analysis-runs",
        json={
            "project_id": project_id,
            "collection_run_id": collection_run_id,
            "analysis_type_id": str(uuid.uuid4()),
            "analysis_type_version": "1",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert r.status_code in (200, 201), r.text
    analysis_run = r.json()
    analysis_run_id = analysis_run["id"]
    assert analysis_run["status"] == "completed", analysis_run

    r = client_a.post(f"/projects/{project_id}/reports", json={"analysis_run_id": analysis_run_id})
    assert r.status_code in (200, 201), r.text
    report = r.json()
    report_id = report["id"]
    assert report["status"] == "draft"
    assert report["citation_count"] == 1

    r = client_a.post(f"/projects/{project_id}/reports/{report_id}/finalize")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "finalized"

    # ---- Instance B: a genuinely separate create_app() call, same db_url. ----
    # No object from Instance A is reachable here -- app_a/client_a are never referenced again.
    app_b = create_app(collection_base_root=base_root, db_url=db_url)
    client_b = TestClient(app_b)

    r = client_b.get(f"/projects/{project_id}/reports/{report_id}")
    assert r.status_code == 200, (
        f"Report not found via a fresh create_app() instance sharing the same db_url -- "
        f"real cross-instance persistence is broken. status={r.status_code} body={r.text}"
    )
    reloaded = r.json()
    assert reloaded["id"] == report_id
    assert reloaded["status"] == "finalized", (
        "Report status reverted to 'draft' on reload -- this is exactly the "
        "IReportRepository.save() gap this epic's work fixed (FinalizeReportOrchestrator "
        "mutates a Report fetched via get_by_id() with no re-save call otherwise)."
    )
    assert reloaded["citation_count"] == 1, (
        "Citation lost on reload -- this is the IReportRepository.save() gap "
        "(GenerateReportOrchestrator mutates via add_citation() after add() with no "
        "re-save call otherwise)."
    )


def test_create_app_without_db_url_still_uses_fresh_non_durable_repositories(
    tmp_path: Path,
) -> None:
    """Regression guard for the *default* path -- must remain byte-for-byte the pre-EPIC-07'
    behavior every existing in-memory-repository test in this suite depends on (same shape as
    `t029_e2e_verification.py` check 10a, expressed as a proper pytest assertion here).
    """
    base_root = Path(tempfile.mkdtemp(prefix="epic07-persistence-default-"))

    app_a = create_app(collection_base_root=base_root)
    client_a = TestClient(app_a)

    r = client_a.post(
        "/projects",
        json={
            "tenant_id": str(uuid.uuid4()),
            "name": "No DB URL",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert r.status_code in (200, 201), r.text
    project_id = r.json()["id"]

    dataset_id = str(uuid.uuid4())
    r = client_a.post(
        f"/datasets/{dataset_id}/collection-runs",
        json={"dataset_id": dataset_id, "idempotency_key": str(uuid.uuid4())},
    )
    assert r.status_code in (200, 201), r.text
    collection_run_id = r.json()["id"]

    r = client_a.post(
        f"/collection-runs/{collection_run_id}/analysis-runs",
        json={
            "project_id": project_id,
            "collection_run_id": collection_run_id,
            "analysis_type_id": str(uuid.uuid4()),
            "analysis_type_version": "1",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert r.status_code in (200, 201), r.text
    analysis_run_id = r.json()["id"]

    r = client_a.post(f"/projects/{project_id}/reports", json={"analysis_run_id": analysis_run_id})
    assert r.status_code in (200, 201), r.text
    report_id = r.json()["id"]

    # Second, independent create_app() call, same base_root, no db_url -- must NOT see the
    # Report Instance A just created (identical reasoning to t029_e2e_verification.py's own
    # check 10a, kept passing unmodified by this epic's work).
    app_b = create_app(collection_base_root=base_root)
    client_b = TestClient(app_b)
    r = client_b.get(f"/projects/{project_id}/reports/{report_id}")
    assert r.status_code == 404, (
        f"Report leaked across create_app() instances with no db_url -- the default path must "
        f"stay non-durable. status={r.status_code} body={r.text}"
    )
