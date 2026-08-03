# Context Pack — API Layer

Full workflow: `IMPLEMENTATION_PLAYBOOK.md` Part B.2.

## Purpose

The first implementation of `api.routes.*` (`PRODUCT_ARCHITECTURE.md` section 12.1 line 822):
HTTP routing per section 11.3's endpoint derivation. BACKLOG.md T-012 scope: the two Walking
Skeleton operations (`CreateProject`, `StartCollectionRun`). BACKLOG.md T-028 scope: the first
Analysis Service operation (`StartAnalysisRun`) and the first Reporting Service operations
(`GenerateReport`/`GetReport`/`FinalizeReport`/`GenerateExport`, plus table export). Exists so
`web/index.html` has a real API Gateway to call, satisfying FG-001 ("frontend calls only the API
Gateway, never Infrastructure directly").

## Domain entities and invariants owned or touched

None directly. Routes translate wire DTOs (`presentation.dto.*`) to/from Application
commands/results and back -- they never construct or mutate a Domain entity themselves. All
Domain invariants (empty-name rejection, CollectionRun/AnalysisRun/Report state transitions) are
enforced exactly where the owning task already put them; this layer adds no new checks.

## API Contract operations implemented

- `CreateProject` (section 11.2 line 657) -> `POST /projects` (section 11.3 line 776, Sync).
- `StartCollectionRun` (section 11.2 line 683) -> `POST /datasets/{dataset_id}/collection-runs`
  (section 11.3 line 778) -- response shape deliberately deviates from the literal contract; see
  `api/routes/collection.py`'s own docstring and BACKLOG.md T-012's Scope Decision 5.
- `StartAnalysisRun` (section 11.2 line 696) -> `POST /collection-runs/{id}/analysis-runs`
  (section 11.3 line 779, matched exactly) -- BACKLOG.md T-028. Same synchronous-response
  deviation as `StartCollectionRun`. Wired in `bootstrap.py` to a demo-only `IAnalysisEngine`,
  not T-019's real `TopicsAnalysisAdapter` -- see `bootstrap.py`'s own docstring and
  `T-028_MIGRATION_RISK_CHECKLIST.md`.
- `GenerateReport` (`CreateReport`+`AddCitation` folded, section 11.2 line 722) ->
  `POST /projects/{project_id}/reports` -- BACKLOG.md T-028, reuses T-025's
  `GenerateReportOrchestrator` unmodified.
- `GetReport` (section 11.2 line 723) -> `GET /projects/{project_id}/reports/{report_id}` --
  BACKLOG.md T-028, first caller of the new `GetReportOrchestrator`.
- `FinalizeReport` (section 11.2 line 722) ->
  `POST /projects/{project_id}/reports/{report_id}/finalize` -- BACKLOG.md T-028, reuses T-027's
  `FinalizeReportOrchestrator` unmodified.
- `GenerateExport` (section 11.2 line 722) ->
  `POST /projects/{project_id}/reports/{report_id}/exports` (section 11.3 line 782's
  `POST /reports/{id}/exports`, path reconciled with `StartCollectionRun`'s own
  parent-scoping-id-in-path precedent) -- BACKLOG.md T-028, reuses T-027's
  `GenerateExportOrchestrator` unmodified. Returns PDF bytes directly, no JSON DTO.
- Table export (T-026's own capability, no section 11.2 command name) ->
  `GET /projects/{project_id}/reports/{report_id}/table` -- BACKLOG.md T-028, reuses T-026's
  `ExportReportTableOrchestrator` unmodified. Returns CSV bytes directly, no JSON DTO.

Not implemented: `CreateTenant`, `InviteMember`, `AssignRole`, `ArchiveProject` (Identity
Service); `CreateDataset`, `ResumeCollectionRun`, `GetDataset`, `ListDatasets`,
`ListCollectionRunsForDataset`, `GetCollectionRun` (Collection Service); `ListAnalysisTypes`,
`GetAnalysisRunResult`, `ListAnalysisRuns` (Analysis Service); `CreateRawSnapshot`,
`AddCitation` as its own standalone command, `ListReportsForProject`, `GetExport`
(Reporting Service); the full AI Interpretation Service; all of Identity & Access beyond
`CreateProject`. None needed by the flows demonstrated so far.

## Guardrails that bind this module

- **IG-001**: `scripts/check_layer_dependencies.py` mechanically enforces `api` -> not importing
  `infrastructure`/`persistence`. It does NOT mechanically enforce `api` -> not importing
  `domain` (section 12.1 line 821's "Forbidden dependencies: Domain directly" half is absent
  from the script's own `FORBIDDEN_IMPORTS` rule set — see the script's docstring). Honored here
  via `tests/unit/test_api/test_architectural_conformance.py`'s `ast`-based checks, the same
  mechanically-uncovered-edge pattern already established for Application (T-009) and
  Infrastructure (T-010). T-028's routes reuse `EntityId`'s own `NewType(..., uuid.UUID)`
  transparency to satisfy Command types with plain `uuid.UUID` values (Pydantic's own field
  type) without importing `finfluencer.domain` at all.
- **BKG-001**: no business logic lives in `api/routes/*.py` — the path/body id-mismatch checks
  (`collection.py`'s `dataset_id`, `analysis.py`'s `collection_run_id`) are request-shape
  validation, not business rules. `reporting.py`'s deterministic export file paths are transport
  plumbing, not a business rule either.
- **FG-001**: this layer's entire reason to exist — `web/index.html` calls only these routes,
  never Infrastructure.
- **FG-002**: `reporting.py`'s export routes return exactly the bytes the real
  `GenerateExportOrchestrator`/`ExportReportTableOrchestrator` produced — nothing rendered or
  computed client-side.

## Integration decisions

- **`bootstrap.py` (top-level, outside `api/`) is the composition root**, not this package. No
  route module constructs a concrete `ICollectionEngine`/`ICollectionRunRepository`/
  `IProjectRepository`/`IAnalysisEngine`/`IPdfRenderer`/etc. implementation — each route only
  calls `Depends(...)` against `api/deps.py`, which reads an already-constructed orchestrator
  (or, for `reporting.py`'s export routes, a request-scoped `Path`) off `Request.app.state`. See
  `bootstrap.py`'s own module docstring for the full reasoning on why a composition root outside
  all six layers is required, not optional, and why it is not a new architectural layer.
- **`StartCollectionRun`'s response is `GetCollectionRunResponse`, not `CollectionRunAccepted`.**
  Deliberate, not an oversight — see `api/routes/collection.py`'s own docstring.
  `StartAnalysisRun`'s response (`AnalysisRunStarted`) makes the identical, symmetric choice for
  the same reason (T-028).
- **`GenerateExport`/table export return raw file bytes, not a JSON DTO pointing at a separate
  download endpoint.** No `IJobDispatcher` exists (same gap `StartCollectionRun` already
  documents), so both orchestrators run synchronously inside the route handler. See
  `api/routes/reporting.py`'s own docstring for the deterministic-output-path reasoning this
  requires for idempotent replay to still return real bytes.
- **`api/routes/reporting.py` maps every caught `ValueError` to HTTP 404**, regardless of
  whether the underlying cause is "resource not found" or "invalid state for this operation"
  (e.g. exporting a non-finalized Report). A known, minor imprecision — none of T-025/T-026/
  T-027's orchestrators raise a distinguishable exception type for the two cases; introducing
  one was judged out of T-028's own scope. Flagged, not silently accepted as correct.

## Known technical debt

- **`api.middleware.idempotency` (section 12.1 line 819) does not exist.** `CreateProject`
  accepts an `idempotency_key` in its request body (T-008's own DTO shape) but nothing
  deduplicates a repeated key yet — two calls with the same key create two Projects. Proven, not
  hidden, by `test_routes_identity.py::test_two_create_project_calls_produce_distinct_projects`.
  `StartCollectionRun`/`StartAnalysisRun` do not have this gap: their own orchestrators already
  perform idempotent dispatch internally, independent of any API-layer middleware. Revisit
  trigger: whichever future task adds real, cross-request idempotency-key deduplication (needs
  durable storage — Persistence Layer, not yet built).
- **No authentication or authorization on any route** — operator constraint for T-012 ("No
  authentication," "No authorization"), consistent with every prior Sprint 0 task's identical
  scope trim, including T-028.
- **Synchronous `StartCollectionRun`/`StartAnalysisRun`/`GenerateExport`/table export, not the
  section 11.2-stated asynchronous contract** — inherited directly from the wrapped
  orchestrators; see each module's own Context Pack for the full reasoning.
- **`_DemoTopicAssignmentEngine` (`bootstrap.py`, T-028) is not a real `AnalysisType`
  implementation.** It produces topics-shaped output only, via a deterministic, non-ML rule —
  see `bootstrap.py`'s own docstring and `T-028_MIGRATION_RISK_CHECKLIST.md`. A `Report` built
  entirely from this demo page cannot be table-exported (needs both a topics- and a
  sentiment-shaped `AnalysisRun`) — a documented, expected 422, not a bug. A real,
  multi-`AnalysisType`-aware exposure of `StartAnalysisRun` (resolving ARB-01's TD-03/TD-04)
  remains a separate, future task.

## Gotchas

- `bootstrap.create_app()` builds a **fresh** temp directory for `CollectionEngineAdapter`'s
  `base_root` on every call (including every test's `TestClient(create_app())`) — collection
  state does not persist across `create_app()` calls, by design (no Persistence Layer yet).
- The in-memory repository stand-ins (`_InMemoryProjectRepository`,
  `_InMemoryCollectionRunRepository`, defined in `bootstrap.py`) are per-`app` instances, not
  module-level singletons — two `create_app()` calls never share state. Real multi-process
  deployment (T-014) means each worker process gets its own, independent in-memory store; this
  is a direct, load-bearing consequence of "No Persistence implementation" and is exactly why a
  real Persistence Layer becomes necessary the moment more than one worker process, or process
  restarts, need to see the same data.
