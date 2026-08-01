# Implementation Roadmap — Computational Communication Research Platform

**Status:** Permanent repository document. Execution sequencing only.
**Relationship to other documents:** This document assumes `docs/product/PRODUCT_ARCHITECTURE.md` is frozen and does not restate, redesign, or reinterpret any decision made there — every architectural claim below is a cross-reference (§N), not a repetition. It precedes `IMPLEMENTATION_PLAYBOOK.md` (not yet written), which will define *how* day-to-day work is performed; this document defines *what gets built, in what order, and why*.
**Method:** Section 3's reuse assessment is based on direct inspection of the repository at `src/finfluencer/` on 2026-08-01 — file paths, line counts, and docstrings cited are read from the actual codebase, not inferred from prior summaries. Where a claim could not be verified (noted explicitly), it is flagged rather than assumed.

---

## 0. Purpose and Reading Guide

This roadmap is the execution bridge between a frozen product architecture and the first line of implementation code. It answers one question per section: what exists already and how reusable is it (§3), what has to happen before what and why (§4), what gets built in which phase (§5), what "done" means at each stage of product maturity (§6), where the real risk is (§7), how work gets validated (§8), what can run in parallel (§9), what stays deliberately unresolved (§10), and what happens after 1.0 (§11). §12 is a permanent, self-critical review of this document, written by the same hand that wrote it — treat it as load-bearing, not decorative.

## 1. Implementation Philosophy

Architecture-Validated Development, not Architecture-Driven Design: the architecture (§1–§17 of PRODUCT_ARCHITECTURE.md) is frozen and trusted, but *how well it holds up in practice* is proven by building one real, deployed, end-to-end slice before committing to the full build — not by writing more documents about it. A single architect working with AI agents (Claude Code, ChatGPT, Copilot, and successors) is the assumed operating model throughout; nothing in this roadmap presumes a multi-person team with role-differentiated ownership. Reuse is the default posture toward the existing `finfluencer` engine, not an afterthought — the burden of proof is on rewriting, not on wrapping.

## 2. Implementation Principles

Contract-first: Domain Model and API Contract exist as code and schema before dependent modules are built, per the prior implementation-planning rounds. Reuse-first: every module below states explicitly what already exists and how it's reused before any new-build estimate is made. Thin-foundation: only artifacts with a direct implementation payoff exist before code, per the same prior rounds — this document does not reopen that decision. Just-in-time detail: per-module integration decisions, failure-handling specifics, and technical debt are recorded at the point of contact with the code (in that module's AI Context Pack), never speculated in advance. Evidence over assumption: every reuse classification in §3 below is grounded in an actual file this document's author read, not a description of what the file probably contains.

## 3. Existing Codebase Inventory and Reuse Assessment

This is the section that should most directly change how implementation is sequenced — it did, in the process of writing it. Four classifications are used, consistently: **Production ready** (usable as-is, only a wrapper needed at the boundary), **Wrapper required** (the logic is sound and tested; it needs an Application-layer contract wrapped around it to be reachable via the API rather than a CLI invocation), **Adaptation required** (the logic is sound but its current shape needs real, deliberate change before it fits the target architecture), **Complete build required** (no prior code exists).

