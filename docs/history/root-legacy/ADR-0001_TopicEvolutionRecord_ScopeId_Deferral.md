# ADR-0001: Defer Population of `TopicEvolutionRecord.scope_id`

**Status:** Accepted
**Date:** 2026-07-18
**Related Migration Steps:** 3.1 (field introduced), 3.2 (established the populate-only-with-consumer pattern for `TopicRecord`), 3.3 (resolver swap, contract explicitly frozen)
**Related audits:** Step 5.1 shadow-script audit; repository-wide `scope_id` consumer search (this session)

---

## Context

The entity-centric migration's Phase 3 introduced `AnalysisScope` to replace ad hoc, independently re-derived `configuration`/`analyst_key` scope resolution — the direct fix for the bug where `run_topics()` and `run_topic_evolution()` could disagree about which comments were in scope. Step 3.1 added `scope_id: str | None = None` additively to three records: `TopicRecord`, `TopicSentimentRecord`, `TopicEvolutionRecord`. Step 3.2 wired `scope_id` into `TopicRecord`/`topics.parquet` and its consumer (`_resolve_scoped_topics_via_scope()`). Step 3.3 swapped `run_topic_evolution()`'s resolver to read `topics.parquet`'s `scope_id` for filtering, under an explicit conservative approval gate.

## Problem

`TopicEvolutionRecord.scope_id` exists in the schema but is never populated by `run_topic_evolution()`'s output. The migration plan's §4 describes `TopicSentimentRecord` and `TopicEvolutionRecord` as undergoing "the same change" without distinguishing their actual implementation timelines, creating ambiguity about whether the null values are a bug, an oversight, or a deliberate deferral — and about which future step, if any, is responsible for closing the gap.

## Repository Evidence

- `core/contracts.py`, field definition: `scope_id: str | None = None  # Phase 3 - not yet populated (Step 3.1 status)` — the field's own author documented non-population contemporaneously, at the point it was added.
- Step 3.2's approval gate (verbatim, from this session): *"scope_id is additive metadata only, not yet an input to `_model_fingerprint()` or the Tier-2 checkpoint key."*
- Step 3.3's approval gate (verbatim): *"2. Do not modify either resolver implementation. 3. Do not modify AnalysisScope. 4. Do not modify contracts."*
- `topics/pipeline.py`'s record-building code inside `run_topic_evolution()` never assigns a `scope_id` key on any output record — confirmed by direct inspection.
- Real `data/processed/topics.parquet`: 35,132/35,132 rows have `scope_id` populated (`TopicRecord`, fully implemented).
- Real `data/processed/topic_evolution.parquet`: schema includes `scope_id`; every populated row would carry it as null under current code.
- Exhaustive repository search (this session) across `src/`, `tests/`, root scripts, and config: **zero** references read, filter, join on, or validate `TopicEvolutionRecord.scope_id`. The one real consumer found (`_resolve_scoped_topics_via_scope()`) reads `topics.parquet`'s `scope_id`, not the evolution output's.

## Decision

`TopicEvolutionRecord.scope_id` shall remain intentionally unpopulated until a real `configuration` → `scope_id` cutover for evolution outputs is scheduled. **This is not tied to Step 3.4** — Step 3.4 is explicitly scoped in the plan to `analysis/topic_sentiment.py`/`TopicSentimentRecord` only. The trigger is the cutover itself, as a named, explicitly approved piece of work, not any pre-existing step number.

## Rationale

Zero runtime consumers today means deferral carries no correctness risk. Both Step 3.2 and Step 3.3's approval gates explicitly and repeatedly forbade contract/producer changes for this exact field, establishing a deliberate pattern rather than an accidental gap. Populating a field with no reader would be speculative work, contrary to the migration's own "resolve once, persist, never re-derive" discipline — which was correctly applied to `TopicRecord` by wiring population *together with* its real consumer in Step 3.2, not ahead of one.

## Alternatives Considered

1. **Populate `scope_id` now, proactively.** Rejected — would have required modifying `TopicEvolutionRecord`'s producer, explicitly forbidden by every relevant approval gate; produces a field with no reader to validate it's even correct.
2. **Attribute this work to Step 3.4.** Rejected — Step 3.4 is explicitly and narrowly scoped to `TopicSentimentRecord`; folding this in would silently expand its documented boundary.
3. **Remove the `scope_id` field from `TopicEvolutionRecord` entirely until needed.** Rejected — a genuine breaking change to a contract every approval gate protected as additive-only; would just reproduce this decision later under time pressure.
4. **Leave the ambiguity undocumented.** Rejected — this is exactly the condition that created the need for this ADR.

## Consequences

