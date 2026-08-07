# Computational Communication Research Operating System (CCR-OS)
### Target Architecture — v3.0/v4.0 Horizon

**Prepared by:** Lead Software Architect, Finfluencer Research Platform
**Scope:** A design exercise, not an implementation. No code. Extends the Entity-Centric Migration Plan (v2.0) just delivered into a multi-tenant platform capable of hosting hundreds of independent computational-communication-research studies, of which the finfluencer study becomes one instance rather than the platform's identity.

---

## 0. Framing: What "Operating System" Means Here, and What It Doesn't

The v2.0 plan fixed one platform's data model. This document asks a different question: what has to be true architecturally for the *same codebase* to host a sentiment study on Turkish finance YouTube, a discourse-network study on climate-policy Twitter, a multimodal study on TikTok health misinformation, and a survey-plus-content-analysis mixed-methods study — simultaneously, without each new study requiring bespoke engineering.

"Operating system" is used deliberately, not decoratively, because the underlying engineering problem is structurally the same one general-purpose operating systems solve: many independent workloads (studies) need to share finite, expensive resources (API quota, compute, storage, researcher time) safely, without one workload corrupting or exhausting another's, while each workload gets to behave, mostly, as if it owns the machine.

**Explicit non-goals**, stated up front because "an OS for a field" is the kind of brief that invites scope collapse into building everything:

- This is not a general-purpose data warehouse or BI platform. It does not compete with Postgres, Snowflake, or a generic ELT tool. It is scoped to the specific, recurring shape of computational communication research: collect artifacts from sources, derive features and labels from them, model relationships between message and messenger properties and downstream outcomes, and produce citable, reproducible statistical output.
- This is not a no-code research tool for non-programmers. Studies are still configured and extended by researchers who can write Python and YAML. A GUI layer (Section 9) is a convenience on top of that, not a replacement for it.
- This is not a hosted SaaS product with billing, multi-organization tenancy, or a business model. "Hundreds of projects" is read here as hundreds of research projects within one lab or institution's infrastructure, not hundreds of paying external customers. If the latter is actually intended, that is a different document — an infrastructure and legal one, not primarily an architecture one — and should be scoped separately before any of what follows is built.
- This does not attempt to solve model training. It orchestrates and versions the *use* of models (embedding, sentiment, topic, LLM-based coding) via providers; it is not an MLOps platform for training new models from scratch.

## 1. Design Principles

Four principles, each chosen because its absence caused a real, documented problem identified in this project's own engineering review or migration plan.

1. **A study is a tenant, not a config file.** The single biggest structural change from v2.0 to CCR-OS is this one. `EntityRecord.study_id` already exists in `core/contracts.py` as of Phase 0 — it is currently an unused column, populated but never read. CCR-OS promotes it to the platform's primary isolation boundary. Everything else in this document follows from taking that field seriously.
2. **Resolve once, persist, never re-derive — at every layer, not just topics.** Phase 3 of the v2.0 plan fixed this for comment-scope fingerprinting specifically (`AnalysisScope`). CCR-OS generalizes the same discipline to study configuration, method versioning, and provider selection: anything a second process might independently recompute and disagree about must instead be resolved once and referenced by ID.
3. **Providers, resolvers, and methods are plugins; studies are not.** The registry pattern (`core/registry.py`, `(kind, key) -> class`) already correctly treats platforms, languages, and market data sources as swappable. CCR-OS extends the same pattern to analysis methods and membership resolvers (both already partly planned in v2.0 Phase 4) — but a *study* itself is never a plugin. It is the unit the OS schedules, isolates, and meters resource consumption against.
4. **Generality is earned by the second and third studies, not designed in advance for the hundredth.** The engineering review's central finding — a "shadow analysis pipeline" of roughly fifteen unpackaged scripts actually producing the submitted manuscript — happened because real analytical needs outran the platform's abstractions and the researcher reasonably worked around them rather than waiting for a general solution. CCR-OS's migration path (Section 12) is deliberately sequenced so that generality is validated against a second real study before a tenth is assumed possible.

