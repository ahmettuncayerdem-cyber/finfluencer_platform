# Implementation Backlog — Sprint 0 to MVP

**Status:** Operational execution artifact. Not governance, not constitutional — classified as **Temporary Practice** under `IMPLEMENTATION_PLAYBOOK.md` Part K: task status changes without ceremony, by editing this file or the equivalent tracker, no PR review required for status changes alone.
**Scope:** every task below drives toward `IMPLEMENTATION_ROADMAP.md` §6's MVP definition. Nothing here reinterprets architecture, roadmap sequencing, or playbook process — every task cites what it's grounded in instead of restating it.
**How to read this:** each task states what a developer (human or AI) can start on immediately once its dependencies are marked done. If a task isn't independently startable, it's still too abstract — none below should be.

---

## Critical Path

`T-001 → T-002 → T-006 → T-007 → T-008 → T-009 → T-011 → T-013 → T-014 → [T-018→T-019→T-020→T-021] → [T-022→T-023] → [T-024→T-025→(T-026 ‖ T-027)→T-028] → T-029 → T-030 → T-031 → T-032`

**EPIC-03 (T-015–T-017, live collection) runs in parallel with EPIC-04/05's build phase**, not before it — it only needs to rejoin at T-029, since MVP requires real collected data but nothing in EPIC-04/05/06's code depends on collection being *live* rather than fixture-sourced. This is the one non-obvious parallelization opportunity in the whole backlog; see Internal Review.

---

## Backlog Snapshot — 2026-08-01

*Temporary Practice — regenerate this section on demand, don't hand-maintain it between real state changes.*

