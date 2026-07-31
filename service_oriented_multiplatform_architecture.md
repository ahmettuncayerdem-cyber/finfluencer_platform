# Service-Oriented, Multi-Interface, Multi-Platform Target Architecture

**Scope.** Design, not implementation. Answers: how business logic becomes GUI-independent and callable from CLI/Python API/GUI/REST alike, and how the entity-centric model generalizes beyond YouTube to Reddit/X/TikTok/Telegram/news sites, while treating reproducibility/provenance/auditability/transparent preprocessing/publication output/long-term archival as first-class constraints rather than afterthoughts.

**Grounding.** This is not a green-field proposal. A prior audit of the current codebase (`collect/main.py`, stage `pipeline.py` modules, `core/registry.py`, `core/config.py`, `core/logging.py`, `core/contracts.py`) found the platform already close to this target in several respects, and specifically short in others. Both are named explicitly below so the plan reads as a gap-closure exercise, not a rewrite.

---

## 1. What's already correct (keep, formalize, don't rebuild)

- **Stage functions are already pure services.** `collect_channels`, `collect_videos`, `collect_comments`, `run_preprocessing`, `run_embeddings`, `run_sentiment`, `run_topics`, `run_topic_evolution`, `run_topic_sentiment` all take plain types (`Settings`, `pd.DataFrame`, `Path`, provider/checkpoint objects) and return `pd.DataFrame`. None read `sys.argv`, none accept a Typer `Context`, none `print()` (one exception, §6). They are already callable from a Python REPL, a notebook, or a future GUI/REST handler with zero adaptation. The task is to make this an explicit, documented, guaranteed contract — not to build it from scratch.
- **`run_pipeline()` is already the right orchestration seam.** It is a plain function (`LoadedConfig`, `stage: str`, `dry_run: bool` → `dict[str, pd.DataFrame]`), separate from the thin `@app.command()` Typer wrapper around it. A GUI or REST layer should call `run_pipeline` (or the finer-grained per-stage functions directly, for a GUI that wants per-stage progress rather than one opaque call) — not reimplement its file-existence checks or provider construction.
- **Config is already loaded once and threaded by reference** (`load_settings()` → one `LoadedConfig`), not re-read per stage. This is the right shape for a long-running GUI/REST process; §7 covers the one gap in it (staleness under env-var changes).
- **A provider abstraction and plugin registry already exist and already generalize.** `core/registry.py` implements `(kind, key) → class` registration with both in-tree (`@register("platform", "youtube")`) and out-of-tree (Python entry-points, group `finfluencer.providers`) discovery paths. `providers/platform/base.py` defines a `PlatformProvider` protocol (`resolve_channel`, `channel_metadata`, `enumerate_videos`, `fetch_video_metadata`, `fetch_top_level_comments`) that `collect/channels.py`/`videos.py`/`comments.py` call exclusively — no direct YouTube API calls leak into those modules. **This is the exact mechanism a Reddit/X/TikTok/Telegram/news adapter should plug into** — register a new provider under `("platform", "reddit")`, implement the protocol, done. No new plugin architecture needs to be invented; §5 extends the protocol's method set, not the registration mechanism.
- **Logging is already structured** (`structlog`, key-value fields, not string interpolation) — a correct foundation for the audit trail in §8, distinct from the progress-eventing gap in §4.

## 2. The layering model

