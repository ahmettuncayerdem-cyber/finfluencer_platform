# Implementation Backlog — Sprint 0 to MVP

**Status:** Operational execution artifact. Not governance, not constitutional — classified as **Temporary Practice** under `IMPLEMENTATION_PLAYBOOK.md` Part K: task status changes without ceremony, by editing this file or the equivalent tracker, no PR review required for status changes alone.
**Scope:** every task below drives toward `IMPLEMENTATION_ROADMAP.md` §6's MVP definition. Nothing here reinterprets architecture, roadmap sequencing, or playbook process — every task cites what it's grounded in instead of restating it.
**How to read this:** each task states what a developer (human or AI) can start on immediately once its dependencies are marked done. If a task isn't independently startable, it's still too abstract — none below should be.

---

## Critical Path

`T-001 → T-002 → T-006 → T-007 → T-008 → T-009 → T-011 → T-013 → T-014 → [T-018→T-019→T-020→T-021] → [T-022→T-023 ✅] → [T-024→T-025→(T-026 ‖ T-027)→T-028 ✅] → T-029 → T-030 → T-031 → T-032`

**EPIC-03 (T-015–T-017, live collection) runs in parallel with EPIC-04/05's build phase**, not before it — it only needs to rejoin at T-029, since MVP requires real collected data but nothing in EPIC-04/05/06's code depends on collection being *live* rather than fixture-sourced. This is the one non-obvious parallelization opportunity in the whole backlog; see Internal Review.

---

## Engineering Workstreams

*A descriptive lens over the EPICs above, not a new backlog namespace, task-id scheme, or
governance artifact — every task keeps its existing `T-0XX` id and epic unchanged. Added
2026-08-03 per operator instruction, following the Project Evolution Strategy Review. One
repository, one roadmap, one governance model, exactly as decided.*

- **Shared Core** — the framework-agnostic analysis pipeline this platform wraps: `collect/`,
  `providers/platform/`, `preprocess/`, `embeddings/`, `topics/`, `sentiment/`,
  `reporting/master_table.py`, and `reporting/`'s statistical/manuscript modules.
- **Research Applications** — the academic research/publication track already present in this
  repository (statistical validation, gold-standard annotation, manuscript preparation, peer
  review response) — currently un-ticketed beyond T-033's own triage item. Consumes Shared Core
  directly, never the six-layer architecture.
- **Product Applications** — the six-layer SaaS platform, EPIC-00 onward, everything on the
  critical path above. Consumes Shared Core only through Infrastructure adapters, per the
  established wrapper pattern (T-010, T-019, T-022).

**Policy:** any modification to a Shared Core module listed above must include, in the same
change, both a **Research impact assessment** (does this alter any output a manuscript,
statistical validation, or annotation process currently depends on?) and a **Product impact
assessment** (does this alter any output an Infrastructure adapter, Domain entity, or API
response currently depends on?) — even when the task's own stated purpose touches only one
workstream. "No impact" is an acceptable finding of the assessment; skipping the assessment is
not.

---

## Backlog Snapshot — 2026-08-03

*Temporary Practice — regenerate this section on demand, don't hand-maintain it between real state changes.*

