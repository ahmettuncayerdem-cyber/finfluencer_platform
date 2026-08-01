# Sprint 0 Completion Report

**Date:** 2026-08-01
**Scope:** EPIC-00 (Unfreeze the Repository, partial) through EPIC-02 (Walking Skeleton, complete).
**Status:** **Sprint 0 is closed.** T-014's Release Verification Checklist is operator-approved; every checklist item passed.

---

## Executive Summary

Sprint 0's goal, per `IMPLEMENTATION_ROADMAP.md` §5 Phase 0, was to reach Milestone 1: create a Project, run a Collection against a canned fixture dataset, and prove interruption and checkpoint resume end to end — reachable in a real, even minimal, environment. That milestone is achieved. A person can now open a web page, create a Project, start a Collection Run against fixture data, watch it complete, and trust that if the process running it were killed mid-run, it would resume correctly with no data loss or duplication — because that exact scenario has been proven with a genuine, uncatchable process kill, not a simulated one.

The path from Presentation through Application, Domain, and Infrastructure to the Legacy Collection Engine and back was built one layer at a time across eleven numbered tasks (T-001, T-004 through T-014), with the pre-existing, already-tested Collection Engine wrapped, never rewritten. Six hundred and seventeen tests pass; `IG-001`'s layer-dependency checker is clean; the application runs as a real server process and answers real HTTP requests.

What remains open is honestly accounted for below: no Persistence Layer, no authentication or authorization, eleven of fifteen Domain entities, and — most consequentially for how Sprint 1 should begin — a cross-vendor architectural review that Playbook Part B.1 treats as mandatory and that has not yet been performed for six of this sprint's eight implementation tasks.

## Sprint Goals

Per `IMPLEMENTATION_ROADMAP.md` §5 Phase 0: complete Sprint 0's seven foundational artifacts, then reach Milestone 1 (create a Project, run a Collection against fixture data, prove interruption/checkpoint resume end to end), deployed and reachable in one real minimal environment. Both halves of this goal are met.

## Completed Tasks

| Task | Outcome |
|---|---|
| T-001 | Uncommitted working-tree diff resolved (commit `e7052ea`; 13 files, corrected scope found via `git status`, not just `git diff`). |
| F-001 | Constitutional/governance documents committed for the first time (Foundation Freeze, tag `platform-foundation-v1`), outside the numbered sequence. |
| T-004 | ADR-0001 (Technology Stack) accepted: Python, FastAPI, PostgreSQL/SQLAlchemy, Redis/arq, React, JWT auth, Docker, GitHub Actions. |
| T-005 | IG-001 layer-dependency checker wired into CI. |
| T-006 | Six-layer package skeleton scaffolded. |
| T-007 | Domain Model: four of fifteen `PRODUCT_ARCHITECTURE.md` §10.1 entities (`Tenant`, `Project`, `Dataset`, `CollectionRun`) implemented with full invariant enforcement; architectural review passed, one Recommended finding resolved. |
| T-008 | API Contract DTOs for `CreateProject` and `StartCollectionRun`/`GetCollectionRun`. |
| T-009 | `CreateProjectOrchestrator` (Application) — Sprint 0 scope: no Persistence, authentication, or authorization. |
| T-010 | `CollectionEngineAdapter` (Infrastructure) wraps the Legacy Collection Engine unmodified, fixture-backed; Risk R-1 resolved for this adapter via ADR-0002; interruption/resume proven with a simulated in-process exception. |
| T-011 | `StartCollectionRunOrchestrator` (Application) — first Walking Skeleton use case: idempotent create/resume/replay dispatch, drives the real T-010 adapter end to end. |
| T-013 | Interruption/checkpoint resume proven against a **real, uncatchable `SIGKILL`** of a genuine subprocess, then a clean resume through the actual orchestrator — no data loss or row duplication, verified directly against the final parquet outputs. |
| T-012 | First implementation of the API Layer (`POST /projects`, `POST /datasets/{id}/collection-runs`) and a composition root (`bootstrap.py`); a minimal static dev frontend proves the Walking Skeleton reachable over real HTTP. |
| T-014 | Application verified to run as a real `uvicorn` process; operator completed the Release Verification Checklist; every item passed. **Closed.** |

**Blocked, not part of this closure:** T-002 (verify test suite in a real environment) and T-003 (align Python version constraint) remain environment-blocked — no Python 3.11+ interpreter obtainable in this sandbox, and no network path to acquire one. Ruled, by explicit operator decision, not to gate T-006 or anything after it. Both remain open in their own right.

## Implemented Capabilities

