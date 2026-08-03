# Release Blocker #6 — Readiness Review: Real Analysis Dispatch Behind `StartAnalysisRun`

**Date:** 2026-08-03
**Status:** Readiness Review only. **No engineering performed.** Per explicit instruction,
implementation may not begin until this review is read and implementation is separately
authorized.
**Scope:** Priority 1 (Release Blocker #6) and Priority 2 (preprocess adaptation) — reviewed
together because code-level evidence below shows they are the same dependency chain, not two
independent tasks.

---

## 1. What code already exists (verified by reading, not assumed)

| Piece | File | Status |
|---|---|---|
| `IAnalysisEngine` Protocol | `domain/analysis_engine.py` | Built (T-019), frozen |
| `StartAnalysisRunOrchestrator` | `application/orchestrators/start_analysis_run.py` | Built (T-020), unmodified since |
| `AnalysisType` entity | `domain/entities/analysis_type.py` | Built (T-018), minimal by design |
| `TopicsAnalysisAdapter` | `infrastructure/analysis/topics_adapter.py` | Built (T-019), wraps `topics.pipeline.run_topics` unmodified |
| `SentimentAnalysisAdapter` | `infrastructure/analysis/sentiment_adapter.py` | Built (T-022), wraps `sentiment.pipeline.run_sentiment` unmodified |
| `EmbeddingsEngineAdapter` | `infrastructure/analysis/embeddings_adapter.py` | Built (Release Blocker #4), wraps `embeddings.pipeline.run_embeddings` unmodified |
| `preprocess.pipeline.run_preprocessing` | `preprocess/pipeline.py` | Built, legacy, tested — **no Infrastructure adapter wraps it yet** |
| `_DemoTopicAssignmentEngine` | `bootstrap.py` | Deliberate demo stand-in (T-028), the only thing currently reachable via the API |
| `POST /collection-runs/{id}/analysis-runs` | `api/routes/analysis.py` | Built (T-028), wired to exactly one `StartAnalysisRunOrchestrator` instance via `api/deps.py` |

## 2. Can `StartAnalysisRun` already dispatch to real engines? **No — confirmed, not assumed.**

Three independent pieces of code evidence, all pointing the same way:

1. **`IAnalysisEngine.run(analysis_run_id, collection_run_id)`** — the Protocol itself does not
   accept an `analysis_type_id` or `key` parameter. A single engine instance has no per-call
   signal telling it which analysis type was requested.
2. **`StartAnalysisRunOrchestrator.__init__`** takes exactly one `analysis_engine: IAnalysisEngine`
   at construction. `execute()` never branches on `command.analysis_type_id` — the docstring says
   so explicitly ("does not load or validate `AnalysisType`'s catalog entry ... trusted as
   given").
3. **`api/deps.py`'s `get_start_analysis_run_orchestrator`** returns one FastAPI-injected
   orchestrator instance, built once at `bootstrap.py` startup, wired to `_DemoTopicAssignmentEngine`.
   `api/routes/analysis.py`'s own docstring: "this route module itself has no idea which concrete
   engine is behind the orchestrator."

This is not an oversight — `ARB-01`'s review already flagged and accepted this
(`GOVERNANCE_REGISTER.md` TD-03/TD-04: "2/10 Generalize → deferred"). `AnalysisType.py`'s own
docstring confirms the catalog/dispatch mechanism was deliberately left for "a future task, not
modeled here to avoid speculative work." **This delta is that future task**, not a bug being
fixed.

## 3. Is preprocess adaptation actually a prerequisite? **Yes — confirmed via code, for both real engines.**

- `collect/providers/platform/youtube.py:486`: every freshly-collected comment is written with
  `text_clean=""` — an **explicit** placeholder, inline-commented `# populated in preprocessing`.
  The column exists (schema-valid); its value is always empty until `preprocess.pipeline.
  run_preprocessing()` runs.
- `sentiment/pipeline.py:191`: `run_sentiment()` requires `"text_clean" not in df.columns` to be
  false — and even where the column exists, groups on `text_clean` values (line 126) to build the
  texts it scores. Empty strings would not error, but would score meaningless (empty) text.
- `topics/pipeline.py`/`embeddings/pipeline.py` (confirmed in Release Blocker #4's own Context
  Pack): same dependency, same "silently empty output, not an error" gotcha for missing/empty
  `text_clean`.

**Both** real analysis types (topics and sentiment) depend on preprocessing having run first.
This was already flagged when Release Blocker #4 was built; this review confirms it's not
optional for either path, not just topics.

## 4. What can be reused unchanged

- `TopicsAnalysisAdapter`, `SentimentAnalysisAdapter`, `EmbeddingsEngineAdapter` — all three,
  verbatim. No changes needed to any of them.
- `preprocess.pipeline.run_preprocessing()` + `build_default_preprocessor()` — verbatim. Already
  generalized: takes any registered `LanguageProvider` (Turkish, English both already exist in
  `providers/language/`), not hardcoded to one language. `financial_tr.py`'s domain normalization
  layers on top regardless of language — a deliberate, always-on Turkish-financial-vocabulary
  choice, not a hardcoding bug.
- `StartAnalysisRunOrchestrator`, `IAnalysisEngine` Protocol, `AnalysisType` entity — all
  unmodified. No Domain or Application code needs to change.
- `api/routes/analysis.py` — unmodified. The route already doesn't care which engine is behind
  the orchestrator; that stays true.

## 5. What requires adaptation (new, small pieces — not modifications to existing files)

**5.1 — `PreprocessEngineAdapter` (new file, mirrors `EmbeddingsEngineAdapter`'s exact shape).**
Wraps `run_preprocessing()` unmodified. Per-`collection_run_id`, not per-`analysis_run_id` — same
reasoning as embeddings: preprocessed text is a property of the collected comments, shared/cached
across however many analysis attempts run against the same `CollectionRun`. **`preprocess/` is a
Shared Core module (`BACKLOG.md`'s Engineering Workstreams policy) — this change requires a
Research Impact Assessment and a Product Impact Assessment in the same commit, even though the
underlying code is unchanged.** Sketch of both, so the size of this obligation is clear before
authorizing:
  - *Research impact:* none — Research's own pipeline already calls `run_preprocessing()`
    directly; wrapping it for API reachability doesn't change Research's own workflow.
  - *Product impact:* `financial_tr.py`'s always-on Turkish-financial normalization is not
    vertical-agnostic (Roadmap Risk R-6). For this Research MVP's single-vertical scope, that's
    correct behavior, not a gap — but a future multi-vertical/multi-language Product surface would
    need this normalization layer to become conditional. Flagging, not resolving, since resolving
    it is out of this delta's scope.

**5.2 — Two small composite `IAnalysisEngine` implementations** (new files, e.g.
`RealTopicsAnalysisEngine`, `RealSentimentAnalysisEngine`), each internally sequencing the
already-built pieces before delegating:
  - Topics: `PreprocessEngineAdapter.ensure_clean(collection_run_id)` →
    `EmbeddingsEngineAdapter.ensure_index(collection_run_id)` → construct a **fresh**
    `TopicsAnalysisAdapter` with the just-produced `embeddings_index_path` → `.run(...)`.
  - Sentiment: `PreprocessEngineAdapter.ensure_clean(collection_run_id)` → delegate to
    `SentimentAnalysisAdapter.run(...)` (no embeddings dependency).

  This is a real, necessary finding, not invented scope: **`TopicsAnalysisAdapter.
  __init__`'s `embeddings_index_path` is a fixed constructor argument, not derived per-call**
  (unlike `comments_path`, which correctly re-derives from `collection_run_id` inside `run()`).
  Constructed once at bootstrap with one path, it cannot serve more than one `CollectionRun`
  correctly. Two ways to close this gap: (a) modify `TopicsAnalysisAdapter` itself to derive the
  path dynamically, mirroring `comments_path`'s own pattern — touches an already-tested,
  already-frozen adapter; or (b) have the composite construct a **fresh** `TopicsAnalysisAdapter`
  instance per request, passing the correct path each time — touches nothing existing, only adds
  new composition code. **(b) is the minimum-diff option** and is what this plan recommends.

  Why a *composite Infrastructure adapter* rather than pushing this sequencing into `bootstrap.py`
  or `api/deps.py`: those two are explicitly documented as wiring-only, zero-sequencing-decision
  modules (`bootstrap.py`'s own docstring: "contains zero business logic ... no sequencing
  decisions"). Preprocess → embeddings → topics is a sequencing decision. The existing precedent
  for "an Infrastructure adapter that internally sequences multiple steps behind one `IAnalysisEngine.
  run()` call" is already established four times over (every existing adapter internally sequences
  checkpoint/cache steps) — this is the same pattern, one level higher, not a new kind of
  abstraction.

**5.3 — Bootstrap + `api/deps.py` wiring (small, contained).** Bootstrap mints two well-known,
fixed `AnalysisType` records (in-memory, same "stand-in, not Persistence" pattern already used for
Project/CollectionRun/AnalysisRun), constructs the two composite engines from 5.2, and builds two
`StartAnalysisRunOrchestrator` instances (unmodified class, just two instances instead of one).
`api/deps.py`'s provider function is extended to receive the request body and pick the matching
orchestrator by `analysis_type_id`, raising `404`/`400` for an unrecognized id — same shape as
`api/routes/analysis.py`'s existing `collection_run_id` consistency check, not a new pattern.

## 6. What is explicitly **not** in this plan, and why

- **No change to `IAnalysisEngine`'s Protocol signature.** Would resolve TD-03/TD-04 for real —
  a legitimate, bigger decision ARB-01 already reviewed and deferred. Not reopened here without
  new evidence contradicting that review, per the frozen-architecture rule.
- **No `IAnalysisTypeRepository` / Domain catalog.** `AnalysisType.py`'s own docstring already
  says this is intentionally out of Domain scope. Two well-known IDs at bootstrap serve the same
  purpose for a Research MVP's two known types, without inventing a persistence-backed catalog
  Sprint 5 hasn't authorized yet.
- **"Real Embeddings" is not a third dispatchable `AnalysisType`.** `EmbeddingsEngineAdapter`
  deliberately does not implement `IAnalysisEngine` (documented in its own class docstring — no
  `AnalysisType` named "embeddings" exists, nothing cites its output from a `Report`). It is a
  prerequisite *step inside* the Topics path (5.2), not a third user-facing analysis type. The
  original framing ("Real BERTopic / Real Sentiment / Real Embeddings" as three parallel targets)
  is corrected here: it is two real, dispatchable analysis types, one of which depends on
  embeddings as an internal step.

## 7. Exact minimum engineering, summarized

New files: `PreprocessEngineAdapter` (1), two composite `IAnalysisEngine` implementations (2),
plus contained edits to `bootstrap.py` (construct 2 real engines + 2 orchestrator instances
instead of 1 demo engine + 1 orchestrator) and `api/deps.py` (pick orchestrator by
`analysis_type_id`). Zero changes to Domain, zero changes to the four already-tested adapters,
zero changes to `StartAnalysisRunOrchestrator` or the API route. Shared Core policy triggers once
(the `PreprocessEngineAdapter` piece) — both impact assessments sketched in §5.1, ready to include
in full in the implementation commit.

## 8. Recommendation

Readiness Review concludes: **implementation is justified and well-scoped.** Evidence supports
every piece of the plan; no cheaper alternative exists (the gaps found — no dispatch mechanism,
no preprocess wrapper, `TopicsAnalysisAdapter`'s static `embeddings_index_path` — are all
structural, not solvable by configuration or evidence alone). Not started — awaiting explicit
authorization to proceed, per the instruction that produced this review.
