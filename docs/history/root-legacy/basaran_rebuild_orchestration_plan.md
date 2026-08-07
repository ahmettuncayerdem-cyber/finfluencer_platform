# Basaran Incremental Rebuild — Orchestration & Validation Plan

**Scope.** Re-collect `analyst_key="basaran"` under the corrected channel (`@MertBasaranOfficial`), then regenerate every downstream artifact that depended on the purged (duplicate-of-`gecer`) data, without touching `gecer`/`satiroglu`/`yesilada`. This document is a plan, not an execution log — nothing below has been run yet.

**Grounding.** All claims about checkpoint behavior are verified against `collect/main.py` (CLI dispatch, `_VALID_STAGES`), `core/checkpoint.py` (`should_run`/`mark_done` semantics), and each stage's `pipeline.py`. All row counts are measured against the current, already-purged production parquet files.

---

## 0. A finding that changes the risk profile

Before the rebuild, I re-measured overlap across the three untouched analysts (`gecer`, `satiroglu`, `yesilada`) on the post-purge data:

| Check | Result |
|---|---|
| `video_id` shared by >1 analyst | **0** |
| `comment_id` shared by >1 analyst | **0** |
| `comment_id` appearing more than once, globally | **0** |

The "144 multi-entity videos" / duplicate-`comment_id` phenomenon that motivated the entity-centric architecture proposal was **entirely explained by the basaran/gecer channel-collision bug**, not a general multi-analyst overlap pattern. With basaran's stale data removed, the corpus is currently duplicate-free across all three real analysts. This directly affects the topic-evolution go/no-go call in §6 — the fingerprint bug is a real latent code defect, but nothing in the *current* data triggers it.

This does not retroactively validate the entity-centric architecture as unnecessary — multi-entity videos remain structurally possible (e.g. a guest-appearance video two analysts both cover legitimately) — it just means today's corpus doesn't happen to exercise that case.

---

## 1. Execution order

```
channels ──▶ videos ──┬──▶ comments ──▶ preprocess ──┬──▶ embeddings ──┐
                       │                              └──▶ sentiment ───┤
                       └──▶ transcripts (parallel,                      ▼
                            not a gate for anything                  topics ──▶ topic_sentiment
                            downstream in this pipeline)                 │
                                                                          ▼
                                                                   topic_evolution
```

Rationale, stage by stage:

1. **`channels`** — resolves `basaran`'s `channel_id` from the corrected handle. Must run first; everything else keys off `channel_id`.
2. **`videos`** — depends on `channels` output. Populates `basaran`'s real video list.
3. **`comments`** and **`transcripts`** — both depend on `videos` (`selected_video_ids`), independent of each other. Can run in either order or back-to-back; neither gates the other.
4. **`preprocess`** — depends on `comments`. Writes `text_clean`/`tokens` back into `comments.parquet` in place (its `output_path` defaults to `comments_path`). Must complete before `embeddings`/`sentiment`, which read the preprocessed fields.
5. **`embeddings`** and **`sentiment`** — both depend on preprocessed `comments.parquet`, independent of each other, per-analyst checkpointed. Either order is fine.
6. **`topics`** — depends on `embeddings` (vectors) and `comments` (text/ids). Does not depend on `sentiment`.
7. **`topic_sentiment`** — depends on both `topics` and `sentiment` (it joins them).
8. **`topic_evolution`** — depends on `topics`'s fitted BERTopic model cache.

This is exactly the order already encoded in `_VALID_STAGES` in `collect/main.py`, so running each `--stage` flag in that declared order, or using `--stage all`, is correct and requires no manual reordering.

---

## 2. Checkpoint reuse vs. recompute

