# Context Pack — Reporting Engine Infrastructure Adapters

Full workflow: `IMPLEMENTATION_PLAYBOOK.md` Part B.2. Covers all three adapters in this package:
`ResultSnapshotAdapter` (T-025), `MasterTableExportAdapter` (T-026), and `PdfRendererAdapter`
(T-027) — kept in one Context Pack, unlike `topics`/`sentiment`'s two separate packs, because all
three are Reporting-internal capabilities on the same `Report`/`InterpretationRecord` data, not
independent pluggable `AnalysisType`s.

## Purpose

- **`ResultSnapshotAdapter`** implements `IResultSnapshotReader` by reading one `AnalysisRun`'s
  own result parquet and serializing it to a JSON string. Exists so `GenerateReportOrchestrator`
  (T-025) can turn a completed `AnalysisRun`'s output into `InterpretationRecord.content` (kind=
  `raw_result_snapshot`) through one Domain-safe method call.
- **`MasterTableExportAdapter`** implements `ITableExporter` by wrapping
  `reporting.master_table.build_master_table`/`save_master_table` unmodified. Exists so
  `ExportReportTableOrchestrator` (T-026) can export a `Report`'s cited `AnalysisRun`s as one
  joined table, reusing the tested join logic exactly.
- **`PdfRendererAdapter`** implements `IPdfRenderer` using `reportlab` (new dependency, ADR-0003)
  to render a `finalized` `Report`'s cited content into a PDF file. Exists so
  `GenerateExportOrchestrator` (T-027) can produce the `Export` (T-024, first real consumer)
  §8.4/§10.1 names. Unlike the two adapters above, this one wraps **no existing tested code** —
  genuinely new implementation, per `IMPLEMENTATION_ROADMAP.md` §3's own "[New for rendering]"
  classification.

## Domain entities and invariants owned or touched

Owns no §10.1 entity directly. Touches `AnalysisRun` only by convention (ids as parameters),
`InterpretationRecord` only indirectly, and — for `MasterTableExportAdapter` — `CollectionRun`
only by convention (`collection_run_id` as a parameter, used solely to resolve `comments_path`).
None of the three adapters construct or mutate any Domain entity — `PdfRendererAdapter` (T-027)
receives already-resolved citation content as plain strings from
`GenerateExportOrchestrator`, never a live `InterpretationRecord`/`Report` instance; the
`Export` entity itself is constructed by the orchestrator (Application), not this adapter. See
Integration decisions below for why T-026 does not produce an `Export` entity at all, and how
T-027 does.

## API Contract operations implemented

None directly. These adapters are the Infrastructure seams `GenerateReportOrchestrator`'s,
`ExportReportTableOrchestrator`'s, and `GenerateExportOrchestrator`'s Application-layer
implementations depend on to satisfy the `CreateRawSnapshot` (§11.2 line 722), table-export
(§8.4), and `GenerateExport` (§11.2 line 722) interactions, not the commands themselves.

## Guardrails that bind this module

- **IG-001** (layer-direction): `ResultSnapshotAdapter`/`MasterTableExportAdapter` import
  `finfluencer.utils.io`, `finfluencer.core.*` (transitively, via `utils.io`), and `pathlib`
  only. `PdfRendererAdapter` imports `reportlab.*` and `pathlib` only. None import
  Presentation/API, or `finfluencer.domain.reporting_engine`'s own consumers.
- **BKG-001** (business rules stay in Application/Domain): every adapter's own sequencing is a
  thin pass-through, not a business rule — deciding *which* `AnalysisRun` to snapshot and *when*
  (`GenerateReportOrchestrator`), whether every citation shares one `CollectionRun`
  (`ExportReportTableOrchestrator`), and whether a `Report` is eligible for export at all
  (`GenerateExportOrchestrator`, T-027) all live in Application, never in these adapters.

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
- **`PdfRendererAdapter` wraps no existing code — investigated and confirmed nothing to reuse.**
  `reporting/orchestrator.py`, `manuscript_figures.py`, `manuscript_tables.py` were re-read in
  full during T-027's Readiness Review; all three produce academic-publication tables/figures
  (matplotlib PNGs, Excel workbooks), not an in-product `Report`-to-PDF render. Confirmed by
  direct inspection, matching `IMPLEMENTATION_ROADMAP.md` §3's own "export rendering is
  genuinely new work" classification exactly.
