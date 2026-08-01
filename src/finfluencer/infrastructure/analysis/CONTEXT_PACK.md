# Context Pack — Analysis Engine Infrastructure Adapter (Topics)

Full workflow: `IMPLEMENTATION_PLAYBOOK.md` Part B.2.

## Purpose

Implements `finfluencer.domain.analysis_engine.IAnalysisEngine` by wrapping the existing, tested
BERTopic pipeline (`finfluencer.topics.pipeline.run_topics`, `finfluencer.topics.bertopic_runner.
BERTopicRunner`), unmodified, behind one adapter class (`TopicsAnalysisAdapter`). Exists so a
future Application-layer orchestrator (`StartAnalysisRun`, BACKLOG.md T-020) can trigger a topic
analysis run through one Domain-safe method call (`IAnalysisEngine.run(analysis_run_id,
collection_run_id)`) without knowing or caring that the implementation is `topics/` + BERTopic,
per `PRODUCT_ARCHITECTURE.md` §8.2's Analysis Engine contract.

## Domain entities and invariants owned or touched

Owns no §10.1 entity directly. Touches `AnalysisRun` (T-018) only by convention -- this adapter's
`analysis_run_id`/`collection_run_id` parameters are expected to be an `AnalysisRun.id`/
`AnalysisRun.collection_run_id` pair once T-020's orchestrator exists, but this interface does
not require or assume that; mapping this adapter's plain `AnalysisOutcome` onto an `AnalysisRun`'s
lifecycle (`queued -> running -> completed | failed`) is Application/Domain's job in T-020, not
this one's -- exactly the same division T-010/T-011 already established for Collection.

## API Contract operations implemented

None directly. This adapter is what a future `StartAnalysisRunOrchestrator` will call internally
to satisfy the `startAnalysisRun` API interaction (§8.2) -- it implements the Infrastructure seam
that command's Application-layer implementation will depend on, not the command itself.

## Guardrails that bind this module

- **IG-001** (layer-direction): this adapter imports `finfluencer.topics.*`, `finfluencer.core.*`,
  and `finfluencer.domain.analysis_engine` only. No Presentation/API import.
- **BKG-001** (business rules stay in Application/Domain): this adapter's own sequencing (derive
  paths -> construct `CheckpointManager` -> call `run_topics`) is a thin pass-through, not a new
  business rule -- the actual analysis logic (caching tiers, UMAP/HDBSCAN fitting, outlier
  reduction, topic merging) lives entirely inside the unmodified `topics/` package, reused
  verbatim, same judgment call T-010 already made and documented for Collection.

## Integration decisions (existing-engine code, if any)

- `finfluencer.topics.pipeline.run_topics` + `finfluencer.topics.bertopic_runner.BERTopicRunner`
  -- **Wrapper required** (`IMPLEMENTATION_ROADMAP.md` §3's Analysis Engine row). Called
  unmodified; zero lines changed in either file by T-019.
- **`embeddings_index_path` is caller-supplied, not derived.** `run_topics()` already requires it
  as a parameter; no task in this backlog wraps `finfluencer.embeddings.pipeline` yet. This
  adapter takes it as a required constructor argument, same as the legacy function already did.
  Wrapping the embeddings stage as its own Infrastructure adapter is a separate, not-yet-ticketed
  concern -- flagged here explicitly, not silently assumed away. Revisit trigger: the first task
  that needs to *generate* embeddings rather than consume an already-produced
  `embeddings_index.parquet` (a fixture, in every test so far).
- **`comments_path` resolution reuses T-010's existing directory convention**
  (`base_root / collection_run_id / "data_raw" / "comments.parquet"`) rather than inventing a new
  one -- this is the exact path `CollectionEngineAdapter` already writes to.
- **Per-`analysis_run_id` isolation** (`checkpoint_root`/`cache_root`/`output_path` all rooted at
  `base_root / analysis_run_id`) mirrors ADR-0002's per-`run_id` partitioning discipline (Roadmap
  Risk R-1), applied here to Analysis instead of Collection -- two distinct `analysis_run_id`s can
  never collide even if a caller passed the same `base_root` for both.

## Known technical debt

- **No real, network/compute-backed run has been exercised in this sandbox.** `bertopic`,
  `umap-learn`, `hdbscan`, `sentence-transformers`, `torch` are all declared dependencies
  (`pyproject.toml`) but not installed here -- every test (this adapter's and the pre-existing
  `tests/unit/test_topics` suite, 49 passed/1 skipped, confirmed clean without these installed)
  injects a fake `runner_factory`/`model_loader`, per `bertopic_runner.py`'s own lazy-import
  design. Revisit trigger: the first task that needs to prove a real BERTopic fit runs correctly
  end to end (analogous to T-015's live-network smoke test for Collection).
- **Embeddings-generation wrapping does not exist yet** (see Integration decisions above) --
  revisit when a task needs to produce `embeddings_index.parquet` from raw collected comments
  rather than consume a pre-existing one.
- **`AnalysisRun`/`CollectionRun` pinning is convention, not enforced by this adapter.** T-020's
  orchestrator is expected to pass a real `AnalysisRun.collection_run_id`; this adapter accepts
  any non-empty string, same permissiveness `CollectionEngineAdapter` already has for `run_id`.

## Gotchas

- `run_topics()` silently writes an empty `TopicRecord`-schema DataFrame (and returns it) if
  `comments.parquet` is missing/empty or has no `text_clean` column, or if no comment IDs match
  between `comments_path` and `embeddings_index_path` -- this adapter does not add its own
  validation on top; a genuinely missing/mismatched fixture will produce `AnalysisOutcome(row_count=0,
  topic_count=0)`, not an exception. Matches legacy behavior exactly; tests must construct a
  properly joined fixture pair to exercise the real assignment path.
- `AnalysisOutcome.topic_count` is `topics_df["topic_id"].nunique()`, which counts `-1` (outlier)
  as its own "topic" if present -- an intentional, simple choice (matches how the underlying
  `topic_id` column already represents outliers), not a bug.
