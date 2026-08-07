# Software Product Architecture — v1.0

**Prepared by:** Chief Software Architect, Finfluencer Research Platform
**Baseline:** Entity-Centric Migration v2 (CLOSED — accepted per `Entity_Centric_Migration_v2_Closeout_Report.md`). This document does not reopen, redesign, or extend that migration. It treats its output as frozen infrastructure and builds a product layer on top of it.
**Scope:** A design blueprint, not an implementation. No code is written or modified here. This is a consolidation document: it does not introduce a new architectural vision from nothing — it indexes, reconciles, and formalizes three design explorations already present in this repository (`CCR_OS_Architecture_v3.md`, `entity_centric_platform_architecture.md`, `service_oriented_multiplatform_architecture.md`) against the real, current codebase, and organizes them into one authoritative v1.0 reference.

---

## 1. Product Vision

The repository today is a working instrument for one study: retail investor sentiment and discourse across four Turkish financial YouTube analyst communities. Its architecture — entity-centric data model, checkpointed pipeline, pluggable providers, scope-based analysis, replication-package tooling — is, however, already substantially domain-agnostic in practice, not just in aspiration. `EntityRecord`, `AnalysisScope`, the registry-based provider system, and the `study:`/`replication:` blocks in `config/settings.yaml` were none of them built as YouTube-specific or finfluencer-specific mechanisms.

The product vision is to make that latent generality explicit and usable: a **Computational Social Science Research Platform** on which a researcher can define a study, collect and process digital-communication data, run validated analytical methods, and produce a citable, archivable, peer-reviewable output — without reading this codebase's internals to do it. The finfluencer study becomes the platform's first fully-realized study, not its identity. YouTube becomes the platform's first fully-realized source, not its only one.

This vision is deliberately bounded. It is not a general-purpose data platform, not a no-code tool, not a hosted multi-tenant SaaS product, and not an MLOps platform for training models — the same four exclusions `CCR_OS_Architecture_v3.md` §0 already stated, restated here because they still hold and should not quietly expand.

## 2. Platform Principles

Six principles govern every design decision below. The first four are inherited, verbatim in spirit, from `CCR_OS_Architecture_v3.md` §1, because nothing in this document's own review found a reason to revise them; the last two are added because this document's job is specifically the product/interface layer those three prior documents left as "future."

1. **A study is the unit of ownership, not a config file.** Everything a researcher does belongs to exactly one study; the platform's job is to make that boundary real (Section 7).
2. **Resolve once, persist, never re-derive.** The discipline `AnalysisScope`/`scope_id` established for comment-scope fingerprinting (Migration v2, Steps 3.1–3.4, closed and verified) is the platform's general rule for any value two independent code paths might otherwise recompute and disagree about — configuration hashes, method versions, provenance IDs alike.
3. **Providers, resolvers, and methods are plugins; studies and their data are not.** The registry pattern (`core/registry.py`) is the platform's one true extension mechanism. New capability is added by registering a new `(kind, key)`, never by branching core code on a new special case.
4. **Generality is earned by the second real study, not designed for the tenth in advance.** Nothing in Sections 7, 15, 16, or 17 below should be built past its "designed, not built" status until a second, genuinely different study exists to validate it against — see Section 22's phasing.
5. **Business logic lives in exactly one layer.** The service layer (Section 4) is the only place a decision about *what gets computed* is allowed to live. CLI, future GUI, future REST — none of them may contain that decision; they format and transport it (`service_oriented_multiplatform_architecture.md` §2).
6. **Every change is additive until proven necessary otherwise.** Every deliverable of the closed migration — `AnalystRecord` still present alongside `EntityRecord`, `configuration` still populated alongside `scope_id`, old parquet shapes reachable through compatibility views — followed this rule under real production constraints and it worked. The product layer inherits the same default: extend, deprecate-with-warning, never break silently.

## 3. User Personas

The platform already serves personas beyond "the researcher who writes Python," even though nothing here has named them until now. Evidence for each persona already exists in the repository, not just in imagination.

**Principal Investigator / Lead Researcher.** Defines a study's scope and research questions, approves configuration (`config/settings.yaml`'s `study:` block already exists for exactly this), reads reports and manuscripts. Does not need to read pipeline code. Today this person *is* the platform's operator by necessity; the product goal is that this stops being required.

**Research Coder / Annotator.** Produces and adjudicates gold-standard labels — evidenced concretely by `gold_standard_sample_n500_CODER_FACING_blinded.csv`, `adjudication_log_complete.csv`, and `sentiment_validation_allocation_log.csv` already present at repo root. This persona interacts with sampling and adjudication artifacts, never with pipeline internals, and today does so through loose CSV/XLSX hand-offs — a real, present workflow this platform already supports informally and should support formally (Section 12).

**Platform Engineer / Maintainer.** Extends providers, adds analysis methods, maintains the pipeline engine and checkpoint system. Currently one person, per `CCR_OS_Architecture_v3.md` §14's finding (two recorded git commits) and this document's own re-confirmation of that fact. The platform's plugin architecture (Section 14) exists specifically to keep this persona's required surface area small as the platform grows.

**External Replicator / Peer Reviewer.** Needs to verify a published result without platform access or this codebase's runtime history. Served today, partially, by `config/settings.yaml`'s `replication:` block (Zenodo deposit staging, tiered restricted-access packaging) — real, already-designed infrastructure, not a proposal (Section 13).

