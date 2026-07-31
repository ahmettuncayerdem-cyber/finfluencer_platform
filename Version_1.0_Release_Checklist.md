# Version 1.0 Release Checklist

**Role:** Release Manager, Finfluencer Research Platform
**Purpose:** Execute after `Production_Validation_Checklist.md` has passed. Produces the `v1.0.0` release.
**Type:** Release process only. No source code changes are performed by this checklist itself — every gate below either passes on current repository state or names the exact, already-identified prerequisite (from `Release_Readiness_Report.md`, already accepted) that must close first. This document does not re-open, re-scope, or soften any of that report's findings.

---

## Gate A — Production validation

| Check | Status |
|---|---|
| `Production_Validation_Checklist.md` §5 sign-off completed with overall result = **PASS** | Required before proceeding past this gate |

Do not proceed to Gate B until Gate A is signed off PASS with evidence archived.

---

## Gate B — Release Readiness Report prerequisites

**This is the honest state of the repository as of this checklist's own preparation, freshly re-verified — not carried forward unverified from the earlier report.** Both `Release_Readiness_Report.md`'s Critical items and its High items are release-blocking by that report's own accepted conclusion ("READY AFTER COMPLETING THE FOLLOWING ITEMS"). Nothing in this session's subsequent work (the Run Manifest System, the Production Execution Guide, the Production Validation Checklist) has touched any of them — re-verification below confirms they are unchanged.

| # | Item | Severity | Status (re-verified) |
|---|---|---|---|
| 1 | `.env` git exposure remediated | Critical | **Still open** — `.env` remains tracked (`git ls-files .env` still returns it); no `.gitignore` exists |
| 2 | `topic_evolution.parquet` regenerated | Critical | **Resolved by Gate A**, if and only if Gate A shows PASS |
| 3 | Test coverage gate (75%) | High | **Still failing** — re-run this session: `68.74%` actual, gate configured at `75.0%`, `pytest` exits non-zero |
| 4 | CLI entry point (`finfluencer.cli:app`) | High | **Still broken** — `src/finfluencer/cli.py` still does not exist |
| 5 | `poetry.lock` committed | High | **Still missing** |
| 6 | CI pipeline | High | **Still absent** — no `.github/workflows/` |
| 7 | ADR-0001 roadmap patch / stale Step 3.3–3.4 status | Medium | **Still open** |
| 8 | `.gitignore` present | Medium | **Still absent** |
| 9 | Package installable as `finfluencer-platform` | Medium | **Still not installable** in a clean environment (verified `pip show` returns not-found) |
| 10 | `export_master_table.py`/`final_health_report.py` `scope_id` migration | Medium | **Still open**, still latent/non-urgent |

