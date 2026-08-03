# Sprint 4 Completion Report

**Date:** 2026-08-03
**Scope:** EPIC-06, Reporting / MVP Core Loop (T-024 through T-028).
**Status:** **Sprint 4 is closed.** All 5 tasks closed in `BACKLOG.md`; every quality gate
(unit regression, integration regression, IG-001) green as of commit `8770c0f`.

---

## Executive Summary

Sprint 4's goal, per `IMPLEMENTATION_ROADMAP.md` §5 Phase 1 and `SPRINT_4_KICKOFF.md`, was to
build the Reporting & Publication Engine: turn a completed `AnalysisRun`'s output into a citable
`Report`, render it to PDF, and make the whole flow reachable over real HTTP — the last piece of
EPIC-06 before T-029's MVP acceptance gate. That goal is achieved. A person can, today, from the
same developer web page Sprint 0 built: collect fixture data, run a (demo-engine) analysis
against it, generate a Report citing that analysis, finalize it, and download a real PDF — the
first time in this project's history any part of the Reporting Service or the Analysis Service
has been reachable outside a test file.

The Domain entities (`InterpretationRecord`, `Report`, `Export`, T-024) were built first and
never needed revision across the four tasks that followed. `Export` in particular sat unused for
three tasks before finding its first real consumer in T-027 and fitting without friction — direct
evidence the T-024 design was sound, not merely convenient. `reporting/master_table.py`, flagged
in T-025 as wrong-granularity for that task, was correctly reused unmodified one task later in
T-026, exactly where BACKLOG had always assigned it. T-027 introduced this project's first new
runtime dependency decision since the Sprint 0 tech stack (`reportlab`, ADR-0003) with no prior
library named anywhere in the architecture. T-028 found and closed a real, pre-existing gap
(`StartAnalysisRun` never exposed via API) using a deliberately scoped, honestly-labeled
substitute (ADR-0004) rather than either silently expanding scope or leaving the Reports screen
undemonstrable.

What remains open is accounted for below: no real, multi-`AnalysisType`-aware `AnalysisRun`
creation via API (ARB-01's TD-03/TD-04, still deferred); no publication-quality PDF layout; no
authentication; no Persistence Layer (every repository this sprint is still an in-memory
stand-in, same as every prior sprint). None of these block T-029.

## Sprint Goals

Per `IMPLEMENTATION_ROADMAP.md` §5 Phase 1 and `SPRINT_4_KICKOFF.md`: implement the Reporting &
Publication Engine's core loop (raw-snapshot citation, table export, PDF export) and expose it
through the Presentation/API layers, completing EPIC-06 as the last prerequisite before T-029's
full-MVP-loop verification. Achieved in full — all five named tasks closed, no scope cut.

## Completed Tasks

| Task | Outcome |
|---|---|
| T-024 | `InterpretationRecord`/`Report`/`Export` Domain entities. `Report` structurally never imports `AnalysisRun` (ast-verified) — section 10.0's citation rule made impossible to violate, not just discouraged. |
| T-025 | `GenerateReportOrchestrator` + `ResultSnapshotAdapter`. Real integration proof: a topic-`AnalysisRun` and a sentiment-`AnalysisRun` both citing into one `Report`. `master_table.py` investigated, correctly deferred to T-026. |
| T-026 | `ExportReportTableOrchestrator` + `MasterTableExportAdapter`, finally reusing `reporting/master_table.py` unmodified. Confirmed CSV/table export is not a Domain `Export` entity (§10.1 restricts `Export` to PDF/Word). |
| T-027 | `PdfRendererAdapter` (`reportlab`, ADR-0003) + `FinalizeReportOrchestrator`/`GenerateExportOrchestrator`. First real construction of `Export` (T-024, dormant until now). Genuinely new implementation — no existing tested code to wrap, confirmed by re-inspection. |
| T-028 | `GetReportOrchestrator` (new) + five new API routes (`api/routes/analysis.py`, `api/routes/reporting.py`), reusing six orchestrators completely unmodified. First Presentation/API exposure of Reporting and (via `StartAnalysisRun`) Analysis. Demo `IAnalysisEngine` stand-in (ADR-0004) closes a real, pre-existing API-exposure gap without resolving TD-03/TD-04. |

**Blocked, not part of this closure:** none — every task this sprint named was fully implementable
in this sandbox; no environment-blocked item was carried into Sprint 4's own scope (unlike
Sprint 0's T-002/T-003 or Sprint 1's live-network verification halves).

