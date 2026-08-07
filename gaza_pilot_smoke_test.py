"""Gaza pilot end-to-end SMOKE TEST -- connectivity + full pipeline validation only.

Explicitly NOT the Phase 3 Pilot Collection Plan (docs/research/
GAZA_PILOT_PHASE2_INFRASTRUCTURE.md sec.7) and NOT the Phase 5 full study -- per the
operator's own instruction (2026-08-07): "verify the new API key connectivity, switch to the
English sentiment model, make the minimum config changes for the Gaza pilot, and run an
end-to-end pilot validation only -- do not start large-scale data collection yet."

Mirrors t029_live_verification.py's own proven pattern exactly (same create_app(...,
use_live_collection=True) real-HTTP-via-TestClient workflow that produced the platform's own
16/16 MVP sign-off) but:
  - points at the ISOLATED Gaza pilot config (config/settings.gaza_pilot.yaml,
    config/analysts.gaza_pilot.yaml) instead of the production Turkish study's config --
    config/settings.yaml and config/analysts.yaml are untouched by this script and by this
    entire pilot.
  - collects from exactly ONE channel (BBC News, the only active entry in
    config/analysts.gaza_pilot.yaml), capped at 2 videos / 50 comments-per-video by that same
    config file -- deliberately smaller than the Pilot Collection Plan's own figures, to keep
    this first real run as small as technically meaningful.
  - runs analysis with the newly pinned English sentiment model (cardiffnlp/
    twitter-roberta-base-sentiment-latest) instead of the Turkish model.
  - prints extra, human-readable samples (cleaned text, sentiment labels, topic labels) so the
    operator can do the manual inspection checklist from
    docs/research/GAZA_PILOT_PHASE2_INFRASTRUCTURE.md sec.7 directly from this run's output,
    not as a separate step.

Requires YT_API_KEY / ANON_SALT set in the environment -- same convention as
t029_live_verification.py and scripts/t015_live_smoke_test.py. Run this from the repository
root, with the new, dedicated Gaza-pilot Google Cloud project's API key (see
docs/research/GAZA_PILOT_PHASE2_INFRASTRUCTURE.md sec.2/3) -- NOT the Turkish study's key, so
the two studies' quota usage stays visibly separate in the Google Cloud Console.

    poetry run python gaza_pilot_smoke_test.py

Not a pytest test (same reasoning as t029_live_verification.py: real API quota, real
compute-heavy ML inference, must never run automatically in CI). Every step prints PASS/FAIL
with evidence. Exits nonzero on any unexpected failure.
"""
from __future__ import annotations

import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, "src")

from fastapi.testclient import TestClient

from finfluencer.bootstrap import (
    SENTIMENT_ANALYSIS_TYPE_ID,
    TOPIC_MODELING_ANALYSIS_TYPE_ID,
    create_app,
)
from finfluencer.utils.io import read_parquet

_REPO_ROOT = Path(__file__).resolve().parent
_GAZA_SETTINGS = _REPO_ROOT / "config" / "settings.gaza_pilot.yaml"
_GAZA_ANALYSTS = _REPO_ROOT / "config" / "analysts.gaza_pilot.yaml"

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, evidence: str) -> None:
    RESULTS.append((name, condition, evidence))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}\n       evidence: {evidence}")


