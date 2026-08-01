# Sprint 2 Kickoff — EPIC-04, Topic Analysis

**Status:** Sprint 1 (EPIC-03, Live Collection) is CLOSED and frozen — T-015/T-016/T-017 not reopened absent a discovered defect. This document does not redesign architecture, rewrite constitutional documents, or reopen Sprint 1.

## Sprint objective

Wrap the existing, tested BERTopic pipeline as the first concrete `AnalysisType`, proving the pluggable-analysis-type architecture (`PRODUCT_ARCHITECTURE.md` §5, §10.1) end to end with one real implementation — the Analysis-side equivalent of what Sprint 0/1 already proved for Collection.

## Scope

`T-018 → T-019 → T-020 → T-021` (EPIC-04 only). Excludes EPIC-05 (Sentiment), EPIC-06 (Reporting/MVP loop), EPIC-07 (Identity) — each is its own future sprint.

## Success criteria

`AnalysisRun` pinned to a specific `CollectionRun` per §10.1's hard rule, immutable once completed. `topics/` (BERTopic) wrapped as an Infrastructure adapter producing real topic assignments from a `Dataset`. `StartAnalysisRun` orchestrator matches T-011's idempotency/BKG-001 discipline exactly. Full regression, Walking Skeleton subset, and IG-001 stay green throughout.

## Deliverables

`AnalysisType`/`AnalysisRun` Domain entities (T-018). Topics Infrastructure adapter + its Context Pack, authored in the same PR (T-019). `StartAnalysisRun` orchestrator (T-020). Immutability/pinning verification test (T-021).

## Known implementation risks

T-019 is Effort L — the backlog's own flag that this is the first place compute cost/runtime genuinely matters, unlike the lightweight Collection wrappers. Roadmap Risk R-2 (`AnalysisScope` reconciliation with `Dataset`/`AnalysisRun`) is exactly what T-018 tests against real code for the first time — may surface a genuine contradiction, in which case implementation stops per standing instruction. Roadmap Risk R-6 (vertical coupling in `preprocess/financial_tr.py`) is adjacent — the topics adapter may touch preprocessing; not this epic's job to fix, only to avoid deepening.

## Technical debt inherited from Sprint 1

T-015's and T-017's live-network/real-timing verification halves remain environment-blocked (manual scripts ready, awaiting an environment with real egress) — unrelated to Topic Analysis, carried forward unchanged.

## Governance debt status: unchanged, plus one addition

Cross-vendor review still outstanding for T-008/T-010/T-011/T-012/T-013/T-015/T-016/T-017 (non-blocking). F-002 (Roadmap's `GetCollectionRunStatus` vs. actual `GetCollectionRun` naming) still open, non-blocking. **New:** T-018 itself carries a mandatory cross-vendor review per its own BACKLOG.md entry (Domain Model change) — tracked, not blocking implementation start.

## Exit criteria

T-018 through T-021 all closed, IG-001 clean, full regression and Walking Skeleton subset green, topics Context Pack authored, BACKLOG.md updated with each task's Outcome.