| Architecture module (§4/§8) | Existing code | Classification | Why |
|---|---|---|---|
| Reproducibility & Experiment Tracking (§8.3) | `core/checkpoint.py` (247 lines, three-tier: per-record JSONL, per-stage `.done` manifest, content-addressed cache), `core/reproducibility.py` (344 lines), `core/contracts.py` (812 lines of strict Pydantic schemas, `extra="forbid"`) | **Production ready, with one flagged risk** | This is the platform's differentiator (§1.2) and it is genuinely mature — but `checkpoint.py`'s own docstring states it assumes a single writer per `checkpoint_root` and that concurrent runs against the same directory "can race." §16.9/§16.21's target Worker Tier is horizontally scaled. See Risk R-1 (§7). |
| Collection Engine (§8.1) | `collect/` — `main.py` (561 lines), `channels.py`, `comments.py`, `quota.py`, `transcripts.py`, `videos.py`; `providers/platform/youtube.py` (459 lines) + `base.py` | **Wrapper required** | Real, tested pagination/quota/transcript/dedup logic, exercised by 68 existing test files and hardened through prior governance work on this exact area (R1/R2/R7/R8). It runs today as CLI-invoked batch scripts. It needs an Application-layer orchestrator implementing `StartCollectionRun`/`GetCollectionRunStatus` (§11.2) around the existing Infrastructure logic — not a rewrite of the logic itself. |
| Analysis Engine — topic modeling and sentiment (§8.2) | `topics/` (`bertopic_runner.py`, `pipeline.py`), `sentiment/` (`base.py`, `pipeline.py`, `transformer_classifier.py`), `embeddings/` (`base.py`, `pipeline.py`, `sentence_transformer.py`) | **Wrapper required** | Same pattern as Collection: working ML pipelines that need a `StartAnalysisRun` orchestrator wrapped around them, plugged in behind the `AnalysisType` mechanism (§5, §10.1) rather than invoked as a script. |
| Analysis Engine — preprocessing (§8.2) | `preprocess/` (`base.py`, `financial_tr.py`, `pipeline.py`) | **Adaptation required** | `financial_tr.py` is explicitly Turkish-financial-vocabulary-specific — the concrete, real instance of the vertical-coupling problem §5 designed the Vertical Template mechanism to solve. It needs to move behind that plugin boundary deliberately, not be carried forward hardcoded into the core pipeline. |
| Analysis Engine — market correlation AnalysisType | `market/` (`collect_market_data.py`, `confirmatory_analysis.py`, `figures.py`, `sentiment_index.py`, `ingest_manual_bist100.py`), `providers/market/` (`tcmb_evds_provider.py`, `yfinance_provider.py`) | **Wrapper required, deliberately deferred** | Real, working code — but §3.3 of the architecture already scoped market correlation as optional, not core. Wrapping it is Phase 3 work (§5), not Phase 1, on the architecture's own authority, not a new call made here. |
| Internationalization groundwork (§17.18) | `providers/language/` (`base.py`, `english.py`, `turkish.py`) | **Production ready** | Not previously known to be this concrete: a working English/Turkish provider abstraction already exists. This meaningfully de-risks §17.18's claim that internationalization needs no new architectural layer — there is now direct evidence, not just an architectural argument. |
| Reporting & Publication Engine (§8.4) | `reporting/` — `orchestrator.py` (631 lines), `job.py`, `manuscript_data.py`, `manuscript_figures.py`, `manuscript_tables.py`, `master_table.py`, `inferential.py`, `replication.py` | **Adaptation required** | There is already a real, substantial orchestrator pattern here — worth using as the internal precedent for how Application-layer orchestrators should look elsewhere in this codebase, not just an external DDD concept. But its current output is manuscript tables/figures for academic publication, not the in-product PDF/Word `Report` rendering §8.4 scopes as new. Data-generation logic is reusable; export rendering is genuinely new work. |
| Existing scope/entity concept | `scope.py` (225 lines), plus `ADR-0001_TopicEvolutionRecord_ScopeId_Deferral.md` and `AnalysisScope_Impact_Analysis.md` at repo root | **Adaptation required — flagged, not resolved** | The existing codebase already has a real `AnalysisScope` concept with its own prior ADR history. Whether this maps cleanly onto `Dataset`/`AnalysisRun` (§10.1) or requires deliberate reconciliation is an open question for the Domain Model Specification, not assumed to be trivial here. See Risk R-2 (§7). |
| CLI entry point (§17.10) | `cli.py`, `__main__.py` (Typer-based) | **Production ready** | Exactly the alternate Presentation-Layer client §17.10 already committed to — becomes a thin client against the API Gateway once it exists, not rewritten. |
| Migration discipline (informing §16.7's migration strategy) | `migration/` (`backfill_entity_model.py`, `backfill_topic_scope.py`), root-level `Entity_Centric_Migration_Plan_v2.md` and its closeout report | **Positive evidence, not a code asset** | The team has already executed and closed out at least one real schema migration on this codebase. That's a genuine risk reducer for the Physical Database Design's migration strategy — proof of discipline already exercised, not a promise. |
| Identity & Access, Public API, Web Application Shell, Billing & Licensing, AI Interpretation Layer, Platform Admin/Ops | — | **Complete build required** | Confirmed by direct inspection, not assumed: no `auth/`, `api/`, web framework, `billing/`, or `ai`/`llm` directory exists anywhere in the repository. This matches §4's own [New] tagging exactly — now verified rather than taken on faith. |

Two further, repo-level facts worth recording because they change real early decisions: the repository already ships under an **MIT license** (root `LICENSE` file, dated 2026) — this doesn't resolve DAD-002 (§17.7), which stays formally open, but any resolution should account for this existing precedent rather than starting from an assumed blank slate. And `pyproject.toml` already depends on `tenacity` (retry logic) and `httpx` (async HTTP) — both directly relevant to Failure Recovery's retry policy and a future AI-provider adapter, meaning those concerns aren't starting from zero library selection either.

## 4. Dependency Graph — Build Order and Why

This is a module dependency graph, not the document dependency graph from earlier planning rounds. Each edge below is a real data or security dependency, not a preference.

**Identity & Access before everything.** §10.1's `Project` is the root aggregate; every other entity (`Dataset`, `CollectionRun`, `AnalysisRun`, `InterpretationRecord`, `Report`) is Project- or Tenant-owned. Nothing else has a valid parent to attach to without it. Hard dependency.

**Collection Engine before Analysis Engine.** §10.1 explicitly pins every `AnalysisRun` to a specific `CollectionRun`. There is no analysis without something collected first. Hard dependency.

**Analysis Engine before Reporting.** A `Report` cites `InterpretationRecord` entries (§10.0), which in turn derive from `AnalysisRun` output. Hard dependency.

**Reporting does not require the AI Interpretation Layer.** This is the single most consequential sequencing fact in this document, and it comes directly from architecture already approved, not a new call: §10.0's `kind` discriminator (`raw_result_snapshot` vs. `ai_generated`) means a `Report` can cite raw analysis snapshots alone. AI-generated interpretation is additive to Reporting, not a prerequisite of it. This is what allows the entire AI Interpretation Layer to be deferred past MVP (§5, §6) without weakening the product's core value.

**Billing has a thin technical dependency and a strong product-sequencing reason to wait anyway.** Technically, Billing needs only a `Tenant` to exist (§11.2) — it could be built early. It should not be: there is nothing to bill for until Collection, Analysis, and Reporting produce something a user would pay for. Building billing infrastructure before there's proven value is pure waste, independent of any technical constraint.

**Public API "hardening" is mostly a policy flip, not new engineering.** §4.1 already established that the internal API and the future Public API are the same surface, documented and access-controlled differently. Once Identity, Collection, Analysis, and Reporting exist behind it, exposing that surface externally is substantially smaller work than its own line item in the original ten-document proposal implied.

**Platform Admin/Ops has a soft dependency on everything else existing at full scope, but needs a sliver from day one.** There is nothing to administer at scale until other modules exist — but Sprint 0 already needs *a* tenant and *a* user to exist for the Walking Skeleton, and provisioning that minimal path is a genuine, small slice of Admin/Ops pulled forward, not deferred with the rest of it.

**Never build before the prerequisite exists:** AI Interpretation before Analysis Engine (nothing to interpret); Billing before a Tenant exists to bill; Public API external exposure before Identity's tenant-isolation posture is solid — exposing an API before its access control is trustworthy is a security risk, not a scheduling nicety; Report PDF/Word rendering before at least one `AnalysisType`'s output shape is stable — rendering a shape that's still changing is wasted work.

## 5. Execution Phases

**Phase 0 — Foundation and Walking Skeleton.** Sprint 0's seven artifacts, then Milestone 1: create a Project, run a Collection against a canned fixture dataset, prove interruption and checkpoint resume end to end — fully specified in the prior implementation-planning round, not repeated here. Exit maturity: internal proof of concept, not yet MVP.

**Phase 1 — Core Research Loop.** Widen Collection from fixture to live YouTube using the existing, tested `collect/` and `youtube.py` code as wrapped Infrastructure adapters. Build the topic-modeling and sentiment `AnalysisType` wrappers. Build minimal Reporting: raw-snapshot citations only, in-app table/figure viewing, basic export — deliberately still AI-free, per §4's dependency finding above. Widen Identity past the single dev-user to real registration, single-tenant, Owner/Member roles only (§6's own MVP-first framing). Exit criteria: MVP Definition (§6).

