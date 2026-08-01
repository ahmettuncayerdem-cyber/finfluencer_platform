# Sprint 4 Kickoff — EPIC-06, Reporting / MVP Core Loop

**Status:** Sprint 3 (EPIC-05, Sentiment Analysis) is CLOSED (T-022/T-023, ARB-01 approved) and frozen. This document does not redesign architecture or reopen Sprint 3.

## Sprint objective
Turn `AnalysisRun` output into citable, exportable `Report`s — the last piece the Roadmap's MVP definition (§6) requires: "collect real YouTube data, run topic and sentiment analysis, view and export results with citations to raw analysis output — no AI interpretation required."

## Scope
`T-024 → T-025 → (T-026 ‖ T-027) → T-028` (EPIC-06 only). Excludes AI-generated citations (Phase 2), Word export (§8.4's "v1.x" tag, not MVP), Billing/Public API/Admin-Ops (Phase 3).

## Success criteria
`InterpretationRecord`/`Report`/`Export` extend the Domain Model (T-024) with `kind: raw_result_snapshot` only. A completed `AnalysisRun` (topic or sentiment) can produce a `Report` with zero AI service calls (T-025). Table/CSV export reuses `reporting/master_table.py`'s tested logic (T-026); PDF rendering is new work, flagged as the backlog's own highest-uncertainty task (T-027). An in-app viewing screen closes the Presentation-layer loop (T-028). Full regression, Walking Skeleton, IG-001 stay green throughout.

## Deliverables
Three new Domain entities + tests (T-024). `GenerateReport` Application command (T-025). CSV export adapter (T-026). PDF rendering adapter (T-027, extra review time budgeted per its own Effort-L/highest-uncertainty flag). In-app Report viewing screen (T-028), FG-001/FG-002 compliant.

## Known implementation risks
T-027 (PDF rendering) is explicitly flagged in BACKLOG.md as this backlog's highest-uncertainty task — no existing tested code to lean on, unlike every other Reporting sub-task. T-024 carried one real design question: `InterpretationRecord`'s snapshot content has no architecture-specified serialization shape (`CreateRawSnapshot(analysisRunId, selector)` names a `selector` parameter but not a content format) — resolved as a flagged, opaque-`str` assumption, not silently picked; the actual encoding is deferred to T-025.

## Technical debt inherited from Sprint 1–3
T-015/T-017 live-network verification halves remain environment-blocked, unrelated to Reporting. T-020's retry-cache-miss characteristic, TD-03 (`AnalysisOutcome.topic_count` naming, classified Generalize, ARB-01) — neither affects Reporting's own entities. `reporting/` is classified **Adaptation required** (not "wrapper required" like Collection/Analysis) — its data-generation logic is reusable, but export rendering is genuinely new, a materially different risk profile than any task closed so far.

## Governance debt status: unchanged
Cross-vendor review still outstanding for T-008/010/011/012/013/015/016/017/018 — T-024 adds itself to this batch (Domain Model change, mandatory per its own Role line), still non-blocking, still batched-before-MVP. CEOM v1.0 remains sole canonical governance document; no new governance framework introduced.

## Exit criteria
T-024 through T-028 all closed, IG-001 clean, full regression and Walking Skeleton green, a `Report` demonstrably generated from a real (fixture-backed) topic or sentiment `AnalysisRun` with zero AI calls, PDF/CSV exports match `Report` content exactly, BACKLOG.md updated with each task's Outcome.