## Implemented Capabilities

A person can, today, from `web/index.html`: collect fixture data (Sprint 0); start a demo
Analysis Run against it (`POST /collection-runs/{id}/analysis-runs`, T-028, backed by T-020's
real orchestrator and a deliberately scoped demo engine); generate a Report citing that run
(`POST /projects/{id}/reports`, T-028/T-025); view it (`GET .../reports/{id}`, T-028); finalize
it (`POST .../finalize`, T-027/T-028); and export it as a real, downloadable PDF
(`POST .../exports`, T-027/T-028) or attempt a CSV table export (`GET .../table`, T-026/T-028,
correctly 422s for a topics-only Report — a documented limitation, not a bug).

Underneath the reachable surface: three new Domain entities with full lifecycle enforcement
(`Report`'s `draft → finalized`, `Export`'s pure immutability, `InterpretationRecord`'s
immutable-from-construction); four new Domain ports (`IResultSnapshotReader`, `ITableExporter`,
`IPdfRenderer`, plus `CitationSnapshot`) and three new repository interfaces
(`IReportRepository`, `IInterpretationRecordRepository`, `IExportRepository`), all following the
Sprint 0-established Domain-defines/Infrastructure-implements pattern with zero friction; one new
runtime dependency (`reportlab`) with its own ADR; and a composition root (`bootstrap.py`) now
wiring ten orchestrator instances across four services (Identity, Collection, Analysis,
Reporting), up from two at the start of this sprint.

## Architecture Compliance

`IG-001` reports clean at every checkpoint across all five tasks, no exceptions. Every
mechanically-uncovered layer edge (Application/Infrastructure not importing Presentation/API,
API not importing Domain directly) is enforced by dedicated `ast`-based tests, extended this
sprint to cover two new route modules (`api/routes/analysis.py`, `api/routes/reporting.py`) and
four new orchestrator modules. BKG-001 (business rules stay in Application/Domain) held
throughout — the one new orchestrator-level business rule this sprint added (T-026's
same-`CollectionRun` invariant) lives in Application, per every prior task's own precedent.
FG-001/FG-002 (T-028's own acceptance criteria) are satisfied by construction: every value
`web/index.html`'s new Reports section shows or downloads is exactly what its corresponding route
returned, nothing computed or fabricated client-side.

## Quality Metrics

Full regression (`tests/unit`, excluding two pre-existing, environment-drift-broken CLI
collection files unrelated to this sprint's own changes — `click` version drift, first noticed
during T-027): **1087 passed, 1 skipped**. `tests/integration`: **5 passed**. IG-001: **clean**
at every task close. **87 new test functions** added across the sprint, measured directly via
`git diff <task-start>..<task-end> -- tests/ | grep -c '^+def test_'` for each task's own commit
range: T-024: 26, T-025: 13, T-026: 11, T-027: 18, T-028: 19.

## Known Limitations Carried Forward

No Persistence Layer — every repository added this sprint (`Report`, `Export`,
`InterpretationRecord`, `AnalysisRun`) is still an in-memory stand-in, same as every prior
sprint's own repositories. No authentication/authorization on any new route. No
publication-quality PDF layout (raw snapshot content only). `_DemoTopicAssignmentEngine` does not
resolve ARB-01's TD-03/TD-04. `api/routes/reporting.py` conflates "not found" and "invalid
state" under HTTP 404. `poetry.lock` not regenerated for `reportlab`/`pypdf` (T-002/T-003's own
environment constraint). None of these block T-029, which requires a *real* end-to-end run with
real collected data and real analysis — itself a separate, already-named future task, not
something Sprint 4 was ever scoped to provide.

## Recommendation

Sprint 4 is ready to close. The next milestone per the critical path is **T-029** (Verify MVP
acceptance: full loop, reproducible) — see `SPRINT_5_READINESS_ASSESSMENT.md` for the detailed
gap analysis between what this sprint built and what T-029 requires before Sprint 5 (EPIC-07,
Identity Widening) can meaningfully begin.