**Phase 2 — Interpretation and Collaboration.** AI Interpretation Layer, single-shot scope (§8.5, §15) — deliberately not before this phase. Reporting gains AI-generated citations alongside raw snapshots. Identity gains invitations, multi-member Projects, the fuller role set (§6). Design System matures across every screen built so far rather than being fully specified up front. Exit criteria: Beta Definition (§6).

**Phase 3 — Commercialization Readiness.** Billing & Licensing, Public API external hardening, the full Security Plan and Infrastructure/Operability Plan (both deferred from Phase 0 per the prior round's just-in-time discipline, triggered now by a real approaching need), Platform Admin/Ops at full scope, the market-correlation `AnalysisType` finally wrapped (deliberately last, per §3.3's own call), and Data Protection & Ethics compliance work. Exit criteria: Release Candidate, then Version 1.0 (§6).

**Phase 4 and beyond** is not re-planned here — §17.25 of the architecture already defines the v1.x → v2 → v3 evolution (institutional multi-project, horizontal platform/domain expansion, enterprise and marketplace). This roadmap ends where that table begins.

## 6. Product Maturity Ladder

**MVP** (end of Phase 1): a researcher can create a Project, collect real YouTube data, run topic and sentiment analysis, view and export results with citations to raw analysis output — no AI interpretation required for this to be a complete, honest product. **Beta** (end of Phase 2): the above plus AI-assisted interpretation, multi-member collaboration, and a matured presentation layer. **Release Candidate** (mid-Phase 3): the above plus billing, external API access, full security and infrastructure posture, and compliance work — feature-complete against v1's scope (§3.2), unproven only in production load. **Version 1.0** (end of Phase 3): Release Candidate with no open release-blocking defect, per the Definition of Done's release-blocking classes (immutable-entity violation, tenant-isolation violation).

