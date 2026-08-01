# Governance Register

**Status:** Temporary Practice (same classification as `BACKLOG.md`, `IMPLEMENTATION_PLAYBOOK.md` Part K) — updated without ceremony as governance-relevant events occur, no PR review required for register-only edits. Mandated by CEOM v1.0 §9. First populated 2026-08-01, retroactively covering decisions/reviews already made this engagement.

**How to read this:** each entry is a pointer, not a duplicate of the full review that produced it — the full text lives in `BACKLOG.md` Outcome sections, Context Packs, or this session's own reports. This file exists so governance state survives context resets without re-deriving it.

**Governance framework:** **CEOM v1.0** is the single canonical, normative governance document (per GIP-01, approved 2026-08-01). Future governance changes follow semantic versioning (CEOM v1.1, v1.2, v2.0, ...) and must be proposed through the GIP process (CEOM §17). No additional top-level governance framework may be introduced unless it represents a genuinely new governance dimension that cannot reasonably fit inside CEOM. The Project Constitution, POS v1.0, EGF v1.0, and ARB v1.0 remain part of the project's historical record — their content was merged into CEOM v1.0 without conflict — but are no longer independently normative.

---

## Architecture Decisions (ADR)

| ID | Status | Reason | Owner | Next Review Point |
|---|---|---|---|---|
| ADR-0001 | Accepted (2026-08-01) | Technology stack (FastAPI/PostgreSQL/SQLAlchemy 2.0/Redis+arq/React+TS/first-party JWT/Docker) — `docs/adr/0001-technology-stack.md`, accepted as-is including the flagged thin-evidence row (React vs. Svelte/Vue). | Operator | None scheduled (frozen). |
| ADR-0002 | Accepted (referenced since T-010) | Per-`run_id` partitioning discipline (checkpoint/cache/output isolation per run), Roadmap Risk R-1. Applied identically to Collection (T-010), Topics (T-019), Sentiment (T-022). | Architecture | None scheduled. |

## Architecture Review Board (ARB)

| ID | Status | Reason | Owner | Next Review Point |
|---|---|---|---|---|
| ARB-01 | Proposed, deferred | `IAnalysisEngine` plugin-pattern review — trigger: second implementation exists (`SentimentAnalysisAdapter`, T-022). Operator elected to defer until T-023 supplies zero-orchestrator-diff evidence, strengthening the review's basis. | Claude (reviewer) / Operator (authorizer) | After T-023 closes. |

## Technical Debt (TD)

| ID | Status | Reason | Owner | Next Review Point |
|---|---|---|---|---|
| TD-01 | Open, non-blocking | T-015/T-017 live-network/real-timing verification halves environment-blocked (sandbox proxy returns 403 for `googleapis.com`). Manual scripts ready for an operator with real egress. | Operator (execution) | First task requiring genuine live-network proof (unscheduled). |
| TD-02 | Open, non-blocking | Retry-after-failure cache-miss: T-019/T-020's per-`analysis_run_id` cache partitioning means a retried analysis run never hits the Tier-3 cache, even on an unchanged corpus. Applies identically to T-022. Correctness-preserving trade-off, not a defect. | Architecture | Unscheduled — revisit only if retry frequency in production makes this a measurable cost. |
| TD-03 | Open, classified **Generalize** (EGF Contract Stability Review) | `AnalysisOutcome.topic_count` is topic-modeling-named, reused for sentiment's distinct-class count (T-022). Field predates a second `AnalysisType`; changing it now touches T-019's frozen contract. | T-023 review | T-023. |
| TD-04 | Open, low priority | Context Pack file-naming asymmetry: `CONTEXT_PACK.md` (unsuffixed, Topics) vs. `CONTEXT_PACK_SENTIMENT.md` (suffixed, Sentiment) — convention never formalized before a second adapter existed. | Housekeeping | Before a third `AnalysisType` is added. |
| TD-05 | Open, non-blocking (flagged since T-019) | Embeddings-generation pipeline not wrapped as its own Infrastructure adapter; `embeddings_index_path` remains caller-supplied to `TopicsAnalysisAdapter`. | Unticketed | First task needing to produce `embeddings_index.parquet` from raw comments rather than consume a pre-existing one. |

## Cross-Vendor Reviews (CVR)

| ID | Status | Reason | Owner | Next Review Point |
|---|---|---|---|---|
| CVR-01 | Open, non-blocking | 9 tasks outstanding: T-008, T-010, T-011, T-012, T-013, T-015, T-016, T-017, T-018. Flagged for a batched pass before MVP, not before. | Operator (scheduling) | Before MVP acceptance (T-029). |

## Known Risks (RISK)

| ID | Severity | Reason | Owner | Next Review Point |
|---|---|---|---|---|
| RISK-01 | Low | Sandbox network egress restriction blocks live-network verification (T-015/T-017). Documented workaround exists (manual scripts for an operator with real egress). | Operator | Whenever real egress is available. |
| RISK-02 | Resolved via GIP-01 (2026-08-01) | Governance process overhead — five framework documents had been adopted in sequence (Project Constitution, POS, EGF, ARB, CEOM). Resolved by consolidating to CEOM v1.0 as sole canonical document; no further top-level frameworks to be introduced absent a genuinely new governance dimension. | Operator | Monitor at next Sprint closure — confirm no new top-level framework was introduced outside the GIP process. |

## Governance Improvement Proposals (GIP)

| ID | Status | Reason | Owner | Next Review Point |
|---|---|---|---|---|
| GIP-01 | **Approved 2026-08-01** | Consolidate five overlapping governance documents into CEOM v1.0 as the single canonical, normative reference; future changes via semantic versioning and the GIP process only. | Operator (approved) | N/A — standing policy. |

## Deferred Improvements (DI)

| ID | Description | Reason Deferred | Impact | Suggested Sprint | Priority |
|---|---|---|---|---|---|
| DI-01 | Generalize `AnalysisOutcome`'s categorical-count field name. | T-019's contract is frozen; T-023 is the correct venue to decide. | Low, cosmetic/semantic. | Sprint 3 closure or Sprint 4. | Low |
| DI-02 | Formalize Context Pack naming convention (retroactively suffix `CONTEXT_PACK.md` → `CONTEXT_PACK_TOPICS.md`). | Cosmetic-only change to a closed task's (T-019) deliverable. | Low. | Before a third `AnalysisType`. | Low |