## 2. The OS Analogy — Layer Map

| OS Concept | CCR-OS Concept | Status |
|---|---|---|
| Kernel / core services | Entity model, storage abstraction, provenance, checkpoint/cache, ethics enforcement | Mostly exists (v1.0/v2.0); needs multi-tenant awareness |
| Device drivers | Data source, model, and analysis-method providers | Exists for platform/language/market; needs a fourth provider kind for analysis methods |
| Processes | Studies | `study_id` field exists, unused; needs full lifecycle, isolation, and quota semantics |
| Package manager | Method registry (sentiment, topic, network, causal, discourse) | Registry mechanism exists (`core/registry.py`); method-as-versioned-package is new |
| Scheduler | Multi-tenant job orchestration and fair-share compute budgeting | `core/budgets.py` exists per-run; no cross-study fairness exists |
| Filesystem | Canonical entity/artifact storage, content-addressed cache | Exists (Phase 0 canonical tables, Tier 3 cache); needs per-study partitioning strategy |
| System calls / API | Python API, planned REST API | CLI exists; REST API planned in `service_oriented_multiplatform_architecture.md`, not yet built |
| Shell / GUI | CLI, Researcher Portal, dashboard | CLI exists (once the broken entry point is fixed); Portal and dashboard are new |
| User accounts and permissions | Researcher accounts, role-based access, data-sensitivity tiers | Does not exist — v1.0 is single-researcher |
| Init system / boot | Study bootstrapping ("new study" scaffolding) | Does not exist — every study today is a manual clone-and-edit of the finfluencer config |
| Audit log | Ethics, consent, and access audit trail | `EthicsConfig.retention_days` exists as a single field; no audit trail exists |
| Package registry / app store | Cross-institution method or provider sharing | Does not exist; out of scope for v3.0, noted as a possible v4.0 direction only |

This table is the spine of the rest of the document: each numbered section below expands one row.

---

## 3. Layer 1 — Kernel: Core Services

The kernel is what every study depends on and no study should reimplement. Five services, three already real:

**Entity and study model (extends existing).** `EntityRecord`, `EntityVideoLinkRecord`, and the v2.0 `AnalysisScope` remain unchanged in shape. What's added is a `Study` record sitting one level above `EntityRecord`: `study_id`, `title`, `pi_researcher`, `created_at`, `status` (`draft`, `active`, `archived`), `data_sensitivity_tier`, `resource_quota_ref`, `ethics_approval_ref`. Every `EntityRecord`, every `AnalysisScope`, every checkpoint, and every cache entry carries a `study_id`. This is additive to the v2.0 schema, not a rewrite of it — v2.0's plan already put `study_id` on `EntityRecord`; this layer is what finally reads it.