## 7. Risk Register

**R-1 — Checkpoint concurrency assumption versus target Worker Tier.** `core/checkpoint.py` documents single-writer-per-`checkpoint_root` as a hard current constraint. §16.9/§16.21 assume horizontal Worker Tier scaling. Nothing in the architecture is contradicted — no two `CollectionRun`/`AnalysisRun` instances need to share a `checkpoint_root` — but the partitioning discipline (one root per run, never shared) must be enforced deliberately in the Collection/Analysis orchestrator wrappers, not assumed to fall out automatically. Owner: whoever wraps Collection Engine first (Phase 1).

**R-2 — `AnalysisScope` reconciliation.** The existing `scope.py` concept and its prior ADR history may not map cleanly onto `Dataset`/`AnalysisRun` (§10.1). Unresolved until the Domain Model Specification is actually written against the real file, not assumed compatible in advance.

**R-3 — Reuse confidence does not transfer automatically to the ported form.** 68 existing test files prove the current CLI-invoked behavior; they do not prove the wrapped, API-invoked, multi-tenant behavior. New integration tests at the orchestrator/API boundary are required regardless of how strong the existing unit-test coverage is.

**R-4 — AI reproducibility and cost**, carried forward from §15.8/§15.14, not new: non-deterministic provider output and opaque model versioning remain a live risk once real AI providers are integrated in Phase 2, and unmonitored cost is a plausible near-term operational surprise.

**R-5 — Tenant isolation is hard to test well**, carried forward from earlier rounds: requires deliberate adversarial test cases, not incidental coverage from ordinary feature tests.

