# Researcher Quickstart

**Audience:** a researcher who wants to run a study on this platform — not a developer working
on the platform's own code. If you're looking for engineering/governance history instead, start
at `docs/implementation/PROGRAM_DIRECTOR_REPORT.md`.

**Status:** written 2026-08-07, as part of the Version 1.0 Research Readiness freeze
(`docs/implementation/V1.0_RESEARCH_READINESS_AUDIT.md`), directly from the exact, real HTTP
calls `t029_live_verification.py` (repo root) used for the platform's own live MVP sign-off
(`docs/implementation/BACKLOG.md` T-029, 16/16 checks passed against real YouTube data). Every
request/response shape below is copied from that proven, working script — not guessed.

---

## 1. What this platform does

Given a roster of YouTube channels, it collects comments, runs topic modeling (BERTopic) and
sentiment analysis (a local transformer classifier — no generative-AI/LLM call anywhere in this
path), and produces a citable Report you can export as a CSV table or a PDF. The original,
currently-configured study is Turkish financial-YouTube-influencer discourse — see §5 for how to
point it at a different topic and channel roster instead.

## 2. Install

```bash
git clone <this repository>
cd finfluencer_platform
poetry install
```

Requires Python (see `pyproject.toml`'s `python` constraint — currently narrowed to satisfy a
temporary Windows `torch` pin; see `KNOWN_ISSUES.md` if `poetry install` fails on that step).

## 3. Set credentials

Two environment variables are required. **Never commit real values — set them as environment
variables, not in any file that gets checked into git.**

```bash
export YT_API_KEY="<your real YouTube Data API v3 key>"
export ANON_SALT="<any sufficiently long random string, kept consistent for one study>"
```

