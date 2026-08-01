# T-019 Architecture & Performance Readiness Review — Wrap `topics/` (BERTopic) as an Infrastructure adapter

## 1. Exact legacy modules wrapped, not rewritten

`finfluencer.topics.pipeline.run_topics` (834 lines) and `finfluencer.topics.bertopic_runner.BERTopicRunner` (227 lines) — both called unmodified. Neither file is touched by this task. `finfluencer.embeddings.*` is **not** wrapped by T-019 (see Assumption 1 below) — it is a separate, not-yet-ticketed pipeline stage.

## 2. Existing contracts that must remain unchanged

`run_topics()`'s full signature (`settings, comments_path, embeddings_index_path, checkpoint, *, output_path, analyst_key, runner_factory, model_loader`) and return shape (a `TopicRecord`-schema DataFrame). `core.contracts.TopicsConfig`/`TopicRecord`/`TopicConfigurations`/`UMAPConfig`/`HDBSCANConfig` (all Pydantic, `core/contracts.py`) — Domain must never import these directly (§12.1's "no external SDK" rule for Domain applies to Pydantic itself, per `domain/entities/_common.py`'s own established reasoning). `CheckpointManager`'s Tier-2/Tier-3 cache-key scheme inside `run_topics` (model fingerprint excludes `reduce_outliers`/`merge_similarity_threshold` by design) — not reproduced or altered.

## 3. External dependencies

Reused, already declared in `pyproject.toml`, **none installed in this sandbox** (same situation `google-api-python-client` was in before T-015): `bertopic ^0.16`, `umap-learn`/`hdbscan` (transitive via bertopic), `sentence-transformers ^2.3`, `torch >=2.8.0,<2.9.0`, `scikit-learn ^1.3`. **No new dependency required.** Confirmed via `tests/unit/test_topics` (49 passed, 1 skipped) running clean in this sandbox with none of the above installed — every existing test injects a fake `runner_factory`/`model_loader` (`bertopic_runner.py`'s own design: heavy imports are lazy, only triggered when constructing a real, non-injected model). T-019's own tests will use the same injection technique — no install needed to implement or test this task.

## 4. Highest expected runtime/memory costs

Inside `BERTopicRunner.__init__` when `model=None` (real construction): UMAP fit (stochastic dimensionality reduction over the full embedding matrix) and HDBSCAN fit are the dominant costs, confirmed by BACKLOG.md's own Effort-L flag on this task ("first place compute cost/runtime genuinely matters"). This cost is entirely inside the wrapped, untouched module — T-019 adds no new compute, only a thin adapter around an existing entry point. `_load_embedding_matrix` (`np.stack` over every comment's `.npy` file) holds the full corpus's embedding matrix in memory at once — an existing, unchanged characteristic of `run_topics()`, not introduced here.

## 5. Determinism / reproducibility requirements

UMAP's `random_state` is fixed via `derive_seed(settings.study.root_seed, "topics")` (existing, unchanged). HDBSCAN has no random component. Topic-merging is an order-independent union-find (existing, unchanged). None of this is touched by T-019 — the adapter calls `run_topics()` with the same `settings`/seed derivation the legacy pipeline already used, so reproducibility is inherited, not re-implemented.

## 6. Caching

Tier-3 (fitted-model cache, keyed by corpus+config fingerprint) and Tier-2 (stage checkpoint) both already exist inside `run_topics()`/`CheckpointManager` — reused as-is. The adapter must always pass a real `CheckpointManager` rooted per `analysis_run_id` (mirroring T-010's `ADR-0002` per-run partitioning) so two distinct `AnalysisRun`s never share a cache root. Nothing needs to be recomputed by this task that the legacy pipeline doesn't already recompute (fresh corpus/config -> refit; unchanged corpus/config -> `.transform()` only).

## 7. Assumptions — flagged explicitly

1. **`embeddings_index.parquet` is a caller-supplied input, not derived by this adapter.** `run_topics()` already requires it as a parameter; no task in the backlog wraps `finfluencer.embeddings.pipeline` yet. T-019's adapter therefore takes `embeddings_index_path` as an explicit parameter (same as the legacy function), leaving embeddings-wrapping to a future, separate ticket if ever needed. This is a scope boundary, not a defect.
2. **`comments.parquet` location is resolved via T-010's existing directory convention** (`base_root / collection_run_id / "data_raw" / "comments.parquet"`) — reusing, not inventing, the partitioning `CollectionEngineAdapter` already established. `AnalysisRun.collection_run_id` (T-018) is the pin this resolves against.
3. **The adapter's own `run()` derives a fresh `checkpoint_root`/`output_path` per `analysis_run_id`**, mirroring ADR-0002's per-run isolation for Analysis instead of Collection.
4. **Domain-safe outcome type is minimal** (`AnalysisOutcome(analysis_run_id, row_count, topic_count)`), mirroring `CollectionOutcome`'s existing shape (§12.1: no DataFrame/pandas crosses into Domain).
5. **No `IAnalysisEngine` Domain interface exists yet** — creating one (mirroring `domain/collection_engine.py`'s `ICollectionEngine`) is this task's job, per T-019's own acceptance criterion ("adapter produces topic assignments from a Dataset") needing something for T-020's future orchestrator to depend on, exactly as `ICollectionEngine` existed for T-011 to depend on.

## 8. Contradiction check

No contradiction found with `PRODUCT_ARCHITECTURE.md` (§8.2, §10.1, §12.1), `IMPLEMENTATION_ROADMAP.md` (§3's "Wrapper required" classification, §4's Collection-before-Analysis ordering), or `IMPLEMENTATION_PLAYBOOK.md` (Part B.1/B.2). Proceeding to implementation.
