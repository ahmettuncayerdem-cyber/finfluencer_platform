# Sprint 4 Retrospective

**Date:** 2026-08-03
**Scope:** T-024 through T-028 (EPIC-06, Reporting / MVP Core Loop).
**Status:** Sprint 4 complete. All 5 tasks closed in `BACKLOG.md`; commits `c03a28d`
(T-024) through `8770c0f` (T-028) on `phase2-development`.

---

## What went well

The Domain-first sequencing (T-024's `InterpretationRecord`/`Report`/`Export` before any
orchestrator touched them) paid off across the whole sprint. `Report.finalize()`'s
terminal-state guard, `Export`'s pure-immutability, and `InterpretationRecord`'s
never-imports-`AnalysisRun` structural rule were all designed once in T-024 and never needed a
second look in T-025 through T-028 — including `Export`, which sat completely unused for three
tasks (T-024→T-025→T-026) before T-027 finally constructed one, and it fit its first real
consumer with zero friction.

The "wrapper, not rewrite" discipline held for the third consecutive sprint, now against a third
kind of legacy code: `reporting/master_table.py` (T-026) was investigated in T-025's own
Readiness Review, correctly judged wrong-granularity for that task, and correctly reused
unmodified one task later — exactly where BACKLOG had always assigned it. This is the strongest
evidence yet that the reuse-classification discipline established in Sprint 0/1 (Roadmap §3's
own reuse table) generalizes past the two engines (Collection, Analysis) it was originally
written against.

T-028's Readiness Review surfaced a real, load-bearing gap — `StartAnalysisRun` (T-020) had never
been exposed via API — before any code was written, not after. Resolving it by building the
architecture's own already-named §11.3 line 779 endpoint, behind a deliberately-scoped,
honestly-labeled demo engine (ADR-0004), kept the fix inside T-028's own effort budget without
either silently expanding scope or leaving the Reports screen undemonstrable.

Every one of T-024 through T-028's own quality gates passed on the first attempt after
implementation — no task needed a second regression run to reach green, and only one trivial
test-assertion bug (a missing `__future__` allowance in an ast import-check) was found and fixed
across the entire sprint.

## What was harder than expected

T-027's technology decision (which PDF library) was a genuine, unprecedented choice — no ADR, no
declared dependency, and no prior task in this project had ever picked a rendering library.
Comparing `reportlab`/`weasyprint`/`pdfkit`/`xhtml2pdf` against this sandbox's actual constraints
(no external system binaries, already-importable) took real investigation, not just following an
established pattern the way T-025/T-026 could.

T-028's scope was harder to bound than any prior task in this backlog. The literal reading of
"build the Report viewing screen" implied needing a real `AnalysisRun` to view a Report from, but
building one properly (real BERTopic, `AnalysisType`-catalog dispatch) would have meant resolving
ARB-01's TD-03/TD-04 and pulling in heavy ML dependencies neither this sandbox nor T-028's own
Effort-M budget could support. Recognizing that the *correct* answer was a small, honestly-scoped,
independent demo engine — not a shortcut, and not scope creep — took more deliberation than any
other single decision this sprint.

## Assumptions validated

The "genuinely new, no existing tested code" flag BACKLOG placed on T-027 (its own
highest-uncertainty task) held up exactly as predicted — it was the sprint's largest single new
dependency decision, and the only task requiring its own ADR for a technology choice. Flagging
uncertainty accurately, before the work started, made the actual work proceed without surprises.

The Domain port pattern (`IResultSnapshotReader`, `ITableExporter`, T-025/T-026) generalized to a
third case (`IPdfRenderer`, T-027) and a fourth non-adapter case (`IExportRepository`, same
minimal-surface repository-growth discipline as every prior repository) with zero friction,
mirroring Sprint 0's own identical finding about `ICollectionEngine`/`IProjectRepository`
generalizing cleanly.

## Assumptions disproved

The assumption, implicit in BACKLOG's own dependency graph (`T-028` depends only on `T-026`,
`T-027`), that T-028 would be a pure Presentation-layer task touching no Application/
Infrastructure code, was wrong. It required one new Application orchestrator (`GetReportOrchestrator`)
and one new, deliberately-scoped Infrastructure-adjacent stand-in (`_DemoTopicAssignmentEngine`)
neither T-026 nor T-027 had any reason to anticipate — a direct consequence of `StartAnalysisRun`'s
API exposure being a genuine, pre-existing gap outside this sprint's own dependency chain.

## Technical debt introduced

`reportlab`/`pypdf` (T-027) are declared in `pyproject.toml` but `poetry.lock` was not
regenerated — this sandbox's own T-002/T-003 environment constraint, not new to this sprint but
newly re-encountered.

PDF rendering (T-027) has no publication-quality layout — raw snapshot content only, `jinja2`
(declared since before this sprint, still unused) deliberately deferred to a future fast-follow.

`_DemoTopicAssignmentEngine` (T-028) does not resolve ARB-01's TD-03/TD-04
(`AnalysisType`-dispatch generalization) — a real, multi-`AnalysisType`-aware `StartAnalysisRun`
exposure remains future work, now more visible (a real route exists) but not more solved.

`api/routes/reporting.py` (T-028) maps every orchestrator `ValueError` to HTTP 404 regardless of
whether the cause is "not found" or "invalid state" — a known, minor imprecision, flagged in
`api/CONTEXT_PACK.md` rather than silently accepted.

Table/CSV export (T-026, now reachable via T-028's HTTP route) still requires a `Report` to cite
both a topics- and a sentiment-shaped `AnalysisRun` — inherent to `build_master_table()`'s own
three-source-table requirement, not new debt, but now user-visible as a 422 for the first time.

## Technical debt retired

None this sprint — Sprint 4 was additive (new capability) throughout; no prior sprint's debt item
was closed as a side effect of this work.