**R-6 — Vertical coupling in `preprocess/financial_tr.py`**: concrete, present-tense evidence of the abstract DAD-001/Vertical-Template tension §5 anticipated — deferred to Phase 3 (§5's own sequencing) but not free to ignore until then, since every Phase 1/2 change to the preprocessing pipeline risks deepening the coupling if made carelessly.

## 8. Validation Gates

Phase 0's Walking Skeleton gate (interruption/resume proven or the foundation gets revised, per the prior round). Every PR, every phase, the same four-stage gate: automated tests and Conformance Baseline CI, an AI architecture-review pass, human review, Definition of Done — as specified for `IMPLEMENTATION_PLAYBOOK.md`, referenced here, not restated. Each phase's own exit criteria (§5) are the coarse-grained gate; the PR-level gate is the fine-grained one that runs continuously underneath it.

## 9. Parallelization Map

Frontend screen work can proceed against the API Contract schema as soon as a slice of it is defined, in parallel with the backend wrapper that implements it — the entire point of contract-first sequencing established two rounds ago. Design System tokens grow independently of any backend work. Within Phase 1, the topic-modeling wrapper and the sentiment wrapper are independent of each other once the Collection wrapper establishes the orchestrator pattern — two parallel tracks, not one serial one. Within Phase 3, Billing, Public API hardening, and Admin/Ops maturity have little mutual dependency and can proceed concurrently.

## 10. Deferred Decisions

Carried forward from the architecture, not reopened here: DAD-001 (branding, §1.4) and DAD-002 (licensing model, §17.7) — both remain formally open; §3's MIT-license finding is new evidence for DAD-002, not a resolution of it. AIG-002 remains an unfilled governance-ID gap, open since the API Architecture deliverable. None of these block Phase 0 or Phase 1 work.

## 11. Post-1.0 Evolution

Not re-planned here. §17.25 of the architecture already defines this ground — this roadmap's Phase 3 exit is exactly where that table's v1.x row begins.

## 12. Architect's Review

This section is a permanent, deliberately unflattering part of the document, not a closing formality.

**What's weak in this roadmap:** the phase boundaries are cleaner on paper than real ports usually are. R-2 in particular — the `AnalysisScope` reconciliation — could expand Phase 1 well past what "wrapper required" implies if the existing concept doesn't map as cleanly as hoped. Every reuse classification above is grounded in reading the actual files, which is real evidence — but it is still evidence from *static reading*, not from having actually attempted the port. Confidence should be treated as provisional until Phase 0 tests it.

**What I would redesign, given the chance to start over:** I would not build the phases in the order written above. I would attempt the Collection Engine wrapper *first* — before Identity is fully built out, using a single hardcoded placeholder tenant — because it is the highest-confidence, most-tested existing code, and the fastest way to get a real signal about whether "wrapper required" holds up under an actual attempt, rather than sequencing by strict logical dependency (Identity, then Collection) when the point of Phase 0 is to learn quickly, not to be tidy.

**Implementation risks not fully captured above:** this whole six-round planning exercise has never produced a real calendar estimate. Phase 1, done properly — live YouTube integration, real multi-tenant identity, real export — is unlikely to be a days-or-single-digit-weeks effort for one person even with AI assistance, and nothing in this document should be read as implying otherwise. The "days, not weeks" language applied specifically to Sprint 0's seven artifacts and the Walking Skeleton, not to Phase 1 as a whole.

**Hidden assumption discovered while writing this document:** that reuse is close to free. It isn't. 812 lines of existing Pydantic schemas in `core/contracts.py` are a real asset, but they are a data-contract layer, not a rich domain model with behavior and invariants in the DDD sense §10.1 calls for — reconciling the two is genuine design work, not a copy operation, and this document's "wrapper required" language should not be read as "small effort" in every case it appears.

**What I would change before writing a single line of code, if I were accountable for this project's outcome rather than its documentation:** confirm the existing test suite actually passes, today, before any porting work begins. This document cites "68 existing test files" as evidence of maturity; it does not claim those tests currently pass, because that was not verified — an attempt to run them in the environment available while writing this document failed for want of installed dependencies, not because the tests were run and failed. That gap should be closed literally before the next command runs. Trusting an unverified claim about test health would be inconsistent with the evidence discipline the earlier governance phase of this project was built around.

**Is `IMPLEMENTATION_PLAYBOOK.md` still the correct next document?** Yes, with one addition ahead of it: running the existing test suite to confirm baseline health is not a document at all, and it should happen before the playbook, not after — it's a five-minute command, not a planning artifact, and it is the one piece of missing verification this entire six-round process has not yet performed.

---

*This document does not define daily workflow, branch strategy, or review mechanics — that is the deliberate scope of `IMPLEMENTATION_PLAYBOOK.md`, next.*
