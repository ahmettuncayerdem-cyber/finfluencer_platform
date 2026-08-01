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

**Epic progress:** EPIC-00 (Unfreeze the Repository) 1/3 tasks closed, 2 blocked-on-environment. EPIC-01 through EPIC-07: not started. EPIC-08 (Housekeeping, non-blocking): 1 task opened, not started.

**Sprint progress (Sprint 0 = EPIC-00 through EPIC-02):** T-001 of 14 Sprint-0 tasks closed. Sprint 0 exit gate (T-014, Walking Skeleton deployed) remains untouched.

**Completed:** T-001 (uncommitted diff resolved — commit `e7052ea`, 13 files, 1438 insertions / 37 deletions).

**F-001 — Resolved 2026-08-01 via Foundation Freeze, not a numbered task.** No constitutional or implementation-planning document had ever been committed to version control (finding first surfaced during T-001's execution). Resolved by committing all nine planning/governance files across 8 commits — `a9d3b83` (Playbook, incl. Part L Collaboration Protocol, committed separately per operator instruction), `a956bc3` (governance drafts GBD-001/GEP-001), `63f94d4` (`PRODUCT_ARCHITECTURE.md`), `5718be1` (`IMPLEMENTATION_ROADMAP.md`), `ac3761f` (Baseline Report), `6fc25b5` (this file, `BACKLOG.md`), `4277abd` (ADR-0001), `9d4904c` (prompts + Context Pack template) — then tagging the result `platform-foundation-v1` (annotated, local only, no remote configured). Verified via `git show --stat` per commit (exact file lists, no scope leakage into the T-033 pile), `git status --short` (clean tracked tree), `git fsck --full` (no corruption). Repository-hygiene concern, deliberately kept outside the numbered task sequence per the Foundation Freeze classification review — see conversation history for the full Backlog-Task-vs-Milestone analysis.

**In progress / drafted, awaiting sign-off:** T-004 (Technology Stack ADR drafted — `docs/adr/0001-technology-stack.md` — needs human sign-off before T-005/T-006 start).

**Blocked (environment, not decision):** T-002 (real-environment test verification — needs Python 3.11+ and the full dependency stack, not present in this sandbox). T-003 (Python version alignment — needs the `poetry` binary itself, not present in this sandbox).

**Not started:** T-005 through T-032 (all gated, directly or transitively, on T-004's sign-off).

**Newly opened, non-blocking:** T-033 (triage ~90 untracked files found during T-001's `git status`; does not sit on the critical path).

**Critical path, restated with current position:** `[T-001 ✅] → T-002 ⏸ (env-blocked) → T-006 → T-007 → T-008 → T-009 → T-011 → T-013 → T-014 → …` — T-004 is not literally on the numbered critical-path chain but is a hard prerequisite for T-005/T-006, which are; it functions as a gate immediately after T-001/T-002/T-003 regardless.

**Parallel-work opportunities available right now:** T-002, T-003, and T-004 were correctly treated as concurrent (per BACKLOG.md's own EPIC-00 structure) — T-002 and T-003 turned out to be blocked by this sandbox specifically, not by each other or by T-004, so they remain immediately startable the moment either runs in a real environment or gets a human/CI runner. T-033 can run fully in parallel with everything else, any time.

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

### T-002 — Verify test suite in a real environment — **BLOCKED (environment), attempted 2026-08-01**
**Purpose:** replace the stale 2026-07-30 historical pass rate with a current, trustworthy result.
**Depends on:** T-001 ✅ closed.
**Priority:** P0. **Effort:** S (environment setup + one full run, ~1 day).
**Role:** Human or Claude Code, in a real environment (not this sandbox).
**Acceptance criteria:** a fresh, dated pytest run completes; pass/fail counts and coverage recorded.
**Verification:** captured pytest output file, timestamped after T-001's commit.
**Architecture:** n/a. **Roadmap:** §7 Risk R-3. **Playbook:** Part D, Testing Policy.

**Status:** genuinely blocked in this sandbox, not silently skipped — confirmed again this session: this environment has Python 3.10.12; `pyproject.toml` requires `>=3.11,<3.14`, and the full dependency stack (pydantic, structlog, torch, transformers, tenacity, etc.) is not installed here. Running pytest under a non-conforming interpreter would produce a number that looks like verification but isn't one. Stays open, needs execution in the real dev environment (or a properly provisioned CI container) — not something to fake past.

### T-003 — Align Python version constraint — **BLOCKED (environment), attempted 2026-08-01**
**Purpose:** resolve `pyproject.toml` (`>=3.11,<3.14`) vs. `poetry.lock` (`>=3.9`) disagreement.
**Depends on:** none — parallel with T-001/T-002.
**Priority:** P1. **Effort:** XS.
**Role:** Claude, human-approved.
**Acceptance criteria:** both files declare the same minimum version; `poetry lock` regenerated clean.
**Verification:** diff of both files shows matching constraints.
**Architecture:** n/a. **Roadmap:** §4, §6. **Playbook:** Part C, Dependency Upgrade Policy.

**Status:** blocked, not by decision-uncertainty but by tooling absence — `poetry` isn't installed in this sandbox, and hand-editing `poetry.lock`'s declared `python-versions` field without re-resolving would desynchronize it from the versions actually locked, which is worse than leaving the mismatch visible. `pyproject.toml`'s `>=3.11,<3.14` is the constraint that looks correct (it matches the newer type-hint syntax and dependency versions actually used in the code read this session) — recommendation is `poetry lock --no-update` in the real environment to reconcile `poetry.lock` to it, not the reverse. One task, two blockers worth distinguishing: T-002 is blocked by missing runtime/deps, T-003 is blocked by missing the `poetry` binary itself.

---

## EPIC-01 — Shared Foundation

*The one place horizontal work is correct — built once, then every later epic cuts a vertical slice through it.*

### T-004 — Record Technology Stack Decision ADR — **DRAFTED, awaiting human sign-off**
**Purpose:** fix language/framework/database/etc. within the categories the architecture deliberately left neutral.
**Depends on:** none.
**Priority:** P0. **Effort:** S.
**Role:** Human decision, Claude drafts the ADR.
**Acceptance criteria:** `docs/adr/0001-technology-stack.md` exists, dated, covers every category PRODUCT_ARCHITECTURE.md §16 left open.
**Verification:** human sign-off on the ADR.
**Architecture:** §16 (explicitly technology-neutral). **Roadmap:** n/a. **Playbook:** Part E, ADR Policy.

**Status:** `docs/adr/0001-technology-stack.md` drafted this session — FastAPI, PostgreSQL, SQLAlchemy 2.0 (Persistence-layer only, per IG-001), Redis + arq, React/TypeScript, first-party JWT auth, Docker packaging (no mandated orchestrator), GitHub Actions. Every backend row is justified from what's already in `pyproject.toml`/`core/contracts.py`, not a greenfield survey. One row flagged as genuinely thin evidence rather than near-certain: React vs. Svelte/Vue, since no frontend code exists yet either way. **Not closed** — this task's own acceptance criterion is human sign-off, which hasn't happened yet; T-005/T-006 should not start until it does.

### T-005 — Wire IG-001 into executable CI
**Purpose:** make the layer-dependency rule a build property, not a described intention.
**Depends on:** T-004 (needs to know the CI platform/language tooling).
**Priority:** P0. **Effort:** S.
**Role:** Claude, human-approved.
**Acceptance criteria:** CI fails on a deliberately-authored violating change; passes once reverted.
**Verification:** the deliberate-violation test itself (write it, confirm red, revert, confirm green).
**Architecture:** §12.1 (six layers). **Roadmap:** n/a. **Playbook:** §0.1 (IG-001), Part D.

### T-006 — Scaffold six-layer package skeleton
**Purpose:** create the `presentation / api / application / domain / infrastructure / persistence` structure IG-001 enforces.
**Depends on:** T-001, T-002, T-003, T-004, T-005.
**Priority:** P0. **Effort:** XS.
**Role:** Claude, human-approved.
**Acceptance criteria:** empty packages exist, import correctly, CI (T-005) runs clean against them.
**Verification:** CI green on an empty commit.
**Architecture:** §12.1. **Roadmap:** §5 Phase 0. **Playbook:** Part D.

### T-007 — Port minimal Domain Model as code
**Purpose:** `Tenant`, `Project`, `Dataset`, `CollectionRun` only — not all fifteen §10.1 entities. The rest arrive per-epic, as each one needs them.
**Depends on:** T-006.
**Priority:** P0. **Effort:** M (2–3 days) — reconciles with existing `core/contracts.py` (812 lines) and `scope.py`'s open `AnalysisScope` question (Roadmap Risk R-2), not a from-scratch design.
**Role:** Claude (primary architect), cross-vendor AI review mandatory (Part B.1 — Domain Model change).
**Acceptance criteria:** four entities exist as typed code with the invariants §10.1 specifies for each; unit tests cover every invariant.
**Verification:** CI + fresh-context AI architecture-review pass.
**Architecture:** §10.1 (four of fifteen entities). **Roadmap:** §4 (Identity-before-everything). **Playbook:** Part B.1, Part D DoD.

### T-008 — Author API Contract schema for skeleton slice
**Purpose:** `CreateProject`, `StartCollectionRun`, `GetCollectionRunStatus` only — grows per-epic like the Domain Model.
**Depends on:** T-007.
**Priority:** P0. **Effort:** S.
**Role:** Claude, cross-vendor AI review mandatory (API Contract change).
**Acceptance criteria:** machine-validatable schema exists for the three operations; matches §11.2's Identity and Collection service contracts for this slice.
**Verification:** schema validates against a sample request/response.
**Architecture:** §11.2. **Roadmap:** §4. **Playbook:** Part B.1.

---

## EPIC-02 — Walking Skeleton

*Sprint 0's exit gate. One deployable vertical slice, all six layers, no live external calls yet.*

### T-009 — Implement CreateProject command
**Purpose:** minimal Identity — one dev-mode user, no registration flow yet — enough to own a Project.
**Depends on:** T-007, T-008.
**Priority:** P0. **Effort:** S.
**Role:** Claude, human-approved.
**Acceptance criteria:** `CreateProject` API call succeeds, persists via the Persistence layer, returns per T-008's schema.
**Verification:** integration test at the API boundary.
**Architecture:** §11.2 Identity Service. **Roadmap:** §4 (Identity before Collection). **Playbook:** Part D.

### T-010 — Wrap `collect/` + `youtube.py` as a fixture-reading Infrastructure adapter
**Purpose:** reuse the tested Collection code (Roadmap §3: wrapper required) against a canned dataset — no live network dependency yet.
**Depends on:** T-006, T-007.
**Priority:** P0. **Effort:** M — includes authoring the Collection Engine's Context Pack as part of this task's Definition of Done, not a separate ticket.
**Role:** Claude (primary — highest-confidence existing code, per Roadmap §12 Architect's Review's own recommendation to port this first).
**Acceptance criteria:** adapter implements the Infrastructure interface the orchestrator (T-011) will call; Context Pack exists per Playbook Part B.2; Roadmap Risk R-1's `checkpoint_root`-partitioning discipline is explicit in the adapter, not assumed.
**Verification:** unit tests against the fixture dataset.
**Architecture:** §8.1, §12.1 (Infrastructure layer). **Roadmap:** §3 (Collection Engine row), §7 Risk R-1. **Playbook:** Part B.2.

### T-011 — Implement `StartCollectionRun` orchestrator
**Purpose:** the Application-layer contract wrapping T-010's adapter, with idempotent dispatch.
**Depends on:** T-009, T-010, T-008.
**Priority:** P0. **Effort:** M.
**Role:** Claude, human-approved.
**Acceptance criteria:** idempotency key honored (duplicate calls are safe, per Roadmap §4's "at-least-once dispatch, idempotent handlers" call); business rules live only in Application/Domain (BKG-001).
**Verification:** duplicate-dispatch test; IG-001 CI check.
**Architecture:** BKG-001, §12.1. **Roadmap:** §4. **Playbook:** §0.1, Part D.

### T-012 — Build minimal frontend: create-Project form + status list
**Purpose:** the Presentation-layer half of the slice.
**Depends on:** T-008 — parallel-eligible with T-009/T-010/T-011.
**Priority:** P0. **Effort:** M.
**Role:** Claude or Copilot (established-pattern UI work), human-approved.
**Acceptance criteria:** calls only the API Gateway (T-008's schema), never Infrastructure directly (FG-001).
**Verification:** manual click-through + IG-001 CI check.
**Architecture:** FG-001, §13. **Roadmap:** §5 Phase 0. **Playbook:** Part D.

### T-013 — Prove interruption and checkpoint resume
**Purpose:** the platform's single non-negotiable Sprint 0 success criterion (§1.2's reproducibility promise).
**Depends on:** T-011.
**Priority:** P0. **Effort:** S.
**Role:** Claude, human-verified.
**Acceptance criteria:** an artificially interrupted `CollectionRun` resumes correctly from checkpoint with no data loss or duplication.
**Verification:** the test itself — kill the process mid-run, restart, assert correctness.
**Architecture:** §1.2. **Roadmap:** §5 Phase 0. **Playbook:** Part F, Reproducibility Checklist.

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