- **`PdfRendererAdapter` uses `reportlab`, not `jinja2`.** `jinja2` is declared in
  `pyproject.toml` ("Templating (report / Publication Engine)") but was never imported anywhere
  in the codebase before or after T-027 — deliberately deferred to a future layout-polish
  fast-follow (see Known technical debt below), not used for T-027's minimal content-rendering
  scope. `reportlab` was added as a new runtime dependency (ADR-0003) since no PDF-capable
  library was previously declared or implied by ADR-0001.
- **`GenerateExportOrchestrator` constructs the `Export` (T-024) Domain entity — unlike T-026,
  this task DOES produce one.** §10.1 line 604 restricts `Export`/`ExportFormat` to "PDF or
  Word"; T-027's PDF rendering is exactly that capability, the first real use of an entity that
  had existed, unused, since T-024.
- **`GenerateExport`'s idempotency uses the natural `(report_id, report_version, format)` key**,
  not a separate caller-supplied idempotency token as §11.2 line 727's wording literally implies
  — `IExportRepository.get_by_report_version_and_format` provides an equivalent guarantee in this
  synchronous, single-process implementation. Flagged design note, not a silent deviation.
- **`FinalizeReportOrchestrator` (T-027, new) provides `FinalizeReport`'s idempotency at the
  Application layer.** `Report.finalize()` (T-024, Domain) raises `DomainInvariantViolation` on
  a second call by design (a terminal-state guard); the orchestrator checks
  `report.status is ReportStatus.FINALIZED` *before* calling `finalize()`, returning the
  already-finalized result as a no-op instead — satisfying §11.2 line 727's "finalizing twice is
  a no-op" without loosening the Domain method's own guard.

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
- **`PdfRendererAdapter` renders raw snapshot content verbatim, no publication-quality layout.**
  BACKLOG.md's own Internal Review named this exact split for T-027 ("render the citation and
  data content" vs. "render publication-quality layout") as a contingency if the task ran long;
  applied here as a deliberate MVP scope choice regardless — a fast-follow task should introduce
  `jinja2`-based templating (already declared, still unused) and per-`AnalysisType` structured
  rendering of snapshot content (tables instead of raw JSON text), not extend this adapter
  speculatively now.
- **No `Word` (`ExportFormat.WORD`) rendering.** Same T-024 TODO, still not actioned — no task
  in `T-024`-`T-028` range implements it; `GenerateExportOrchestrator` raises `ValueError` for
  any `format` other than `ExportFormat.PDF`.
- **`poetry.lock` not regenerated for `reportlab`/`pypdf`.** Same environment constraint as
  T-002/T-003; both packages are already importable in this sandbox's ambient Python environment
  (verified directly before implementation), so tests run and pass here, but a real
  `poetry install --sync` on a fresh environment has not been exercised this session.

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
- `PdfRendererAdapter.render()` receives already-resolved citation content as plain
  `dict[str, str]` rows (record_id/analysis_run_id/kind/selector/content) built by
  `GenerateExportOrchestrator` — it never calls any repository itself, unlike how
  `ResultSnapshotAdapter`/`MasterTableExportAdapter` resolve their own file paths by convention.
  This is a genuine, evidence-based shape difference (T-027's Readiness Review Q6): raw snapshot
  content lives in a repository-backed `InterpretationRecord`, not on a filesystem path this
  adapter could resolve by naming convention the way `topics.parquet`/`sentiment.parquet` are.
- `GenerateExportOrchestrator.execute()` raises `ValueError` if the `Report` is not yet
  `FINALIZED` — callers must invoke `FinalizeReportOrchestrator` first; this orchestrator never
  finalizes a `Report` on the caller's behalf (a deliberate product-behavior choice, not just a
  technical gap-fill: the PI may still want to add citations before locking the Report).
