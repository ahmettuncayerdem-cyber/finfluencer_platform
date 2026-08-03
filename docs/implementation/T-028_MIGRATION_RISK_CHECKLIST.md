# T-028 Migration Risk Checklist — In-App Report Viewing Screen

Scope: first real Presentation/API exposure of the Reporting Service (T-024–T-027) and of
`StartAnalysisRun` (T-020, previously unexposed) — thin routes over existing, unmodified
orchestrators, plus one small new query orchestrator and one demo-only Analysis Engine
stand-in.

## Reuse boundary

- [x] `GenerateReportOrchestrator`, `FinalizeReportOrchestrator`, `ExportReportTableOrchestrator`,
      `GenerateExportOrchestrator` (T-025/T-026/T-027) are called with **zero code changes** —
      confirmed by re-reading all four modules in full before this task began.
- [x] `StartAnalysisRunOrchestrator` (T-020) is called with **zero code changes** — first real
      caller since its own test suite.
- [x] `CollectionEngineAdapter`/`FixtureCollectionProvider` (T-010), `TopicsAnalysisAdapter`
      (T-019) are **not touched and not wrapped** by the new demo Analysis Engine — see Domain
      Model boundary below for why a separate, honestly-labeled stand-in was built instead.
- [x] `bootstrap.py`'s existing `_InMemoryProjectRepository`/`_InMemoryCollectionRunRepository`
      pattern and `_serve_dev_ui()`/`web/index.html` structure are extended, not restructured.

## Domain Model boundary

- [x] No new Domain entity, no modification to any existing one (`Report`, `Export`,
      `InterpretationRecord`, `AnalysisRun` all read/called exactly as T-024/T-018 left them).
- [x] `GetReportOrchestrator` (new) adds no business logic — a single `IReportRepository
      .get_by_id()` call, wrapped only because API must not depend on a Domain-owned repository
      interface directly (section 12.1's Application/Domain-owns-the-interfaces rule).
- [x] **New demo `IAnalysisEngine` implementation is intentionally NOT `TopicsAnalysisAdapter`.**
      Real BERTopic model loading is heavy, network/model-availability-dependent, and T-019's own
      test suite already establishes that even its own tests inject a fake `runner_factory`/
      `model_loader` rather than load a real model. The demo engine is independent,
      dependency-free (only `pandas`/`finfluencer.utils.io`), reads real `comments.parquet`,
      writes a real `topics.parquet` in the exact shape `MasterTableExportAdapter`'s own tests
      already fixture (`comment_id`, `configuration`, `topic_id`, `topic_label`, `topic_prob`),
      and is clearly labeled in its own docstring as a Sprint-0/demo stand-in for `IAnalysisEngine`
      — the same class of decision `FixtureCollectionProvider` already established for
      `ICollectionEngine`, applied here for the first time to `IAnalysisEngine`.
- [x] This does **not** resolve TD-03/TD-04 (ARB-01's flagged `AnalysisType`-dispatch
      generalization) — the demo engine is wired directly, by construction, not through any new
      dispatch/registry mechanism. A real, multi-`AnalysisType`-aware exposure of
      `StartAnalysisRun` remains future work.

## Layering (IG-001 / BKG-001)

- [x] `api/routes/reporting.py`, `api/routes/analysis.py` import only `finfluencer.application.*`,
      `finfluencer.presentation.dto.*`, `finfluencer.api.deps` — no `finfluencer.infrastructure`,
      no `finfluencer.domain` (matching the existing `api/routes/collection.py`/`identity.py`
      precedent, verified by the same ast-based check `test_architectural_conformance.py`
      already applies).
- [x] `application/orchestrators/get_report.py` imports no `finfluencer.infrastructure.*`, no
      `finfluencer.presentation.*`, no `finfluencer.api.*` — same discipline as every prior
      orchestrator.
- [x] The one new route-local logic (path/body id mismatch checks, if any) is request-shape
      validation, not a business rule — same reasoning `collection.py`'s existing check already
      documents.
- [x] `bootstrap.py` remains the sole composition root touching all layers for wiring only — no
      new business logic (no `if` branching on domain state) added there beyond object
      construction and route registration, same constraint the module's own docstring already
      states.

## Idempotency / side effects

- [x] `POST .../reports` (GenerateReport): idempotency behavior unchanged from T-025's own
      orchestrator (create-or-cite, no new dedup logic added at the route).
- [x] `POST .../reports/{id}/finalize`: idempotent no-op on a second call, per T-027's own
      `FinalizeReportOrchestrator` (unchanged).
- [x] `POST .../reports/{id}/exports` (PDF) and `GET .../reports/{id}/table` (CSV): run
      synchronously and return file bytes directly in the response body — no separate download
      endpoint, no job queue, same "no `IJobDispatcher` exists yet" simplification already
      recorded for `StartCollectionRun`. PDF export writes to a **deterministic** path
      (`base_root/exports/{report_id}-v{version}.pdf`, keyed off the same `(report_id, version,
      format)` tuple `GenerateExportOrchestrator`'s own idempotency check uses) so a repeat call
      that hits the idempotent-replay branch (no re-render) still has real bytes on disk to
      serve.
- [x] `POST /collection-runs/{id}/analysis-runs`: idempotency behavior unchanged from T-020's own
      orchestrator (unmodified).

## Cross-project isolation

- [x] Every new route requiring `project_id` scoping (`reports`, `reports/{id}/*`) passes it
      through to the existing, already-scoped orchestrator calls
      (`IReportRepository.get_by_id(project_id, report_id)` etc.) — no new isolation logic
      invented, none needed.

## REST derivation fidelity

- [x] `POST /collection-runs/{id}/analysis-runs` matches `PRODUCT_ARCHITECTURE.md` §11.3 line 779
      **exactly** — not invented, the architecture's own representative endpoint.
- [x] `POST /projects/{project_id}/reports/{report_id}/exports` matches §11.3 line 782's
      `POST /reports/{id}/exports` ← `GenerateExport`, with the same parent-scoping-id-in-path
      convention `StartCollectionRun`'s own already-implemented route already established
      (`/datasets/{dataset_id}/collection-runs`) — reconciling the abstract table with concrete
      precedent, documented in the route module's own docstring.
- [x] `GET .../reports/{id}/table` (CSV/table export) has **no** §11.2 command name — table
      export was never a formal Reporting Service command (§8.4's separate "manuscript-ready
      table objects" capability, T-026's own finding). Route name chosen to reflect that: a
      resource read (`GET .../table`), not a command-derived `POST`.

## What this checklist deliberately does not cover

- Authentication/authorization on any new route — same Sprint-0-wide operator constraint every
  prior route inherits.
- A production-grade `StartAnalysisRun` exposure supporting every `AnalysisType` — the demo
  engine wired here is explicitly NOT that; a real exposure remains a future, separate task.
- SCR-RPT-01 (Reports List) — requires a `ListReportsForProject` query and a new repository
  method neither exists yet; deliberately deferred, same "build only what the demonstrated flow
  needs" discipline T-012 already established for `ListDatasets`/`GetCollectionRun`.
- Real-scale performance of any new route — not exercised in this sandbox.
