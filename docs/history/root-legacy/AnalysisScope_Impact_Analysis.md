# AnalysisScope — Full Impact Analysis (Pre-Step 3.1)

**Method.** Every dependency below was located by direct inspection of the repository — `grep` across all non-vendor Python files for `configuration`, `analyst_key` (in topics/topic-sentiment/topic-evolution context), `topics.parquet`, `topic_sentiment.parquet`, `topic_evolution.parquet`, `TopicRecord`, `TopicSentimentRecord`, `TopicEvolutionRecord` — followed by reading each matching file to confirm the dependency is real, not a false positive from an unrelated use of a common word. No dependency below is assumed from the architecture documents; each is line-cited.

**Scope note.** Step 3.1 itself — adding the new `AnalysisScope` contract — is additive and touches nothing existing; in isolation it has zero blast radius. What follows maps the full chain Step 3.1 sets in motion through Steps 3.2–3.4 (the `configuration`+`analyst_key` → `scope_id` rename on `TopicRecord`/`TopicSentimentRecord`/`TopicEvolutionRecord`), because that is the impact a Step 3.1 design decision (field shape, alias mechanism) needs to be made with full knowledge of.

---

## Tier 0 — Contract layer (new + modified)

| Item | Why it depends | Timing | Direct/Indirect | Complexity | Manuscript risk |
|---|---|---|---|---|---|
| `core/contracts.py` — new `AnalysisScope` class | This is the contract itself | Compile-time (Pydantic model, validated at construction) | Direct (origin) | Low — new, additive class, no existing field touched | None |
| `core/contracts.py` — `TopicRecord.configuration: str` (line 447) | Field being generalized to `scope_id` | Compile-time (Pydantic required field) | Direct | Medium — must decide alias strategy (both fields populated one release, per the already-committed backward-compat plan) | Low, contingent on alias being honored |
| `core/contracts.py` — `TopicSentimentRecord.configuration`/`.analyst_key` (lines 494–495) | Same rename, plus `analyst_key` folds into `scope_id` (a `within_analyst` scope already implies its analyst) | Compile-time | Direct | Medium — two fields collapsing into one is a strict simplification but still a breaking shape change | Low, contingent on alias |
| `core/contracts.py` — `TopicEvolutionRecord.configuration`/`.analyst_key` (lines 515–516) | Same rename | Compile-time | Direct | Medium | Low, contingent on alias |

## Tier 1 — Direct in-package runtime dependents

