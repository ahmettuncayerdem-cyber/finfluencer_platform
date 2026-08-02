# Context Pack — Reporting Engine Infrastructure Adapters

Full workflow: `IMPLEMENTATION_PLAYBOOK.md` Part B.2. Covers both adapters in this package:
`ResultSnapshotAdapter` (T-025) and `MasterTableExportAdapter` (T-026) — kept in one Context
Pack, unlike `topics`/`sentiment`'s two separate packs, because both are Reporting-internal
capabilities on the same `Report`/`InterpretationRecord` data, not two independent pluggable
`AnalysisType`s.

## Purpose

- **`ResultSnapshotAdapter`** implements `IResultSnapshotReader` by reading one `AnalysisRun`'s
  own result parquet and serializing it to a JSON string. Exists so `GenerateReportOrchestrator`
  (T-025) can turn a completed `AnalysisRun`'s output into `InterpretationRecord.content` (kind=
  `raw_result_snapshot`) through one Domain-safe method call.
- **`MasterTableExportAdapter`** implements `ITableExporter` by wrapping
  `reporting.master_table.build_master_table`/`save_master_table` unmodified. Exists so
  `ExportReportTableOrchestrator` (T-026) can export a `Report`'s cited `AnalysisRun`s as one
  joined table, reusing the tested join logic exactly.

## Domain entities and invariants owned or touched

Owns no §10.1 entity directly. Touches `AnalysisRun` only by convention (ids as parameters),
`InterpretationRecord` only indirectly, and — for `MasterTableExportAdapter` — `CollectionRun`
only by convention (`collection_run_id` as a parameter, used solely to resolve `comments_path`).
Neither adapter constructs or mutates any Domain entity, including `Export` — see Integration
decisions below for why T-026 does not produce an `Export` entity at all.

## API Contract operations implemented

None directly. These adapters are the Infrastructure seams `GenerateReportOrchestrator`'s and
`ExportReportTableOrchestrator`'s Application-layer implementations depend on to satisfy the
`CreateRawSnapshot` (§11.2 line 722) and table-export (§8.4) interactions, not the commands
themselves.

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
- **`MasterTableExportAdapter` DOES reuse `reporting.master_table.build_master_table()`/
  `save_master_table()`, unmodified — zero lines changed.** This is the correct reuse target
  BACKLOG.md always assigned to T-026 (not T-025, see `ResultSnapshotAdapter`'s own entry
  above): a joined, cross-`AnalysisType` table is exactly what a `Report` citing both a topics-
  and a sentiment-`AnalysisRun` needs exported as one file.
- **T-026 constructs no Domain `Export` entity.** §10.1 line 604 restricts `Export`/
  `ExportFormat` to "PDF or Word" — CSV/table generation is the separate "manuscript-ready table
  objects... available for in-app viewing before export" capability §8.4 names, which needs no
  new entity. Verified against the frozen architecture text during T-026's own Readiness Review
  before deciding, not assumed; no Domain Model extension was made for this reason.
- **`MasterTableExportAdapter` resolves `topics_path`/`sentiment_path` by presence among the
  given `analysis_run_ids`, duplicating `ResultSnapshotAdapter`'s own resolution-by-presence
  logic rather than sharing it.** Accepted deliberately: two small, independent adapters, not
  yet a pattern worth extracting a shared base class for (this turn's own instruction: "do not
  introduce speculative abstractions").
- **`ExportReportTableOrchestrator` requires every citation in a `Report` to pin to the same
  `CollectionRun`.** A joined master table has no coherent meaning across two different
  `CollectionRun`s' comments — this invariant is enforced in the orchestrator (Application),
  never in this adapter, per BKG-001.

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

- `ResultSnapshotAdapter.read()` raises `FileNotFoundError` if neither known filename exists
  (e.g. the `AnalysisRun` isn't actually completed yet, or was written by a future adapter this
  module doesn't know about) and `ValueError` if somehow both exist for the same
  `analysis_run_id` (should be structurally impossible today — each `AnalysisRun` produces
  exactly one output file — but checked explicitly rather than silently picking one).
- `MasterTableExportAdapter.export()` raises `FileNotFoundError` if the given `analysis_run_ids`
  don't collectively resolve to both a topics and a sentiment path — `build_master_table()`
  itself requires all three source tables, so a `Report` citing only one `AnalysisType` cannot
  be table-exported yet (a real limitation, not a bug; flagged as Known technical debt above,
  same "T-025's own Verification line already assumed two-run scenarios" reasoning).
- `MasterTableExportAdapter.export()` inherits `build_master_table()`'s own
  `CorpusValidationError` if any of the three resolved source tables is empty — not caught or
  suppressed here.
