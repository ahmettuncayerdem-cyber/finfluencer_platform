# Entity-Centric Migration v2 — Project Closeout Report

**Date:** 2026-07-18
**Status:** Implementation frozen. No further migration work is proposed by this report. Reopen only if a production issue is discovered.

---

## 1. Completed Implementation

**Phase 0 — Canonical entity model.** `EntityType`, `EntityRecord`, `EntityVideoLinkRecord`, `CanonicalVideoRecord`, `CanonicalCommentRecord` (`core/contracts.py`) and `migration/backfill_entity_model.py` are implemented, tested, and re-validated against live production data (Step 0.1): 955 videos, 17,566 comments, 4 entities, zero cross-analyst duplication in the current corpus.

**Phase 3 — `AnalysisScope`, complete for its defined scope:**
- **Step 3.1:** `AnalysisScope`/`AnalysisScopeType` contract and `resolve_scope()`/`persist_scope()` (`scope.py`) — additive, non-breaking.
- **Step 3.2:** `run_topics()` resolves and persists `scope_id` on every row it writes. Real `topics.parquet`: 35,132/35,132 rows populated.
- **Step 3.2.5:** `scope_id` backfilled onto the pre-existing real `topics.parquet` via `migration/backfill_topic_scope.py`, with full backup/validate/write/re-verify discipline; all 20 checkpoint markers confirmed byte-identical before/after.
- **Step 3.3:** `run_topic_evolution()`'s production call site swapped to the scope-based resolver (`_resolve_scoped_topics_via_scope()`), after one deliberate rollback-and-retry cycle when the first attempt found real data lacking `scope_id` (resolved by Step 3.2.5). Validated via byte-level regression against a reconstructed pre-change snapshot and a 7-test resolver-equivalence suite with a negative control.
- **Step 3.4:** `analysis/topic_sentiment.py` generalized to carry `scope_id` through from `topics.parquet` into `topic_sentiment.parquet`. Verified against real data: 333/333 rows, all other columns byte-identical, `scope_id` populated and independently cross-checked correct across all 5 groups (pooled + 4 analysts).

This closes the specific defect the migration was undertaken to fix: `run_topics()` and `run_topic_evolution()` previously re-derived "which comments are in scope" through two independent join paths that could disagree. They now read the same persisted `scope_id`.

**Stabilization.** `pub_data_pull.py` and `final_health_report.py` were hardened to raise `CorpusValidationError` immediately on any missing or empty required input, closing an active defect where an empty `topic_evolution.parquet` silently produced the literal string `"nan"` in publication-grounding data, and a silently-misleading `0` in the health report.

**Step 5.1 audit.** All 19 root-level analysis scripts were checked for `topics.parquet`/`configuration` dependence. Four real readers were found and individually risk-classified; the two carrying active risk were resolved by stabilization above, the remaining two carry only latent (non-active) risk, described in §4.

---

## 2. Deferred Architectural Decisions

**ADR-0001 — `TopicEvolutionRecord.scope_id` deferral.** Formally documented, accepted decision: `scope_id` exists in the contract (added Step 3.1) but is never populated by `run_topic_evolution()`'s output. A repository-wide, exhaustive search found **zero runtime consumers** of this field anywhere in the codebase — nothing reads, filters, joins on, or depends on it. The decision: it remains intentionally unpopulated until a real `configuration`→`scope_id` cutover for evolution outputs is explicitly scheduled as its own piece of work — not assumed to be part of Step 3.4, which was scoped only to `TopicSentimentRecord`.

This is documented, not a gap discovered late: both Step 3.2's and Step 3.3's approval gates explicitly forbade the contract/producer change that would have populated it, and the field's own inline comment recorded non-population at the moment it was added.

A migration-plan patch (two small insertions into `Entity_Centric_Migration_Plan_v2.md`, disambiguating §4's language and correcting a stale line in §10's Step 3.3 entry) was prepared and is included in `ADR-0001_TopicEvolutionRecord_ScopeId_Deferral.md`. **It has not been applied to the roadmap document** — pending your confirmation, per the same approval discipline used throughout this project.

---

## 3. Remaining Operational Prerequisite

**`data/processed/topic_evolution.parquet` is currently empty (0 rows).** It was corrupted by a pre-existing test bug during Step 3.2 (a test called `run_topic_evolution()` without an explicit output path, silently overwriting the real file) and has never been regenerated, because doing so requires a real environment with `bertopic` installed — not available in this sandbox at any point in this project.

