# T-020 Architecture & Execution Readiness Review — `StartAnalysisRun` orchestrator

## 1. Reused from T-011 vs. must differ

**Reused:** the overall idempotent-dispatch shape (look up by key -> branch on status -> create/replay/re-run), delegating actual work to a Domain-owned Protocol abstractly (`IAnalysisEngine` instead of `ICollectionEngine`), calling only Domain methods to transition state (never re-implementing `start`/`complete`/`fail`), never importing Infrastructure/Presentation/API, and the identical `ast`-based conformance test technique.

**Must differ:** (a) no `resume()` call exists or is invoked on a `FAILED` run — §10.1 line 577 / T-018's own entity: a duplicate dispatch onto a `FAILED` `AnalysisRun` constructs a **brand-new** `AnalysisRun` instead, pinned to the same `(collection_run_id, analysis_type_id, analysis_type_version)` the caller asked for again. (b) the repository key tuple is `(project_id, idempotency_key)`, not `(dataset_id, idempotency_key)` -- `AnalysisRun` belongs to a `Project`, not a `Dataset` (§10.1 line 576). (c) `AnalysisRun`'s constructor needs three pinning fields Collection doesn't have (`collection_run_id`, `analysis_type_id`, `analysis_type_version`), all required, all caller-supplied in the command. (d) `IAnalysisRunRepository.add()` may legitimately be called more than once for the same idempotency key over a run's retry lifetime (each `FAILED` retry adds a new `AnalysisRun` and re-points the key) -- `ICollectionRunRepository.add()` is only ever called once per key, since Collection resumes in place.

## 2. Domain contracts participating

`AnalysisRun`/`AnalysisRunStatus` (T-018), `IAnalysisEngine`/`AnalysisOutcome` (T-019). New: `IAnalysisRunRepository` (this task adds it, mirroring `ICollectionRunRepository`'s existing shape and minimal-surface discipline). `AnalysisType` itself is **not** loaded or validated here -- the command carries `analysis_type_id`/`analysis_type_version` directly; no catalog/repository for `AnalysisType` exists yet (T-018's own scoping), so this orchestrator trusts the caller's pin, same permissiveness T-011 already has for `dataset_id`.

## 3. Lifecycle transitions

`queued -> running -> completed | failed` via `start()`/`complete()`/`fail()`. **Resume is intentionally absent**, confirmed directly against `PRODUCT_ARCHITECTURE.md` §10.1 line 577 ("re-run creates a new `AnalysisRun`, never mutates an existing one") and T-018's own entity (no `resume()` method exists to call).

## 4. Idempotency

`execute()` must be safe to call twice with the same key. Key = `(project_id, idempotency_key)`. On retry: `COMPLETED` -> return the existing result, no re-analysis (matches T-011). `FAILED` -> construct and dispatch a **new** `AnalysisRun`, re-pointing the repository's key mapping (differs from T-011's in-place resume). `QUEUED`/`RUNNING` -> defensive, non-mutating fallback, identical reasoning to T-011 (unreachable in this synchronous, single-process orchestrator; kept for a future concurrent implementation).

## 5. Assumptions, flagged explicitly

- `collection_run_id` is trusted as given, not verified against a real, `COMPLETED` `CollectionRun` (no `ICollectionRunRepository` lookup here) -- mirrors T-011's own precedent of trusting `dataset_id`. A genuine pinning-validity check is T-021's explicit job ("an `AnalysisRun` cannot be created without a valid `CollectionRun` reference"), not this task's.
- **Retry-after-failure will not hit T-019's BERTopic model cache even if the underlying corpus/config is unchanged.** Each retry gets a fresh `AnalysisRun.id`, and `TopicsAnalysisAdapter` partitions both `checkpoint_root` and `cache_root` per `analysis_run_id` (mirroring Collection's Risk-R1 discipline, already closed in T-019). This is a correctness-neutral performance characteristic, not a defect -- flagged here, not fixed, to avoid speculative optimization beyond this task's scope and to avoid reopening the closed T-019 adapter without a demonstrated need.
- The fake `IAnalysisRunRepository` test double must support being called with `add()` more than once for the same key (superseding the mapping) -- a genuine behavioral difference from `FakeCollectionRunRepository`, not an oversight if the two don't look identical.

## 6. BKG-001 / IG-001 compliance

BKG-001: the only business logic this task adds is the create/replay/retry decision, and it stays in Application; `AnalysisRun`'s own state machine is called, never reimplemented; `TopicsAnalysisAdapter` is invoked only through `IAnalysisEngine`, abstractly. IG-001: the new orchestrator module will import `finfluencer.domain.*` only -- verified by the same `ast`-based test T-011 already uses (no `presentation`/`api`/`infrastructure`/`topics` import).

## 7. Contradiction check

No contradiction found with `PRODUCT_ARCHITECTURE.md`, `IMPLEMENTATION_ROADMAP.md`, `IMPLEMENTATION_PLAYBOOK.md`, any ADR, or `BACKLOG.md`. Proceeding to implementation.
