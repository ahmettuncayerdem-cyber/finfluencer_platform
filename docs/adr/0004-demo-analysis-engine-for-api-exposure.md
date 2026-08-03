# ADR 0004 — Demo `IAnalysisEngine` Stand-In for `StartAnalysisRun`'s First API Exposure

**Date:** 2026-08-03
**Status:** Accepted — 2026-08-03 (BACKLOG.md T-028; Claude drafted, human-approved by proceeding
with T-028 under the operator's own Task Authorization). No prior ADR addresses how
`StartAnalysisRun` (T-020) should be exposed via API — this is the first task in that scope.
**Drafted by:** Claude, grounded in direct inspection of `StartAnalysisRunOrchestrator` (T-020),
`TopicsAnalysisAdapter` (T-019, and its own test suite's fake-runner-factory precedent), and
`PRODUCT_ARCHITECTURE.md` §11.3 line 779's own representative endpoint for `StartAnalysisRun`.

## Context

T-028 ("Build in-app Report viewing screen") requires a real, backend-computed `AnalysisRun` for
`GenerateReport` to cite — without one, `GenerateReportOrchestrator` (T-025) has nothing to
operate on and BACKLOG.md's own T-028 Verification line ("manual click-through") is unsatisfiable.
No task before T-028 had ever exposed `StartAnalysisRun` (T-020) via API — `bootstrap.py` wired
only `CreateProject`/`StartCollectionRun` before this task.

Two real obstacles rule out simply wiring the real `TopicsAnalysisAdapter` (T-019) behind a new
route: (1) its default `model_loader` loads an actual BERTopic model — heavy, and
network/model-availability-dependent in a way this sandbox cannot reliably guarantee; T-019's own
test suite already establishes the precedent that even its own tests inject a fake
`runner_factory`/`model_loader` rather than load a real one. (2) `StartAnalysisRunOrchestrator`
takes a single, fixed `analysis_engine: IAnalysisEngine` at construction — there is no
`AnalysisType`-keyed dispatch mechanism (ARB-01 flagged this generalization gap as TD-03/TD-04,
explicitly non-blocking and deferred). Resolving that dispatch question was judged out of T-028's
own scope ("Presentation-layer half of Reporting," not a plugin-architecture generalization task).

## Decision

Add `_DemoTopicAssignmentEngine` (`bootstrap.py`, not a new Infrastructure adapter file — see
Reasoning) implementing `IAnalysisEngine` (`domain/analysis_engine.py`) directly, independent of
`TopicsAnalysisAdapter`. It reads a real `comments.parquet` a real `CollectionRun` already
produced and writes a real `topics.parquet`, using a deterministic, non-ML rule
(`topic_id = hash(comment_id) % 3`) — no BERTopic, no embeddings, no external model. Wired as the
single `analysis_engine` behind a new, spec-exact route:
`POST /collection-runs/{id}/analysis-runs` (§11.3 line 779, matched exactly, not invented).

## Reasoning

**Why not wrap `TopicsAnalysisAdapter` with fakes injected, the way its own tests do.** Doing so
would require assembling `TopicsAnalysisAdapter`'s full dependency set at `bootstrap.py` startup
(a `TopicsConfig`, per-comment embedding `.npy` files, a `CheckpointManager`) purely to reach a
fake `runner_factory`/`model_loader` underneath — more moving parts, for a result that is still
not "real" topic modeling, with no offsetting benefit over a direct, independent implementation.

**Why a new, independent class instead of a new `infrastructure/analysis/` adapter file.**
`FixtureCollectionProvider` (T-010) is a real, honest, reusable Infrastructure implementation of
`ICollectionProvider` — it genuinely substitutes for live network access, and other tasks are
expected to use it. `_DemoTopicAssignmentEngine` is different in kind: it does not substitute for
BERTopic in any general sense (its topic assignment is not analytically meaningful), exists
solely so this one task's Reports screen has something real to demonstrate against, and should
not be mistaken for a reusable Infrastructure component by a future task browsing
`infrastructure/analysis/`. Keeping it in `bootstrap.py`, alongside the already-established
in-memory repository stand-ins (also demo/Sprint-0-only, also defined there), signals this
distinction structurally, not just in a docstring.

**Why the route path is real, even though the engine behind it is not.** §11.3 line 779 already
names `POST /collection-runs/{id}/analysis-runs` as the derived endpoint for `StartAnalysisRun` —
building it now, reusing `StartAnalysisRunOrchestrator` (T-020) completely unmodified, is not
speculative; only bootstrap.py's choice of which concrete `IAnalysisEngine` to inject is a
Sprint-0-scoped simplification, invisible to the route module itself (the same separation
`api/routes/collection.py` already has from `FixtureCollectionProvider` vs. a future live
provider).

**Why this does not resolve TD-03/TD-04.** The demo engine is injected directly into one
`StartAnalysisRunOrchestrator` instance — there is still no mechanism resolving an
`analysis_type_id` to a concrete engine. A real, multi-`AnalysisType`-aware exposure remains
future work; this ADR explicitly does not claim to have built it.

## Consequences

- `POST /collection-runs/{id}/analysis-runs` is real, tested, and produces genuinely
  backend-computed `AnalysisRun`s a human can drive `GenerateReport`/`FinalizeReport`/
  `GenerateExport` against through `web/index.html`.
- Every `AnalysisRun` created through this route produces topics-shaped output only. A `Report`
  built entirely from it cannot be table-exported via `ExportReportTableOrchestrator`
  (`MasterTableExportAdapter` needs both a topics- and a sentiment-shaped `AnalysisRun`) — a
  documented, expected `FileNotFoundError`/HTTP 422, not a defect (T-026's own already-documented
  limitation, now reachable over HTTP for the first time).
- A future task building a real, `AnalysisType`-catalog-aware `StartAnalysisRun` exposure
  (resolving TD-03/TD-04) will replace `_DemoTopicAssignmentEngine`'s wiring in `bootstrap.py`
  with real engine(s) selected by `analysis_type_id` — no route or orchestrator code changes,
  since `api/routes/analysis.py` and `StartAnalysisRunOrchestrator` are already engine-agnostic.