| Stage | Checkpoint key(s) | State right now | Effect on next run |
|---|---|---|---|
| `collect_channels` | one global marker | invalidated (content overwritten with sentinel hash) | full stage re-entered; Tier-1 per-`analyst_key` dedup means only `basaran` is actually re-resolved via the API — the other three are read from existing Tier-1 records and skipped |
| `collect_videos` | one global marker | invalidated | same pattern: Tier-1 dedup by `(analyst_key, video_id)` skips already-collected videos for the other three |
| `collect_comments` | one global marker | invalidated | Tier-1 dedup by comment record skips already-collected comments; only `basaran`'s (new) videos get fetched |
| `collect_transcripts` | one global marker | invalidated | same pattern, `basaran` only |
| `preprocess_comments__basaran` | per-analyst | invalidated | `basaran` reprocessed; `gecer`/`satiroglu`/`yesilada` markers untouched → skipped, prior rows carried through unchanged |
| `preprocess_comments__{gecer,satiroglu,yesilada}` | per-analyst | **untouched, valid** | skipped |
| `embed_comments__basaran` | per-analyst | invalidated | `basaran` recomputed |
| `embed_comments__{gecer,satiroglu,yesilada}` | per-analyst | **untouched, valid** | skipped, carried through |
| `sentiment_comments__basaran` | per-analyst | invalidated | `basaran` recomputed |
| `sentiment_comments__{gecer,satiroglu,yesilada}` | per-analyst | **untouched, valid** | skipped, carried through |
| `topics_within__basaran` | per-analyst | invalidated | `basaran`'s within-analyst BERTopic model refit |
| `topics_within__{gecer,satiroglu,yesilada}` | per-analyst | **untouched, valid** | skipped, carried through |
| `topics_pooled` | one global marker | invalidated | pooled BERTopic model **must** refit — see §3 |
| `topic_sentiment` | none (never checkpointed) | n/a | always fully recomputed, every run — cheap, pure aggregation |
| `topic_evolution` | none (never checkpointed) | n/a | always attempts a fresh join + cache lookup — see §6 |

One correction to a working assumption from the purge step: `preprocess`/`embeddings`/`sentiment` config-slice hashes are built only from model/provider/settings identifiers — **not** from comment text or `comment_id` sets. They would *not* have auto-detected that `basaran`'s comments changed. Manually invalidating their per-analyst markers (already done) was therefore necessary, not just a safety margin. `topics`'s fingerprint, by contrast, does hash `sorted(comment_ids)`, so it is content-aware on its own — its manual invalidation was redundant-but-harmless insurance.

---

## 3. Incremental vs. global recomputation

