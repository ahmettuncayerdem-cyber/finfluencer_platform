"""T-029 Phase 2: End-to-end verification script.

Exercises the complete user-visible MVP workflow through the real FastAPI app
(fixture/demo data, since real live-network YouTube collection is environment-blocked
in this sandbox -- see T-015/T-017's own already-confirmed finding, re-confirmed rather
than re-discovered here). Uses the real TestClient (real HTTP request/response cycle,
real routing, real orchestrators, real adapters) -- nothing mocked except the network
transport that T-015/T-017 already established as blocked.

Every step prints PASS/FAIL with the evidence. Exits nonzero on any unexpected failure.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, "src")

from fastapi.testclient import TestClient

from finfluencer.bootstrap import create_app

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, evidence: str) -> None:
    RESULTS.append((name, condition, evidence))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}\n       evidence: {evidence}")


def main() -> int:
    base_root = Path(tempfile.mkdtemp(prefix="t029-e2e-"))
    app = create_app(collection_base_root=base_root)
    client = TestClient(app)

    # ---- 1. Project creation ----
    idem1 = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    r = client.post("/projects", json={"tenant_id": tenant_id, "name": "T-029 Verification Project", "idempotency_key": idem1})
    check("1a. POST /projects returns 200/201", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:300]}")
    project = r.json()
    project_id = project["id"]
    check("1b. Project has active status", project.get("status") == "active", f"body={project}")

    # ---- 2. Collection Run ----
    dataset_id = str(uuid.uuid4())
    idem2 = str(uuid.uuid4())
    r = client.post(
        f"/datasets/{dataset_id}/collection-runs",
        json={"dataset_id": dataset_id, "idempotency_key": idem2},
    )
    check("2a. POST .../collection-runs returns 200/201", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:400]}")
    coll = r.json()
    collection_run_id = coll["id"]
    check("2b. CollectionRun reaches completed status", coll.get("status") == "completed", f"body={coll}")

    # Idempotent replay of Collection Run
    r_replay = client.post(
        f"/datasets/{dataset_id}/collection-runs",
        json={"dataset_id": dataset_id, "idempotency_key": idem2},
    )
    check(
        "2c. Duplicate CollectionRun dispatch (same idempotency_key) returns same run id",
        r_replay.status_code in (200, 201) and r_replay.json().get("id") == collection_run_id,
        f"first_id={collection_run_id} replay_id={r_replay.json().get('id')}",
    )

    # ---- 3. Analysis Run (topics, demo engine) ----
    idem3 = str(uuid.uuid4())
    r = client.post(
        f"/collection-runs/{collection_run_id}/analysis-runs",
        json={
            "project_id": project_id,
            "collection_run_id": collection_run_id,
            "analysis_type_id": str(uuid.uuid4()),
            "analysis_type_version": "1",
            "idempotency_key": idem3,
        },
    )
    check("3a. POST .../analysis-runs (topics) returns 200/201", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:400]}")
    topics_run = r.json()
    topics_run_id = topics_run["id"]
    check("3b. AnalysisRun (topics) reaches completed status", topics_run.get("status") == "completed", f"body={topics_run}")
    check("3c. AnalysisRun (topics) produced nonzero topic_count", topics_run.get("topic_count", 0) > 0, f"body={topics_run}")

    # Second, independent Analysis Run to simulate the "sentiment" half of MVP's
    # acceptance criterion. NOTE (flagged, not concealed): the T-028 demo engine
    # (`_DemoTopicAssignmentEngine`, ADR-0004) always produces topics-shaped output --
    # there is no independently wired sentiment-shaped demo engine reachable via this
    # route. This second run is topics-shaped again, not a real sentiment AnalysisRun.
    idem4 = str(uuid.uuid4())
    r2 = client.post(
        f"/collection-runs/{collection_run_id}/analysis-runs",
        json={
            "project_id": project_id,
            "collection_run_id": collection_run_id,
            "analysis_type_id": str(uuid.uuid4()),
            "analysis_type_version": "1",
            "idempotency_key": idem4,
        },
    )
    second_run = r2.json()
    second_run_id = second_run["id"]
    check(
        "3d. Second AnalysisRun (also topics-shaped -- demo engine has no sentiment path) completes",
        r2.status_code in (200, 201) and second_run.get("status") == "completed",
        f"status={r2.status_code} body={second_run}",
    )

    # ---- 4. Report Generation ----
    r = client.post(
        f"/projects/{project_id}/reports",
        json={"analysis_run_id": topics_run_id},
    )
    check("4a. POST .../reports returns 200/201", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:400]}")
    report = r.json()
    report_id = report["id"]
    check("4b. Report is in draft status with 1 citation", report.get("status") == "draft" and report.get("citation_count") == 1, f"body={report}")

    # Cite second AnalysisRun into the same Report
    r = client.post(
        f"/projects/{project_id}/reports",
        json={"analysis_run_id": second_run_id, "existing_report_id": report_id},
    )
    check("4c. Second citation into same Report succeeds", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:400]}")
    report2 = r.json()
    check("4d. Report now has 2 citations", report2.get("citation_count") == 2, f"body={report2}")

    # ---- 5. Report Retrieval ----
    r = client.get(f"/projects/{project_id}/reports/{report_id}")
    check("5a. GET .../reports/{id} returns 200", r.status_code == 200, f"status={r.status_code} body={r.text[:300]}")
    got = r.json()
    check("5b. Retrieved report matches generated report (id, citation_count)", got.get("id") == report_id and got.get("citation_count") == 2, f"body={got}")

    # ---- 6. Finalize Report ----
    r = client.post(f"/projects/{project_id}/reports/{report_id}/finalize")
    check("6a. POST .../finalize returns 200", r.status_code == 200, f"status={r.status_code} body={r.text[:300]}")
    fin = r.json()
    check("6b. Report status is finalized", fin.get("status") == "finalized", f"body={fin}")

    # Idempotent finalize (finalize twice = no-op, per §11.2 line 727)
    r2 = client.post(f"/projects/{project_id}/reports/{report_id}/finalize")
    check("6c. Second finalize call is a no-op (still 200, still finalized)", r2.status_code == 200 and r2.json().get("status") == "finalized", f"status={r2.status_code} body={r2.text[:300]}")

    # ---- 7. CSV / table export ----
    r = client.get(f"/projects/{project_id}/reports/{report_id}/table")
    # Per T-026/T-028's own documented, expected limitation: since both citations are
    # topics-shaped (no real sentiment AnalysisRun reachable via the demo engine),
    # build_master_table() cannot find a sentiment source table -> expect 422.
    check(
        "7a. GET .../table on a topics-only Report returns the documented 422 (not a crash)",
        r.status_code == 422,
        f"status={r.status_code} body={r.text[:300]}",
    )

    # ---- 8. PDF Export ----
    r = client.post(f"/projects/{project_id}/reports/{report_id}/exports", json={"format": "pdf"})
    check("8a. POST .../exports returns 200", r.status_code == 200, f"status={r.status_code} headers={dict(r.headers)}")
    pdf_bytes = r.content
    check("8b. Response content-type is application/pdf", r.headers.get("content-type", "").startswith("application/pdf"), f"content-type={r.headers.get('content-type')}")
    check("8c. Response body is a real PDF (starts with %PDF)", pdf_bytes[:4] == b"%PDF", f"first_bytes={pdf_bytes[:8]!r} len={len(pdf_bytes)}")

    # ---- 9. Idempotent / repeated execution ----
    r2 = client.post(f"/projects/{project_id}/reports/{report_id}/exports", json={"format": "pdf"})
    check(
        "9a. Repeated PDF export call returns byte-identical content (idempotent replay)",
        r2.status_code == 200 and r2.content == pdf_bytes,
        f"status={r2.status_code} same_bytes={r2.content == pdf_bytes} len1={len(pdf_bytes)} len2={len(r2.content)}",
    )

    # File output check: deterministic exports_root/{report_id}.pdf actually on disk
    exports_root = app.state.exports_root
    expected_path = exports_root / f"{report_id}.pdf"
    check(
        "9b. Deterministic export file exists on disk with correct bytes",
        expected_path.exists() and expected_path.read_bytes() == pdf_bytes,
        f"path={expected_path} exists={expected_path.exists()}",
    )

    # ---- 10. Restart-where-applicable: fresh app instance against the SAME base_root ----
    # In-memory repositories (Report/Export/AnalysisRun/CollectionRun/Project) do NOT
    # survive a fresh create_app() call -- there is no Persistence Layer yet (flagged,
    # known, carried since Sprint 0). This is expected, not a bug: it is exactly what
    # "no Persistence Layer" means. Verified directly rather than assumed.
    app2 = create_app(collection_base_root=base_root)
    client2 = TestClient(app2)
    r = client2.get(f"/projects/{project_id}/reports/{report_id}")
    check(
        "10a. Fresh app instance (same data dir) does NOT retain in-memory Report state (expected -- no Persistence Layer)",
        r.status_code == 404,
        f"status={r.status_code} body={r.text[:200]}",
    )
    # But the collected parquet files on disk (the actual collected DATA, as opposed to
    # repository bookkeeping) do survive, since CollectionEngineAdapter writes real files.
    data_files = list(base_root.glob(f"{collection_run_id}/**/*.parquet"))
    check(
        "10b. Collected data artifacts on disk survive process restart",
        len(data_files) > 0,
        f"found {len(data_files)} parquet files under {base_root}/{collection_run_id}",
    )

    # ---- 11. Failure scenarios ----
    # 11a. Export before finalize
    r_proj = client.post("/projects", json={"tenant_id": str(uuid.uuid4()), "name": "Failure Scenarios Project", "idempotency_key": str(uuid.uuid4())})
    fp_id = r_proj.json()["id"]
    fp_dataset_id = str(uuid.uuid4())
    r_coll = client.post(f"/datasets/{fp_dataset_id}/collection-runs", json={"dataset_id": fp_dataset_id, "idempotency_key": str(uuid.uuid4())})
    fp_coll_id = r_coll.json()["id"]
    r_ana = client.post(
        f"/collection-runs/{fp_coll_id}/analysis-runs",
        json={"project_id": fp_id, "collection_run_id": fp_coll_id, "analysis_type_id": str(uuid.uuid4()), "analysis_type_version": "1", "idempotency_key": str(uuid.uuid4())},
    )
    fp_ana_id = r_ana.json()["id"]
    r_rep = client.post(f"/projects/{fp_id}/reports", json={"analysis_run_id": fp_ana_id})
    fp_report_id = r_rep.json()["id"]
    r_export_draft = client.post(f"/projects/{fp_id}/reports/{fp_report_id}/exports", json={"format": "pdf"})
    check(
        "11a. Exporting a DRAFT (non-finalized) Report is rejected, not silently allowed",
        r_export_draft.status_code == 404,
        f"status={r_export_draft.status_code} body={r_export_draft.text[:300]}",
    )

    # 11b. Get unknown report
    r_unknown = client.get(f"/projects/{project_id}/reports/{uuid.uuid4()}")
    check("11b. GET unknown report_id returns 404", r_unknown.status_code == 404, f"status={r_unknown.status_code} body={r_unknown.text[:200]}")

    # 11c. Generate report from unknown analysis_run_id
    r_unknown_ar = client.post(f"/projects/{project_id}/reports", json={"analysis_run_id": str(uuid.uuid4())})
    check("11c. GenerateReport from unknown analysis_run_id returns 404", r_unknown_ar.status_code == 404, f"status={r_unknown_ar.status_code} body={r_unknown_ar.text[:200]}")

    # 11d. Malformed / unknown-field request rejected at the DTO boundary
    r_bad = client.post("/projects", json={"name": "x", "idempotency_key": str(uuid.uuid4()), "unexpected_field": "nope"})
    check("11d. Unknown field in request body rejected (422)", r_bad.status_code == 422, f"status={r_bad.status_code} body={r_bad.text[:200]}")

    # 11e. Collection run with mismatched path/body dataset_id
    r_mismatch = client.post(f"/datasets/{dataset_id}/collection-runs", json={"dataset_id": str(uuid.uuid4()), "idempotency_key": str(uuid.uuid4())})
    check("11e. Path/body dataset_id mismatch rejected (400)", r_mismatch.status_code == 400, f"status={r_mismatch.status_code} body={r_mismatch.text[:200]}")

    # ---- Summary ----
    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = total - passed
    print("\n" + "=" * 70)
    print(f"T-029 Phase 2 E2E VERIFICATION: {passed}/{total} checks passed, {failed} failed")
    if failed:
        print("FAILURES:")
        for name, ok, ev in RESULTS:
            if not ok:
                print(f"  - {name}\n    {ev}")
    print("=" * 70)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
