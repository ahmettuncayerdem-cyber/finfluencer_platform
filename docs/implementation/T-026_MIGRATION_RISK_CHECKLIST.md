# T-026 Migration Risk Checklist — Table/CSV Export

Scope: reuse `reporting/master_table.py` unmodified behind a new Infrastructure adapter and
Application orchestrator, exporting a `Report`'s cited `AnalysisRun` data as a joined CSV table.

## Reuse boundary

- [x] `build_master_table()` and `save_master_table()` (`reporting/master_table.py`) are called
      with zero code changes — confirmed by re-reading the full module before this task began.
- [x] No modification to `reporting/master_table.py`, `reporting/orchestrator.py`, or any other
      Sprint 1/2.1 reporting module.
- [x] `master_table.py`'s own empty-source validation (`CorpusValidationError`) is preserved,
      not caught or suppressed by the new adapter.

## Domain Model boundary

- [x] No new Domain entity introduced. `Export` (T-024) is **not** extended with a CSV
      `ExportFormat` member — `PRODUCT_ARCHITECTURE.md` §10.1 line 604 names only "PDF or Word"
      for the `Export` entity; CSV/table generation is the separate "manuscript-ready table
      objects... available for in-app viewing before export" capability §8.4 names, which does
      not require a new entity. Verified against the frozen architecture text before deciding,
      not assumed.
- [x] `IInterpretationRecordRepository` gains exactly one new method (`get_by_id`) — the
      surface T-025's own docstring already anticipated this task adding, not a speculative
      addition.

## Layering (IG-001)

- [x] New Infrastructure adapter (`infrastructure/reporting/table_export_adapter.py`) imports
      only `finfluencer.core.*`, `finfluencer.reporting.master_table`, `pathlib` — no
      Presentation/API import (ast-verified in tests).
- [x] New Application orchestrator (`application/orchestrators/export_report_table.py`) imports
      no `pandas`, no `finfluencer.infrastructure.*` — same discipline as T-025's orchestrator
      (ast-verified in tests).

## Business rules (BKG-001)

- [x] The one new business rule this task adds ("a Report's cited AnalysisRuns must all belong
      to the same CollectionRun, or the master table cannot be built") lives in the Application
      orchestrator, never in Infrastructure.

## Idempotency / side effects

- [x] `export()` is a pure read-and-write-one-file operation — calling it twice with the same
      inputs overwrites the same `output_path` with byte-identical content (same behavior
      `save_master_table()` already has). No new idempotency mechanism invented; none is needed
      for this task's scope (no repository `add()` call is keyed by this operation).

## Cross-project isolation

- [x] `ExportReportTableOrchestrator` resolves every citation's `AnalysisRun` through
      `IAnalysisRunRepository.get_by_id(project_id, ...)`, the same project-scoped lookup T-025
      already established — a citation belonging to another project's `AnalysisRun` cannot be
      exported by this command.

## What this checklist deliberately does not cover

- Real-scale CSV performance (large `AnalysisRun` outputs) — not exercised in this sandbox,
  same class of deferred verification as every prior adapter task.
- PDF rendering (T-027) — separate task, no dependency either direction beyond both reading
  from the same `Report`/`InterpretationRecord` data.
