# ADR-Sprint2-01: `AnalysisJob` Composes Over `run_reporting_pipeline`, Never Reimplements It

**Status:** Accepted (implemented, Sprint 2.6)
**Date:** decided during Sprint 2 planning, ahead of Sprint 2.6; persisted as a
file during Sprint 2.7A (Documentation milestone) — this decision was made
and acted on in chat across the engagement but had never been written down
until now.
**Related Sprint 2 steps:** 2.1 (`run_reporting_pipeline`, the engine this
ADR keeps canonical), 2.3 (`reporting/main.py`, the CLI consumer that
proves the engine is interface-agnostic), 2.6 (`reporting/job.py`,
`AnalysisJob`, this ADR's actual subject)
**Related tests:** `tests/unit/test_reporting/test_job.py`, in particular
`TestArchitectureCompliance` and
`test_execute_is_the_only_call_site_of_run_reporting_pipeline`, which
enforce this decision mechanically, not just by convention.

---

## Context

Sprint 2 needed a GUI-facing way to run the reporting pipeline: something
that runs on a background thread (so a GUI event loop is never blocked),
exposes pollable `status`/`current_stage`/`progress`/`outputs` state, turns
the orchestrator's `on_progress` callback into a structured timeline, and
offers a `cancel()` method. Sprint 2.1 had already produced
`run_reporting_pipeline()` — a plain, synchronous, pure function taking
`(config, stage, dry_run, force, on_progress, cancel_event)` and returning
a results dict — as the pipeline's one orchestration seam, used directly
and unmodified by the Sprint 2.3 CLI (`reporting/main.py`).

The question this ADR answers: should the new GUI adapter call
`run_reporting_pipeline()` as a black box, or should it reimplement
stage-by-stage orchestration itself (checkpoint lookups, dependency
checks, manifest writing) so it can report progress and support
cancellation with finer granularity than the orchestrator's own
`on_progress`/`cancel_event` contract already provides?

## Decision

`AnalysisJob` (`reporting/job.py`) is a **state-management layer only**.
It delegates execution to exactly one call of `run_reporting_pipeline()`
per job instance, passing its own `on_progress`/`cancel_event` handlers
through the engine's existing, unmodified contract. It never calls
`master_table.py`, `inferential.py`, `manuscript_data.py`,
`manuscript_figures.py`, or `manuscript_tables.py` directly, and contains
no statistical or file-I/O logic of its own. `run_reporting_pipeline()`
stays the single canonical orchestration engine — used identically by the
CLI (Sprint 2.3) and by `AnalysisJob` (Sprint 2.6) — and `orchestrator.py`
itself is not modified to accommodate the GUI use case.

This is a hybrid API in the following precise sense: there are two public
entry points into the reporting pipeline (a synchronous function for the
CLI, a stateful class for a GUI), but only one engine underneath both.
Neither entry point is a special case of the other; both are thin adapters
over the same orchestration logic, following the same pattern already
established in this codebase by `CheckpointManager` (stateful) coexisting
with `build_provenance()` (pure) rather than one being reimplemented in
terms of the other.

## Rationale

**A second orchestration implementation is a second place to get stage
ordering, checkpoint interaction, or manifest writing wrong.**
`orchestrator.py`'s `_execute_stage()` is the only place stage
dependency-checking, checkpoint `should_run()`/`mark_done()` calls, and
run-manifest writing happen. Reimplementing any of this inside
`AnalysisJob` would create two sources of truth that could silently drift
— exactly the failure mode this project's "resolve once, persist, never
re-derive" principle (established during the entity-centric migration and
restated in `Software_Product_Architecture_v1.0.md` §2) exists to prevent
elsewhere in the codebase.

**The orchestrator's existing callback contract is already sufficient.**
`on_progress(stage, event)` and a cooperative `cancel_event` were built
into `run_reporting_pipeline()` at Sprint 2.1, before any GUI consumer
existed, specifically because a future non-CLI caller was anticipated.
Sprint 2.6 is the first real test of that contract, and it worked without
requiring any change to `orchestrator.py` — evidence the Sprint 2.1
design was sound, not just convenient.

**A `run_id` needs to exist before the engine returns one.** A GUI needs a
stable identifier for a job the moment it starts (to correlate UI state,
logs, and eventually the run manifest), but `run_reporting_pipeline()`
generates its own internal run ID for its manifest filename and does not
return it to the caller — and `orchestrator.py` is frozen, so this could
not be changed without violating the decision above. `AnalysisJob`
resolves this by generating its **own** run ID at construction time via
the same `generate_run_id()` generator the orchestrator itself uses, as a
stable, job-local correlation identifier. It is explicitly not guaranteed
to equal the orchestrator's own internal manifest run ID for the same
execution, and nothing in `AnalysisJob` reads or depends on that internal
ID — this is a deliberate, documented non-guarantee, not an oversight.

## Alternatives Considered

1. **`AnalysisJob` reimplements stage-by-stage orchestration for finer
   progress granularity.** Rejected — creates a second orchestration
   implementation (see Rationale); the marginal UX benefit of
   finer-grained progress than five stage-level events does not justify
   two sources of truth for checkpoint/manifest logic.
2. **Modify `orchestrator.py` to accept a GUI-specific hook or return its
   internal run ID.** Rejected — `orchestrator.py` was already frozen and
   verified (byte-equivalent behavior) by the time Sprint 2.6 started;
   reopening it for a GUI-only need would have re-exposed a component
   this project had deliberately closed out.
3. **Make the CLI (`reporting/main.py`) call `AnalysisJob` instead of
   `run_reporting_pipeline()` directly, so there is only one public entry
   point.** Rejected — the CLI has no use for background-thread execution,
   pollable state, or a timeline; routing it through `AnalysisJob` would
   add synchronization overhead and an extra layer for no behavioral
   benefit, and would make the CLI depend on GUI-adapter code.

## Consequences

**Positive:** `orchestrator.py` remains untouched and verified since
Sprint 2.1; the CLI and `AnalysisJob` are provably equivalent thin
adapters over the same engine (enforced by
`test_execute_is_the_only_call_site_of_run_reporting_pipeline`, which
greps `AnalysisJob._execute`'s own source for the call and separately
asserts no other method's source contains it); a future third consumer
(e.g. a REST job endpoint) has a proven pattern to follow — call
`run_reporting_pipeline()`, do not reimplement it.

**Negative:** `AnalysisJob`'s `run_id` and the orchestrator's own internal
manifest run ID are two different identifiers for related but not
identical purposes, which could confuse a future maintainer who assumes
they are the same value — mitigated by this ADR and by `job.py`'s own
docstring stating the non-guarantee explicitly.

## Future Trigger Conditions

Revisit this decision if `orchestrator.py` itself is ever reopened for
modification (e.g. to natively support the Section 16 REST API design in
`Software_Product_Architecture_v1.0.md`), or if a future consumer needs
progress granularity finer than one event per stage — at that point,
extending `run_reporting_pipeline()`'s own callback contract (available to
every consumer identically) is the pattern to extend, not adding a
job-specific orchestration path.
