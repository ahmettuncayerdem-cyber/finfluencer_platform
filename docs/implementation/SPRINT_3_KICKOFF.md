# Sprint 3 Kickoff — EPIC-05, Sentiment Analysis

**Status:** Sprint 2 (EPIC-04, Topic Analysis) is CLOSED (T-018–T-021, human-verified 2026-08-01) and frozen — not reopened absent a discovered defect. This document does not redesign architecture, rewrite constitutional documents, or reopen Sprint 2.

## Sprint objective

Wrap the existing, tested sentiment pipeline as a second concrete `AnalysisType`, proving the pluggable-analysis-type architecture generalizes beyond the one implementation (BERTopic) it was built against — not a one-off built for topic modeling specifically.

## Scope

`T-022 → T-023` (EPIC-05 only). Excludes EPIC-06 (Reporting/MVP loop), EPIC-07 (Identity) — each is its own future sprint.

## Success criteria

`sentiment/` pipeline wrapped as an Infrastructure adapter implementing `IAnalysisEngine` (T-019's own interface, unchanged), producing sentiment scores from a `Dataset`'s collected comments. `StartAnalysisRunOrchestrator` (T-020) dispatches it with **zero code changes** — T-023's own acceptance criterion. Full regression, Walking Skeleton subset, and IG-001 stay green throughout.

## Deliverables

Sentiment Infrastructure adapter + its Context Pack, authored in the same PR (T-022). A diff review confirming `start_analysis_run.py` was not touched, or an ADR explicitly justifying any diff that was required (T-023).

## Known implementation risks

The whole point of T-023 existing as its own task is that this is not yet proven — if wiring a second `AnalysisType` turns out to need an orchestrator change, that is a real gap in the plugin abstraction worth surfacing now, before a third `AnalysisType` compounds it. T-022's own BACKLOG line rates this **lower risk than T-019** ("same established pattern"), since `IAnalysisEngine`/`TopicsAnalysisAdapter`'s shape has already been proven once.

## Technical debt inherited from Sprint 1/2

T-015's and T-017's live-network/real-timing verification halves remain environment-blocked (manual scripts ready, awaiting real egress) — unrelated to Sentiment Analysis, carried forward unchanged. T-020's retry-after-failure cache-miss characteristic (T-019's per-`analysis_run_id` cache partitioning) applies identically to whichever `AnalysisType` is retried — not sentiment-specific, not addressed here.

## Governance debt status: unchanged

Cross-vendor review still outstanding for T-008/T-010/T-011/T-012/T-013/T-015/T-016/T-017/T-018 (non-blocking; growing list, flagged for a batched pass before MVP, not before). F-002 (Roadmap naming mismatch) still open, non-blocking. No new cross-vendor review requirement expected from T-022/T-023 (neither is a Domain Model change).

## Exit criteria

T-022 and T-023 both closed, IG-001 clean, full regression and Walking Skeleton subset green, sentiment Context Pack authored, BACKLOG.md updated with each task's Outcome, orchestrator diff for T-022 confirmed zero (or justified via ADR).