**Institution Administrator (future).** Named explicitly as future-scope in the mission brief. No current evidence of this persona being served at all; deferred to Section 17, consistent with `CCR_OS_Architecture_v3.md` §9's own governance layer, itself explicitly gated behind a second real study existing.

## 4. Modular Architecture

The codebase already implements a clean four-layer separation; `service_oriented_multiplatform_architecture.md` §1 confirmed this by direct code audit and this document reconfirms it holds for the current tree. No layer needs inventing — the work is formalizing the boundary as an enforced contract rather than an accidental property of clean function signatures.

```
Interface Adapters   CLI (Typer, working) · Python API (implicit today) · GUI (Section 15, planned) · REST (Section 16, planned)
        |
Service Layer         collect/*, preprocess/*, embeddings/*, sentiment/*, topics/*, analysis/*, market/*
                       — pure functions: (Settings, DataFrame, Path, provider/checkpoint objects) -> DataFrame
                       run_pipeline() as the orchestration seam
        |
Source Adapters        Core Contracts              Infrastructure
providers/platform/*   core/contracts.py            core/checkpoint.py (3-tier)
providers/language/*   (Pydantic, entity-centric)   core/registry.py
providers/market/*                                  core/config.py, core/logging.py
                                                      core/reproducibility.py, core/budgets.py
                                                      scope.py (AnalysisScope)
```

`market/` sits beside the main sentiment/topics line as a parallel analytical domain (financial market data and confirmatory statistics) rather than a stage in the same pipeline — its module boundary is correct as-is and should not be forced into the collect→process→analyze chain it doesn't belong to. `migration/` is infrastructure for one-time, reviewable backfills (`backfill_entity_model.py`, `backfill_topic_scope.py`) and is correctly separate from both the service layer and the pipeline engine — it should remain the home for any future backfill, not a pattern that leaks into steady-state modules.