The code path is correct and validated at every layer this sandbox can reach: the resolver swap is proven byte-equivalent, the real `topics.parquet` has `scope_id` fully populated, all five required Tier-3 model-cache fingerprints have corresponding `.done` checkpoint markers present. What has never happened, in any environment, is an actual execution of `run_topic_evolution()` against a real, loadable BERTopic model. `Topic_Evolution_Regeneration_Runbook.md` was prepared with the exact commands, preconditions, and validation steps for this — **it has not been executed.**

Until this runs, `pub_data_pull.py` and `final_health_report.py` will correctly refuse to complete (by design, per the stabilization work above) — this is the intended, safe behavior, not a new defect.

---

## 4. Known Technical Debt

| ID | Item | Risk | Status |
|---|---|---|---|
| TD-0001 | `TopicEvolutionRecord.scope_id` unpopulated | None active (zero consumers, per ADR-0001) | Deferred, tracked |
| — | `export_master_table.py` filters `topics.parquet` by the literal `configuration` string rather than a `scope_id` join | Medium, latent only — `configuration` remains present and populated, never removed | Not urgent |
| — | `final_health_report.py` has the same latent `configuration`-string dependency | Medium, latent only | Not urgent (unrelated to the stabilization fix already applied to this file) |
| — | `pyproject.toml`'s CLI entry point (`finfluencer.cli:app`) points to a nonexistent `finfluencer/cli.py` | Low — confirmed broken, flagged repeatedly across this project, never fixed | Open, low priority |
| — | Roadmap document not yet updated with ADR-0001's patch | Low — documentation only | Open, pending approval |

Remaining migration phases (1, 2, 4, full Phase 5 cutover) were never started in this project. Per `Migration_Roadmap_Reassessment.md`'s own reprioritization, Phase 1/2 lost urgency once Step 0.1 confirmed the current corpus has zero duplication; they are not technical debt in the sense of an open defect, simply unstarted future scope. This report does not propose starting them.

---

## 5. Residual Risks

**Real BERTopic execution of the migrated code path has never occurred in any environment.** Every validation of Step 3.3's resolver swap was performed via resolver-level equivalence proofs, byte-level regression against synthetic and real-schema fixtures, and injected fake models in tests — never a live model. Strong circumstantial evidence (checkpoint markers and cache buckets present for all 5 required fingerprints; Step 3.2.5's independent fingerprint recomputation matched the real cached hash exactly) supports confidence this will succeed cleanly, but it is evidence, not confirmation.

**`topic_evolution.parquet` is empty until the runbook is executed.** Any consumer of that file is non-functional until then — correctly blocked, per §3, rather than silently wrong.

**No independent review has occurred at any layer of this migration.** All validation — hash checks, regression suites, resolver-equivalence proofs, the Step 5.1 audit, the `ADR-0001` consumer search — was performed by the same party that implemented the change. This is a process risk independent of the correctness evidence gathered.

**Single-developer project with sparse commit history** (flagged at the start of this migration in `Entity_Centric_Migration_Plan_v2.md`'s own risk table) — a correctness-critical data-model rewrite with limited bisectable history if a future issue needs tracing to its cause.

---

## 6. Declaration of Production Readiness

**Conditionally production-ready.**

Everything implemented in this project — Phase 0, Phase 3 Steps 3.1 through 3.4, and the stabilization work — is verified correct against real production data with reproducible, evidence-based validation at every step: row counts, byte-level regression, checkpoint and fingerprint integrity, and independent cross-checks of every new value against its source of truth. No known defect exists in any code path this sandbox has been able to exercise.

Production readiness is conditional on exactly one precondition, already fully specified and not requiring further design work: **execute `Topic_Evolution_Regeneration_Runbook.md` in a real environment with `bertopic` installed**, and complete its own validation and post-run verification steps. Until that runs, the platform's topic-evolution output remains empty and the two scripts that depend on it will correctly refuse to run — this is expected, documented, safe behavior, not an unknown risk.

Everything else documented in this report — `ADR-0001`'s deferral, the latent `configuration`-string dependencies, the broken CLI entry point, the unapplied roadmap patch — is disclosed, tracked, and assessed as non-blocking for production use of the completed scope.

This project is closed. No further migration work is proposed here. Reopening this initiative should be triggered only by a real production issue, the `topic_evolution.parquet` regeneration actually being run (which then completes the last open item in this report), or the future `configuration`→`scope_id` cutover named as `ADR-0001`'s own explicit trigger condition — not by default continuation.
