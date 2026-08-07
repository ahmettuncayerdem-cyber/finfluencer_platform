# From Finfluencer Platform to a Domain-Agnostic YouTube Computational Communication Research Platform

## Architecture Design Document

Prepared for: `finfluencer_platform` → generalized research infrastructure
Status: **Proposal — design only, no implementation**

---

## 1. Problem Statement and Design Principle

The current pipeline treats `analyst_key` as a partition key baked into every collection and processing stage: videos, comments, embeddings, sentiment scores and topic models are all fetched, cached and checkpointed *per analyst*. This was a reasonable simplification when the entity space was "four named YouTube creators," but it breaks down the moment a unit of study is not a creator but a **discourse, event, or campaign** — because those units are defined by *membership criteria over a shared pool of videos*, not by channel ownership. The same video can legitimately belong to zero, one, or many such units simultaneously (a joint interview belongs to two creators; a video about a ceasefire announcement belongs to both `gaza_war` and `israel_palestine_conflict`).

Today's debugging session surfaced the concrete cost of the current design: 144 videos are attributed to more than one `analyst_key`, so `collect_comments()` — whose checkpoint key is `(analyst_key, video_id)` — legitimately, by design, fetches and stores the same ~4,750 comments twice. That duplication then propagates silently into `sentiment.parquet` and, worse, into two *independently re-derived* BERTopic model fingerprints (`run_topics` vs. `run_topic_evolution`) that disagree because each function joins the same duplicated rows through a different path. This is not a bug in either function individually — it is the entity-as-partition-key assumption breaking down under multi-membership data.

**Governing principle for the redesign:** *videos and comments are physical facts that exist exactly once; entities are labels attached to videos through an explicit many-to-many relationship; every downstream computation over comments operates on deduplicated content and is parameterized by an explicit, persisted, reproducible **scope**, never by an implicitly re-joined entity column.*

---

## 2. Target Data Model

### 2.1 Core entities

**`Entity`** — generalizes "analyst" into any unit of study.

| field | type | notes |
|---|---|---|
| `entity_key` | string (PK) | stable slug, e.g. `satiroglu`, `gaza_war`, `election_2027_tr` |
| `entity_type` | enum | `creator`, `topic`, `campaign`, `event`, `custom` — extensible registry, not a hardcoded union |
| `display_name` | string | human-readable |
| `description` | string | free text, for the research record |
| `membership_strategy` | string | key into a registry of resolver implementations (see §2.4) |
| `membership_params` | JSON | strategy-specific parameters (channel IDs for `creator`; keyword/query rules for `topic`; date range + hashtag set for `campaign`) |
| `study_id` | string | which research project this entity belongs to (multi-tenancy) |
| `created_at` | timestamp | |

**`Video`** — exists once, ever, regardless of how many entities reference it.

| field | type | notes |
|---|---|---|
| `video_id` | string (PK) | YouTube's own ID — globally unique by construction |
| `channel_id` | string | |
| `published_at` | timestamp | |
| `title`, `description` | string | |
| `duration_sec`, `view_count`, `like_count`, `comment_count` | numeric | |
| `category_id` | string | |
| `made_for_kids` | bool | |
| `collected_at` | timestamp | |