**Update (Sprint 1/2):** `reporting/` (`master_table.py`, `inferential.py`, `manuscript_data.py`, `manuscript_figures.py`, `manuscript_tables.py`, `orchestrator.py`, `main.py`, `job.py`, `replication.py`) is a new service-layer package, added after this document's original diagram was drawn. It sits downstream of `outputs/{auto,manuscript}` (it reads pipeline outputs, not raw comments) with its own orchestration seam (`run_reporting_pipeline()`, Section 6 update) rather than being a stage inside `run_pipeline()`'s own chain — the same "parallel domain" relationship this section already describes for `market/`. Two of the four Interface Adapters this section lists as "planned" are, for the reporting package specifically, now real: the CLI row gains `finfluencer analyze`/`report`/`validate`/`export` (`reporting/main.py`, composed onto the same root `app` object as `collect/main.py`'s `run`), and the "GUI (planned)" row gains a working, if not yet UI-attached, adapter — `AnalysisJob` (`reporting/job.py`). See Section 12's update for the full mapping.

## 5. Module Dependency Graph

Dependencies flow in one direction, with two deliberate cross-cutting layers:

```
providers/{platform,language,market}   (leaf: no dependency on other finfluencer modules except core/)
        v
collect/*        --> writes canonical Video/Comment-shaped records
        v
preprocess/*      --> text cleaning, keyed by comment_id
        v
embeddings/*      --> content-addressed cache (Tier 3), keyed by (text, model, revision)
        v
sentiment/* ---+
        |      |
topics/* ------+--> analysis/* (topic_sentiment.py; scope_id-aware as of Step 3.4)
        v
market/*  (parallel domain; consumes sentiment/topics output but is not depended on by them)
        v
outputs/{auto,manuscript,replication}
```

Cross-cutting, depended on by every layer above: `core/contracts.py` (schema), `core/checkpoint.py` (staleness/skip logic), `core/registry.py` (provider lookup), `core/config.py` (settings loading), `scope.py` (scope resolution, consumed by `topics/pipeline.py` and, as of Step 3.4, `analysis/topic_sentiment.py` — not yet by `run_topic_evolution()`'s output schema, per the accepted `ADR-0001` deferral, which this document does not revisit).

No cycle exists in this graph today. The one dependency-graph risk worth naming: the ~30 root-level scripts (`build_*.py`, `run_R4.py`–`run_R7.py`, `pub_data_pull.py`, `final_health_report.py`, `export_master_table.py`) sit *outside* this graph entirely — they import from `src/finfluencer` but are not depended on by anything, and nothing enforces that they stay consistent with the modules they read from. This is addressed as a workspace-layout and refactoring concern in Sections 8 and 24, not a service-layer one.

## 6. Pipeline Engine

The pipeline engine already exists and is already correctly shaped; this section formalizes it as a named, documented component rather than an implicit property of `collect/main.py`.

**Contract.** Every stage function is a pure service: it accepts `Settings`, `pd.DataFrame`, `Path`, and provider/checkpoint objects, and returns a `pd.DataFrame`. None read `sys.argv`, none accept a CLI framework object, and — with one flagged exception in `providers/platform/youtube.py`'s `_execute()`, noted here as a real, minor, pre-existing gap rather than newly discovered — none produce uncontrolled stdout side effects. This makes every stage already callable from a REPL, a notebook, or a future GUI/REST handler with zero adaptation, which is the entire reason Sections 15 and 16 below are additive work rather than rewrites.

**Orchestration.** `run_pipeline(config, stage, dry_run)` is the single orchestration seam. It is a plain function, not a Typer command — the CLI's `@app.command()` wrapper around it should remain thin, and any future GUI or REST job runner (Section 16) should call `run_pipeline` or the finer-grained per-stage functions directly, never reimplement its file-existence and provider-construction logic.

**Checkpointing.** `CheckpointManager`'s three tiers (Tier 1 stage-level markers keyed by config-slice hash, Tier 2 `.done` files, Tier 3 content-addressed model/embedding cache) are confirmed schema-agnostic at the primitive level and remain untouched by every phase of the closed migration. This is the platform's single most valuable piece of existing infrastructure for the product goals in this document: it is what makes "resume, don't recompute" work identically whether the entity in scope is a YouTube creator today or a Reddit subreddit tomorrow.

**One real, named gap.** There is no event/progress callback mechanism today — progress is observable only by tailing structured logs. This is sufficient for a CLI and insufficient for a GUI progress bar or a REST job-status endpoint. `service_oriented_multiplatform_architecture.md` §4 already specifies the fix (a `ProgressReporter` protocol, no-op by default, injected alongside the checkpoint manager) — this document adopts that design without modification.

**Update (Sprint 2.1/2.6, closing this gap for the reporting pipeline specifically):** `reporting/orchestrator.py`'s `run_reporting_pipeline()` now takes an `on_progress(stage, event)` callback and a cooperative `cancel_event`, emitting `start`/`done`/`skipped` events per stage. `reporting/job.py`'s `AnalysisJob` is the first real consumer of this contract — a stateful, background-thread adapter exposing pollable `status`/`current_stage`/`progress`/`outputs` and a structured event timeline for GUI use, without any change to the orchestrator itself. See `ADR-Sprint2-01_AnalysisJob_Composes_Over_Orchestrator.md` for the decision record. This closes the gap for the reporting pipeline; the original `collect/` pipeline (Section 6's main subject above) does not yet have this mechanism — the gap described in this section's original text still applies there.

## 7. Project Management System

"Study" is the platform's project unit, and the seed of this already exists: `config/settings.yaml`'s `study:` block (`name`, `version`, `root_seed`, `description`) is a real, working, single-study instance of exactly this concept. The product-level generalization — multiple such studies coexisting, each owning its own entity graph, checkpoint namespace, and provenance trail — is designed in full in `CCR_OS_Architecture_v3.md` §3 and §5 (the `Study` record; lifecycle `draft → active → archived`; per-study checkpoint namespacing; study templates for one-command scaffolding) and is not re-derived here, only referenced as the authoritative design for this component.

What this document adds beyond that prior design: the Project Management System's job is specifically to let a Principal Investigator persona (Section 3) create and monitor a study without editing YAML by hand — the study template mechanism (`single-platform-sentiment`, `cross-platform-comparison`, etc., per `CCR_OS_Architecture_v3.md` §5) is the concrete feature that serves that persona, and should be the first piece of the `Study` design actually built, ahead of quota enforcement or archival policy, because it is the piece with a named user waiting on it today (the PI persona already exists; a second tenant does not yet).

## 8. Workspace Layout

Current, real layout:

```
src/finfluencer/{collect,preprocess,embeddings,sentiment,topics,analysis,market,migration,providers,core}/
config/{settings.yaml, analysts.yaml}
data/{raw, processed, market}
cache/            (Tier-3 content-addressed model/embedding cache)
checkpoints/      (Tier-1/2 markers)
outputs/
  auto/{tables, figures, reports}     -- regenerated every run, never hand-edited
  manuscript/{figures}                -- human-edited prose, pipeline never overwrites
  market/                              -- market-domain outputs
tests/unit/{test_analysis, test_core, test_embeddings, test_market, test_migration, test_preprocess, test_providers, test_sentiment, test_topics, test_utils}
logs/
```

This structure is correct and should not be reorganized. The layout problem is not inside `src/`, `data/`, or `outputs/` — it is at repo root, where ~30 loose analysis/build scripts (`build_e5_e6_tables.py`, `build_e7_tables*.py`, `run_R4.py`–`run_R7.py`, `pub_data_pull.py`, `export_master_table.py`, `final_health_report.py`, `diagnose_sentiment_memory.py`, `recover_basaran_only.py`, `smoke_test_market_module.py`) sit interleaved with dozens of manuscript-support data artifacts (gold-sample CSVs, adjudication logs, `E5`/`E6`/`E7` result files, `manuscript_*.csv`, four generations of `Graphical_Abstract*` images, and two stale `.zip` archives) and five separate architecture/status documents. None of this is a defect in the running system — every one of these files was produced deliberately and most are still live inputs to the manuscript. It is a discoverability and long-term-maintenance problem, addressed concretely in Section 24.

## 9. Configuration System

Already well-designed and should be extended, not replaced. `config/settings.yaml` is a single, hierarchically-organized, Pydantic-validated document (`study`, `providers`, `collection`, `preprocessing`, `sentiment`, `topics`, `dictionaries`, `statistics`, `behavioural_indices`, `output`, `ethics`, `replication`, `llm`), loaded once via `load_settings()` into an immutable `LoadedConfig` and threaded by reference through a run — the correct shape for a future long-running GUI/REST process (`service_oriented_multiplatform_architecture.md` §1 already flags this as a kept-as-is strength). `config/analysts.yaml` plays the role of a study's entity roster.

Two extension points, both additive:

**Per-study configuration, not one global file.** As the Project Management System (Section 7) generalizes `study:` from a block in one file into a record with many instances, `settings.yaml`'s non-`study` sections become the *defaults* a new study's config is scaffolded from (via the templates in Section 7), not a single global truth every study shares. This is a straightforward generalization of a pattern the file already models internally.

**Environment staleness.** `service_oriented_multiplatform_architecture.md` §7 flags one real gap: config is loaded once per process, correct for a CLI invocation, but a long-running GUI/REST session (Section 15, 16) needs a defined reload/staleness policy the current single-load model doesn't specify. This should be resolved inside the `RunContext` object (Section 6, 16), not by changing how `load_settings()` itself works.

## 10. Experiment Tracking

Partially built, correctly designed, missing one connective piece. What exists today: `core/reproducibility.py`'s `root_seed`/`derive_seed()` convention (all randomness — UMAP, HDBSCAN, subsampling, permutation tests — traces to one seed, set once in `study:` and never mid-study); `hash_config_dict()` producing the `config_slice_sha256` every checkpoint marker already carries; and, as of the closed migration, `scope_id` as a persisted, content-hashed record of exactly which comments a given analysis ran over.

The named gap, already identified by prior review and not contradicted by anything found in this document's own audit: there is no single **run manifest** stitching these per-stage hashes into one run-level reproducibility statement (installed package version/commit, resolved config, every checkpoint's config-slice hash, all in one retrievable record keyed by a run ID). `service_oriented_multiplatform_architecture.md` §8 specifies this component in full; this document endorses building it as the connective layer between the checkpoint system's existing per-stage rigor and the Publication Engine's need (Section 13) for one complete, citable provenance record per study.

**Update (Sprint 2.1, closing this gap for the reporting pipeline):** `run_reporting_pipeline()`'s `_write_manifest_safe()` now writes exactly this record — `build_provenance()`'s output (config, checkpoint state, status, error detail) — to `output.paths.checkpoints/run_manifests/<run_id>.json` after every stage execution, best-effort (a manifest-write failure is logged, never allowed to mask the pipeline's own result). This is the run manifest this section calls for, scoped to the reporting pipeline; the original `collect/` pipeline's own run-manifest gap (this section's original subject) is unaffected and still open.

## 11. Data Lineage

The clearest example of a fully-shipped, verified lineage mechanism in this codebase today is `AnalysisScope`/`scope_id` itself — not a proposed design, but the actual, closed output of Migration v2 Steps 3.1–3.4: a scope is resolved once, its member comment-ID set is hashed and persisted, and every downstream consumer (topic modeling, and as of Step 3.4, topic-sentiment cross-tabs) reads that persisted value rather than re-deriving it. This is data lineage as a working mechanism, not an aspiration, and it is the concrete proof that the "resolve once, persist, never re-derive" principle (Section 2, #2) is buildable and holds up under real production data — it already has.

The generalization this document recommends, without proposing new migration work: the same discipline `scope_id` established for "which comments are in scope" extends naturally to method versioning (which embedding-model revision, which sentiment-classifier checkpoint, which BERTopic fit produced this row) and provider versioning (`CCR_OS_Architecture_v3.md` §4's `provider.yaml` manifest convention). Every derived row should ultimately be traceable, by ID, to the exact scope, method version, and run manifest (Section 10) that produced it — the mechanism for the first of these three already exists and works; the other two are designed but not built.

## 12. Reporting Framework

`outputs/auto/{tables,figures,reports}` already exists as a structural convention, is already populated by real runs, and already enforces the correct separation (regenerated automatically, never hand-edited, distinct from `outputs/manuscript`'s human-edited prose). `final_health_report.py`'s `health_report.json` is a working instance of an automated report artifact today.

The product-level gap is not the convention, which is sound — it is that report *generation* is currently done by individually-invoked root-level scripts (Section 8) rather than through the pipeline engine's own service-layer contract (Section 4, 6). Bringing report generation behind a proper `finfluencer.api` façade (Section 14, 16) — so "generate the health report" or "generate table 3" is a service call any interface can invoke, not a script a person runs by hand — is the concrete next step for this component, and is scoped as part of the gap-closure list already specified in `service_oriented_multiplatform_architecture.md` §11.

**Update (Sprint 1/2, closing this gap for statistical + manuscript reporting):** the `reporting/` package (`master_table.py`, `inferential.py`, `manuscript_data.py`, `manuscript_figures.py`, `manuscript_tables.py`) now implements exactly the report-generation service-layer contract this section calls for, and `reporting/orchestrator.py`'s `run_reporting_pipeline()` is the single seam every caller goes through — invoked identically by the CLI (`finfluencer analyze`/`report`/`validate`/`export`, `reporting/main.py`) and by `AnalysisJob` (`reporting/job.py`, a GUI-facing adapter over the same engine, see `ADR-Sprint2-01_AnalysisJob_Composes_Over_Orchestrator.md`). This is "generate table 3" as a service call any interface can invoke, not a hand-run script, delivered without a `finfluencer.api` façade module existing yet — the façade this section anticipates turns out to already be `run_reporting_pipeline()` itself. The original root-level scripts (`build_stats_tables.py`, `build_stats_figures.py`, etc.) remain in place as the historical, unrefactored versions these packaged modules were built from; consolidating or removing them is not yet done and remains open.

## 13. Publication Engine

This is, concretely, the platform's most mature forward-looking component on paper, and one of its least formalized in practice. `config/settings.yaml`'s `replication:` block already specifies a staged model with no analogue elsewhere in this document's review: a `stage` field (`exploratory → internal → submission → publication`) controlling reproducibility-check strictness, a Zenodo deposit target with sandbox/production modes and embargo support, a tiered package design (`include_model_weights`, plus a `restricted_tier` for raw comment text under access control, currently unset), and — evidenced concretely by real repo contents — an active publication workflow already producing `manuscript_fig{1,2,3}_data.csv`, `manuscript_table1.csv`, `pub_data.json`, and staged Referee Report documents.

What's designed but not yet built, per `service_oriented_multiplatform_architecture.md` §10: the "assemble replication package" service itself — one callable (from CLI/API/GUI/REST identically, per the layering rule in Section 2) that draws together the run manifest (Section 10), resolved config and roster, checkpoint markers, canonical entity-centric tables, and a codebook (field-by-field descriptions already latent in `core/contracts.py`'s own Pydantic docstrings) into one archive. Long-term archival additionally requires a plain-text/CSV export path alongside parquet, so a replication package remains openable independent of this codebase's own future. None of this requires new design work; it requires building what `replication:`'s config surface already promises.

**Update (Sprint 2.5, closing part of this gap):** `reporting/replication.py`'s `build_replication_package()` is now exactly this callable — invoked identically by the CLI's `export` command (`reporting/main.py`) and available to any future GUI/REST caller with no CLI dependency. It stages the current report-stage outputs (manuscript, figures, tables, reports) into a timestamped snapshot under `output.paths.replication`, with dry-run and force-overwrite support. What remains open, per this section's original text: true archival/versioning/Zenodo-deposition logic, the plain-text/CSV export path, and folding in the run manifest (Section 10) as part of the assembled package rather than a separate artifact — `replication.py`'s own docstring states these as explicitly out of scope for what was built.

## 14. Plugin System

Already real, already working, and the platform's primary extension mechanism going forward. `core/registry.py` implements `(kind, key) -> class` registration with both in-tree decorator registration and out-of-tree Python entry-point discovery (group `finfluencer.providers`), and three provider kinds — `platform` (YouTube), `language` (Turkish, English), `market` (TCMB EVDS, yfinance) — already use it correctly, with `providers/platform/base.py`'s `PlatformProvider` protocol as the clearest example of the pattern done right: `collect/channels.py`/`videos.py`/`comments.py` call the protocol exclusively, with no YouTube-specific logic leaking upward.

Two extensions are designed, not yet built, and require no new mechanism — only new registrations against the existing registry:

**A fourth provider kind: analysis method.** Sentiment, topic modeling, and embedding generation become `AnalysisMethodProvider` registrations rather than pipeline-specific code that happens to call a swappable model (`CCR_OS_Architecture_v3.md` §4).

**A fifth: entity-type / membership resolver.** `creator`-type membership (the only resolver that exists today, implicitly, as `analysts.yaml`) generalizes to `topic`, `campaign`, and `event` resolvers under the same registry, per `entity_centric_platform_architecture.md` §2.4 — this is Migration v2's own Phase 4, already fully designed there and correctly out of this document's scope to redesign, only to reference as the plugin system's future third dimension.

A small manifest convention (`provider.yaml`: kind, key, config schema, semantic version, per `CCR_OS_Architecture_v3.md` §4) is the one genuinely new addition this layer needs, so that a study's run manifest (Section 10) can record not just "used the YouTube provider" but which version.

## 15. GUI Architecture

Not built. Fully specified as a thin layer, and should remain thin by design. Per `service_oriented_multiplatform_architecture.md` §5 and `CCR_OS_Architecture_v3.md` §8: a GUI ("Researcher Portal") is a convenience layer over the REST API (Section 16), whose only jobs are (a) letting a Principal Investigator persona (Section 3) create a study from a template (Section 7) without hand-editing YAML, and (b) surfacing job/quota status via the `ProgressReporter` mechanism (Section 6). It contains no business logic of its own — any GUI code that decides *what* gets computed, rather than *how a result is displayed*, is a layering violation per Section 2, #5, full stop, and should be flagged in review exactly as `service_oriented_multiplatform_architecture.md` §2 already specifies as a PR checklist item.

Build order: the GUI depends on the REST API existing and the Project Management System's templates existing; it should not be started before either.

## 16. REST API Architecture

Not built. Fully specified: a `finfluencer.api` façade package re-exporting stage functions and `run_pipeline` as a documented, stable public surface (so REST/GUI adapters depend on a contract, not on internal module layout); a `RunContext` object bundling `LoadedConfig` + `CheckpointManager` + provider instances + `ProgressReporter`, constructed once per session/job rather than once per CLI invocation; an asynchronous job runner sitting above the service layer (submits a stage or `run_pipeline` call to a worker/queue, tracks status, never itself decides what to compute); and request/response schemas derived directly from the same Pydantic models already in `core/contracts.py`/`core/config.py`, which — via FastAPI or an equivalent — yields an OpenAPI schema close to free rather than requiring a hand-written parallel validation layer.

Per `CCR_OS_Architecture_v3.md` §8's specific addition to this design: once the Project Management System (Section 7) exists, every REST endpoint should be scoped by `study_id` and should enforce the access tiers from Section 17 — the REST layer is where storage-level study isolation is actually enforced for any client that isn't a trusted local CLI session.

## 17. Authentication and Permissions (Future)

Explicitly future-scope, does not exist today, and — per `CCR_OS_Architecture_v3.md` §9 and §14 — should not be built ahead of a real second study and a real answer from an actual institutional ethics/compliance function about what it requires. The design that exists, ready when that trigger condition is met: three roles (`study_owner`, `contributor`, `institution_admin`), a `data_sensitivity_tier` per study (`public`, `pseudonymized`, `identifiable`) gating storage backend and role access, and an audit trail appended on every identifiable-tier access, study status transition, and cross-study data-sharing event. This is intentionally the minimum role set the platform's ethics gate needs to be meaningful, not a general-purpose RBAC system — building more than this before it's needed is exactly the kind of premature investment Section 2's principles exist to prevent.

## 18. Deployment Architecture

Current reality, stated plainly: this is a single-machine, filesystem-based, synchronously-executed CLI application. There is no Dockerfile, no CI workflow, and no `poetry.lock` committed in the current tree, despite `pyproject.toml`'s own header comments explicitly stating the lockfile "MUST be committed" as part of its reproducibility contract — a real, present gap between documented intent and current state, worth naming rather than assuming resolved.

Target architecture, per `CCR_OS_Architecture_v3.md` §3, deferred until the Project Management System (Section 7) has a second real tenant to justify it: a per-study-partitioned parquet layout on a shared filesystem or S3-compatible object store (`studies/{study_id}/...`), explicitly *not* a relational database migration — the same reasoning Migration v2 already gave for staying parquet-based holds at this scale too. Above that storage layer, a job queue and worker pool (Section 7's scheduler) replace synchronous CLI execution for anything the REST API (Section 16) submits, while the CLI itself may continue running synchronously in-process indefinitely — the two execution models are not mutually exclusive and the CLI does not need to be rebuilt to support the async path.

The immediately actionable item in this section, independent of any future-tenancy work: commit a `poetry.lock`, and add a minimal CI workflow that runs the existing test suite on every change — both close a gap against the project's own already-stated standard, not a new standard invented here.

## 19. Testing Strategy

Real, current state: nine test modules under `tests/unit/` map cleanly to nine source packages (`test_analysis`, `test_core`, `test_embeddings`, `test_market`, `test_migration`, `test_preprocess`, `test_providers`, `test_sentiment`, `test_topics`, `test_utils` — the mapping itself is evidence the codebase's modular boundaries, Section 4, are already reflected in how it's tested). Coverage tooling is present and run (`coverage.xml`, `htmlcov/`); the last recorded figure is 48.6% line coverage, a real number from this repository's own coverage report, not an estimate.

Two testing-strategy commitments follow directly from that number and from this document's own findings, not from generic best practice: first, coverage concentrated away from the most-changed modules (the finding `CCR_OS_Architecture_v3.md` §14 already surfaced) is a materially worse position than the same aggregate percentage evenly spread — a coverage target should be expressed per-module for the service layer (Section 4) specifically, not as one repo-wide number, because that is where a regression is costliest. Second, the interface adapters this document proposes (Sections 15, 16) are new, untested-by-construction code the moment they exist; `service_oriented_multiplatform_architecture.md` §11's own gap-closure list correctly sequences adding tests for the currently-unverified-but-already-callable collection functions (`collect/channels.py`, `videos.py`, `comments.py`, `transcripts.py`, `run_pipeline` itself) *before* building GUI/REST on top of them, on the reasoning that those interfaces will depend on this contract daily. This document adopts that sequencing without modification.

## 20. Versioning Strategy

Three distinct things need versions in this platform, and today only one of them consistently has one. **Platform version**: `pyproject.toml` declares `0.1.0`; no changelog or tagging discipline currently attaches meaning to version bumps, which should be resolved by adopting standard semantic versioning against the `finfluencer.api` façade (Section 16) once it exists — that façade, not internal module layout, is what a version number should describe compatibility for. **Study version**: already real and working — `study.version` in `settings.yaml` is explicitly scoped to "a substantive change to how the study runs," separate from platform version, and this separation is correct and should not be collapsed. **Method/model version**: partially real (`topics.embedding_model.revision` exists as a config field, currently the literal placeholder `"REPLACE_WITH_HF_COMMIT_SHA"` pending the still-open `topic_evolution.parquet` regeneration, per the closeout report — not revisited here) and should generalize, per Section 14's plugin manifest convention, to every registered provider and, eventually, every `AnalysisMethodProvider`.

**Update (Sprint 2.7A, closing the platform-version half of this gap):** standard SemVer discipline for the platform version is now formalized in `docs/VERSIONING.md` and `docs/RELEASING.md`, ahead of the `finfluencer.api` façade this paragraph originally gated it on — in practice, `run_reporting_pipeline()`, the CLI, and `AnalysisJob` (Section 12 update) already constitute the compatibility surface a version number describes, so the façade was not, in the end, a hard precondition. This closes the versioning half of Sprint 2.7A's own Release Hardening effort: `finfluencer.__version__` is enforced to match `pyproject.toml` by `tests/unit/test_version_sync.py`; tagging and CHANGELOG discipline are defined in `docs/RELEASING.md`. This section's third, distinct axis — a **research/citation version**, tracked in `CITATION.cff` and independent of both platform and study version — was identified during Sprint 2.7A (`docs/VERSIONING.md`, TD-10) as a fourth thing this platform versions; it is not a generalization of platform version and should not be collapsed into it, mirroring this section's own existing warning against collapsing study version into platform version.

Contract versioning discipline is already demonstrated and should be the template going forward, not reinvented: `AnalystRecord`/`VideoRecord`/`CommentRecord` remain present in `core/contracts.py`'s `__all__` today, deprecated but not removed, behind the Migration v2 compatibility view — new fields and new records are added alongside old ones with an explicit deprecation window, never as an in-place breaking rename. Section 2, #6 states this as a principle; this is the evidence it already works in practice.

## 21. Extension Strategy

How new capability gets added, concretely, using only mechanisms that already exist:

*A new data source* (Reddit, X, a news archive) implements the `PlatformProvider` protocol and registers under a new `(kind="platform", key=...)` — per `service_oriented_multiplatform_architecture.md` §6, the protocol should first be generalized (method names like `resolve_source_container` in place of `resolve_channel`) so it reads as source-agnostic rather than YouTube-shaped, with old method names retained as aliases during transition, additive per Section 2's rule. Platform-specific fields go in a `platform_metadata: dict`, never as new required fields on core contracts — the same discipline already applied to `made_for_kids`/`category_id`.

*A new analysis method* (a different topic model, a causal-inference test, an LLM-based coding rubric) registers as an `AnalysisMethodProvider` (Section 14) once that provider kind exists; until then, it follows the same pattern `sentiment/` and `topics/` already use — a pipeline module calling a swappable, registered implementation underneath.

*A new entity/study type* (a `topic`, `campaign`, or `event`-defined unit of study, rather than a `creator`) implements a membership resolver against the registry, per `entity_centric_platform_architecture.md` §2.4 — Migration v2's own Phase 4, unchanged and unrevisited here, simply named as the concrete instance of "extension" this section describes generically.

*A new study/project* is scaffolded from a template (Section 7) once the Project Management System exists; today it is a manual clone-and-edit of `config/settings.yaml` and `analysts.yaml`, which is the real, current, correct-for-now answer, worth stating plainly rather than implying a mechanism exists before it does.

## 22. Product Roadmap

This roadmap proposes no new migration. Every item below is already designed in one of the three prior documents this document consolidates; nothing here is a new architectural commitment — it is a prioritized reading list against work already specified, organized by what's actionable now versus what is correctly gated behind a precondition that hasn't happened yet.

**Now — no precondition, closes real, already-named gaps.** Execute the two operational items already on record from the migration closeout (regenerate `topic_evolution.parquet`; apply `ADR-0001`'s roadmap patch) — restated here only because they remain open, not reopened as new work. Fix the broken `finfluencer.cli:app` entry point. ~~Commit `poetry.lock`; add a CI workflow running the existing test suite (Section 18, 19).~~ **Done, Sprint 2.7A:** `poetry.lock` is committed (Milestone 2.7A.1); `.github/workflows/ci.yml` runs a scoped `ruff`/`mypy` lint gate plus the full test suite across an `ubuntu-latest`/`windows-latest` × Python `3.11`/`3.12` matrix (Milestone 2.7A.2). Add unit tests for the currently-untested-but-callable collection functions (Section 19). None of this requires a design decision this document or its predecessors haven't already made.

**Near-term — service-layer formalization, per `service_oriented_multiplatform_architecture.md` §11's own ordered list.** Retire the bespoke transcript fetcher in favor of the generalized provider protocol; introduce `ProgressReporter` (Section 6) and the `finfluencer.api` façade + `RunContext` (Sections 16, 9) as additive, no-op-by-default components; build the run-manifest writer (Section 10). Each is independently shippable and backward-compatible, in the dependency order already specified there.

**Mid-term — gated behind the Project Management System's first real use (Section 7).** Build study templates and the `Study` record; this is Phase A of `CCR_OS_Architecture_v3.md` §12, already scoped there as buildable now, without a second tenant, because it validates against the one study whose expected behavior is already fully known.

**Longer-term — explicitly gated behind a second, real, different study existing (`CCR_OS_Architecture_v3.md` §12 Phase B's own stated success criterion: onboarding it requires zero kernel changes).** REST API, GUI, multi-platform provider generalization, the analysis-method and entity-type provider kinds. Starting these before Phase B's criterion is met or has told you specifically what Phase A got wrong is the one sequencing error this document actively recommends against, because it is the exact one `CCR_OS_Architecture_v3.md` §12 already flags as the failure mode this platform's own past scope-exploration made concrete.

**Deferred, correctly, pending an organizational answer this document cannot supply.** Multi-tenant scheduler, governance/access-control/audit layer (Section 17), cross-study knowledge catalog. `CCR_OS_Architecture_v3.md` §14 already states why plainly: these require a team, not just an architecture, and no document can design that into existence.

## 23. Risks

| Risk | Evidence | Mitigation |
|---|---|---|
| Single-developer project, two recorded git commits | Confirmed directly in this document's own review (`git log --oneline` = 2) | Named risk, not architecturally mitigable; bounds how much of Section 22's "longer-term" tier should be attempted before more capacity exists |
| Test coverage (48.6%) concentrated away from most-changed modules | `coverage.xml` (901/1854 lines), consistent with prior finding | Per-module coverage targets for the service layer specifically (Section 19), not a repo-wide aggregate |
| Root-level script and artifact sprawl (~30 scripts, dozens of data/report files, five architecture documents at repo root) | Directly observed in this document's own repo audit | Section 24 |
| `topic_evolution.parquet` regeneration still pending real-environment execution | Carried forward from the migration closeout report, not reopened here | Execute the existing runbook; not a design question |
| Documentation fragmentation: this is now the fourth substantial architecture document for one platform (three prior, plus this one) | Directly observed — `CCR_OS_Architecture_v3.md`, `entity_centric_platform_architecture.md`, `service_oriented_multiplatform_architecture.md` all exist, pre-dating this one, with real content overlap | Section 24 recommends this document become the single indexed entry point, with the three prior documents kept as historical design inputs rather than independently-maintained parallel sources of truth going forward |
| Building REST/GUI/multi-tenancy ahead of a second real study, repeating the exact sequencing risk `CCR_OS_Architecture_v3.md` already names | This document's own Section 22 roadmap is the concrete guardrail | Do not start "longer-term" tier work before Phase B's success criterion (Section 22) is met |
| Config/deployment gap between stated intent and reality (`poetry.lock` "MUST be committed" per `pyproject.toml`'s own header, but absent) | Directly observed | Section 18, listed as immediately actionable, not deferred |

## 24. Recommended Repository Refactoring

Recommendations only — nothing in this section has been executed, and nothing here proposes touching `src/finfluencer/` module boundaries, which are already correct (Section 4). All of the following is additive reorganization, reversible, and does not change any module's public behavior.

**Consolidate root-level scripts.** Move `build_*.py`, `run_R4.py`–`run_R7.py`, `pub_data_pull.py`, `export_master_table.py`, `final_health_report.py`, `diagnose_sentiment_memory.py`, `recover_basaran_only.py`, and `smoke_test_market_module.py` into a `scripts/` or `research/` directory, distinct from `src/finfluencer/`. This is purely a discoverability move: it makes the Section 5 dependency-graph boundary ("these are consumers of the package, not part of it") visible in the directory layout, not just true in principle. It does not require rewriting any of them, though it is also the natural moment to note — without acting on it here — that these are the scripts the Reporting Framework (Section 12) should eventually absorb behind the service layer.

**Consolidate manuscript-support artifacts.** The gold-sample, adjudication, `E5`/`E6`/`E7`, and `manuscript_*` files at repo root are live research artifacts, not clutter to delete — but they belong under `outputs/manuscript/` or a new `outputs/manuscript_support/`, consistent with the layout Section 8 already confirms is correct everywhere else in the tree.

**Index the architecture documents.** Four documents now describe this platform's target architecture at varying scopes (three prior, plus this one). Recommend a `docs/architecture/` directory with this document (`Software_Product_Architecture_v1.0.md`) as the entry point and index, and the three prior documents retained underneath it as dated design inputs already absorbed into this one — not deleted, since they contain detail (e.g., the full `CanonicalVideoRecord → Artifact` schema proposal, the complete `ContentItem`/`Interaction` field tables) this document intentionally referenced rather than reproduced in full.

**Review stale build artifacts.** `finfluencer_missing_subpackages.zip` and `finfluencer_windows_test_fix.zip` at repo root read as one-off transfer or recovery artifacts from past sessions. Recommend confirming they're no longer needed and removing them — flagged here as a recommendation requiring the user's own review and explicit deletion approval, not something this document or any automated process should remove unilaterally.

## 25. Executive Recommendations

Three recommendations, stated directly.

**Execute what's already approved before designing anything new.** Every item in Section 22's "Now" tier is already fully specified by work this project has already done — the migration closeout's own open items, plus small, low-risk hygiene fixes (CI, lockfile, entry point). None of it needs this document's permission; it needs execution.

**Treat Phase A (Section 22, mid-term) as the next real piece of platform work, and Phase B's success criterion as a hard gate, not a formality.** The single biggest risk this document identifies (Section 23) is building REST, GUI, or multi-tenancy infrastructure before a second real study has told you whether the tenancy model is actually general — `CCR_OS_Architecture_v3.md` already reasoned through why that ordering matters; this document's only addition is confirming, after its own independent repo audit, that nothing has changed to make skipping that gate safer now than it was when that reasoning was first written.

**Let this document close the architecture-exploration phase, not extend it.** Three substantial target-architecture documents already existed before this one was requested. That pattern — each new document adding another speculative layer on top of the last — is itself a risk this platform has direct, recent, first-hand experience with in a different but structurally identical form (the governance-framework exploration earlier in this project's history, deliberately closed by explicit instruction rather than left to accumulate further). This document's intended role is to be the *consolidation* of that pattern, not its next installment: one indexed, evidence-grounded reference, built from what already exists, with a roadmap whose every item is gated behind a concrete precondition rather than an aspiration. The next architecture document this platform needs, if any, should be written after Phase B's real second study exists — not before.