| Item | Why it depends | Timing | Direct/Indirect | Complexity | Manuscript risk |
|---|---|---|---|---|---|
| `topics/pipeline.py` (683 lines) — `run_topics()` (line 385), `_process_pooled()`/`_process_within_analyst()` (lines 242, 320), `_rows_from_result()` (line 212), `_model_fingerprint()` (line 111, includes `"configuration"` in the fingerprint dict, line 128) | Constructs `TopicRecord` rows with `configuration=...`; the fingerprint that keys Tier-2/Tier-3 checkpoints and the Tier-3 model cache is built including `configuration` as a literal string | Runtime (DataFrame column access + dict key), plus compile-time via `TopicRecord(...)` construction | Direct | **High** — this is the largest, most invasive change in the whole migration (already flagged as such in the migration plan); fingerprint construction must move from "compute `configuration` string into the hash" to "read the already-resolved `scope_id`" | **Highest single risk in this analysis** — this is the literal function whose fingerprint disagreement motivated the migration; an incorrect rewrite here is the one failure mode that could silently change published topic-model output |
| `topics/pipeline.py` — `run_topic_evolution()` (line 515), incl. `scoped_topics = topics_df.loc[topics_df["configuration"] == configuration]` (line 602) | Filters `topics.parquet` by the literal `configuration` string to know which topic-model fit to read | Runtime (DataFrame filter) | Direct | Medium-High — this is the specific read path that must change from *re-deriving* scope to *reading* the persisted `scope_id`/fingerprint — the literal fix for the bug | High if done wrong, but this is also the step whose correctness this entire migration exists to guarantee — already the most carefully-flagged step in the roadmap |
| `topics/pipeline.py` — `_within_stage_name()` (line 99), checkpoint `stage_name`/`cfg_slice` construction (lines 134, 253–312, 348–377) | Checkpoint stage names embed `analyst_key`/`configuration`-derived strings (`f"{_STAGE_PREFIX_WITHIN}__{analyst_key}"`) | Runtime (string formatting), but structurally tied to `CheckpointManager.should_run()`'s `config_slice: dict[str, Any]` (checkpoint.py line 66) | Indirect (via `CheckpointManager`, which itself needs no change — confirmed below) | Low — `CheckpointManager` takes an opaque dict, so this is a call-site change only, not an infrastructure change | Low — expected, one-time checkpoint invalidation, already flagged as an accepted cost in the original risk table |
| `analysis/topic_sentiment.py` — `run_topic_sentiment()`, groups by `(configuration, analyst_key)` per its own docstring (lines 16–27), constructs `TopicSentimentRecord` | Consumes `topics.parquet`'s `configuration` column and groups by it | Runtime (DataFrame groupby) + compile-time (`TopicSentimentRecord` construction) | Direct | Low — the aggregation logic is unaffected, only its grouping key (already noted in the original migration plan) | Low |
| `collect/main.py` — CLI dispatch for `stage in ("topics", "all")` / `("topic_sentiment", "all")` / `("topic_evolution", "all")` (lines ~307–384), `run_topic_evolution(..., configuration="pooled", ...)` default argument (line 382) | Calls the three functions above with a hardcoded `configuration="pooled"` keyword | Runtime (function call), compile-time in the sense that the keyword argument name must exist on the callee's signature | Direct | Low — one default-argument update once `run_topic_evolution()`'s signature changes to `scope_id` | Low — CLI behavior (`--stage topics`, etc.) is unaffected by design, per the original plan's backward-compat commitment on stage names |

## Tier 2 — Direct external readers (root-level scripts)

Confirmed by reading each file's actual `pd.read_parquet(...)` and column-filter lines — not assumed from the "shadow pipeline" label alone.

| Item | Why it depends | Timing | Direct/Indirect | Complexity | Manuscript risk |
|---|---|---|---|---|---|
| `export_master_table.py` (lines 11, 14, 17) — `tp[tp["configuration"] == "pooled"]`, `tp[tp["configuration"] == "within_analyst"]` | Reads `topics.parquet` directly and filters on the literal `configuration` string to build `master_table.csv` | Runtime (DataFrame filter, unguarded — a `KeyError` if the column is renamed without an alias) | Direct | Low — two filter lines change from `df["configuration"]==...` to `df["scope_id"]==...` (or an equivalent scope-type lookup) | **High if not updated in the same change as Step 3.2** — `master_table.csv` is the single feeder file for most of the manuscript's downstream statistical tables (see Tier 3); this is the one script whose breakage would propagate furthest |
| `final_health_report.py` (lines 38, 40–41) — `tp["configuration"] == "pooled"`, `tp["configuration"].unique()` | Reads `topics.parquet`/`topic_sentiment.parquet`/`topic_evolution.parquet` for a diagnostic report | Runtime | Direct | Low | None — confirmed leaf script, prints to stdout only, no other script reads its output |
| `pub_data_pull.py` (lines 25, 37, 40) — `ts[ts["configuration"] == "pooled"]`, `tp[tp["configuration"] == "within_analyst"]`, `te[te["configuration"] == "pooled"]` | Reads all three topic-derived tables for a publication-data-pull diagnostic | Runtime | Direct | Low | None — confirmed leaf script, prints to stdout only, no other script reads its output |

## Tier 3 — Indirect dependents (one hop removed, insulated by Tier 2)

Verified by tracing what each script actually reads — none of these read `topics.parquet`/`topic_sentiment.parquet`/`topic_evolution.parquet` directly; they read CSVs that `export_master_table.py` (or an untraceable prior step, see note) already derived.

