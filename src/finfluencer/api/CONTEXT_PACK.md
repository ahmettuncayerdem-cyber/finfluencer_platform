# Context Pack — API Layer

Full workflow: `IMPLEMENTATION_PLAYBOOK.md` Part B.2.

## Purpose

The first implementation of `api.routes.*` (`PRODUCT_ARCHITECTURE.md` section 12.1 line 822):
HTTP routing per section 11.3's endpoint derivation for the two Walking Skeleton operations
(`CreateProject`, `StartCollectionRun`). Exists so `web/index.html` (BACKLOG.md T-012) has a real
API Gateway to call, satisfying FG-001 ("frontend calls only the API Gateway, never
Infrastructure directly").

## Domain entities and invariants owned or touched

None directly. Routes translate wire DTOs (`presentation.dto.*`, T-008) to/from Application
commands/results (T-009, T-011) and back -- they never construct or mutate a Domain entity
themselves. All Domain invariants (empty-name rejection, CollectionRun state transitions) are
enforced exactly where T-007/T-009/T-011 already put them; this layer adds no new checks.

## API Contract operations implemented

- `CreateProject` (section 11.2 line 657) -> `POST /projects` (section 11.3 line 776, Sync).
- `StartCollectionRun` (section 11.2 line 683) -> `POST /datasets/{dataset_id}/collection-runs`
  (section 11.3 line 778) -- response shape deliberately deviates from the literal contract; see
  `api/routes/collection.py`'s own docstring and BACKLOG.md T-012's Scope Decision 5.

Not implemented: `CreateTenant`, `InviteMember`, `AssignRole`, `ArchiveProject` (Identity
Service); `CreateDataset`, `ResumeCollectionRun`, `GetDataset`, `ListDatasets`,
`ListCollectionRunsForDataset`, `GetCollectionRun` (Collection Service) -- none needed by the
Walking Skeleton's two operations.

## Guardrails that bind this module

- **IG-001**: `scripts/check_layer_dependencies.py` mechanically enforces `api` -> not importing
  `infrastructure`/`persistence`. It does NOT mechanically enforce `api` -> not importing
  `domain` (section 12.1 line 821's "Forbidden dependencies: Domain directly" half is absent
  from the script's own `FORBIDDEN_IMPORTS` rule set — see the script's docstring). Honored here
  via `tests/unit/test_api/test_architectural_conformance.py`'s `ast`-based checks, the same
  mechanically-uncovered-edge pattern already established for Application (T-009) and
  Infrastructure (T-010).
- **BKG-001**: no business logic lives in `api/routes/*.py` — the one piece of route-local logic
  (the path/body `dataset_id` mismatch check in `collection.py`) is request-shape validation, not
  a business rule about `CollectionRun`/`Dataset` themselves.
- **FG-001**: this layer's entire reason to exist for T-012 — `web/index.html` calls only these
  routes, never Infrastructure.

## Integration decisions

- **`bootstrap.py` (top-level, outside `api/`) is the composition root**, not this package. No
  route module constructs a concrete `ICollectionEngine`/`ICollectionRunRepository`/
  `IProjectRepository` implementation — each route only calls `Depends(...)` against
  `api/deps.py`, which reads an already-constructed orchestrator off `Request.app.state`. See
  `bootstrap.py`'s own module docstring for the full reasoning on why a composition root outside
  all six layers is required, not optional, and why it is not a new architectural layer.
- **`StartCollectionRun`'s response is `GetCollectionRunResponse`, not `CollectionRunAccepted`.**
  Deliberate, not an oversight — see `api/routes/collection.py`'s own docstring.

## Known technical debt

- **`api.middleware.idempotency` (section 12.1 line 819) does not exist.** `CreateProject`
  accepts an `idempotency_key` in its request body (T-008's own DTO shape) but nothing
  deduplicates a repeated key yet — two calls with the same key create two Projects. Proven, not
  hidden, by `test_routes_identity.py::test_two_create_project_calls_produce_distinct_projects`.
  `StartCollectionRun` does not have this gap: T-011's own orchestrator already performs
  idempotent dispatch internally, independent of any API-layer middleware. Revisit trigger:
  whichever future task adds real, cross-request idempotency-key deduplication (needs durable
  storage — Persistence Layer, not yet built).
- **No authentication or authorization on any route** — operator constraint for T-012 ("No
  authentication," "No authorization"), consistent with every prior Sprint 0 task's identical
  scope trim.
- **Synchronous `StartCollectionRun`, not the section 11.2-stated asynchronous contract** —
  inherited directly from `StartCollectionRunOrchestrator` (T-011); see that module's own
  Context Pack for the full reasoning. This layer's only new contribution to that gap is the
  response-shape consequence documented above (Integration decisions).

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