`YT_API_KEY`: a real key from Google Cloud Console (YouTube Data API v3 enabled). `ANON_SALT`:
used to anonymize commenter/channel identifiers consistently within a study — not a secret that
needs to be memorable, just non-empty and not one of the placeholder values `core/config.py`
rejects once `replication.stage` is `submission` or `publication` (the platform's current
default — see `config/settings.yaml`'s own comments).

## 4. Run a study end to end

**There is currently no long-running server entry point wired for live (real-network) mode** —
`create_app()`'s `use_live_collection` flag (`src/finfluencer/bootstrap.py`) is opt-in and only
ever exercised via Python's `TestClient`, which wraps the real FastAPI app in-process and issues
real HTTP-shaped requests against it synchronously. This is not a limitation of your study — it
is exactly how the platform's own MVP sign-off was performed and verified, and is fully
functional; it just means you drive the workflow from a small Python script rather than `curl`
against a listening port today. (A real `uvicorn`-served live-mode entry point would be a
reasonable small addition for whoever picks up the next engineering pass — flagged here, not
built by this documentation-only freeze.)

The fastest way to get a real study running is to copy `t029_live_verification.py` and adapt it.
Its own workflow, in order (every path and payload below is exactly what that script sends):

```python
from fastapi.testclient import TestClient
from finfluencer.bootstrap import (
    SENTIMENT_ANALYSIS_TYPE_ID, TOPIC_MODELING_ANALYSIS_TYPE_ID, create_app,
)
import tempfile, uuid
from pathlib import Path

base_root = Path(tempfile.mkdtemp(prefix="my-study-"))
app = create_app(collection_base_root=base_root, use_live_collection=True)
client = TestClient(app)

# 1. Create a Project
r = client.post("/projects", json={
    "tenant_id": str(uuid.uuid4()), "name": "My Study", "idempotency_key": str(uuid.uuid4()),
})
project_id = r.json()["id"]

# 2. Real, live Collection Run -- spends real YouTube API quota, collects your
#    config/analysts.yaml roster (see section 5 to point this at different channels)
dataset_id = str(uuid.uuid4())
r = client.post(f"/datasets/{dataset_id}/collection-runs", json={
    "dataset_id": dataset_id, "idempotency_key": str(uuid.uuid4()),
})
collection_run_id = r.json()["id"]

# 3. Real topic-modeling AnalysisRun (BERTopic)
r = client.post(f"/collection-runs/{collection_run_id}/analysis-runs", json={
    "project_id": project_id, "collection_run_id": collection_run_id,
    "analysis_type_id": str(TOPIC_MODELING_ANALYSIS_TYPE_ID),
    "analysis_type_version": "1.0.0", "idempotency_key": str(uuid.uuid4()),
})
topics_run_id = r.json()["id"]

# 4. Real sentiment AnalysisRun (transformer classifier)
r = client.post(f"/collection-runs/{collection_run_id}/analysis-runs", json={
    "project_id": project_id, "collection_run_id": collection_run_id,
    "analysis_type_id": str(SENTIMENT_ANALYSIS_TYPE_ID),
    "analysis_type_version": "1.0.0", "idempotency_key": str(uuid.uuid4()),
})
sentiment_run_id = r.json()["id"]

# 5. Report: cite both AnalysisRuns
r = client.post(f"/projects/{project_id}/reports", json={"analysis_run_id": topics_run_id})
report_id = r.json()["id"]
client.post(f"/projects/{project_id}/reports", json={
    "analysis_run_id": sentiment_run_id, "existing_report_id": report_id,
})

# 6. Finalize -- required before export
client.post(f"/projects/{project_id}/reports/{report_id}/finalize")

# 7. CSV/table export (see docs/research/OUTPUT_CODEBOOK.md for column meanings)
r = client.get(f"/projects/{project_id}/reports/{report_id}/table")
Path("my_study_table.csv").write_bytes(r.content)

# 8. PDF export (a bounded preview of each citation, not a second full data copy --
#    the CSV/table above is always the complete dataset)
r = client.post(f"/projects/{project_id}/reports/{report_id}/exports", json={"format": "pdf"})
Path("my_study_report.pdf").write_bytes(r.content)

print("Artifacts also on disk under:", base_root)
```

Expect step 2 (collection) to take real wall-clock time proportional to your roster's comment
volume, and steps 3-4 (BERTopic, transformer inference) to be genuinely compute-heavy on CPU —
this is normal, not a hang (see `docs/implementation/PROGRAM_DIRECTOR_REPORT.md`'s own deltas for
what real per-analyst timing has looked like in practice).

**Copy your artifacts out immediately.** `base_root` is a temp directory; there is no
Persistence Layer yet (a known, deliberately deferred Sprint 5 item —
`docs/implementation/RELEASE_BLOCKING_ASSESSMENT.md` item 8). Nothing here will survive a reboot
or the OS reclaiming temp space on its own schedule. Copy `my_study_table.csv`,
`my_study_report.pdf`, and everything under `base_root` (raw comments, intermediate parquet
files, `provenance.json`) to permanent storage after every run, not just at the end of a study.

## 5. Running your own study (different topic, different channels)

`config/analysts.yaml` defines the channel roster and is extensively self-commented — open it
directly; each field (`handle`/`channel_id`/`pilot`/`expertise_class`) is explained inline. Point
it at a different set of channels and re-run the workflow in §4 unchanged.

**Language/model compatibility — check before you collect, not after.** The currently-configured
sentiment classifier (`config/settings.yaml`'s `sentiment.primary_model`) is a Turkish-language
model. If your channels' comments are not in Turkish, sentiment output will not be valid without
swapping in a different model first — this is a config change (`sentiment.primary_model.name`/
`.revision`, pinned to a real HuggingFace commit SHA, not a placeholder — see
`core/config.py`'s `is_placeholder_revision` check), not a code change. Topic modeling's
embedding model (`topics.embedding_model`) is already multilingual
(`paraphrase-multilingual-MiniLM-L12-v2`) and does not have this constraint.

**Construct validity is a separate question from technical compatibility.** A sentiment model
tuned on one discourse domain (e.g., financial-influencer commentary) is not automatically valid
on a different one (e.g., political or crisis discourse) even if it runs without error. Before
treating any sentiment number as reportable in a new domain, validate it against a human-coded
gold sample and report inter-rater reliability — this repository's own `research_archive/`
(git-ignored, not shipped) shows this was done once already for the original study; repeat the
same discipline for a new one.

## 6. Interpreting your output

See `docs/research/OUTPUT_CODEBOOK.md` for a full column-by-column and concept-by-concept
reference (`master_table.csv`'s columns, what a "citation" and a "snapshot" are, what
`replication.stage` means for your Methods section).