**Truly incremental (touches only basaran's rows, verified via carry-through logic in each stage):**
`channels`, `videos`, `comments`, `transcripts`, `preprocess`, `embeddings`, `sentiment`, `topics` (within-analyst part only).

**Unavoidably global, by design — not a bug:**
- **`topics_pooled`** — pooled BERTopic clusters the joint corpus of all four analysts. Adding basaran's real comments changes the pooled corpus composition, so the pooled model must refit even though `gecer`/`satiroglu`/`yesilada`'s underlying comments are unchanged. This does not modify their data, only the shared clustering that spans all of it.
- **`topic_sentiment`** — has no checkpoint at all, recomputes every run regardless. Inexpensive (pandas join, no model inference).
- **`topic_evolution`** — same, no checkpoint, always recomputes.

Net effect: only `basaran`'s per-analyst compute is new work; the pooled-topics refit is the one place where "global" recomputation is structurally required, and it is cheap relative to a full four-analyst refit since UMAP/HDBSCAN still only touches the combined corpus once.

---

## 4. Validation checks after each stage

Each check should be run immediately after its stage, before proceeding to the next — cheaper to catch a bad state at stage N than to discover it at stage N+3 downstream.

**After `channels`:**
- `channels.parquet` has exactly 4 rows, one per `analyst_key`.
- `basaran`'s `channel_id` is **not** `UCqU4fCu2zSL8gamk2CgvjCQ` (the old `gecer` collision value).
- All four `channel_id` values are pairwise distinct.

**After `videos`:**
- `videos.parquet` row count for `basaran` > 0.
- `set(videos[basaran].video_id) & set(videos[gecer].video_id) == ∅` (zero video overlap — the specific failure mode being corrected).
- Total row count = sum of per-analyst counts (no stray rows).

**After `comments`:**
- Every `comment_id` in `comments.parquet` for `basaran` references a `video_id` present in `basaran`'s `videos.parquet` rows (referential integrity).
- `comments[basaran].comment_id` has zero duplicates within itself.
- `set(comments[basaran].comment_id) & set(comments[gecer].comment_id) == ∅`.

**After `preprocess`:**
- `text_clean`/`tokens` are non-null for all `basaran` rows (no silently-skipped rows).
- `gecer`/`satiroglu`/`yesilada` rows are byte-identical to their pre-rebuild values (spot-check a hash of those three analysts' `text_clean` columns before/after).

**After `embeddings`:**
- `embeddings_index.parquet` has one row per `comment_id` in `comments.parquet` for `basaran` (1:1 coverage, no gaps, no extras).
- Embedding vector dimensionality matches the other three analysts' vectors (same model/revision).
- `gecer`/`satiroglu`/`yesilada` embedding rows unchanged (row-count and a sample hash check).

**After `sentiment`:**
- 1:1 coverage between `sentiment.parquet` and `comments.parquet` for `basaran`.
- Label distribution for `basaran` is not degenerate (not 100% one class — a cheap sanity signal that the model actually ran rather than defaulting).
- Other three analysts unchanged.

**After `topics`:**
- `topics_within__basaran` produces cluster assignments covering 100% of `basaran`'s comment_ids.
- `topics_pooled` cluster assignments cover 100% of the combined corpus.
- **Duplicate-check gate** (directly relevant to §6): recompute `sorted(comment_ids)` the same way `run_topics()` does and confirm zero duplicates in the resulting list.

**After `topic_sentiment`:**
- No `NaN` sentiment scores joined against valid topics (a `NaN` here means the topics/sentiment join key set diverged).

**After `topic_evolution`:**
- Confirm before running: recompute the fingerprint both ways (`run_topics`'s single-join path and `run_topic_evolution`'s double-join path) and diff the resulting `comment_id` lists. If they differ, stop — this is the known unfixed bug, not a data problem to retry past.

---

## 5. Final integrity report

Template below, populated with currently-verified numbers for the three untouched analysts. `basaran` rows are placeholders (zero/pending) until recollection completes — this section should be re-run and the numbers filled in as the actual completion check, not assumed from this plan.

**Channel count per analyst**

| analyst_key | channels |
|---|---|
| satiroglu | 1 |
| yesilada | 1 |
| gecer | 1 |
| basaran | 0 (pending recollection — expect 1) |

**Video count per analyst**

| analyst_key | videos |
|---|---|
| satiroglu | 303 |
| yesilada | 62 |
| gecer | 304 |
| basaran | 0 (pending — expect a real, independent count, not 304) |

**Comment count / unique comment count per analyst**

| analyst_key | raw rows | unique comment_id |
|---|---|---|
| satiroglu | 8153 | 8153 |
| yesilada | 510 | 510 |
| gecer | 3654 | 3654 |
| basaran | 0 | 0 (pending) |

(Raw rows == unique count for all three already-verified analysts — zero internal duplication.)

**Overlap matrix — video_id** (post-purge, pre-basaran-recollection; re-run after)

| | satiroglu | yesilada | gecer | basaran |
|---|---|---|---|---|
| satiroglu | 303 | 0 | 0 | pending |
| yesilada | 0 | 62 | 0 | pending |
| gecer | 0 | 0 | 304 | pending |
| basaran | pending | pending | pending | pending |

**Overlap matrix — comment_id** — identical structure/result to the video matrix above; re-run with the same pairwise-intersection query once `basaran` is populated. The pass criterion is every off-diagonal cell equal to 0.

**Duplicate comment_id count, globally:** 0 (verified). **Duplicate video_id count, globally:** 0 (verified). Both must remain 0 after `basaran` is added — this is the primary integrity gate for the whole rebuild, since it's the exact condition whose violation caused the original bug.

---

## 6. Go / No-Go

| Analysis | Decision | Condition |
|---|---|---|
| **Within-analyst BERTopic** | **GO**, conditional | Proceed once `topics_within__basaran` completes and passes the §4 coverage check. Does not depend on cross-analyst state at all — lowest risk of the three. |
| **Pooled BERTopic** | **GO**, conditional | Proceed once `topics_pooled` refits and the overlap matrix in §5 confirms zero cross-analyst `video_id`/`comment_id` overlap including `basaran`. Given §0's finding (zero overlap among the other three already), this is expected to pass, but it must be *checked*, not assumed — `basaran`'s real channel is the one untested unknown. |
| **Topic evolution** | **CONDITIONAL GO — gated, not blocked** | Proceed only after the explicit fingerprint-equality check in §4 ("After `topic_evolution`") passes. If it fails, this is the pre-existing, confirmed, unfixed bug in `topics/pipeline.py` (`_model_fingerprint` hashes `sorted(comment_ids)` without deduplication, and `run_topics()`/`run_topic_evolution()` compute that list via a single-join vs. double-join respectively). It is currently latent because the corpus happens to be duplicate-free, not because the code defect is fixed. Recommend scheduling the actual fix (dedup the comment_id list before hashing, or make both functions derive it via the same join path) as follow-up technical debt regardless of whether this rebuild's gate passes — a future analyst addition or a collection-time glitch (e.g. duplicate comment IDs from pagination overlap) will retrigger it otherwise. |