**Storage abstraction (extends existing).** v2.0 deliberately kept the platform parquet-file-based and deferred a database engine as a v3.0/v4.0-tier decision (per the migration plan's own Section 3). That deferred decision arrives here: at "hundreds of studies" scale, a per-study-partitioned parquet layout on a shared filesystem or object store (S3-compatible) becomes the pragmatic answer, not a relational database. Each study gets its own prefix (`studies/{study_id}/...`); cross-study reads (Section 10) go through the storage abstraction rather than direct file access, so a partitioning-scheme change later doesn't require rewriting every study's analysis code. This is a filesystem-layout decision, explicitly not a "migrate to Postgres" decision — that remains out of scope, per the same reasoning the v2.0 plan already gave.

**Provenance and reproducibility (extends existing).** The existing reproducibility manifest concept generalizes from "one manuscript's inputs" to "one study's full lineage": every `AnalysisScope`, every method-package version (Section 6), every provider version used, timestamped and content-hashed, retrievable by `study_id` months or years later. This is what makes "hundreds of projects" a research-integrity asset rather than a liability — a platform where every study's exact analytical lineage is queryable is a stronger publication and replication story than any single manuscript's own reproducibility statement.

**Checkpoint and cache (extends existing).** `CheckpointManager`'s three tiers are already confirmed entity-agnostic at the primitive level (v2.0 plan, Section 8: "None — already entity-agnostic"). The only change needed here is namespacing cache keys by `study_id` at the tier-2/tier-3 boundary where two different studies might otherwise collide on an identical config-slice hash for unrelated reasons (e.g., two studies both choosing the same sentiment model with the same batch size). Tier 3's content-addressed cache should, deliberately, remain global rather than per-study — if two studies embed the same YouTube comment text with the same model, they should share that cache entry. Sharing compute-expensive derived artifacts across studies where the underlying content is identical is one of the concrete efficiency gains "hundreds of projects" makes newly worth engineering for; at four studies it would not be worth the complexity.

**Ethics and governance enforcement (new, not merely extended).** Today `EthicsConfig.retention_days` is a single unenforced field. At kernel level this becomes an active gate: a study cannot transition from `draft` to `active` without a non-null `ethics_approval_ref`; scheduled jobs (Section 8) check `retention_days` against `resolved_at` timestamps and flag or block continued processing of data past its retention window; a `data_sensitivity_tier` on each study (`public`, `pseudonymized`, `identifiable`) gates which storage backends and which researcher roles (Section 9) can read it. This is the one genuinely new kernel service — everything else above is an existing service learning to be `study_id`-aware.

## 4. Layer 2 — Drivers: The Provider Ecosystem, Generalized

v1.0 already has three provider kinds, correctly built on the registry pattern: platform (YouTube today), language, and market. Two changes generalize this into a full driver layer:

**A fourth provider kind: analysis method.** Sentiment classification, topic modeling, embedding generation, and (new, see Section 6) network analysis, causal inference, and discourse-analytic coding all become `AnalysisMethodProvider` implementations registered under `(kind="analysis_method", key=...)`. Today these live as pipeline-specific code (`sentiment/pipeline.py`, `topics/pipeline.py`) that happens to call a swappable model underneath; CCR-OS inverts that so the pipeline orchestration is generic and the method itself is the plugin. This is the same shape of change v2.0's Phase 4 already planned for membership resolvers, applied one layer up.

**A fifth provider kind: data source, generalized beyond "platform."** YouTube is one instance of a broader `DataSourceProvider` interface that a survey-import provider, a Reddit provider, a news-archive provider, or a researcher's own CSV-upload provider can all implement. The interface contract is: given source-specific config, produce `CanonicalVideoRecord`/`CanonicalCommentRecord`-shaped output (or their generalization, Section 11) plus an `EntityVideoLinkRecord`-equivalent membership record. Nothing about YouTube-specific logic (quota tracking, transcript fetching) belongs at this interface level; it stays inside the YouTube provider implementation, exactly as it does today.

**Driver installation model.** v1.0's registry already supports both in-tree decorator registration and out-of-tree Python entry-points (confirmed in the engineering review as implemented and reusable). CCR-OS's only addition here is a manifest convention — a small `provider.yaml` alongside any new provider package stating its kind, key, required config schema, and a semantic version — so that a study's reproducibility manifest (Section 3) can record not just "used the YouTube provider" but "used youtube-provider v1.3.0," the same discipline software package managers already require and computational research has historically lacked.

## 5. Layer 3 — Processes: The Study as a First-Class Unit

This is the layer where "hundreds of projects" is actually won or lost.

**Lifecycle.** `draft` (config being written, no jobs run) to `active` (collection/processing/analysis jobs may run, gated on ethics approval per Section 3) to `archived` (data retained per policy, no new jobs, still queryable for replication). A study's `status` transition is the one place governance (Section 10) and orchestration (Section 8) meet: nothing schedules a job for a study not in `active` status.

**Isolation with deliberate, narrow sharing.** Each study owns its `EntityRecord`/`AnalysisScope`/checkpoint namespace outright — one study's bug or misconfiguration cannot corrupt another's results. But two specific things are shared by design, not accident: the Tier 3 content-addressed cache (Section 3, for identical derived artifacts), and — the more interesting case — raw collected data itself, when two studies' data sources genuinely overlap (e.g., a second study also analyzing a subset of the same YouTube channels the finfluencer study already collected). This second kind of sharing requires the `EntityVideoLinkRecord` bridge-table pattern v2.0 already built for exactly this purpose within one study, extended so a `video_id` collected once can be linked into multiple studies' entity graphs without re-fetching or duplicating storage. This is the direct, natural extension of the "one video, one row" fix v2.0 made for one study's four analysts, now applied across study boundaries.

**Resource quotas.** `core/budgets.py` already exists as a per-run compute/API budgeting mechanism. At process level it becomes per-study: a `resource_quota_ref` on the `Study` record caps API calls, GPU-hours, and storage for that study, enforced by the scheduler (Section 8) rather than trusted to researcher discipline — the same reason operating systems enforce process memory limits instead of trusting programs to behave.

**Study templates.** The single highest-leverage new capability for actually reaching "hundreds" rather than staying at a handful: a small number of named templates (`single-platform-sentiment`, `cross-platform-comparison`, `survey-plus-content-analysis`, `network-diffusion`) that scaffold a new study's `entities.yaml`, provider selection, and default `AnalysisScope` configuration in one command, analogous to a web framework's `startproject`. Templates are themselves versioned artifacts, not one-off scripts — a template improvement should be able to benefit studies created from it going forward without silently rewriting studies already using an older template version.

---

## 6. Layer 4 — Package Manager: Methods as Versioned, Citable Packages

Computational communication research's actual replication crisis is rarely "the code was wrong" — it is "the code that produced Table 3 no longer exists in a runnable form six months later," which is precisely the failure mode the engineering review's "shadow analysis pipeline" finding already documented concretely for this project's own manuscript. The package-manager layer exists to make that failure structurally harder, not just to add a fifth provider kind for its own sake.

**What a method package is.** A versioned, registry-registered implementation of one analytical step (a sentiment classifier, a topic-modeling configuration, a mixed-effects specification, a Granger-causality test, a discourse-analytic LLM-coding prompt-and-rubric pair) that declares its inputs, outputs, and dependencies explicitly, and whose exact version is recorded in a study's reproducibility manifest (Section 3) every time it runs. This is the `AnalysisMethodProvider` from Section 4, viewed from the packaging angle rather than the driver angle — same object, different concern.

**Why this is a package *manager* and not just a registry.** The existing `core/registry.py` already solves "look up a class by (kind, key)." What it does not yet solve, and what hundreds of studies genuinely require, is: which version of a method did study 47 use eighteen months ago, can that exact version still be installed today, and what does it mean when a method package's second version changes its output schema. These are dependency-resolution and version-compatibility questions, not lookup questions — the same category CRAN, PyPI, and npm exist to answer for general software, applied here to research methods specifically.

**Deliberately not building.** A public, cross-institution package index (an "app store" for research methods) is explicitly out of scope for v3.0, listed as a possible v4.0 direction only in the layer map above. At the "one lab, hundreds of studies" scale this document targets, an internal, git-backed method registry is sufficient and dramatically lower-risk than building public distribution infrastructure prematurely.

## 7. Layer 5 — Scheduler: Multi-Tenant Orchestration

`core/budgets.py` already tracks compute and API budgets within a single run. What's missing for concurrent studies is fairness across runs.

**Job queue, not synchronous CLI execution.** v1.0's `run_pipeline()` runs synchronously in the researcher's own process. At multi-study scale, collection and processing jobs are submitted to a queue and executed by workers that can be scaled independently of any one researcher's laptop or terminal session — the same shift any single-user script makes when it needs to become a shared service.

**Fair-share scheduling.** When two studies' jobs compete for the same finite resource (most concretely, a shared YouTube API quota, which is a single account-level budget regardless of how many studies want to use it), the scheduler enforces each study's `resource_quota_ref` (Section 5) rather than first-come-first-served exhaustion, which is the failure mode that would otherwise make one large collection job for study A silently starve study B for the rest of the day.

**Provider-level rate limiting stays provider-level.** This is a scoping note, not a new component: YouTube quota tracking (`collect/quota.py`, confirmed in the engineering review as already API-call-count-based, not analyst-partitioned) does not move into the scheduler. The scheduler enforces per-study fairness *within* whatever ceiling the provider itself already reports; it does not duplicate the provider's own rate-limit bookkeeping.

## 8. Layer 6 — Interfaces: CLI, API, Portal

**CLI (extends existing, fixes a known defect first).** The engineering review already flagged the broken `pyproject.toml` entry point (`finfluencer.cli:app` pointing at a file that doesn't exist) as an immediate, low-cost fix. That fix is a prerequisite here too, since CCR-OS's CLI grows new study-scoped subcommands (`finfluencer study create`, `finfluencer study list`, `finfluencer study archive`) that should not be built on top of a packaging entry point that doesn't currently work.

**REST API (planned, not yet built).** `service_oriented_multiplatform_architecture.md` already documents this as a planned layer. CCR-OS's specific requirement of it: every endpoint is scoped by `study_id` and enforces the access-control tiers from Section 9, so the API is where the storage-layer isolation described in Section 5 is actually enforced for any client that isn't the researcher's own trusted CLI session.

**Researcher Portal (new).** A thin web layer over the REST API, whose only job is making the two highest-friction manual steps of running a study — creating one from a template (Section 5) and monitoring job/quota status (Section 7) — self-service, so that a new study does not require the platform's original author personally setting it up. This is explicitly scoped as thin: the Portal is a convenience layer over the API and CLI, not a parallel implementation of study logic.

## 9. Layer 7 — Governance: Ethics, Access, Audit

**Access-control tiers.** Three roles, deliberately few: `study_owner` (full read/write on their own studies, per Section 5's quota limits), `contributor` (read/write on specific studies they're added to, e.g. a research assistant or co-author), `institution_admin` (read-only visibility across all studies for compliance and resource-planning purposes, write access only to quota and ethics-approval fields). This is not a general-purpose RBAC system; it is the minimum role set the kernel's ethics gate (Section 3) actually needs to be meaningful.

**Consent and data-sharing agreements as data, not policy documents.** Where a study's data source has source-specific terms (a platform's terms of service, a survey's IRB-approved consent language, a data-sharing agreement with another institution), those terms are attached to the `Study` record as structured metadata the kernel can check programmatically before allowing cross-study sharing (Section 5) — e.g., a study whose data-sharing agreement forbids reuse cannot be selected as a source when another study's `EntityVideoLinkRecord` bridge would otherwise let it borrow already-collected data.

**Audit trail (new).** Every access to identifiable-tier data (Section 3's `data_sensitivity_tier`), every study status transition, and every cross-study data-sharing event is appended to an audit log keyed by `study_id` and actor. This did not exist at all in v1.0 and is one of the few genuinely new components in this entire document rather than an extension of something that already exists — it is also the component an institutional review board or ethics committee is most likely to actually ask for once the platform hosts studies beyond its original author's own.

---

## 10. Layer 8 — Knowledge Layer: The Research Catalog

This is the layer that turns "hundreds of studies running on shared infrastructure" into "hundreds of studies that make each other more valuable," and the layer most tempting to over-build before the studies exist to populate it. Kept deliberately narrow:

**A searchable catalog, not an automated meta-analysis engine.** For each `active` or `archived` study: title, data sources used, methods used (with versions, per Section 6), entity/scope summary statistics, and — where the study has published output — a citation. Queryable across studies ("which studies used the youtube-provider v1.x line," "which studies analyzed messenger-credibility effects"). This is achievable by making Section 3's provenance records queryable, not by building new analytical infrastructure.

**Cross-study benchmark tracking, deferred.** A shared benchmark set (e.g., a labeled Turkish financial-sentiment validation set already built for the finfluencer study) that future studies using the same language/domain could evaluate new methods against is a genuinely valuable v4.0 idea, flagged here and explicitly not designed further — it depends on enough studies existing in the same domain to make a shared benchmark meaningful, which is not true yet at study count one.

## 11. The Generalized Data Model

The single conceptual change every layer above depends on: `CanonicalVideoRecord`/`CanonicalCommentRecord` are YouTube-shaped by name and by field. A survey-based study or a Reddit-thread study cannot honestly be forced into a schema called `CanonicalCommentRecord`.

**Proposed generalization, additive to v2.0's schema, not a replacement of it:**

- `Artifact` — the generalization of `CanonicalVideoRecord`: any top-level unit of content a study collects (a video, a news article, a survey wave, a forum thread). Platform-specific fields (view count, like count) move into a `platform_metadata: dict` extension field, exactly as the v2.0 plan already isolates volatile YouTube-specific metrics (`_VOLATILE_VIDEO_METRICS`) rather than baking them into the schema's required fields.
- `Interaction` — the generalization of `CanonicalCommentRecord`: any response, reply, or coded unit attached to an `Artifact` (a comment, a survey response, a coded utterance). Comment-specific fields (reply-to structure) similarly move into an extension field.
- `Actor` — a new, explicit generalization of "who produced this," currently implicit and YouTube-specific (a channel/analyst). An `Actor` can be a YouTube channel, a survey respondent, a news outlet, or an anonymized participant ID, with the same `EntityRecord`/`EntityVideoLinkRecord` membership-resolution machinery from v2.0 applying identically regardless of what kind of actor is being grouped into an entity.

**Why this is additive, not a rewrite, and why that matters given the project's own history.** `AnalystRecord`, `VideoRecord`, `CommentRecord` are still in `core/contracts.py`'s `__all__` today, deprecated-but-present behind the v2.0 compatibility view. This document proposes the same discipline one more time: `Artifact`/`Interaction`/`Actor` arrive alongside `CanonicalVideoRecord`/`CanonicalCommentRecord`, not instead of them, with YouTube-specific code able to keep using the more specific, already-working schema indefinitely if a generalized one buys it nothing. Generalization is offered to the *second* study, not imposed retroactively on the first.

## 12. Migration Path from v2.0 to CCR-OS

Four phases, sequenced so the platform is never left half-migrated with no working state, and so nothing here starts before the v2.0 migration plan's own Phase 3 validation (old vs. new comment-ID sets identical) has passed — CCR-OS is built on a corrected fingerprinting layer, not a still-buggy one.

**Phase A — Multi-tenancy without multiple tenants.** Add the `Study` record and `study_id`-namespacing to checkpoints and storage (Section 3), and complete the v2.0 migration plan's own Phases 1 to 5 under a single, real `study_id` for the finfluencer study itself. Nothing about this phase requires a second study to exist yet; it requires the *first* study to be correctly modeled as a tenant of one. This phase is where the risk of "multi-tenant design that's never been exercised by a second tenant" is lowest, because it can be fully validated against a study whose expected behavior is already known.

**Phase B — Second study, real not synthetic.** Onboard one genuinely new, different study (ideally a different platform or a different entity type than `creator`, to stress-test the parts of v2.0 Phase 4 and Section 4's driver generalization that no amount of single-study design review can validate) using a study template (Section 5) built during this phase. The explicit success criterion: the second study's onboarding required zero changes to kernel or driver code, only new provider/resolver implementations and a new `entities.yaml`. If it requires kernel changes, that is signal the "OS" layer isn't actually general yet, and Phase C should wait.

**Phase C — Scheduler, governance, and portal.** Only once Phase B's success criterion is met: build the job queue and fair-share scheduler (Section 7), the access-control and audit layers (Section 9), and the Researcher Portal (Section 8). This phase is what actually enables "hundreds," but it is infrastructure investment that is wasted if Phase B reveals the tenancy model itself needs rework first.

**Phase D — Knowledge layer and template library expansion.** Build the research catalog (Section 10) once enough studies exist for it to return non-trivial results, and expand the study-template library based on what Phase B and early Phase C studies actually needed rather than anticipated needs.

## 13. Risks at This Scale

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Multi-tenant isolation bug lets one study's job exhaust another's quota or corrupt its checkpoint namespace | Medium | High | Phase A validates isolation against a single known study before Phase B introduces a second, genuinely independent one; quota enforcement (Section 7) is scheduler-level, not trusted to study code |
| Generalized `Artifact`/`Interaction` schema (Section 11) is designed from one platform's shape and turns out wrong for the second study anyway | Medium | Medium | Explicitly deferred: Section 11's schema is proposed but not finalized until Phase B's real second study exists to validate it against, per the same "don't design for the hundredth study in advance" principle from Section 1 |
| Governance/audit layer (Section 9) is built to satisfy an assumed institutional requirement that turns out not to match the actual IRB or data-sharing rules the lab operates under | Medium | Medium-High | Section 9 should be reviewed against the institution's actual ethics-board and data-governance requirements before Phase C, not designed from generic best practice alone — this document flags the need, it does not substitute for that review |
| Single-developer project (per the engineering review, two git commits recorded to date) attempting infrastructure of this scope | High | High | This is the largest risk in the entire document and is addressed directly in Section 14, not mitigated architecturally — no amount of good layering fixes a staffing mismatch |
| Scope creep: the knowledge layer (Section 10) and public package registry (noted as v4.0-only in Section 6) are the most conceptually interesting parts of this document and the easiest to over-invest in before Phases A-B are solid | Medium | Medium | Same sequencing discipline the v2.0 plan already applied to its own Phase 4: no work on Sections 10 or the v4.0 package-index idea starts before Phase B's success criterion is met |
| Shared Tier-3 cache (Section 3) becomes a cross-study information leak — study B can infer study A's exact input text from a shared cache key even if it can't read study A's results directly | Low-Medium | Medium | Cache keys should hash content, not reveal it; a `data_sensitivity_tier` of `identifiable` (Section 9) should opt a study's derived artifacts out of the shared cache entirely, accepting the redundant-compute cost as the price of that tier's isolation guarantee |

---

## 14. Feasibility Assessment: The Question This Document Cannot Design Around

Every prior deliverable in this project's review has been an architecture question. This one is not purely that, and honesty requires saying so directly rather than answering only the question asked.

The engineering review already established, from the actual git history, that this is a single-developer project with two recorded commits and 48.6% test coverage concentrated away from its most-changed modules. The entity-centric migration plan already required, on its own, careful multi-phase sequencing to execute safely. This document adds: a `Study` tenancy model, a fourth and fifth provider kind, a method package manager, a job scheduler, a role-based access and audit system, a researcher portal, and a cross-study knowledge catalog — on top of a codebase whose original author is, currently, this document's only reader.

None of the individual layers above is architecturally exotic; each is a well-understood pattern (multi-tenancy, plugin registries, job queues, RBAC) applied to a domain that happens not to have a mature off-the-shelf platform for it yet. The risk this document cannot design away is not technical, it is organizational: "hundreds of research projects" implies hundreds of researchers, which implies a team maintaining this platform, a documented onboarding process, and — per Section 9 — an actual answer from the institution's ethics/compliance function about what governance it requires, not just this document's best guess. Phase A and Phase B (Section 12) are scoped to be buildable by the platform's current author alone, on the current codebase, without waiting for that organizational question to be answered. Phases C and D are not, and should not be started on the assumption that "the architecture is designed, so the org will follow" — that assumption is exactly the kind of unverified premise this review process has been built to catch at every other stage.

## 15. Final Recommendation

Build Phase A now, as a direct continuation of the v2.0 entity-centric migration already planned — it is low-risk, immediately useful even at study count one, and the correct foundation regardless of whether "hundreds of studies" ultimately materializes. Treat Phase B as the platform's actual validation gate: do not plan Phase C's scheduler, governance, or portal investment in detail until a second, real, different study has been onboarded and the zero-kernel-change success criterion in Section 12 has either been met or has told you specifically what Phase A got wrong. And before Phase C, get a real answer — not an architectural assumption — to who besides the current author will operate, maintain, and govern this platform once it is no longer one researcher's tool for one paper.