**Epic progress:** EPIC-00 (Unfreeze the Repository) 1/3 tasks closed, 2 blocked-on-environment, no longer gating EPIC-01 (see Dependency Ruling below). EPIC-01 (Shared Foundation) 5/5 tasks closed (T-004, T-005, T-006, T-007, T-008 implementation — T-008's cross-vendor review outstanding, see its own entry). EPIC-02 (Walking Skeleton) 5/6 tasks closed for Sprint 0 scope (T-009 — Persistence-backed criterion deferred; T-010, T-011, T-012, T-013 — cross-vendor review outstanding; see each entry). EPIC-03 through EPIC-07: not started. EPIC-08 (Housekeeping, non-blocking): 1 task opened, not started.

**Sprint progress (Sprint 0 = EPIC-00 through EPIC-02):** T-001, T-004, T-005, T-006, T-007, T-008 (implementation), T-009 (Sprint 0 scope), T-010 (Sprint 0 scope), T-011 (Sprint 0 scope), T-012 (Sprint 0 scope), T-013 (Sprint 0 scope) of 14 Sprint-0 tasks closed. Only T-014 (deploy — Sprint 0 exit gate) remains of the original 14.

**Dependency ruling, 2026-08-01 (resolved):** T-006 originally listed `T-001, T-002, T-003, T-004, T-005` as dependencies. An evidence-only review (this file, `IMPLEMENTATION_ROADMAP.md`, `IMPLEMENTATION_PLAYBOOK.md`, `PRODUCT_ARCHITECTURE.md` — no other source consulted) found no binding sentence in any of the four conditioning package-skeleton creation on Python/test-suite readiness; `IMPLEMENTATION_ROADMAP.md` §12's related statement ("confirm the existing test suite actually passes... before any porting work begins") names *porting* work (T-007, T-010), not skeleton creation. Operator reviewed this finding and ruled T-002/T-003 do not block T-006. T-006's dependency list narrowed to `T-001, T-004, T-005` and closed same-day. T-002/T-003 remain open in their own right — EPIC-00 itself is not closed by this ruling, only the specific T-006 gate.

**Completed:** T-001 (uncommitted diff resolved — commit `e7052ea`, 13 files, 1438 insertions / 37 deletions). T-004 (ADR-0001 accepted). T-005 (IG-001 wired into CI). T-006 (six-layer skeleton scaffolded). T-007 (four-entity Domain Model, architectural review passed, one Recommended finding resolved). T-008 (API Contract schema implemented and locally verified — cross-vendor review outstanding, see its own entry). T-009 (`CreateProjectOrchestrator` implemented for Sprint 0 scope — no Persistence Layer, authentication, or authorization yet, see its own entry). T-010 (`CollectionEngineAdapter` wraps `collect/`+`youtube.py`'s Protocol seam unmodified, fixture-backed, checkpoint_root partitioning resolves Risk R-1, interruption/resume proven directly — cross-vendor review outstanding, see its own entry). T-011 (`StartCollectionRunOrchestrator` — first Walking Skeleton use case, idempotent dispatch with create/resume/replay handling, drives the real T-010 adapter end to end; synchronous execution and no Dataset-aggregate load flagged as deliberate Sprint 0 simplifications — cross-vendor review outstanding, see its own entry). T-013 (interruption/checkpoint-resume proven against a real, uncatchable `SIGKILL` of a genuine subprocess — not a simulated exception — then resumed through the actual `StartCollectionRunOrchestrator`; final parquet outputs verified row-unique with no data loss; no new abstractions introduced, only a test-only subprocess worker script — cross-vendor review outstanding, see its own entry). T-012 (first implementation of the API Layer — `POST /projects`, `POST /datasets/{id}/collection-runs`, both thin routes over T-009's/T-011's unmodified orchestrators; a new top-level composition root, `bootstrap.py`, wires Sprint 0 in-memory repository stand-ins and T-010's real adapter; a single static HTML+JS dev page proves the Walking Skeleton reachable end to end over real HTTP, with React deferred to its own future task — cross-vendor review outstanding, see its own entry).

**F-001 — Resolved 2026-08-01 via Foundation Freeze, not a numbered task.** No constitutional or implementation-planning document had ever been committed to version control (finding first surfaced during T-001's execution). Resolved by committing all nine planning/governance files across 8 commits — `a9d3b83` (Playbook, incl. Part L Collaboration Protocol, committed separately per operator instruction), `a956bc3` (governance drafts GBD-001/GEP-001), `63f94d4` (`PRODUCT_ARCHITECTURE.md`), `5718be1` (`IMPLEMENTATION_ROADMAP.md`), `ac3761f` (Baseline Report), `6fc25b5` (this file, `BACKLOG.md`), `4277abd` (ADR-0001), `9d4904c` (prompts + Context Pack template) — then tagging the result `platform-foundation-v1` (annotated, local only, no remote configured). Verified via `git show --stat` per commit (exact file lists, no scope leakage into the T-033 pile), `git status --short` (clean tracked tree), `git fsck --full` (no corruption). Repository-hygiene concern, deliberately kept outside the numbered task sequence per the Foundation Freeze classification review — see conversation history for the full Backlog-Task-vs-Milestone analysis.

**F-002 — Open, non-blocking, awaiting operator decision.** `IMPLEMENTATION_ROADMAP.md` line 28 names a `GetCollectionRunStatus` query in connection with §11.2, but no such query exists in the approved Collection Service contract — the actual, binding name is `GetCollectionRun` (`PRODUCT_ARCHITECTURE.md` §11.2 line 684). Found 2026-08-01 during T-008's naming-reconciliation pass (which corrected the identical error in this file, `BACKLOG.md`, per operator instruction). `IMPLEMENTATION_ROADMAP.md` is a frozen constitutional document — not edited under this pass's authority. Severity: cosmetic/documentation only, does not block T-009 or any other task. Backlog-Required: no, pending operator decision on whether/when to correct the Roadmap.

**In progress / drafted, awaiting sign-off:** none.

**Blocked (environment, not decision):** T-002, T-003 — both re-attempted 2026-08-01, root cause precise: no Python >=3.11 interpreter obtainable in this sandbox (network-restricted from downloading one; `poetry`, 2.4.1, is installed and confirms the same constraint directly via `poetry lock`). No longer gate T-006 (see Dependency Ruling above), but remain open in their own right.

**Not started:** T-014 through T-032 (T-009 through T-013 all closed for Sprint 0 scope; T-009's full closure needs a future Persistence Layer task and richer API-layer routing; T-010/T-011/T-012/T-013 need the still-outstanding cross-vendor review and, for T-010 eventually, a real network-backed provider adapter; T-011's async-dispatch/`IDatasetRepository`/`ResumeCollectionRunOrchestrator` gaps, T-013's orchestrator-process-durability scope note, and T-012's `api.middleware.idempotency`/React-deferral gaps are flagged in their own entries). T-014 (Sprint 0 exit gate) now depends on nothing outstanding — T-012 and T-013 are both closed.

**Newly opened, non-blocking:** T-033 (triage ~90 untracked files found during T-001's `git status`; does not sit on the critical path).

**Critical path, restated with current position:** `[T-001 ✅] → T-002 ⏸ (env-blocked, no longer gates T-006) → [T-006 ✅] → [T-007 ✅] → [T-008 ✅ impl., review outstanding] → [T-009 ✅ Sprint 0 scope] → [T-010 ✅ Sprint 0 scope, review outstanding] → [T-011 ✅ Sprint 0 scope, review outstanding] → [T-013 ✅ Sprint 0 scope, review outstanding] → [T-012 ✅ Sprint 0 scope, review outstanding] → T-014 (no outstanding dependency) → …` — T-004 ✅, T-005 ✅, T-006 ✅, T-007 ✅ closed. T-008/T-009/T-010/T-011/T-013 implemented 2026-08-01 (details in their own entries). T-012 implemented 2026-08-01: the API Layer's first implementation (`POST /projects`, `POST /datasets/{id}/collection-runs`), a new composition root (`src/finfluencer/bootstrap.py`, deliberately outside the six layers — see its own entry's Scope Decision 3) wiring Sprint 0 in-memory repository stand-ins and T-010's real `CollectionEngineAdapter`, and a single static HTML+JS developer page (`web/index.html`) proving Project-creation and Collection-Run-starting are reachable over real HTTP end to end — the Walking Skeleton's first "a person, not just a test, can open this" moment. React adoption (ADR-0001) deliberately deferred to its own future task; `api.middleware.idempotency` deliberately not implemented (flagged). Found and fixed one unrelated environment/declaration mismatch (`httpx` 0.28.1 installed vs. `pyproject.toml`'s own `^0.27` constraint; downgraded to comply). 617 tests total this session, all passing (14 new under `tests/unit/test_api/`); Walking Skeleton regression subset 126 passing; IG-001 clean. Cross-vendor review outstanding, same as T-008 through T-011/T-013's own gates. EPIC-01 (Shared Foundation) is now 5/5 implemented; EPIC-02 (Walking Skeleton) 5/6 for Sprint 0 scope — only T-014 (deploy) remains, and its own dependencies (T-012, T-013) are both now closed. Next unblocked task: **T-014** — see the dedicated evaluation below on whether it can complete without introducing additional architecture.

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

### T-014 — Deploy Walking Skeleton to one real minimal environment
**Purpose:** Sprint 0's actual exit gate — a working, reachable thing, not finished documents.
**Depends on:** T-012, T-013.
**Priority:** P0. **Effort:** S.
**Role:** Human + Claude.
**Acceptance criteria:** skeleton reachable in a real (even minimal) environment; CI green including IG-001; Context Pack merged.
**Verification:** manual access to the deployed environment.
**Architecture:** §16.20 (single environment sufficient pre-scale). **Roadmap:** §5 Phase 0. **Playbook:** Part D.

---

## EPIC-03 — Live Collection *(Sprint 1 — parallel with EPIC-04/05's build phase)*

### T-015 — Replace fixture adapter with live YouTube Data API calls
**Purpose:** prove the highest-confidence existing asset under real conditions.
**Depends on:** T-013.
**Priority:** P0. **Effort:** M. Update the Collection Context Pack in the same PR — no separate ticket.
**Role:** Claude, human-approved.
**Acceptance criteria:** a real channel's data is collected end to end.
**Verification:** live collection run against a small real channel.
**Architecture:** §8.1. **Roadmap:** §3, §5 Phase 1. **Playbook:** Part B.2.

### T-016 — Implement quota/rate-limit handling and retry policy
**Purpose:** real external APIs fail in ways a fixture never does.
**Depends on:** T-015.
**Priority:** P0. **Effort:** M — `tenacity` is already a dependency (Baseline Report §3), not new library selection.
**Role:** Claude, human-approved.
**Acceptance criteria:** transient failures retry with backoff; quota exhaustion fails gracefully, not silently.
**Verification:** simulated quota-exhaustion and network-failure test cases.
**Architecture:** n/a (implementation detail). **Roadmap:** §7 Risk R-4 pattern (external dependency risk). **Playbook:** Part F, Reproducibility Checklist.

### T-017 — Real-world interruption test against a live run
**Purpose:** T-013 proved resume against a fixture; this proves it against real, variable-timing data.
**Depends on:** T-016.
**Priority:** P0. **Effort:** S.
**Role:** Human-verified.
**Acceptance criteria:** same correctness bar as T-013, live data.
**Verification:** the test itself.
**Architecture:** §1.2. **Roadmap:** §5 Phase 1. **Playbook:** Part F.

---

## EPIC-04 — Topic Analysis *(Sprint 2)*

### T-018 — Extend Domain Model: `AnalysisType`, `AnalysisRun`
**Purpose:** the next two of fifteen §10.1 entities, added because this epic needs them, not before.
**Depends on:** T-007 — **not** T-017; can start once EPIC-02 closes, in parallel with EPIC-03.
**Priority:** P0. **Effort:** M.
**Role:** Claude, cross-vendor AI review mandatory (Domain Model change).
**Acceptance criteria:** `AnalysisRun` pinned to a specific `CollectionRun` per §10.1's hard rule; immutability enforced.
**Verification:** a test that attempts to mutate a completed `AnalysisRun` and confirms it fails.
**Architecture:** §10.1. **Roadmap:** §4 (Collection before Analysis, hard dependency). **Playbook:** Part B.1.

### T-019 — Wrap `topics/` (BERTopic) as an Infrastructure adapter
**Purpose:** reuse the tested topic-modeling pipeline (Roadmap §3: wrapper required).
**Depends on:** T-018.
**Priority:** P0. **Effort:** L — first place compute cost/runtime genuinely matters; includes Context Pack in the same PR.
**Role:** Claude, human-approved.
**Acceptance criteria:** adapter produces topic assignments from a `Dataset`; Context Pack records any vertical-specific coupling found (Roadmap Risk R-6 pattern).
**Verification:** unit test against a fixture dataset with known expected topics.
**Architecture:** §8.2, §5 (analysis types as plugins). **Roadmap:** §3 (Analysis Engine row). **Playbook:** Part B.2.

### T-020 — Implement `StartAnalysisRun` orchestrator
**Purpose:** the Application-layer contract wrapping T-019, proving the `AnalysisType` plugin mechanism end to end with one real implementation.
**Depends on:** T-019.
**Priority:** P0. **Effort:** M.
**Role:** Claude, human-approved.
**Acceptance criteria:** same idempotency and BKG-001 discipline as T-011.
**Verification:** IG-001 CI check, duplicate-dispatch test.
**Architecture:** §5, BKG-001. **Roadmap:** §4. **Playbook:** Part D.

### T-021 — Verify `AnalysisRun` immutability and `CollectionRun` pinning
**Purpose:** the first real test of §10.1's pinning rule against actual code, not just Domain Model theory.
**Depends on:** T-020.
**Priority:** P0. **Effort:** XS.
**Role:** Claude, human-verified.
**Acceptance criteria:** an `AnalysisRun` cannot be created without a valid `CollectionRun` reference; cannot be re-pointed after creation.
**Verification:** the test itself.
**Architecture:** §10.1. **Roadmap:** §4. **Playbook:** Part F.

---

## EPIC-05 — Sentiment Analysis *(Sprint 3)*

### T-022 — Wrap `sentiment/` pipeline as a second `AnalysisType`
**Purpose:** prove the plugin pattern generalizes — not a one-off built for topic modeling specifically.
**Depends on:** T-021.
**Priority:** P0. **Effort:** M — lower risk than T-019, same established pattern.
**Role:** Copilot-eligible for the repetitive wiring, Claude for the orchestrator integration; human-approved.
**Acceptance criteria:** same as T-019/T-020, for sentiment.
**Verification:** unit test against a fixture dataset with known expected sentiment scores.
**Architecture:** §5, §8.2. **Roadmap:** §3 (Analysis Engine row). **Playbook:** Part B.1 (phase-weighted Copilot eligibility).

### T-023 — Verify plugin pattern generalizes with zero orchestrator changes
**Purpose:** if T-022 required touching `StartAnalysisRun`'s orchestrator code, the plugin abstraction has a real gap worth knowing about now, not in a third `AnalysisType` later.
**Depends on:** T-022.
**Priority:** P0. **Effort:** XS.
**Role:** Claude, human-verified.
**Acceptance criteria:** orchestrator diff for T-022 is zero, or any diff found is explicitly justified in an ADR.
**Verification:** diff review.
**Architecture:** §5. **Roadmap:** §4. **Playbook:** Part E, ADR Policy.

---

## EPIC-06 — Reporting / MVP Core Loop *(Sprint 4)*

### T-024 — Extend Domain Model: `InterpretationRecord` (kind=`raw_result_snapshot`), `Report`, `Export`
**Purpose:** the reporting entities MVP needs — deliberately without the `ai_generated` kind, which is out of scope until Phase 2.
**Depends on:** T-021.
**Priority:** P0. **Effort:** M.
**Role:** Claude, cross-vendor AI review mandatory (Domain Model change).
**Acceptance criteria:** `Report` cites only immutable `InterpretationRecord` entities, never a live `AnalysisRun` pointer, per §10.0.
**Verification:** a test asserting a `Report`'s citations are frozen snapshots, not live references.
**Architecture:** §10.0, §10.1. **Roadmap:** §4 (Reporting does not require AI — the key sequencing fact). **Playbook:** Part B.1.

### T-025 — Implement `GenerateReport` command
**Purpose:** turn `AnalysisRun` output into citable `raw_result_snapshot` records.
**Depends on:** T-024.
**Priority:** P0. **Effort:** M.
**Role:** Claude, human-approved.
**Acceptance criteria:** a `Report` can be generated from any completed `AnalysisRun` without any AI service call.
**Verification:** integration test, topic + sentiment `AnalysisRun` → `Report`.
**Architecture:** §10.0, §11.2 Reporting Service. **Roadmap:** §4, §6 (MVP definition). **Playbook:** Part D.

### T-026 — Implement table/CSV export
**Purpose:** lower-risk half of export — reuses `reporting/master_table.py`'s existing, tested logic (Roadmap §3: adaptation required).
**Depends on:** T-025 — parallel-eligible with T-027.
**Priority:** P0. **Effort:** M.
**Role:** Copilot-eligible (adapting existing, tested logic), human-approved.
**Acceptance criteria:** export matches `Report` content exactly.
**Verification:** differential test against `master_table.py`'s existing output.
**Architecture:** §8.4. **Roadmap:** §3 (Reporting Engine row). **Playbook:** Part B.1.

### T-027 — Implement PDF report rendering
**Purpose:** the genuinely new half of §4's [New for rendering] tag — no existing tested code to lean on.
**Depends on:** T-025 — parallel-eligible with T-026.
**Priority:** P0. **Effort:** L — **flagged as this backlog's highest-uncertainty task**; see Internal Review.
**Role:** Claude, human-approved, extra review time budgeted.
**Acceptance criteria:** a `Report` renders to PDF, matching its citations exactly.
**Verification:** manual visual review + automated content-match test.
**Architecture:** §8.4. **Roadmap:** §3 (Reporting Engine row, explicitly [New for rendering]). **Playbook:** Part D.

### T-028 — Build in-app Report viewing screen
**Purpose:** the Presentation-layer half of Reporting.
**Depends on:** T-026, T-027.
**Priority:** P0. **Effort:** M.
**Role:** Claude or Copilot, human-approved.
**Acceptance criteria:** FG-001/FG-002 compliant — reproducible solely from backend state.
**Verification:** manual click-through, IG-001 CI check.
**Architecture:** FG-001, FG-002, §13. **Roadmap:** §5 Phase 1. **Playbook:** Part D.

### T-029 — Verify MVP acceptance: full loop, reproducible
**Purpose:** the single gate that actually declares MVP done, per Roadmap §6.
**Depends on:** T-017 (real collected data — EPIC-03 rejoins here), T-023 (sentiment proven), T-028.
**Priority:** P0. **Effort:** S.
**Role:** Human sign-off.
**Acceptance criteria:** a researcher creates a Project, collects real YouTube data, runs topic *and* sentiment analysis, views and exports a Report citing raw snapshots — no AI call anywhere in the path.
**Verification:** the end-to-end run itself, performed once, live.
**Architecture:** §1.2, §3.2. **Roadmap:** §6 (MVP Definition). **Playbook:** Part G, Feature Lifecycle.

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
