# Entity-Centric Architecture Migration Plan — Finfluencer Research Platform v1.0 → v2.0

**Role:** Lead Software Architect implementation plan. Design only — no code is written or modified by this document.

**Method note, stated up front because it changes the whole plan:** this is not a green-field design exercise. Direct inspection of the repository for this plan found that **Phase 0 of the entity-centric migration is already implemented**, not merely proposed: `core/contracts.py` already defines `EntityType`, `EntityRecord`, `EntityVideoLinkRecord`, `CanonicalVideoRecord`, and `CanonicalCommentRecord` as additive Pydantic schemas (lines 543–671), and `migration/backfill_entity_model.py` (302 lines, with a companion test file) already implements a working, idempotent backfill that derives all four canonical tables from the current `videos.parquet`/`comments.parquet`, including a careful consistency check that refuses to silently deduplicate a video/comment whose fixed fields disagree across duplicate rows, and a specific, already-validated exemption for volatile snapshot metrics (views/likes/comment_count, resolved by taking the max observed value — confirmed against production data where 7 real multi-entity videos differ only in these fields). This plan therefore starts from "Phase 0 done, verify and build on it," not from zero. Nothing downstream of Phase 0 — no collection stage, no preprocessing/embeddings/sentiment stage, no topic-modelling stage, no config file — has been changed to read from or write to the new tables yet. `analysts.yaml` is still the live, sole configuration source; `run_pipeline()` in `collect/main.py` still orchestrates the original ten stages (`channels`, `videos`, `comments`, `preprocess`, `embeddings`, `sentiment`, `topics`, `topic_sentiment`, `topic_evolution`, `transcripts`) entirely against the analyst-partitioned tables.

---

## 1. CURRENT ARCHITECTURE

**Partition key:** `analyst_key`, baked into every stage as an implicit loop variable or DataFrame column — not a first-class, queryable relationship.

**Data flow (as implemented today):**

```
analysts.yaml (roster of 4 named creators)
        │
   collect_channels()  ──► channels.parquet
        │
   collect_videos()    ──► videos.parquet        (analyst_key column; a video shared by
        │                                          two analysts appears as two rows)
   collect_comments()  ──► comments.parquet       (checkpoint key includes analyst_key;
        │                                          a shared video's comments are fetched
        │                                          and stored once per owning analyst)
   run_preprocessing() ──► comments.parquet (text_clean populated in place)
        │
   run_embeddings()    ──► per-analyst-key loop, one Tier-2 checkpoint stage per key
        │
   run_sentiment()     ──► per-analyst-key loop, one Tier-2 checkpoint stage per key
        │
   run_topics()        ──► configuration ∈ {"pooled", "within_analyst"} (a string, not
        │                   a persisted, content-addressed scope)
   run_topic_evolution()──► independently re-derives its own comment-set fingerprint by
                             re-joining the same tables through a different path than
                             run_topics() does
```

**Consequence, as originally measured in production data (per `entity_centric_platform_architecture.md`):** 144 videos were attributed to more than one `analyst_key`, producing roughly 4,750–4,756 duplicated comment rows, which propagated into `sentiment.parquet` and into two independently-computed BERTopic fingerprints (`run_topics` vs. `run_topic_evolution`) that disagreed with each other because each joined the same duplicated rows through a different path. **Correction (Step 0.1 re-validation, see §10):** this specific duplication was fully explained by a `basaran`/`gecer` channel-collision bug, already fixed by re-collecting `basaran` under its correct channel — the current corpus (955 videos, 17,566 comments) has zero cross-analyst duplication. The fingerprint-disagreement mechanism described above remains a real, latent code-level defect (two functions independently re-deriving a fingerprint through different join paths will disagree the moment duplication *does* occur again), which is why Phase 3 below still stands; only the "already measured/144 videos" framing needed correcting.

**What is *not* broken and should not be touched:** `core/registry.py`'s `(kind, key) → class` plugin pattern is entity-agnostic already and is the mechanism the target architecture extends, not replaces. `core/checkpoint.py`'s `CheckpointManager` is also already entity-agnostic at the primitive level — `should_run(stage_name, config_slice)` has no notion of "analyst" built into it. The analyst-partitioning happens one layer up, in the calling code that constructs `stage_name` and `config_slice` per analyst key (e.g. inside `embeddings/pipeline.py`, `sentiment/pipeline.py`, `topics/pipeline.py`). This is an important, favorable finding for the migration: **the checkpoint infrastructure itself needs no changes; only the call sites that currently parameterize it by `analyst_key` need to stop doing so.**

---

## 2. TARGET ARCHITECTURE

Governing principle (unchanged from the existing design document, restated because every decision below follows from it): *videos and comments are physical facts that exist exactly once; entities are labels attached to videos through an explicit many-to-many relationship; every downstream computation over comments operates on deduplicated content and is parameterized by an explicit, persisted, reproducible scope, never by an implicitly re-joined entity column.*

**Data flow (target):**

```
entities.yaml (any number of entities: creators, topics, campaigns, events)
        │
   resolve_membership()  ──► entity_video_link.parquet  (many-to-many, entity_key × video_id)
        │                     (per-entity: eligible, selected, matched_via, criteria_version)
   collect_videos()   ──► videos_canonical.parquet   (deduplicated union of video_ids
        │                  across ALL configured entities — fetched once, ever)
   collect_comments() ──► comments_canonical.parquet (deduplicated, no analyst_key column)
        │
   run_preprocessing()──► single global pass, comment_id-keyed, no per-entity loop
   run_embeddings()   ──► single global pass, comment_id-keyed, no per-entity loop
   run_sentiment()    ──► single global pass, comment_id-keyed, no per-entity loop
        │
   resolve_scope(entity_keys=[...], filters={...})  ──► AnalysisScope
        │              (resolved_comment_ids_hash computed ONCE, persisted)
   run_topics(scope_id) ──► topics.parquet (keyed by scope_id, not "configuration" string)
   run_topic_evolution(scope_id) ──► reads the SAME persisted resolved_comment_ids_hash;
                                       never re-derives it — this is the direct, structural
                                       fix for the fingerprint-mismatch bug
```