A person can, today, from a web browser: create a Project (`POST /projects`, backed by `CreateProjectOrchestrator` and the `Project`/`Tenant` Domain entities); start a Collection Run against a fixture dataset (`POST /datasets/{id}/collection-runs`, backed by `StartCollectionRunOrchestrator`, `CollectionRun`/`Dataset`, and the real `CollectionEngineAdapter` wrapping the unmodified Legacy Collection Engine); submit the same request twice safely, with the second call returning the original result rather than double-collecting; and trust that an interrupted run resumes correctly, because that has been proven against a real process kill, not assumed.

Underneath the reachable surface: a four-entity Domain Model with full lifecycle/invariant enforcement (`CollectionRun`'s `queued → running → completed | failed`, immutable once completed, resumable from `failed`); a Domain-owned repository/engine interface pattern (`IProjectRepository`, `ICollectionRunRepository`, `ICollectionEngine`) with Infrastructure/test-double implementations, never the reverse; per-run checkpoint isolation (ADR-0002) that structurally prevents two runs from ever sharing a checkpoint root; and a documented, deliberately-placed composition root that makes dependency injection possible without violating any layer's own forbidden-dependency rule.

## Architecture Compliance

`IG-001` (the mechanical layer-dependency checker) reports clean at every checkpoint across all fourteen tasks, with no exceptions. Every edge the checker does not mechanically cover — Application not importing Presentation/API/Infrastructure, Infrastructure not importing Presentation/API, the API Layer not importing Domain directly — is enforced instead by dedicated, hand-written `ast`-based tests, applied consistently at every layer boundary this sprint touched (five separate instances across T-009, T-010, T-011, and T-012's two rules).

Zero lines of the Legacy Collection Engine (`collect/*.py`, `core/checkpoint.py`) were modified — verified by `git diff` at every relevant task close and by a static check that the adapter never monkeypatches or reloads the wrapped modules. Zero business logic exists outside Application/Domain (BKG-001); the one exception considered and rejected was `CollectionEngineAdapter`'s internal four-stage sequencing, judged to be reuse of the legacy engine's own already-tested order, not a new rule authored at the Infrastructure layer — flagged explicitly for cross-vendor review to weigh in on, not silently decided.

One deliberate, fully-documented departure from strict six-layer purity: `bootstrap.py`, the composition root, lives outside all six layers by necessity (no layer's own rules permit it to construct the concrete objects an orchestrator needs injected) and is explicitly exempt from IG-001's checker by virtue of its placement, not by exploiting a blind spot silently.

## Testing Summary

**617 tests passing** as of this report, spanning `tests/unit` (excluding `test_reporting`, `test_embeddings`, `test_sentiment`, `test_topics`, `test_analysis`, `test_market` — pre-existing, unrelated ML-dependency gaps in this sandbox, and `test_cli.py` — a pre-existing `click`/`typer` API-version mismatch, neither caused by this engagement) and `tests/integration` (new this sprint, T-013). A focused Walking Skeleton regression subset (`test_domain`, `test_presentation`, `test_application`, `test_infrastructure/test_collection`, `test_api`, `test_integration`) passes in isolation at **126 tests**. `python scripts/check_layer_dependencies.py` reports clean at every checkpoint, most recently confirmed alongside this report.

No test written this sprint mocks the component it is meant to prove: T-010's and T-013's interruption/resume tests exercise the real `CollectionEngineAdapter` and real `CheckpointManager`; T-012's API tests exercise the real HTTP request/response cycle via FastAPI's `TestClient`, not direct Python function calls; T-013's test kills a real OS subprocess with `SIGKILL`, not a simulated exception.

## Verification Summary

The Sprint 0 Release Verification Checklist (`SPRINT_0_RELEASE_VERIFICATION_CHECKLIST.md`) — application starts, HTTP server responds, home page loads, Create Project succeeds, Start Collection Run succeeds, duplicate request behaves correctly, crash/resume already proven by T-013, Walking Skeleton regression passes, IG-001 passes, no unexpected log warnings, working tree clean, repository state matches latest commit — has been run and **approved by the operator**. This is the human half of T-014 (Role: Human + Claude; Verification: manual access to the deployed environment); Claude could not have completed it alone, and did not attempt to substitute a claim of completion for the operator's own confirmation.

## Deferred Work

Persistence Layer (real, durable repository implementations — PostgreSQL/SQLAlchemy per ADR-0001; every repository today is an in-memory stand-in). Authentication and authorization (explicitly out of scope for every Sprint 0 task by operator instruction). Eleven of fifteen Domain entities (`User`, `TenantMembership`, `ProjectMembership`, `VerticalTemplate`, `AnalysisType`, `AnalysisRun`, `InterpretationRecord`, `Report`, `Export`, `Subscription`, `AuditLogEntry`), each with a TODO citing its future attachment point. A live, network-backed `PlatformProvider` (T-015, next). Quota/rate-limit handling and retry policy (T-016). Genuine asynchronous dispatch (`IJobDispatcher`) — `StartCollectionRun` runs synchronously today, a flagged Sprint 0 simplification. A standalone `ResumeCollectionRunOrchestrator` (§12.3 names it separately; today, resume is only reachable through `StartCollectionRun`'s own idempotent-replay path). `api.middleware.idempotency` (`CreateProject` duplicates are not deduplicated at the HTTP boundary). `ListDatasets`/`ListCollectionRunsForDataset`/`GetCollectionRun` queries (the dev page's "status list" is a client-side session view of responses already received, not a server-side query). The ADR-0001-decided React+TypeScript frontend (a plain static HTML+JS page was used instead, flagged explicitly, not silently substituted).

## Remaining Technical Debt

The absence of a Persistence Layer is the single largest and most consequential item — it is the direct cause of the `IDatasetRepository` gap, the `api.middleware.idempotency` gap, and the fact that every "repository" in this codebase today is a test double relocated into a runnable process rather than a real implementation. `IMPLEMENTATION_ROADMAP.md`'s own Risk R-1 (checkpoint concurrency vs. a horizontally-scaled Worker Tier) is resolved only for the Collection Engine adapter specifically (ADR-0002); the general assumption inside `core/checkpoint.py` remains a standing, unresolved constraint. The synchronous-vs-asynchronous tension for `StartCollectionRun` surfaced twice (T-011, then again at T-012's HTTP boundary) and is fully documented but not resolved — it will surface a third time whenever `IJobDispatcher` is finally built. The `anon_salt` environment-variable default-sourcing behavior (preserved unchanged from the legacy engine) is flagged for a fresh look whenever secret management is formalized.

## Open Findings

**F-002 (open, non-blocking):** `IMPLEMENTATION_ROADMAP.md` line 28 names a `GetCollectionRunStatus` query that does not exist in the approved Collection Service contract (the actual, binding name is `GetCollectionRun`, `PRODUCT_ARCHITECTURE.md` §11.2 line 684). `BACKLOG.md` was corrected during T-008's naming-reconciliation pass; `IMPLEMENTATION_ROADMAP.md` itself was not, since it is a frozen constitutional document and this finding does not rise to a Required-level contradiction. Awaiting operator decision.

**Standing, unresolved process question (raised at T-010's close, not re-raised since):** Playbook Part G's own worked example treats `IMPLEMENTATION_ROADMAP.md` Risk-Register status updates as routine, non-ceremonial edits ("gets a status update, not a rewrite"). This engagement has held a stricter line — no edits to the Roadmap without explicit operator authorization — throughout. The operator has not yet indicated whether to grant a standing exception for this specific, narrow class of edit.

## Cross-vendor Review Status

**T-007:** an architectural conformance review was performed and operator-accepted, with one Recommended finding resolved. This review was conducted within the same session/vendor as the implementation itself — per this engagement's own standing discipline, a same-session review does not satisfy Playbook Part B.1's mandatory cross-vendor, fresh-context requirement, even though the operator explicitly chose to accept it as sufficient for closure.

**T-008, T-010, T-011, T-012, T-013:** no cross-vendor review has been performed. Each task's own `BACKLOG.md` entry flags this explicitly as outstanding, not silently assumed satisfied. **T-009** is the one exception where this gate does not apply, per that task's own Role line.

This is the single largest governance gap carried out of Sprint 0. Playbook Part G's worked example calls for exactly this review "wherever a second AI vendor is actually available" for orchestrator- and adapter-pattern work "other modules will imitate" — a description that fits T-010's adapter, T-011's orchestrator, and T-012's composition-root pattern directly.

## Sprint Assessment

Sprint 0 met its stated goal: the Walking Skeleton exists, is architecturally sound by every mechanical and textual check this engagement could apply, and is now operator-verified as reachable in a real environment. The implementation-first discipline held throughout — no task introduced governance or process beyond what the current task genuinely needed, and every scope trim (missing Persistence, synchronous execution, fixture-only provider, plain-HTML frontend) was flagged at the moment it was made rather than discovered later. The one area where this sprint's own discipline was consistently honest about falling short of the constitutional documents' own requirement is cross-vendor review — a real, unclosed gap, not a technical one, and the most important item for the operator to weigh before Sprint 1 begins.