def main() -> int:
    if not _GAZA_SETTINGS.exists() or not _GAZA_ANALYSTS.exists():
        print(f"FATAL: expected config files not found:\n  {_GAZA_SETTINGS}\n  {_GAZA_ANALYSTS}")
        return 2

    base_root = Path(tempfile.mkdtemp(prefix="gaza-pilot-smoke-"))
    print(f"base_root: {base_root}")
    print(f"settings:  {_GAZA_SETTINGS}")
    print(f"analysts:  {_GAZA_ANALYSTS}")
    app = create_app(
        settings_path=_GAZA_SETTINGS,
        analysts_path=_GAZA_ANALYSTS,
        collection_base_root=base_root,
        use_live_collection=True,
    )
    client = TestClient(app)

    # ---- 1. Project creation ----
    tenant_id = str(uuid.uuid4())
    r = client.post(
        "/projects",
        json={
            "tenant_id": tenant_id,
            "name": "Gaza Pilot Smoke Test",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    check("1. POST /projects returns 200/201", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:300]}")
    project_id = r.json()["id"]

    # ---- 2. Real, live Collection Run (BBC News only, capped small by config) ----
    dataset_id = str(uuid.uuid4())
    print("Starting live collection run against BBC News -- real network call, quota spend...")
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

    comments_path = base_root / collection_run_id / "data_raw" / "comments.parquet"
    if comments_path.exists():
        comments_df = read_parquet(comments_path)
        check("2d. Real comments collected (nonzero rows)", len(comments_df) > 0, f"row_count={len(comments_df)}")
        if len(comments_df) > 0 and "text_clean" in comments_df.columns:
            print("\n--- Manual inspection: sample cleaned English comment text ---")
            for txt in comments_df["text_clean"].head(5).tolist():
                print(f"  - {txt!r}")
            print("--- end sample ---\n")
    else:
        check("2d. Real comments collected (nonzero rows)", False, f"comments.parquet not found at {comments_path}")

    # ---- 3. Real Analysis Run: topics (BERTopic, English embedding model, reduced HDBSCAN params) ----
    print("Starting real topic-modeling AnalysisRun (BERTopic)...")
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
    check(
        "3c. Real topics AnalysisRun produced nonzero topic_count (not degenerate)",
        topics_run.get("topic_count", 0) > 0,
        f"body={topics_run} -- if this is 0 or 1, the HDBSCAN params in "
        f"settings.gaza_pilot.yaml may still be too coarse for this sample size",
    )

    # ---- 4. Real Analysis Run: sentiment (cardiffnlp English model) ----
    print("Starting real sentiment AnalysisRun (cardiffnlp/twitter-roberta-base-sentiment-latest)...")
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

    # ---- 7. CSV / table export -- check real content AND the new provenance columns ----
    r = client.get(f"/projects/{project_id}/reports/{report_id}/table")
    if r.status_code == 200:
        table_evidence = f"{len(r.content)} bytes CSV, X-Row-Count={r.headers.get('X-Row-Count')}"
    else:
        table_evidence = f"status={r.status_code} body={r.text[:400]}"
    check("7a. GET .../table succeeds (200)", r.status_code == 200, table_evidence)

    if r.status_code == 200:
        import csv
        import io

        rows = list(csv.DictReader(io.StringIO(r.content.decode("utf-8"))))
        header = rows[0].keys() if rows else []
        expected_provenance_cols = {
            "sentiment_analysis_run_id", "sentiment_model_name", "sentiment_model_revision",
            "topics_analysis_run_id", "topics_model_name", "topics_model_revision",
        }
        check(
            "7b. Provenance columns present on export",
            expected_provenance_cols.issubset(set(header)),
            f"missing={expected_provenance_cols - set(header)} present_header={list(header)}",
        )
        if rows:
            check(
                "7c. sentiment_model_name reflects the NEW English model, not the Turkish one",
                rows[0].get("sentiment_model_name") == "cardiffnlp/twitter-roberta-base-sentiment-latest",
                f"sentiment_model_name={rows[0].get('sentiment_model_name')!r}",
            )
            print("\n--- Manual inspection: sample sentiment_class / topic_label assignments ---")
            for row in rows[:5]:
                print(
                    f"  text={row.get('text_clean', '')[:80]!r} "
                    f"sentiment={row.get('sentiment_class')} "
                    f"topic_pooled={row.get('topic_label_pooled')}"
                )
            print("--- end sample ---\n")

    # ---- 8. PDF export ----
    r = client.post(f"/projects/{project_id}/reports/{report_id}/exports", json={"format": "pdf"})
    check("8a. PDF export returns 200", r.status_code == 200, f"status={r.status_code}")
    check("8b. Real PDF bytes (starts with %PDF)", r.content[:4] == b"%PDF", f"first_bytes={r.content[:8]!r} len={len(r.content)}")

    # ---- Summary ----
    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = total - passed
    print("\n" + "=" * 70)
    print(f"GAZA PILOT SMOKE TEST: {passed}/{total} checks passed, {failed} failed")
    if failed:
        print("FAILURES:")
        for name, ok, ev in RESULTS:
            if not ok:
                print(f"  - {name}\n    {ev}")
    print("=" * 70)
    print(f"\nAll artifacts on disk under: {base_root}")
    print(
        "\nNext: check the new project's real quota usage in the Google Cloud Console "
        "(APIs & Services -> Dashboard) against the ~25-unit smoke-test estimate before "
        "deciding whether to proceed to the fuller Phase 3 Pilot Collection Plan."
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
