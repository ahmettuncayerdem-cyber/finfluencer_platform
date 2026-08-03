# Release Blocker #4 — Embeddings Pipeline Wrapping: Readiness Review + Migration Risk Checklist

**Date:** 2026-08-03
**Source:** `RELEASE_BLOCKING_ASSESSMENT.md` item #4 ("Embeddings pipeline unwrapped — no source
of `embeddings_index_path` for real `TopicsAnalysisAdapter` runs"), classified **Release
blocker**, priority 5 of 7.
**Not a numbered BACKLOG task.** No new `T-0XX` id, no new EPIC — this is Release Engineering
work against an already-approved Roadmap reuse classification (below), tracked only in this
checklist and `RELEASE_BLOCKING_ASSESSMENT.md` per the operator's own "no new governance
artifacts" instruction.

---

## Step 2 — Release Readiness Review

**What exactly is blocking release?** `TopicsAnalysisAdapter` (T-019) requires a caller-supplied
`embeddings_index_path` pointing to an already-produced `embeddings_index.parquet`. No
Infrastructure adapter currently produces one — `finfluencer.embeddings.pipeline.run_embeddings`
exists, is tested, but is invoked by nothing in `src/finfluencer/infrastructure/` or
`src/finfluencer/application/`. Without this, a real (non-demo) topic-analysis run has no way to
obtain its required input inside the six-layer architecture.

**Is this blocker already partially implemented?** Yes, entirely on the legacy side:
`finfluencer.embeddings.pipeline.run_embeddings` (cache-first, per-analyst checkpointed) and
`finfluencer.embeddings.sentence_transformer.SentenceTransformerProvider` (lazy-imports
`sentence_transformers`/`torch`, same discipline as `BERTopicRunner`/
`TransformerSentimentClassifier`) are both complete, tested (`tests/unit/test_embeddings/`,
confirmed passing without heavy ML deps installed, fake-provider injection). Nothing on the
Infrastructure side exists yet.

**Which existing code can be reused unchanged?** All of it — `run_embeddings()` and
`SentenceTransformerProvider` need zero modification. `IMPLEMENTATION_ROADMAP.md` §3's own reuse
table already classifies `embeddings/` (`base.py`, `pipeline.py`, `sentence_transformer.py`)
under the same "Analysis Engine — topic modeling and sentiment" row as `topics/`/`sentiment/`,
**"Wrapper required."** This is not a new classification invented here.

**Which code must only be wrapped?** `run_embeddings()` itself — called directly, unmodified,
mirroring `TopicsAnalysisAdapter`/`SentimentAnalysisAdapter`'s own established shape exactly
(derive isolated paths, construct `CheckpointManager`, call the legacy function, return an
outcome).

**Which code must be adapted?** None for this blocker specifically.

**Which code must be newly implemented?** One new Infrastructure adapter class
(`EmbeddingsEngineAdapter`) — thin, no new business logic, same tier as T-019/T-022's own
adapters.

**Which architecture rules constrain this work?** IG-001 (Infrastructure may not import
Presentation/API); BKG-001 (no business rule introduced — path derivation and a pass-through call
is not a business rule, same judgment call already made and accepted for T-010/T-019/T-022);
§12.1's Domain/Infrastructure dependency direction. No Domain entity in §10.1 names "Embedding" —
correctly, since none should be introduced (see contradiction check below).

