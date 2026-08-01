# Sprint 1 Readiness Assessment

**Date:** 2026-08-01
**Scope of this assessment:** EPIC-03, Live Collection (`IMPLEMENTATION_ROADMAP.md`'s Sprint 1, running in parallel with EPIC-04/05's build phase per `BACKLOG.md`'s own parallelization note) — T-015 (replace fixture adapter with live YouTube Data API calls) onward.
**This document does not begin Sprint 1.** It answers the four questions the operator asked, and nothing more. No Sprint 1 planning or implementation follows this document without explicit operator approval.

---

## Is Sprint 1 technically ready?

**Conditionally yes, with one governance gate outstanding.**

Technically, the path T-015 needs already exists and is proven: `ICollectionEngine` and `CollectionEngineAdapter` (T-010) depend on `PlatformProvider` as a Protocol, not a concrete class — swapping `FixtureCollectionProvider` for a real, network-backed `YouTubePlatformProvider` implementation is, by design, a constructor-argument change, not a rewrite of the adapter. `IMPLEMENTATION_ROADMAP.md`'s own dependency line for T-015 names only `T-013` as a prerequisite, and T-013 is closed. The reproducibility guarantee T-015's live data will need to honor (checkpoint/resume under real interruption) has already been proven against a genuine process kill, not merely assumed — this is precisely the evidence `IMPLEMENTATION_ROADMAP.md` §12's Architect's Review asked for before trusting the wrapped form under real conditions.

The gate is not technical: Playbook Part B.1's mandatory cross-vendor architectural review has not been performed for T-010 (the adapter T-015 will extend), T-011 (the orchestrator T-015's real data will flow through), or T-012 (the API/composition-root pattern any new adapter wiring will imitate). T-015 is exactly the kind of task Playbook Part G's worked example describes as needing that review "wherever a second AI vendor is actually available" — and it is a higher-stakes moment to skip it than T-010 was, because T-015 is the first task in this entire engagement to spend real quota and hold real external credentials.

## What blocks Sprint 1?

Nothing architectural. The Walking Skeleton is sound, deployable, and verified. What blocks a fully clean start is the accumulated cross-vendor review debt described above — a process gate this engagement has consistently flagged rather than silently skipped, now large enough (six tasks) that beginning live-API work on top of it compounds the debt rather than merely carrying it forward.

A secondary, non-blocking factor worth naming plainly: T-002 and T-003 (verify the test suite in a real environment; align the Python version constraint) remain environment-blocked in this sandbox, and the operator's own Dependency Ruling already established these do not gate implementation work. That ruling was made when every task was still fixture-only and reversible. T-015 changes that calculus somewhat — it is the first task where a real environment's test results (rather than this sandbox's `PYTHONPATH=src` workaround) start to matter more, since real YouTube API calls consume real quota and a mistake costs more than CPU time. This does not block starting Sprint 1, but it is worth weighing before T-015's live calls go beyond a small manual smoke test.

## What should be completed before Sprint 1?

Resolving the cross-vendor review backlog — at minimum for T-010, T-011, and T-012, the three tasks establishing patterns (the adapter, the orchestrator, the composition root) that T-015 and everything after it will directly imitate or extend. This is the one item this assessment recommends actually doing before writing new code, not merely deciding about.

Two cheap, already-open decisions that have been sitting unresolved since earlier in Sprint 0 and cost nothing to close now: F-002 (the `IMPLEMENTATION_ROADMAP.md` `GetCollectionRunStatus` naming error) and the standing question of whether to grant a routine exception for Risk-Register status-note edits to that same frozen document.

Obtaining a real Python 3.11+ environment (resolving T-002/T-003's underlying blocker) before T-015's live calls move past an initial small-scale manual smoke test — not because this sandbox's results have been wrong, but because live external API work is exactly the category where "verified in a real environment, not a workaround" starts to matter for reasons beyond code correctness (actual credentials, actual quota, actual rate limits).

## What should intentionally remain deferred?

Everything this Completion Report already lists as deferred work remains correctly deferred, not accidentally postponed: the Persistence Layer, authentication and authorization, the eleven unimplemented Domain entities, `IJobDispatcher`/genuine async dispatch, a standalone `ResumeCollectionRunOrchestrator`, `api.middleware.idempotency`, the `ListDatasets`/`ListCollectionRunsForDataset`/`GetCollectionRun` queries, and the ADR-0001 React frontend. None of these block T-015 or T-016 (quota/retry handling, which depends only on T-015), and pulling any of them forward now would be exactly the kind of architecture-expansion-ahead-of-need this whole engagement has deliberately avoided at every step. `IMPLEMENTATION_ROADMAP.md`'s own §7 Risks R-2 (AnalysisScope reconciliation), R-4 (AI cost), R-5 (tenant isolation), and R-6 (vertical coupling) also remain correctly out of scope until the tasks that actually touch them arrive.

---

**Awaiting explicit operator approval before any Sprint 1 planning or implementation begins.**