| Item | Why it (indirectly) depends | Timing | Direct/Indirect | Complexity | Manuscript risk |
|---|---|---|---|---|---|
| `build_stats_figures.py`, `run_inferential_tests.py`, `build_manuscript_data.py` | Read `master_table.csv` / `master_table_with_category.csv`, which `export_master_table.py` produces from `topics.parquet` — but `export_master_table.py` filters on `configuration` internally and never writes that column into `master_table.csv` (confirmed: its output columns are `topic_id_pooled`/`topic_label_pooled`/`topic_prob_pooled`/`topic_id_within`/`topic_label_within`, not `configuration`) | Runtime, one hop removed | Indirect | None required in these three files themselves | **Zero, provided `export_master_table.py` is updated correctly** — this is the key finding of this analysis: the rename's blast radius does not reach these files at all |
| `build_stats_tables.py`, `build_e5_e6_tables.py` | Read `topic_level_test_results.csv` / `weekly_sentiment_by_analyst.csv` | Runtime, one hop removed | Indirect | None | Zero directly, **but note:** no script in the current repo snapshot writes `topic_level_test_results.csv` — its generator is not traceable here. This is a pre-existing reproducibility gap (consistent with the prior engineering audit's "shadow pipeline" finding), not something this migration creates or worsens. Flagged for awareness, not blocking. |
| `build_R4_R7_tables.py`, `run_R4.py`–`run_R7.py` | No direct `read_parquet`/`read_csv` calls to the topic-derived tables found | — | None found | — | None — outside this migration's blast radius entirely |

## Tier 4 — Tests (direct, will fail on old assertions without updates)

| File | Test count | `configuration` refs | `analyst_key` refs | Complexity |
|---|---|---|---|---|
| `tests/unit/test_topics/test_pipeline.py` | 11 | 7 | 4 | Medium — asserts on `TopicRecord.configuration` values directly; needs updating to assert on `scope_id` (or both, during the alias window) |
| `tests/unit/test_topics/test_topic_evolution.py` | 6 | 14 | 5 | Medium-High — this file's own comment (line 150) notes it "pre-seeds the Tier-3 model cache exactly as `run_topics` would," meaning its fixtures encode the current fingerprint construction directly; these fixtures need rebuilding alongside the fingerprint rewrite, not just the assertions |
| `tests/unit/test_analysis/test_topic_sentiment.py` | 6 | 10 | 7 | Low-Medium — grouping-key assertions only, aggregation logic itself untouched |

No manuscript risk from the tests themselves — risk here is entirely "migration incomplete/incorrect," caught by the test suite itself before anything reaches production data, which is exactly what tests are for.

## Tier 5 — Related but not required to change for Step 3.1

| Item | Relationship | Why no change is required yet |
|---|---|---|
| `config/settings.yaml` — `topics.configurations.{within_analyst, pooled}` (lines 248–250) | The settings-level boolean toggle that `run_topics()` currently reads to decide which modes to fit | Conceptually this is exactly the `{"pooled","within_analyst"}` binary `AnalysisScope.scope_type` is meant to eventually generalize past (Phase 4). For Step 3.1–3.4 specifically (generalizing the *record* schema, not adding new scope types), this settings block can stay as-is; it becomes a real dependency only when Phase 4 resolvers are implemented. Noted here so it isn't rediscovered as a surprise later. |
| `core/contracts.py` — `TopicConfigurations` class (line 236) | Backs the settings block above | Same reasoning — additive-compatible with `AnalysisScope`, not a blocker |

## Confirmed NOT impacted

| Item | Why it was checked | Finding |
|---|---|---|
| `core/checkpoint.py` — `CheckpointManager.should_run()`/`.mark_done()`/`.cache_path()` | Topics pipeline's checkpoint calls are the highest-touch checkpoint usage in the codebase | Confirmed schema-free: `config_slice: dict[str, Any]` (line 66) — an opaque dict. `CheckpointManager` itself requires zero changes; only its *callers'* dict contents change shape, which is a call-site concern already captured in Tier 1. |
| `topics/bertopic_runner.py` | Imports `TopicRecord`/`TopicEvolutionRecord` per earlier search hit | Both references are docstring mentions only (lines 111, 221) — no actual field access to `configuration`/`analyst_key`. Fingerprint-agnostic by design, as the original migration plan already found. |
| `providers/market/*.py` (6 files) | Flagged in the prior engineering audit as the platform's best-isolated subpackage | Re-confirmed by this session's own grep: zero matches for `topics.parquet`/`configuration` in `market/`. Consumes the pooled sentiment index only, not topic records. |
| `outputs/auto/figures/*.png`, `*.svg` | Filenames literally encode `pooled`/`by_analyst` (e.g. `fig2_top_topics_pooled.png`) | These are already-rendered static image artifacts, not code — no functional dependency. The naming convention is cosmetic and doesn't need to change for the schema migration to succeed, though it's worth a human glance if any figure gets regenerated post-migration to confirm the underlying data is still what the filename claims. |

---

## Dependency graph

```
AnalysisScope (NEW, additive)                                        [Step 3.1 — zero blast radius alone]
    |
    v
resolve_scope()  (NEW module)
    |
    v
core/contracts.py: TopicRecord / TopicSentimentRecord /
                    TopicEvolutionRecord  (configuration+analyst_key -> scope_id)   [Step 3.1 schema change]
    |
    +----------------------------------------------------------------+
    |                                                                  |
    v                                                                  v
topics/pipeline.py                                          collect/main.py
  run_topics()            [HIGH complexity/risk]              CLI dispatch, default kwargs   [LOW]
  _model_fingerprint()                                              |
  _process_pooled/_within                                           v
  run_topic_evolution()   [the literal bug fix, HIGH]        (stage names unaffected —
    |                                                          backward-compat commitment)
    v
analysis/topic_sentiment.py
  run_topic_sentiment()   [LOW — grouping key only]
    |
    v
data/processed/{topics,topic_sentiment,topic_evolution}.parquet   (schema changed)
    |
    +---------------------------+---------------------------+
    |                           |                           |
    v                           v                           v
export_master_table.py   final_health_report.py       pub_data_pull.py
  [DIRECT, LOW effort,      [DIRECT, LOW effort,         [DIRECT, LOW effort,
   HIGH downstream reach     leaf — stdout only,          leaf — stdout only,
   if not fixed]             zero downstream risk]        zero downstream risk]
    |
    v
master_table.csv / master_table_with_category.csv    (configuration column absorbed, NOT propagated)
    |
    v
build_stats_figures.py, run_inferential_tests.py,
build_manuscript_data.py                               [INDIRECT — zero risk if export_master_table.py
                                                          is updated correctly]

tests/unit/test_topics/test_pipeline.py                 [DIRECT, 11 tests, medium effort]
tests/unit/test_topics/test_topic_evolution.py          [DIRECT, 6 tests, medium-high effort —
                                                           fixtures encode current fingerprint logic]
tests/unit/test_analysis/test_topic_sentiment.py        [DIRECT, 6 tests, low-medium effort]

NOT IMPACTED: core/checkpoint.py, topics/bertopic_runner.py, providers/market/*.py,
              build_R4_R7_tables.py, run_R4.py-run_R7.py, outputs/auto/figures/*
RELATED, NOT REQUIRED YET: config/settings.yaml topics.configurations, TopicConfigurations class
```

---

## Summary

Nine files require an actual code change (three in `src/`, three root-level scripts, three test files). Three more files depend indirectly but are fully insulated *provided* `export_master_table.py` is updated in the same change as `topics/pipeline.py` — that pairing is the one sequencing constraint this analysis surfaces that wasn't explicit in the original roadmap. The highest-complexity, highest-risk item by a clear margin is `topics/pipeline.py`'s `run_topics()`/`run_topic_evolution()` pair — expected, since that is the literal bug this migration exists to fix. Everything else in the blast radius is low-to-medium effort and low risk, especially given the transitional-alias commitment already made in the migration plan's backward-compatibility section (§6): if `configuration` continues to be populated alongside `scope_id` for one release, Tier 2/3's manuscript risk drops from "high if missed" to "low," because nothing downstream breaks even if a consumer script isn't updated in the same release.

**One concrete recommendation this analysis produces for Step 3.1's design:** build the alias into `AnalysisScope`/`TopicRecord` from the start (`configuration` as a computed property derived from `scope_id`, not a second independently-set field) rather than deferring the alias mechanism to Step 3.2 — that removes the sequencing risk of Tier 2 scripts being updated in a different commit than Tier 1.

No blocking issue was found. Step 3.1 (additive `AnalysisScope` contract) can proceed.
