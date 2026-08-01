# T-021 Architecture & Invariant Readiness Review — Verify `AnalysisRun` immutability and `CollectionRun` pinning

## 1. Immutability guarantees §10.1 requires for `AnalysisRun`

Line 578: "**Immutable once `completed`** — same reasoning as `CollectionRun`." Line 577: "re-run creates a new `AnalysisRun`, never mutates an existing one." Both are already implemented in T-018's entity (`_reject_if_completed()` guards every transition method; no `resume()` exists at all, so there is no code path that could mutate a completed *or* failed run back into `running`).

## 2. Which `CollectionRun` fields are pinned vs. left as references

Nothing about `CollectionRun` itself is copied into `AnalysisRun` — line 576 says `AnalysisRun` "references exactly one `CollectionRun`," not that it duplicates its data. T-018 modeled this correctly: `AnalysisRun.collection_run_id: EntityId` is a reference (an id), never a `CollectionRun` object, and never any of `CollectionRun`'s own fields (`dataset_id`, `status`, etc.). There is nothing to "pin into" `AnalysisRun` beyond the id itself — the pinned *state* (the actual collected data) lives on disk, addressed via that id, exactly how `TopicsAnalysisAdapter` (T-019) already resolves `comments_path`.

## 3. Pinning vs. copying, precisely

Pinning = storing a stable reference (`collection_run_id: EntityId`) that never changes after construction, so "which `CollectionRun`'s data state this analysis ran against" is permanently recoverable and unambiguous — this is what makes an `AnalysisRun` "a valid reproducibility anchor" (line 578's own phrase, borrowed from `CollectionRun`'s line 568). Copying would mean duplicating `CollectionRun`'s own fields into `AnalysisRun` at creation time — not done, not required, and would create exactly the "moving target" problem line 576 warns against if the copy ever silently diverged from the source.

## 4. Invariants that must be impossible to violate after creation

(a) `collection_run_id`, `analysis_type_id`, `analysis_type_version`, `project_id` never change value for a given `AnalysisRun` instance — no setter exists for any of them (T-018). (b) No transition method succeeds once `status is COMPLETED` (`_reject_if_completed`). (c) No `resume()` method exists or can be invoked — retrying is only possible by constructing a distinct instance (T-020's orchestrator already does this).

## 5. Existing components that must remain unchanged

`domain/entities/analysis_run.py` and `analysis_type.py` (T-018), `domain/analysis_engine.py` and `infrastructure/analysis/topics_adapter.py` (T-019), `application/orchestrators/start_analysis_run.py` and `domain/repositories.py`'s `IAnalysisRunRepository` (T-020) — all already implement the invariants this task verifies. T-021's own BACKLOG entry (Effort XS, "the first real test... not just Domain Model theory") confirms this is a verification-only task.

## 6. Assumptions, flagged explicitly

- "Cannot be re-pointed after creation" is verified at the level this codebase's own established idiom already uses for every other entity (`CollectionRun`, `Dataset`, etc.): no public setter/method exists to change a pinning field. It does not mean immune to direct private-attribute (`_collection_run_id`) manipulation via Python's own dynamic object model — no entity in this codebase (nor `PRODUCT_ARCHITECTURE.md`) claims that stronger, language-level guarantee, and adding one (e.g. `__slots__` + descriptor tricks) would be a new abstraction this task does not need and was not asked to invent.
- "Previously completed AnalysisRuns remain unchanged" is interpreted as: after a retry creates a new `AnalysisRun` for the same idempotency key, the old (failed) instance's own fields and status are untouched — not that a `COMPLETED` run's *underlying analysis output* (parquet files) is re-verified byte-for-byte here (that is `topics_adapter.py`'s and `run_topics()`'s own already-tested caching/output behavior, T-019, not re-tested here).

## 7. BKG-001 / IG-001 compliance

No business rule changes — this task adds no new orchestration logic, only tests. IG-001 unaffected: no new production module, no new cross-layer import.

## 8. Contradiction check

None found. Proceeding — implementation is test-only, per Effort XS and "prefer invariant enforcement over defensive runtime checks" (the invariants are already enforced architecturally by T-018; this task proves it, it does not add new guards).