**Positive:** no wasted implementation effort; contract stability preserved per established discipline; the plan's ambiguity is resolved by a decision that persists independent of the plan's own text; future work has a named, explicit trigger.

**Negative:** the field will sit visibly null in `topic_evolution.parquet` indefinitely until the cutover, which could confuse a reader unfamiliar with this decision — mitigated by this ADR, the roadmap patch (below), and the field's own inline comment.

## Future Trigger Conditions

Revisit this decision when either: (a) a real consumer is proposed that would read, filter, or join on `TopicEvolutionRecord.scope_id`, or (b) the `configuration` → `scope_id` cutover for evolution outputs is explicitly scheduled as its own approved piece of work.

---

## Migration Plan Patch (for `Entity_Centric_Migration_Plan_v2.md`)

Two minimal insertions, neither renumbering anything nor introducing a new step:

**Patch A — insert immediately after §4's existing paragraph 3** (the "`TopicSentimentRecord` and `TopicEvolutionRecord` generalization — same change..." paragraph):

> **Status note (post-Step 3.3, disambiguating the "same change" language above):** `TopicRecord.scope_id` (`topics.parquet`) is fully implemented, populated, and actively consumed as of Step 3.2/3.3. `TopicSentimentRecord.scope_id` and `TopicEvolutionRecord.scope_id` are **not** on the same timeline as each other despite being described together above. `TopicSentimentRecord`'s migration is Step 3.4's explicit scope (below). `TopicEvolutionRecord.scope_id` has no assigned step — it remains intentionally unpopulated, by design, because a repository-wide audit found zero runtime consumers of it (see `ADR-0001`). It will be populated only when a real `configuration`→`scope_id` cutover for evolution outputs is scheduled, not automatically alongside Step 3.4.

**Patch B — append to §10's existing Step 3.3 entry**, directly after the line *"Breaking changes (pending, not yet made): `TopicEvolutionRecord.configuration`+`analyst_key` → `scope_id`."*:

> *Correction, added post-Step 3.3 retry:* the breaking change listed above was never executed and is not scheduled as part of Step 3.3, 3.4, or any other currently-numbered step. Step 3.3 as actually approved and executed explicitly forbade contract modification. `TopicEvolutionRecord.scope_id` remains intentionally deferred — see `ADR-0001` and the Technical Debt Record (`TD-0001`). Do not read the line above as still-pending work assigned to this step.

*(Not applied to the file automatically — provided here for review before insertion.)*

---

## Technical Debt Record

| Field | Value |
|---|---|
| **ID** | TD-0001 |
| **Title** | `TopicEvolutionRecord.scope_id` intentionally unpopulated |
| **Description** | Contract field added in Step 3.1, never populated by `run_topic_evolution()`'s output records; `topic_evolution.parquet`'s `scope_id` column exists but is all-null in current and any freshly regenerated data. |
| **Current Risk** | None identified — zero runtime consumers found via exhaustive repository audit. |
| **Business Risk** | None currently. Would become non-zero only if a manuscript-facing report were built assuming `scope_id`-based joins against `topic_evolution.parquet` before population. |
| **Technical Risk** | Low — a future implementer unaware of this decision could assume Step 3.4 covers this field (the exact ambiguity this document resolves) and either skip needed work or duplicate effort. |
| **Owner** | Unassigned, pending cutover scheduling. |
| **Priority** | Low (deferred, not blocking). |
| **Trigger** | A real `configuration`→`scope_id` cutover for evolution outputs being explicitly scheduled, OR a new consumer being proposed that would read/filter/join on this field. |
| **Exit Criteria** | `TopicEvolutionRecord.scope_id` populated on every row of a freshly regenerated `topic_evolution.parquet`, under an explicit, separately approved migration step (not silently folded into Step 3.4), passing the Future Activation Checklist below. |
| **Verification** | Repository-wide consumer search re-run at cutover time to confirm the risk landscape hasn't changed; regression suite extended to assert non-null `scope_id` where it currently only checks old-vs-new equivalence (both null). |
| **Status** | **Deferred / Not Blocking / No Runtime Consumers.** |

---

## Future Activation Checklist

To be fully completed, in order, before `TopicEvolutionRecord.scope_id` is ever populated:

1. **Repository search** — re-run the exhaustive `scope_id`/`TopicEvolutionRecord` grep across `src/`, `tests/`, and root scripts to confirm the "zero consumers" finding still holds immediately before starting; do not assume this document's finding is still current without re-verifying.
2. **Consumer identification** — for whatever prompted the cutover, explicitly document what the new consumer is, where it lives, and exactly what it reads/joins/filters, to the same evidence standard used in this ADR.
3. **Backward compatibility** — decide and document whether `configuration`/`analyst_key` are retained as a computed alias (per the plan's own §6 pattern) or dropped; confirm `pub_data_pull.py` and `final_health_report.py` (already stabilized against `configuration`-based access) are updated or confirmed compatible before cutover.
4. **Migration strategy** — decide explicitly between (a) an additive change to `run_topic_evolution()`'s record-building code, mirroring how Step 3.2 wired `TopicRecord`, or (b) a one-time backfill script mirroring `backfill_topic_scope.py`'s pattern if historical rows need retroactive population; get this decision approved before implementation, per this project's established gate discipline.
5. **Data regeneration** — regenerate `topic_evolution.parquet` in a real `bertopic`-enabled environment (per `Topic_Evolution_Regeneration_Runbook.md`) if not already done by cutover time; verify regenerated `scope_id` values match what `resolve_scope()` would independently recompute for the same groups, mirroring `backfill_topic_scope.py`'s own idempotency-verification test.
6. **Regression tests** — extend `test_step3_3_regression.py` (or its successor) to assert `scope_id` is non-null and matches `topics.parquet`'s `scope_id` for the same group — closing the gap that the current suite never checks the evolution output's `scope_id` content; add a byte-level regression comparing pre/post-cutover output for every field except `scope_id` itself.
7. **Performance validation** — confirm the cutover doesn't change `run_topic_evolution()`'s fingerprint computation or cache-hit behavior, using the same fingerprint/cache-hit verification pattern already used for Step 3.3; confirm no unplanned refit is triggered.
8. **Documentation update** — mark this ADR Superseded (not deleted) by the ADR documenting the cutover; update the Migration Plan patch language accordingly; close TD-0001 with the Exit Criteria evidence attached.

---

## Architectural Consistency Review

| Dimension | Rating | Justification |
|---|---|---|
| **Contract consistency** | 🟢 Green | `TopicRecord`, `TopicSentimentRecord`, `TopicEvolutionRecord` all declare `scope_id` identically (`str \| None = None`), additive and non-breaking. No contract violates its own declared type — an all-null Optional field is valid under its own annotation. |
| **Schema consistency** | 🟡 Yellow | The on-disk schema matches its contract exactly (not broken), but is inconsistent with `topics.parquet`'s schema in a way easy to miss: the same field name is fully populated in one table and entirely null in a related one. Nothing crashes or produces wrong data — hence not Red — but it is a real, evidenced ambiguity a reader must know to check for. |
| **Behavioral consistency** | 🟢 Green | Every approval gate for Steps 3.2/3.3 explicitly required and verified byte-equivalence; the resolver swap changed nothing observable. `run_topic_evolution()`'s behavior today is provably identical to its pre-migration behavior except for the (irrelevant, unconsumed) `scope_id` column's mere presence. |
| **Migration consistency** | 🟡 Yellow | The roadmap's own §4 language ("same change") doesn't match what Steps 3.2/3.3 actually implemented for `TopicEvolutionRecord` specifically — the core ambiguity this document resolves. Not Red because the code itself is internally consistent and correct; Yellow because the planning document doesn't yet reflect the actual implementation history. |
| **Documentation consistency** | 🔴 Red (as the repository currently stands, before this ADR and its patch are applied) | The roadmap's Step 3.3 entry still lists the `TopicEvolutionRecord` schema change as "pending, not yet made" with no correction, and no ADR previously existed recording this deferral explicitly. This document — once its patch is applied to `Entity_Centric_Migration_Plan_v2.md` — resolves this to Green; until applied, the gap remains as described. |

---

## Executive Summary

**This is an intentionally deferred architectural decision, not a bug, and not ordinary technical debt in the sense of an unplanned shortcut** — though it is formally tracked as technical debt (TD-0001) for portfolio visibility, since that's the right instrument for surfacing deferred, non-urgent work regardless of how it originated.

The evidence supports this classification specifically, not the alternatives: it is not a bug, because both Step 3.2's and Step 3.3's approval gates explicitly and repeatedly forbade the exact change (contract/producer modification) whose absence is in question — code that faithfully honors an explicit constraint is not malfunctioning. It is not an unplanned shortcut, because the field's own inline comment documents non-population contemporaneously, at the moment the field was added in Step 3.1, before any pressure to cut corners could have applied. And it is not currently risky, because an exhaustive, repository-wide search — not an assumption — found zero code anywhere that reads, filters, joins on, or depends on this field. The only real defect found in this entire investigation was documentary: the migration plan's own language implied a shared timeline for two records that were, in practice, deliberately split — which is what this ADR and its patch exist to correct.

No source code was modified to produce this document.