**Gate B status: NOT CLEARED.** One Critical item (#1) and three High items (#3, #4, #5, #6) remain open, independent of and unaffected by Gate A. A `v1.0.0` tag created before these close would assert a level of readiness this repository does not currently have, by its own already-accepted standard.

**What this means operationally:** the sections below (git status verification through repository freeze) are written to be fully executable and correct *once Gate B is cleared*. If you are running this checklist before that point, §1 (git status verification) will legitimately show the same failures documented above — that is this checklist working correctly, not a bug in the checklist. Do not skip §1's checks or treat a dirty/blocked result as something to work around.

---

## 1. Git status verification

| # | Check | Command | PASS criteria | Current real result |
|---|---|---|---|---|
| 1.1 | Working tree clean | `git status --porcelain` | Empty output | **FAIL** — 222 changed/untracked paths (185 untracked) |
| 1.2 | No secrets tracked | `git ls-files .env` | Empty output | **FAIL** — `.env` is tracked |
| 1.3 | On the intended release branch/commit | `git log -1 --oneline` | Matches the exact commit the production run in Gate A was executed against | Currently `e3121e4 Baseline after preprocess pipeline completed` — confirm this is still HEAD after Gate A's execution, since Gate A's run may itself have produced new local changes (e.g. `data/processed/topic_evolution.parquet`, a new `checkpoints/run_manifests/*.json`) that need to be committed before tagging |
| 1.4 | Existing tag history sane | `git tag -l` | No conflicting `v1.0.0` already present | Currently only `v0.1.0-phase1` exists — no conflict |
| 1.5 | All Gate A outputs committed | `git status --porcelain` after `git add` of the regenerated `topic_evolution.parquet`, new `run_manifests/*.json`, and any evidence files intended to ship in the repo | Empty output | Cannot be evaluated until Gate A has actually run |

**1.1 and 1.2 must both show PASS before proceeding to §2.** They currently do not (see Gate B). Resolving them is exactly Gate B items 1 and 8 (`.env` remediation, `.gitignore`) — do not resolve them ad hoc inside this checklist; that is engineering work explicitly out of this document's scope.

---

## 2. Version tag creation (v1.0.0)

Run only once §1 is fully clean.

```bash
# Confirm the exact commit being tagged
git log -1 --oneline

# Annotated tag, matching the existing v0.1.0-phase1 naming convention
git tag -a v1.0.0 -m "v1.0.0 — Entity-Centric Migration v2 complete; scope_id-based analysis layer;
Run Manifest System; topic_evolution.parquet regenerated and validated.
See Entity_Centric_Migration_v2_Closeout_Report.md, ADR-0001, Software_Product_Architecture_v1.0.md,
Release_Readiness_Report.md, and Production_Validation_Checklist.md sign-off for full provenance."

# Verify
git tag -n99 v1.0.0

# Push, once the remote and branch protection policy for this repository are confirmed separately
# (this checklist does not assume a specific remote/hosting setup)
git push origin v1.0.0
```

**PASS criteria:** `git tag -n99 v1.0.0` shows the annotated message above attached to the correct commit; `git log -1 --oneline` matches the commit that produced Gate A's evidence.

---

## 3. Release notes

Draft, ready to file as `CHANGELOG.md` or a GitHub/GitLab release description. Fill in the bracketed fields from Gate A's sign-off.

```markdown
# v1.0.0 — [release date]

First production release of the Finfluencer Research Platform following the closed
Entity-Centric Migration v2 and the accepted Software Product Architecture v1.0.

## Included

- Entity-centric data model (Phase 0) and AnalysisScope-based analysis layer
  (Migration v2 Steps 3.1–3.4): `run_topics()`, `analysis/topic_sentiment.py`, and
  `run_topic_evolution()` now share one persisted, non-re-derived comment-scope
  fingerprint (`scope_id`) — the fix for the fingerprint-mismatch bug that motivated
  this migration. See `Entity_Centric_Migration_v2_Closeout_Report.md`.
- `TopicEvolutionRecord.scope_id` remains intentionally unpopulated — see `ADR-0001`
  (zero runtime consumers; deferred, not a defect).
- Run Manifest System (Architecture v1.0 §10): every `run_pipeline()` invocation now
  writes a lifecycle-tracked manifest (`RUNNING` → `SUCCESS`/`FAILED`) under
  `checkpoints/run_manifests/`, including per-stage checkpoint hashes, environment,
  and git state.
- `data/processed/topic_evolution.parquet` regenerated and validated in a real
  BERTopic-enabled environment — run ID: [run_id from Gate A], [row count] rows,
  [date/time].

## Known limitations at this release

- [If Gate B items were resolved before tagging, list them as closed here.]
- [If any Gate B item was explicitly accepted as open at release time — which this
  checklist does not recommend — name it here with the accepted risk, not silently.]
- `ProgressReporter` protocol, `finfluencer.api` façade, Study/Project Management
  System, REST API, GUI, and multi-platform support are designed
  (`Software_Product_Architecture_v1.0.md`) and explicitly out of scope for v1.0.

## Evidence

Full validation evidence archived at: [path from Production_Validation_Checklist §3]
```

---

## 4. Artifact archive

Bundle the following into a single dated archive (e.g. `release_artifacts/v1.0.0.tar.gz` or equivalent), separate from the git tag itself:

1. All six evidence items from `Production_Validation_Checklist.md` §3 (run manifest, regenerated `topic_evolution.parquet`, checkpoint diffs, `pub_data.json`, health report output, pytest output).
2. The five governing documents as tagged: `Entity_Centric_Migration_v2_Closeout_Report.md`, `ADR-0001_TopicEvolutionRecord_ScopeId_Deferral.md`, `Software_Product_Architecture_v1.0.md`, `Release_Readiness_Report.md`, `Topic_Evolution_Production_Execution_Guide.md`.
3. Full environment snapshot from the production machine: `poetry.lock` (once committed per Gate B item 5), `pip freeze` or equivalent, Python version, OS/platform string.
4. The exact `config/settings.yaml`/`config/analysts.yaml` used for the tagged release (content-hash them; the run manifest already contains `settings_file_sha256`/`analysts_file_sha256` — cross-reference rather than re-deriving).
5. `git log -1 --format=%H` for the tagged commit, stored alongside the archive so the archive is independently traceable back to the exact code state even if the tag is later moved or deleted.

**Do not** include raw `data/raw/comments.parquet` or any identifiable-tier data in this archive without separately confirming that doing so is consistent with `config/settings.yaml`'s `ethics:`/`replication:` policy for this study — that determination is out of this checklist's scope and should not be assumed.

---

## 5. Replication package status

**Not built, and this release does not claim otherwise.** `config/settings.yaml`'s `replication:` block (staged model, Zenodo target, tiered restricted-access packaging) is fully *designed* — confirmed present and unchanged — but the "assemble replication package" service itself (Architecture v1.0 §13) has not been implemented. `replication.stage` is currently `"exploratory"`.

For v1.0, treat the artifact archive in §4 as a **manual, partial substitute** for the automated replication package, not the thing itself. If a real replication package (Zenodo deposit, DOI-minted, tiered access) is required for this release, that is a separate piece of work this checklist does not perform and this release should not be represented as including.

---

## 6. Repository freeze recommendations

"Freeze" here means: the tagged `v1.0.0` commit is the fixed reference point for anything claiming to be "the v1.0 platform," not that no further commits are ever made to the repository.

1. **Branch protection on the commit history leading to `v1.0.0`**, if the hosting platform supports it — prevent force-push/history rewrite on the tagged commit and its ancestors.
2. **Any further change is a new version, not a silent edit to v1.0.0.** Per the additive/backward-compatible discipline already used throughout this project (Migration v2, the Run Manifest System), a post-release fix is `v1.0.1`, a new feature is `v1.1.0` — never a re-tag of `v1.0.0` itself.
3. **The five governing documents (§4 item 2) are frozen alongside the code.** If any of them needs a substantive update after this point (e.g., finally applying the ADR-0001 roadmap patch — Gate B item 7), that update ships as part of a subsequent version's documentation, referencing what changed and why, not as a silent edit to the v1.0.0-era files.
4. **`Software_Product_Architecture_v1.0.md`'s own roadmap (§22) remains the reference for what comes next** (`ProgressReporter`, `finfluencer.api`, then the Study system, gated behind a second real study). This release checklist does not add to, reorder, or reopen that roadmap.
5. **Gate B's still-open items do not disappear at tag time** — whichever of them remain open when `v1.0.0` is actually tagged should be carried forward explicitly as the first entries of the next version's work, not treated as resolved by the act of releasing.

---

## Final status

Given the current, freshly re-verified state of Gate B, this checklist's sections 1–6 are **ready to execute exactly as written, the moment Gate B's Critical and High items are closed** — nothing here needs further clarification or design work to run. They are **not** ready to execute against the repository's current state today: §1.1 and §1.2 would fail immediately, and tagging `v1.0.0` against a tree with a tracked secrets file and a failing coverage gate would misrepresent this release relative to the standard `Release_Readiness_Report.md` already set for it.
