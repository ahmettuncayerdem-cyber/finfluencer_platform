# Sprint 5 Readiness Assessment

**Date:** 2026-08-03
**Scope of this assessment:** the gate between Sprint 4's close (EPIC-06, Reporting) and
Sprint 5 (EPIC-07, Identity Widening) — which, per `BACKLOG.md`'s own critical path, is **not**
a direct transition: `T-029` (Verify MVP acceptance: full loop, reproducible) sits between them
and has not been authorized or started. This is the Sprint 4 closure sequence's own required
readiness assessment (naming follows `SPRINT_1_READINESS_ASSESSMENT.md`'s precedent — produced
at the prior sprint's close, titled after what comes next).
**This document does not begin T-029 or Sprint 5.** It answers the same four questions
`SPRINT_1_READINESS_ASSESSMENT.md` established as this project's standard readiness-assessment
shape, and nothing more.

---

## Is T-029 technically ready?

**Partially. The Reporting half is ready; the live-data half is not, and was never Sprint 4's
job to make ready.**

T-029's acceptance criterion is explicit: "a researcher creates a Project, collects real YouTube
data, runs topic *and* sentiment analysis, views and exports a Report citing raw snapshots — no
AI call anywhere in the path." Sprint 4 built and proved the last third of that chain
end-to-end: Report generation, finalization, and PDF export are real, tested, and reachable over
HTTP (T-024–T-028). What T-029 additionally requires and Sprint 4 did not attempt: **real**
(not fixture) YouTube collection (T-015's own live-network half remains environment-blocked, per
`SPRINT_0_COMPLETION_REPORT.md`/`BACKLOG.md`'s own repeated notes) and **real** sentiment/topic
analysis (T-022's `SentimentAnalysisAdapter`/T-019's `TopicsAnalysisAdapter` are both fully built
and tested, but neither is wired into the API — only a deliberately non-real demo engine is,
per T-028's own ADR-0004).

Concretely, the gap between "what Sprint 4 leaves working" and "what T-029 needs" is: (1) a real,
network-backed `YouTubePlatformProvider` reachable via API (T-015's live half), and (2) a real,
`AnalysisType`-catalog-aware `StartAnalysisRun` exposure wired to `TopicsAnalysisAdapter`/
`SentimentAnalysisAdapter` instead of `_DemoTopicAssignmentEngine` — which also means finally
resolving ARB-01's TD-03/TD-04 dispatch generalization, deferred at every opportunity since T-023.

## What blocks T-029?

Nothing architectural in the Reporting chain — that part is proven. Two real blockers, both
already-known, neither newly discovered by Sprint 4: this sandbox's own environment (no live
network egress for T-015's YouTube calls, already flagged since Sprint 1's own closure) and the
`AnalysisType`-dispatch generalization gap (ARB-01's TD-03/TD-04) that no task has yet been
authorized to resolve.

A secondary, T-029-specific consideration: T-029 is explicitly scoped as **Human sign-off**
(BACKLOG's own Role line) and a **one-time, live, performed-once verification** (its own
Verification line), not something this or any AI session can complete unattended even once the
technical blockers above are cleared.

## What should be completed before T-029?

Resolving TD-03/TD-04 — a real `StartAnalysisRun` exposure needs to select between
`TopicsAnalysisAdapter` and `SentimentAnalysisAdapter` by `analysis_type_id`, which today has no
mechanism to do (`StartAnalysisRunOrchestrator` takes one fixed engine at construction).
`_DemoTopicAssignmentEngine` (T-028) deliberately does not attempt this — it was scoped to prove
the Reporting screens, not to close this gap.

Resolving T-015's live-network verification — either by obtaining a real network-egress-capable
environment for this project, or by the operator running the already-documented manual
verification script T-015's own closure left ready.

Neither of these is Sprint 5 (EPIC-07, Identity Widening) work — both sit squarely inside
EPIC-04/EPIC-06's already-closed scope, reopened only to the extent T-029 needs them live rather
than fixture-backed.

## What should intentionally remain deferred?

Everything Sprint 4's own Completion Report already lists as deferred remains correctly deferred:
the Persistence Layer (every repository across all four sprints so far is still an in-memory
stand-in), authentication/authorization, publication-quality PDF layout, `jinja2`-based
templating, `api.middleware.idempotency`, `ListReportsForProject`/`GetExport`/`ListAnalysisRuns`
and every other still-unbuilt query. None of these block T-029's own acceptance criterion, and
pulling any forward now would be the same architecture-expansion-ahead-of-need this engagement
has avoided at every prior gate. Sprint 5 (EPIC-07, Identity Widening) itself remains correctly
sequenced after T-029, not before it — Roadmap §12's own self-critique ("port Collection first,
build real Identity once there's something to protect") is exactly why.

---

**Awaiting explicit operator authorization before T-029 or Sprint 5 planning begins.**