**Does any contradiction exist?** No architectural contradiction. **One real, previously
under-scoped dependency was found and must be recorded, not silently absorbed into this
blocker's own implementation:** `run_topics()` (and therefore also `run_embeddings()`, which
reads `comments.parquet.text_clean`) requires a `text_clean` column that is populated by
`finfluencer.preprocess.pipeline` — confirmed directly (`collect/comments.py` writes no
`text_clean` column at all; `preprocess/pipeline.py`'s own docstring: "Fills the placeholder
`text_clean`/`tokens`/..."). **No Infrastructure adapter wraps `preprocess/` yet either.** This
means: even after today's `EmbeddingsEngineAdapter` lands, a real end-to-end topic-analysis run
against real `CollectionEngineAdapter`-produced data still cannot succeed, because
`comments.parquet` reaching this adapter would lack `text_clean` entirely. This is not a
contradiction in the architecture — `IMPLEMENTATION_ROADMAP.md` §3 already separately classifies
`preprocess/` as **"Adaptation required"** (not "Wrapper required," because
`preprocess/financial_tr.py` is Turkish-financial-vocabulary-specific, the concrete instance of
Roadmap Risk R-6's vertical-coupling problem) — a materially different, larger, riskier piece of
work than today's blocker, correctly out of today's scope. **Recorded here as a newly-precise
dependency for whoever picks up Release Blocker #6 (real dispatch behind `StartAnalysisRun`) or a
future preprocess-wrapping task — not implemented today, and today's adapter is still worth
building on its own merits (self-contained, fully fixture-testable, matches the Roadmap's own
reuse classification).**

## Step 3 — Migration Risk Checklist

**Legacy assumptions:** `run_embeddings()` assumes `comments.parquet` has `analyst_key` and
`text_clean` columns populated (see contradiction note above — real collected data does not yet
satisfy this; fixture-based tests, mirroring T-019/T-022's own precedent, construct it directly).
Assumes `provider.encode()` is stateless and safe to call repeatedly (documented in
`EmbeddingProvider`'s own Protocol docstring, unchanged).

**Runtime risks:** none beyond what T-019/T-022 already carry — `sentence_transformers`/`torch`
remain declared-but-uninstalled in this sandbox; this adapter's own tests, like `topics_adapter`'s
and `sentiment_adapter`'s, inject a fake `EmbeddingProvider` and never require them. A real
(non-fake) run additionally inherits the already-documented `torch >=2.9.0` Windows DLL risk
(`KNOWN_ISSUES.md`) — flagged, not newly introduced by this task.

**Data risks:** cache-key collisions are governed entirely by `run_embeddings()`'s own unmodified
hash composition (`text_clean::model_name::revision::device`) — no new risk introduced.
Per-`collection_run_id` (not per-`analysis_run_id`) output isolation is a deliberate divergence
from T-019/T-022's own per-`analysis_run_id` pattern (see Integration Decisions in the Context
Pack update) — the risk this introduces is that two different callers requesting embeddings for
the same `collection_run_id` will share one `embeddings_index.parquet`, which is the intended
caching behavior, not a defect, but is a genuine behavioral divergence worth flagging explicitly
since it looks different from the sibling adapters at first glance.

**Compatibility risks:** none — zero lines of `embeddings/*.py` changed; `AnalysisOutcome` is not
reused here (this adapter does not implement `IAnalysisEngine` — see Context Pack for why), so no
existing Domain contract is touched at all.

**Rollback strategy:** the new adapter is a pure addition — nothing existing calls it yet (no
orchestrator or `bootstrap.py` wiring is added in this change, since none currently needs it; the
demo `_DemoTopicAssignmentEngine` path is untouched). Rollback is a plain file deletion / `git
revert` with zero blast radius on any currently-running code path.

**Testing strategy:** mirror `test_topics_adapter.py`'s exact structure (fake-provider injection,
per-run isolation proof, empty-id rejection, ast-based Presentation/API import check, ast-based
no-legacy-mutation check) — same discipline, same fixtures-only approach, no heavy ML dependency
required.

**Release verification strategy:** full unit regression + IG-001 + architecture conformance, same
gates every prior Infrastructure adapter task has run. No integration/Walking-Skeleton-subset
impact expected (no route, no orchestrator, no `bootstrap.py` change).

**Environment assumptions:** none beyond what is already true — no network, no real Python
version requirement change, no new sandbox capability needed. This is precisely why this blocker,
unlike #1/#2/#3/#7, is executable here today.
