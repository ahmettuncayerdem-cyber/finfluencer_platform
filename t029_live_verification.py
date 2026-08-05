"""T-029 MVP sign-off: end-to-end verification through the real, live-wired FastAPI app.

Companion to `t029_e2e_verification.py` (fixture/demo data, already 31/31 passing) -- this
script exercises the exact same product-visible workflow, but with `create_app
(use_live_collection=True)` (bootstrap.py, added after Release Blocker #3's T-015/T-017
live-network verification) and the two Release Blocker #6 real-engine `analysis_type_id`s
(`TOPIC_MODELING_ANALYSIS_TYPE_ID`/`SENTIMENT_ANALYSIS_TYPE_ID`), so both the collection AND
the analysis steps run for real: real YouTube network I/O, real BERTopic topic modeling, real
transformer-based sentiment classification. No AI/LLM call anywhere in this path -- topic
modeling is BERTopic (UMAP + HDBSCAN + c-TF-IDF over sentence-transformer embeddings) and
sentiment is a local transformer classifier; both are statistical/ML inference over already
-collected raw text, not a call to any generative AI service.

Not a pytest test (deliberately -- real YouTube API quota, real compute-heavy ML inference,
must never run automatically in CI). Run manually, once, per BACKLOG.md T-029's own
"Role: Human sign-off" / "Verification: the end-to-end run itself, performed once, live":

    poetry run python t029_live_verification.py

Requires `YT_API_KEY`/`ANON_SALT` set (same as scripts/t015_live_smoke_test.py). Collects the
full configured roster (config/analysts.yaml) -- more representative of real MVP usage than a
single analyst, and T-015/T-017 already confirmed quota headroom comfortably covers one
analyst's full pipeline (~400 units), so four analysts remains well within a normal daily quota.
Expect this to take noticeably longer than the fixture-based script: real network latency for
collection, plus real BERTopic (embeddings, UMAP, HDBSCAN) and transformer inference for
analysis.

Every step prints PASS/FAIL with the evidence. Exits nonzero on any unexpected failure.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "src")

from fastapi.testclient import TestClient

from finfluencer.bootstrap import (
    SENTIMENT_ANALYSIS_TYPE_ID,
    TOPIC_MODELING_ANALYSIS_TYPE_ID,
    create_app,
)

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, evidence: str) -> None:
    RESULTS.append((name, condition, evidence))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}\n       evidence: {evidence}")


def main() -> int:
    import uuid

    base_root = Path(tempfile.mkdtemp(prefix="t029-live-"))
    print(f"base_root: {base_root}")
    app = create_app(collection_base_root=base_root, use_live_collection=True)
    client = TestClient(app)

    # ---- 1. Project creation ----
    tenant_id = str(uuid.uuid4())
    r = client.post(
        "/projects",
        json={"tenant_id": tenant_id, "name": "T-029 Live MVP Sign-off", "idempotency_key": str(uuid.uuid4())},
    )
    check("1. POST /projects returns 200/201", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:300]}")
    project_id = r.json()["id"]

    # ---- 2. Real, live Collection Run (real YouTube network I/O, real quota spend) ----
    dataset_id = str(uuid.uuid4())
    print("Starting live collection run -- real network call, this will take a while...")
    r = client.post(
        f"/datasets/{dataset_id}/collection-runs",
        json={"dataset_id": dataset_id, "idempotency_key": str(uuid.uuid4())},
    )
    check("2a. POST .../collection-runs (live) returns 200/201", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:500]}")
    coll = r.json()
    collection_run_id = coll["id"]
    check("2b. Live CollectionRun reaches completed status", coll.get("status") == "completed", f"body={coll}")

    data_files = list(base_root.glob(f"{collection_run_id}/**/*.parquet"))
    check("2c. Real parquet files written to disk", len(data_files) > 0, f"found {len(data_files)} files under {base_root}/{collection_run_id}")

    # ---- 3. Real Analysis Run: topics (BERTopic, TOPIC_MODELING_ANALYSIS_TYPE_ID) ----
    print("Starting real topic-modeling AnalysisRun (BERTopic) -- this will take a while...")
    r = client.post(
        f"/collection-runs/{collection_run_id}/analysis-runs",
        json={
            "project_id": project_id,
            "collection_run_id": collection_run_id,
            "analysis_type_id": str(TOPIC_MODELING_ANALYSIS_TYPE_ID),
            "analysis_type_version": "1.0.0",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    check("3a. POST .../analysis-runs (real topics) returns 200/201", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:500]}")
    topics_run = r.json()
    topics_run_id = topics_run["id"]
    check("3b. Real topics AnalysisRun reaches completed status", topics_run.get("status") == "completed", f"body={topics_run}")
    check("3c. Real topics AnalysisRun produced nonzero topic_count", topics_run.get("topic_count", 0) > 0, f"body={topics_run}")

    # ---- 4. Real Analysis Run: sentiment (transformer classifier, SENTIMENT_ANALYSIS_TYPE_ID) ----
    print("Starting real sentiment AnalysisRun (transformer classifier)...")
    r = client.post(
        f"/collection-runs/{collection_run_id}/analysis-runs",
        json={
            "project_id": project_id,
            "collection_run_id": collection_run_id,
            "analysis_type_id": str(SENTIMENT_ANALYSIS_TYPE_ID),
            "analysis_type_version": "1.0.0",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    check("4a. POST .../analysis-runs (real sentiment) returns 200/201", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:500]}")
    sentiment_run = r.json()
    sentiment_run_id = sentiment_run["id"]
    check("4b. Real sentiment AnalysisRun reaches completed status", sentiment_run.get("status") == "completed", f"body={sentiment_run}")

    # ---- 5. Report: cite both real AnalysisRuns ----
    r = client.post(f"/projects/{project_id}/reports", json={"analysis_run_id": topics_run_id})
    check("5a. POST .../reports (topics citation) returns 200/201", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:400]}")
    report = r.json()
    report_id = report["id"]

    r = client.post(
        f"/projects/{project_id}/reports",
        json={"analysis_run_id": sentiment_run_id, "existing_report_id": report_id},
    )
    check("5b. Second citation (sentiment) into same Report succeeds", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:400]}")
    check("5c. Report has 2 citations (topics + sentiment)", r.json().get("citation_count") == 2, f"body={r.json()}")

    # ---- 6. Finalize ----
    r = client.post(f"/projects/{project_id}/reports/{report_id}/finalize")
    check("6. Finalize returns 200, status=finalized", r.status_code == 200 and r.json().get("status") == "finalized", f"status={r.status_code} body={r.text[:300]}")

    # ---- 7. CSV / table export -- with BOTH topics and sentiment cited, this should now
    # succeed for real (200), not the documented 422 the fixture-only script hits. ----
    r = client.get(f"/projects/{project_id}/reports/{report_id}/table")
    if r.status_code == 200:
        table_evidence = f"{len(r.content)} bytes CSV, X-Row-Count={r.headers.get('X-Row-Count')}"
    else:
        table_evidence = f"status={r.status_code} body={r.text[:400]}"
    check(
        "7. GET .../table succeeds (200) -- both topics and sentiment shapes present",
        r.status_code == 200,
        table_evidence,
    )

    # ---- 8. PDF export, citing raw snapshots, no AI call in the path ----
    r = client.post(f"/projects/{project_id}/reports/{report_id}/exports", json={"format": "pdf"})
    check("8a. PDF export returns 200", r.status_code == 200, f"status={r.status_code}")
    check("8b. Real PDF bytes (starts with %PDF)", r.content[:4] == b"%PDF", f"first_bytes={r.content[:8]!r} len={len(r.content)}")

    # ---- Summary ----
    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = total - passed
    print("\n" + "=" * 70)
    print(f"T-029 LIVE MVP SIGN-OFF: {passed}/{total} checks passed, {failed} failed")
    if failed:
        print("FAILURES:")
        for name, ok, ev in RESULTS:
            if not ok:
                print(f"  - {name}\n    {ev}")
    print("=" * 70)
    print(f"\nAll artifacts on disk under: {base_root}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
