# ADR 0002 — Collection Run Checkpoint-Root Partitioning

**Date:** 2026-08-01
**Status:** Accepted — 2026-08-01 (BACKLOG.md T-010; Claude drafted, human-approved by proceeding
with T-010 under the operator's own instruction that this discipline be "explicit in the
adapter, not assumed"). Resolves `IMPLEMENTATION_ROADMAP.md` §7 Risk R-1 for the Collection
Engine specifically — R-1 itself is not closed by this ADR (it remains a standing constraint on
`core/checkpoint.py`), only addressed for this one adapter.
**Drafted by:** Claude, grounded in direct inspection of `core/checkpoint.py` and
`IMPLEMENTATION_ROADMAP.md` §7 Risk R-1, not a from-scratch design.

## Context

`core/checkpoint.py`'s `CheckpointManager` documents itself as assuming a single writer per
`checkpoint_root`: "running two `finfluencer run` invocations concurrently against the same
checkpoint directory is unsupported and can race." `PRODUCT_ARCHITECTURE.md` §16.9/§16.21 assume
a horizontally-scaled Worker Tier. `IMPLEMENTATION_ROADMAP.md` §7 Risk R-1 already named the
resolution shape without implementing it: "no two `CollectionRun`/`AnalysisRun` instances need
to share a `checkpoint_root` — but the partitioning discipline (one root per run, never shared)
must be enforced deliberately in the Collection/Analysis orchestrator wrappers, not assumed to
fall out automatically. Owner: whoever wraps Collection Engine first (Phase 1)." BACKLOG.md
T-010 is that task.

## Decision

`CollectionEngineAdapter` (`src/finfluencer/infrastructure/collection/collection_engine_adapter.py`)
takes one `base_root: Path` at construction and derives a dedicated
`(checkpoint_root, cache_root, data_raw)` triple per `run_id` via `_paths_for(run_id)`:

```
base_root/<run_id>/checkpoints/
base_root/<run_id>/cache/
base_root/<run_id>/data_raw/
```

Two distinct `run_id`s can never collide, structurally — there is no code path in this class
that lets two different `run_id`s resolve to the same `checkpoint_root`. Calling `run()` again
with the *same* `run_id` is the resume path, and correctly reuses the same root — this is
resumability, not a race, since `core/checkpoint.py`'s own single-writer assumption is only
violated by *concurrent* writers to one root, not sequential re-invocation.

## Reasoning

**Partition at the adapter, not the caller.** An alternative would be to accept an
already-computed `checkpoint_root` from the caller (a future orchestrator) and trust it to pass
a distinct one per run. Rejected: that would make the partitioning discipline something every
future caller must remember to get right, rather than something structurally guaranteed by the
one class that actually touches `CheckpointManager`. Risk R-1 itself says this discipline "must
be enforced deliberately... not assumed to fall out automatically" — enforcing it inside the
adapter, where it cannot be bypassed by a forgetful caller, is the more literal reading of that
sentence.

**`run_id` as the partition key, not a `CollectionRun` entity reference.** `CollectionRun`
(`PRODUCT_ARCHITECTURE.md` §10.1) does not exist in this adapter's dependency graph — Domain
entities are not imported here (see this module's Context Pack). `run_id` is deliberately just a
caller-supplied string; a future orchestrator (T-011) is expected to pass a `CollectionRun.id`
once that entity is wired into this flow, but this ADR does not require that mapping to exist
yet — see the Context Pack's "Known technical debt" for the deferred roster-vs-Dataset
granularity question this does not resolve.

**Data outputs (`data_raw/`) partitioned identically, not just checkpoints.** Not strictly
required by Risk R-1's own text (which only names `checkpoint_root`), but the same race the
Risk describes — two runs writing to the same location — applies equally to `channels.parquet`
etc. Leaving `data_raw` shared while partitioning only checkpoints would have solved the letter
of R-1 while leaving an equivalent, undocumented race in the adjacent output path. Extending the
same discipline to `data_raw` is a direct, narrow consequence of R-1's own reasoning, not a new,
separate decision.

## Consequences

- Every `CollectionEngineAdapter.run(run_id)` call is safe to invoke concurrently with a
  *different* `run_id` against the same `base_root` — proven directly by
  `tests/unit/test_infrastructure/test_collection/test_collection_engine_adapter.py::
  test_different_run_ids_get_isolated_checkpoint_roots`.
- Concurrent calls with the *same* `run_id` remain exactly as unsafe as `core/checkpoint.py`
  itself documents — this ADR does not add locking or otherwise change that file's own
  concurrency contract, which is out of scope for a "wrapper, not rewrite" task.
- `base_root`'s own lifecycle (retention, cleanup of completed runs) is not addressed here —
  flagged as an open item for whichever future task owns Persistence/storage retention policy,
  consistent with `PRODUCT_ARCHITECTURE.md` §16.12's similarly-flagged artifact-retention gap.