```
┌─────────────────────────────────────────────────────────────────┐
│  Interface Adapters (thin, no business logic, swappable)         │
│  ┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌─────────────────┐  │
│  │   CLI    │ │  Python API  │ │   GUI    │ │    REST API     │  │
│  │ (Typer)  │ │  (facade)    │ │ (future) │ │    (future)     │  │
│  └────┬─────┘ └──────┬───────┘ └────┬─────┘ └────────┬────────┘  │
└───────┼──────────────┼──────────────┼────────────────┼───────────┘
        │              │              │                │
        └──────────────┴──────────────┴────────────────┘
                             │
                 ┌───────────────────────┐
                 │   Service Layer         │  ← all business logic lives here
                 │  (stage functions,      │     exclusively. No adapter above
                 │   run_pipeline())       │     this line contains a decision
                 └───────────┬─────────────┘     about what the research does.
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                     │
┌───────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Source Adapters│  │  Core Contracts   │  │  Infrastructure   │
│ (PlatformProvider│ │ (Pydantic models,│  │ (CheckpointManager,│
│  per platform) │  │  entity-centric)  │  │  cache, registry)  │
└───────────────┘  └──────────────────┘  └──────────────────┘
```

**The rule that makes this enforceable, not aspirational**: an interface adapter is only permitted to (a) parse/validate external input into the types a service function already accepts, (b) call exactly one service function or `run_pipeline`, (c) format/transport the returned `pd.DataFrame`/report object outward, and (d) handle transport-level errors (HTTP status codes, CLI exit codes, GUI dialogs). Anything else — a conditional that changes what gets computed, a data transformation, a retry policy, a default that isn't already the service function's own default — is business logic and belongs one layer down. This is a code-review checklist item, not just a diagram: any PR touching `cli/`, a future `gui/`, or a future `api/rest/` that adds an `if` statement deciding *what* to compute (rather than *how to present* the result) should be flagged.

## 3. Formalizing the Python API as a first-class interface

Today "Python API" callability is true by accident of clean function signatures, not by declared contract. Two additions make it explicit:

- A `finfluencer.api` package that re-exports the stage functions and `run_pipeline` as the *documented* public surface (today they're reached via internal module paths like `finfluencer.sentiment.pipeline.run_sentiment` — fine for in-tree use, but a GUI/REST layer should depend on a stable façade, not internal module layout, so internal refactors don't break every adapter).
- A single `RunContext` object (wrapping the existing `LoadedConfig` + `CheckpointManager` + `PlatformProvider` instances + the new `ProgressReporter` port from §4) that every interface constructs once and passes into every service call. CLI constructs one per process invocation (as today); a GUI or REST server constructs one per session/job and reuses it across many calls — this is what makes "long-running process, not re-spawned per action" actually work, and it's the natural home for the config-staleness fix in §7.

## 4. Progress and events (the one interaction primitive that doesn't exist yet)

Today, progress is observable only by tailing structured logs — there is no callback/event mechanism. This is fine for a CLI (logs print to the terminal) but insufficient for a GUI progress bar or a REST job-status endpoint, both of which need structured, queryable progress ("142 of 973 videos processed"), not log-tailing.

Proposed addition: a `ProgressReporter` protocol (methods like `stage_started(stage, total)`, `item_done(stage, n_done, n_total)`, `stage_finished(stage, summary)`), injected into `RunContext` alongside the checkpoint manager. Default implementation is a no-op (CLI can keep relying on structlog for now, or a thin adapter can bridge `ProgressReporter` calls into log lines). A GUI implementation updates a progress bar; a REST implementation writes to a job-status store polled by `GET /jobs/{id}`. This is deliberately a separate concern from the structlog audit trail — logs are the permanent record for §8; `ProgressReporter` is ephemeral UX signal that nobody needs to archive. Conflating them would pull UI concerns into the service layer, which is exactly the coupling this whole design exists to avoid.

## 5. REST and GUI: what they add, structurally

Neither REST nor a GUI needs new business logic — they need two things the CLI doesn't:

- **Asynchronous execution.** A CLI invocation blocks the terminal for the run's duration, which is acceptable for a researcher running a stage by hand. A REST client and a GUI both need to submit a run and poll/subscribe for completion rather than hold a connection open for a multi-hour BERTopic refit. This is a **job runner** sitting above the service layer (submits `run_pipeline(...)` or a single stage function to a worker/queue, tracks status via `ProgressReporter`, stores the result), not inside it — the job runner never decides *what* to compute, only *when/how* to execute the already-defined service call. A REST endpoint like `POST /stages/topics/run` accepts a config-slice payload, validates it against the same Pydantic `Settings`/config models the CLI already uses, and hands off to the job runner.
- **Schema for external validation.** A GUI form or a REST request body both need input validation before a service function is ever called — this already exists in the form of the Pydantic models in `core/contracts.py`/`core/config.py`. A REST layer gets an OpenAPI schema for near-free by exposing those same models (via FastAPI or similar) rather than hand-writing a parallel validation layer — another reason contracts must stay platform-agnostic and complete (§6) rather than something each adapter patches around.

## 6. Multi-platform source abstraction

**Current gap, precisely.** `PlatformProvider` already generalizes channel/video/comment collection cleanly. `collect/transcripts.py`, however, does not take a `PlatformProvider` at all — it has its own bespoke `fetcher` parameter, meaning transcript-like content (long-form text/media attached to a content item) is not behind the same abstraction boundary. This matters because most future platforms don't have a "transcript" at all (a Reddit post has no transcript; an X thread has no transcript) but *do* have an analogous "extended content body" concept (post body, thread text, article full text) that today's design has no generalized slot for.

**Proposed generalization** of the provider protocol, still registered through the existing `core/registry.py` mechanism (no new plugin system needed):

| Current (YouTube-specific) | Generalized | Reddit | X | TikTok | Telegram | News sites |
|---|---|---|---|---|---|---|
| `resolve_channel` | `resolve_source_container` | subreddit/user | account | account | channel | publication/section |
| `channel_metadata` | `source_container_metadata` | subreddit info | account info | account info | channel info | outlet metadata |
| `enumerate_videos` | `enumerate_content_items` | posts | tweets/threads | videos | messages/posts | articles |
| `fetch_video_metadata` | `fetch_content_item_metadata` | post metadata | tweet metadata | video metadata | message metadata | article metadata |
| `fetch_top_level_comments` | `fetch_interactions` | comments | replies/quotes | comments | replies/reactions | comments (if enabled) |
| *(bespoke `fetcher` param, not in protocol)* | `fetch_content_body` (optional method, default returns empty) | post self-text | tweet full text | caption/transcript | message text | article full text |

Every platform implements the subset of methods that applies to it; a `NotImplementedError`-by-default base class (already the shape of a `Protocol` with concrete fallbacks) lets, e.g., a platform with no interaction/reply concept simply not override `fetch_interactions`. This is why the generalized name matters more than it looks: `fetch_content_body` replaces the special-cased transcript fetcher with something every future platform can implement or skip through the same interface, instead of transcripts remaining a permanent one-off.

**Platform-specific fields do not go in the core contracts.** `made_for_kids` and `category_id` are YouTube-only concepts currently living directly on `VideoRecord`/`CommentRecord` — that pattern doesn't scale to five more platforms each contributing their own one-off fields (subreddit flair, tweet quote-count, TikTok duet-chain, Telegram forward-origin, article paywall status). The fix, consistent with the additive, non-breaking migration style already used for Phase 0: a `platform_metadata: dict[str, Any]` (or a linked side-table keyed by `content_item_id`/`interaction_id`, if query performance on specific platform fields matters later) holds everything platform-specific, while the core `ContentItem`/`Interaction` contracts (§7) hold only fields that are genuinely universal (id, container, author-hash, timestamp, text, engagement-count-if-any). Nothing platform-specific should ever be a required field on the core entity model — a required YouTube-only field is exactly what would need breaking changes when Reddit is added.

## 7. The entity-centric model, made source-agnostic

Phase 0 (already implemented, additive) introduced `Entity`/`EntityVideoLink`/`CanonicalVideoRecord`/`CanonicalCommentRecord` to resolve the multi-analyst-video-overlap problem. Extending it to multi-platform is a renaming-and-generalizing step, not a redesign, and should stay just as additive:

- `CanonicalVideoRecord` → **`ContentItem`**: a unit of primary content on any platform (video, post, tweet/thread, article). Universal fields: `content_item_id`, `source_platform` (`"youtube"`, `"reddit"`, ...), `container_ref` (channel/subreddit/account/outlet), `published_at`, `title_or_summary`, `body_text`, `engagement_counts: dict[str, int]` (view/like/upvote/retweet — heterogeneous by platform, hence a dict, not fixed columns), plus `platform_metadata` per §6.
- `CanonicalCommentRecord` → **`Interaction`**: a unit of response to a `ContentItem` (comment, reply, reply-to-reply). Universal fields: `interaction_id`, `content_item_id`, `commenter_hash`, `posted_at`, `text_raw`, `text_clean`, `tokens`, plus `platform_metadata`.
- `EntityVideoLinkRecord` → **`EntityContentLink`**: unchanged in spirit — many-to-many between a research `Entity` (a creator, a topic, a campaign, an event) and a `ContentItem`, now platform-agnostic since `ContentItem` itself is.
- `EntityRecord.membership_params` already stores an open `dict[str, Any]` (`channel_ids` today) — this generalizes for free to `{"platform": "reddit", "subreddit_ids": [...]}` or a cross-platform entity spanning a creator's YouTube channel *and* X account simultaneously, which is a real research scenario (tracking one financial influencer across platforms) this model should support without a schema change.

**Migration discipline stays the same as Phase 0**: additive tables, nothing existing broken, production stages keep reading `VideoRecord`/`CommentRecord` until each is explicitly migrated stage-by-stage. Multi-platform support does not require migrating YouTube's existing pipeline first — a Reddit adapter could be built and write directly into `ContentItem`/`Interaction` while YouTube stages still run on the legacy tables, with a compatibility view bridging them for any cross-platform pooled analysis in the interim.

## 8. Reproducibility, provenance, auditability

These three are related but distinct guarantees, worth designing separately so none gets silently dropped:

- **Reproducibility** — "can the exact same output be regenerated." Requires: (a) a **run manifest** written per pipeline invocation, capturing the full resolved config (already hashable via `hash_config_dict`), the installed package version/git commit, the Python/dependency environment (`pip freeze` or a lockfile hash), and every checkpoint's `config_slice_sha256` at run time; (b) checkpointing already gives content-addressed reproducibility at the stage level — the manifest is what stitches stage-level hashes into one run-level reproducibility statement.
- **Provenance** — "where did this specific row come from." Every row in every derived table already implicitly traces back through `comment_id`/`video_id` joins; making it explicit means each derived record (a sentiment score, a topic assignment) carries or is joinable to: source `interaction_id`/`content_item_id`, the stage that produced it, that stage's `config_slice_sha256`, and the run manifest ID from above. This is a natural extension of the checkpoint system already in place, not a new subsystem — the checkpoint markers already record the config hash; the gap is only that individual output *rows* don't currently carry a back-reference to which checkpointed run produced them (relevant when a table has been incrementally updated across many runs, as the basaran rebuild just did).
- **Auditability** — "can a reviewer verify what happened, after the fact, without re-running anything." The structured `structlog` audit trail already provides this at the log-line level (`stage_start`/`stage_done` with row counts, as seen throughout this project's diagnostic work). Formalizing it means: logs are append-only (never rotated away within a study's active lifetime), and every mutating operation on raw/canonical data (like the basaran purge) produces a written, timestamped record of exactly what changed and why — the before/after row-count reporting pattern already used ad hoc in that cleanup should become a standard, logged artifact of any such operation, not something I compose freely each time.

## 9. Transparent preprocessing

