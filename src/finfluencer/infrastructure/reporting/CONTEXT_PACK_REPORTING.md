# Context Pack — Reporting Engine Infrastructure Adapter

Full workflow: `IMPLEMENTATION_PLAYBOOK.md` Part B.2.

## Purpose

Implements `finfluencer.domain.reporting_engine.IResultSnapshotReader` by reading one
`AnalysisRun`'s own result parquet and serializing it to a JSON string, behind one adapter class
(`ResultSnapshotAdapter`). Exists so `GenerateReportOrchestrator` (BACKLOG.md T-025) can turn a
completed `AnalysisRun`'s output into `InterpretationRecord.content` (kind=`raw_result_snapshot`)
through one Domain-safe method call, without knowing or caring how or where the result is stored
on disk.

## Domain entities and invariants owned or touched

Owns no §10.1 entity directly. Touches `AnalysisRun` only by convention (its `id` is the
`analysis_run_id` parameter) and `InterpretationRecord` only indirectly (this adapter produces
the `content` a caller constructs one from; it never constructs the entity itself).

## API Contract operations implemented

None directly. This adapter is the Infrastructure seam `GenerateReportOrchestrator`'s
Application-layer implementation depends on to satisfy the `CreateRawSnapshot` interaction
(§11.2 line 722), not the command itself.

## Guardrails that bind this module

- **IG-001** (layer-direction): imports `finfluencer.utils.io`, `finfluencer.core.*` (transitively,
  via `utils.io`), and `pathlib` only. No Presentation/API import, no import of
  `finfluencer.domain.reporting_engine`'s own consumers.
- **BKG-001** (business rules stay in Application/Domain): this adapter's sequencing (resolve
  path by presence → read parquet → serialize to JSON) is a thin pass-through, not a business
  rule — deciding *which* `AnalysisRun` to snapshot, and *when*, is `GenerateReportOrchestrator`'s
  job.

## Integration decisions (existing-engine code, if any)

- **`reporting.master_table.build_master_table()` was investigated and deliberately NOT
  reused.** It requires `comments.parquet`, `topics.parquet`, AND `sentiment.parquet`
  simultaneously (raising `CorpusValidationError` if any is empty) and produces a single,
  cross-AnalysisType joined table — a different granularity than "one snapshot of one
  `AnalysisRun`'s own output" (§10.1 line 586: an `InterpretationRecord` "belongs to exactly one
  `AnalysisRun`, always"). BACKLOG.md's own line assigns `master_table.py` reuse to **T-026**
  (CSV export of the full joined table), not T-025. Forcing it into T-025's per-run granularity
  would have meant working around its all-three-required constraint for no benefit. Flagged in
  T-025's own Readiness Review, not silently force-fit.
- **Which result filename applies is resolved by presence, not by an `AnalysisType` lookup.**
  There is no `AnalysisType` catalog/repository wired up anywhere in this codebase yet that
  Application could consult to resolve `analysis_type_id` (an opaque `EntityId`) to a concrete
  filename. `_KNOWN_OUTPUT_FILENAMES = ("topics.parquet", "sentiment.parquet")` is checked by
  existence under the conventional path instead.
- **Snapshot content is `DataFrame.to_json(orient="records")` of the full result table, no
  partial-selector query language.** `selector` (named in §11.2's `CreateRawSnapshot`) is
  produced by the orchestrator as a fixed value for this task's scope, not interpreted by this
  adapter at all — this adapter always returns the complete result.

## Known technical debt

- **Filename-presence resolution does not generalize automatically to a third `AnalysisType`.**
  A future `AnalysisType` wrapped behind a new adapter (mirroring T-019/T-022's own pattern)
  needs its own filename added to `_KNOWN_OUTPUT_FILENAMES`, or this adapter needs a more
  general mechanism (e.g. an actual `AnalysisType` → filename catalog) — not built speculatively
  now, since only two `AnalysisType`s exist and no catalog exists to consult even if built.
- **No partial/selective snapshot support.** `selector` is currently a fixed, whole-table value.
  A real per-topic/per-statistic selection mechanism is future work, only if a real need
  surfaces — not invented here ahead of a concrete requirement.
- **No real, large-result-set performance characteristics measured.** `to_json(orient="records")`
  on a fixture-sized table is instant; behavior on a realistically large `AnalysisRun` output
  (thousands of rows) has not been exercised in this sandbox.

## Gotchas

- Raises `FileNotFoundError` if neither known filename exists (e.g. the `AnalysisRun` isn't
  actually completed yet, or was written by a future adapter this module doesn't know about) and
  `ValueError` if somehow both exist for the same `analysis_run_id` (should be structurally
  impossible today — each `AnalysisRun` produces exactly one output file — but checked
  explicitly rather than silently picking one).