**What becomes possible that isn't today:** an `entity_type="topic"` entity (e.g. "earthquake coverage") or `entity_type="campaign"` entity can be defined and analyzed using the exact same collection/processing/topic-modelling code, with zero changes to those stages — only a new membership resolver and a config entry. This is the concrete mechanism by which the platform becomes "domain-agnostic" rather than "the four-analyst platform plus an extra table."
---

## 3. DATABASE REDESIGN

**Scope decision, stated explicitly:** this migration is a *data-model* redesign, not a switch from files to a relational database engine. The platform remains parquet-file-based in v2.0; introducing SQLite/Postgres is a separate, larger decision (flagged in the prior engineering audit's gap analysis as a v3.0/v4.0-tier item) and is deliberately out of scope here, because conflating "fix the partition-key bug" with "adopt a database engine" would roughly double this migration's risk and timeline for no benefit the entity-centric model actually requires. The tables below are parquet files exactly as `videos_canonical.parquet` / `comments_canonical.parquet` / `entities.parquet` / `entity_video_link.parquet` already are today.

**Table inventory, old vs. new:**

| Table (current) | Status | Table (target) | Status |
|---|---|---|---|
| `channels.parquet` | Unchanged | `channels.parquet` | Unchanged |
| `videos.parquet` (analyst-partitioned) | Deprecated behind compat view (§6) | `videos_canonical.parquet` | **Already implemented** (Phase 0) |
| `comments.parquet` (analyst-partitioned) | Deprecated behind compat view | `comments_canonical.parquet` | **Already implemented** (Phase 0) |
| — | New | `entities.parquet` | **Already implemented** (Phase 0) |
| — | New | `entity_video_link.parquet` | **Already implemented** (Phase 0) |
| — | New | `analysis_scope.parquet` | **Not yet implemented** — new in this plan |
| `sentiment.parquet` | Schema unchanged, source dedup'd | `sentiment.parquet` | Unchanged schema, new upstream source |
| `embeddings_index.parquet` | Schema unchanged | `embeddings_index.parquet` | Unchanged |
| `topics.parquet` (`configuration` column) | Column renamed/generalized | `topics.parquet` (`scope_id` column) | New in this plan |
| `topic_sentiment.parquet` | `configuration`+`analyst_key` columns | `topic_sentiment.parquet` (`scope_id`) | New in this plan |
| `topic_evolution.parquet` | `configuration`+`analyst_key`, re-derived fingerprint | `topic_evolution.parquet` (`scope_id`, persisted fingerprint) | New in this plan |

**Why `analysis_scope.parquet` is the one genuinely new table this plan adds beyond what Phase 0 already built:** Phase 0 solved the collection-side duplication (one video, one row). It did not yet solve the analysis-side fingerprint-mismatch bug, because that bug lives in how `run_topics` and `run_topic_evolution` each independently decide "which comments are in scope" — today via `configuration ∈ {"pooled","within_analyst"}`, a string that gets re-resolved by a fresh join every time it's used. `AnalysisScope` replaces that string with a persisted row: a scope is resolved once, its member `comment_id` set is hashed and stored, and every later reader of that scope loads the stored hash rather than recomputing it. This is the direct structural fix for the specific bug that motivated this whole migration in the first place, and it is the one piece of the target design that Phase 0 did not touch.

**Storage-layout note (deferred, not decided here):** at multi-million-comment scale, partitioning `comments_canonical`/`sentiment`/embeddings by ingestion date or a `video_id` hash-bucket becomes necessary, since a comment no longer has a single owning entity to partition by. At the current corpus size (17,566 comments) this is not a v2.0 concern and is flagged only so it isn't silently forgotten when the platform scales.

---

## 4. DATA CONTRACTS REDESIGN

**Already done (verified in `core/contracts.py`, lines 543–671):**

- `EntityType` (enum: `creator`, `topic`, `campaign`, `event`, `custom`)
- `EntityRecord` (`entity_key`, `entity_type`, `membership_strategy`, `membership_params`, `study_id`, …)
- `EntityVideoLinkRecord` (`entity_key`, `video_id`, `matched_via`, `eligible`, `selected`, `criteria_version`, …)
- `CanonicalVideoRecord` (video-intrinsic fields only, no `analyst_key`)
- `CanonicalCommentRecord` (comment-intrinsic fields only, no `analyst_key`)

All five are additive — `AnalystRecord`, `VideoRecord`, `CommentRecord` remain in `__all__` unmodified, exactly as the project's own schema-change discipline (documented in the module docstring: contract violations are bugs in a producer, changes require explicit versioning) requires.

**Still needed (new work for this plan, not yet in the codebase):**

1. **`AnalysisScope`** — the one new contract this plan requires:
   - `scope_id: str` (PK, content hash of the fields below)
   - `scope_type: Enum` (`entity`, `entity_set`, `global`, `filtered`)
   - `entity_keys: list[str]`
   - `filter_params: dict[str, Any]`
   - `resolved_comment_ids_hash: str` (SHA-256 of the sorted, deduplicated comment_id list, computed once at resolution time)
   - `resolved_at: str` (ISO 8601)
   - `criteria_version: str`

2. **`TopicRecord` generalization** — replace the free-text `configuration: str` field with `scope_id: str`, referencing `AnalysisScope`. Because `TopicRecord` is a *data-record* schema (validated per-row, opt-in), this is a genuine breaking change to the field's meaning, not just an addition — it must be versioned explicitly (see §6). The `topic_tier`/`topic_label`/`topic_prob` fields are unaffected.

3. **`TopicSentimentRecord` and `TopicEvolutionRecord` generalization** — same change: `configuration` + `analyst_key` (nullable, populated only for `within_analyst`) collapse into a single `scope_id`. This is a strict simplification of the schema (two fields become one), which is itself evidence the current design is more complex than the underlying concept requires.

4. **`MembershipResolverConfig`** (new, small) — the Pydantic shape of `EntityRecord.membership_params` per resolver type, so that a `creator` entity's `{"channel_ids": [...]}` and a `topic` entity's `{"keywords": [...], "date_range": [...]}` are validated, not just passed through as an untyped `dict[str, Any]` as they are in the Phase 0 schema today. This was reasonably deferred in Phase 0 (no resolver besides `creator` exists yet to validate against) but becomes necessary the moment Phase 4 (below) introduces a second resolver type.

5. **`entities.yaml` top-level config schema** (new, parallel to `AnalystRoster`) — validates the new config file format (§6 covers the migration path from `analysts.yaml`).
---

## 5. MIGRATION STRATEGY

Six phases, numbered to match the existing design document so prior planning stays traceable. Phase 0 is marked complete based on direct code inspection; phases 1–5 are this plan's actual scope.

**Phase 0 — Additive canonical tables + backfill.** ✅ **Implemented, tested, and re-validated against live data (Step 0.1, §10).** (`core/contracts.py`, `migration/backfill_entity_model.py`, `tests/unit/test_migration/test_backfill_entity_model.py`). Re-run against current production `data/raw/{videos,comments,channels}.parquet` (955 videos, 17,566 comments, 4 entities): `n_multi_entity_videos = 0`, `n_duplicate_comment_rows_collapsed = 0` — the corpus is currently duplicate-free (the previously-cited 144-video/~4,750-comment figures were stale, explained by an already-fixed `basaran`/`gecer` channel-collision bug; see §10, Step 0.1 for the full correction). The backfill script itself runs correctly and idempotently against real data either way; Phase 1 can proceed.

**Phase 1 — Rewrite collection stages to consume/produce canonical tables.** `collect_videos()` and `collect_comments()` change from "iterate this analyst's videos" to "iterate the deduplicated `video_id` set unioned across every entity currently configured, fetch each exactly once." `EntityVideoLink` population becomes a separate, cheap, idempotent step per entity's membership resolver, decoupled from the API-calling collection stages. *Why necessary:* this is where the actual quota/API savings and the elimination of duplicate fetches happen — Phase 0 fixed the data model retroactively (backfill from already-duplicated data); Phase 1 stops the duplication from happening on the next collection run. *Difficulty:* Medium — the resolver-then-collect ordering is a real control-flow change to `run_pipeline()`, but the underlying API-calling logic in `providers/platform/youtube.py` is untouched. *Breaking changes:* `collect/videos.py`, `collect/comments.py` signatures change (analyst-keyed loop replaced by a deduplicated video-ID-set loop); `run_pipeline()`'s stage sequence gains a new `resolve_membership` stage before `videos`.

**Phase 2 — Rewrite preprocessing/embeddings/sentiment as single global passes.** Drop the per-`analyst_key` loop in `embeddings/pipeline.py` and `sentiment/pipeline.py` entirely; one cache-first pass over `comments_canonical`, keyed by `comment_id`. *Why necessary:* this is a straightforward simplification once Phase 1 supplies deduplicated input — there is no longer a reason to loop by analyst at all, since a comment has no owning analyst in the target model. *Difficulty:* Low-Medium — mechanically, this *removes* code (the per-key looping/checkpoint-naming logic) rather than adding it, which is unusual for a migration and worth noting as a genuine simplification, not just a refactor. *Breaking changes:* checkpoint stage names change shape (no longer `f"embeddings_{analyst_key}"`-style keys), which invalidates all existing checkpoints for these stages on first run post-migration — expected and acceptable (re-running embeddings/sentiment on 17,566 comments is cheap relative to re-collecting from the API), but should be called out explicitly in the release notes so it isn't mistaken for a bug.

**Phase 3 — Generalize the analysis layer via `AnalysisScope`.** Implement `resolve_scope()` (new function, new module — see §9) that takes `entity_keys`/`filter_params`, resolves the member `comment_id` set exactly once, persists it as an `AnalysisScope` row, and returns `scope_id`. `run_topics()`, `run_topic_sentiment()`, `run_topic_evolution()` all take `scope_id` instead of `configuration`. *Why necessary:* this is the direct fix for the fingerprint-mismatch bug that motivated the entire migration — without this phase, Phases 1–2 fix collection-side duplication but leave the analysis-side bug exactly as it is today, since that bug is about re-derivation, not duplication. *Difficulty:* Medium-High — `topics/pipeline.py` (683 lines, the largest file in the package) needs careful surgery to swap its fingerprinting logic without changing its actual topic-modelling behavior, and topic evolution's read path must be rewritten to *read* the persisted hash rather than *compute* it. *Breaking changes:* `TopicRecord`/`TopicSentimentRecord`/`TopicEvolutionRecord` schema change (§4); any downstream script (including the shadow analysis pipeline identified in the prior engineering audit) that reads `topics.parquet`'s `configuration` column breaks and must be updated to read `scope_id` joined against `analysis_scope.parquet`.

**Phase 4 — Entity-type registry: topic/campaign/event resolvers.** Implement membership resolvers beyond `creator` (keyword/query matching for `topic`, date-range+hashtag for `campaign`), registered via the existing `core/registry.py` pattern under a new `"membership_resolver"` kind namespace. *Why necessary:* this is the phase that actually delivers on "domain-agnostic platform" — everything before this fixes correctness bugs on the existing four-creator study; this is what makes a new, different study (e.g. an event-based corpus) possible without touching collection/processing code. *Difficulty:* Medium — each resolver is a bounded, independent unit of new logic; the risk is entirely in resolver-specific edge cases (e.g. what does "eligible" mean for a keyword-matched video that also happens to be a Short?), not in the surrounding architecture. *Breaking changes:* none to existing `creator`-type entities; purely additive.

**Phase 5 — Cutover and deprecation.** Re-point any remaining downstream consumers (the shadow analysis pipeline identified in the prior audit, any manuscript-table-building scripts) at the new tables; mark `videos.parquet`/`comments.parquet`/the `configuration`-keyed analysis tables as deprecated behind the compatibility view (§6) for one full release cycle before physical removal. *Why necessary:* this is what makes the migration actually complete rather than "the new tables exist alongside the old ones forever," which would leave the platform in a permanent, more-complex-than-either-alternative intermediate state. *Difficulty:* Low technically, High in coordination — the actual code change is small, but it requires auditing every consumer (including the ~15 unpackaged shadow scripts from the prior engineering audit, which is exactly why that audit's own top recommendation — package the shadow pipeline first — should be sequenced before or alongside this phase, not after it). *Breaking changes:* by design, at the end of the deprecation window — this is the one phase where "breaking" is the intended, scheduled outcome, not a risk to mitigate.

---

## 6. BACKWARD COMPATIBILITY

- **Compatibility view, not a physical table.** Reconstruct the old analyst-centric shape (`comment × analyst_key`, duplicated exactly as before, if a legacy script expects that) as an on-demand join of `comments_canonical ⋈ entity_video_link ⋈ videos_canonical`, filtered to `entity_type="creator"`. Existing downstream scripts keep working unmodified against this view while new code targets the canonical tables directly. This view is a function, not a materialized file — it should live in a small new module (§9) rather than as a maintained duplicate dataset.
- **Config migration.** `analysts.yaml` becomes `entities.yaml` with an `entity_type` discriminator, via a one-time, mechanical, lossless transform: every existing analyst becomes an `entity_type="creator"` entity with its channel ID as `membership_params.channel_ids`. `config.py`'s `load_settings()` should accept *either* file for one release cycle, auto-wrapping a detected `analysts.yaml` into the new shape and emitting a deprecation warning — not silently, and not by hard-failing on the old format immediately.
- **Contracts.** Continue the pattern Phase 0 already established: new schemas are additive (`AnalysisScope` alongside, not replacing, anything), and the two genuinely breaking schema changes identified in §4 (`TopicRecord.configuration` → `scope_id`, and the equivalent on `TopicSentimentRecord`/`TopicEvolutionRecord`) should ship with both field names accepted for one release (old field populated via a computed alias) rather than a hard cutover in a single release.
- **CLI/pipeline stage names.** `run_pipeline(stage=...)`'s valid stage list grows (`resolve_membership`, `resolve_scope`) but no existing stage name is removed or repurposed to mean something different — a script calling `run_pipeline(stage="topics")` continues to work, it simply now requires a `scope_id` to have been resolved first (with a clear, actionable error message if it hasn't, per the existing `require_done()` pattern in `CheckpointManager`).
---

## 7. RISKS

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Silent data loss during dedup (two rows for the same `video_id`/`comment_id` disagree on an intrinsic field and one value is silently dropped) | Low | High | Already mitigated by design — `_assert_consistent()` in the existing `backfill_entity_model.py` raises `ValueError` rather than guessing. This behavior must be preserved, not relaxed, when Phase 1 rewrites live collection (not just the one-time backfill) to do the same deduplication. |
| Fingerprint/behavior drift: Phase 3's `AnalysisScope` resolves a *different* comment set than the current `configuration="pooled"` path did, silently changing published results | Medium | High | Before Phase 3 ships, run both the old and new resolution paths against the current dataset and assert the resulting comment-ID sets are identical (not just equal in count) — this is a one-time validation, not ongoing test infrastructure, but it is the single highest-value check in this entire plan given a manuscript has already been built on the old path's output. |
| Checkpoint invalidation on Phase 2 cutover forces a full re-run of embeddings/sentiment/topics | High (expected) | Low | Not really a risk — flagged in §5 as an expected, one-time cost. Communicate it in release notes so it isn't debugged as a bug. |
| Scope creep: Phase 4's resolver types (topic/campaign/event) are the most conceptually interesting part of this plan and the easiest to over-invest in before Phases 1–3 are solid | Medium | Medium | Sequence strictly — no resolver-type work starts until Phase 3's scope-fingerprint fix is validated against the existing corpus, per the Part 7 final recommendation of the prior engineering audit (fix correctness before adding capability). |
| The shadow analysis pipeline (root-level scripts, per the prior engineering audit) silently keeps reading the old `topics.parquet`'s `configuration` column after Phase 3 ships, producing a manuscript table from stale or schema-mismatched data without erroring loudly | Medium-High | High | This is the most concrete, paper-relevant risk in the whole plan. It argues for sequencing the prior audit's own top recommendation — package the shadow pipeline into `finfluencer.reporting` — either just before or in parallel with this migration, specifically so there is exactly one place, not fifteen scripts, that needs to be checked and updated when `topics.parquet`'s schema changes. |
| Single-developer project, only two git commits recorded to date, doing a correctness-critical rewrite of the platform's central data model | Medium | High | Procedural, not technical: commit each phase (or sub-phase) separately with a working, test-passing state, specifically so that if Phase 3's validation check (above) fails, the failure can be bisected to a specific change rather than debugged against a multi-week, multi-file diff. This is the one recommendation in this plan that is about process rather than architecture, and it is here because the project's own git history shows it hasn't been the default practice so far. |
| BERTopic/UMAP scaling ceiling reached sooner because Phase 4's `entity_set`/`global` scopes make "run topic modelling over everything" a one-line request that wasn't easily expressible before | Low at current scale (17,566 comments), rising with adoption | Medium | Already flagged as an explicit, separate workstream in the existing design document (§8 there) — not a reason to change this plan, but a reason to not silently assume Phase 3's scope mechanism is a performance-neutral change at larger corpus sizes. |
| Test coverage gap: the prior engineering audit found 48.6% line coverage platform-wide, concentrated away from exactly the modules this plan touches most (`topics/pipeline.py`, `collect/`) | Medium | Medium-High | Each phase in §5 should ship with new or updated tests covering the specific behavior it changes, not just the happy path — particularly a test asserting `run_topics` and `run_topic_evolution` resolve to the *same* `resolved_comment_ids_hash` for the same `scope_id`, since that specific invariant is the entire point of Phase 3. |
---

## 8. REQUIRED FILE MODIFICATIONS

Every file below is a real, existing file in `src/finfluencer/` (paths verified against the current tree). "None" entries are listed explicitly to record what does *not* need to change — equally important information for scoping this work.

| File | Change required | Phase |
|---|---|---|
| `core/contracts.py` | Add `AnalysisScope`; generalize `TopicRecord`/`TopicSentimentRecord`/`TopicEvolutionRecord` (`configuration`+`analyst_key` → `scope_id`, with a transitional alias per §6); add `MembershipResolverConfig` variants | 3, 4 |
| `core/config.py` | Accept `entities.yaml` alongside `analysts.yaml`; auto-wrap old format with a deprecation warning | 1 |
| `core/registry.py` | **None** — already generic; register new resolvers under a new `"membership_resolver"` kind, no changes to the registry mechanism itself | 4 |
| `core/checkpoint.py` | **None** — already entity-agnostic at the primitive level (see §1) | — |
| `collect/channels.py` | Minimal — output still one row per channel; no analyst-partitioning to remove here | 1 |
| `collect/videos.py` | Rewrite: iterate deduplicated `video_id` set unioned across configured entities, not per-analyst loop; write to `videos_canonical.parquet` | 1 |
| `collect/comments.py` | Rewrite: fetch per unique `video_id` only (checkpoint key drops `analyst_key`); write to `comments_canonical.parquet` | 1 |
| `collect/transcripts.py` | **None required for this migration** — already video-keyed, not analyst-partitioned; separately flagged in the prior engineering audit as an unused/orphaned feature, worth a decision independent of this plan | — |
| `collect/quota.py` | **None** — quota tracking is API-call-count-based, not analyst-partitioned | — |
| `collect/main.py` | Add `resolve_membership` and `resolve_scope` stages to `run_pipeline()`'s stage list and orchestration logic; existing stage names/behavior otherwise preserved per §6 | 1, 3 |
| `preprocess/pipeline.py` | Remove per-`analyst_key` loop; single global pass over `comments_canonical` | 2 |
| `embeddings/pipeline.py` | Remove per-`analyst_key` loop and per-key checkpoint naming; single global cache-first pass | 2 |
| `sentiment/pipeline.py` | Same as `embeddings/pipeline.py` | 2 |
| `topics/pipeline.py` (683 lines, largest file in the package) | Most invasive change in this plan: replace `configuration` string handling with `scope_id`; rewrite `run_topic_evolution()` to read the persisted `resolved_comment_ids_hash` instead of re-deriving it — this is the literal fix for the bug that motivated the migration | 3 |
| `topics/bertopic_runner.py` | **None** — the BERTopic wrapper itself is fingerprint-agnostic; only its caller (`pipeline.py`) changes what it passes in | — |
| `analysis/topic_sentiment.py` | Generalize `(configuration, analyst_key)` grouping to `scope_id` grouping | 3 |
| `market/*.py` (all six files) | **None** — the market subpackage consumes the pooled sentiment index, not analyst-partitioned comment data directly; already the platform's best-isolated subpackage per the prior engineering audit, and this migration is a further, independent confirmation of that isolation | — |
| `migration/backfill_entity_model.py` | **None required to *run*** — already complete; may warrant a follow-up "Phase 5 cutover" sibling script (see §9) that is new, not a modification of this file | — |
| `providers/platform/*.py`, `providers/language/*.py`, `providers/market/*.py` | **None** — providers operate below the entity/video/comment layer entirely; this migration doesn't touch what a provider does, only how its output is assembled | — |
| `utils/dedup.py`, `utils/hashing.py`, `utils/io.py`, `utils/time.py` | **None expected** — `utils/hashing.py` (368 lines, already the platform's largest utility module) is a candidate to *reuse*, not modify, for computing `resolved_comment_ids_hash` in the new scope-resolution module | — |
| `config/analysts.yaml` | Superseded by `config/entities.yaml`; retained read-only for the one-release compatibility window per §6 | 1 |
| `config/settings.yaml` | Minor addition: a `providers.membership_resolver` or equivalent default-resolver setting, mirroring the existing `providers.language`/`providers.platform` pattern | 4 |
| `pyproject.toml` | Separately from this migration (flagged in the prior engineering audit): fix the broken `finfluencer.cli:app` entry point. Not required by this plan technically, but doing it in the same release is close to free and removes one more reason a new contributor's first experience with the platform is an error | — |

## 9. REQUIRED NEW MODULES

| New module | Purpose | Phase |
|---|---|---|
| `finfluencer.entities` (new subpackage) | Membership resolver registry and implementations: `creator` (ports the logic already implicit in Phase 0's backfill), `topic`, `campaign`, `event`, `custom`. Each resolver's sole job is producing `EntityVideoLinkRecord` rows — it never calls collection/processing code directly. | 1 (creator only), 4 (others) |
| `finfluencer.entities.scope` (or `finfluencer.scope` as a top-level module — naming is a minor decision, not made here) | `resolve_scope(entity_keys, filter_params) -> AnalysisScope`: the single place `resolved_comment_ids_hash` is computed. Every stage that needs "which comments are in scope" calls this once and persists the result; nothing downstream re-derives it. This is the module that directly implements the fingerprint-mismatch fix. | 3 |
| `finfluencer.compat` (new, small) | The backward-compatibility view described in §6 — an on-demand join reconstructing the old analyst-centric shape from the new canonical tables, so legacy scripts (including, until they're migrated, the shadow analysis pipeline) keep working. Deliberately kept separate from `finfluencer.entities` so it can be deleted cleanly at the end of the deprecation window without touching the permanent modules around it. | 5 |
| `finfluencer.migration.cutover_entity_model` (new script, sibling to the existing `backfill_entity_model.py`, not a modification of it) | Phase 5's one-time cutover: audits remaining readers of the deprecated tables, emits a report of what still needs migrating (explicitly including the shadow analysis pipeline's ~15 scripts as named targets), and — only once that report is clean — performs the physical deprecation. | 5 |

Every other capability this plan needs (`AnalysisScope` persistence, checkpoint keying, provider registration) is served by extending existing modules listed in §8, not by new ones — the target architecture adds exactly three new subpackages/modules to the platform, which is a deliberately small footprint for a change of this structural significance.
---

## 10. STEP-BY-STEP IMPLEMENTATION ROADMAP

Thirteen steps across the six phases. Each step states why it's necessary, difficulty, expected benefit, and possible breaking changes, so the roadmap can be picked up, paused, or reviewed step-by-step rather than as one large change.

**Step 0.1 — Re-validate Phase 0 against live production data.** ✅ **DONE.**
*Why:* the existing backfill has only been confirmed against test fixtures in this review; it must be run against the real `videos.parquet`/`comments.parquet` before anything is built on top of it. *Difficulty:* Trivial (the function already exists and is idempotent). *Breaking changes:* none — read-only, additive output.

*Result, and a correction to this plan's own motivating figures:* the "144-video / ~4,750-comment" duplication numbers cited earlier in this document (§0, §5) were **stale at the time this plan was written** and did not reflect the data current as of this validation run. Running `backfill_entity_model()` against the real `data/raw/{videos,comments,channels}.parquet` (955 videos, 17,566 comments, 4 entities) produced `n_multi_entity_videos = 0` and `n_duplicate_comment_rows_collapsed = 0` — no duplication in the current corpus. Root cause, per `basaran_rebuild_orchestration_plan.md` (already in the repo, predating this plan): the 144-video figure was entirely explained by a `basaran`/`gecer` channel-collision bug, since fixed by re-collecting `basaran` under its correct channel handle. Today's corpus is duplicate-free across all four analysts.

This does **not** invalidate the entity-centric migration or count as the "blocking issue" that would warrant redesign — multi-entity videos remain structurally possible (e.g. a guest-appearance video two analysts legitimately both cover), and the topic-evolution fingerprint-mismatch bug (§0, the actual motivating defect) is a latent code-level defect independent of whether the current corpus happens to trigger the duplication case. It does mean this plan's own cited justification numbers were wrong and are corrected here rather than carried forward silently. Existing fixture-based test suite (9 tests, `tests/unit/test_migration/test_backfill_entity_model.py`) re-run clean, unchanged. No repository files were modified by this step — output was written to a scratch location only, per the read-only scope of this step; persisting `entities.parquet`/`entity_video_link.parquet`/canonical tables into the repo is deferred to Step 1.1, where they are first actually consumed.

**Step 1.1 — Implement the `creator` membership resolver as a standalone function.**
*Why:* Phase 1 needs a resolver to call before it can rewrite collection; starting with `creator` only (which Phase 0's backfill already implements the logic for, just not as a registered, reusable resolver) is the lowest-risk first slice. *Difficulty:* Low — mostly extracting existing logic into `finfluencer.entities`. *Benefit:* first real use of the registry pattern for this purpose, validated against the one entity type already well understood. *Breaking changes:* none yet — not wired into `run_pipeline()` this step.

**Step 1.2 — Rewrite `collect_videos()`/`collect_comments()` to consume `EntityVideoLink` output.**
*Why:* this is where the actual API-call and storage duplication stops happening going forward. *Difficulty:* Medium. *Benefit:* immediate, measurable reduction in duplicate API calls and storage on the very next full collection run. *Breaking changes:* function signatures change; any external caller of these two functions directly (rather than through `run_pipeline()`) must update.

**Step 1.3 — Add `resolve_membership` stage to `run_pipeline()`.**
*Why:* wires Steps 1.1–1.2 into the actual CLI/orchestration path researchers use. *Difficulty:* Low. *Benefit:* the migration becomes usable end-to-end for `creator`-type entities, i.e. functionally equivalent to today's platform but on the new data model. *Breaking changes:* `run_pipeline()`'s valid-stage list grows; existing `stage="videos"`/`stage="comments"` calls now require `resolve_membership` to have run first, with a clear error if it hasn't (mirroring `CheckpointManager.require_done()`'s existing pattern).

**Step 2.1 — Remove the per-analyst loop from `preprocess/pipeline.py`.**
*Why:* lowest-risk of the three Phase 2 stages to convert first (no model-loading cost, easiest to verify output equivalence against the old path). *Difficulty:* Low. *Benefit:* proves the "single global pass" pattern before applying it to the more expensive embeddings/sentiment stages. *Breaking changes:* checkpoint keys for this stage change shape (expected, per §7).

**Step 2.2 — Remove the per-analyst loop from `embeddings/pipeline.py` and `sentiment/pipeline.py`.**
*Why:* same pattern as 2.1, applied to the two most compute-expensive stages — where eliminating redundant per-entity recomputation actually saves meaningful time/cost, not just code complexity. *Difficulty:* Medium (more moving parts: batch sizing, GPU memory budgeting via `core/budgets.py` interacts with batch construction). *Benefit:* this is the step where the migration starts paying for itself in wall-clock time, not just correctness. *Breaking changes:* same checkpoint-invalidation note as 2.1, at higher cost per re-run (model inference, not just text cleaning).

**Step 3.1 — Implement `AnalysisScope` contract and `resolve_scope()`.** ✅ **DONE.**
*Why:* the prerequisite for everything else in Phase 3; nothing downstream can be rewritten until this exists. *Difficulty:* Medium. *Benefit:* establishes the "resolve once, persist, never re-derive" pattern as a reusable primitive. *Breaking changes:* none — additive, not wired into `topics/pipeline.py` this step.

*Implemented:* `AnalysisScope`/`AnalysisScopeType` (`core/contracts.py`), including `legacy_configuration_label()` — the backward-compatible alias mechanism, built into the contract layer per `AnalysisScope_Impact_Analysis.md`'s recommendation, rather than deferred to Step 3.2. New, optional (`None`-default) `scope_id` field added to `TopicRecord`/`TopicSentimentRecord`/`TopicEvolutionRecord` — purely additive, not yet set by any pipeline code. New module `finfluencer/scope.py` (`resolve_scope()`/`persist_scope()`) — not yet called by any pipeline stage. 30 new tests (`tests/unit/test_core/test_analysis_scope.py`, `tests/unit/test_scope.py`), full existing suite re-run: 324/324 tests pass (323 passed, 1 pre-existing skip unrelated to this change — missing optional `bertopic` package), zero diff in `topics/pipeline.py` or `analysis/topic_sentiment.py`. All ten invariants from the Step 3.1 approval gate verified — see chat record for the full verification. No integration-test suite exists separately from the unit suite in this repo (the `integration` pytest marker is reserved in `pyproject.toml` but currently unused by any test); the 324-test run is the complete suite.

**Step 3.2 — Rewrite `run_topics()` to take `scope_id`.** ✅ **DONE, with a narrower scope than originally stated below.**
*Why:* the first of the two functions whose disagreement caused the original bug. *Difficulty:* Medium-High (683-line file, careful surgery required to avoid changing actual topic-modelling behavior, only its fingerprinting). *Benefit:* topic modelling becomes scope-parameterized rather than tied to the `{"pooled","within_analyst"}` binary — the direct enabler of Phase 4's new entity types later. *Breaking changes:* none this step — see below.

*Implemented, per an explicit conservative-mode instruction from the approval gate:* `run_topics()` now calls `resolve_scope()`/`persist_scope()` internally and populates the new `scope_id` column on every `TopicRecord` row — but `TopicRecord.configuration` is **not** replaced; it continues to be set directly, unchanged, exactly as before. `scope_id` is additive metadata, not yet an input to `_model_fingerprint()` or the Tier-2 checkpoint key, so the "breaking changes" originally anticipated for this step did not occur — they are deferred to a future step, if the alias is ever exercised. `run_topics()`'s public signature, `collect/main.py`'s CLI call site, and `analysis/topic_sentiment.py` are all unchanged (zero diff). New output: `data/processed/analysis_scope.parquet` (additive).

*Verification:* a byte-exact reconstruction of the pre-Step-3.2 `topics/pipeline.py` (via mechanical reversal of the known edits) was used to run a deterministic row-by-row regression test (`tests/unit/test_topics/test_step3_2_regression.py`, 4 new tests) — confirms every row identical except `scope_id` (NaN → populated), and confirms Tier-3 model-cache fingerprints and Tier-2 checkpoint `.done` file contents byte-identical between old and new code. Full suite: 328/328 pass (327 passed, 1 pre-existing skip).

*Incident discovered and fixed during this step's invariant verification (unrelated to the AnalysisScope change itself):* `tests/unit/test_topics/test_topic_evolution.py::test_empty_topics_is_handled` (pre-existing test) called `run_topic_evolution()` without an explicit `output_path`, defaulting to the real `data/processed/topic_evolution.parquet` — every full-suite test run from the repo root was silently overwriting that real file with an empty table. The file's real content (1,231 rows) was overwritten during this session's test runs (Step 3.1 and/or Step 3.2) before being caught. It is recoverable — `topics.parquet` and the Tier-3 BERTopic model cache are both confirmed intact — by re-running the real `topic_evolution` pipeline stage; this sandbox cannot do so (`bertopic` is not installed here). The test bug itself is fixed (explicit `output_path` added to all 4 call sites in that file); full-suite runs no longer touch the real file, confirmed by mtime checks across two subsequent full runs.

**Step 3.2.5 — Backfill `scope_id` onto the existing `topics.parquet`.** ✅ **DONE. Unblocks the Step 3.3 rollback above.**
*Why:* Step 3.3's rollback (below) traced to a real gap: `data/processed/topics.parquet` predates Step 3.2 and had no `scope_id` column, and — per `core/checkpoint.py`'s `should_run()`, which keys purely on a `config_slice` hash Step 3.2 deliberately left unchanged — a plain rerun of `--stage topics` would hit the existing `.done` marker and skip straight to carrying prior (scope_id-less) rows through unchanged. Waiting for "the next real run" was evaluated and rejected as not technically viable under the current checkpoint architecture. *Difficulty:* Low — pure-pandas, no model fitting. *Benefit:* unblocks Step 3.3 without an expensive/risky full model refit.

*Implementation:* `finfluencer/migration/backfill_topic_scope.py` (268 lines), same structural pattern as `backfill_entity_model.py` (Phase 0) with one documented, deliberate deviation: it modifies the existing `topics.parquet` in place (via the caller) rather than writing a new sibling file, because that is specifically what Step 3.3's call site needs to find `scope_id` on. Group membership for each `(configuration[, analyst_key])` group is taken from `topics.parquet`'s own already-recorded rows (ground truth of what was actually fitted), not re-derived from a fresh `comments.parquet`/`embeddings_index.parquet` join — documented explicitly in the module docstring, per the approval gate's requirement, because a fresh join could silently include comments collected after the original fit. `analyst_key` (needed only for `within_analyst` grouping, since `topics.parquet` doesn't carry it) is looked up from `comments.parquet`, still the platform's live source of truth pending Phase 1's resolvers — not a legacy field in the deprecated sense.

*Executed against real data, with a full backup/validate/write/re-verify sequence:* `data/processed/topics.parquet.pre_step3_2_5.bak` created before any write. In-memory result validated (row count, row order, `topic_id`/`topic_prob`/`configuration`/`topic_label` all unchanged; `scope_id` fully populated, 5 distinct values = 1 pooled + 4 analysts) before writing. Post-write: re-read from disk and re-validated identically. All 20 `.done` checkpoint markers confirmed byte-identical (mtime + size + diff) before vs. after. `topic_evolution.parquet`/`topic_sentiment.parquet`/`comments.parquet` confirmed untouched (mtime). The pooled-stage fingerprint was independently recomputed from current `comments.parquet`/`embeddings_index.parquet`/settings and matches the checkpoint marker's recorded hash exactly — proof a hypothetical future rerun would still correctly hit the cache, unaffected by this backfill. 12 new tests (`tests/unit/test_migration/test_backfill_topic_scope.py`); full suite 351/351 (350 passed, 1 pre-existing skip).

**Step 3.3 — Rewrite `run_topic_evolution()` to read the persisted fingerprint.** 🛑 **Attempted, rolled back — blocker (above) now cleared. Re-attempting the call-site swap requires fresh approval, not automatic.**
*Why:* this is the specific line of work that fixes the bug this entire migration exists to fix. *Difficulty:* Medium — smaller change in code volume than 3.2, but the highest-stakes single step in the plan, and should not be merged without the validation check from §7 (old vs. new comment-ID sets identical) passing first. *Benefit:* `run_topics` and `run_topic_evolution` become structurally incapable of disagreeing, because they read the same persisted material instead of each computing their own. *Breaking changes (pending, not yet made):* `TopicEvolutionRecord.configuration`+`analyst_key` → `scope_id`.

*What happened:* the production call site in `run_topic_evolution()` was switched from `_resolve_scoped_topics_via_configuration()` to `_resolve_scoped_topics_via_scope()` — the single, minimal change authorized for this step. Byte-level regression testing (`test_step3_3_regression.py`, 4 tests) confirms the swap is correct: given a `topics_df` with `scope_id` already populated, output is byte-identical to the old resolver's, for every reachable scope. Running the full suite against this change, however, surfaced a real blocker: three pre-existing tests in `test_topic_evolution.py` failed with `KeyError: 'scope_id'`, which traced back to a fact about the *real* data, not the tests — **`data/processed/topics.parquet` was never regenerated by Step 3.2's code (that requires a live BERTopic run, not available in this environment) and has no `scope_id` column.** `_resolve_scoped_topics_via_scope()` unconditionally reads `topics_df["scope_id"]`, so pointing the production call site at it today would make `run_topic_evolution()` raise on the platform's actual current data — a direct violation of the "no downstream script should break" backward-compatibility requirement for this step. The call site was rolled back to `_resolve_scoped_topics_via_configuration()`; full suite re-confirmed green (339/339, 1 pre-existing skip) with the rollback in place. Neither resolver implementation was modified at any point.

*What this means for sequencing:* Step 3.3's actual prerequisite was incomplete — it needs not just "the new resolver is proven equivalent" (done) but "the real `topics.parquet` has `scope_id` populated" (not done, and not achievable in this environment). Two options going forward, not decided here: (a) backfill `scope_id` onto the existing `topics.parquet` additively (a small, Phase-0-style script analogous to `migration/backfill_entity_model.py`, computing `scope_id` via `resolve_scope()` from each existing `(configuration, analyst_key)` group's comment IDs, without refitting any model), or (b) wait for the next real `--stage topics` run (which will use Step 3.2's already-shipped code and populate `scope_id` naturally) before flipping this call site. Awaiting direction.

*Prerequisite validation completed as its own reviewed step:* the old, configuration-string resolution logic was extracted (zero behavior change - verified by the existing 6-test `test_topic_evolution.py` suite passing unchanged) into `_resolve_scoped_topics_via_configuration()`, still the only mechanism production code (`run_topic_evolution()`) calls. A candidate new mechanism, `_resolve_scoped_topics_via_scope()`, was added alongside it - not yet wired into production - which independently re-derives each scope's comment-ID set from `comments_df`/`embeddings_df` (never reading `configuration`) and resolves it via `resolve_scope()` to obtain `scope_id`, then filters `topics_df` by that. `tests/unit/test_topics/test_scope_resolution_equivalence.py` (7 new tests) proves the two mechanisms select identical comment-ID sets for every reachable scope (`pooled` + all four analysts' `within_analyst`), plus a full-corpus partition cross-check, plus a deliberate negative control confirming the comparison would actually catch a real divergence rather than passing vacuously. Full suite: 335/335 pass. Per the approval gate for this preparatory step, the old mechanism remains in production use; it is removed only once Step 3.3 itself is approved and executed.

**Step 3.4 — Update `analysis/topic_sentiment.py`.**
*Why:* the last remaining reader of the old `configuration`/`analyst_key` grouping. *Difficulty:* Low — the aggregation logic itself is unaffected, only its grouping key. *Benefit:* completes Phase 3; every packaged analytical module now speaks `scope_id`. *Breaking changes:* `TopicSentimentRecord` schema, per §4.

**Step 4.1 — Implement the `topic`/`campaign`/`event`/`custom` resolvers.**
*Why:* delivers the actual "domain-agnostic platform" capability this migration is ultimately for. *Difficulty:* Medium per resolver, independent of each other (can be built and shipped incrementally, one resolver type per release if desired). *Benefit:* a second research study (non-creator-based) becomes possible without touching any collection/processing/analysis code. *Breaking changes:* none to existing `creator` entities.

**Step 5.1 — Package-and-cut-over the shadow analysis pipeline (coordinated with, not part of, this plan).**
*Why:* flagged repeatedly throughout this plan as the highest-risk unaddressed dependency — the prior engineering audit's own top recommendation, and a precondition for Phase 5 actually being completable. *Difficulty:* Medium (per the prior audit, the logic already exists and works; this is a packaging/testing exercise, not new analytical development). *Benefit:* removes the single largest source of "silently reads stale schema" risk identified in §7. *Breaking changes:* none to this plan directly, but blocks Step 5.2 if skipped.

**Step 5.2 — Run `finfluencer.migration.cutover_entity_model`, deprecate old tables.**
*Why:* the formal completion of the migration — without this step, the platform carries both data models indefinitely. *Difficulty:* Low technically, contingent on 5.1's audit report being clean. *Benefit:* the platform reaches a single, coherent data model; `finfluencer.compat` (§9) can eventually be deleted. *Breaking changes:* scheduled, communicated, intentional — `videos.parquet`/`comments.parquet` and the old `configuration`-keyed analysis tables stop being written after this step, per the one-release deprecation window already committed to in §6.