**`Comment`** — exists once, ever. Belongs to exactly one video (YouTube's own model — comments are not entity-scoped, only video-scoped).

| field | type | notes |
|---|---|---|
| `comment_id` | string (PK) | YouTube's own ID |
| `video_id` | string (FK → Video) | |
| `commenter_hash` | string | anonymized at ingest, unchanged from current design |
| `posted_date` | date | day-truncated, unchanged from current design |
| `text_raw`, `text_clean` | string | `text_clean` populated by preprocessing stage |
| `like_count`, `reply_count` | numeric | |
| `parent_comment_id` | string, nullable | reserved for reply-thread support |
| `collected_at` | timestamp | |

### 2.2 Bridge table (the core structural fix)

**`EntityVideoLink`** — the *only* place the many-to-many relationship lives.

| field | type | notes |
|---|---|---|
| `entity_key` | string (FK → Entity) | |
| `video_id` | string (FK → Video) | composite PK: `(entity_key, video_id)` |
| `matched_via` | string | e.g. `channel_membership`, `keyword_match:"ateşkes"`, `manual_curation` |
| `eligible` | bool | per-entity eligibility (a video can match a keyword but still be excluded for entity-specific reasons — shorts, promo content, etc.) |
| `selected` | bool | per-entity selection decision, mirrors today's `selected` flag but now entity-scoped, not global |
| `linked_at` | timestamp | |
| `criteria_version` | string | which version of `membership_params` produced this link (see §9.2) |

This table stays small even at scale: it is `O(entities × avg. videos per entity)`, never `O(comments)`. It is the sole place where "does this video belong to this unit of study" is recorded, and it is the sole table that changes when entity definitions evolve.

### 2.3 Derived, comment-intrinsic layer (computed exactly once, globally)

These tables have **no entity dimension at all** — they are properties of a comment, full stop.

**`CommentFeature`** (preprocessing output): `comment_id` (PK), `text_clean`, `language`, `token_count`, preprocessing metadata.

**`Embedding`**: `comment_id` (PK), `embedding_path`, `model_name`, `revision`, `dimension`.

**`Sentiment`**: `comment_id` (PK), `sentiment_prob`, `sentiment_class`, `sentiment_pseudo_neutral`, `sentiment_target`, `sentiment_market_directed` (or domain-appropriate equivalents). Structurally identical to today's `SentimentRecord` — the fix here isn't the schema, it's that the *source* comments table feeding it is now deduplicated by construction.

Because these three tables are keyed purely by `comment_id`, the entire "per-analyst loop with a Tier-2 checkpoint per key" scaffolding in today's `embeddings/pipeline.py` and `sentiment/pipeline.py` — which has been the source of essentially every bug diagnosed in this conversation — disappears. There is one global cache-first pass per stage, over all comments that exist, once.

### 2.4 Entity membership resolvers (registry pattern)

Consistent with the existing `core/registry.py` pattern already used for language/platform/embedding/sentiment providers, membership resolution becomes a registered strategy:

- `creator` resolver: video belongs to entity if `channel_id ∈ membership_params.channel_ids`.
- `topic` / `keyword` resolver: video belongs to entity if title/description/transcript matches `membership_params.query` (keyword list, regex, or a classifier score threshold) within `membership_params.date_range`.
- `campaign` / `event` resolver: combination of date range + hashtag/keyword set + optionally channel allowlist.
- `custom` resolver: escapes to a user-supplied plugin, e.g. a manual CSV of video IDs curated by a research assistant.

Each resolver's job is only to populate `EntityVideoLink` rows. It never touches `Video`/`Comment` collection directly — collection operates on the deduplicated video ID set unioned across *all* entities' links, once per video, regardless of resolver type.

### 2.5 Analysis layer (entity-scoped, computed on demand)

The old design hardcoded exactly two "configurations": `pooled` and `within_analyst`. The new design replaces this binary with a first-class, persisted **`AnalysisScope`**.

**`AnalysisScope`**:

| field | type | notes |
|---|---|---|
| `scope_id` | string (PK) | content hash of the fields below |
| `scope_type` | enum | `entity`, `entity_set`, `global`, `filtered` |
| `entity_keys` | list[string] | empty for `global` |
| `filter_params` | JSON | e.g. date range, language filter — anything beyond entity membership |
| `resolved_comment_ids_hash` | string | SHA-256 of the sorted, deduplicated comment_id list this scope resolved to, **at resolution time** |
| `resolved_at` | timestamp | |
| `criteria_version` | string | ties back to the `EntityVideoLink.criteria_version` values in effect at resolution time |

This is the single most important addition motivated by today's debugging session (§8). A scope is resolved **once**, its member `comment_id` set is persisted, and every downstream fingerprint (topic model cache, topic evolution lookup) reads that *stored* set — it is never independently re-derived by joining tables a second time with a possibly different join path.

**`Topic`**: `comment_id`, `scope_id` (replaces `configuration` string), `topic_id`, `topic_prob`, `topic_label`, `topic_tier`.

**`TopicEvolution`**: `scope_id`, `topic_id`, `time_bin`, `frequency`, `bin_words`, `topic_label`.

**`TopicSentiment`** (cross-tab): `scope_id`, `topic_id`, aggregate sentiment statistics — same shape as today's `TopicSentimentRecord`, generalized from `(configuration, analyst_key)` to `scope_id`.

---

## 3. Checkpoint Strategy

| stage | old checkpoint unit | new checkpoint unit |
|---|---|---|
| video collection | implicit, per-channel | per unique `video_id` (deduplicated across all entities before fetch) |
| comment collection | `(analyst_key, video_id)` | per unique `video_id` only |
| `EntityVideoLink` population | n/a | idempotent upsert per `(entity_key, video_id, criteria_version)` — cheap, no API calls, re-runs freely |
| preprocessing / embeddings / sentiment | per `(analyst_key)` loop, one Tier-2 stage per key | single global stage over all comments — cache-first at the `comment_id` level, no per-entity partitioning at all |
| topic modeling | per `configuration ∈ {pooled, within_analyst__<key>}` | per `scope_id` — same Tier-2/Tier-3 split, generalized key |
| topic evolution | recomputes fingerprint from a fresh join (bug source) | reads `resolved_comment_ids_hash` from the persisted `AnalysisScope` row — never re-derives it |

**Mandatory structural rule going forward** (this generalizes the one defensive pattern that already exists correctly in `collect_comments()` and should become universal): *a stage's "should I skip this?" check must require both a matching Tier-2 config-slice hash **and** the existence of the actual output artifact.* Every bug diagnosed in this session's earlier phases — the `topic_label` staleness, the sentiment `basaran`-only truncation, the silent row-drop on retry — traces back to exactly one place violating this rule. In the new design this becomes a shared helper (`should_materialize(stage_name, cfg_slice, output_path)`), not a convention each module has to remember to reimplement.

---

## 4. Cache Strategy

- **Tier-3 embeddings/sentiment cache**: unchanged in principle — content hash of `(text_clean, model_name, revision[, device])`. Already entity-agnostic today; the fix is removing the per-entity *scaffolding* around it, not the cache key itself.
- **Tier-3 topic model cache**: fingerprint of `(resolved_comment_ids_hash, embedding_model_name, embedding_revision, UMAP config, HDBSCAN config, stage_seed)`. The critical change: `resolved_comment_ids_hash` comes from the **persisted `AnalysisScope`**, computed once at fit time and read (not recomputed) at every subsequent lookup — including from read-only consumers like topic evolution.
- **Model cache manifest**: alongside each cached `.pkl`, persist a small sidecar JSON (`{scope_id, resolved_comment_ids_hash, n_comments, fit_at, config}`) so the cache is human-auditable and so a fingerprint mismatch becomes immediately debuggable (compare stored vs. recomputed material) instead of an opaque hash string, which is exactly what cost significant diagnostic effort today.

---

## 5. Fingerprint Strategy — General Principle

Every fingerprint, in every stage, going forward follows one rule: **compute it from canonical, deduplicated, sorted, explicitly-typed material exactly once, and persist that material as a first-class artifact.** Any function that needs the same fingerprint later reads the persisted material; it never independently re-derives it through its own join or filter logic. This single rule is the direct, generalized fix for the `run_topics` vs. `run_topic_evolution` fingerprint mismatch found today, and it preempts the same bug class from recurring in every future stage (cross-entity sentiment comparison, cross-scope topic diffing, etc.).

---

## 6. Migration Path

**Phase 0 — Introduce canonical tables alongside the existing ones (additive, non-breaking).**
Add `Video`, `Comment`, `EntityVideoLink` as new tables. Backfill from current `videos.parquet`/`comments.parquet`: deduplicate by `video_id`/`comment_id`; every existing `analyst_key` becomes an `Entity` row with `entity_type="creator"`; every (analyst, video) pair the current data implies becomes an `EntityVideoLink` row — the 144 already-discovered multi-entity videos become the first real multi-membership links in the system, not an anomaly to special-case.

**Phase 1 — Rewrite collection stages.**
`collect_videos`/`collect_comments` iterate the deduplicated `video_id` set (union across all entities currently configured), fetch once, write to `Video`/`Comment`. `EntityVideoLink` population becomes a separate, cheap, idempotent step per entity's membership resolver.

**Phase 2 — Rewrite preprocessing/embeddings/sentiment.**
Drop the per-`analyst_key` loop entirely. Single global cache-first pass over `Comment`. This is a simplification, not just a generalization — it removes the entire class of per-key checkpoint bugs debugged in this session.

**Phase 3 — Generalize the analysis layer.**
Replace `configuration ∈ {"pooled","within_analyst"}` with explicit `AnalysisScope` resolution; topic modeling, topic evolution, and topic-sentiment cross-tabs all take a `scope_id` produced by the same shared resolver.

**Phase 4 — Entity-type registry.**
Plug in `topic`/`campaign`/`event` membership resolvers alongside the existing `creator` resolver, using the same registry pattern already established for providers. This is the point at which the platform becomes genuinely domain-agnostic rather than "finfluencer platform with an extra table."

**Phase 5 — Backfill and cutover.**
Re-point all downstream consumers (dashboards, statistics module, GUI) at the new tables; deprecate direct reads of the old `analyst_key`-partitioned parquet files behind a compatibility view (§7) for one release cycle.

---

## 7. Backward Compatibility

- **Compatibility view, not a physical table**: reconstruct the old analyst-centric shape (`comment × analyst_key`, duplicated exactly as before if a legacy script expects that) as an on-demand join of `Comment ⋈ EntityVideoLink ⋈ Video`, so existing downstream scripts keep working unmodified while new code targets the canonical deduplicated tables.
- **Config migration**: `analysts.yaml` becomes `entities.yaml` with an `entity_type` discriminator. A one-time, mechanical, lossless transform wraps every existing analyst as `entity_type="creator"` with its channel IDs as `membership_params`. Old configs continue to validate via a compatibility schema for one release cycle.
- **Contracts**: introduce `EntityRecord`, `EntityVideoLinkRecord`, `AnalysisScopeRecord` etc. as new, additive Pydantic schemas rather than mutating `AnalystRecord`-shaped ones in place; deprecate the old ones with an explicit migration window and a `DeprecationWarning`-style log event, matching the project's existing discipline around schema changes requiring explicit approval.

---

## 8. Performance Implications

- **The core win**: for `N` entities with an average video-overlap factor `k`, the current design does `O(N·k)` redundant fetch/preprocess/embed/sentiment work per shared video; the new design does this work exactly once per unique video/comment. This matters most for the expensive, model-bound stages (embeddings, sentiment, topic fitting) — precisely the stages that dominate compute cost at "millions of comments" scale.
- **`EntityVideoLink` stays cheap**: it scales with `entities × videos`, never with `comments` — the expensive fan-out never touches the entity dimension.
- **Global topic modeling at scale**: BERTopic's UMAP/HDBSCAN steps have known scaling ceilings well before "millions of comments." This should be tracked as a separate scaling workstream (chunked/incremental UMAP, hierarchical topic reduction, or principled subsampling for exploratory passes) — orthogonal to the entity-model refactor, but worth flagging now since the new design makes "global, cross-entity" topic modeling a first-class, easy-to-request operation, and someone will ask for it at scale.
- **Storage layout**: at multi-million-comment scale, partition `Comment`/`CommentFeature`/`Embedding`/`Sentiment` by ingestion date or a `video_id` hash-bucket — never by entity, since a comment no longer has a single owning entity. This is a departure from today's single-parquet-file-per-stage convention and is flagged here as its own decision point, not bundled silently into this refactor.

---

## 9. Reproducibility Considerations

1. **Persisted scope resolution, not re-derivation** (§5) is the primary reproducibility guarantee this redesign adds relative to today's system.
2. **Entity membership is versioned.** Because `membership_params` for `topic`/`campaign` entities can legitimately evolve mid-study (a keyword list gets refined), every `EntityVideoLink` and `AnalysisScope` row carries a `criteria_version`. A historical analysis remains exactly reproducible against the criteria in effect when it was run, even after the entity definition changes later — this did not need to exist for `creator`-type entities (channel membership is effectively static) but is required the moment `topic`/`campaign` types are introduced.
3. **Reproducibility manifests** (extending the existing `ANON_SALT` / `core/reproducibility.py` conventions) should record the entity-type registry version and the specific membership-resolver implementation version alongside `root_seed`, since "which comments are in scope" is now a function of resolvable — and potentially evolving — criteria, not a fixed static column.
4. **Checkpoint determinism is preserved, not weakened**: every checkpoint key in the new design is still a pure function of stable identifiers (`video_id`, `comment_id`, `scope_id`) and config-slice hashes — the redesign changes *what* the partition key is (content-based rather than entity-based for collection/processing stages), not the determinism guarantee itself.

---

## 10. Summary of What This Fixes vs. What It Adds

**Fixes** (root causes already diagnosed in this project): comment duplication from multi-entity videos; the two-independently-derived-fingerprints bug between topic modeling and topic evolution; the entire class of "checkpoint says done but output missing" bugs in per-entity-loop stages (sentiment, embeddings, topics-within).

**Adds**: a registry of pluggable entity types beyond "creator," enabling topic-, campaign-, and event-based studies on the same infrastructure without touching collection/processing code — only the membership-resolver layer and configuration change per new research domain.

This document is a proposal. No code has been written or modified. The recommended next step, if approved, is to scope Phase 0 (additive canonical tables + backfill) as a standalone, reviewable unit of work, since it is non-breaking and can be validated against the current finfluencer dataset — including the 144 known multi-entity videos — before any downstream stage is touched.
