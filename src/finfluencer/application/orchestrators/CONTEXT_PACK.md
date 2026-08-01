# Context Pack — Application Orchestrators

Full workflow: `IMPLEMENTATION_PLAYBOOK.md` Part B.2.

## Purpose

Application-layer command handlers, one per command (`PRODUCT_ARCHITECTURE.md` section 12.1
line 830, section 12.3's full mapping). Holds `CreateProjectOrchestrator` (T-009) and, as of
this pack, `StartCollectionRunOrchestrator` (T-011) — the first orchestrator that reaches all
the way down to an Infrastructure adapter and back, not just Domain + a repository stub.

## T-011 orchestration sequence (produced before implementation, per operator instruction)

```
Presentation                finfluencer.presentation.dto.collection.StartCollectionRunRequest /
                             CollectionRunAccepted (T-008). NOT imported by this orchestrator --
                             a future API route maps these DTOs onto/from the command and result
                             below. This pack documents the mapping's shape, not a dependency.
      |
      v  (dataset_id, idempotency_key)
Application     StartCollectionRunOrchestrator.execute(StartCollectionRunCommand)
                 1. collection_run_repository.get_by_idempotency_key(dataset_id, idempotency_key)
                    -> CollectionRun | None   [idempotent-dispatch check, Roadmap section 4/16.10:
                    "at-least-once dispatch, idempotent handlers"]
                 2. None found  -> construct a new CollectionRun(dataset_id) [Domain], persist via
                    collection_run_repository.add(run, idempotency_key=...), call run.start()
                    ("completed" found -> return its current snapshot immediately, no re-execution
                    "failed" found    -> call run.resume() (Domain's own failed->running
                                          transition), re-invoke Infrastructure with the SAME
                                          run_id, relying on CheckpointManager's own resumability
                                          "queued"/"running" found -> return the current snapshot
                                          as-is; this synchronous, single-process model has no
                                          path that leaves a run queued/running across calls, so
                                          this branch is a defensive no-op, not an expected path)
      |
      v  (Domain owns the state machine; Application only calls its public methods)
Domain           finfluencer.domain.entities.collection_run.CollectionRun
                 queued -> running (start()) -> completed (complete()) | failed (fail())
                 failed -> running (resume())
                 Immutable once completed (section 10.1 line 568) -- enforced by the entity
                 itself, not re-checked here.
      |
      v  collection_engine.run(run_id=str(collection_run.id))   [ICollectionEngine, Domain-owned
                                                                   Protocol, section 12.1 line 839
                                                                   pattern]
Infrastructure   finfluencer.infrastructure.collection.CollectionEngineAdapter (T-010)
    Adapter      _paths_for(run_id) derives this CollectionRun's own, exclusive
                 (checkpoint_root, cache_root, data_raw) triple (ADR-0002) -- using the
                 CollectionRun's own entity id as run_id is what makes constraint #7
                 ("every CollectionRun must own its own checkpoint_root exactly as defined by
                 ADR-0002") concretely true, not just asserted.
      |
      v  collect_channels -> collect_videos -> collect_comments -> collect_transcripts
Legacy           finfluencer.collect.{channels,videos,comments,transcripts} +
Collection       finfluencer.core.checkpoint.CheckpointManager -- unmodified, per constraint #6.
Engine
      |
      v  CollectionOutcome(run_id, stage_row_counts)  |  raises (mid-run failure)
Result           Application catches a raised exception, calls run.fail(), re-raises (does not
                 swallow -- matches the no-swallow discipline established in T-009/T-010).
                 On success: run.complete(), then StartCollectionRunResult(id, dataset_id,
                 status, stage_row_counts) is returned to the caller.
```

### IG-001 conformance, checked edge by edge

- **Application -> Domain**: `finfluencer.domain.entities.collection_run`,
  `finfluencer.domain.collection_engine`, `finfluencer.domain.repositories` only. Allowed
  (section 12.1 line 826). Mechanically checked by IG-001 for `domain`'s own inbound rules; not
  checked for `application`'s outbound rules by the current script, honored via a dedicated
  `ast`-based test, identical discipline to T-009/T-010.
- **Application -> Infrastructure**: NOT imported by source. The orchestrator's constructor
  takes `collection_engine: ICollectionEngine` and `collection_run_repository:
  ICollectionRunRepository` -- both Domain-defined Protocols (section 12.1 line 831: "Application
  and Domain jointly own these interfaces"). The concrete `CollectionEngineAdapter` is wired in
  only by test code (outside all six layers), never by `application/orchestrators/*.py` itself.
- **Application -> Presentation/API**: not imported, for the same reason as T-009 (section 12.1
  line 829, "never calls upward"). Verified by the same `ast`-based import-statement test pattern.
- **Domain -> anything**: `CollectionRun`/`Dataset`/`ICollectionEngine`/`ICollectionRunRepository`
  import nothing outside `finfluencer.domain.*` and the standard library (unchanged from T-007/
  T-010; not touched by T-011).
- **Infrastructure -> Application/Presentation/API**: unchanged from T-010 -- this task does not
  modify `collection_engine_adapter.py`.

## Guardrails that bind this module

- **IG-001**: see above.
- **BKG-001**: the idempotency-key lookup, the choice between create/resume/no-op-return, and
  the `start()`/`complete()`/`fail()` sequencing are the only business rules this task adds, and
  they live here (Application), not in `ICollectionRunRepository`'s (Persistence-facing)
  implementation or in `CollectionEngineAdapter` (Infrastructure). The repository's job is
  storage lookup by key; the orchestrator's job is deciding what that lookup result *means*.

## Known technical debt

- **Roster-wide run granularity vs. per-`Dataset` `CollectionRun`, still not fully reconciled.**
  T-010's CONTEXT_PACK.md deferred this to T-011. This task resolves it minimally: the
  orchestrator constructs `CollectionRun(dataset_id=command.dataset_id)` directly, without
  loading a full `Dataset` aggregate via a repository (no `IDatasetRepository` exists yet --
  not introduced here, since T-011 does not need to mutate a live `Dataset.collection_runs`
  collection to satisfy `CollectionRun`'s own "belongs to exactly one Dataset" invariant, which
  is already enforced by the constructor's required `dataset_id`). The full aggregate-consistent
  pattern (`ProjectRepository` loads a whole `Project` graph, mutation happens through
  `Dataset.add_collection_run()`, the whole aggregate is saved back) needs real Persistence and
  is deferred to whichever future task introduces it. Revisit trigger: first task that adds a
  concrete Persistence implementation.
- **Synchronous execution, not async dispatch.** `PRODUCT_ARCHITECTURE.md` section 11.2 states
  `StartCollectionRun`'s Sync/Async characteristic as **asynchronous**, returning a CollectionRun
  in `queued` state immediately while a job dispatcher runs collection out-of-band. No
  `IJobDispatcher` exists yet, so `StartCollectionRunOrchestrator.execute()` runs the whole
  pipeline inline and returns only once it reaches `completed`/`failed`. This is a deliberate,
  flagged Sprint 0 simplification (the same category of trim as T-009's missing Persistence and
  T-010's missing live network), not a silent redesign -- the eventual async version is a
  constructor/composition change (inject an `IJobDispatcher`, return immediately after
  `add()`+`start()`), not a rewrite of the state-machine logic itself. Revisit trigger: whichever
  future task introduces `IJobDispatcher`.
- **`ResumeCollectionRun` (section 12.3's separately-named orchestrator) is not implemented as
  its own class.** `CollectionRun.resume()` (Domain) is exercised here only as part of
  `StartCollectionRunOrchestrator`'s own idempotent-replay-of-a-failed-run path, not exposed as
  an independently callable command. A dedicated `ResumeCollectionRunOrchestrator` (for a client
  explicitly asking to retry a known-failed run, as opposed to an at-least-once duplicate of the
  original `StartCollectionRun` dispatch) remains a distinct, not-yet-scheduled task.

## Gotchas

- `get_by_idempotency_key` is keyed on `(dataset_id, idempotency_key)`, not `idempotency_key`
  alone -- two different Datasets are free to reuse the same idempotency key value without
  colliding.
- The fake/test `ICollectionRunRepository` implementation stores `idempotency_key` as
  repository-level bookkeeping metadata alongside the `CollectionRun`, not as a field on the
  `CollectionRun` entity itself -- the Domain entity's public shape is unchanged from T-007.
  This mirrors how a real column-based Persistence implementation would likely store it (an
  `idempotency_key` column in a `collection_runs` table) without needing the Domain class itself
  to expose that property.