Preprocessing steps (tokenization, dedup thresholds, financial-domain-specific cleaning) must be independently inspectable and versioned, for the same reason model weights are pinned by revision: a silent library-version bump in a tokenizer changes results without changing any config value the checkpoint system would notice. Two additions: (a) preprocessing config (already checkpointed per `preprocess_comments__<analyst_key>`) should also record the *library versions* of any preprocessing dependency (not just the `preprocessor.key`/threshold values it already hashes), so a `should_run()` staleness check also catches a dependency upgrade, not just a config-value change; (b) a small, human-readable "preprocessing decision log" — plain text or markdown, not buried in JSONL — documenting *why* each threshold (`min_tokens`, `jaccard_dup_threshold`) was chosen, since a reviewer or co-author needs to evaluate methodology, not just replay it byte-for-byte.

## 10. Publication-ready outputs and long-term archival

`config/settings.yaml` already stages this intent structurally (`outputs/auto/{tables,figures,appendices,reports}` — regenerated every run; `outputs/manuscript` — human-edited prose the pipeline never overwrites; `outputs/replication` — described as a future "replication package staging area"). The target architecture should treat that `replication/` directory as the concrete deliverable of everything above, not a placeholder: a single "build replication package" service (callable from CLI/API/GUI/REST identically, per §2's rule) that assembles, into one archive, the run manifest (§8), the resolved config and roster files, checkpoint markers (proving what was and wasn't recomputed), the canonical entity-centric tables, and the auto-generated tables/figures — everything needed for a third party to verify results without needing this codebase's full runtime history.

**Long-term archival** adds one more constraint beyond reproducibility-today: format longevity beyond this codebase's own lifetime. Parquet is efficient but tool-dependent; the replication package should additionally include a plain-text/CSV export of the canonical entity-centric tables plus a codebook (field-by-field description, matching the Pydantic model docstrings that already exist in `core/contracts.py`) — a format a researcher can open in 15 years with nothing but a text editor, independent of whether `pyarrow`/`pandas` APIs have changed.

## 11. What changes, concretely (gap-closure list)

Ordered by dependency, each independently shippable and backward-compatible:

1. Remove the raw `print()` calls in `providers/platform/youtube.py` (`_execute()`) and replace with structured logging — a REST/GUI process must never have stdout side-effects it didn't ask for.
2. Bring `collect/transcripts.py` behind the `PlatformProvider` protocol as `fetch_content_body` (§6), retiring the bespoke `fetcher` parameter — closes the one place the current design isn't yet uniform.
3. Add unit tests for `collect/channels.py`, `collect/videos.py`, `collect/comments.py`, `collect/transcripts.py`, and `run_pipeline` itself — these are already library-callable by signature, but unverified; a GUI/REST layer will depend on them daily, so their contract needs test coverage before more is built on top.
4. Introduce `ProgressReporter` (§4) as an optional, no-op-by-default port on `RunContext` — additive, nothing existing breaks.
5. Introduce the `finfluencer.api` façade package (§3) and `RunContext` (§3) — a thin re-export layer, no logic moves.
6. Extend `PlatformProvider` with the generalized method names (§6) as a superset of the current protocol (old method names can remain as aliases during transition) — additive, opens the door to a first non-YouTube adapter without touching YouTube's implementation.
7. Add `ContentItem`/`Interaction`/`EntityContentLink` as Phase 1 of the entity-centric migration (§7), following the exact additive discipline of Phase 0 — new tables, zero changes to existing stages, until a stage is explicitly migrated.
8. Build the run-manifest writer (§8) and wire it into `run_pipeline` — the one piece with no direct precedent in the current code, and the one most worth doing first among the provenance items since everything else in §8-§10 depends on a run having a stable identity to reference.
9. Build the "assemble replication package" service (§10) last, once manifest + canonical tables + codebook generation all exist to draw from.

None of steps 1-7 require a GUI or REST server to exist yet — they are purely service-layer and contract work, verifiable by the existing test suite and CLI. The GUI and REST adapters themselves (§2, §5) become comparatively thin once these are in place, which is the point of doing them in this order.