**Epic progress:** EPIC-00 (Unfreeze the Repository) 1/3 tasks closed, 2 blocked-on-environment, no longer gating EPIC-01 (see Dependency Ruling below). EPIC-01 (Shared Foundation) 5/5 tasks closed (T-004, T-005, T-006, T-007, T-008 implementation — T-008's cross-vendor review outstanding, see its own entry). **EPIC-02 (Walking Skeleton) 6/6 tasks closed for Sprint 0 scope — COMPLETE.** (T-009 — Persistence-backed criterion deferred; T-010, T-011, T-012, T-013 — cross-vendor review outstanding; T-014 — human-verified and closed 2026-08-01; see each entry). **EPIC-03 (Live Collection, Sprint 1): 3/3 tasks closed — COMPLETE (live-network verification halves of T-015/T-017 environment-blocked, not code gaps).** T-015 — implementation closed, live-network half of Verification environment-blocked. T-016 — closed, retry policy implemented and tested. T-017 — implementation closed, live-network half environment-blocked (same constraint, re-confirmed not rediscovered). See each entry.

**EPIC-04 (Topic Analysis, Sprint 2): 4/4 tasks CLOSED — SPRINT 2 COMPLETE.** T-018 — `AnalysisType`/`AnalysisRun` Domain entities, cross-vendor review outstanding (non-blocking). T-019 — `TopicsAnalysisAdapter`. T-020 — `StartAnalysisRunOrchestrator`, retry-creates-new-run proven. T-021 — immutability/pinning exhaustively tested, zero new production code, human-verified 2026-08-01. `SPRINT_2_KICKOFF.md` approved 2026-08-01.

**EPIC-05 (Sentiment Analysis, Sprint 3): 2/2 tasks CLOSED — SPRINT 3 COMPLETE.** T-022 — `SentimentAnalysisAdapter` wraps `sentiment.pipeline.run_sentiment` unmodified, second `IAnalysisEngine` implementation. T-023 — verified zero orchestrator diff since T-020 (`git diff`-confirmed, plus structural dispatch/signature/no-branching proof). ARB-01 — plugin architecture formally reviewed 2026-08-01, 8/10 dimensions Accept, 2/10 Generalize (non-blocking, tracked as TD-03/TD-04); no architectural changes recommended. **Sprint 3 formally CLOSED 2026-08-01.**

**EPIC-06 (Reporting / MVP Core Loop, Sprint 4): 5/5 tasks closed — SPRINT 4 COMPLETE.** `SPRINT_4_KICKOFF.md` approved 2026-08-01. T-024 — `InterpretationRecord`/`Report`/`Export` Domain entities, `Report` structurally never references `AnalysisRun` (ast-verified). T-025 — `GenerateReportOrchestrator`, real integration proof of a topic-AnalysisRun and a sentiment-AnalysisRun citing into one `Report`; `reporting/master_table.py` investigated and correctly deferred to T-026. T-026 — `ExportReportTableOrchestrator`, `reporting/master_table.py` finally reused unmodified as BACKLOG always intended; confirmed CSV/table export is not a Domain `Export` entity (§10.1 restricts `Export` to PDF/Word). T-027 — `PdfRendererAdapter` (`reportlab`, new dependency, ADR-0003) + `FinalizeReportOrchestrator`/`GenerateExportOrchestrator`; first real use of the `Export` entity (T-024, dormant until now); genuinely new implementation, no existing tested code to wrap, confirmed by re-inspection during its own Readiness Review. T-028 — first real Presentation/API exposure of Reporting (and, via `StartAnalysisRun`, Analysis) — five new routes over six completely-unmodified orchestrators (one new, `GetReportOrchestrator`, T-020/025/026/027 otherwise untouched); `StartAnalysisRun`'s first-ever API exposure required a deliberately-scoped demo `IAnalysisEngine` (ADR-0004), not the real BERTopic adapter. **Sprint 4 formally CLOSED 2026-08-03.** EPIC-07/EPIC-08 (except the housekeeping item below): not started.

**T-029 (MVP acceptance verification), 2026-08-03: implementation-side verification complete
(full audit, 31/31 E2E checks, all quality gates clean, no new gaps found — see
`T-029_MVP_VERIFICATION_REPORT.md`). Not closed — its own Role line requires human sign-off on a
live, real-YouTube-data run, blocked pending a real-network environment and resolution of
ARB-01's TD-03/TD-04 (real analysis engines behind `StartAnalysisRun`). See its own entry.**

**Sprint progress (Sprint 0 = EPIC-00 through EPIC-02): 10 of 14 Sprint-0 tasks closed — SPRINT 0 COMPLETE.** T-001, T-004, T-005, T-006, T-007, T-008 (implementation), T-009 (Sprint 0 scope), T-010 (Sprint 0 scope), T-011 (Sprint 0 scope), T-012 (Sprint 0 scope), T-013 (Sprint 0 scope), T-014 (closed, human-verified) — every task this sprint's own scope required is closed. T-002/T-003 remain open but, per the Dependency Ruling below, never gated this closure. Formal closure documents: `SPRINT_0_RETROSPECTIVE.md`, `SPRINT_0_COMPLETION_REPORT.md`, `SPRINT_1_READINESS_ASSESSMENT.md` (2026-08-01). Sprint 0 remains CLOSED and immutable.

**Sprint 1 (EPIC-03, Live Collection) is COMPLETE — T-015, T-016, T-017 all closed 2026-08-01.** T-015 — real `YouTubePlatformProvider` wired into the unmodified T-010 adapter. T-016 — bounded retry with backoff for `RateLimitError`/`NetworkError` inside `youtube.py::_execute`. T-017 — real-`SIGKILL` interruption/resume proven against the live-wired chain (network transport stubbed), plus retry-survives-the-real-chain proof. The live-network, real-timing halves of T-015's and T-017's own Verification lines remain environment-blocked in this sandbox (one constraint, confirmed twice, not two separate findings) — both have a ready-to-run manual script for an operator with real egress. Per `IMPLEMENTATION_ROADMAP.md`'s own parallelization note (Critical Path section above), EPIC-03's completion means it can now rejoin the critical path at T-029 as planned; EPIC-04 (Topic Analysis, Sprint 2) is the next unstarted epic.

**Dependency ruling, 2026-08-01 (resolved):** T-006 originally listed `T-001, T-002, T-003, T-004, T-005` as dependencies. An evidence-only review (this file, `IMPLEMENTATION_ROADMAP.md`, `IMPLEMENTATION_PLAYBOOK.md`, `PRODUCT_ARCHITECTURE.md` — no other source consulted) found no binding sentence in any of the four conditioning package-skeleton creation on Python/test-suite readiness; `IMPLEMENTATION_ROADMAP.md` §12's related statement ("confirm the existing test suite actually passes... before any porting work begins") names *porting* work (T-007, T-010), not skeleton creation. Operator reviewed this finding and ruled T-002/T-003 do not block T-006. T-006's dependency list narrowed to `T-001, T-004, T-005` and closed same-day. T-002/T-003 remain open in their own right — EPIC-00 itself is not closed by this ruling, only the specific T-006 gate.

**Completed:** T-001 (uncommitted diff resolved — commit `e7052ea`, 13 files, 1438 insertions / 37 deletions). T-004 (ADR-0001 accepted). T-005 (IG-001 wired into CI). T-006 (six-layer skeleton scaffolded). T-007 (four-entity Domain Model, architectural review passed, one Recommended finding resolved). T-008 (API Contract schema implemented and locally verified — cross-vendor review outstanding, see its own entry). T-009 (`CreateProjectOrchestrator` implemented for Sprint 0 scope — no Persistence Layer, authentication, or authorization yet, see its own entry). T-010 (`CollectionEngineAdapter` wraps `collect/`+`youtube.py`'s Protocol seam unmodified, fixture-backed, checkpoint_root partitioning resolves Risk R-1, interruption/resume proven directly — cross-vendor review outstanding, see its own entry). T-011 (`StartCollectionRunOrchestrator` — first Walking Skeleton use case, idempotent dispatch with create/resume/replay handling, drives the real T-010 adapter end to end; synchronous execution and no Dataset-aggregate load flagged as deliberate Sprint 0 simplifications — cross-vendor review outstanding, see its own entry). T-013 (interruption/checkpoint-resume proven against a real, uncatchable `SIGKILL` of a genuine subprocess — not a simulated exception — then resumed through the actual `StartCollectionRunOrchestrator`; final parquet outputs verified row-unique with no data loss; no new abstractions introduced, only a test-only subprocess worker script — cross-vendor review outstanding, see its own entry). T-012 (first implementation of the API Layer — `POST /projects`, `POST /datasets/{id}/collection-runs`, both thin routes over T-009's/T-011's unmodified orchestrators; a new top-level composition root, `bootstrap.py`, wires Sprint 0 in-memory repository stand-ins and T-010's real adapter; a single static HTML+JS dev page proves the Walking Skeleton reachable end to end over real HTTP, with React deferred to its own future task — cross-vendor review outstanding, see its own entry). T-014 (Sprint 0's actual exit gate — the operator ran the Release Verification Checklist personally against a real `uvicorn` process and approved every item; **closed, human-verified**).

**F-001 — Resolved 2026-08-01 via Foundation Freeze, not a numbered task.** No constitutional or implementation-planning document had ever been committed to version control (finding first surfaced during T-001's execution). Resolved by committing all nine planning/governance files across 8 commits — `a9d3b83` (Playbook, incl. Part L Collaboration Protocol, committed separately per operator instruction), `a956bc3` (governance drafts GBD-001/GEP-001), `63f94d4` (`PRODUCT_ARCHITECTURE.md`), `5718be1` (`IMPLEMENTATION_ROADMAP.md`), `ac3761f` (Baseline Report), `6fc25b5` (this file, `BACKLOG.md`), `4277abd` (ADR-0001), `9d4904c` (prompts + Context Pack template) — then tagging the result `platform-foundation-v1` (annotated, local only, no remote configured). Verified via `git show --stat` per commit (exact file lists, no scope leakage into the T-033 pile), `git status --short` (clean tracked tree), `git fsck --full` (no corruption). Repository-hygiene concern, deliberately kept outside the numbered task sequence per the Foundation Freeze classification review — see conversation history for the full Backlog-Task-vs-Milestone analysis.

**F-002 — Open, non-blocking, awaiting operator decision.** `IMPLEMENTATION_ROADMAP.md` line 28 names a `GetCollectionRunStatus` query in connection with §11.2, but no such query exists in the approved Collection Service contract — the actual, binding name is `GetCollectionRun` (`PRODUCT_ARCHITECTURE.md` §11.2 line 684). Found 2026-08-01 during T-008's naming-reconciliation pass (which corrected the identical error in this file, `BACKLOG.md`, per operator instruction). `IMPLEMENTATION_ROADMAP.md` is a frozen constitutional document — not edited under this pass's authority. Severity: cosmetic/documentation only, does not block T-009 or any other task. Backlog-Required: no, pending operator decision on whether/when to correct the Roadmap.

**In progress / drafted, awaiting sign-off:** none.

**Blocked (environment, not decision):** T-002, T-003 — both re-attempted 2026-08-01, root cause precise: no Python >=3.11 interpreter obtainable in this sandbox (network-restricted from downloading one; `poetry`, 2.4.1, is installed and confirms the same constraint directly via `poetry lock`). No longer gate T-006 (see Dependency Ruling above), but remain open in their own right.

**Not started:** T-025 through T-032. `SPRINT_4_KICKOFF.md` and T-024's own Readiness Review approved 2026-08-01; T-024 authorized and closed same day. T-025 (`GenerateReport` command) is next-in-sequence, awaiting its own Task Authorization.

**Newly opened, non-blocking:** T-033 (triage ~90 untracked files found during T-001's `git status`; does not sit on the critical path).

**Critical path, restated with current position:** `[T-001 ✅] → T-002 ⏸ (env-blocked, no longer gates T-006) → [T-006 ✅] → [T-007 ✅] → [T-008 ✅ impl., review outstanding] → [T-009 ✅ Sprint 0 scope] → [T-010 ✅ Sprint 0 scope, review outstanding] → [T-011 ✅ Sprint 0 scope, review outstanding] → [T-013 ✅ Sprint 0 scope, review outstanding] → [T-012 ✅ Sprint 0 scope, review outstanding] → T-014 (no outstanding dependency) → …` — T-004 ✅, T-005 ✅, T-006 ✅, T-007 ✅ closed. T-008/T-009/T-010/T-011/T-013 implemented 2026-08-01 (details in their own entries). T-012 implemented 2026-08-01: the API Layer's first implementation (`POST /projects`, `POST /datasets/{id}/collection-runs`), a new composition root (`src/finfluencer/bootstrap.py`, deliberately outside the six layers — see its own entry's Scope Decision 3) wiring Sprint 0 in-memory repository stand-ins and T-010's real `CollectionEngineAdapter`, and a single static HTML+JS developer page (`web/index.html`) proving Project-creation and Collection-Run-starting are reachable over real HTTP end to end — the Walking Skeleton's first "a person, not just a test, can open this" moment. React adoption (ADR-0001) deliberately deferred to its own future task; `api.middleware.idempotency` deliberately not implemented (flagged). Found and fixed one unrelated environment/declaration mismatch (`httpx` 0.28.1 installed vs. `pyproject.toml`'s own `^0.27` constraint; downgraded to comply). 617 tests total this session, all passing (14 new under `tests/unit/test_api/`); Walking Skeleton regression subset 126 passing; IG-001 clean. Cross-vendor review outstanding, same as T-008 through T-011/T-013's own gates. EPIC-01 (Shared Foundation) is now 5/5 implemented; EPIC-02 (Walking Skeleton) is now **6/6 closed for Sprint 0 scope — COMPLETE.** T-014 was evaluated immediately after T-012 (no additional architecture required; the app was verified to run as a real `uvicorn` process and answer real HTTP requests), then closed once the operator personally ran the Release Verification Checklist and approved every item. **Sprint 0 is formally closed** — see `SPRINT_0_RETROSPECTIVE.md`, `SPRINT_0_COMPLETION_REPORT.md`, and `SPRINT_1_READINESS_ASSESSMENT.md` for the full closure documentation. Sprint 1 (T-015 onward) has explicitly **not** begun and will not begin without the operator's own approval.

**Parallel-work opportunities available right now:** T-002 and T-003 remain immediately startable the moment either runs in a real environment or gets a CI runner — no longer coupled to T-006's progress. T-033 can run fully in parallel with everything else, any time.

*Resolves the three blocking findings from `IMPLEMENTATION_BASELINE_REPORT.md` §11. Nothing below can start until this epic closes.*

### T-001 — Resolve uncommitted working-tree diff — **CLOSED 2026-08-01**
**Purpose:** clear the operator-decision blocker on six core files (1107 uncommitted lines) before any new code lands on top of them.
**Depends on:** none.
**Priority:** P0. **Effort:** XS (decision + commit/revert, <1 day).
**Role:** Human only — Baseline Report §8 explicitly declines to make this call for you.
**Acceptance criteria:** `git status` shows a clean working tree; the decision (kept or reverted) is recorded in a commit message or `docs/adr/`.
**Verification:** `git status --short` returns empty.
**Architecture:** n/a. **Roadmap:** §7 Risk Register (context). **Playbook:** Part E, Change Management.

**Outcome:** committed as `e7052ea` on `phase2-development`, "fix(collect,core): resolve R1/R2/R8 remediation items (ADR-P2-002, ADR-P2-003, ADR-P2-004)". `git status --short` on all previously-tracked files is clean (verification criterion met exactly as written).

**Correction to scope, found during execution, not before:** the original 1107-line/six-file figure was incomplete. `git status` (not `git diff`, which only sees tracked files) showed two untracked test files — `tests/unit/test_collect/test_comments.py` and `tests/unit/test_core/test_logging.py` — dated the same window (2026-07-30) and whose own docstrings cite the same ADR-P2-002/ADR-P2-003 remediation as the six tracked files. `git diff --stat` never surfaces new untracked files, so the earlier diff read missed them. They were included in the same commit rather than left stranded, since they're the same logical change, not scope creep. Actual commit: **13 files, 1438 insertions(+), 37 deletions(-)**.

**New finding, not previously surfaced — flagged, not acted on:** the same `git status` also revealed roughly 90 unrelated untracked files at the repo root and under `docs/` — statistical-validation exports, gold-standard annotation datasets, `run_R4.py`–`run_R7.py`, several `pytest_output*.txt` captures, and Turkish-language "Hakem Raporu" (referee report) documents, oldest dated mid-July. These appear to belong to a separate research/publication track sharing this repository, entirely undocumented in `PRODUCT_ARCHITECTURE.md`/`IMPLEMENTATION_ROADMAP.md`/this backlog. Not touched by this commit. See T-033.

**Environment note:** this sandbox's mount of the repository cannot `unlink()` files (git's own lock/temp-object cleanup fails with `Operation not permitted`; confirmed not project-specific — `rm` and `mv`-as-delete both fail the same way on any file). `mv`-to-rename worked as a manual workaround for stale `index.lock`/`HEAD.lock` files each time git left one behind; `git fsck --full` after the commit shows only harmless dangling objects, no corruption. Future git writes in this same sandbox session will likely need the same manual lock-clearing step.

### T-002 — Verify test suite in a real environment — **BLOCKED (environment), re-attempted 2026-08-01**
**Purpose:** replace the stale 2026-07-30 historical pass rate with a current, trustworthy result.
**Depends on:** T-001 ✅ closed.
**Priority:** P0. **Effort:** S (environment setup + one full run, ~1 day).
**Role:** Human or Claude Code, in a real environment (not this sandbox).
**Acceptance criteria:** a fresh, dated pytest run completes; pass/fail counts and coverage recorded.
**Verification:** captured pytest output file, timestamped after T-001's commit.
**Architecture:** n/a. **Roadmap:** §7 Risk R-3. **Playbook:** Part D, Testing Policy.

**Status, refined 2026-08-01:** root cause is more precise than first recorded. This sandbox has Python 3.10.12 only; `pyproject.toml` requires `>=3.11,<3.14`. `uv` (a Python version manager, no root needed) is present and lists 3.11.15 as installable, but the download fails with a network/connection error (`uv python install 3.11` → `tunnel error: unsuccessful` reaching `github.com` release assets) — PyPI itself is reachable (pip installs succeeded), but GitHub release-asset downloads are not, in this sandbox's network allowlist. Not a missing-tool problem, a network-restriction problem. Stays open, needs the real dev environment or a CI container with unrestricted network / a pre-provisioned 3.11+ interpreter.

### T-003 — Align Python version constraint — **BLOCKED (environment), re-attempted 2026-08-01**
**Purpose:** resolve `pyproject.toml` (`>=3.11,<3.14`) vs. `poetry.lock` (`>=3.9`) disagreement.
**Depends on:** none — parallel with T-001/T-002.
**Priority:** P1. **Effort:** XS.
**Role:** Claude, human-approved.
**Acceptance criteria:** both files declare the same minimum version; `poetry lock` regenerated clean.
**Verification:** diff of both files shows matching constraints.

**Status, refined 2026-08-01:** the earlier "no poetry binary" diagnosis was incomplete. `poetry` (2.4.1) installed cleanly via `pip install --user` this session — it was never actually absent, just not on `PATH` in the first check. With poetry available, the real blocker surfaced directly: `poetry lock --no-update` refuses outright — "The currently activated Python version 3.10.12 is not supported by the project (>=3.11,<3.14). Poetry was unable to find a compatible version." Same root cause as T-002, not a second, independent blocker: no 3.11+ interpreter, and no way to obtain one here (see T-002). Manually hand-editing `poetry.lock`'s declared constraint without a real `poetry lock` run was already ruled out as unsafe (desyncs the file from what's actually resolvable) and remains ruled out.
**Architecture:** n/a. **Roadmap:** §4, §6. **Playbook:** Part C, Dependency Upgrade Policy.

**Status:** blocked, not by decision-uncertainty but by tooling absence — `poetry` isn't installed in this sandbox, and hand-editing `poetry.lock`'s declared `python-versions` field without re-resolving would desynchronize it from the versions actually locked, which is worse than leaving the mismatch visible. `pyproject.toml`'s `>=3.11,<3.14` is the constraint that looks correct (it matches the newer type-hint syntax and dependency versions actually used in the code read this session) — recommendation is `poetry lock --no-update` in the real environment to reconcile `poetry.lock` to it, not the reverse. One task, two blockers worth distinguishing: T-002 is blocked by missing runtime/deps, T-003 is blocked by missing the `poetry` binary itself.

---

## EPIC-01 — Shared Foundation

*The one place horizontal work is correct — built once, then every later epic cuts a vertical slice through it.*

### T-004 — Record Technology Stack Decision ADR — **CLOSED 2026-08-01**
**Purpose:** fix language/framework/database/etc. within the categories the architecture deliberately left neutral.
**Depends on:** none.
**Priority:** P0. **Effort:** S.
**Role:** Human decision, Claude drafts the ADR.
**Acceptance criteria:** `docs/adr/0001-technology-stack.md` exists, dated, covers every category PRODUCT_ARCHITECTURE.md §16 left open.
**Verification:** human sign-off on the ADR.
**Architecture:** §16 (explicitly technology-neutral). **Roadmap:** n/a. **Playbook:** Part E, ADR Policy.

**Outcome:** operator accepted `docs/adr/0001-technology-stack.md` as-is on 2026-08-01 — FastAPI, PostgreSQL, SQLAlchemy 2.0 (Persistence-layer only, per IG-001), Redis + arq, React/TypeScript, first-party JWT auth, Docker packaging (no mandated orchestrator), GitHub Actions. ADR status line updated to Accepted; content not reopened or redesigned, including the one flagged thin-evidence row (React vs. Svelte/Vue), per explicit instruction.

### T-005 — Wire IG-001 into executable CI — **CLOSED 2026-08-01**
**Purpose:** make the layer-dependency rule a build property, not a described intention.
**Depends on:** T-004 ✅ closed.
**Priority:** P0. **Effort:** S.
**Role:** Claude, human-approved.
**Acceptance criteria:** CI fails on a deliberately-authored violating change; passes once reverted.
**Verification:** the deliberate-violation test itself (write it, confirm red, revert, confirm green).
**Architecture:** §12.1 (six layers). **Roadmap:** n/a. **Playbook:** §0.1 (IG-001), Part D.

**Outcome:** `scripts/check_layer_dependencies.py` — stdlib-only (ast + pathlib), deliberately not a third-party import-linter dependency, since `poetry.lock` cannot currently be regenerated in this sandbox (T-003) and IG-001's two-sentence rule doesn't need a general contract DSL. Wired into `.github/workflows/ci.yml` as a new `layer-conformance` job, independent of the `poetry install --sync` the lint/test jobs need (no shared failure mode with T-002/T-003's blockers). `tests/unit/test_scripts/test_check_layer_dependencies.py` — 9 tests, run and passed locally this session (`python -m pytest ... -o addopts=""`, standalone pytest, no project dependency stack needed): directory-absent-is-clean, clean-passes, domain→infrastructure flagged, presentation→persistence flagged, api→domain correctly allowed, application-layer correctly unchecked (IG-001 names it in neither restricted list), and — the literal acceptance criterion — `test_violation_then_revert`, proving red then green against one fixture. Also ran the checker directly against real `src/finfluencer`: clean, as expected (no layer directories exist yet, pre-T-006). **Not verified: actual GitHub Actions execution** — this repository has no remote configured (confirmed via `git remote -v`, empty), so the workflow file is correct and locally proven but has never run on GitHub's own infrastructure. Not a gap in the implementation, a gap in what can be observed from this sandbox.

### T-006 — Scaffold six-layer package skeleton — **CLOSED 2026-08-01**
**Purpose:** create the `presentation / api / application / domain / infrastructure / persistence` structure IG-001 enforces.
**Depends on:** ~~T-001, T-002, T-003, T-004, T-005~~ → **T-001, T-004, T-005** (narrowed by operator decision, 2026-08-01 — see Dependency Ruling below).
**Priority:** P0. **Effort:** XS.
**Role:** Claude, human-approved.
**Acceptance criteria:** empty packages exist, import correctly, CI (T-005) runs clean against them.
**Verification:** CI green on an empty commit.
**Architecture:** §12.1. **Roadmap:** §5 Phase 0. **Playbook:** Part D.

**Dependency ruling, 2026-08-01:** evidence-only review (BACKLOG.md, IMPLEMENTATION_ROADMAP.md, IMPLEMENTATION_PLAYBOOK.md, PRODUCT_ARCHITECTURE.md — no binding sentence found in any of the four conditioning T-006 on T-002/T-003) concluded both were soft, sequencing-inherited dependencies, not hard technical ones — T-006 touches no existing code, invokes no test suite, and needs no resolved `poetry.lock`. Operator reviewed the evidence and ruled T-006 may proceed. T-002 and T-003 remain open in their own right (EPIC-00 is not closed by this ruling) but no longer gate T-006.

**Outcome:** six `src/finfluencer/<layer>/__init__.py` packages created (`presentation`, `api`, `application`, `domain`, `infrastructure`, `persistence`), each a docstring-only module citing its exact PRODUCT_ARCHITECTURE.md §12.1 responsibility/dependency rules — no logic, per this task's own "empty by design" scope; first real content is T-007 (domain) and T-010 (infrastructure). `tests/unit/test_layer_skeleton.py` — 7 tests, run and passed locally this session (`PYTHONPATH=src python -m pytest ... -o addopts=""`, standalone pytest): all six packages import correctly, and the T-005 checker reports zero violations against the real `src/finfluencer` tree — both halves of this task's acceptance criteria proven directly, not assumed. **Not verified: a true editable install** (`pip install -e .`) — this sandbox can't run one (Python 3.11+ unavailable, T-002/T-003's root cause); local verification used `PYTHONPATH=src` as a substitute, which exercises the same import mechanics but isn't identical to what `poetry install --sync` will do on GitHub Actions. Flagged, not glossed over.

### T-007 — Port minimal Domain Model as code — **CLOSED 2026-08-01**
**Purpose:** `Tenant`, `Project`, `Dataset`, `CollectionRun` only — not all fifteen §10.1 entities. The rest arrive per-epic, as each one needs them.
**Depends on:** T-006 ✅ closed.
**Priority:** P0. **Effort:** M (2–3 days) — reconciles with existing `core/contracts.py` (812 lines) and `scope.py`'s open `AnalysisScope` question (Roadmap Risk R-2), not a from-scratch design.
**Role:** Claude (primary architect), cross-vendor AI review mandatory (Part B.1 — Domain Model change).
**Acceptance criteria:** four entities exist as typed code with the invariants §10.1 specifies for each; unit tests cover every invariant.
**Verification:** CI + fresh-context AI architecture-review pass.
**Architecture:** §10.1 (four of fifteen entities). **Roadmap:** §4 (Identity-before-everything). **Playbook:** Part B.1, Part D DoD.

**Sprint 0 scope ruling, 2026-08-01 (operator decision, following the forensic evidence review of `PRODUCT_ARCHITECTURE.md` §10.1):** the four-entity subset (`Tenant`, `Project`, `Dataset`, `CollectionRun`) is confirmed as a permitted minimal Sprint 0 slice, explicitly not the complete multi-tenant model — `User` and `TenantMembership` remain required for real multi-tenancy (Tenant's ownership of Project is indirect, via `TenantMembership`, §10.1 line 486) and are out of scope for this task by operator instruction, not by omission. `ProjectMembership`, `VerticalTemplate`, `AnalysisType`, `AnalysisRun`, `InterpretationRecord`, `Report`, `Export`, `Subscription`, and `AuditLogEntry` are likewise explicitly deferred. No authorization logic was added.

**Outcome:** `src/finfluencer/domain/entities/` — four rich entities (`Tenant`, `Project`, `Dataset`, `CollectionRun`), each a hand-written class (stdlib `enum`/`uuid` only — no Pydantic or other external SDK, per §12.1's Domain "no exceptions" dependency rule) enforcing its own lifecycle/immutability invariants through explicit methods rather than open setters, matching the "`AnalysisRun.complete()` is the only path to a status change" pattern §12.1 names at line 835. Every entity's own §10.1 invariant is enforced in code: `Project` is the aggregate root and its `active → archived` transition is one-way and freezes further mutation through `Project` itself (line 548); `Dataset`/`CollectionRun` belong to exactly one parent, enforced at construction and at `add_*()` time; `CollectionRun` is immutable once `completed` — every transition method rejects further calls once that status is reached (line 568, the literal T-007 acceptance criterion for this entity). `Tenant` deliberately holds no `projects` collection, per the forensic review's finding that Tenant's ownership of Project is indirect through `TenantMembership` (line 486) — encoding a direct collection would have fabricated a relationship the architecture does not describe. Every deferred entity/relationship (`User`, `TenantMembership`, `ProjectMembership`, `VerticalTemplate`, `AnalysisType`, `AnalysisRun`, `InterpretationRecord`, `Report`, `Export`, `Subscription`, `AuditLogEntry`) is marked with a `TODO` comment citing its exact `PRODUCT_ARCHITECTURE.md` §10.1 line range, per operator instruction — none were speculatively implemented or inferred.

`tests/unit/test_domain/` — 59 tests (`test_tenant.py`, `test_project.py`, `test_dataset.py`, `test_collection_run.py`, `test_aggregate_ownership_chain.py`), run and passed locally this session (`PYTHONPATH=src python -m pytest tests/unit/test_domain -v -o addopts=""`, standalone pytest): every invariant cited above has a direct test, including negative tests for every entity's forbidden transitions (e.g. `test_completed_run_rejects_every_transition`, parametrized over all four mutator methods) and the two "enforced by omission" invariants (no `Dataset.remove_collection_run`, no `Project.unarchive`/`Tenant.reactivate`). Combined with the pre-existing `test_layer_skeleton.py` and `test_check_layer_dependencies.py` suites: **75 tests total, all passing.** `PYTHONPATH=src python scripts/check_layer_dependencies.py` against the real `src/finfluencer` tree: **IG-001 clean** — the new `domain/entities/` package imports only its own submodules and the standard library, exactly as §12.1 requires.

**Architectural review, 2026-08-01 — passed.** An 8-point architectural-conformance check against `IMPLEMENTATION_PLAYBOOK.md` Part B.1's Domain Model criteria (aggregate root, Tenant/Project indirection, Dataset↔Project and CollectionRun↔Dataset cardinality, no mutable public setters, no business logic outside Domain, IG-001, deferred-entity documentation) found all eight satisfied, with one **Recommended** finding: `AnalysisType` (§10.1, lines 533–541) was the one deferred entity of eleven named only in `domain/entities/__init__.py`'s prose docstring, without its own dedicated `TODO` line-range citation the other ten each carry.

**Recommended finding — resolved 2026-08-01.** A dedicated `TODO(PRODUCT_ARCHITECTURE.md section 10.1, AnalysisType, lines 533-541)` comment was added in `project.py`, next to the `VerticalTemplate` TODO it's referenced from (§10.1 lines 526, 536). Re-verified via a documentation-consistency check only (not a full re-review, per operator instruction): all eleven deferred entities now have a locatable line-range citation somewhere in `domain/entities/*.py`; `python -m py_compile` confirms no syntax regression.

**T-007 fully closed.** Caveat preserved for the record rather than erased: the architectural review above was performed by Claude in the same session that authored the code under review — not a genuinely different vendor or a fresh-context session, the literal reading of Part B.1. The operator explicitly reviewed this caveat and directed T-007 be treated as architecturally accepted and fully closed on that basis; this is an operator decision, recorded as such, not a claim that a true cross-vendor review occurred. **Not verified for the same reason as T-006:** a true editable install (Python 3.11+ unavailable in this sandbox); local verification used `PYTHONPATH=src`.

### T-008 — Author API Contract schema for skeleton slice — **IMPLEMENTATION CLOSED 2026-08-01; CROSS-VENDOR REVIEW OUTSTANDING**
**Purpose:** `CreateProject`, `StartCollectionRun`, `GetCollectionRun` only — grows per-epic like the Domain Model.
**Depends on:** T-007 ✅ closed.
**Priority:** P0. **Effort:** S.
**Role:** Claude, cross-vendor AI review mandatory (API Contract change).
**Acceptance criteria:** machine-validatable schema exists for the three operations; matches §11.2's Identity and Collection service contracts for this slice.
**Verification:** schema validates against a sample request/response.
**Architecture:** §11.2. **Roadmap:** §4. **Playbook:** Part B.1.

**Naming reconciliation, 2026-08-01 (resolved) — operator-directed architectural preparation pass ahead of T-009.** This task's Purpose line originally named the third operation "`GetCollectionRunStatus`"; §11.2's actual, binding Collection Service query has always been `GetCollectionRun` (line 684) — no `GetCollectionRunStatus` query exists anywhere in the approved contract. Per operator instruction, the discrepancy is resolved in this operational document rather than in the architecture: the Purpose line above is corrected to `GetCollectionRun`, and every reference to `GetCollectionRunStatus` as an alternate name has been removed from code comments/docstrings (`presentation/dto/collection.py`, `tests/unit/test_presentation/test_dto_schema_validation.py`) rather than kept alongside the canonical name. The DTO class names themselves (`GetCollectionRunRequest`/`GetCollectionRunResponse`) never used the incorrect name — only this file's Purpose line and explanatory prose did; no code rename was required, only documentation correction.

**Outcome:** `src/finfluencer/presentation/dto/` — three DTO pairs (six Pydantic models total) per §11 command/query, per §12.1 line 814's `presentation.dto.*` convention: `identity.py` (`CreateProjectRequest`/`ProjectCreated`, §11.2 lines 657/662/776), `collection.py` (`StartCollectionRunRequest`/`CollectionRunAccepted`, §11.2 lines 683/688/689/778; `GetCollectionRunRequest`/`GetCollectionRunResponse`, §11.2 line 684). Pydantic (not stdlib-only) is used deliberately — Presentation's forbidden-dependency list (§12.1 line 813) names Application/Domain/Infrastructure/Persistence, not third-party libraries, unlike Domain's "no exceptions" rule — and reconciles with the existing `core/contracts.py` convention (snake_case fields, `ConfigDict(extra="forbid")`). No DTO imports a Domain entity (§12.1 line 813); status values are independently re-declared as `Literal`s rather than importing `ProjectStatus`/`CollectionRunStatus` from `finfluencer.domain.entities`. `idempotency_key` is a required field on both command requests, per §11.2 lines 662/688; `CollectionRunAccepted.status` is locked to the single literal `"queued"`, per line 689's "returns a `CollectionRun` in `queued` state immediately," while `GetCollectionRunResponse.status` covers the full four-value range from §10.1 line 567.

`tests/unit/test_presentation/test_dto_schema_validation.py` — 26 tests, run and passed locally this session (`PYTHONPATH=src python -m pytest tests/unit/test_presentation -v -o addopts=""`): each DTO's `model_json_schema()` output is asserted directly (closed-object shape, exact required-field set, correct enum/const values for `status`), and each DTO validates real sample request/response payloads via `model_validate()`, both positive (T-008's literal Verification line) and negative (missing idempotency key, unknown field, wrong status value, non-UUID id). Combined with the full pre-existing suite: **101 tests total, all passing.** `python scripts/check_layer_dependencies.py` against the real `src/finfluencer` tree: **IG-001 clean.**

**Dependency note, flagged rather than silently added:** validation deliberately does **not** import the third-party `jsonschema` package, even though it is present in this sandbox (`pip show jsonschema`: `Location: /usr/lib/python3/dist-packages`, `Required-by:` empty — an OS-level package, not a declared project dependency). Depending on it in committed test code would pass here and fail on a clean `poetry install` elsewhere. Validation instead runs through `pydantic` itself, already a declared main dependency (`pyproject.toml` line 78) — no new dependency, and therefore no new `poetry.lock` skew, was introduced by this task, beyond the pre-existing T-002/T-003 environment limitation.

**Not satisfied, flagged rather than silently closed:** this task's own **Role** line marks cross-vendor AI review as mandatory per Playbook Part B.1 (API Contract change), matching T-007's own outstanding gate. Recorded as implementation-complete and locally verified, not fully closed against its own Definition of Done. **Not verified for the same reason as T-006/T-007:** a true editable install (Python 3.11+ unavailable in this sandbox); local verification used `PYTHONPATH=src`, and `pydantic` was installed standalone via `pip install --break-system-packages` rather than through `poetry install --sync`.

---

## EPIC-02 — Walking Skeleton

*Sprint 0's exit gate. One deployable vertical slice, all six layers, no live external calls yet.*

### T-009 — Implement CreateProject command — **CLOSED FOR SPRINT 0 SCOPE 2026-08-01; PERSISTENCE-BACKED CRITERION DEFERRED**
**Purpose:** minimal Identity — one dev-mode user, no registration flow yet — enough to own a Project.
**Depends on:** T-007 ✅ closed, T-008 ✅ closed.
**Priority:** P0. **Effort:** S.
**Role:** Claude, human-approved.
**Acceptance criteria:** `CreateProject` API call succeeds, persists via the Persistence layer, returns per T-008's schema.
**Verification:** integration test at the API boundary.
**Architecture:** §11.2 Identity Service. **Roadmap:** §4 (Identity before Collection). **Playbook:** Part D.

**Pre-implementation naming reconciliation, 2026-08-01 (operator-directed):** BACKLOG.md's own T-008 Purpose line previously named a Collection Service operation "`GetCollectionRunStatus`," which does not exist in `PRODUCT_ARCHITECTURE.md` §11.2 — the binding query name has always been `GetCollectionRun` (line 684). Corrected in T-008's entry above (this file, not the architecture). One additional occurrence of the same incorrect name was found in `IMPLEMENTATION_ROADMAP.md` line 28 ("...an Application-layer orchestrator implementing `StartCollectionRun`/`GetCollectionRunStatus` (§11.2)") — **`IMPLEMENTATION_ROADMAP.md` is a frozen constitutional document, not left to this pass's authority to edit**, so it was left untouched and is recorded here as a Finding rather than silently fixed: **F-002 — `IMPLEMENTATION_ROADMAP.md` line 28 names a `GetCollectionRunStatus` query that does not exist in §11.2's approved Collection Service contract (the actual name is `GetCollectionRun`, line 684). Severity: cosmetic/documentation, does not block any task. Recommendation: correct on the Roadmap's next legitimate open-for-edit occasion; not urgent enough to justify reopening a frozen document on its own. Backlog-Required: no, pending operator decision.** DTO class names themselves (`GetCollectionRunRequest`/`GetCollectionRunResponse`, `presentation/dto/collection.py`) were already correct and needed no change — only prose in two documents used the wrong name, and only one of those two was ours to fix in this document.

**Scope ruling, 2026-08-01 (operator instruction):** implemented as Application orchestration and a Domain repository interface only — no Persistence Layer implementation, no authentication, no authorization, no API-layer routing. This is a deliberate narrowing of this task's own acceptance criteria for this pass, parallel to how T-007 was narrowed to four entities: the "persists via the Persistence layer" clause is **not yet satisfied** and is not claimed as satisfied — `IProjectRepository` (new, `domain/repositories.py`) is an interface only, with no concrete implementation anywhere in the repository. Closing this task fully against its original Definition of Done requires a future Persistence Layer task (not yet on the critical path by number) to supply a real `ProjectRepository`, and an API Layer task to wire an actual HTTP route. Marked closed **for Sprint 0 scope** rather than fully closed, to avoid overstating what exists.

**Outcome:** `src/finfluencer/domain/repositories.py` — `IProjectRepository`, a `typing.Protocol` with one method (`add`), per §12.1 line 831 ("Application and Domain jointly own these interfaces"). `src/finfluencer/application/orchestrators/create_project.py` — `CreateProjectOrchestrator`, `CreateProjectCommand`, `CreateProjectResult`: constructs a `Project` (Domain enforces its own invariants unchanged from T-007; the orchestrator does not re-validate), calls `IProjectRepository.add()`, returns a result shaped to map onto T-008's `ProjectCreated` DTO. Deliberately defines its own `CreateProjectCommand`/`CreateProjectResult` rather than importing `presentation.dto.identity.CreateProjectRequest`/`ProjectCreated` directly — §12.1 line 829 lists Presentation and API among Application's forbidden dependencies ("never calls upward"), a rule `scripts/check_layer_dependencies.py`'s IG-001 checker does not currently encode for the `application` layer (its own comment: "layers with no entry here (application, infrastructure, persistence) are not constrained by IG-001"). Honored as a textual architectural rule regardless of the checker's current coverage, per "no shortcuts around IG-001." `idempotency_key` (§11.2 line 662) is deliberately absent from `CreateProjectCommand` — idempotency-key deduplication is an API Layer responsibility (§12.1 line 819), not Application's, and is marked with a TODO rather than implemented here.

`tests/unit/test_application/test_create_project_orchestrator.py` — 7 tests, run and passed locally this session: successful creation and persistence via a `FakeProjectRepository` test double (an ordinary test fixture, not a Persistence-layer implementation — it never touches `src/finfluencer/persistence/`); Domain's empty-name validation error propagates uncaught and blocks persistence; two executions produce distinct IDs; the orchestrator's result is proven, by actually constructing one, to validate as a `ProjectCreated` DTO (T-009's "returns per T-008's schema" criterion); and a dedicated `ast`-based test asserting the orchestrator module contains no `import` of `finfluencer.presentation` or `finfluencer.api` (checking real import statements, not a naive text search, since the module's own docstring legitimately discusses Presentation in prose). Combined with the full pre-existing suite: **108 tests total, all passing.** `python scripts/check_layer_dependencies.py` against the real `src/finfluencer` tree: **IG-001 clean.**

**Not satisfied, flagged rather than silently closed:** the full acceptance criterion ("persists via the Persistence layer") and "CreateProject API call succeeds" (implying real API-layer routing) are both open, per the Scope ruling above — tracked, not silently declared done. No cross-vendor AI review requirement applies to this task (its own Role line says "Claude, human-approved" only, unlike T-007/T-008's Part B.1 mandate) — operator approval for this specific scope was given in this same instruction. **Not verified for the same reason as T-006/T-007/T-008:** a true editable install (Python 3.11+ unavailable in this sandbox); local verification used `PYTHONPATH=src`.

### T-010 — Wrap `collect/` + `youtube.py` as a fixture-reading Infrastructure adapter — **CLOSED FOR SPRINT 0 SCOPE 2026-08-01; CROSS-VENDOR REVIEW OUTSTANDING**
**Purpose:** reuse the tested Collection code (Roadmap §3: wrapper required) against a canned dataset — no live network dependency yet.
**Depends on:** T-006 ✅ closed, T-007 ✅ closed.
**Priority:** P0. **Effort:** M — includes authoring the Collection Engine's Context Pack as part of this task's Definition of Done, not a separate ticket.
**Role:** Claude (primary — highest-confidence existing code, per Roadmap §12 Architect's Review's own recommendation to port this first).
**Acceptance criteria:** adapter implements the Infrastructure interface the orchestrator (T-011) will call; Context Pack exists per Playbook Part B.2; Roadmap Risk R-1's `checkpoint_root`-partitioning discipline is explicit in the adapter, not assumed.
**Verification:** unit tests against the fixture dataset.
**Architecture:** §8.1, §12.1 (Infrastructure layer). **Roadmap:** §3 (Collection Engine row), §7 Risk R-1. **Playbook:** Part B.2.

**Migration Risk Checklist, 2026-08-01 (produced before implementation, per operator instruction):** assumptions (the four `collect_*` stage functions and `CheckpointManager` are correct/tested as-is; `PlatformProvider` is the correct substitution seam; preprocess/embeddings/sentiment/topics are Analysis Engine, not Collection Engine, despite living in `collect/main.py::run_pipeline` alongside the four in-scope stages); legacy contracts (uniform `collect_X(settings, prior_df, provider, checkpoint, *, output_path, ...) -> pd.DataFrame` signature; `PlatformProvider` Protocol; typed exception hierarchy); checkpoint behavior (three-tier, single-writer-per-`checkpoint_root`, exactly Risk R-1); retry semantics (internal to `providers/platform/youtube.py`, untouched — only `ResourceNotFoundError` caught per-item by stage loops, everything else propagates); idempotency expectations (unchanged config slice → Tier-2 marker hit → no-op); interruption/resume guarantees (Tier-1 JSONL survives a crash, resume skips already-recorded keys) — each verified directly against the wrapped form by a dedicated test, not merely trusted from the legacy suite (Risk R-3). One open question flagged, not resolved: the legacy engine collects for the *entire configured roster* per invocation; `PRODUCT_ARCHITECTURE.md` §10.1 scopes one `CollectionRun` to one `Dataset` — this granularity mismatch is deferred to T-011 (Application-layer sequencing, per BKG-001), recorded in the Collection Engine's `CONTEXT_PACK.md` under "Known technical debt," not silently resolved here.

**Outcome:** `src/finfluencer/domain/collection_engine.py` (new) — `ICollectionEngine` Protocol + `CollectionOutcome` dataclass, the Domain-owned interface this task's own acceptance criterion required ("the Infrastructure interface the orchestrator (T-011) will call") to exist; follows the same Domain-defines/Infrastructure-implements pattern as `IAIProvider` (§12.1 line 839). `src/finfluencer/infrastructure/collection/` (new): `collection_engine_adapter.py` (`CollectionEngineAdapter`, wraps `collect_channels/videos/comments/transcripts` + `CheckpointManager` **unmodified** — zero lines changed in any wrapped legacy file, verified by `git status`/`git diff` against `collect/` and `providers/platform/` showing no changes), `fixture_data.py` + `fixture_provider.py` (`FixtureCollectionProvider`, a `PlatformProvider` implementation answering from canned data keyed to the *real* `config/analysts.yaml` roster — no parallel fixture Settings object invented), `CONTEXT_PACK.md` (per Playbook Part B.2, including the BKG-001 layering judgment call on stage-sequencing placement, flagged explicitly for the still-outstanding cross-vendor review to weigh in on). `docs/adr/0002-collection-run-checkpoint-root-partitioning.md` (new) — records the `_paths_for(run_id)` partitioning decision that resolves Risk R-1 for this adapter specifically (R-1 itself, in `IMPLEMENTATION_ROADMAP.md` §7, is not edited — see the note below on why).

`tests/unit/test_infrastructure/test_collection/test_collection_engine_adapter.py` (new) — 10 tests, run and passed locally this session: full-pipeline counts against the fixture (4 channels/4 videos/8 comments/4 transcripts); parquet outputs land under a run-specific `data_raw/`; empty `run_id` rejected; **Risk R-1 proof** — two distinct `run_id`s get fully isolated `checkpoint_root`s, and the same `run_id` reuses its own root idempotently across calls (marker mtime unchanged on a no-op re-run); idempotency — a second call with the same `run_id` returns an identical `CollectionOutcome` and never re-contacts the provider; **the interruption/resume test** — a provider wrapper simulates a crash after 2 of 4 analysts' channel resolution, the run raises and leaves exactly 2 Tier-1 records and no `.done` marker, and a resumed run with a working provider completes all 4 while only re-contacting the provider for the 2 remaining analysts (directly answers Roadmap Risk R-3: this proves the *wrapped* form's resumability, not just the legacy suite's); two architectural-conformance checks (an `ast`-based test that the adapter never imports `finfluencer.presentation`/`finfluencer.api`, per §12.1 line 845's textual rule — not mechanically enforced by IG-001 for the `infrastructure` layer today — and a static check that the module never monkeypatches/reloads the wrapped legacy code). Combined with the full pre-existing repository test suite (excluding Analysis Engine/Reporting/market-correlation directories that require heavy ML dependencies — `torch`, `transformers`, `sentence-transformers`, `bertopic`, `pymannkendall`'s current version, none installable/compatible in this sandbox, unrelated to Collection Engine and never claimed as verified by this task): **593 pre-existing tests + 118 prior-session tests + these 10 = all passing, zero regressions.** `python scripts/check_layer_dependencies.py` against the real `src/finfluencer` tree: **IG-001 clean.**

**F-002 cross-reference:** the naming-reconciliation work done immediately before T-010 (this file's T-008 entry, and `IMPLEMENTATION_ROADMAP.md` line 28's still-open Finding) is unrelated to and unaffected by T-010's own work.

**IMPLEMENTATION_ROADMAP.md §7 Risk R-1, status note (not edited in the Roadmap itself):** `IMPLEMENTATION_PLAYBOOK.md` Part G's own worked example for this exact task says "the Roadmap's Risk Register... gets a status update, not a rewrite" as routine, expected practice. This session applied the same discipline already established for F-002 two turns ago and left `IMPLEMENTATION_ROADMAP.md` untouched, treating it as a frozen constitutional document not to be edited without explicit operator authorization — even for a routine status note the Playbook itself describes as normal workflow. **This is a genuine tension between the Playbook's prescribed process and this engagement's stricter practice, flagged rather than silently resolved either way:** R-1's resolution for the Collection Engine specifically is recorded here and in ADR-0002 instead. If the operator wants the Playbook's literal workflow honored going forward, an explicit, standing authorization to make routine Risk Register status-note edits (distinct from reopening architecture) would resolve this cleanly.

**Not satisfied, flagged rather than silently closed:** this task's own **Role** line places it in Phase 1, cross-layer, orchestrator-shaping work — Playbook Part B.1 marks this architect-heavy tier as needing the cross-vendor reviewer "wherever a second AI vendor is actually available," and Part G's own worked example for this exact scenario calls for "AI architecture-review pass, fresh context — cross-vendor, since this touches an orchestrator pattern other modules will imitate." Not performed this session, tracked the same way as T-007/T-008's outstanding review gates. The BKG-001 layering judgment call on stage-sequencing placement (see `CONTEXT_PACK.md`) is the specific item most worth that review's attention. **Not verified for the same reason as T-006/T-007/T-008/T-009:** a true editable install (Python 3.11+ unavailable in this sandbox); local verification used `PYTHONPATH=src`, with `structlog`/`pyyaml`/`pandas`/`pyarrow`/`numpy`/`tenacity`/`typer`/`langdetect` (all pre-existing declared dependencies) installed standalone via `pip install --break-system-packages` for this session's test run.

### T-011 — Implement `StartCollectionRun` orchestrator — **CLOSED (Sprint 0 scope) 2026-08-01**
**Purpose:** the Application-layer contract wrapping T-010's adapter, with idempotent dispatch.
**Depends on:** T-009, T-010, T-008.
**Priority:** P0. **Effort:** M.
**Role:** Claude, human-approved.
**Acceptance criteria:** idempotency key honored (duplicate calls are safe, per Roadmap §4's "at-least-once dispatch, idempotent handlers" call); business rules live only in Application/Domain (BKG-001).
**Verification:** duplicate-dispatch test; IG-001 CI check.
**Architecture:** BKG-001, §12.1. **Roadmap:** §4. **Playbook:** §0.1, Part D.

**Orchestration sequence, produced before implementation (operator instruction) —
full diagram in `src/finfluencer/application/orchestrators/CONTEXT_PACK.md`:** Presentation
(T-008 DTOs, not imported here) → Application (`StartCollectionRunOrchestrator.execute`:
idempotency-key lookup, then create-or-resume-or-replay decision) → Domain (`CollectionRun`'s
own `start`/`resume`/`complete`/`fail` state machine, unchanged from T-007) → Infrastructure
Adapter (`CollectionEngineAdapter`, T-010, called via `run_id=str(collection_run.id)` — this is
what makes constraint #7, "every CollectionRun owns its own checkpoint_root per ADR-0002,"
concretely true) → Legacy Collection Engine (unmodified) → Result (`StartCollectionRunResult`,
Application's own shape, not `CollectionRunAccepted` — see below on why). Every edge checked
against IG-001 in the Context Pack, including the edges the mechanical checker doesn't cover
for `application` (Presentation/API/Infrastructure all absent from source imports, enforced by
a dedicated `ast`-based test, same discipline as T-009/T-010).

**Outcome:** `src/finfluencer/domain/repositories.py` extended with `ICollectionRunRepository`
(`add(collection_run, *, idempotency_key)`, `get_by_idempotency_key(dataset_id, idempotency_key)`
— `idempotency_key` kept as repository-level bookkeeping, not a new `CollectionRun` field, so
T-007's already-closed Domain Model is not reopened). `src/finfluencer/application/orchestrators/
start_collection_run.py` (new) — `StartCollectionRunCommand`, `StartCollectionRunResult`,
`StartCollectionRunOrchestrator`. Idempotent-dispatch logic: no existing run for the
`(dataset_id, idempotency_key)` pair → create + persist + `start()` + run the engine;
existing run `completed` → return its snapshot, no re-execution; existing run `failed` → call
Domain's own `resume()` and re-invoke the engine with the *same* `run_id`, relying on
`CheckpointManager`'s existing resumability (unchanged, T-010) to skip already-completed work;
existing run `queued`/`running` → defensive no-op return (unreachable in this synchronous,
single-process model, kept only in case a future shared-process repository makes it reachable).
A mid-run engine exception is caught, `run.fail()` is called, then the exception is
**re-raised** — never swallowed, same discipline as T-009/T-010.
`src/finfluencer/application/orchestrators/CONTEXT_PACK.md` (new) — full sequence diagram,
IG-001 edge-by-edge walkthrough, and three flagged, deliberate Sprint 0 simplifications: (1) no
`IDatasetRepository`/`Dataset` aggregate load — `CollectionRun`'s own required `dataset_id`
already satisfies "belongs to exactly one Dataset," and the full aggregate-consistent pattern
needs real Persistence, not yet built; (2) **synchronous execution, not the architecture's
stated asynchronous contract** (§11.2) — no `IJobDispatcher` exists yet, so `execute()` runs the
whole pipeline inline and returns `"completed"`/`"failed"`, not an immediate `"queued"` response
matching `CollectionRunAccepted`; this orchestrator's result type is deliberately its own shape,
not that DTO, until a real async version exists; (3) no standalone `ResumeCollectionRunOrchestrator`
(named separately in §12.3) — resume is exercised only as part of `StartCollectionRun`'s own
idempotent-replay-of-a-failed-run path.

`tests/unit/test_application/test_start_collection_run_orchestrator.py` (new) — 8 tests, run and
passed locally this session, exercising the *real* T-010 `CollectionEngineAdapter` +
`FixtureCollectionProvider` end to end (only the repository is a fake, per "Persistence remains
abstract"): full pipeline completes with expected counts; the engine `run_id` used is provably
the `CollectionRun`'s own id (checkpoint subtree named after it); duplicate dispatch with the
same `(dataset_id, idempotency_key)` creates exactly one `CollectionRun` and never re-invokes the
engine; different keys (or the same key against different datasets) create distinct runs;
a mid-run crash marks the run `failed` and re-raises; **the orchestrator-level interruption/
resume test** — first dispatch crashes 2/4 analysts in, second dispatch with the *same*
idempotency key resumes via `CollectionRun.resume()`, reuses the same checkpoint_root, completes,
and only recontacts the provider for the 2 remaining analysts, with the repository never gaining
a second entry; one `ast`-based architectural-conformance test (module imports none of
`finfluencer.presentation`/`finfluencer.api`/`finfluencer.infrastructure`/`finfluencer.collect`).
Combined with the full pre-existing suite (same ML-dependent exclusions as T-010, plus
`test_cli.py`, excluded for a pre-existing, unrelated `click`/`typer` API-version mismatch in
this sandbox — `CliRunner.__init__() got an unexpected keyword argument 'mix_stderr'` — not a
regression from this task): **601 tests passing, zero failures.**
`python scripts/check_layer_dependencies.py`: **IG-001 clean.**

**Not satisfied, flagged rather than silently closed:** cross-vendor review (Playbook Part B.1)
remains outstanding, same as T-008/T-009/T-010 — Part G's own worked example calls this out
explicitly for orchestrator-pattern work "other modules will imitate," which applies here at
least as much as it did to T-010's adapter. The three Sprint 0 simplifications above (no Dataset
aggregate load, synchronous execution, no separate Resume orchestrator) are the specific items
most worth that review's attention. The standing question about authorizing routine
`IMPLEMENTATION_ROADMAP.md` Risk-Register status-note edits (raised at T-010's close) remains
unanswered — not raised again here, just still open. **Not verified for the same reason as every
prior task:** no true editable install (Python 3.11+ unavailable in this sandbox); verification
used `PYTHONPATH=src` against the existing installed dependency set, no new packages required
for this task beyond what T-010 already installed.

### T-012 — Build minimal frontend: create-Project form + status list — **CLOSED (Sprint 0 scope) 2026-08-01**
**Purpose:** the Presentation-layer half of the slice.
**Depends on:** T-008 — parallel-eligible with T-009/T-010/T-011.
**Priority:** P0. **Effort:** M.
**Role:** Claude or Copilot (established-pattern UI work), human-approved.
**Acceptance criteria:** calls only the API Gateway (T-008's schema), never Infrastructure directly (FG-001).

**Guiding questions, answered before implementation (operator instruction, "optimize for completing the Walking Skeleton"):**
- **User-visible capability unlocked:** a person can create a Project and start a Collection Run from a web page, watch it complete against fixture data, and see the result — the first time any of this work is reachable by anything other than a Python test or the CLI.
- **Why required before T-014:** T-014's acceptance criterion is "skeleton reachable in a real (even minimal) environment" — reachable implies something a person can open and use, not just a passing test suite. T-012 is the only remaining Sprint-0-scope gap between "the backend works" and "the Walking Skeleton is reachable."
- **Existing execution path completed:** the full path this whole engagement has built one layer at a time — Presentation DTOs (T-008) → Application orchestrators (T-009, T-011) → Domain (T-007) → Infrastructure (T-010) — reachable, for the first time, over a real HTTP request/response cycle instead of only in-process Python calls.

**Scope decisions, flagged rather than silently made (neither contradicts PRODUCT_ARCHITECTURE.md or ADR-0001 — both are Sprint 0 narrowings of an already-decided or already-specified thing, not new architecture):**
1. **A minimal API Layer was required, not optional.** `api.routes.*` (`PRODUCT_ARCHITECTURE.md` section 12.1) had no implementation before this task — T-012's own acceptance criterion ("calls only the API Gateway... never Infrastructure directly," FG-001) is literally unsatisfiable without one. Building it now is filling in an already-specified box (the same thing every prior task did for its own layer), not inventing a new one.
2. **FastAPI, not a new framework decision.** `docs/adr/0001-technology-stack.md` already chose FastAPI (Status: Accepted) and its own Consequences section already names `fastapi` as a dependency to add "once T-004 is approved" — this task is simply the first to actually need it. Added to `pyproject.toml` alongside `uvicorn` (the standard ASGI server every FastAPI deployment needs to run as a process, for T-014) and installed in this sandbox.
3. **A composition root (`src/finfluencer/bootstrap.py`) was required, placed deliberately outside the six layers.** Read literally, every layer's own forbidden-dependency rule (section 12.1) forbids it from constructing the concrete objects an orchestrator needs injected — Application may only depend on "Infrastructure-defined interfaces... never a concrete Infrastructure class" (line 828); API is forbidden from importing Infrastructure/Persistence at all (line 821). No layer is allowed to wire the others together. Every strict-DI architecture needs exactly one exception for this — section 12.2 line 865 already names the pattern ("Injected into Infrastructure adapters at startup... via dependency injection"). `bootstrap.py` is that startup point: object construction and route registration only, zero business logic, not walked by IG-001's checker (which only inspects `presentation`/`api`/`domain`), and documented as such in its own module docstring rather than silently relying on the checker's blind spot.
4. **Plain static HTML + vanilla JS, not the ADR-0001-decided React+TypeScript frontend.** ADR-0001 accepted React but explicitly left its own monorepo-layout/`package.json` location as an open sub-decision, and no frontend toolchain exists anywhere in this repository yet. Standing up npm/a bundler/React for a "create-Project form + status list" would be disproportionate to Sprint 0's own "prefer finishing Sprint 0 over improving existing code" instruction and would resolve ADR-0001's still-open sub-decision as a side effect of this task, not as its own considered choice. `web/index.html` (new) is a single static file with vanilla JS `fetch()` calls, served same-origin by the same FastAPI app (no CORS, no dev server, no build step) — flagged explicitly as a temporary Sprint 0 developer page, not the eventual product frontend. Full React adoption remains deferred to its own future task.
5. **`StartCollectionRun`'s route returns `GetCollectionRunResponse`, not `CollectionRunAccepted`.** `StartCollectionRunOrchestrator` (T-011) still runs synchronously to completion (its own already-flagged Sprint 0 simplification) — by the time the route's call returns, status is `completed`/`failed`, never `queued`. `CollectionRunAccepted` hard-locks `status` to the literal `"queued"`; constructing it with `"completed"` would fail validation, and forcing `"queued"` while the run has, in fact, already finished would be dishonest, not merely incomplete. `GetCollectionRunResponse` (section 11.2 line 684's query shape, which covers the full status range) is used instead — an honest reflection of today's synchronous reality. Restructuring the orchestrator to support a genuine early return is out of scope here (operator instruction: "reuse existing orchestrators") and deferred to whichever future task adds `IJobDispatcher`.

**Outcome:** `pyproject.toml` — `fastapi`/`uvicorn` added (dependencies only; ADR-0001-anticipated). `src/finfluencer/api/routes/identity.py` (new) — `POST /projects`, translates `CreateProjectRequest` (T-008) to/from `CreateProjectCommand`/`CreateProjectResult` (T-009), unmodified orchestrator. `src/finfluencer/api/routes/collection.py` (new) — `POST /datasets/{dataset_id}/collection-runs`, translates `StartCollectionRunRequest` to/from `StartCollectionRunCommand`/`StartCollectionRunResult` (T-011, unmodified), path/body `dataset_id` mismatch rejected with 400. `src/finfluencer/api/deps.py` (new) — `Request.app.state`-backed dependency providers, typed against Application only. `src/finfluencer/bootstrap.py` (new, top-level, outside the six layers — see Scope Decision 3) — `create_app()` FastAPI factory: two in-memory repository stand-ins (`_InMemoryProjectRepository`, `_InMemoryCollectionRunRepository` — the exact shape of the `FakeProjectRepository`/`FakeCollectionRunRepository` test doubles already used in T-009/T-010/T-011's own tests, relocated into a runnable composition root, explicitly non-durable, not Persistence), a `CollectionEngineAdapter` wired to `FixtureCollectionProvider` (T-010, unmodified) against a fresh temp directory, both orchestrators constructed and injected, routes registered, `GET /` serving `web/index.html`. `web/index.html` (new) — create-Project form, start-collection-run form, a client-side session status table rendering only responses the API Gateway actually returned (no invented state, no server-side list query — `ListDatasets`/`ListCollectionRunsForDataset`/`GetCollectionRun`, section 11.2 line 684, remain unimplemented, deferred).

`tests/unit/test_api/` (new, 14 tests): `test_routes_identity.py` (create succeeds with real UUID + `active` status; empty name rejected at the DTO boundary before the orchestrator runs; unknown field rejected; two calls with the same idempotency key still create two Projects — the flagged, deferred `api.middleware.idempotency` gap, documented as today's actual behavior, not an aspiration). `test_routes_collection.py` (a real HTTP call actually runs the real T-010 adapter against fixture data end to end and returns `completed`; path/body mismatch is a 400; **duplicate dispatch through the real HTTP boundary returns the identical run and does not re-collect** — T-011's idempotency proof extended one layer further, through real request/response serialization; different keys create distinct runs; unknown field rejected). `test_architectural_conformance.py` (`ast`-based proof that `api/routes/*.py` and `api/deps.py` import none of `finfluencer.domain`/`finfluencer.infrastructure`/`finfluencer.persistence` — section 12.1 line 821's "no Domain" half is not in IG-001's own `FORBIDDEN_IMPORTS` rule set per the script's own docstring, same mechanically-uncovered-edge pattern as Application/Infrastructure in T-009/T-010; plus a direct subprocess invocation of `scripts/check_layer_dependencies.py` itself). `test_ui_page.py` (the page is served, contains the expected form/table element ids and the exact `fetch()` targets) — this is the automated substitute for BACKLOG's own "manual click-through" verification line; genuine manual click-through in a real browser is a human verification step this sandbox cannot perform (no display, no browser; Playwright/Selenium are not declared dependencies and would be disproportionate to add for one smoke check) and is not claimed as satisfied here.

An environment note, found and fixed during this task, unrelated to any of the above design decisions: this sandbox had `httpx` 0.28.1 installed, which broke `starlette`'s `TestClient` (`Client.__init__() got an unexpected keyword argument 'app'` — `httpx` 0.28 dropped that constructor shortcut). `pyproject.toml` already declares `httpx = "^0.27"` (i.e. `<0.28`); downgraded the sandbox's installed `httpx` to `0.27.2` to match the project's own already-declared constraint — not a new decision, a pre-existing environment/declaration mismatch corrected to what the repository already specifies. Full suite re-run clean after the downgrade.

Combined with the full pre-existing suite (same exclusions as T-013): **617 tests passing.** Walking Skeleton regression subset (`test_domain`, `test_presentation`, `test_application`, `test_infrastructure/test_collection`, `test_api`, `test_integration`) run in isolation: **126 passing.** `python scripts/check_layer_dependencies.py`: **IG-001 clean.**

**Not satisfied, flagged rather than silently closed:** cross-vendor review (Playbook Part B.1) remains outstanding, same gate as T-008 through T-011/T-013 — this task in particular introduces a brand-new layer's first implementation (API) and a composition-root pattern other modules may imitate, which Part G's own worked-example framing (used for T-010/T-011) would treat as squarely in scope for that review. `api.middleware.idempotency` (section 12.1 line 819) remains unimplemented — `CreateProject` duplicate submissions are not deduplicated at the HTTP boundary (flagged in Scope Decision/test above). Genuine manual click-through in a real browser remains an outstanding human verification step. **Not verified for the same reason as every prior task:** no true editable install (Python 3.11+ unavailable in this sandbox); `fastapi`/`uvicorn`/`httpx` version adjustments this session are recorded above.
**Verification:** manual click-through + IG-001 CI check.
**Architecture:** FG-001, §13. **Roadmap:** §5 Phase 0. **Playbook:** Part D.

### T-013 — Prove interruption and checkpoint resume — **CLOSED (Sprint 0 scope) 2026-08-01**
**Purpose:** the platform's single non-negotiable Sprint 0 success criterion (§1.2's reproducibility promise).
**Depends on:** T-011.
**Priority:** P0. **Effort:** S.
**Role:** Claude, human-verified.
**Acceptance criteria:** an artificially interrupted `CollectionRun` resumes correctly from checkpoint with no data loss or duplication.
**Verification:** the test itself — kill the process mid-run, restart, assert correctness.
**Architecture:** §1.2. **Roadmap:** §5 Phase 0. **Playbook:** Part F, Reproducibility Checklist.

**Guiding questions, answered before implementation (operator instruction, "prioritize Walking Skeleton completion over architectural expansion"):**
- **User-visible capability unlocked:** proof that a real collection run survives an actual process crash without losing or duplicating data — `IMPLEMENTATION_ROADMAP.md` line 63's Milestone 1 ("create a Project, run a Collection against a canned fixture dataset, prove interruption and checkpoint resume end to end") and the single reproducibility guarantee the whole product promises.
- **Existing execution path extended:** the exact T-010/T-011 path — `StartCollectionRunOrchestrator` → `CollectionRun.resume()` (Domain, T-007) → `CollectionEngineAdapter.run(same run_id)` (Infrastructure, T-010) → `CheckpointManager` — now driven by a genuine, uncatchable `SIGKILL` instead of a simulated in-process exception. No new execution path.
- **New architectural concept, and why (not) unavoidable:** none in `src/finfluencer`. The only new artifact is `tests/integration/_t013_worker.py`, a test-only subprocess entry point that exists solely to give the parent test process something it can genuinely kill — it is not Domain, Application, or Infrastructure code, imports nothing that isn't already used by T-010's own tests, and is never imported by anything under `src/`.

**Outcome:** `tests/integration/` (new — the first integration-test directory, distinct from `tests/unit`, since this test spans real process/signal boundaries `tests/unit` never has). `_t013_worker.py` (new, test-only): wraps `FixtureCollectionProvider` in a thin `_SlowProvider` that sleeps between analysts (a test-timing device, not a production retry/backoff policy) and calls the real `CollectionEngineAdapter.run(run_id)` — this is what the parent test spawns as a subprocess and kills. `test_t013_interruption_and_resume.py` (new) — two tests: (1) the interruption/resume proof itself: spawns the worker as a real subprocess, polls the Tier-1 checkpoint file on disk until exactly 2 of 4 analysts are recorded, sends a real `SIGKILL` (`proc.returncode == -signal.SIGKILL` proves the kill was genuine and uncooperative, not a graceful exit), asserts the on-disk partial state is well-formed (2 valid JSON records, no duplicate analyst, no `.done` marker, no partial `channels.parquet`), then performs the Walking Skeleton resume: a `FakeCollectionRunRepository` pre-seeded with a `CollectionRun` in `failed` status (same entity id the killed subprocess used as its `run_id`), fed into a fresh `StartCollectionRunOrchestrator`, which calls `CollectionRun.resume()` and re-invokes the adapter with the identical `run_id` — reusing exactly the checkpoint state the real crash produced. Asserts final `status == "completed"`, correct `stage_row_counts`, and — the specific "no duplication" requirement — reads the four final parquet files directly and asserts `analyst_key`/`video_id`/`comment_id` uniqueness plus full row counts (4/4/8/4), proving the resumed run did not re-append rows on top of pre-crash state. (2) a control test proving the worker script itself is correct when left uninterrupted, isolating "the kill/resume mechanics failed" from "the worker script is broken." Both run and passed 5/5 consecutive times locally with no flakiness in the poll-based kill timing.

Combined with the full pre-existing suite (same exclusions as T-011, plus the two new integration tests): **603 tests passing.** Walking Skeleton regression subset (`test_domain`, `test_presentation`, `test_application`, `test_infrastructure/test_collection`, `test_integration` — T-007 through T-013's own test suites) run in isolation: **112 passing.** `python scripts/check_layer_dependencies.py`: **IG-001 clean.**

**Scope note, flagged rather than silently assumed (not a blocker; documentary evidence recorded per operator instruction on when to stop):** this test proves the *worker* (the process actually running `collect_*`) can be genuinely killed and resumed correctly — it does not prove the *orchestrator's own process* surviving a real kill, since `FakeCollectionRunRepository` is in-memory and would not survive a kill of the process that holds it. The pre-seeded `failed` `CollectionRun` record models what a real Persistence implementation would already have on disk once the crash is detected — this is the same "test double stands in for Persistence" pattern used throughout T-009/T-010/T-011, not a new gap this task introduces. `PRODUCT_ARCHITECTURE.md` section 12.2's own worker/`IJobDispatcher` model supports this split (orchestrator dispatches, a separate worker executes and can crash independently) — this is not read as a Sprint 0 simplification becoming a blocker, since T-013's acceptance criterion is about the `CollectionRun`'s data/checkpoint surviving interruption, which this test proves directly and for real. Proving the orchestrator process's own crash-survival remains explicitly out of scope, deferred to whichever future task introduces a real Persistence implementation (already flagged as Known Technical Debt in T-011's `CONTEXT_PACK.md`).

**Not satisfied, flagged rather than silently closed:** cross-vendor review (Playbook Part B.1) remains outstanding, same gate as T-008 through T-011. **Not verified for the same reason as every prior task:** no true editable install (Python 3.11+ unavailable in this sandbox); no new packages required beyond what T-010/T-011 already installed.

### T-014 — Deploy Walking Skeleton to one real minimal environment — **CLOSED 2026-08-01**
**Purpose:** Sprint 0's actual exit gate — a working, reachable thing, not finished documents.
**Depends on:** T-012, T-013.
**Priority:** P0. **Effort:** S.
**Role:** Human + Claude.
**Acceptance criteria:** skeleton reachable in a real (even minimal) environment; CI green including IG-001; Context Pack merged.
**Verification:** manual access to the deployed environment.
**Architecture:** §16.20 (single environment sufficient pre-scale). **Roadmap:** §5 Phase 0. **Playbook:** Part D.

**Evaluation, performed immediately after T-012 closed, per operator instruction ("immediately evaluate whether T-014 can complete the Walking Skeleton without introducing additional architecture"):**

**No additional architecture is required.** Everything T-014 needs already exists: a real, runnable FastAPI app (`finfluencer.bootstrap.create_app()`), a real ASGI server dependency (`uvicorn`, added in T-012), and a green CI signal (full suite + IG-001, both passing as of T-012's close). Concretely verified this session, not just asserted: started `python -m uvicorn "finfluencer.bootstrap:create_app" --factory` as a genuine standalone OS process (not `TestClient`) on `127.0.0.1`, confirmed `GET /` and `POST /projects` both respond correctly over a real socket, then stopped it cleanly. No new Domain/Application/Infrastructure/Persistence code was needed to do this. Also closed one small, pre-existing documentation gap discovered during this check: `src/finfluencer/api/CONTEXT_PACK.md` (new) — the API Layer had routes and a composition root but no Context Pack yet, unlike every other module this session (Playbook Part B.2 convention); added now since T-014's own acceptance criterion names "Context Pack merged." No architecture changed to write it.

**What T-014 cannot complete without the operator, and why this is not a "genuine contradiction" stop-condition:** this task's own **Role** line is "Human + Claude" (not "Claude, human-approved" like every task since T-007) and its **Verification** line is "manual access to the deployed environment" — both explicitly name a human participant, the same pattern already established for T-001 ("Role: Human only") and T-002/T-003 (blocked on an environment decision only a human/real infrastructure can resolve). This sandbox has no persistent, externally-reachable target and no cloud/deployment credentials — there is nothing in this environment "a real (even minimal) environment" could concretely mean beyond what was just proven (the app runs as a real process and answers real HTTP requests). Standing up genuine external reachability (a VM, a container host, even just confirming `uvicorn` running on the operator's own machine and reaching `localhost` themselves) is a decision and an action only the operator can make/take — architecturally identical to T-001's "Human only" gate, not a contradiction between the legacy pipeline and `PRODUCT_ARCHITECTURE.md` (the specific condition the operator's standing instructions ask to be flagged before proceeding), so this is reported as a bounded, human-shaped remaining step, not escalated as an architectural problem.

**Recommendation, not a decision made unilaterally:** the operator can close T-014 by either (a) running `PYTHONPATH=src uvicorn finfluencer.bootstrap:create_app --factory --host 0.0.0.0 --port 8000` themselves in an environment they control, confirming `manual access` personally, and reporting that back, or (b) explicitly scoping T-014 down to "proven runnable as a real server process in this sandbox" (what has already been verified above) as sufficient Sprint 0 closure, deferring genuine external/multi-user reachability to whenever real deployment infrastructure (Docker, per ADR-0001; a real host) is decided. Not resolved here — awaiting operator direction before marking T-014 closed.

**Status: NOT CLOSED.** Blocked only on the operator's own participation (Role: Human + Claude); nothing architectural stands in the way.

**Closure, 2026-08-01:** the operator ran `SPRINT_0_RELEASE_VERIFICATION_CHECKLIST.md` personally and approved it — every item passed, including the twelve observable-behavior checks (application start, HTTP response, home page, Create Project, Start Collection Run, duplicate-request idempotency, crash/resume per T-013, Walking Skeleton regression, IG-001, log cleanliness, working-tree cleanliness, and repository state matching the latest commit). **T-014 is closed.** This is the actual, human-verified Sprint 0 exit gate — not a Claude-only claim of completion. Full closure documentation: `SPRINT_0_RETROSPECTIVE.md`, `SPRINT_0_COMPLETION_REPORT.md`, `SPRINT_1_READINESS_ASSESSMENT.md` (all new, this date). Sprint 0 is now formally closed. Sprint 1 does not begin automatically — awaiting explicit operator approval, per the Readiness Assessment's own closing line.

---

## EPIC-03 — Live Collection *(Sprint 1 — parallel with EPIC-04/05's build phase)*

### T-015 — Replace fixture adapter with live YouTube Data API calls — **IMPLEMENTATION CLOSED 2026-08-01; LIVE-NETWORK VERIFICATION ENVIRONMENT-BLOCKED**
**Purpose:** prove the highest-confidence existing asset under real conditions.
**Depends on:** T-013.
**Priority:** P0. **Effort:** M. Update the Collection Context Pack in the same PR — no separate ticket.
**Role:** Claude, human-approved.
**Acceptance criteria:** a real channel's data is collected end to end.
**Verification:** live collection run against a small real channel.
**Architecture:** §8.1. **Roadmap:** §3, §5 Phase 1. **Playbook:** Part B.2.

**Outcome:** `build_live_collection_engine` (`src/finfluencer/infrastructure/collection/live_provider.py`) wires the real, already-tested `YouTubePlatformProvider` into `CollectionEngineAdapter` (T-010) by reusing `collect.main.build_provider_and_quota(cfg)` — the same factory `run_pipeline` already used — unmodified. `CollectionEngineAdapter` required **zero code changes**, confirming T-010's own Context Pack prediction ("a real, network-backed provider adapter is a pure constructor-argument swap"). `bootstrap.py` (T-012, Sprint 0) deliberately left untouched — the dev page's default wiring stays fixture-backed; live wiring is opt-in via an explicit caller, not a new default, since defaulting to live would spend real quota on every page load. Proven with a stubbed-`googleapiclient.discovery.build` test (`tests/unit/test_infrastructure/test_collection/test_live_provider.py`, 2 tests, both passing) that exercises the real registry lookup, real `YouTubePlatformProvider` construction, real `QuotaTracker`, real adapter, and every real `collect/*.py` stage function — only the actual network boundary is stubbed. A genuine live smoke test (`scripts/t015_live_smoke_test.py`, targeting `config/analysts.yaml`'s pilot analyst `satiroglu`, a real verified channel) was written and run twice: first hit a missing-dependency error (`google-api-python-client`, declared in `pyproject.toml` but never installed in this sandbox — installed via `pip install --break-system-packages`, matching the established on-demand-install pattern); second reached a **real HTTPS call attempt** and failed with `httplib2.socks.HTTPError: (403, b'Forbidden')`, independently confirming a direct `curl` finding that this sandbox's outbound proxy returns `403 from proxy after CONNECT` for `googleapis.com` — a genuine environment/network constraint, the same class of blocker as T-002/T-003 (Python version) and T-014 (human-verification requirement), not a code defect. **Finding, not yet acted on (T-016's job):** `youtube.py`'s own module docstring claims a retry policy for transient errors, but no retry loop or `tenacity` usage exists anywhere in `providers/platform/youtube.py` or `collect/*.py` — confirmed by direct search, documented in the Context Pack and the Migration Risk Checklist, deferred to T-016 (not silently absorbed). **Test-infrastructure gap found and fixed locally:** `tests/conftest.py`'s `autouse=True` `_reset_registry` fixture only re-imports the `language` provider subpackage after clearing the registry, not `platform` — the first test file to exercise registry-based `platform` lookup in isolation hit `ProviderNotFoundError` until a local, explicitly-ordered fixture (`_ensure_youtube_provider_registered`, depends on `_reset_registry` by name) re-registered `YouTubePlatformProvider` directly; `conftest.py` itself deliberately left unmodified (shared test infrastructure, outside T-015's scope). Full regression suite: 619 passed (same exclusions as every prior task: `test_reporting`, `test_embeddings`, `test_sentiment`, `test_topics`, `test_analysis`, `test_market`, `test_cli.py` — the last for a pre-existing, unrelated `click`/`CliRunner` version mismatch). Walking Skeleton regression subset: 128 passed, including the new `test_live_provider.py`. IG-001: clean. `docs/implementation/T-015_MIGRATION_RISK_CHECKLIST.md` and the Collection Context Pack (Integration decisions, Known technical debt, Gotchas sections) both updated in this same change set. **Deferred, environment-blocked, not a stop condition:** the actual live-network half of this task's own Verification line ("live collection run against a small real channel") could not be executed to completion in this sandbox; recommend running `scripts/t015_live_smoke_test.py` in an environment with real egress to `googleapis.com` to close that half out. Cross-vendor review outstanding, same as T-008/T-010/T-011/T-012/T-013.

### T-016 — Implement quota/rate-limit handling and retry policy — **CLOSED 2026-08-01**
**Purpose:** real external APIs fail in ways a fixture never does.
**Depends on:** T-015.
**Priority:** P0. **Effort:** M — `tenacity` is already a dependency (Baseline Report §3), not new library selection.
**Role:** Claude, human-approved.
**Acceptance criteria:** transient failures retry with backoff; quota exhaustion fails gracefully, not silently.
**Verification:** simulated quota-exhaustion and network-failure test cases.
**Architecture:** n/a (implementation detail). **Roadmap:** §7 Risk R-4 pattern (external dependency risk). **Playbook:** Part F, Reproducibility Checklist.

**Outcome:** `youtube.py::_execute` now wraps its existing HTTP-error classification (renamed to `_execute_once`) in a `tenacity.Retrying` loop — retries only `RateLimitError`/`NetworkError` (bounded attempts, exponential backoff); `QuotaExhaustedError`/`ResourceNotFoundError`/`CommentsDisabledError`/`AuthenticationError` still propagate on the first attempt. Three new optional constructor kwargs, all defaulted — zero changes required in `build_provider_and_quota`, `live_provider.py`, or the registry. Implemented inside `youtube.py` itself rather than as a wrapping decorator: `PlatformProvider`'s own Protocol docstring already specifies retries happen "inside the implementation," so a decorator would have contradicted, not fulfilled, the existing contract. 5 new tests (`TestRetryBehavior`: retry-then-succeed for both error types, retry exhaustion still raises the correct type, quota/not-found errors never retried) plus 3 existing `TestExecuteErrorClassification` cases updated to pass `retry_max_attempts=1` so they stay instant (exception-type assertions unchanged). Full regression: 624 passed. Walking Skeleton subset: 128 passed. IG-001: clean. Collection Context Pack updated (Known technical debt entry resolved). Checkpoint/idempotency/interruption guarantees unaffected by construction — retry is contained inside one provider method call, invisible to `CollectionEngineAdapter`.

### T-017 — Real-world interruption test against a live run — **IMPLEMENTATION CLOSED 2026-08-01; LIVE-NETWORK HALF ENVIRONMENT-BLOCKED**
**Purpose:** T-013 proved resume against a fixture; this proves it against real, variable-timing data.
**Depends on:** T-016.
**Priority:** P0. **Effort:** S.
**Role:** Human-verified.
**Acceptance criteria:** same correctness bar as T-013, live data.
**Verification:** the test itself.
**Architecture:** §1.2. **Roadmap:** §5 Phase 1. **Playbook:** Part F.

**Outcome:** `tests/integration/_t017_worker.py` + `test_t017_live_interruption.py` extend T-013's real-`SIGKILL`-subprocess technique to the live-provider chain (T-015's `build_provider_and_quota`, T-016's retry-wrapped `YouTubePlatformProvider`) instead of `FixtureCollectionProvider` — only the network transport (`googleapiclient.discovery.build`) is stubbed, the same boundary T-015's own `test_live_provider.py` already stubs, so the registry, `YouTubePlatformProvider` (including its T-016 retry loop), `QuotaTracker`, `CollectionEngineAdapter`, and `CheckpointManager` all run for real. Three tests, all passing: (1) a real `SIGKILL` after the channels stage checkpoints but before the videos stage starts, followed by a clean resume through `StartCollectionRunOrchestrator` (T-011) with no data loss or duplication; (2) a transient 429 on the very first network call still lets the run complete, proving T-016's retry logic survives the full subprocess/adapter/checkpoint chain, not just an isolated unit test; (3) a no-interruption control run. Single analyst (`satiroglu`) used throughout — same quota-minimization decision as T-015/T-016; flagged trade-off: makes the no-duplication assertion correct but less redundant than T-013's 4-analyst version. `PlatformProvider` Protocol and `YouTubePlatformProvider` are unmodified by this task. `scripts/t017_live_interruption_manual.py` (not a pytest test, mirrors `scripts/t015_live_smoke_test.py`'s precedent) provides the genuine real-network, real-timing half for the operator to run in an environment with real egress — attempted in this sandbox and confirmed blocked at the same point as T-015 (`httplib2.socks.HTTPError: (403, b'Forbidden')` against `googleapis.com`, via the real, unstubbed worker path this time), re-confirming rather than newly discovering the constraint. Full regression: 627 passed. Walking Skeleton subset: 131 passed. IG-001: clean. Collection Context Pack updated.

---

## EPIC-04 — Topic Analysis *(Sprint 2)*

### T-018 — Extend Domain Model: `AnalysisType`, `AnalysisRun` — **IMPLEMENTATION CLOSED 2026-08-01; CROSS-VENDOR REVIEW OUTSTANDING**
**Purpose:** the next two of fifteen §10.1 entities, added because this epic needs them, not before.
**Depends on:** T-007 — **not** T-017; can start once EPIC-02 closes, in parallel with EPIC-03.
**Priority:** P0. **Effort:** M.
**Role:** Claude, cross-vendor AI review mandatory (Domain Model change).
**Acceptance criteria:** `AnalysisRun` pinned to a specific `CollectionRun` per §10.1's hard rule; immutability enforced.
**Verification:** a test that attempts to mutate a completed `AnalysisRun` and confirms it fails.
**Architecture:** §10.1. **Roadmap:** §4 (Collection before Analysis, hard dependency). **Playbook:** Part B.1.

**Outcome:** `AnalysisType` (`domain/entities/analysis_type.py`) — minimal catalog-reference entity (`key`, `version`); no catalog/parameter-schema modeling, out of this task's scope. `AnalysisRun` (`domain/entities/analysis_run.py`) — pinned to `project_id`, `collection_run_id`, `analysis_type_id`+`analysis_type_version`, all required at construction, no setters (immutable references). Same `queued -> running -> completed | failed` lifecycle and "immutable once completed" discipline as `CollectionRun`, but deliberately has **no `resume()` method** — §10.1 line 577 specifies a failed `AnalysisRun` is retried by constructing a new instance, not by resuming the old one; this divergence from `CollectionRun` is explicit, not an oversight (tested directly: `test_analysis_run_has_no_resume_method`). 22 new tests across both entities (construction validation, lifecycle, completed-run immutability, distinct ids, collection_run_id non-settability). Roadmap Risk R-2 (`AnalysisScope` reconciliation) not touched or resolved by this task — `core.contracts.AnalysisScope` (comment-scoping) and §10.1's `AnalysisType` (pluggable analysis kind) are different concepts; §10.1's `AnalysisRun` spec has no scope reference at all, so R-2 remains legitimately deferred, not newly blocking. Full regression: 649 passed (was 627; +22). Walking Skeleton subset: 153 passed. IG-001: clean. Cross-vendor review mandatory per this task's own Role line (Domain Model change) — outstanding, non-blocking, same as T-008/010/011/012/013/015/016/017.

### T-019 — Wrap `topics/` (BERTopic) as an Infrastructure adapter — **CLOSED 2026-08-01**
**Purpose:** reuse the tested topic-modeling pipeline (Roadmap §3: wrapper required).
**Depends on:** T-018.
**Priority:** P0. **Effort:** L — first place compute cost/runtime genuinely matters; includes Context Pack in the same PR.
**Role:** Claude, human-approved.
**Acceptance criteria:** adapter produces topic assignments from a `Dataset`; Context Pack records any vertical-specific coupling found (Roadmap Risk R-6 pattern).
**Verification:** unit test against a fixture dataset with known expected topics.
**Architecture:** §8.2, §5 (analysis types as plugins). **Roadmap:** §3 (Analysis Engine row). **Playbook:** Part B.2.

**Outcome:** `domain/analysis_engine.py` (`IAnalysisEngine` Protocol, `AnalysisOutcome`) mirrors `domain/collection_engine.py`'s existing shape. `infrastructure/analysis/topics_adapter.py` (`TopicsAnalysisAdapter`) wraps `topics.pipeline.run_topics` + `BERTopicRunner` unmodified — zero lines changed in either wrapped file. `comments_path` resolved via T-010's existing directory convention (`base_root/collection_run_id/data_raw/comments.parquet`); `embeddings_index_path` is caller-supplied (flagged assumption: no task wraps `embeddings/pipeline.py` yet, out of this task's scope). Per-`analysis_run_id` checkpoint/cache/output isolation mirrors ADR-0002's Risk R-1 partitioning, applied to Analysis. 6 new tests (known-topic-assignment via fixture + fake runner, checkpoint isolation across two `analysis_run_id`s, input validation, IG-001-style ast import check, no-legacy-mutation check) — same injection technique already established in `tests/unit/test_topics` (fake `runner_factory`/`model_loader`; no `bertopic`/`umap-learn`/`hdbscan`/`torch` install needed or performed). Confirmed the pre-existing `test_topics` suite (49 passed, 1 skipped) also runs clean in this sandbox with none of those heavy deps installed, so it is now included in this task's regression run going forward (previously excluded out of an unverified assumption it needed them). Roadmap Risk R-6 (vertical coupling in `preprocess/financial_tr.py`) not encountered — this adapter never touches `preprocess/`. Full regression: 704 passed, 1 skipped. Walking Skeleton subset (now including `test_infrastructure/test_analysis`): 159 passed. IG-001: clean. Context Pack authored in the same PR. Cross-vendor review not mandatory per this task's own Role line (human-approved, not Domain-Model-change-mandatory like T-018) — none flagged as newly outstanding.

### T-020 — Implement `StartAnalysisRun` orchestrator — **CLOSED 2026-08-01**
**Purpose:** the Application-layer contract wrapping T-019, proving the `AnalysisType` plugin mechanism end to end with one real implementation.
**Depends on:** T-019.
**Priority:** P0. **Effort:** M.
**Role:** Claude, human-approved.
**Acceptance criteria:** same idempotency and BKG-001 discipline as T-011.
**Verification:** IG-001 CI check, duplicate-dispatch test.
**Architecture:** §5, BKG-001. **Roadmap:** §4. **Playbook:** Part D.

**Outcome:** `StartAnalysisRunOrchestrator` (`application/orchestrators/start_analysis_run.py`) mirrors T-011's idempotent-dispatch shape closely, with one deliberate divergence: a duplicate dispatch onto a `FAILED` `AnalysisRun` constructs and dispatches a **new** `AnalysisRun` rather than resuming in place (§10.1 line 577 — `AnalysisRun` has no `resume()`, confirmed already in T-018). New `IAnalysisRunRepository` (`domain/repositories.py`), keyed `(project_id, idempotency_key)`, with an explicit docstring flag: `add()` may be called more than once per key over a run's retry lifetime, unlike `ICollectionRunRepository`. 7 new tests, all exercising the real T-019 `TopicsAnalysisAdapter` (not mocks): happy path, duplicate-dispatch same/different keys, cross-project key isolation, fit-crash failure propagation, and the retry-creates-a-new-run proof (explicitly asserts the failed run has no `resume` attribute and its status stays `FAILED` after a successful retry under a different id). `AnalysisType`/`collection_run_id` validity is trusted as given, not verified against a repository — flagged in the Readiness Review as T-021's job, not this task's. Full regression: 711 passed, 1 skipped (was 704; +7). Walking Skeleton subset: 166 passed. IG-001: clean.

### T-021 — Verify `AnalysisRun` immutability and `CollectionRun` pinning — **CLOSED 2026-08-01 (human-verified)**
**Purpose:** the first real test of §10.1's pinning rule against actual code, not just Domain Model theory.
**Depends on:** T-020.
**Priority:** P0. **Effort:** XS.
**Role:** Claude, human-verified.
**Acceptance criteria:** an `AnalysisRun` cannot be created without a valid `CollectionRun` reference; cannot be re-pointed after creation.
**Verification:** the test itself.
**Architecture:** §10.1. **Roadmap:** §4. **Playbook:** Part F.

**Outcome:** Verification-only, per this task's own Effort-XS scope — zero production code changed; every invariant proven here was already implemented by T-018. New `tests/unit/test_domain/test_analysis_run_pinning_and_immutability.py` (16 tests): construction fails without any pinning reference (`project_id`/`collection_run_id`/`analysis_type_id`/`analysis_type_version`); no pinning field is settable after construction; pinning fields provably stable across every lifecycle transition; every field (not just `status`) unchanged after `COMPLETED` rejects further transitions; `AnalysisRun` has no `resume()` at all (class-level and instance-level check); a `FAILED` run stays `FAILED` regardless of what is called on it; retrying constructs a genuinely distinct instance pinned to the identical `CollectionRun`/`AnalysisType`, and the old failed instance remains untouched even after the retry succeeds. Full regression: 727 passed, 1 skipped (was 711; +16). Walking Skeleton subset: 182 passed. IG-001: clean. **Operator confirmed human verification 2026-08-01 — EPIC-04 (Topic Analysis, Sprint 2) is now formally CLOSED**, same convention as T-014's own closure.

---

## EPIC-05 — Sentiment Analysis *(Sprint 3)*

### T-022 — Wrap `sentiment/` pipeline as a second `AnalysisType` — **CLOSED 2026-08-01**
**Purpose:** prove the plugin pattern generalizes — not a one-off built for topic modeling specifically.
**Depends on:** T-021.
**Priority:** P0. **Effort:** M — lower risk than T-019, same established pattern.
**Role:** Copilot-eligible for the repetitive wiring, Claude for the orchestrator integration; human-approved.
**Acceptance criteria:** same as T-019/T-020, for sentiment.
**Verification:** unit test against a fixture dataset with known expected sentiment scores.
**Architecture:** §5, §8.2. **Roadmap:** §3 (Analysis Engine row). **Playbook:** Part B.1 (phase-weighted Copilot eligibility).

**Outcome:** `infrastructure/analysis/sentiment_adapter.py` (`SentimentAnalysisAdapter`) implements `IAnalysisEngine` by wrapping `sentiment.pipeline.run_sentiment` unmodified — zero lines changed in the wrapped file. `comments_path` resolved via the same T-010/T-019 directory convention. One genuinely new decision beyond T-019's own pattern: the `SentimentProvider` is resolved lazily (an optional `provider` for direct injection, or an optional zero-arg `provider_factory`, invoked only inside `run()` — never at construction), extending `TopicsAnalysisAdapter`'s existing model_loader/runner_factory deferred-callable discipline to this adapter's own dependency. **Flagged finding for T-023:** `AnalysisOutcome.topic_count` (T-019's frozen contract, not modified here) is topic-modeling-named; this adapter reuses it, populated as `sentiment_df["sentiment_class"].nunique()` (count of distinct classes produced, 0–2) — a defensible reuse of the same "nunique() of the categorical output column" shape, but a genuine naming-fit gap worth T-023's attention, documented in `CONTEXT_PACK_SENTIMENT.md`'s Gotchas. 7 new tests (known-sentiment-classification via fixture + fake provider, checkpoint isolation across two `analysis_run_id`s, lazy-provider-resolution proof, input validation, IG-001-style ast import check, no-legacy-mutation check) — same fake-injection technique as T-019, no `transformers`/`torch` install needed. Confirmed `tests/unit/test_sentiment` (20 passed) also runs clean without those heavy deps installed — same housekeeping correction as T-019's `test_topics` discovery; now included in the standard full-regression command going forward. Full regression: 754 passed, 1 skipped (was 727; +20 test_sentiment +7 new). Walking Skeleton subset: 189 passed (was 182; +7). IG-001: clean. `StartAnalysisRunOrchestrator` (T-020) not touched — diff review is T-023's own job.

### T-023 — Verify plugin pattern generalizes with zero orchestrator changes — **CLOSED 2026-08-01**
**Purpose:** if T-022 required touching `StartAnalysisRun`'s orchestrator code, the plugin abstraction has a real gap worth knowing about now, not in a third `AnalysisType` later.
**Depends on:** T-022.
**Priority:** P0. **Effort:** XS.
**Role:** Claude, human-verified.
**Acceptance criteria:** orchestrator diff for T-022 is zero, or any diff found is explicitly justified in an ADR.
**Verification:** diff review.
**Architecture:** §5. **Roadmap:** §4. **Playbook:** Part E, ADR Policy.

**Outcome:** `git diff 28ed4a3..HEAD -- src/finfluencer/application/ src/finfluencer/domain/` confirms **zero lines changed** in either tree since T-020's close — `StartAnalysisRunOrchestrator`, `IAnalysisEngine`, `AnalysisOutcome`, `IAnalysisRunRepository`, and every T-018 Domain entity are byte-identical to their T-020 state. No ADR required — the acceptance criterion's "zero diff" branch is met, not the "justified diff" branch. Verification-only, zero new production code (same precedent as T-021): new `tests/unit/test_application/test_t023_plugin_generalization.py` (3 tests) proves this structurally rather than only textually — the orchestrator actually dispatches a `SentimentAnalysisAdapter` end to end through the unmodified `IAnalysisEngine` seam; `TopicsAnalysisAdapter.run`/`SentimentAnalysisAdapter.run`/`IAnalysisEngine.run` signatures are identical; an ast-based import/control-flow check confirms the orchestrator never imports `finfluencer.topics.*`/`finfluencer.sentiment.*`/any concrete adapter, and its only three `if` branches are T-020's own create/replay/retry status dispatch, not per-`AnalysisType` branching. `AnalysisOutcome.topic_count` (TD-03) evaluated and classified **Generalize** — not fixed here, contract remains frozen pending a future task. Full regression: 757 passed, 1 skipped (was 754; +3). Walking Skeleton subset: 192 passed (was 189; +3). IG-001: clean. **Conclusion: the plugin architecture successfully generalized across two `AnalysisType` implementations with no architectural changes required.**

---

## EPIC-06 — Reporting / MVP Core Loop *(Sprint 4)*

### T-024 — Extend Domain Model: `InterpretationRecord` (kind=`raw_result_snapshot`), `Report`, `Export` — **CLOSED 2026-08-01**
**Purpose:** the reporting entities MVP needs — deliberately without the `ai_generated` kind, which is out of scope until Phase 2.
**Depends on:** T-021.
**Priority:** P0. **Effort:** M.
**Role:** Claude, cross-vendor AI review mandatory (Domain Model change).
**Acceptance criteria:** `Report` cites only immutable `InterpretationRecord` entities, never a live `AnalysisRun` pointer, per §10.0.
**Verification:** a test asserting a `Report`'s citations are frozen snapshots, not live references.
**Architecture:** §10.0, §10.1. **Roadmap:** §4 (Reporting does not require AI — the key sequencing fact). **Playbook:** Part B.1.

**Outcome:** Three new standalone Domain entities, mirroring `AnalysisRun`'s (T-018) established conventions exactly — `_common.py` primitives, `_reject_if_<terminal>()` guards, TODO comments citing exact architecture line ranges. `InterpretationRecord` (`interpretation_record.py`): `kind: InterpretationRecordKind` with only `RAW_RESULT_SNAPSHOT` implemented (`AI_GENERATED` explicitly not added — flagged, not built speculatively); zero mutating methods, immutable from construction (stronger than `CollectionRun`/`AnalysisRun`'s "immutable once completed" — there is no non-terminal state to guard). `Report` (`report.py`): **never imports `AnalysisRun`** — citations stored as `InterpretationRecord.id` only, verified by an ast-based no-import test (T-023's technique reused), structurally enforcing §10.0's "cites InterpretationRecord, never a live AnalysisRun pointer" rule rather than relying on convention; `draft → finalized` lifecycle, `add_citation()`/`finalize()`, a `version: int` field for a future (not-yet-ticketed) create-new-version command. `Export` (`export.py`): pins `(report_id, report_version)` together — not just `report_id` — so a later Report edit can never silently change what an already-generated Export represents; `ExportFormat` with only `PDF` implemented (`WORD`, tagged v1.x in §8.4, deliberately not added). One flagged assumption: `InterpretationRecord.content`'s serialization format is unspecified by the architecture (only a `selector` parameter is named, §11.2) — left as an opaque `str`, with the actual table/stat-to-string encoding deferred to T-025. Housekeeping: corrected two stale TODO comments (`project.py`, `analysis_run.py`) that still said `AnalysisRun`/`InterpretationRecord` were unimplemented after T-018 had already implemented one of them — documentation-only, zero behavioral change. 26 new tests (construction validation, immutability, ast-based no-`AnalysisRun`-import check, finalized-Report rejects further mutation, `Export` pinning). Full regression: 783 passed, 1 skipped (was 757; +26). Walking Skeleton subset: 218 passed (was 192; +26). IG-001: clean. Cross-vendor review mandatory per this task's own Role line (Domain Model change) — added to the existing outstanding batch (now T-008/010/011/012/013/015/016/017/018/024), not newly blocking.

### T-025 — Implement `GenerateReport` command — **CLOSED 2026-08-01**
**Purpose:** turn `AnalysisRun` output into citable `raw_result_snapshot` records.
**Depends on:** T-024.
**Priority:** P0. **Effort:** M.
**Role:** Claude, human-approved.
**Acceptance criteria:** a `Report` can be generated from any completed `AnalysisRun` without any AI service call.
**Verification:** integration test, topic + sentiment `AnalysisRun` → `Report`.
**Architecture:** §10.0, §11.2 Reporting Service. **Roadmap:** §4, §6 (MVP definition). **Playbook:** Part D.

**Outcome:** New Domain port `domain/reporting_engine.py` (`IResultSnapshotReader`, mirrors `IAnalysisEngine`'s shape). New Infrastructure adapter `infrastructure/reporting/snapshot_adapter.py` (`ResultSnapshotAdapter`) reads one `AnalysisRun`'s own result parquet (`topics.parquet`/`sentiment.parquet`, resolved by presence at the existing T-019/T-022 conventional path) and serializes it to JSON — **not** a wrap of `reporting/master_table.py`, which requires all three source tables simultaneously and produces a cross-AnalysisType joined table, the wrong granularity for a per-`AnalysisRun` snapshot (investigated and explicitly rejected in this task's own Readiness Review; `master_table.py` reuse remains correctly assigned to T-026). `domain/repositories.py` extended: `IAnalysisRunRepository.get_by_id()` added (a genuine minimal gap — no existing method could look up a specific, already-known `AnalysisRun` by id); two new Protocols, `IReportRepository`, `IInterpretationRecordRepository`, same minimal-surface discipline as every repository before them. `application/orchestrators/generate_report.py` (`GenerateReportOrchestrator`): reads a `completed` `AnalysisRun`'s snapshot, constructs an `InterpretationRecord` (kind=`raw_result_snapshot`, fixed `selector="full_result"` — no partial-selector query language built speculatively), and cites it into a `Report` — creating a new draft `Report` if no `existing_report_id` is given, or citing into an already-existing draft otherwise, letting one `Report` accumulate citations across multiple `AnalysisRun`s without a separate `AddCitation` orchestrator ahead of need. Zero AI interpretation logic anywhere in this module — ast-verified no import of `pandas`/`finfluencer.infrastructure.*`. 13 new tests (6 adapter: both result types, missing/ambiguous output, empty-id rejection, IG-001 ast check; 7 orchestrator: happy path, **the topic+sentiment→one-Report integration proof this task's own Verification line requires**, non-completed-run rejection, unknown-run/report rejection, cross-project-access rejection, no-pandas/no-Infrastructure ast check). Full regression: 796 passed, 1 skipped (was 783; +13). Walking Skeleton subset: 231 passed (was 218; +13). IG-001: clean. BKG-001: no business rule moved outside Application/Domain.

### T-026 — Implement table/CSV export — **CLOSED 2026-08-01**
**Purpose:** lower-risk half of export — reuses `reporting/master_table.py`'s existing, tested logic (Roadmap §3: adaptation required).
**Depends on:** T-025 — parallel-eligible with T-027.
**Priority:** P0. **Effort:** M.
**Role:** Copilot-eligible (adapting existing, tested logic), human-approved.
**Acceptance criteria:** export matches `Report` content exactly.
**Verification:** differential test against `master_table.py`'s existing output.
**Architecture:** §8.4. **Roadmap:** §3 (Reporting Engine row). **Playbook:** Part B.1.

**Outcome:** **Key architectural finding, resolved before implementation (T-026 Readiness Review):** §10.1 line 604 restricts the `Export` Domain entity to "PDF or Word" — CSV/table generation is the separate "manuscript-ready table objects... available for in-app viewing before export" capability §8.4 names. No `Export`/`ExportFormat` extension was made; this task constructs no Domain entity at all (read-only with respect to the Domain Model). New Domain port `ITableExporter` (`domain/reporting_engine.py`, alongside T-025's `IResultSnapshotReader`). New Infrastructure adapter `infrastructure/reporting/table_export_adapter.py` (`MasterTableExportAdapter`) wraps `reporting.master_table.build_master_table`/`save_master_table` **unmodified — the correct reuse target `ResultSnapshotAdapter` (T-025) deliberately was not**, confirming that earlier finding. `domain/repositories.py` extended: `IInterpretationRecordRepository.get_by_id()` added — exactly the gap T-025's own docstring anticipated this task would need. `application/orchestrators/export_report_table.py` (`ExportReportTableOrchestrator`): resolves a `Report`'s `citation_ids` → each `InterpretationRecord.analysis_run_id` → each `AnalysisRun.collection_run_id`, enforces that every citation pins to the **same** `CollectionRun` (BKG-001: enforced in Application, not Infrastructure — a joined table has no meaning across two `CollectionRun`s' comments), then exports via `ITableExporter`. 11 new tests (6 adapter: differential test proving byte-identical output to calling `build_master_table()` directly, missing-source error, empty-id rejection, IG-001 ast checks, no-legacy-mutation check; 5 orchestrator: happy path exporting a topics+sentiment `Report`, cross-`CollectionRun` rejection, no-citations rejection, unknown-report rejection, no-pandas/no-Infrastructure ast check). Full regression: 807 passed, 1 skipped (was 796; +11). Walking Skeleton subset: 242 passed (was 231; +11). IG-001: clean. `T-026_MIGRATION_RISK_CHECKLIST.md` and `CONTEXT_PACK_REPORTING.md` (extended, covers both T-025's and T-026's adapters) authored before implementation.

### T-027 — Implement PDF report rendering — **CLOSED 2026-08-03**
**Purpose:** the genuinely new half of §4's [New for rendering] tag — no existing tested code to lean on.
**Depends on:** T-025 — parallel-eligible with T-026.
**Priority:** P0. **Effort:** L — **flagged as this backlog's highest-uncertainty task**; see Internal Review.
**Role:** Claude, human-approved, extra review time budgeted.
**Acceptance criteria:** a `Report` renders to PDF, matching its citations exactly.
**Verification:** manual visual review + automated content-match test.
**Architecture:** §8.4. **Roadmap:** §3 (Reporting Engine row, explicitly [New for rendering]). **Playbook:** Part D.

**Outcome:** **Key architectural finding, resolved before implementation (T-027 Readiness Review):**
unlike T-026, this task DOES construct a Domain `Export` entity — §10.1 line 604 restricts
`Export`/`ExportFormat` to "PDF or Word", which is exactly what PDF rendering is; `Export`
(T-024) had existed, unused, until this task. No PDF rendering library was previously declared
(`ADR-0001` names none) — added `reportlab` (runtime) via new **ADR-0003**, after comparing it
against `weasyprint`/`pdfkit`/`xhtml2pdf` (rejected for external system-binary dependencies or
unavailability); `jinja2` (already declared, "Templating (report / Publication Engine)")
deliberately NOT used — zero import — deferred to a future layout-polish fast-follow, matching
BACKLOG's own Internal Review split for this task ("render the citation and data content" now,
"publication-quality layout" later). `pypdf` added as a **dev-only** dependency, used solely by
the new automated content-match test. New Domain port `IPdfRenderer` + `CitationSnapshot`
(`domain/reporting_engine.py`, alongside T-025's/T-026's ports). New Domain repository
`IExportRepository` (`add`, `get_by_report_version_and_format` — natural-key idempotency,
flagged deviation from §11.2's literal "idempotency key" wording, justified in the Readiness
Review). New Infrastructure adapter `infrastructure/reporting/pdf_renderer_adapter.py`
(`PdfRendererAdapter`) — genuinely new code, no existing tested code wrapped (confirmed by
re-reading `reporting/orchestrator.py`/`manuscript_figures.py`/`manuscript_tables.py`; all three
produce academic-publication artifacts, not an in-product `Report` render). Two new Application
orchestrators: `finalize_report.py` (`FinalizeReportOrchestrator` — the previously-unbuilt
`FinalizeReport` command, §11.2 line 722, a minimal necessary prerequisite this task discovered
it needed; provides §11.2 line 727's "finalizing twice is a no-op" idempotency at the
Application layer without loosening `Report.finalize()`'s own Domain-level terminal-state
guard) and `generate_export.py` (`GenerateExportOrchestrator` — requires a `FINALIZED` `Report`,
rejects a draft rather than auto-finalizing it, a deliberate product-behavior choice). 18 new
tests (5 adapter: content-match via `pypdf` text extraction, empty-citations/report-id/version
rejection, markup-escaping, IG-001 ast import check; 5 `FinalizeReportOrchestrator`: finalize,
idempotent-twice, unknown-report rejection, no-Infrastructure ast check; 8
`GenerateExportOrchestrator`: real end-to-end PDF generation via the real `PdfRendererAdapter`,
idempotent-no-re-render via a counting spy renderer, draft-report/no-citations/unknown-report/
non-PDF-format rejection, no-Infrastructure ast check). Full regression (`tests/unit`, excluding
two pre-existing, environment-drift-broken CLI collection files — see Current Task Risks): 1068
passed, 1 skipped (was N/A at this exact scope in prior sessions' narrower invocations — see
Reuse Summary in the full task report). `tests/integration`: 5 passed. IG-001: clean.
`T-027_MIGRATION_RISK_CHECKLIST.md`, `CONTEXT_PACK_REPORTING.md` (extended, now covers all three
Reporting Infrastructure adapters), and `docs/adr/0003-pdf-rendering-library-reportlab.md`
authored before/during implementation.

### T-028 — Build in-app Report viewing screen — **CLOSED 2026-08-03**
**Purpose:** the Presentation-layer half of Reporting.
**Depends on:** T-026, T-027.
**Priority:** P0. **Effort:** M.
**Role:** Claude or Copilot, human-approved.
**Acceptance criteria:** FG-001/FG-002 compliant — reproducible solely from backend state.
**Verification:** manual click-through, IG-001 CI check.
**Architecture:** FG-001, FG-002, §13. **Roadmap:** §5 Phase 1. **Playbook:** Part D.

**Outcome:** **Key finding, resolved before implementation (T-028 Readiness Review):**
`GenerateReport` needs a real, completed `AnalysisRun`, but `StartAnalysisRun` (T-020) had never
been exposed via API — a real gap outside T-028's own named dependencies (T-026/T-027 only).
Resolved by building `POST /collection-runs/{id}/analysis-runs` (§11.3 line 779, matched exactly)
reusing `StartAnalysisRunOrchestrator` (T-020) unmodified, wired to a new, deliberately-scoped
demo-only `IAnalysisEngine` (`_DemoTopicAssignmentEngine`, `bootstrap.py`) — NOT T-019's real
`TopicsAnalysisAdapter` (too heavy/model-dependent for a demo endpoint; T-019's own tests already
inject fakes for the same reason). Recorded as **ADR-0004**. Does not resolve ARB-01's TD-03/
TD-04 (`AnalysisType`-dispatch generalization) — wired directly, not through any new dispatch
mechanism.

Five new routes (`api/routes/analysis.py`, `api/routes/reporting.py`), all reusing T-020/T-025/
T-026/T-027's orchestrators **completely unmodified**: `StartAnalysisRun`, `GenerateReport`,
`GetReport` (new `GetReportOrchestrator` — the previously-unbuilt §11.2 line 723 query, a single
`IReportRepository.get_by_id()` wrap), `FinalizeReport`, `GenerateExport` (returns PDF bytes
directly, no download endpoint — deterministic `(report_id)`-keyed path makes idempotent replay
still serve real bytes) and table export (T-026's own capability, no §11.2 command name, returns
CSV bytes directly). `bootstrap.py` extended with four new in-memory Persistence stand-ins
(`AnalysisRun`, `Report`, `InterpretationRecord`, `Export`) and wiring for all six new
orchestrator instances, following the exact `_InMemoryProjectRepository` precedent. `web/
index.html` extended with a "Start Analysis Run"/"Reports" section (Generate/Get/Finalize/
Export PDF/Export CSV), each action showing exactly what its route returned (FG-002).

Full, real end-to-end flow manually smoke-tested (Collection → demo-Analysis → Report → Get →
Finalize → Export PDF → idempotent replay → table-export's expected 422) before writing the
automated test suite. 45 new tests (5 `GetReportOrchestrator`; 4 `api/routes/analysis.py`,
covering the real fixture-backed Collection→Analysis chain; 7 `api/routes/reporting.py`,
covering the full HTTP-level flow, idempotent PDF replay, and the documented table-export 422; 2
extending `test_ui_page.py` for the new Reports section; 2 extending
`test_architectural_conformance.py` for the two new route modules — all reusing existing test
infrastructure/patterns, no new test framework). Full regression (`tests/unit`, excluding the
two pre-existing, T-027-already-flagged environment-drift-broken CLI collection files): 1087
passed, 1 skipped. `tests/integration`: 5 passed. Walking-Skeleton-adjacent subset
(`test_application` + `test_api`): 82 passed. IG-001: clean. `T-028_MIGRATION_RISK_CHECKLIST.md`,
`api/CONTEXT_PACK.md` (extended), `docs/adr/0004-demo-analysis-engine-for-api-exposure.md`
authored before/during implementation.

**EPIC-06 (Reporting / MVP Core Loop, Sprint 4) is now 5/5 tasks CLOSED — SPRINT 4 COMPLETE.**

### T-029 — Verify MVP acceptance: full loop, reproducible
**Purpose:** the single gate that actually declares MVP done, per Roadmap §6.
**Depends on:** T-017 (real collected data — EPIC-03 rejoins here), T-023 (sentiment proven), T-028.
**Priority:** P0. **Effort:** S.
**Role:** Human sign-off.
**Acceptance criteria:** a researcher creates a Project, collects real YouTube data, runs topic *and* sentiment analysis, views and exports a Report citing raw snapshots — no AI call anywhere in the path.
**Verification:** the end-to-end run itself, performed once, live.
**Architecture:** §1.2, §3.2. **Roadmap:** §6 (MVP Definition). **Playbook:** Part G, Feature Lifecycle.

**Status, 2026-08-03: IMPLEMENTATION-SIDE VERIFICATION COMPLETE; LIVE-DATA / HUMAN SIGN-OFF HALF
OUTSTANDING** (same pattern as T-015/T-017's own closure). Full audit, end-to-end verification
(31/31 checks against the real running app, fixture/demo data), and quality-gate re-run performed
— see `T-029_MVP_VERIFICATION_REPORT.md` for the complete Evidence Matrix, MVP Gap Analysis, and
Release Readiness assessment. Zero production/test code changed by this task (`git diff --stat`
confirms). Full regression: 1087 passed, 1 skipped (unchanged from T-028's own count — no
regression). IG-001, architecture conformance, API conformance, presentation smoke tests: all
clean. **No previously-undocumented gap was found.**

**What remains before this task's own literal acceptance criterion is met, per its own Role line
("Human sign-off") and Verification line ("the end-to-end run itself, performed once, live"):**
(1) real YouTube network collection, blocked in every sandboxed environment tried so far
(T-015/T-017, re-confirmed rather than re-discovered); (2) `StartAnalysisRun`'s only API-reachable
engine is the T-028 demo stand-in (ADR-0004), not the real `TopicsAnalysisAdapter`/
`SentimentAnalysisAdapter` — resolving ARB-01's TD-03/TD-04 is required first; (3) the human,
live, once-performed run itself. **Newly surfaced by this audit, not previously stated this
plainly:** every green test result this entire engagement has ever produced, including this
session's, ran under `PYTHONPATH=src` against this sandbox's Python 3.10.12 — never through the
`pyproject.toml`-declared `>=3.11` install path (T-002/T-003, still open) — so "another developer
can clone and run this" remains unproven, not merely unverified.

**Not marked CLOSED.** This task's own Role line requires the operator's direct participation;
declaring it done from this session alone would overstate what a fixture/demo-backed
verification pass can prove.

---

## EPIC-07 — Identity Widening *(Sprint 5 — MVP completion)*

### T-030 — Implement real user registration and login
**Purpose:** replace the single dev-user now that there's real value worth protecting — deliberately sequenced last, per Roadmap §12's own self-critique: port Collection first, build real Identity once there's something to protect.
**Depends on:** T-029.
**Priority:** P0. **Effort:** M.
**Role:** Claude, cross-vendor AI review mandatory (touches Identity Service, security-adjacent).
**Acceptance criteria:** registration, login, session management per §14.2–§14.6.
**Verification:** integration test covering the full auth flow.
**Architecture:** §14. **Roadmap:** §4 (Identity before Collection is a hard *code* dependency; widening Identity beyond one dev-user is a *product-sequencing* choice, not one). **Playbook:** Part F, Security Checklist.

### T-031 — Implement single-tenant Owner/Member roles
**Purpose:** the minimal role set §6 scopes for MVP — not the full nine-role matrix from §6 of the architecture.
**Depends on:** T-030.
**Priority:** P0. **Effort:** S.
**Role:** Claude, human-approved.
**Acceptance criteria:** role checks resolve via `CheckAuthorization` (§14.10's four-step algorithm), not ad hoc per-endpoint logic.
**Verification:** unit tests for both roles' permission boundaries.
**Architecture:** §6, §14.10. **Roadmap:** §5 Phase 1. **Playbook:** Part D.

### T-032 — Tenant-isolation adversarial verification test
**Purpose:** the release-blocking defect class named throughout the Playbook — deliberately tested for, not assumed.
**Depends on:** T-031.
**Priority:** P0. **Effort:** S.
**Role:** Claude drafts, human designs the oracle (Playbook Part D: tenant-isolation tests require a human-designed oracle, not AI-generated-and-trusted).
**Acceptance criteria:** a deliberate cross-tenant access attempt is rejected.
**Verification:** the adversarial test itself.
**Architecture:** §14.7. **Roadmap:** §7 Risk R-5. **Playbook:** Part D, Testing Policy; Part F, Security Checklist.

---

## EPIC-08 — Repository Hygiene *(non-blocking, does not sit on the critical path)*

### T-033 — Triage untracked working-tree files outside the engineering scope
**Purpose:** `git status` surfaced during T-001 execution (2026-08-01) shows roughly 90 untracked files at the repo root and under `docs/` — statistical-validation exports (CSV/XLSX/JSON), gold-standard annotation datasets, `run_R4.py`–`run_R7.py`, several `pytest_output*.txt` captures, and Turkish-language "Hakem Raporu" (referee report) documents, oldest dated mid-July 2026. Nothing in `PRODUCT_ARCHITECTURE.md`, `IMPLEMENTATION_ROADMAP.md`, or this backlog accounts for what they are or whether they belong in version control at all. Left untriaged, they'll keep resurfacing in every future `git status`/`git add -A` and obscure genuine new untracked files.
**Depends on:** none — does not block T-002/T-003/T-004 or anything on the critical path.
**Priority:** P2. **Effort:** XS to classify, unknown to resolve (depends on what's decided).
**Role:** Human — this is almost certainly a decision about a separate research/publication track sharing this repository, not an engineering call Claude should make unilaterally.
**Acceptance criteria:** for each cluster of files, a decision is recorded: commit (belongs in version control), `.gitignore` (regenerable output, shouldn't be tracked), or relocate (belongs in a different repository entirely, e.g. if this is a manuscript/publication working directory that happens to share a checkout with the engineering codebase).
**Verification:** `git status --short` shows only files that are either tracked or deliberately, explicitly ignored — no unexplained untracked accumulation.
**Architecture:** n/a. **Roadmap:** n/a. **Playbook:** Part C, Repository Hygiene (existing housekeeping norms) — no new governance ID needed, this is a Temporary-Practice cleanup call, not an architectural question.

---

## Internal Review

**Is any task too large?** T-019 (BERTopic wrapper, L) and T-027 (PDF rendering, L) are the two outliers. T-019 stays as one task because splitting it would separate the adapter from its own correctness test, which shouldn't be separable. T-027 I'd genuinely reconsider before starting it — it's the one task in this backlog with no existing tested code behind it at all, and if it starts running long, split it into "render the citation and data content" versus "render publication-quality layout," ship the first half as MVP's actual export and treat layout polish as a fast-follow.

**Is any dependency unnecessary?** Yes, and I already removed it rather than just flagging it: an earlier draft of this backlog had standalone "author Context Pack" tickets after each wrapper task. A Context Pack update is Definition-of-Done-mandated on the *same* PR as the code it describes (Playbook Part B.2) — making it a separate ticket implied it could be deferred, which contradicts that rule. It's folded into T-010, T-015, and T-019's acceptance criteria instead.

**Is any task missing?** A rollback/kill-switch task for T-027 specifically, if it overruns — noted above as a contingency rather than a numbered ticket, since it only exists conditionally.

**Can any work run in parallel?** Yes, two real opportunities, not just aspirational ones: T-012 (frontend skeleton) against T-009–T-011 (backend skeleton) once T-008's contract exists, and — the larger finding — all of EPIC-03 (live collection) against EPIC-04 and EPIC-05's build phases, since neither depends on collection being *live* rather than fixture-sourced. They only have to converge at T-029.

**Is the critical path truly minimal?** For a single architect plus AI agents, yes — every remaining step depends on genuine code output from the step before it, not on documentation or ceremony. The one place it could theoretically shorten further is dropping EPIC-05 (sentiment) from the MVP-blocking path and shipping T-029 on topic modeling alone, exactly the 30%-cut option raised in the prior round — not done here because Roadmap §6 explicitly defines MVP as requiring both.

**Would I execute this myself as Engineering Lead tomorrow?** Yes, in this order, starting at T-001 this afternoon — with T-027 the one task I'd personally check in on daily rather than let run unattended, because it's the single task in the entire MVP path built on no existing tested code at all.
