# Context Pack — Analysis Engine Infrastructure Adapter (Sentiment)

Full workflow: `IMPLEMENTATION_PLAYBOOK.md` Part B.2. Sibling document to `CONTEXT_PACK.md`
(topics, T-019) — this one covers `SentimentAnalysisAdapter` (T-022) only.

## Purpose

Implements `finfluencer.domain.analysis_engine.IAnalysisEngine` by wrapping the existing, tested
sentiment-polarity pipeline (`finfluencer.sentiment.pipeline.run_sentiment`), unmodified, behind
one adapter class (`SentimentAnalysisAdapter`). Added specifically to prove the `IAnalysisEngine`
plugin pattern generalizes beyond `TopicsAnalysisAdapter`, the one implementation it was proven
against so far (T-019's own Readiness Review closed with this exact open question). Same division
of responsibility as T-019: `StartAnalysisRunOrchestrator` (T-020) triggers this adapter through
one Domain-safe method call (`IAnalysisEngine.run(analysis_run_id, collection_run_id)`) without
knowing or caring that the implementation is `sentiment/` + a `TransformerSentimentClassifier`.

## Domain entities and invariants owned or touched

Owns no §10.1 entity directly. Touches `AnalysisRun` (T-018) only by convention, identical
reasoning to `CONTEXT_PACK.md`'s own section — mapping this adapter's `AnalysisOutcome` onto an
`AnalysisRun`'s lifecycle is T-020's orchestrator's job, not this adapter's.

## API Contract operations implemented

None directly — same reasoning as the topics adapter. This is the Infrastructure seam
`StartAnalysisRunOrchestrator` depends on abstractly (via `IAnalysisEngine`), not the orchestrator
itself.

## Guardrails that bind this module

- **IG-001** (layer-direction): this adapter imports `finfluencer.sentiment.*`, `finfluencer.core.*`,
  and `finfluencer.domain.analysis_engine` only. No Presentation/API import.
- **BKG-001** (business rules stay in Application/Domain): this adapter's own sequencing (derive
  paths → construct `CheckpointManager` → resolve a `SentimentProvider` → call `run_sentiment`) is
  a thin pass-through, not a new business rule — the actual scoring logic (cache-first lookup,
  pseudo-neutral banding, per-analyst checkpointing) lives entirely inside the unmodified
  `sentiment/` package, reused verbatim, same judgment call T-019 already made for `topics/`.

## Integration decisions (existing-engine code, if any)

- `finfluencer.sentiment.pipeline.run_sentiment` — **Wrapper required**
  (`IMPLEMENTATION_ROADMAP.md` §3's Analysis Engine row). Called unmodified; zero lines changed.
- **`SentimentProvider` is resolved lazily, not eagerly at construction.** Unlike
  `embeddings_index_path` (T-019's flagged caller-supplied requirement), `run_sentiment()` needs
  no equivalent externally-produced artifact — the one genuinely new decision here is *when* the
  (potentially heavy, `transformers`/`torch`-backed) provider gets constructed. This adapter
  accepts an optional `provider` (direct injection, what every test uses) or an optional
  `provider_factory` (a zero-arg callable, invoked only inside `run()`); if neither is given, it
  builds the real `TransformerSentimentClassifier` from `settings.sentiment.primary_model` on
  first `run()`, never at `__init__` time. Mirrors `TopicsAnalysisAdapter`'s existing discipline of
  keeping `model_loader`/`runner_factory` as deferred callables rather than eager values.
- **`comments_path` resolution reuses T-010's existing directory convention**
  (`base_root / collection_run_id / "data_raw" / "comments.parquet"`) — identical to
  `TopicsAnalysisAdapter`, not a second convention invented for sentiment.
- **Per-`analysis_run_id` isolation** (`checkpoint_root`/`cache_root`/`output_path` all rooted at
  `base_root / analysis_run_id`) — identical partitioning discipline to `TopicsAnalysisAdapter`
  (ADR-0002, Roadmap Risk R-1). A `TopicsAnalysisAdapter` run and a `SentimentAnalysisAdapter` run
  against the same `collection_run_id` never share a checkpoint/cache root, because each carries
  its own distinct `analysis_run_id` (T-018 already guarantees this).

## Known technical debt

- **No real, model-backed run has been exercised in this sandbox.** `transformers`/`torch` are
  declared dependencies but not installed here — every test (this adapter's and the pre-existing
  `tests/unit/test_sentiment` suite, 20 passed, confirmed clean without these installed) injects a
  fake `SentimentProvider`, per `transformer_classifier.py`'s own lazy-import design. Revisit
  trigger: the first task that needs to prove a real transformer inference run end to end.
- **`AnalysisRun`/`CollectionRun` pinning is convention, not enforced by this adapter** — same
  permissiveness as `TopicsAnalysisAdapter` (T-019); accepts any non-empty string.
- **T-020's retry-after-failure cache-miss characteristic applies identically here.** A retried
  `SentimentAnalysisAdapter.run()` gets a fresh `analysis_run_id` and thus a fresh `cache_root`,
  so the Tier-3 sentiment-score cache is not hit on retry even if the corpus/model are unchanged —
  not sentiment-specific, already documented against T-019/T-020, carried forward unchanged.

## Gotchas

- `run_sentiment()` silently writes an empty `SentimentRecord`-schema DataFrame (and returns it)
  if `comments.parquet` is missing/empty or lacks an `analyst_key`/`text_clean` column — this
  adapter adds no validation on top, matching `TopicsAnalysisAdapter`'s identical behavior for
  `run_topics()`. A missing/malformed fixture produces `AnalysisOutcome(row_count=0,
  topic_count=0)`, not an exception.
- **`AnalysisOutcome.topic_count` is a topic-modeling-named field, reused here for sentiment
  without renaming** — `IAnalysisEngine`/`AnalysisOutcome` are T-019's frozen contracts, and
  changing their shape is out of this task's scope (would also require touching T-020's
  orchestrator, which T-023's own acceptance criterion requires to stay at zero diff). Populated
  as `sentiment_df["sentiment_class"].nunique()` — the count of distinct sentiment classes
  actually produced (0, 1, or 2) — the same "`nunique()` of the categorical output column" shape
  `TopicsAnalysisAdapter` already uses for `topic_id`, applied to `sentiment_class` instead. This
  is a defensible reuse, not an arbitrary placeholder, but the field name itself is a genuine
  naming-fit finding worth surfacing for **T-023's own generalization review**: a truly
  AnalysisType-agnostic contract would likely need a differently-named (or generic) summary field
  rather than one borrowed from the first implementation. Not fixed here — fixing it would mean
  reopening T-019's already-closed `AnalysisOutcome` contract, which this task's scope forbids
  absent a demonstrated defect (this is a naming/generality concern, not a correctness defect).
- **Housekeeping note, same class of finding as T-019's `test_topics` discovery:**
  `tests/unit/test_sentiment` (20 tests) was verified during this task to pass cleanly without
  `transformers`/`torch` installed — it was already excluded from the standard "full regression"
  command under the same unverified assumption `test_topics` was. Corrected in this task's own
  BACKLOG.md Outcome: `test_sentiment` is now included in the standard full-regression command
  going forward.
