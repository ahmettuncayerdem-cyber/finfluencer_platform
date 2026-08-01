# Product Architecture — Computational Communication Research Platform

**Status:** Living design document. Built incrementally, section by section, by explicit request.
**Scope:** Product/UX/platform architecture only. No implementation until the full architecture-first pass is complete.
**Relationship to the codebase:** This document describes a *future* product built on top of the existing `finfluencer` research toolkit. It does not describe, and should not be confused with, the Engineering Governance work in `docs/governance/` (WP-01–WP-06), which concerns the current Python package's internal quality, not the product built around it.

---

## 1. Product Vision

### 1.1 Where this starts from

The engine that exists today is not a generic "communication research platform." It is a specific, working pipeline: collect YouTube activity for a defined roster of channels, checkpoint and reproduce every run, extract topics (BERTopic), score sentiment, and correlate against Turkish equity/macro data (BIST100, TCMB EVDS). It was built to answer one study's questions about Turkish financial YouTube influencers.

That specificity is an asset, not a limitation to be immediately generalized away. It means real methodological decisions — reproducibility guarantees, checkpointing, a run-manifest system, a versioning policy that already separates software version from research/citation version — were made under the pressure of an actual study, not speculated in the abstract. Most research-tooling projects that try to be general-purpose from day one end up general-purpose and useless; the ones that become platforms usually start as one good tool for one real problem and widen deliberately.

### 1.2 Vision statement

> **A reproducible, auditable research platform that turns "collect social content → model it → interpret it → publish it" from a bespoke engineering project into a repeatable service — starting from the influencer/creator-content research use case the engine already proves, and widening to computational communication research as a category once that wedge is validated commercially.**

Three words carry the weight here, and each is a deliberate design constraint, not marketing language:

- **Reproducible** — every analysis run must be re-derivable from its inputs and parameters. This is not a nice-to-have UX feature; it is already a hard engineering invariant in the current system (checkpoints, run manifests, deterministic seeding) and it is the single biggest thing that differentiates a research platform from a generic analytics SaaS. Academic buyers will not trust a black box.
- **Auditable** — every number that ends up in a paper or a report must be traceable back to the run, the model version, and the raw data that produced it. This maps directly onto "Publication-ready Tables" and "Reproducibility" in your module list, and it should be treated as a cross-cutting requirement, not a feature checkbox.
- **Category, not single-vertical, ambition — but sequenced.** See 1.4 below; this is the one place I'd push back hardest on the brief as written.

### 1.3 Who it's for, and in what order

Your target-user list (communication researchers, universities, research centers, graduate students, digital communication analysts, computational social science researchers, media researchers, think tanks) is a *market map*, not a *launch sequence*. Treating it as a launch sequence — i.e., building generically for all eight groups at once — is the most common way research-tooling products stall: the information architecture, the AI assistant's prompts, the report templates, and the pricing all end up mushy because they're trying to serve a media researcher studying TikTok moderation and a finance PhD studying YouTube influencers with the same defaults.

Recommended sequencing:

1. **Beachhead (v1):** Individual researchers and small labs doing creator/influencer-content research on YouTube — this is exactly what the engine does today. Buyer: a single PI or a graduate student with a small grant. Unit of value: one study, start to finish, reproducibly, faster than hand-rolling scripts.
2. **Expansion (v1.x–v2):** Research centers and think tanks running *multiple* studies/projects concurrently — this is where "Project Management," "Cross-project comparison," and "Institutional Accounts" start to earn their keep, because a single researcher rarely needs to compare across projects; a lab does.
3. **Horizontal (v2+):** Generalize past YouTube/finance into other platforms (TikTok, Instagram, X) and other analysis domains (political communication, health communication) once the collection-provider abstraction and topic/sentiment pipeline have been proven reusable by real paying users on the beachhead case — not before. The codebase already has the right shape for this (`providers/platform/` is already an abstraction boundary, not a YouTube-only module), which is a genuine head start; it just isn't evidence that the *product* should market itself as platform-agnostic on day one.

### 1.4 An assumption I'd challenge directly: the brand

`finfluencer.ai` / `finfluencer.com` names the product after one specific research object (financial influencers). That's a strong, clear name for the v1 beachhead — arguably better than a generic name, because it signals exactly what the tool is good at to the exact buyer who needs it first. It is a *weak* name for the "computational social science / media research" horizontal in section 1.3's step 3: a health-communication researcher or a political-communication lab is unlikely to seriously evaluate a product called "Finfluencer."

This is a real fork, not a detail to defer silently:

- **Option A — Own the vertical.** Keep the Finfluencer brand, stay deliberately positioned as *the* tool for financial-influencer and creator-economy research, and let the horizontal platform (if it happens) be a second brand or a rename event later, the way many B2B tools rebrand at their Series A once the ICP is proven.
- **Option B — Neutral platform name now.** Pick a category-neutral name today (something like a generic "Corpus"/"Signal"/"[X]lens" style name) and treat "Finfluencer" as the name of the *first vertical template/module* inside the neutral platform, not the platform itself.

I'd lean toward **Option A** for v1 — a sharp, credible name for a sharp, credible v1 scope beats a vague name for a vague scope — but this is a decision with real downstream consequences for domain registration, IA naming, and go-to-market, so I'm flagging it explicitly rather than picking silently. It also directly affects the Information Architecture below: whether "Project" is a generic research container or something more Finfluencer-specific (e.g., "Study") is a naming decision that should follow from this call.

### 1.5 What "commercial-grade" should mean here, concretely

Given the audience (academics, not enterprise IT buyers), commercial-grade should not be read as "enterprise SaaS with SSO/SCIM/SOC2 on day one." It should be read as:

- Reliability and reproducibility a peer reviewer would accept without argument.
- A price point and procurement path a single grant or a university subscription can actually clear (this rules out enterprise-only sales motions as the primary GTM).
- Institutional accounts and role management as a *retention and expansion* mechanism (a lab renews as a lab, not as five individual subscriptions), not as a security-compliance checkbox chased prematurely.

I'll return to pricing/licensing mechanics in the Commercialization Roadmap deliverable — flagging it here only because it should shape the Information Architecture's tenancy model now, before screens get designed against the wrong assumption.

### 1.6 Out of scope for v1 (explicit, not implied)

To keep the vision honest about sequencing:

- Multi-platform collection (TikTok/Instagram/X) — v2+, not v1.
- Non-YouTube, non-financial verticals — v2+, not v1.
- Enterprise security certifications (SOC2/ISO) — deferred until institutional buyers actually require it in a live deal.
- A general-purpose "bring your own dataset" ingestion layer — v1 ingestion is YouTube-collection-shaped, matching what the engine already does well.

---

## 2. Information Architecture

*(Diagram delivered separately in-conversation as the IA hierarchy visual. Structure and reasoning below; not duplicated here.)*

### 2.1 Core entities and their relationships

The IA is organized around a small number of nesting containers, each mapping to something that already exists conceptually in the current backend (noted in brackets) or is genuinely new:

- **Institution / Tenant** *(new)* — the billing and access boundary. A university department, a research center, or an individual researcher account are all "one tenant," just different sizes.
- **Users & Roles** *(new)* — see User Roles deliverable (next-but-one). Scoped to a tenant.
- **Project** *(generalizes the current hardcoded 4-analyst roster / `analysts.yaml` concept)* — the unit a researcher actually thinks in: "my study." A Project owns its own roster of channels/analysts, its own configuration, and everything nested below.
  - **Datasets & Collections** *(maps directly to `collect/` + the checkpoint/manifest system, which already exists and already gives you reproducible, resumable collection runs — a genuine platform asset)*
  - **Analyses & Experiments** *(maps to `topics/bertopic_runner.py`, `reporting/orchestrator.py`, the market subsystem — and to the existing reproducibility/versioning discipline, which is directly sellable as "every result is re-derivable")*
  - **Reports & Exports** *(maps to `reporting/`; PDF/Word export are net-new frontend/export work, not net-new analytical work)*
- **AI Research Assistant** *(new, cross-cutting)* — deliberately drawn as attaching across Projects/Analyses rather than nested inside one, because its most valuable use ("explain this topic cluster," "draft the methods paragraph for this run") needs context from an Analysis but shouldn't be architecturally trapped inside it — see AI Integration Strategy deliverable.
- **Platform Services** *(new)* — API, billing/license, tenant admin. Deliberately grouped as one box at the diagram level to keep the top tier readable; each is a real subsystem, detailed in later deliverables (API Architecture, Commercialization Roadmap).

Two capabilities from your module list — **Cross-project comparison** and **Research history** — are deliberately *not* drawn as nodes in the hierarchy. They are views that query *across* the Project boundary (e.g., "compare topic drift between two studies"), not containers something else lives inside. Modeling them as first-class nodes would misrepresent the IA as flatter/more tangled than it is; modeling them as cross-cutting queries over the Project layer is both more accurate and simpler to build (they become a reporting/query feature on top of a clean per-Project data model, not a structural fork of it).

### 2.2 Why "Project," not "Study" or "Workspace" (pending 1.4)

I've used "Project" provisionally, matching your module list. If Option A from 1.4 (own the vertical) is chosen, I'd revisit this specifically — "Study" reads more naturally to an academic user and maps more precisely onto how communication researchers already talk about their work (a "study," not a "project" in the software-engineering sense). This is a small naming call but it ripples through every screen title in the Screen Inventory deliverable, so worth deciding once, early, rather than drifting.

### 2.3 Depth constraint

The hierarchy is deliberately capped at **Tenant → Project → {Datasets, Analyses, Reports}** — three levels, not four. `Datasets` does not further nest `Collection Runs` as a separate IA-level container; a Collection Run is a *version/state* of a Dataset (this is exactly what the existing checkpoint/manifest system already models), surfaced as a history/timeline within the Dataset screen rather than as its own IA node. Same logic applies to Analysis runs versus Analyses. Keeping the tree shallow is a deliberate navigation-usability call, not a simplification for its own sake — it directly shapes the Navigation Structure deliverable (a left-nav that's 3 levels deep stays usable; one that's 5 levels deep does not).

---

---

## Deliverable Status

| # | Deliverable | Status |
|---|---|---|
| 1 | Product Vision | Done |
| 2 | Information Architecture | Done |
| 3 | Product Scope | Done |
| 4 | System Modules | Done |
| 5 | User Roles | Done |
| 6 | User Journey | Done |
| — | Module Specifications (Purpose / Inputs / Outputs / Dependencies / API) | Done — supporting artifact, not in original 16-item list; produced now as groundwork for Screen Inventory, Database Concept, API Architecture |
| 7 | Navigation Structure | Done |
| 8 | Screen Inventory | Done |
| — | AIG-001 (AI Interpretation Guardrail) | Done — formal guardrail, binds AI Integration Strategy (pending) |
| 9 | Database Concept | Done — refines the Report↔InterpretationRecord relationship first sketched in §9.3/§9.4; see §10.0 |
| 10 | API Architecture | Done — contract-first; REST endpoints derived, not designed, in §11.3 |
| — | AIG-003 (AI Operations are Stateless) | Done — formalized in §11.4; note AIG-002 is not yet defined anywhere in this document, flagged not filled |
| 11 | Backend Architecture | Done — BKG-001 formalized in §12.5 |
| 12 | Frontend Architecture | Done — FG-001, FG-002 formalized in §13.14 |
| 13 | Authentication Strategy | Done — extends §10.1's `AuditLogEntry` with a User-scoped `AuthenticationEvent`; introduces `ServiceAccountToken` (see §14.1) |
| 14 | AI Integration Strategy | Done — introduces `PromptTemplate` entity; formalizes **AIG-004** (§15.21); AIG-002 still not invented |
| 15 | Deployment Architecture | Done — formalizes **DAG-001** (§16.24); AIG-002 still not invented |
| 16 | Product Evolution & Commercialization Architecture *(requested as "Future Commercialization Roadmap"; expanded per turn 17's instructions)* | Done — introduces **DAD-002** (§17.7); no new AIG/BKG/FG/DAG required |

**Working title:** "Finfluencer Platform." Final branding is a Deferred Architectural Decision — see **DAD-001** at the end of this document. Do not read the working title as a resolved decision.

---

## 3. Product Scope

### 3.1 MVP scoping table

Scored against the v1 beachhead defined in §1.3 (individual researcher / small lab, YouTube creator-influence research). "Backend asset" marks capabilities the existing Python engine already provides — these are wrap-and-expose work, not new research/engineering. Everything else is genuinely new build.

| Capability | v1 MVP | v1.x | v2+ | Backend asset today? |
|---|---|---|---|---|
| Project Management | ✅ | | | No — new container concept |
| Dataset / Collection Management | ✅ | | | ✅ `collect/`, checkpoint system |
| YouTube Collection | ✅ | | | ✅ `providers/platform/youtube.py` |
| Topic Modeling | ✅ | | | ✅ `topics/bertopic_runner.py` |
| Sentiment Analysis | ✅ | | | ✅ reporting pipeline |
| Cross-channel comparison | ✅ | | | ✅ already the study's core design (comparative, non-hierarchical framing across the analyst roster) |
| Topic/Sentiment Visualization | ✅ | | | Partial — data exists, no web rendering layer |
| Publication-ready Tables | ✅ | | | ✅ `reporting/manuscript_tables.py` |
| PDF Report Generation | ✅ | | | No — rendering layer only |
| Experiment Tracking | ✅ | | | ✅ checkpoint + Run Manifest System |
| Reproducibility | ✅ | | | ✅ core existing invariant |
| User Accounts & Auth | ✅ | | | No |
| Minimal Roles (Owner / Member) | ✅ | | | No |
| Market correlation (BIST100/TCMB) | ✅ (as an optional analysis type, not a core requirement) | | | ✅ market subsystem — see §3.3 |
| Word Export | | ✅ | | No |
| Network / Graph Generation | | ✅ | | No |
| LLM-assisted Interpretation (scoped: explain-this-result) | | ✅ | | No |
| Role Management (granular RBAC) | | ✅ | | No |
| Institutional Accounts | | ✅ | | No |
| Cross-project comparison | | ✅ | | No — depends on multi-project use, which is itself v1.x |
| Public API | | ✅ | | No |
| Subscription billing (Stripe-hosted, seat-based) | | ✅ | | No |
| Conversational AI Research Assistant | | | ✅ | No — larger scope than scoped interpretation above |
| Multi-platform collection (TikTok/Instagram/X) | | | ✅ | No |
| License Management (institutional terms) | | | ✅ | No |
| Non-YouTube, non-financial verticals | | | ✅ | No |

### 3.2 What "MVP" means here

The MVP is not "fewer features" in the abstract — it is specifically: **everything a single researcher needs to run one reproducible study end-to-end, from collection to a submittable PDF table, without touching a CLI.** That is a coherent, shippable, individually valuable product on its own, which matters commercially: it can be sold and used before a single line of the v1.x institutional/multi-project layer exists. A common failure mode in platform rebuilds is treating v1.x concerns (roles, institutional accounts, cross-project comparison) as blocking v1 — they should not; they depend on v1's data model being right, not the other way around.

### 3.3 A scope call worth surfacing explicitly

Market correlation (BIST100/TCMB EVDS) is listed as v1 MVP but marked "optional analysis type." This is a deliberate scope narrowing from how the current engine treats it: today, market data is part of *this specific study's* design. In the product, it should be modeled as one pluggable analysis type among several (topic modeling, sentiment, market correlation), selectable per Project — not a universal requirement every Project must configure. A media researcher studying health-communication influencers has no BIST100 correlation to run. Keeping it optional-but-present in v1 costs little (the backend already does it) and is the first concrete instance of the domain-extensibility principle DAD-001 depends on — see §5.

### 3.4 Explicit non-goals for v1 (reaffirmed from §1.6)

Multi-platform collection, non-YouTube/non-financial verticals, enterprise security certifications, and a general "bring your own dataset" ingestion layer remain out of scope for v1, as stated in the Vision. Nothing in this Scope section reopens that.

---

## 4. System Modules

Functional modules — what the system does, not how it's built (backend/frontend technology choices belong to later deliverables). Each module is marked **[Backend-inherited]** (existing engine capability, needs a service/API boundary put around it) or **[New]** (no current equivalent).

1. **Collection Engine** [Backend-inherited] — ingests channel/creator content via a pluggable content-platform provider (YouTube today). Owns collection runs, rate/quota management, and checkpointed resumability.
2. **Analysis Engine** [Backend-inherited] — runs configured analysis types (topic modeling, sentiment, market correlation as of v1) against a Dataset. Each analysis type is a plugin, not a hardcoded pipeline stage — this is the second concrete extensibility hook for DAD-001.
3. **Reproducibility & Experiment Tracking** [Backend-inherited, cross-cutting] — not a module a user "opens"; a service every other module calls into. Owns run manifests, parameter snapshots, and the guarantee that any Analysis or Collection run is re-derivable. This is the platform's strongest existing differentiator and should be architected as infrastructure, not a feature.
4. **Reporting & Publication Engine** [Backend-inherited for tables; New for rendering] — turns Analysis output into manuscript-ready tables (exists), and renders them into PDF (new) and, in v1.x, Word (new).
5. **AI Interpretation Layer** [New] — v1.x scoped as single-shot "explain this result" against one Analysis's output; the full conversational Research Assistant (v2) is an extension of this module's context model, not a separate module bolted on later.
6. **Identity & Access** [New] — accounts, auth, tenant membership, and roles. Minimal in v1 (Owner/Member), extends to granular RBAC and Institutional Accounts in v1.x without a data-model change (roles are additive, not restructured).
7. **Billing & Licensing** [New] — v1.x. Seat/subscription billing first; formal license-term management (institutional agreements) is v2, layered on top of the same tenant model rather than a separate system.
8. **Public API** [New] — v1.x. The web frontend consumes an internal API from v1 onward (see §4.1); "Public API" is that same API, documented and access-controlled for external institutional integration — not a second API built later.
9. **Web Application Shell** [New] — navigation, Project workspace, the actual UI. Detailed in Navigation Structure and Screen Inventory (pending deliverables).
10. **Platform Admin / Ops** [New, internal-only] — tenant provisioning, usage monitoring, support tooling. Not user-facing; included here because it has real scope and staffing implications later, not because it appears in the product's own navigation.

### 4.1 One architectural decision worth stating now, not deferring

The frontend should never talk directly to the Collection/Analysis Engines. From v1, there is exactly one API surface (module 8) that the Web Application Shell consumes — the same surface later exposed externally as the "Public API." Building two API surfaces (an informal internal one now, a "real" public one later) is a common, expensive rebuild trap; building one from the start costs nothing extra at MVP size and removes an entire future migration.

---

## 5. Architectural Implications for DAD-001 (Branding)

DAD-001 is deliberately not being resolved here. What *is* being resolved now is that the architecture must not foreclose either branding path identified in §1.4 (own the vertical vs. neutral platform + first vertical template). Three concrete commitments, made in this pass, keep that door open:

1. **Vertical Template concept (introduced here, formalized in Database Concept).** A Project is instantiated from a template that supplies its default analysis types, vocabulary, and report layout. "Financial Influencer Study" is the v1 template. This means Option A (stay "Finfluencer," add templates later under the same name) and Option B (neutral platform name, "Finfluencer" becomes the name of the first template) are **both still reachable from the same architecture** — the difference between them becomes a marketing/naming decision at the presentation layer, not a data-model fork. This is the single most important implication: DAD-001 is now safely deferrable *because* it no longer has architectural teeth.
2. **Domain-neutral internal vocabulary, domain-specific default copy.** Internal entity names (Project, Dataset, Analysis, Creator/Channel Roster) stay generic in the data model and API (§4.1) regardless of what the UI calls them. The v1 UI can say "Analyst Roster" and "Finfluencer Study" as *template-level display strings* without those words appearing in the schema or the API contract. This was already implicit in §2's IA naming (`Project` chosen provisionally over `Study`); it's now an explicit rule, not an accident of naming.
3. **Analysis types as plugins, not pipeline stages (§4, module 2).** Market correlation being optional-not-core (§3.3) is the proof case: nothing about the Analysis Engine's architecture assumes "finance" or "Turkish markets" as a first-class concept. A future health-communication or political-communication vertical template supplies different default analysis types against the same Engine, with no re-architecture.

**Resolution trigger for DAD-001 (as instructed):** revisit once Product Scope, System Modules, and MVP boundaries — all now defined — are joined by enough of the remaining deliverables (particularly Screen Inventory and Frontend Architecture) that the actual v1 user-facing vocabulary is concrete enough to test a name against real screens, not an abstract module list.

### Deferred Architectural Decisions Register

| ID | Decision | Status | Depends On | Architectural Safeguard Applied |
|---|---|---|---|---|
| DAD-001 | Product / domain branding (own the vertical vs. neutral platform name) | Deferred | Screen Inventory, Frontend Architecture | Vertical Template concept; domain-neutral internal vocabulary; pluggable analysis types |

---

## 6. User Roles

Designed for the full SaaS/institutional end-state, not just the MVP — but every role below is tagged with the phase it actually activates in (§3's v1 / v1.x / v2 sequencing), so this table describes the target shape without implying all of it ships at once. Roles are scoped at either **Tenant** level (institution-wide) or **Project** level (per-study); this two-level scoping is itself the extensibility mechanism — v1 collapses both levels onto one person (an individual researcher *is* their own tenant), v1.x/v2 separate them without a data-model change, consistent with §5's domain-extensibility principle applied to identity rather than branding.

| Role | Phase | Scope | Core Responsibilities | Key Permissions | Future Extensibility |
|---|---|---|---|---|---|
| **Institution Owner / Admin** | v1.x | Tenant | Billing, seat management, tenant-wide settings, create/remove Projects, assign Project Owners | Full on Identity & Access + Billing modules; override access to all Projects in the tenant | v2: splits into a dedicated Billing Admin (finance contact) once tenant size makes a single billing+access owner impractical |
| **Lab / Department Manager** | v2 | Tenant sub-group | Oversee a subset of Projects within a larger institutional tenant; manage seat allocation within a budget; approve new Projects in their group | Full within assigned Project group; no tenant-wide billing access | Enables org-chart-shaped deployments (a university-wide license with per-department budgets) without restructuring the Tenant/Project model |
| **Project Owner (Principal Investigator)** | v1 | Project | Configure roster/config, run collection & analysis, invite collaborators, export, archive/delete the Project | Full within own Project(s); no access to other Projects or tenant billing | v1.x: can be granted cross-Project "Program Lead" read access without owning those Projects — supports Cross-project comparison (§3) without weakening per-Project ownership |
| **Researcher / Collaborator (Member)** | v1 | Project | Run collection & analysis, view/edit data and reports within an assigned Project | Execute + Edit within assigned Project; cannot delete the Project, change roster ownership, or touch billing | v1.x: promotable to the narrower Analyst or Viewer sub-roles below as granular RBAC ships — Member is the v1 default because v1 has no finer grain yet, not because it's the intended long-term default |
| **Analyst / Contributor** | v1.x | Project | Run pre-configured analyses against existing Datasets; cannot alter collection configuration or the channel/creator roster | Execute Analysis; View Reports; no Collection-config write access | Directly serves the "graduate student / RA" persona from the Vision's target-user list — someone who should run analyses under a study design they didn't set up |
| **Viewer / Reviewer** | v1.x | Project | View results and reports only; no execution rights | View only, across Reports and (read-only) Analysis output | v2: shareable read-only links without requiring a full account — high value for thesis committees, journal reviewers, co-authors outside the tenant |
| **External Collaborator / Guest** | v2 | Project (scoped, time-limited) | Cross-institution collaboration on a single Project without full tenant membership | Configurable subset, typically Analyst- or Viewer-equivalent, with an expiry date | Answers a real academic pattern (a co-PI at another university) that Institutional Accounts alone doesn't solve, since that co-PI isn't part of the host institution's tenant |
| **Service Account / API Client** | v1.x | Tenant or Project (scoped token) | Non-human identity for institutional integrations pulling reports/data via the Public API | Scoped, token-based; read-mostly by default | v2: write-scoped tokens for automated collection triggering (e.g., a university's own scheduler kicking off a monthly collection run) |
| **Platform Admin / Support** *(internal, not customer-facing)* | v1 (internal from day one) | All tenants | Tenant provisioning, support diagnostics, abuse/quota monitoring | Full internal visibility, audited access | Not part of the commercial role model — documented here because it has real staffing and access-control implications for Identity & Access (module 6) regardless |

### 6.1 Permission matrix (by System Module)

Rows are the customer-facing roles only (internal Platform Admin excluded — it has blanket audited access by design, not a graduated permission level).

| Role | Collection Engine | Analysis Engine | Reporting | AI Interpretation | Identity & Access | Billing | Public API |
|---|---|---|---|---|---|---|---|
| Institution Owner/Admin | Full (all Projects) | Full (all Projects) | Full (all Projects) | Full (all Projects) | Full | Full | Manage tokens |
| Lab/Department Manager | Full (group) | Full (group) | Full (group) | Full (group) | View (group) | None | None |
| Project Owner (PI) | Full (own Project) | Full (own Project) | Full (own Project) | Full (own Project) | Manage own Project's members | None | Manage own Project's tokens |
| Researcher/Collaborator | Execute + Edit | Execute + Edit | Edit | Use | View own membership | None | None |
| Analyst/Contributor | View only | Execute (pre-configured) | View | Use | View own membership | None | None |
| Viewer/Reviewer | View only | View only | View only | View only | View own membership | None | None |
| External Collaborator | Per grant (Analyst/Viewer-equivalent) | Per grant | Per grant | Per grant | View own membership | None | None |
| Service Account | Per token scope | Per token scope | Per token scope | None | None | None | Per token scope |

---

## 7. User Journey

### 7.1 Overview

Modeled as seven stages, with one deliberate loop rather than a strict pipeline: researchers routinely re-run analysis after an AI-assisted interpretation surfaces a data-quality concern or an unexpected pattern worth re-parameterizing, and the architecture should treat that as the normal path, not an edge case. Diagram delivered separately in-conversation; stage detail below.

### 7.2 Stage-by-stage

1. **Project Creation** — *Actor: Project Owner (PI).* Selects a Vertical Template (§5 — "Financial Influencer Study" in v1), names the Project, defines the initial channel/creator roster. Backs onto Identity & Access (Project + membership created) and establishes the Project as the reproducibility boundary everything below nests inside.
2. **Data Collection** — *Actor: PI or Researcher/Collaborator.* Configures a collection run (date window, roster subset) and executes it through the Collection Engine. Reproducibility & Experiment Tracking checkpoints the run from the first step — a partial or interrupted collection is resumable, not restarted, exactly as the existing engine already guarantees.
3. **Analysis Configuration** — *Actor: PI or Researcher.* Selects which analysis types to run against the collected Dataset (topic modeling, sentiment, and — per §3.3 — market correlation only if the template/study calls for it) and sets parameters. This is where the "pluggable analysis type" architecture (§5) becomes user-visible: the configuration screen's option list is template-driven, not hardcoded.
4. **Analysis Execution** — *Actor: system, triggered by PI/Researcher/Analyst.* The Analysis Engine runs the configured analyses, checkpointed the same way as Collection. Produces the run's manifest — the artifact that makes step 5 and step 6 both trustworthy and re-derivable.
5. **AI-Assisted Interpretation** — *Actor: any role with Analysis view access.* Scoped in v1.x to single-shot "explain this result" against one Analysis run's output (§4, module 5). Frequently loops back to step 4 — an explanation surfaces a confound or an unexpected topic cluster, the researcher adjusts parameters and re-runs. This loop is the single most important non-linear element in the journey and should shape the UI (an "iterate" affordance, not a dead-end "done" state) once Screen Inventory is designed.
6. **Reporting & Export** — *Actor: PI or Researcher/Collaborator with Edit rights.* Assembles manuscript-ready tables (existing capability), renders PDF (v1) and Word (v1.x). This is the stage where Viewer/Reviewer role access matters most — a PI shares a Report, not raw Analysis output, with a co-author or committee member.
7. **Project Archival** — *Actor: PI.* Freezes the Project into a read-only, still-citable state — not deleted, not billed as an active seat necessarily (billing implications belong to the Commercialization Roadmap deliverable), but permanently retrievable. This is the direct product expression of the Reproducibility principle from the Vision: a study archived today must still be re-derivable and viewable years later, including by a peer reviewer who was never a tenant member (pairing naturally with the v2 shareable read-only link idea from §6).

### 7.3 What's deliberately not in this journey yet

Cross-Project comparison and Research History (§2.1) are not journey *stages* — they're views a PI or Lab Manager reaches from outside any single Project's lifecycle, after multiple Projects exist. They'll be modeled in Navigation Structure as a separate entry point, not inserted into this per-Project lifecycle.

---

## 8. Module Specifications

Written to directly seed Screen Inventory (Inputs/Outputs imply screens and forms), Database Concept (Inputs/Outputs imply entities), and API Architecture (Primary API Interactions imply endpoints) — deliberately at the conceptual level; none of these three deliverables are being designed yet.

### 8.1 Collection Engine
- **Purpose:** Ingest content-platform data (channels/creators, videos, comments) into a Dataset, reproducibly and resumably.
- **Inputs:** Roster (channel/creator identifiers), collection window (date range), platform credentials/quota state, prior checkpoint state (if resuming).
- **Outputs:** A versioned Dataset (raw + normalized records); a Collection Run manifest (parameters, timing, quota consumption, resulting row counts).
- **Dependencies:** Reproducibility & Experiment Tracking (checkpointing, manifest); Identity & Access (Project-scoped credential/quota ownership).
- **Primary API interactions:** `startCollectionRun`, `getCollectionRunStatus`, `resumeCollectionRun`, `listDatasets`.

### 8.2 Analysis Engine
- **Purpose:** Run a configured, pluggable set of analysis types (topic modeling, sentiment, market correlation, future types) against a Dataset.
- **Inputs:** A Dataset reference, selected analysis type(s), parameters per type, the active Vertical Template's default configuration.
- **Outputs:** Analysis Run results (topic assignments, sentiment scores, correlation output as applicable); an Analysis Run manifest.
- **Dependencies:** Collection Engine (source Dataset must exist); Reproducibility & Experiment Tracking; Reporting & Publication Engine (consumes results downstream).
- **Primary API interactions:** `configureAnalysisRun`, `startAnalysisRun`, `getAnalysisRunResult`, `listAnalysisTypes` (template-driven).

### 8.3 Reproducibility & Experiment Tracking
- **Purpose:** Cross-cutting service guaranteeing every Collection and Analysis run is checkpointed, versioned, and re-derivable from its recorded parameters. Not a screen users navigate to directly.
- **Inputs:** Run parameters and state from Collection Engine and Analysis Engine at each checkpoint.
- **Outputs:** Run manifests (the artifact other modules cite as evidence of reproducibility); resumable checkpoint state.
- **Dependencies:** None upstream — this is infrastructure other modules depend on, not a consumer of them.
- **Primary API interactions:** Internal only in v1 (no direct user-facing endpoint); manifests are surfaced *through* Collection/Analysis Engine responses, not queried standalone until a later "Research History" API is scoped.

### 8.4 Reporting & Publication Engine
- **Purpose:** Turn Analysis Run output into manuscript-ready tables, PDF reports, and (v1.x) Word documents.
- **Inputs:** One or more Analysis Run results, a report template/layout selection, author/citation metadata.
- **Outputs:** Rendered PDF (v1) / Word (v1.x) documents; manuscript-ready table objects (already an existing backend capability) available for in-app viewing before export.
- **Dependencies:** Analysis Engine (source results); Identity & Access (Viewer/Reviewer sharing permissions apply here).
- **Primary API interactions:** `generateReport`, `getReportStatus`, `exportReport(format)`, `listReportsForProject`.

### 8.5 AI Interpretation Layer
- **Purpose:** v1.x — produce a single-shot natural-language explanation of one Analysis Run's output. v2 — extend the same context model into a conversational Research Assistant.
- **Inputs:** An Analysis Run result reference, the requesting user's question/prompt (v2) or a fixed "explain this" trigger (v1.x).
- **Outputs:** Natural-language interpretation text, optionally citing specific result elements (a topic, a sentiment shift) it's explaining.
- **Dependencies:** Analysis Engine (source of truth for what's being explained); must never be the source of truth itself — see AI Integration Strategy (pending deliverable) for the guardrail this implies.
- **Primary API interactions:** `requestInterpretation(analysisRunId, scope)`, `getInterpretationHistory` (v2, once conversational).

### 8.6 Identity & Access
- **Purpose:** Own tenants, Projects, users, memberships, and the role model defined in §6.
- **Inputs:** User registration/auth events, role assignment actions, Project creation events.
- **Outputs:** Authenticated sessions/tokens; authorization decisions consumed by every other module.
- **Dependencies:** None upstream — foundational, alongside Reproducibility & Experiment Tracking.
- **Primary API interactions:** `authenticate`, `getCurrentUser`, `listProjectMembers`, `assignRole`, `createProject`.

### 8.7 Billing & Licensing
- **Purpose:** v1.x — seat/subscription billing. v2 — formal institutional license-term management.
- **Inputs:** Tenant plan selection, seat count, payment method (via a payment processor, not stored directly — see Authentication Strategy deliverable for the security posture this implies).
- **Outputs:** Subscription status, invoices, seat-usage state consumed by Identity & Access to gate new member invitations.
- **Dependencies:** Identity & Access (tenant/seat counts).
- **Primary API interactions:** `getSubscriptionStatus`, `updateSeats`, webhook intake from the payment processor (not a direct client-facing endpoint).

### 8.8 Public API
- **Purpose:** v1.x — the same internal API surface the Web Application Shell already consumes (§4.1), documented and access-controlled for external/institutional integration.
- **Inputs:** Authenticated requests via Service Account tokens (§6) or user session tokens.
- **Outputs:** JSON representations of Datasets, Analysis Runs, Reports — no capability exists here that isn't also used internally.
- **Dependencies:** Identity & Access (auth/scoping); every other module (it's a facade, not a separate implementation).
- **Primary API interactions:** N/A at this level of detail — full endpoint design belongs to the API Architecture deliverable.

### 8.9 Web Application Shell
- **Purpose:** The navigable UI — Project workspace, module screens, cross-cutting views (Cross-project comparison, Research History).
- **Inputs:** User interactions; API responses from every backend module.
- **Outputs:** Rendered screens; user-initiated API calls.
- **Dependencies:** Public API (§8.8) exclusively — no direct backend access, per the §4.1 decision.
- **Primary API interactions:** Consumes all of the above; detailed in the pending Navigation Structure and Screen Inventory deliverables.

### 8.10 Platform Admin / Ops
- **Purpose:** Internal tenant provisioning, support diagnostics, abuse/quota monitoring. Not customer-facing.
- **Inputs:** Support tickets, quota/usage alerts, provisioning requests.
- **Outputs:** Tenant configuration changes, audit logs.
- **Dependencies:** Identity & Access (audited override access, §6).
- **Primary API interactions:** Internal-only administrative endpoints, out of scope for the Public API surface entirely.

---

## 9. Navigation Structure & Screen Inventory

Designed as one layer, not two documents, per instruction. This is the point where Product Architecture stops being purely conceptual and becomes the direct input to Database Concept (entities), API Architecture (endpoints), and Frontend Architecture (routes/components) — every field below was chosen because a later deliverable consumes it directly, not for documentation completeness on its own.

### 9.1 How navigation nodes relate to screens

A **navigation node** is a persistent destination reachable from the app shell's nav rail/menu — it has a stable place in the tree a user can always get back to. A **screen** is any distinct view, including ones reached only by drilling into another screen (e.g., clicking a specific Analysis Run). Every navigation node maps to exactly one screen; most screens are *not* navigation nodes. This directly preserves the §2.3 commitment that the entity hierarchy stays three levels deep (Tenant → Project → {Datasets, Analyses, Reports}) — Collection Runs and Analysis Runs are drill-down screens reached from their parent list screen, never separate nav-tree nodes, exactly as §2.3 specified for the data model and now confirmed for navigation too.

### 9.2 Navigation Structure

| Node ID | Node | Parent | Children | Accessible Roles | Target Screen | Backend Modules Involved |
|---|---|---|---|---|---|---|
| NAV-01 | Dashboard | ROOT | — | All authenticated roles | SCR-DASH-01 | Identity & Access, Reporting, Reproducibility |
| NAV-02 | Projects (List) | ROOT | NAV-03 | All except Service Account | SCR-PROJ-01 | Identity & Access, Collection Engine |
| NAV-03 | Project Workspace | NAV-02 | NAV-04–NAV-09 | PI, Researcher, Analyst, Viewer, External Collaborator (per grant) | SCR-PROJ-02 | All Project-scoped modules |
| NAV-04 | Overview | NAV-03 | — | Same as NAV-03 | SCR-PROJ-02 | Reproducibility, Reporting |
| NAV-05 | Datasets & Collections | NAV-03 | — | PI, Researcher (edit); Analyst, Viewer (view) | SCR-DATA-01 | Collection Engine, Reproducibility |
| NAV-06 | Analyses | NAV-03 | — | PI, Researcher, Analyst (execute); Viewer (view) | SCR-ANLY-01 | Analysis Engine, Reproducibility |
| NAV-07 | Reports | NAV-03 | — | PI, Researcher (edit); Analyst, Viewer (view) | SCR-RPT-01 | Reporting & Publication Engine |
| NAV-08 | Project Settings | NAV-03 | NAV-08a, NAV-08b | PI only | SCR-SET-01 | Collection Engine (roster), Identity & Access |
| NAV-08a | Roster & Configuration | NAV-08 | — | PI only | SCR-SET-01 | Collection Engine, Identity & Access |
| NAV-08b | Members & Roles | NAV-08 | — | PI only | SCR-SET-02 | Identity & Access |
| NAV-09 | Archive Project | NAV-03 | — | PI only | SCR-PROJ-03 | Reproducibility, Reporting, Identity & Access |
| NAV-10 | Cross-Project Comparison *(v1.x)* | ROOT | — | PI (own Projects), Lab Manager (group), Institution Owner (all) | SCR-XPRJ-01 | Analysis Engine, Reporting |
| NAV-11 | Research History | ROOT | — | PI, Lab Manager, Institution Owner | SCR-HIST-01 | Reproducibility & Experiment Tracking |
| NAV-12 | Institution Admin *(v1.x)* | ROOT | NAV-12a, NAV-12b | Institution Owner/Admin only | SCR-ADM-01 | Billing & Licensing, Identity & Access |
| NAV-12a | Billing & Seats | NAV-12 | — | Institution Owner/Admin | SCR-ADM-01 | Billing & Licensing |
| NAV-12b | Tenant Members & Roles | NAV-12 | — | Institution Owner/Admin | SCR-ADM-02 | Identity & Access |
| NAV-13 | Account Settings | ROOT | — | All authenticated roles | SCR-ACCT-01 | Identity & Access |

NAV-10 and NAV-12 are v1.x-gated at the navigation level, consistent with §3's MVP table — in v1 they render hidden or as an upgrade prompt rather than a broken link, which the Frontend Architecture deliverable should treat as a standard pattern, not a one-off.

### 9.3 Screen Inventory

*Auth screens (SCR-AUTH-01/02) are included for completeness; full design belongs to the pending Authentication Strategy deliverable. Entity names below (Project, Dataset, CollectionRun, AnalysisRun, Report, InterpretationRecord, User, Membership, Tenant, VerticalTemplate, AnalysisType) are the conceptual entities Database Concept will formalize — used consistently here so that deliverable has no naming to invent, only structure to define.*

**SCR-AUTH-01 — Login**
Purpose: authenticate an existing user. Primary users: all. Inputs: credentials (mechanism TBD in Authentication Strategy). Outputs: authenticated session. Navigation entry: unauthenticated root. Exit paths: → SCR-DASH-01 on success; → SCR-AUTH-02 (sign-up) on request. Backend modules: Identity & Access. Primary API: `authenticate`. Core entities: User, Tenant. AI interactions: none. Error/empty states: invalid credentials; account locked; no empty state (always has the form).

**SCR-AUTH-02 — Sign Up / Tenant Onboarding**
Purpose: create a new individual or institutional tenant. Primary users: new PI or Institution Owner. Inputs: email, tenant type (individual/institutional), initial plan (v1.x). Outputs: new Tenant + User + default membership. Navigation entry: from SCR-AUTH-01. Exit paths: → SCR-PROJ-01 (empty state, prompting first Project creation). Backend modules: Identity & Access, Billing & Licensing (v1.x). Primary API: `createTenant`, `authenticate`. Core entities: Tenant, User, Membership. AI interactions: none. Error/empty states: email already registered; payment failure (v1.x, deferred to Billing & Licensing's own error handling).

**SCR-DASH-01 — Dashboard**
Purpose: tenant-wide landing view — recent activity across Projects, quick links. Primary users: all authenticated roles. Inputs: none (read view). Outputs: none. Navigation entry: NAV-01, post-login default. Exit paths: → SCR-PROJ-01, → SCR-HIST-01, → SCR-XPRJ-01 (v1.x). Backend modules: Reporting (summary widgets), Reproducibility (recent runs), Identity & Access (scoping). Primary API: `getDashboardSummary`. Core entities: Project, AnalysisRun (recent), Report (recent). AI interactions: none. Error/empty states: **empty state is the primary v1 first-run experience** — no Projects yet → prominent "Create your first Project" CTA, not a blank dashboard.

**SCR-PROJ-01 — Projects List**
Purpose: list all Projects the user has access to; entry point to create a new one. Primary users: PI (own), Researcher/Analyst/Viewer (assigned), Lab Manager/Institution Owner (group/all, v1.x). Inputs: none (list + filter). Outputs: selection → Project Workspace. Navigation entry: NAV-02. Exit paths: → SCR-PROJ-02 (select existing), → Project creation flow (new). Backend modules: Identity & Access, Collection Engine (status badges). Primary API: `listProjects`, `createProject`. Core entities: Project, Membership. AI interactions: none. Error/empty states: no Projects yet → CTA to create one (mirrors SCR-DASH-01's first-run state); load failure → retry.

**SCR-PROJ-02 — Project Overview**
Purpose: per-Project home — status of latest Collection/Analysis runs, quick links to the four Project-scoped areas. Primary users: all Project-assigned roles. Inputs: none. Outputs: none. Navigation entry: NAV-04, or directly from SCR-PROJ-01. Exit paths: → SCR-DATA-01, SCR-ANLY-01, SCR-RPT-01, SCR-SET-01 (PI only). Backend modules: Reproducibility, Reporting, Collection Engine, Analysis Engine (status only). Primary API: `getProjectSummary`. Core entities: Project, CollectionRun (latest), AnalysisRun (latest). AI interactions: none. Error/empty states: new Project with no Datasets yet → CTA into SCR-DATA-01's collection-run creation flow, not a generic empty grid.

**SCR-DATA-01 — Datasets & Collections List**
Purpose: list Datasets within a Project; entry point to start a new Collection Run. Primary users: PI, Researcher (full); Analyst, Viewer (view only). Inputs: none (list). Outputs: selection → Dataset Detail. Navigation entry: NAV-05. Exit paths: → SCR-DATA-02 (select), → SCR-DATA-03 (new run). Backend modules: Collection Engine, Reproducibility. Primary API: `listDatasets`. Core entities: Dataset, CollectionRun (summary). AI interactions: none. Error/empty states: no Datasets yet → CTA to SCR-DATA-03; a Dataset with a failed/interrupted run shows a resumable-state badge, not an error dead-end (per the Vision's reproducibility guarantee).

**SCR-DATA-02 — Dataset Detail**
Purpose: view a Dataset's contents and its full Collection Run history (the "version/state timeline" described in §2.3 — this screen, not a nav node, is where that history lives). Primary users: PI, Researcher, Analyst, Viewer (all view; PI/Researcher can trigger a new run). Inputs: none (view) / new-run trigger. Outputs: none. Navigation entry: drill-down from SCR-DATA-01. Exit paths: → SCR-DATA-03 (re-collect/extend), → SCR-ANLY-02 (use this Dataset in a new Analysis Run). Backend modules: Collection Engine, Reproducibility. Primary API: `getDataset`, `listCollectionRunsForDataset`. Core entities: Dataset, CollectionRun. AI interactions: none. Error/empty states: interrupted run → resumable-state indicator with a "resume" action, consistent with SCR-DATA-01.

**SCR-DATA-03 — New Collection Run**
Purpose: configure and launch a Collection Run (roster subset, date window). Primary users: PI, Researcher. Inputs: roster selection, date window. Outputs: a running CollectionRun. Navigation entry: from SCR-DATA-01 or SCR-DATA-02. Exit paths: → SCR-DATA-02 (run detail/progress) on submit. Backend modules: Collection Engine, Reproducibility. Primary API: `startCollectionRun`. Core entities: CollectionRun, Dataset. AI interactions: none. Error/empty states: quota-exceeded or invalid roster entry surfaced inline, not as a silent failure — this is a direct product-level expression of the existing engine's own quota/error-handling discipline.

**SCR-ANLY-01 — Analyses List**
Purpose: list Analysis Runs within a Project; entry point to configure a new one. Primary users: PI, Researcher, Analyst (execute); Viewer (view only). Inputs: none. Outputs: selection → Analysis Run Detail. Navigation entry: NAV-06. Exit paths: → SCR-ANLY-02 (new), → SCR-ANLY-03 (select existing). Backend modules: Analysis Engine, Reproducibility. Primary API: `listAnalysisRuns`. Core entities: AnalysisRun, AnalysisType. AI interactions: none. Error/empty states: no Analyses yet → CTA to SCR-ANLY-02, gated on at least one Dataset existing (else redirected toward SCR-DATA-03 first).

**SCR-ANLY-02 — New Analysis Run**
Purpose: select a Dataset, choose analysis type(s) from the active VerticalTemplate's available set (§3.3, §5), and configure parameters. Primary users: PI, Researcher, Analyst. Inputs: Dataset selection, AnalysisType selection(s), parameters. Outputs: a running AnalysisRun. Navigation entry: from SCR-ANLY-01 or SCR-DATA-02. Exit paths: → SCR-ANLY-03 (run detail/progress) on submit. Backend modules: Analysis Engine, Reproducibility. Primary API: `listAnalysisTypes` (template-scoped), `startAnalysisRun`. Core entities: AnalysisRun, AnalysisType, VerticalTemplate. AI interactions: none at configuration time. Error/empty states: invalid parameter combination surfaced inline before submit, not after a failed run.

**SCR-ANLY-03 — Analysis Run Detail**
Purpose: view results (topic assignments, sentiment, market correlation as applicable) and their visualizations; entry point to AI-assisted interpretation. Primary users: all Project-assigned roles (view); PI/Researcher/Analyst (re-run/iterate). Inputs: none (view) / re-run trigger. Outputs: none directly — the interpretation trigger opens SCR-ANLY-04. Navigation entry: drill-down from SCR-ANLY-01. Exit paths: → SCR-ANLY-04 (AI interpretation), → SCR-ANLY-02 (iterate — the §7.2 loop, pre-filled with this run's parameters), → SCR-RPT-02 (add to a Report). Backend modules: Analysis Engine, Reproducibility. Primary API: `getAnalysisRunResult`. Core entities: AnalysisRun, its result payload. AI interactions: entry point only (trigger, not inline). Error/empty states: a run still in progress shows live/polling status, not a blank results page; a failed run shows the failure reason with a direct re-run action pre-filled from the failed attempt's parameters.

**SCR-ANLY-04 — AI Interpretation Panel**
Purpose: v1.x — request and display a single-shot natural-language explanation of the parent AnalysisRun's results, bound by **AIG-001** (§9.4). Primary users: any role with view access to the parent AnalysisRun. Inputs: interpretation request (v1.x: fixed trigger; v2: free-text question, scoped to the same AnalysisRun). Outputs: interpretation text plus explicit citation of the source AnalysisRun ID and manifest hash (mandatory per AIG-001, not optional UI chrome). Navigation entry: triggered from SCR-ANLY-03; embedded panel, not a standalone nav destination. Exit paths: → SCR-ANLY-02 (iterate, if the interpretation surfaces a concern — the §7.2 loop's actual UI trigger point), → back to SCR-ANLY-03. Backend modules: AI Interpretation Layer, Analysis Engine (source of truth), Reproducibility (manifest citation). Primary API: `requestInterpretation(analysisRunId, scope)`. Core entities: InterpretationRecord (new entity — always foreign-keyed to one immutable AnalysisRun manifest, never to a live/mutable query — this is AIG-001 made concrete in the data model, previewed here for Database Concept). AI interactions: this screen's entire purpose. Error/empty states: model/service unavailable → explicit failure state, never a silently degraded or fabricated-looking answer; interpretation explicitly labeled as AI-generated with its source citation visible at all times, not just on hover or in a tooltip.

**SCR-RPT-01 — Reports List**
Purpose: list Reports within a Project; entry point to build a new one. Primary users: PI, Researcher (edit); Analyst, Viewer (view). Inputs: none. Outputs: selection → Report Detail. Navigation entry: NAV-07. Exit paths: → SCR-RPT-02 (new or select). Backend modules: Reporting & Publication Engine. Primary API: `listReportsForProject`. Core entities: Report. AI interactions: none. Error/empty states: no Reports yet → CTA to SCR-RPT-02, gated on at least one completed AnalysisRun.

**SCR-RPT-02 — Report Builder / Detail**
Purpose: assemble one or more AnalysisRun results into manuscript-ready tables and a report layout. Primary users: PI, Researcher. Inputs: AnalysisRun selection(s), table/layout template, author/citation metadata. Outputs: a Report object, viewable before export. Navigation entry: from SCR-RPT-01 or directly from SCR-ANLY-03 ("add to Report"). Exit paths: → SCR-RPT-03 (export). Backend modules: Reporting & Publication Engine, Analysis Engine (source data). Primary API: `generateReport`, `getReportStatus`. Core entities: Report, AnalysisRun (referenced). AI interactions: none — deliberately; report content is assembled from AnalysisRun output and (if included) an InterpretationRecord's already-generated, already-citable text, never generated fresh at export time, which would violate AIG-001's reproducibility clause. Error/empty states: a referenced AnalysisRun that's since failed/been deleted is flagged inline, not silently dropped from the Report.

**SCR-RPT-03 — Export**
Purpose: render a Report to PDF (v1) or Word (v1.x). Primary users: PI, Researcher. Inputs: format selection. Outputs: downloadable file. Navigation entry: from SCR-RPT-02. Exit paths: → SCR-RPT-01 (back to list) or stays on SCR-RPT-02. Backend modules: Reporting & Publication Engine. Primary API: `exportReport(format)`. Core entities: Report. AI interactions: none. Error/empty states: render failure surfaced with retry, not a silent download of nothing.

**SCR-SET-01 — Roster & Configuration**
Purpose: manage the Project's channel/creator roster and template-derived configuration. Primary users: PI only. Inputs: roster edits, config changes. Outputs: updated Project configuration. Navigation entry: NAV-08a. Exit paths: → SCR-PROJ-02. Backend modules: Collection Engine, Identity & Access. Primary API: `updateProjectRoster`, `updateProjectConfig`. Core entities: Project, VerticalTemplate (reference). AI interactions: none. Error/empty states: invalid roster entry (e.g., unresolvable channel) surfaced inline at save time.

**SCR-SET-02 — Members & Roles**
Purpose: invite/remove Project members and assign roles (§6). Primary users: PI only. Inputs: member invite, role assignment. Outputs: updated Membership records. Navigation entry: NAV-08b. Exit paths: → SCR-PROJ-02. Backend modules: Identity & Access. Primary API: `listProjectMembers`, `assignRole`, `inviteMember`. Core entities: Membership, User. AI interactions: none. Error/empty states: inviting an email already at seat capacity (v1.x) surfaced with a link to SCR-ADM-01, not a dead end.

**SCR-XPRJ-01 — Cross-Project Comparison** *(v1.x)*
Purpose: compare AnalysisRun results across multiple Projects the user has access to. Primary users: PI (own Projects), Lab Manager (group), Institution Owner (all). Inputs: Project selection (2+), comparable AnalysisType. Outputs: comparative view. Navigation entry: NAV-10. Exit paths: → SCR-PROJ-02 (drill into one Project), → SCR-RPT-02 (export a comparison as a Report — extends Report's AnalysisRun references to span Projects, noted for Database Concept). Backend modules: Analysis Engine, Reporting. Primary API: `compareAnalysisRuns(projectIds, analysisType)`. Core entities: Project (multiple), AnalysisRun (multiple). AI interactions: none in v1.x; a natural v2 extension of AIG-001-bound interpretation, not built now. Error/empty states: fewer than 2 accessible Projects → explains the feature rather than showing a broken control.

**SCR-HIST-01 — Research History**
Purpose: chronological view of all Collection and Analysis runs the user has access to, across Projects — the user-facing surface of the Reproducibility & Experiment Tracking module, which otherwise has no screen of its own (§8.3). Primary users: PI, Lab Manager, Institution Owner. Inputs: filters (date, Project, run type). Outputs: none (read view) / drill-down. Navigation entry: NAV-11. Exit paths: → SCR-DATA-02, → SCR-ANLY-03 (jump to the specific run). Backend modules: Reproducibility & Experiment Tracking. Primary API: `listRunHistory`. Core entities: CollectionRun, AnalysisRun (manifest-level, cross-Project). AI interactions: none. Error/empty states: no history yet → same first-run guidance as SCR-DASH-01, not a separate empty-state design.

**SCR-ADM-01 — Billing & Seats** *(v1.x)*
Purpose: manage tenant subscription and seat allocation. Primary users: Institution Owner/Admin. Inputs: plan/seat changes. Outputs: updated subscription state. Navigation entry: NAV-12a. Exit paths: → SCR-ADM-02. Backend modules: Billing & Licensing, Identity & Access. Primary API: `getSubscriptionStatus`, `updateSeats`. Core entities: Tenant, Subscription (new entity, previewed for Database Concept). AI interactions: none. Error/empty states: payment failure surfaced with a clear remediation path, never a silent seat downgrade.

**SCR-ADM-02 — Tenant Members & Roles** *(v1.x)*
Purpose: manage tenant-wide membership and Institution-level role assignment, distinct from per-Project SCR-SET-02. Primary users: Institution Owner/Admin. Inputs: member invite, role assignment. Outputs: updated Membership records at tenant scope. Navigation entry: NAV-12b. Exit paths: → SCR-ADM-01. Backend modules: Identity & Access. Primary API: `listTenantMembers`, `assignTenantRole`. Core entities: Membership (tenant-scoped), User. AI interactions: none. Error/empty states: same seat-capacity pattern as SCR-SET-02.

**SCR-ACCT-01 — Account Settings**
Purpose: personal profile, password/auth settings, notification preferences. Primary users: all authenticated roles. Inputs: profile edits. Outputs: updated User record. Navigation entry: NAV-13. Exit paths: none fixed (personal utility screen). Backend modules: Identity & Access. Primary API: `getCurrentUser`, `updateUser`. Core entities: User. AI interactions: none. Error/empty states: standard validation only.

### 9.4 AIG-001 — AI Interpretation Guardrail (formal)

| Field | Value |
|---|---|
| ID | AIG-001 |
| Title | AI Interpretation Layer is Never the Source of Truth |
| Status | Formalized, binding on all future deliverables that touch AI (AI Integration Strategy, Backend Architecture, Database Concept) |
| Applies to | AI Interpretation Layer (§8.5), SCR-ANLY-04, and any future extension of it (conversational Research Assistant, v2) |

**Rule 1 — Never the source of truth.** The AI Interpretation Layer may only explain, summarize, or contextualize output that the Analysis Engine has already produced and persisted. It must never compute, adjust, or supply a result that a Report or a downstream screen treats as data. Concretely: `InterpretationRecord` is additive commentary attached to an `AnalysisRun`; it is never itself queried as if it were analysis output, and SCR-RPT-02 explicitly does not allow an interpretation to substitute for a table or figure — it may only accompany one.

**Rule 2 — Traceable and reproducible.** Every `InterpretationRecord` must store, immutably, the exact `AnalysisRun` ID and its Reproducibility & Experiment Tracking manifest hash (§8.3) it was generated from, plus the interpretation model/version and prompt template used. "Reproducible from the same project state" means: given the same `AnalysisRun` manifest and the same model/prompt version, regenerating the interpretation is a defined, repeatable operation the product actually exposes (a "regenerate" action on SCR-ANLY-04), not merely a theoretical property. If the underlying `AnalysisRun` is ever re-run with different parameters, that produces a *new* `AnalysisRun` and a *new* `InterpretationRecord` — old interpretations are never silently re-pointed at new data.

**Why this is architectural, not just a UI copy rule:** it constrains the data model (`InterpretationRecord` must be a first-class, immutably-linked entity — previewed in §9.3, formalized in Database Concept), the API (`requestInterpretation` must accept and echo back the manifest reference, not just the AnalysisRun ID, so the response is self-describing), and the AI Integration Strategy deliverable (whatever model/provider is chosen must support deterministic-enough behavior, or at minimum versioned prompt/model pinning, for "reproducible" to be a true claim rather than aspirational copy). Nothing in Backend Architecture, Database Concept, or API Architecture should be designed in a way that makes AIG-001 unenforceable later.

---

## 10. Database Concept

Treated as the central architectural artifact, per instruction — this is the layer API Architecture, Backend Architecture, Frontend Architecture, and eventual implementation all derive from, not a diagram produced alongside them. Conceptual level throughout; no SQL, no storage-engine choices.

### 10.0 A design tension surfaced and resolved before the entity list

This turn's instructions state two things that, read literally together, conflict with what §9.4 (AIG-001) established: AIG-001 said an interpretation "may only accompany" a table or figure, never substitute for one — implying a Report cites raw `AnalysisRun` output directly for its tables/figures. This turn instructs "every Report references immutable InterpretationRecords rather than raw analyses." Taken literally, that would mean AI-generated commentary is the *only* thing a Report can cite, which would put AI in the citation path for every table and figure — the opposite of AIG-001's intent.

The resolution, applied below rather than silently picked: **`InterpretationRecord` is generalized from "AI-generated commentary" to the general concept of an immutable, versioned, citable unit** — every distinct thing a Report can cite is one, carrying a `kind` field:

- `kind: raw_result_snapshot` — a frozen snapshot of a specific table/figure/statistic taken from one `AnalysisRun` at cite-time. No AI involved. This is what most Report citations will actually be.
- `kind: ai_generated` — bound by the full AIG-001 rule set (exact `AnalysisRun` + manifest hash, model/prompt version, regenerable). This is what SCR-ANLY-04 produces.

This satisfies the letter of this turn's instruction (Report only ever references `InterpretationRecord` entities, never a live `AnalysisRun` pointer) while *strengthening*, not violating, AIG-001: raw citations become frozen and immutable too (a genuine reproducibility improvement — a Report's cited table can no longer silently drift even in principle), and AI-generated content stays clearly, structurally distinguished by `kind`, never presented as data. AIG-001 itself is unchanged; this is a data-model mechanism that makes it easier to enforce, not a policy change. §9.3's SCR-RPT-02 description ("assembled from AnalysisRun output and, if included, an InterpretationRecord's text") should be read as superseded by this section rather than edited retroactively — noted here so the two sections don't silently disagree.

### 10.1 Entity specifications

**Tenant**
- Purpose: the billing and access boundary — one university department, research center, or individual researcher account.
- Owner Module: Identity & Access.
- Relationships: owns many `User` (via `TenantMembership`); owns zero-or-one `Subscription`; owns many `Project` (indirectly, through `TenantMembership` → `Project` ownership — see Project below for the actual aggregate boundary).
- Lifecycle: created at sign-up (SCR-AUTH-02); active indefinitely; suspendable (non-payment) or closable (account deletion) — both are state transitions, not deletions, pending a data-retention policy (flagged as open, belongs to Deployment Architecture / a future compliance pass).
- Immutable or Mutable: Mutable (name, plan, settings change over time).
- Versioning Strategy: none — Tenant is a slowly-changing configuration entity, not a versioned research artifact.
- Audit Requirements: tenant-level changes (plan, ownership transfer, suspension) are logged, but — per this turn's instruction that Project owns audit history — tenant-level audit is a separate, smaller trail from the Project-scoped one; not nested under any Project.
- Primary API Consumers: SCR-AUTH-02, SCR-ADM-01, SCR-ADM-02, Institution Admin nav (NAV-12).

**User**
- Purpose: an individual human identity, potentially belonging to multiple Tenants (e.g., a researcher consulting for two institutions).
- Owner Module: Identity & Access.
- Relationships: many-to-many with `Tenant` via `TenantMembership`; many-to-many with `Project` via `ProjectMembership`.
- Lifecycle: created at sign-up or invitation acceptance; deactivable, not hard-deleted while owning any `Project` (ownership must be transferred first — a rule for Backend Architecture to enforce, not just a UI nicety).
- Immutable or Mutable: Mutable (profile fields).
- Versioning Strategy: none.
- Audit Requirements: login events and role/permission-affecting changes are audited at the `TenantMembership`/`ProjectMembership` level (below), not on `User` itself.
- Primary API Consumers: SCR-AUTH-01, SCR-ACCT-01, all screens indirectly (current-user context).

**TenantMembership**
- Purpose: binds a `User` to a `Tenant` with a tenant-scoped role (Institution Owner/Admin, Lab/Department Manager — §6).
- Owner Module: Identity & Access.
- Relationships: belongs to exactly one `Tenant` and one `User`.
- Lifecycle: created on invitation acceptance; revocable.
- Immutable or Mutable: Mutable (role can change).
- Versioning Strategy: none directly, but every role change is an `AuditLogEntry` (tenant-scoped, per Tenant's audit note above).
- Audit Requirements: every creation, role change, and revocation is audited.
- Primary API Consumers: SCR-ADM-02.

**ProjectMembership**
- Purpose: binds a `User` to a `Project` with a project-scoped role (PI, Researcher, Analyst, Viewer, External Collaborator — §6).
- Owner Module: Identity & Access, but logically owned within the `Project` aggregate (see §10.2).
- Relationships: belongs to exactly one `Project` and one `User`.
- Lifecycle: created on invitation acceptance (or automatically for the PI at Project creation); revocable; time-limited for External Collaborator (§6).
- Immutable or Mutable: Mutable (role can change; expiry date for External Collaborator).
- Versioning Strategy: none directly — changes are audit events.
- Audit Requirements: every creation, role change, and revocation is a `Project`-scoped `AuditLogEntry` — this is the first entity where "Project owns audit history" becomes concrete.
- Primary API Consumers: SCR-SET-02.

**VerticalTemplate**
- Purpose: the extensibility mechanism DAD-001 depends on (§5) — supplies a Project's default analysis types, vocabulary, and report layout at creation time. "Financial Influencer Study" is the v1 instance.
- Owner Module: **Open — no single module in §8 cleanly owns this.** It configures Collection Engine (roster defaults), Analysis Engine (default `AnalysisType` set), and Reporting (default layout) simultaneously. Flagged honestly rather than forced: Backend Architecture should decide whether this becomes its own small "Catalog" service or is stewarded by Analysis Engine as primus inter pares. Not resolved here.
- Relationships: referenced by many `Project` (a template is reused across Projects, never owned by one); references many `AnalysisType` (its default set).
- Lifecycle: platform-managed, not user-created in v1 (users select, don't author, templates); versionable in principle once multiple institutions want customized templates (v2+).
- Immutable or Mutable: Mutable at the platform-management level; effectively immutable from a single Project's point of view once selected (a Project doesn't inherit later template edits — see Versioning Strategy).
- Versioning Strategy: **must be versioned, not just editable in place.** A `Project` created from "Financial Influencer Study v1" must keep behaving as v1 even if the template is later revised to v2 — otherwise reproducibility (the Vision's core promise) breaks for every existing Project the moment a template changes. Each `Project` stores the specific `VerticalTemplate` version it was instantiated from.
- Audit Requirements: template revisions are audited at the platform level, not per-Project.
- Primary API Consumers: SCR-AUTH-02/Project creation flow, SCR-ANLY-02 (`listAnalysisTypes`, template-scoped).

**AnalysisType**
- Purpose: catalog definition of one pluggable analysis kind (topic modeling, sentiment, market correlation, future types).
- Owner Module: Analysis Engine.
- Relationships: referenced by `VerticalTemplate` (as a default) and by `AnalysisRun` (as the type actually executed).
- Lifecycle: platform-managed; new types added as the Analysis Engine gains capabilities (this is the concrete mechanism behind §5's "pluggable analysis types, not pipeline stages" claim).
- Immutable or Mutable: Mutable at the catalog level (a type's parameter schema can evolve).
- Versioning Strategy: versioned, same reasoning as `VerticalTemplate` — an `AnalysisRun` records which `AnalysisType` version produced it, so re-deriving old results means running the same version, not whatever the type has since become.
- Audit Requirements: catalog changes audited at the platform level.
- Primary API Consumers: SCR-ANLY-02 (`listAnalysisTypes`).

**Project — the root aggregate**
- Purpose: the unit a researcher thinks in ("my study"); owns everything beneath it, per this turn's explicit instruction.
- Owner Module: no single §8 module — Project itself is the aggregate root Identity & Access, Collection Engine, and Analysis Engine all operate within; if forced to name a stewarding module, Identity & Access owns the `Project` record itself (creation, membership, archival state), while every other module owns what it contributes *inside* the aggregate.
- Relationships: owns many `Dataset`, many `AnalysisRun`, many `InterpretationRecord` (transitively, via `AnalysisRun`), many `Report`, many `Export` (transitively, via `Report`), many `ProjectMembership`, many `AuditLogEntry`; references exactly one `VerticalTemplate` (pinned version, per above); belongs to exactly one `Tenant`.
- Lifecycle: created (SCR-PROJ-01) → active → archived (SCR-PROJ-03/04, §7.2 stage 7) → (no hard-delete state in v1; deletion, if ever offered, is a v2+ policy question given the reproducibility promise archival exists to serve).
- Immutable or Mutable: Mutable while active (roster, config); the `active → archived` transition is a one-way state change that then freezes everything inside the aggregate — archival is enforced at the aggregate root, not per-child-entity, which is precisely why Project must be the root aggregate rather than a loose grouping.
- Versioning Strategy: not versioned itself (it's the container), but its `VerticalTemplate` reference is pinned (see above) — this is how a Project stays reproducible even as the platform's templates evolve.
- Audit Requirements: **the primary audit boundary of the platform**, per this turn's instruction. Every state-changing action on anything inside the aggregate (`Dataset`, `CollectionRun`, `AnalysisRun`, `InterpretationRecord`, `Report`, `Export`, `ProjectMembership`) produces a `Project`-scoped `AuditLogEntry`.
- Primary API Consumers: SCR-PROJ-01, SCR-PROJ-02, SCR-PROJ-03, NAV-03.

**Dataset**
- Purpose: a named collection container within a Project (e.g., "YouTube comments, Analyst Roster A, Jan–Jun 2026").
- Owner Module: Collection Engine.
- Relationships: belongs to exactly one `Project`; owns many `CollectionRun` (its version/state history, per §2.3 — not a separate IA node, but a real owned entity here).
- Lifecycle: created on first collection configuration (SCR-DATA-03); extended by subsequent `CollectionRun`s against the same roster/window scope; never deleted while any `AnalysisRun` references it (referential integrity constraint for Backend Architecture to enforce).
- Immutable or Mutable: the `Dataset` record itself (name, description) is mutable; its *content* is not directly mutable — content only changes by adding a new `CollectionRun`, never by editing existing collected data in place.
- Versioning Strategy: implicit, via its `CollectionRun` history — see below.
- Audit Requirements: `Project`-scoped `AuditLogEntry` on creation and on each new `CollectionRun`.
- Primary API Consumers: SCR-DATA-01, SCR-DATA-02.

**CollectionRun**
- Purpose: one execution of the Collection Engine against a `Dataset` — the "version/state" §2.3 describes, and the concrete reproducibility anchor an `AnalysisRun` pins to (see `AnalysisRun` below).
- Owner Module: Collection Engine.
- Relationships: belongs to exactly one `Dataset`; referenced by many `AnalysisRun` (as the pinned input state).
- Lifecycle: `queued → running → completed | failed`; resumable from a `failed`/interrupted state (existing engine guarantee, carried into the product per §7.2 stage 2).
- Immutable or Mutable: **Immutable once `completed`.** This is what makes it a valid reproducibility anchor — a completed `CollectionRun`'s resulting data snapshot never changes retroactively.
- Versioning Strategy: each `CollectionRun` is itself an immutable version; no further versioning needed.
- Audit Requirements: `Project`-scoped `AuditLogEntry` on start, completion, and failure.
- Primary API Consumers: SCR-DATA-02, SCR-DATA-03, SCR-HIST-01.

**AnalysisRun**
- Purpose: one execution of a specific `AnalysisType` against a specific `CollectionRun`'s data state.
- Owner Module: Analysis Engine.
- Relationships: belongs to exactly one `Project`; references exactly one `CollectionRun` (**not** a loosely-scoped `Dataset` — pinning to a specific `CollectionRun` is the refinement flagged in §9's original module spec (§8.2 said "a Dataset reference"); tightened here for true reproducibility, since a `Dataset` can grow across multiple `CollectionRun`s and an `AnalysisRun` must pin to one immutable state, not a moving target); references exactly one `AnalysisType` (pinned version); owns many `InterpretationRecord`.
- Lifecycle: `queued → running → completed | failed`; re-run creates a new `AnalysisRun`, never mutates an existing one (§7.2's iteration loop is modeled as "create new `AnalysisRun`," not "edit existing one" — this is what makes old `InterpretationRecord`s stay validly attached to the exact state they were generated from, per AIG-001 Rule 2).
- Immutable or Mutable: **Immutable once `completed`** — same reasoning as `CollectionRun`, and the direct enabler of AIG-001's manifest-hash citation requirement.
- Versioning Strategy: each `AnalysisRun` is itself an immutable version, keyed by its manifest hash (Reproducibility & Experiment Tracking, §8.3).
- Audit Requirements: `Project`-scoped `AuditLogEntry` on start, completion, and failure.
- Primary API Consumers: SCR-ANLY-01, SCR-ANLY-02, SCR-ANLY-03, SCR-HIST-01.

**InterpretationRecord**
- Purpose: the immutable, versioned, citable unit every `Report` references (§10.0) — either a frozen raw-result snapshot or an AI-generated interpretation, discriminated by `kind`.
- Owner Module: AI Interpretation Layer (for `kind: ai_generated`); Analysis Engine (for `kind: raw_result_snapshot` — it's the module producing the thing being snapshotted, even though the snapshot mechanism itself is shared infrastructure).
- Relationships: **belongs to exactly one `AnalysisRun`, always** (both `kind`s — this is AIG-001 Rule 2 made structural, not just true for the AI case); referenced by many `Report` (a `Report` can cite several).
- Lifecycle: created at cite-time (`raw_result_snapshot`, whenever a result is added to a Report) or at interpretation-request time (`ai_generated`, SCR-ANLY-04); never updated after creation.
- Immutable or Mutable: **Immutable — non-negotiable, per this turn's explicit instruction and AIG-001 Rule 2.** No API path may update an existing `InterpretationRecord`; "regenerate" (SCR-ANLY-04) always creates a new one.
- Versioning Strategy: each record IS a version — there is no separate versioning layer on top, by design (versioning something already-immutable would be redundant).
- Audit Requirements: `Project`-scoped `AuditLogEntry` on creation only (there is nothing else to audit — no updates or deletions are possible in v1).
- Primary API Consumers: SCR-ANLY-04 (`requestInterpretation`), SCR-RPT-02 (citation selection).

**Report**
- Purpose: an assembled, citable document referencing one or more `InterpretationRecord`s — per this turn's instruction, never a raw `AnalysisRun` pointer directly.
- Owner Module: Reporting & Publication Engine.
- Relationships: belongs to exactly one `Project` (or, for `SCR-XPRJ-01` in v1.x, references `InterpretationRecord`s across multiple `Project`s the user can access — flagged as the one place the "belongs to exactly one Project" rule needs an explicit v1.x exception, not silently glossed over); references many `InterpretationRecord`.
- Lifecycle: `draft → finalized`; a finalized `Report` is what `Export` renders from; editable while in `draft`.
- Immutable or Mutable: Mutable while `draft`; **immutable once `finalized`** (the state a citable, exportable document needs to be trustworthy).
- Versioning Strategy: editing a `finalized` Report creates a new version (`Report v2`) rather than mutating the finalized one — preserves the same reproducibility guarantee `InterpretationRecord` and `AnalysisRun` already carry, applied one layer up.
- Audit Requirements: `Project`-scoped `AuditLogEntry` on creation, finalization, and each new version.
- Primary API Consumers: SCR-RPT-01, SCR-RPT-02.

**Export**
- Purpose: one rendered artifact (PDF or Word) of a specific, finalized `Report` version.
- Owner Module: Reporting & Publication Engine.
- Relationships: belongs to exactly one `Report` (specifically, one `Report` *version*, per above).
- Lifecycle: generated on demand (SCR-RPT-03); once generated, permanent (a download link to a stored artifact) until the owning `Project` is archived or the platform's retention policy (open item, §10.1 Tenant) removes it.
- Immutable or Mutable: **Immutable** — an `Export` is a rendering of a specific, already-immutable `Report` version; there's nothing to mutate.
- Versioning Strategy: none needed — immutable by construction; a new export of an updated Report is a new `Export` record tied to the new `Report` version, not an update to the old one.
- Audit Requirements: `Project`-scoped `AuditLogEntry` on generation.
- Primary API Consumers: SCR-RPT-03.

**Subscription** *(v1.x)*
- Purpose: a Tenant's billing/plan state.
- Owner Module: Billing & Licensing.
- Relationships: belongs to exactly one `Tenant`.
- Lifecycle: created at plan selection; transitions on payment events (webhook-driven, per §8.7); cancelable.
- Immutable or Mutable: Mutable (plan, seat count, status).
- Versioning Strategy: none — current-state entity; history lives in the payment processor's own records, not duplicated here.
- Audit Requirements: Tenant-scoped audit (not Project-scoped — a deliberate exception, consistent with Tenant's own audit note above).
- Primary API Consumers: SCR-ADM-01.

**AuditLogEntry**
- Purpose: the audit trail itself — per this turn's instruction, primarily owned by `Project` as the root aggregate, with a smaller, separate `Tenant`-scoped trail for tenant-level events (billing, tenant membership) that fall outside any single Project's boundary.
- Owner Module: cross-cutting — written by whichever module performs the audited action; not "owned" for business logic the way other entities are.
- Relationships: belongs to exactly one `Project` (primary case) or exactly one `Tenant` (the tenant-level exception, above) — never both.
- Lifecycle: append-only; created, never updated.
- Immutable or Mutable: **Immutable by definition** — an audit log that could be edited isn't an audit log.
- Versioning Strategy: not applicable (append-only log entries aren't versioned objects).
- Audit Requirements: n/a — this entity IS the audit requirement for everything else.
- Primary API Consumers: none directly in v1's Screen Inventory (no dedicated audit-log screen was specified in §9.3) — flagged as a gap: a v1.x "Project Activity Log" screen is a natural, currently-unlisted addition Navigation Structure/Screen Inventory should absorb in a future revision, not designed here.

### 10.2 What this settles for later deliverables

- **API Architecture:** every mutating endpoint maps to exactly one entity's lifecycle transition above (e.g., `startAnalysisRun` → `AnalysisRun: queued`); no endpoint should be designed that mutates an entity marked immutable-once-complete.
- **Backend Architecture:** the `Project`-as-aggregate-root boundary is a strong hint toward a service/module boundary that loads and authorizes at the Project level once, not per-child-entity — worth carrying forward explicitly when that deliverable is designed.
- **Frontend Architecture:** immutable entities (`CollectionRun`, `AnalysisRun`, `InterpretationRecord`, finalized `Report`, `Export`) never need client-side optimistic-update/conflict-resolution logic — only `draft` `Report`, `Dataset` metadata, `Project` config, and membership entities do. That's a real simplification worth stating once here rather than rediscovering per-screen later.
- **Open items carried forward, not resolved here:** `VerticalTemplate`'s owning module (§10.1); data-retention policy for closed Tenants/archived Projects (§10.1 Tenant); a Project Activity Log screen for `AuditLogEntry` (§10.1 AuditLogEntry). None block proceeding.

---

## 11. API Architecture

Treated as the constitutional contract of the platform, per instruction: this section defines what each internal service *promises* — its commands, queries, events, and the guarantees around them — before a single REST path is written. REST endpoints (§11.3) are a derived artifact of the contracts (§11.2), not the other way around.

### 11.1 A numbering note, flagged rather than silently resolved

This turn asks to formalize **AIG-003**. No **AIG-002** has been defined anywhere in this document — only AIG-001 (§9.4) exists so far. Rather than inventing a plausible-sounding AIG-002 to fill the gap or silently renumbering AIG-003 to AIG-002, this is stated openly: AIG-002 is currently an unassigned ID. If it corresponds to a guardrail from outside this document's history, it should be supplied explicitly; otherwise the register below simply has a gap between 001 and 003, which is honest and traceable rather than smoothed over.

### 11.2 Service contracts

Nine services. Eight are internal, never directly reachable — the ninth, the API Gateway, is the single external surface (§4.1), reconfirmed and made contractually explicit here.

**Identity Service**
- Purpose: authentication, authorization, and lifecycle for Tenant, User, TenantMembership, ProjectMembership, and the Project record itself (not Project's contents — see Collection/Analysis/Reporting below).
- Consumers: API Gateway; every other internal service (authorization checks).
- Commands: `CreateTenant`, `CreateProject`, `InviteMember`, `AssignRole`, `RevokeMembership`, `UpdateUserProfile`, `ArchiveProject`.
- Queries: `GetCurrentUser`, `ListProjects`, `GetProject`, `ListProjectMembers`, `ListTenantMembers`, `CheckAuthorization` (the primitive every other service calls rather than re-implementing role logic).
- Events: `ProjectCreated`, `ProjectArchived`, `MembershipGranted`, `MembershipRevoked`, `RoleChanged`.
- Authentication: issues and validates session tokens and Service Account tokens (§6) — the identity root; nothing else authenticates *against* it, everything else *trusts* it.
- Authorization: the canonical decision point for the two-level Tenant/Project role model (§6/§6.1); other services call `CheckAuthorization` rather than duplicating logic.
- Idempotency: `CreateTenant`/`CreateProject` require a client idempotency key; `InviteMember` is naturally idempotent (re-inviting is a no-op).
- Sync vs Async: synchronous — authorization sits on the critical path of every request.
- Primary entities: Tenant, User, TenantMembership, ProjectMembership, Project (record only).
- Dependencies: none — foundational.

**Reproducibility Service**
- Purpose: checkpointing and manifest-hash generation for Collection and Analysis runs — the infrastructure AIG-001 and AIG-003 both structurally depend on. Not directly user-facing beyond SCR-HIST-01.
- Consumers: Collection Service, Analysis Service (internal callers); Gateway, read-only, for `ListRunHistory`.
- Commands: `RecordCheckpoint` — internal-only, never externally callable.
- Queries: `GetManifest(runId)`, `ListRunHistory` (cross-Project, powers SCR-HIST-01).
- Events: none published — consumes `CollectionRunCompleted`/`AnalysisRunCompleted` to finalize manifests rather than emitting its own.
- Authentication: internal service-to-service for `RecordCheckpoint`; Gateway-delegated for `ListRunHistory`.
- Authorization: `ListRunHistory` is Project-membership-scoped via `CheckAuthorization`.
- Idempotency: `RecordCheckpoint` is naturally idempotent (append-only, keyed by run + step).
- Sync vs Async: synchronous with respect to the run being checkpointed (resumability requires it), invisible to the end user otherwise.
- Primary entities: CollectionRun/AnalysisRun manifest state (a facet of those entities, not a separate one — confirmed, not redundantly introduced).
- Dependencies: none — foundational, alongside Identity Service.

**Collection Service**
- Purpose: run and track Collection Runs against a Dataset.
- Consumers: API Gateway; Analysis Service (reads a `completed` CollectionRun when pinning an AnalysisRun).
- Commands: `CreateDataset`, `StartCollectionRun`, `ResumeCollectionRun`.
- Queries: `GetDataset`, `ListDatasets`, `ListCollectionRunsForDataset`, `GetCollectionRun`.
- Events: `CollectionRunCompleted`, `CollectionRunFailed`.
- Authentication: Gateway-delegated to Identity Service.
- Authorization: PI/Researcher may `StartCollectionRun` (§6.1); Analyst/Viewer query-only.
- Idempotency: `StartCollectionRun` requires an idempotency key — a duplicate submission must not double-collect or double-spend quota.
- Sync vs Async: **asynchronous** — a real, quota-bounded external collection can take minutes to hours; returns a `CollectionRun` in `queued` state immediately.
- Primary entities: Dataset, CollectionRun.
- Dependencies: Identity Service (authz); Reproducibility Service (checkpointing).

**Analysis Service**
- Purpose: run a pluggable AnalysisType against a specific, pinned CollectionRun.
- Consumers: API Gateway; Reporting Service (reads completed output for `raw_result_snapshot` citations); AI Interpretation Service (reads completed output as the thing being explained).
- Commands: `StartAnalysisRun(collectionRunId, analysisTypeId, params)` — pinned to a `CollectionRun` ID, never a loose `Dataset` reference, enforcing §10.1's tightened reproducibility rule at the contract level.
- Queries: `ListAnalysisTypes` (template-scoped), `GetAnalysisRun`, `ListAnalysisRuns`.
- Events: `AnalysisRunCompleted`, `AnalysisRunFailed`.
- Authentication: Gateway-delegated.
- Authorization: PI/Researcher/Analyst may `StartAnalysisRun` (§6.1); Viewer query-only.
- Idempotency: `StartAnalysisRun` requires an idempotency key.
- Sync vs Async: **asynchronous** — compute-bound (topic modeling, sentiment).
- Primary entities: AnalysisRun, AnalysisType.
- Dependencies: Collection Service (reads a `completed` CollectionRun); Reproducibility Service (checkpointing, manifest-hash minting — this is *where* the hash AIG-001/AIG-003 cite actually originates); Identity Service (authz).

**AI Interpretation Service**
- Purpose: produce `InterpretationRecord`s of `kind: ai_generated`, bound by AIG-001 and AIG-003.
- Consumers: API Gateway (SCR-ANLY-04 only).
- Commands: `RequestInterpretation(analysisRunId, scope)` — the **only** command. No `UpdateInterpretation`, no `DeleteInterpretation` exists in this contract, structurally enforcing immutability rather than relying on convention.
- Queries: `GetInterpretation(id)`, `ListInterpretationsForAnalysisRun`.
- Events: `InterpretationCreated`.
- Authentication: Gateway-delegated.
- Authorization: any role with view access to the parent AnalysisRun (§6.1).
- Idempotency: **deliberately not idempotent** — see AIG-003 (§11.4); two identical requests produce two separate, separately-provenanced records.
- Sync vs Async: synchronous in the v1.x single-shot case (seconds-scale); Backend Architecture decides whether latency later pushes this async — not fixed here.
- Primary entities: InterpretationRecord (`kind: ai_generated` only).
- Dependencies: Analysis Service (reads a `completed` AnalysisRun — never a running or failed one); Reproducibility Service (reads the manifest hash to stamp onto every new record).

**Reporting Service**
- Purpose: assemble InterpretationRecords (both `kind`s) into Reports; render Exports.
- Consumers: API Gateway (SCR-RPT-*). Not a consumer of AI Interpretation Service — see Dependencies.
- Commands: `CreateRawSnapshot(analysisRunId, selector)` (mints `kind: raw_result_snapshot` — confirms §10.1's ownership note: this half of InterpretationRecord is created here, not by AI Interpretation Service), `CreateReport`, `AddCitation(reportId, interpretationRecordId)`, `FinalizeReport`, `GenerateExport(reportId, format)`.
- Queries: `GetReport`, `ListReportsForProject`, `GetExport`.
- Events: `ReportFinalized`, `ExportGenerated`.
- Authentication: Gateway-delegated.
- Authorization: PI/Researcher (Edit); Analyst/Viewer query-only (§6.1).
- Idempotency: `GenerateExport` requires an idempotency key (re-request returns the existing Export, no duplicate render); `FinalizeReport` is naturally idempotent (finalizing twice is a no-op).
- Sync vs Async: `CreateRawSnapshot`/`AddCitation`/`FinalizeReport` synchronous (metadata operations); `GenerateExport` **asynchronous** (PDF/Word rendering).
- Primary entities: Report, Export, InterpretationRecord (`kind: raw_result_snapshot` only).
- Dependencies: Analysis Service (source data for snapshots). **Deliberately not dependent on AI Interpretation Service** — Reporting Service only ever reads an already-created InterpretationRecord by ID when a user adds a citation; it never requests one be generated. This is "AI is never the source of truth" enforced as a service-dependency-graph fact, not just a policy statement.

**Billing Service**
- Purpose: Tenant subscription/seat state.
- Consumers: API Gateway (SCR-ADM-01); Identity Service (checks seat availability before `InviteMember` succeeds).
- Commands: `UpdateSeats`, `CancelSubscription`.
- Queries: `GetSubscriptionStatus`.
- Events: `SubscriptionUpdated`, `PaymentFailed`.
- Authentication: Gateway-delegated for user-initiated calls; separately, authenticated webhook intake from the payment processor (a distinct, non-Gateway path).
- Authorization: Institution Owner/Admin only.
- Idempotency: webhook intake keyed by the processor's own event ID (processors retry).
- Sync vs Async: `GetSubscriptionStatus`/`UpdateSeats` synchronous; webhook intake inherently async/event-driven.
- Primary entities: Subscription.
- Dependencies: Identity Service (seat count is read from `TenantMembership`, not duplicated).

**Admin/Ops Service**
- Purpose: internal tenant provisioning, support diagnostics, abuse/quota monitoring. Never reachable via the Public API.
- Consumers: internal staff tooling only.
- Commands: `ProvisionTenant` (internal override, distinct from self-service `CreateTenant`), `SuspendTenant`, `OverrideQuota`.
- Queries: `GetTenantDiagnostics`, `ListAuditLogEntries` (cross-Tenant — the one legitimate consumer of the audit gap flagged in §10.1, even without a customer-facing screen yet).
- Events: none published; consumes all other services' events for monitoring.
- Authentication: a **separate internal-staff auth path** — deliberately not the customer Identity Service session model, isolating internal credentials from customer attack surface.
- Authorization: internal role-based, outside §6's customer role model entirely.
- Idempotency: `SuspendTenant`/`OverrideQuota` idempotent (re-applying is a no-op).
- Sync vs Async: synchronous; low-volume, human-triggered.
- Primary entities: reads across everything for diagnostics; writes none of the core research entities.
- Dependencies: all other services (read-only).

**API Gateway**
- Purpose: **the single external API surface.** Composes and routes to the eight services above; never exposes them directly — "backend engines never exposed directly" made contractually explicit, not just architecturally implied.
- Consumers: Web Application Shell (v1); external institutional integrations via Service Account tokens (v1.x — this becomes the externally-documented "Public API," the *same* surface, not a second one, reconfirming §8.8/§4.1).
- Commands/Queries: none of its own — a pass-through/composition layer that validates and routes to the service whose contract defines the operation. Deliberate: a Gateway with no business logic of its own cannot become a place where AIG-001/AIG-003 are silently bypassed.
- Events: none owned; may fan out event notifications to external Service Account consumers in v1.x (a Public API feature, not designed further here).
- Authentication: terminates all external authentication (session and Service Account tokens) and forwards a validated identity context inward; internal services trust the Gateway's assertion rather than re-authenticating.
- Authorization: delegates every decision to Identity Service's `CheckAuthorization` — enforces, does not decide, keeping authorization logic in exactly one place.
- Idempotency: enforces idempotency-key handling uniformly for the commands that require it, rather than trusting each service to implement it identically.
- Sync vs Async: synchronous request/response to the caller in all cases; async internal work (Collection, Analysis, Export) is fronted by an immediate "accepted" response with a run/export ID, never a long-held connection.
- Primary entities: none owned.
- Dependencies: all eight services above.

### 11.3 Deriving REST endpoints from the contracts

Deliberately partial and representative, not an exhaustive spec — every command/query above maps to exactly one endpoint by the same pattern, so only enough is shown here to demonstrate the derivation, consistent with the instruction to avoid implementation-specific detail at this stage.

| Service | Representative Endpoint | Derived From | Sync/Async |
|---|---|---|---|
| Identity | `POST /projects` | `CreateProject` command | Sync |
| Identity | `GET /projects/{id}/members` | `ListProjectMembers` query | Sync |
| Collection | `POST /datasets/{id}/collection-runs` | `StartCollectionRun` command | Async (202 Accepted + polling/event) |
| Analysis | `POST /collection-runs/{id}/analysis-runs` | `StartAnalysisRun` command — path shape itself encodes the CollectionRun-pinning rule (§10.1) at the API surface, not just in documentation | Async |
| AI Interpretation | `POST /analysis-runs/{id}/interpretations` | `RequestInterpretation` command — **no `PUT`/`PATCH`/`DELETE` sibling exists on this resource**, the REST-level expression of AIG-003 | Sync (v1.x) |
| Reporting | `POST /reports/{id}/citations` | `AddCitation` command | Sync |
| Reporting | `POST /reports/{id}/exports` | `GenerateExport` command | Async |
| Billing | `GET /tenant/subscription` | `GetSubscriptionStatus` query | Sync |
| Admin/Ops | *(not exposed via this Gateway path prefix at all — a separate internal-only host/path space)* | — | — |

The full endpoint catalog — request/response schemas, pagination, error codes — belongs to an implementation-level API spec (OpenAPI or equivalent), explicitly out of scope for this deliverable per instruction.

### 11.4 AIG-003 — AI Operations Are Stateless (formalized)

| Field | Value |
|---|---|
| ID | AIG-003 |
| Title | AI operations are stateless |
| Status | Formalized, binding on AI Interpretation Service and any future extension (conversational Research Assistant, v2) |
| Applies to | AI Interpretation Service, `InterpretationRecord` (`kind: ai_generated`) |
| Depends on | AIG-001 (§9.4) — AIG-003 is a stricter, service-contract-level restatement of AIG-001 Rule 2, not a new independent policy |

**Rule.** Every AI request creates a new, immutable `InterpretationRecord`, carrying complete provenance: the source `AnalysisRun` ID, its `CollectionRun` ID (transitively — the pinned input state), the Reproducibility Service manifest hash, the AI model version, the prompt template version, and a timestamp. No existing analytical artifact — `AnalysisRun`, `CollectionRun`, or any prior `InterpretationRecord` — is ever mutated by an AI operation.

**Enforcement, structural not procedural:** `AI Interpretation Service`'s contract (§11.2) exposes exactly one command, `RequestInterpretation`, with no update or delete counterpart — statelessness isn't a rule the service *follows*, it's a rule the contract makes it *incapable of violating*. The REST derivation (§11.3) mirrors this: the endpoint has no `PUT`/`PATCH`/`DELETE`. Two identical requests are not deduplicated (§11.2's idempotency note) precisely because each is a distinct, separately-provenanced act of interpretation, even against unchanged data — deduplicating them would blur exactly the provenance trail AIG-003 exists to keep intact.

---

## 12. Backend Architecture

The implementation blueprint derived from §10 (Database Concept) and §11 (API Architecture) — not new decisions, but the layer that makes those decisions buildable. Six layers, dependencies flowing inward toward Domain, which depends on nothing. This inward flow is the actual enforcement mechanism for **BKG-001** (§12.5), not a separate rule layered on top of it.

### 12.1 The six layers

**Presentation Layer**
- Responsibilities: wire protocol and contract shape — REST/JSON (chosen once, stated here rather than assumed elsewhere), request/response envelope format, API versioning scheme, a uniform error-response shape, and one DTO pair per §11 command/query (e.g., `StartAnalysisRunRequest` / `AnalysisRunAccepted`).
- Allowed dependencies: API Layer only.
- Forbidden dependencies: Application, Domain, Infrastructure, Persistence — a DTO must never import a Domain entity directly; that would make the wire contract and the domain model change in lockstep, defeating the reason to separate them.
- Primary modules: `presentation.dto.*`, `presentation.envelope`, `presentation.versioning`.
- Primary interfaces: none of its own — consumes API Layer's routing, produces the wire format API Layer sends.
- Extension points: a new DTO version when a §11 contract evolves (e.g., a `v2` shape) without touching anything below; a future GraphQL surface alongside REST would live here without touching Application/Domain.

**API Layer**
- Responsibilities: HTTP routing per §11.3's endpoint derivation; authentication token validation (delegating the actual check to Identity Service); authorization enforcement via `CheckAuthorization`; idempotency-key deduplication; rate limiting. This is the API Gateway service contract (§11.2) made concrete as backend code.
- Allowed dependencies: Application Layer (invokes orchestrators/use cases); Presentation Layer (DTO translation).
- Forbidden dependencies: Domain directly (must go through an Application use case), Infrastructure, Persistence.
- Primary modules: `api.routes.*` (one per §11.2 service — `api.routes.collection`, `api.routes.analysis`, `api.routes.interpretation`, `api.routes.reporting`, `api.routes.identity`, `api.routes.billing`), `api.middleware.auth`, `api.middleware.idempotency`, `api.middleware.rate_limit`.
- Primary interfaces: `AuthenticationValidator`, `AuthorizationChecker` — both call into Domain's `AuthorizationPolicy`, never reimplement it.
- Extension points: new routes for the Public API (v1.x) are added here only — confirms §11.2's "single surface" claim at the code level, since this is the only layer with route definitions at all.

**Application Layer**
- Responsibilities: orchestrates each §11 command/query into a coordinated sequence of Domain and Infrastructure-interface calls. One orchestrator per command (e.g., `StartAnalysisRunOrchestrator`: verify the target `CollectionRun` is `completed`, check `AuthorizationPolicy`, create the `AnalysisRun` entity in `queued` state, persist it, dispatch a background job). Sequencing only — no business *rules* here; that distinction from Domain is what BKG-001 actually turns on.
- Allowed dependencies: Domain Layer (entities, domain services, repository *interfaces*); Infrastructure-defined *interfaces* only (`IJobDispatcher`, `IEventPublisher`, `ICheckpointRecorder`, `ILogger`, `IAuditWriter`) — never a concrete Infrastructure class.
- Forbidden dependencies: Presentation, API (never calls upward); concrete Infrastructure/Persistence implementations.
- Primary modules: `application.orchestrators.*` (one per command — full mapping in §12.3), `application.queries.*` (thinner read-path handlers: authorization scoping + a repository call).
- Primary interfaces: defines `IRepository<T>`, `IJobDispatcher`, `IEventPublisher`, `ICheckpointRecorder`, `ILogger`, `IAuditWriter` — Application and Domain jointly own these interfaces; Infrastructure/Persistence only ever implement them.
- Extension points: a new orchestrator is the unit of extension for a new capability (e.g., a v2 `AskFollowUpQuestionOrchestrator` extending AI Interpretation).

**Domain Layer**
- Responsibilities: the business rules themselves — the actual subject of BKG-001. Rich entities (every entity from §10.1) enforcing their own lifecycle rules in code, not by convention: `AnalysisRun.complete()` is the only path to a status change, and the entity itself refuses `completed → anything else`; `InterpretationRecord` exposes no mutator at all after construction (immutability enforced in the entity, the same guarantee AIG-001/AIG-003 describe, now made structural here rather than only at the API layer, §11.4). Domain services hold cross-entity policy: `AuthorizationPolicy` (the full §6.1 matrix), `ReproducibilityPolicy` (the rule that an `AnalysisRun` may only be created against a `completed` `CollectionRun` — the pinning rule lives here, as an invariant, not as a validation some other entry point could skip), `InterpretationProvenance` (assembles the AIG-001/003 provenance bundle — manifest hash, model version, prompt version — onto every new `InterpretationRecord`).
- Allowed dependencies: **none, outward.** The one non-negotiable rule of the architecture, and the actual mechanism enforcing BKG-001: if Domain cannot import Infrastructure, Persistence, API, or Presentation, business logic cannot leak into those layers by construction — they are the ones doing the importing (of Domain), never the reverse.
- Forbidden dependencies: everything outside itself — Application, Presentation, API, Infrastructure, Persistence, and any external SDK (AI provider client, HTTP client, database driver, queue client) — no exceptions.
- Primary modules: `domain.entities.*`, `domain.services.authorization_policy`, `domain.services.reproducibility_policy`, `domain.services.interpretation_provenance`, `domain.value_objects.*` (`ManifestHash`, `InterpretationKind`, `RoleGrant`).
- Primary interfaces: *defines but never implements* `IRepository<T>`, `IJobDispatcher`, `IEventPublisher`, `ICheckpointRecorder`, and `IAIProvider` — the last one is Domain stating "an AI provider must accept a prompt and a manifest hash and return text plus a model-version tag," without knowing or caring which LLM actually answers.
- Extension points: deliberately the hardest layer to extend casually, by design — a new `AnalysisType` rule, a new §6 role, a new entity lifecycle state all change here first, before anything else is touched.

**Infrastructure Layer**
- Responsibilities: implements every interface Domain/Application defined, and is the *only* layer allowed to talk to the outside world. See §12.2 for the full adapter inventory (provider adapters, AI adapters, jobs, events, checkpoint, logging, audit, configuration) — deliberately broken out separately since the instruction calls these out explicitly, not folded silently into a layer description.
- Allowed dependencies: Domain Layer (implements its interfaces); any external SDK/library — the only layer permitted to.
- Forbidden dependencies: Presentation, API (never calls upward — a job worker doesn't know it was triggered by an HTTP request, only that Application dispatched it).
- Primary modules: see §12.2.
- Primary interfaces: implements everything Domain/Application defined; defines nothing Domain/Application need to know about — a strict one-way contract.
- Extension points: **this is where §5's and §10's extensibility claims become concrete code, not just documented intent.** Swapping the AI provider, adding a second content platform (TikTok/Instagram, v2+), or changing the job-queue technology are all Infrastructure-only changes, invisible above.

**Persistence Layer**
- Responsibilities: repository implementations, one per aggregate, per §10's `Project`-as-root-aggregate design — `ProjectRepository` loads/saves the whole aggregate boundary in one place, the concrete form of §10.2's hint toward a service boundary. Storage technology is deliberately not named here (Deployment Architecture's concern); this layer is described by interface implementations, not a database product.
- Allowed dependencies: Domain Layer (implements `IRepository<T>` per entity; translates domain objects to/from a storage representation).
- Forbidden dependencies: Presentation, API, Application (repositories are called *by* Application through an interface Domain defined — never initiate upward); Infrastructure (Persistence and Infrastructure are peers, not dependent on each other).
- Primary modules: `persistence.repositories.project_repository`, `.dataset_repository`, `.collection_run_repository`, `.analysis_run_repository`, `.interpretation_record_repository` (notably exposes **`create` and read methods only — no `update`**, the persistence-level mirror of AIG-003's "no Update/Delete command," so immutability is enforced at three independent layers at once: the Domain entity, the missing Application orchestrator, and now the missing repository method), `.report_repository`, `.export_repository`, `persistence.mappers.*`.
- Primary interfaces: implements `IRepository<T>` variants.
- Extension points: a new entity's repository, or a storage-representation change (e.g., moving raw collected content to object storage while metadata stays relational) — both Persistence-only.

### 12.2 Cross-cutting concerns, explicitly identified

- **Background job execution:** `IJobDispatcher` (Application/Domain-defined) → `infrastructure.jobs.queue_dispatcher`. Used by the three async operations identified in §11.2: Collection, Analysis, Export. The job's actual work is still Domain+Infrastructure code invoked by a worker — there is no separate "job layer" where business logic could hide; BKG-001 applies inside job workers exactly as it does inside a request handler.
- **Event publication:** `IEventPublisher` → `infrastructure.events.publisher`. Every `*Completed`/`*Failed` event (§11.2) is published here once an orchestrator's Domain operation succeeds. Reproducibility Service *consumes* these rather than publishing (confirmed again here, consistent with its §11.2 contract).
- **Checkpoint integration:** `ICheckpointRecorder` → `infrastructure.checkpoint.manifest_recorder` — a direct wrapper around the existing engine's checkpoint/manifest system (already-proven, already-tested infrastructure, not a rebuild). Called by Collection and Analysis orchestrators mid-execution; produces the manifest hash AIG-001/003 require.
- **Logging:** `ILogger`, injected into Application orchestrators (not into Domain — Domain performs no I/O of any kind, including logging, keeping it free of side effects entirely) → `infrastructure.logging.structured_logger`, wrapping the existing engine's logging module.
- **Audit:** `IAuditWriter`, called by Application orchestrators after a Domain state transition succeeds (again, not by Domain entities themselves) → `infrastructure.audit.audit_writer`, persisting `AuditLogEntry` (§10.1) via its own repository. "What happened" is Application's job to report; "was this allowed" was already Domain's job (`AuthorizationPolicy`) earlier in the same orchestrator — the two are deliberately not merged.
- **Configuration:** `infrastructure.config.settings_loader` — wraps the existing engine's config module. Injected into Infrastructure adapters at startup (AI provider endpoint, platform credentials); Domain and Application never read configuration directly, they receive already-configured adapters via dependency injection — "how we're configured" is explicitly not a business rule, so it stays out of the two layers BKG-001 reserves for business rules.

### 12.3 Service Contract → backend implementation map

| Service Contract (§11.2) | Application Orchestrators | Domain Entities / Services | Infrastructure Adapters | Persistence Repositories |
|---|---|---|---|---|
| Identity Service | `CreateTenantOrchestrator`, `CreateProjectOrchestrator`, `InviteMemberOrchestrator`, `AssignRoleOrchestrator`, `ArchiveProjectOrchestrator` | `Tenant`, `User`, `TenantMembership`, `ProjectMembership`, `Project`; `AuthorizationPolicy` | `infrastructure.auth.token_service` | `TenantRepository`, `UserRepository`, `ProjectRepository` (aggregate root) |
| Reproducibility Service | *(internal-only; invoked from within Collection/Analysis orchestrators, not its own top-level orchestrator)* | `ManifestHash` value object | `infrastructure.checkpoint.manifest_recorder` (wraps existing checkpoint system) | manifest state persisted as part of `CollectionRunRepository`/`AnalysisRunRepository`, not a separate store |
| Collection Service | `StartCollectionRunOrchestrator`, `ResumeCollectionRunOrchestrator` | `Dataset`, `CollectionRun` | `infrastructure.providers.youtube_adapter` (wraps existing `providers/platform/youtube.py`), checkpoint integration | `DatasetRepository`, `CollectionRunRepository` |
| Analysis Service | `StartAnalysisRunOrchestrator` | `AnalysisRun`, `AnalysisType`; `ReproducibilityPolicy` (CollectionRun-pinning) | Analysis execution adapter (wraps existing topic-modeling/sentiment/market pipeline), checkpoint integration, job dispatch | `AnalysisRunRepository` |
| AI Interpretation Service | `RequestInterpretationOrchestrator` | `InterpretationRecord` (`kind: ai_generated`); `InterpretationProvenance` | `infrastructure.ai.llm_adapter` (implements `IAIProvider`) | `InterpretationRecordRepository` (create + read only) |
| Reporting Service | `CreateRawSnapshotOrchestrator`, `CreateReportOrchestrator`, `AddCitationOrchestrator`, `FinalizeReportOrchestrator`, `GenerateExportOrchestrator` | `Report`, `Export`, `InterpretationRecord` (`kind: raw_result_snapshot`) | `infrastructure.rendering.pdf_adapter`, `.docx_adapter` (extends existing manuscript-table output) | `ReportRepository`, `ExportRepository` |
| Billing Service | `UpdateSeatsOrchestrator`, `CancelSubscriptionOrchestrator` | `Subscription` | `infrastructure.payments.processor_adapter` | `SubscriptionRepository` |
| Admin/Ops Service | thin, elevated-authorization query handlers | *(reads across everything; no dedicated entities)* | separate internal-staff auth path | reads via existing repositories — no new ones |
| API Gateway | *(not an orchestrator target — corresponds to the Presentation + API Layers themselves, spanning every contract's routing)* | — | — | — |

### 12.4 Reused vs. new, stated plainly

Three Infrastructure adapters are direct wrappers around already-built, already-tested engine code, not new implementations: the YouTube provider adapter, the checkpoint/manifest recorder, and the structured logger. This is a real, evidence-grounded cost saving worth stating outside the abstraction — most of Infrastructure's collection/reproducibility/logging surface is integration work, not net-new engineering. Everything else in Infrastructure (AI adapter, job dispatcher, event publisher, audit writer, payment adapter, PDF/Word rendering) is genuinely new.

### 12.5 BKG-001 — Business Rules Belong Exclusively to Application and Domain (formalized)

| Field | Value |
|---|---|
| ID | BKG-001 |
| Title | Business rules belong exclusively to the Application and Domain layers |
| Status | Formalized, binding on all backend implementation work derived from this document |
| Applies to | All six layers (§12.1); specifically prohibits business logic in API controllers, persistence models, infrastructure adapters, and AI providers |

**Rule.** Business rules — anything that decides *whether* an action is valid, *what* state something may transition to, or *how* a result should be interpreted — live only in the Application Layer (sequencing) and Domain Layer (the rules themselves). API controllers, persistence models, infrastructure adapters, and AI providers must never contain business logic.

**Enforcement, structural not procedural, consistent with how AIG-001/003 were enforced in §11:** the Domain Layer's "no outward dependencies" rule (§12.1) is the actual mechanism — a codebase where Domain cannot import anything cannot have Infrastructure reach in and add a business rule, because Infrastructure only ever *implements interfaces Domain defined*, it never *extends* Domain. Concretely: the YouTube adapter cannot decide that a video is "ineligible" (that's a Domain rule already established in the existing engine's `_to_video_record` eligibility logic, and stays a Domain rule here, not something the adapter re-derives); the AI adapter cannot decide an interpretation is "final" or "correct" (that's outside Domain's authority entirely too — per AIG-001, nothing decides that, the interpretation is commentary, never a verdict); a persistence mapper cannot silently default a missing field to a business-meaningful value (defaults are a Domain concern, mappers only translate shape). Where this document's own examples (§12.1, §12.2) show a policy decision, it is always attributed to a named Domain service (`AuthorizationPolicy`, `ReproducibilityPolicy`, `InterpretationProvenance`) — never to an adapter, a repository, or a route handler — by construction, not by reviewer diligence.

### 12.6 What this settles for later work

- **Package structure:** six top-level packages (`presentation`, `api`, `application`, `domain`, `infrastructure`, `persistence`), with an automated dependency-direction check (Domain importing nothing outward, Infrastructure/Persistence never imported by Presentation/API) as a buildable lint rule, not just a documented convention — a concrete, testable expression of BKG-001 for the eventual Testing Strategy.
- **Testing strategy (foreshadowed, not designed here):** Domain and Application are unit-testable with no I/O whatsoever (no database, no network, no AI provider) since neither depends on Infrastructure/Persistence — a direct, structural benefit of the layering, worth carrying forward explicitly when a Testing Strategy is eventually scoped.
- **AIG-002 remains unassigned**, per instruction — not invented here either.

---

## 13. Frontend Architecture

The presentation and orchestration layer derived from §9 (Navigation/Screen Inventory), §10 (Database Concept), §11 (API Architecture), and §12 (Backend Architecture) — no framework named anywhere below; every principle should survive a framework choice made later.

### 13.1 Frontend Design Principles

1. **The backend is the single source of truth, without exception.** The frontend renders state the API Gateway (§11.2) returns; it never derives, computes, or infers analytical results client-side. This is the frontend-specific restatement of §11's "single API surface" and §12's Domain-owns-the-rules design, carried one layer further out.
2. **The frontend has exactly one job description, formalized as FG-001 (§13.14):** presentation, orchestration, user interaction. Nothing else.
3. **Reproducibility is a frontend obligation too, formalized as FG-002 (§13.14):** every rendered visualization, dashboard, Report preview, and AI explanation must be reconstructable from backend state alone — not from anything only the client currently holds in memory.
4. **Framework-independence is deliberate, not incidental.** These principles, and everything in §13.2–§13.13, are written so a React, Vue, or Svelte implementation (or a future rewrite in whichever framework is current then) satisfies them identically — the architecture's stability should not be coupled to a JavaScript ecosystem's churn.

### 13.2 Layout Architecture

Two shell modes, matching the Tenant/Project scoping already established in §6 and §9.2, not invented fresh here:

- **Tenant Shell** — renders NAV-01, NAV-02, NAV-10, NAV-11, NAV-12, NAV-13 (Dashboard, Projects list, Cross-Project Comparison, Research History, Institution Admin, Account Settings). No Project context is active.
- **Project Workspace Shell** — renders once a Project is selected (NAV-03's children: Overview, Datasets, Analyses, Reports, Settings, Archive). Carries a persistent Project-context indicator (name, archived/active state) so a user is never ambiguous about which study they're looking at — directly reflecting §10.1's Project-as-root-aggregate boundary in the layout itself, not just in the data model.

A breadcrumb (Tenant → Project → Section → Entity) is the layout-level expression of §10's aggregate hierarchy; it is generated from the current route (§13.5), never maintained as separate client state.

### 13.3 Navigation Model

The frontend's route tree is §9.2's Navigation Structure table, directly — not a reinterpretation of it. §9.1's distinction (nav nodes are persistent shell destinations; most screens are drill-down views, not nav nodes) is enforced here as: only NAV-01 through NAV-13 render in the persistent shell chrome; every other screen from §9.3 is reached by in-context navigation from a parent screen and does not appear in the nav rail, even if it's directly deep-linkable (§13.5).

Nav items are **data-driven from role and Tenant plan, never hardcoded per user type**: NAV-10 (Cross-Project Comparison) and NAV-12 (Institution Admin) are v1.x-gated exactly as §9.2 specifies — in v1 they render hidden or as an upgrade affordance, decided once here as the standard pattern rather than a per-screen special case.

### 13.4 State Management Strategy

Three distinct categories, deliberately not one undifferentiated "app state":

- **Server state** (the large majority) — Project, Dataset, CollectionRun, AnalysisRun, InterpretationRecord, Report, Export data fetched from the API Gateway. Held in a cache keyed by entity ID, revalidated on a defined policy (not held forever, not refetched constantly) — **never duplicated into a separately-mutable client store.** For every entity §10.2 already marked immutable-once-complete (`CollectionRun`, `AnalysisRun`, `InterpretationRecord`, finalized `Report`, `Export`), the cache needs no optimistic-update or conflict-resolution logic at all, since the underlying data cannot change out from under it — a direct, structural payoff of §10's immutability design, not a frontend convenience layered on afterward.
- **Local UI state** — form inputs before submission, filter/sort/pagination selections, nav/panel toggles. Ephemeral, screen-scoped, never persisted beyond the session unless a specific screen says otherwise.
- **Session/identity state** — current `User`, current `Tenant`, current `Project` context. Global in reach but still sourced from Identity Service (§11.2/§12.3) via the API, not a client-invented concept — "session state" describes its *scope*, not its *origin*.

The one entity requiring genuine local-mutable state before it becomes server state is a **draft `Report`** (§10.1's one mutable-while-draft entity) — handled explicitly in the Builder screen category (§13.6.D), not treated as a general pattern the rest of the app needs.

### 13.5 Routing Strategy

URL structure mirrors the entity hierarchy from §10 and the drill-down relationships from §9.3 — e.g. `/projects/:projectId`, `/projects/:projectId/datasets/:datasetId`, `/projects/:projectId/analyses/:runId`, `/projects/:projectId/reports/:reportId`. Deliberately framework-agnostic: this is a URL *scheme*, not a router library's configuration.

**Every screen in §9.3 is deep-linkable**, including drill-down screens that aren't nav nodes — this matters concretely for the Viewer/Reviewer sharing pattern (§6, §7.2 stage 6) and the v2 shareable-read-only-link idea (§6's Viewer/Reviewer extensibility note). A route guard on the client is a UX convenience only, never the actual security boundary — authorization is re-checked server-side on every request regardless of how the client got there (§11.2's `CheckAuthorization`, §12.1's API Layer), so a deep link to a Report a user shouldn't see fails at the API, not just at the router.

### 13.6 Screen Composition Model

Every one of the 22 screens in §9.3 is an instance of one of six categories — the categories, not the 22 screens individually, are what §13.7 specifies, since the categories are what actually needs a consistent design:

- **A — List/Table:** SCR-PROJ-01, SCR-DATA-01, SCR-ANLY-01, SCR-RPT-01, SCR-HIST-01, SCR-XPRJ-01.
- **B — Detail/Read:** SCR-PROJ-02, SCR-DATA-02, SCR-ANLY-03.
- **C — Configuration/Form:** SCR-DATA-03, SCR-ANLY-02, SCR-SET-01, SCR-SET-02, SCR-AUTH-01, SCR-AUTH-02, SCR-ACCT-01, SCR-ADM-01, SCR-ADM-02 (Admin/Billing screens are Category C with elevated authorization, not a separate category).
- **D — Builder:** SCR-RPT-02.
- **E — Export/Action Confirmation:** SCR-RPT-03, SCR-PROJ-03/04.
- **F — AI Interpretation Panel:** SCR-ANLY-04.

### 13.7 Per-Category Specification

**A — List/Table Screens**
- Purpose: enumerate entities within a scope; entry point to creation or drill-down.
- State ownership: server-state cache (read-through); local state for filter/sort/pagination only.
- API dependencies: one `list*` query (§11.2/§11.3) per screen.
- Loading states: skeleton rows, not a full-screen spinner — preserves the data-density layout (§13.9) instead of a jarring pop-in.
- Empty states: category-specific first-run guidance (per-screen copy already fixed in §9.3), standardized as a *pattern* here, not re-specified per screen.
- Error states: inline banner within the data region only; shell/nav chrome stays intact and usable.
- AI interaction points: none — status badges only (e.g., "interpretation available"); the interaction itself belongs to category F.
- Navigation behavior: row click → category B or F; a persistent "create new" action → category C.

**B — Detail/Read Screens**
- Purpose: show one entity's full state (Project Overview, Dataset with its CollectionRun history, AnalysisRun with results).
- State ownership: server-state cache keyed by entity ID; **no local mutable copy for immutable entities** — an `AnalysisRun` detail view has no "save" affordance because there is nothing to save, a direct UI consequence of §10.1.
- API dependencies: one `get*` query, plus a nested `list*` where the entity has run history (`ListCollectionRunsForDataset`).
- Loading states: skeleton matching the eventual header + body layout, minimizing shift on data-dense screens.
- Empty states: sub-region empty states nested within an otherwise-populated screen (e.g., zero CollectionRuns yet), never a whole-screen empty state — the entity itself already exists.
- Error states: distinguishes "not found / no access" (terminal) from "transient fetch failure" (inline retry) — requires the uniform error envelope (§13.10) to carry enough structure for the frontend to tell these apart without guessing from an HTTP status code alone.
- AI interaction points: SCR-ANLY-03 specifically triggers category F; other Detail screens have none.
- Navigation behavior: entered from category A or a parent Detail screen; exits per §9.3's documented exit paths (e.g., Dataset detail → new Collection Run).

**C — Configuration/Form Screens**
- Purpose: collect structured input to start an action (new Collection Run, new Analysis Run, roster/settings edits, sign-up/login).
- State ownership: **local, uncommitted form state until submission** — the one category where client state genuinely, necessarily diverges from server state temporarily.
- API dependencies: an option-populating `list*` query where relevant (e.g., `ListAnalysisTypes`, template-scoped — §8.2/§9.3), plus the triggering command on submit.
- Loading states: option fields skeleton/disabled while lists load; submit has its own distinct in-flight state, separate from page-load skeletons.
- Empty states: an option list with zero choices is a blocking inline message, not a silently empty dropdown.
- Error states: field-level validation shown inline (**client-side shape validation only — required fields, formats; never business-rule validation**, which stays server-side per FG-001/BKG-001); submission failures distinguish "rejected, fixable on this form" from "backend/service failure, offer retry."
- AI interaction points: **none** — configuration screens never invoke AI, matching §9.3's explicit statement for SCR-ANLY-02.
- Navigation behavior: successful submission routes to the resulting entity's category B screen; cancel returns to the originating category A screen.

**D — Builder Screens**
- Purpose: assemble multiple immutable `InterpretationRecord` citations (§10.1, both `kind`s) into an editable `Report` draft.
- State ownership: hybrid — the draft's own metadata/layout is local form state (category C's pattern); cited `InterpretationRecord`s are **read-only server-state references only, never copied into editable local state** — the Builder holds pointers to immutable citations, not their content, which is the frontend-level enforcement of §10.0's Report↔InterpretationRecord rule.
- API dependencies: `ListInterpretationsForAnalysisRun` / `CreateRawSnapshot` (new citation), `AddCitation`, `GetReport`, `FinalizeReport`.
- Loading states: the citation picker loads independently of the draft's own metadata form — two independent regions, not one blocking spinner.
- Empty states: a Report with zero citations blocks `FinalizeReport` with an explicit inline reason, not a silently disabled button.
- Error states: category C's field/form pattern, plus a citation-specific case: a referenced `AnalysisRun`/`InterpretationRecord` that's since become unavailable is flagged per-citation (§9.3), never silently dropped.
- AI interaction points: **none for generation** — a Builder screen never asks AI to draft report text (§9.3's explicit rule for SCR-RPT-02, reaffirmed); it may only let a user select an existing `kind: ai_generated` record as a citation, exactly like selecting a `raw_result_snapshot` one.
- Navigation behavior: entered from category A (Reports List) or directly from category B ("add to Report"); exits to category E once finalized.

**E — Export/Action Confirmation Screens**
- Purpose: trigger and confirm an irreversible or side-effecting action (export rendering, Project archival).
- State ownership: minimal transient confirmation state, plus the async job status once triggered (shares §13.8's Long-running Job pattern).
- API dependencies: the triggering command (`GenerateExport`, `ArchiveProject`) plus a status query/subscription.
- Loading states: §13.8's async pattern — an in-progress indicator, never a blocking modal spinner.
- Empty states: not applicable — these are action screens, not data displays.
- Error states: the primary failure mode here is **action failure, not fetch failure** — the UI must distinguish "the export failed to generate" from "we failed to check whether it succeeded," which need different user guidance.
- AI interaction points: none.
- Navigation behavior: success routes to the owning List/Detail screen with the confirmation state visible on arrival (Export → Reports List; Archive → the now-read-only SCR-PROJ-04), never conveyed only by a toast that could be missed.

**F — AI Interpretation Panel**
- Purpose: request and display a `kind: ai_generated` `InterpretationRecord`, bound by AIG-001/AIG-003 and FG-001/FG-002 (§13.14 below).
- State ownership: **server-state only, immutable once returned.** No local editing of interpretation text is possible — that would violate both AIG-001's immutability and FG-001's "never implements... AI reasoning." "Regenerate" issues a new request; it is not an edit of the displayed one, mirroring §11.4's contract-level rule exactly at the UI.
- API dependencies: `RequestInterpretation`, `GetInterpretation` / `ListInterpretationsForAnalysisRun`.
- Loading states: a distinct "generating" state, separate from generic data-loading skeletons — AI latency has a different shape (indeterminate, seconds-scale) than a table fetch, and **must be visually unambiguous as "nothing has been returned yet,"** never a skeleton a user could mistake for partial content — this is where FG-002 has direct teeth: any placeholder content here would not be backend-sourced.
- Empty states: no prior interpretation exists yet — a clear "request an explanation" call to action, not a blank panel.
- Error states: **the category-defining rule, already specified per-screen in §9.3 and restated here as the standard**: model/service unavailable is an explicit failure state, never a silently degraded or fabricated-looking answer.
- AI interaction points: this category *is* the AI interaction point — confirming every other category's "none" was a deliberate boundary, not an oversight repeated by accident.
- Navigation behavior: opens as an embedded panel from category B (SCR-ANLY-03), never its own route; its "iterate" action routes to category C, pre-filled — the concrete UI expression of the §7.2 loop.

### 13.8 Long-running Job UX

Collection, Analysis, and Export are asynchronous at the API level (§11.2, §12.2) — the frontend needs one consistent pattern reused across all three, not three bespoke ones:

- A **persistent "jobs in progress" indicator** in the shell chrome (§13.2), not a spinner buried on a single screen — a researcher may navigate away while a Collection Run executes over hours (§7.2 stage 2) and must still see it's running from anywhere in the app.
- **Subscribe where available, poll as fallback** — the frontend subscribes to the relevant `*Completed`/`*Failed` event (§11.2) where the transport supports it, falling back to interval polling of the run's status query otherwise; this is a strategy, not a transport commitment (WebSocket vs. server-sent events vs. polling is a Deployment/implementation choice, deliberately not made here).
- A shared **Run Status component pattern** (`queued` / `running` / `completed` / `failed` / `resumable`) used identically across Collection and Analysis screens — §9.3 already specified "resumable-state badge, not an error dead-end" per-screen; here it's generalized into one reusable pattern rather than three independent implementations that could drift.
- The **§7.2 iteration loop** (Analysis Execution ⇄ AI Interpretation) is this section's most important case: the "iterate" affordance in category F is not an edge case bolted onto the AI panel, it is the primary expected path back into a new Analysis configuration, and the Long-running Job pattern must support "start a new run from these pre-filled parameters" as a first-class entry point, not just "start a run from a blank form."

### 13.9 Design System Principles

Framework- and library-agnostic: a shared token system (color, spacing, typography), a clear boundary between primitives (buttons, tables, form controls — no domain awareness) and feature components (§13.11, domain-aware, render backend state only). One explicit, evidence-grounded call: **this is a data-dense, desktop-research tool, not a consumer app** — the actual users (§1.3: individual researchers and small labs first) work with tabular comment/topic data and multi-panel analysis views; the design system should default to information density (dense tables, compact controls) rather than the generous whitespace/card-based patterns common in consumer SaaS, which would waste screen space against how this specific audience actually works.

### 13.10 Error Handling Strategy

One uniform error envelope, matching the Presentation Layer's error-response shape (§12.1), mapped consistently to UI treatment everywhere rather than screen-by-screen improvisation:

- **Recoverable** (quota exceeded, render failure, transient fetch failure) → inline, with retry.
- **Terminal** (authorization denial, entity not found) → distinct treatment, typically a redirect or a clear access-denied state, never presented identically to a recoverable error.
- **AI-specific** (§13.7.F) → its own category: model/service unavailable is explicit and unambiguous, **never a silently degraded or fabricated-looking answer** — the single most important error-handling rule in this document, since violating it would break FG-002, not just look bad.
- Errors are surfaced **inline, near the point of failure** — a global toast-only strategy is explicitly rejected here, since it doesn't compose well with the data-dense, multi-region layouts described in §13.9 (a toast can't tell you *which* of three panels on screen failed).

### 13.11 Accessibility Strategy

Primitives (§13.9) carry the primary accessibility burden — semantic HTML, ARIA, keyboard navigation, focus management — so screen-level composition doesn't reinvent it per screen. Two points specific to this platform, not generic boilerplate: data-dense tables (§13.9's own density principle) need deliberate attention to table semantics and sortable-column announcements, since density and accessibility are in tension by default and must be designed together, not traded off; and AI-generated content (category F) must be **announced as AI-generated to assistive technology, not just visually labeled** — a screen-reader user is otherwise excluded from exactly the distinction AIG-001 and FG-001 exist to preserve for sighted users.

### 13.12 Responsive Strategy

An explicit, evidence-grounded call rather than a default mobile-first assumption: the primary target is **desktop/laptop**, matching the actual v1 persona (§1.3) — a researcher doing data-dense analysis work, not someone configuring a new Analysis Run from a phone. Tablet/mobile receive a **reduced, read-oriented experience** — viewing Reports, checking job status, approving/reviewing — not full feature parity. Building full mobile parity for Configuration/Builder screens (categories C/D) would spend real effort against a use case the Vision (§1) never claimed exists for v1; this is stated plainly rather than assumed away silently.

### 13.13 Performance Strategy

- **Route-level code splitting** (§13.5) — each screen category loads its own bundle on demand, not one monolithic application bundle.
- **Server-state caching and revalidation** (§13.4) avoids redundant refetches of data that hasn't changed, particularly important for the immutable entities that never need revalidation at all once loaded once.
- **Virtualization** for large tables/lists — comment-level and topic-assignment data (the platform's actual domain, per the Vision) can be large; list/detail screens (categories A/B) must not render every row into the DOM at once.
- **Visualizations are rendered from backend-computed data only, never recomputed client-side** (direct FG-002 consequence) — but large visualizations (BERTopic topic maps, sentiment-over-time charts) still need lazy/progressive loading given realistic dataset sizes; performance work here is about *loading* backend-computed output efficiently, never about computing more of it client-side to compensate.

### 13.14 FG-001 / FG-002 (formalized)

*(Numbered after the 13 requested strategy sections, consistent with how AIG-001 followed §9.1–§9.3 and BKG-001 followed §12.1–§12.4 — the guardrail formalization is the closing section of its deliverable, not a step inside the walkthrough.)*

| ID | Title | Status | Applies to | Depends on |
|---|---|---|---|---|
| FG-001 | The frontend implements presentation, orchestration, and user interaction only | Formalized | All frontend code, all six screen categories (§13.6) | BKG-001 (§12.5) — the frontend-side half of the same boundary |
| FG-002 | Every visualization, dashboard, Report preview, and AI explanation must be reproducible solely from backend state | Formalized | All frontend rendering, especially category F (§13.7) | AIG-001 (§9.4), AIG-003 (§11.4) — the frontend-side guarantee that those guardrails' provenance isn't defeated by client-side reconstruction |

**FG-001, stated precisely.** The frontend never implements business rules, analytical logic, or AI reasoning. It does not decide whether a video is eligible, compute a sentiment score, judge whether an interpretation is "correct," or default a missing value to something business-meaningful — every one of those is a Domain Layer responsibility (§12.1), unconditionally. What the frontend *does* do — and this boundary is worth stating precisely so FG-001 isn't read as forbidding ordinary UI logic — includes client-side form-shape validation (required fields, formats), display formatting (dates, numbers, pluralization), and UI-state decisions (which panel is open, which tab is active). None of those are business rules; they have no effect on what the backend considers true.

**FG-002, stated precisely.** Nothing on screen may exist only because the client computed or remembered it. A chart is drawn from an API response's data, not from a client-side reduction the backend hasn't itself produced and could return again identically. This is the frontend-side reason category F's loading state (§13.7.F) must never resemble content, and why category D's Builder (§13.7.D) never lets AI draft report text — either would put something on screen the backend didn't produce and couldn't reproduce, which is exactly what FG-002 exists to prevent. Pure display formatting is explicitly not a violation — reformatting a backend-supplied ISO timestamp into a locale-friendly string doesn't change what's true, it changes how it's shown.

**Relationship to the backend guardrails, made explicit:** BKG-001 (§12.5) draws the business-logic boundary *inside* the backend (Domain/Application vs. everything else). FG-001 draws the equivalent boundary *between* backend and frontend. Together, they guarantee business logic exists in exactly one place in the entire system — the Domain Layer — never in Infrastructure, never in the API/Presentation layers, and never in the frontend. AIG-002 remains unassigned, per instruction — not invented here either.

---

## 14. Authentication Strategy

The identity foundation the rest of the platform sits on — derived from §6 (User Roles), §10 (Database Concept), §11 (API Architecture's Identity Service), §12 (Backend Architecture), and §13 (Frontend Architecture's session-state category). Technology-neutral throughout: no specific protocol, library, or provider is named as a requirement.

**The throughline, stated once up front:** §10.1's `Tenant`/`User`/`TenantMembership`/`ProjectMembership` model is already the extensibility mechanism this section needs — an individual researcher (v1's MVP target) is simply a one-User Tenant. Scaling to a research group, a university, or an enterprise deployment changes *how many* Users and Memberships exist and *which* Infrastructure adapter authenticates them (§14.13–§14.14) — it does not change the Identity Model itself. Nothing below introduces a new entity that only makes sense "at enterprise scale"; where a genuine gap exists (§14.12), it's named and fixed once, for every scale, not deferred as enterprise-only debt.

### 14.1 Identity Model

- **`User`** (§10.1) is the single global identity — one User, potentially holding independent `TenantMembership`s in multiple Tenants (e.g., a researcher consulting for two universities). Authentication is Tenant-agnostic (a User logs in once); authorization is Tenant- and Project-scoped (§6.1) on every subsequent request.
- **`ServiceAccountToken`** *(new — not previously given its own entity spec in §10.1, filled in here rather than left implicit)*: the non-human counterpart to `User` (§6's Service Account role). Belongs to exactly one Tenant or, more narrowly, one Project; carries a scoped permission set and an optional expiry; has no password, email, or session — only a token and a revocation state. Owner Module: Identity Service, same as `User`.
- Diagram above: one `User`, independent `TenantMembership`s into Tenant A and Tenant B, `ProjectMembership`s only reachable through the owning Tenant — the structural basis for §14.7's isolation guarantee.

### 14.2 Authentication Model

Identity Service (§11.2) is the sole authenticator; the API Gateway (§11.2, §12.1) terminates all external authentication and forwards a validated identity context inward — internal services trust the Gateway's assertion rather than re-authenticating, exactly as already established, not redesigned here. v1 baseline: credential-based (email + password). The model is deliberately provider-agnostic from day one — §14.13 extends it to federated identity without touching this section's structure, because "how a session gets established" and "what a session *is*" (§14.3) are kept as separate concerns on purpose.

### 14.3 Session Management

A session is a short-lived, revocable credential validated by the API Gateway on every request (§11.2/§12.1's `AuthenticationValidator`) — the specific token format is an implementation choice, out of scope here. Requirements, not mechanisms: sessions must be independently revocable (logout, password change, suspicious-activity response) without waiting for natural expiry; a password reset (§14.6) revokes all other active sessions for that `User` as a hard rule, not a configurable option. The frontend's session/identity state (§13.4) is sourced from this layer via the API on every load — it is never the frontend's own concept, consistent with "backend is the single source of truth" (§13.1).

### 14.4 Password Policy

Grounded in current practice rather than legacy complexity rules: length over composition (a minimum length requirement, not mandatory symbol/number/uppercase rules, which research shows push users toward predictable patterns rather than genuine entropy); reject known-breached passwords at set time (checked against a breach corpus, not invented in-house); no mandatory periodic rotation without cause (forced rotation is no longer considered a net security benefit absent evidence of compromise); rate-limited and lockout-protected authentication attempts (ties to §14.11). Storage: passwords are never stored in plaintext or reversibly encrypted — hashed with a memory-hard hashing function, chosen at implementation time, not fixed here.

### 14.5 Email Verification

A new `User` (SCR-AUTH-02) exists in a `pending verification` state until the registration email is confirmed. Full product access is gated on verification — this is a hard requirement, not a soft nag, because email is also the channel for §14.6 (password reset) and §14.9 (invitations); an unverified email undermines both. Resend is always available; verification does not expire the underlying account, only gates its use.

### 14.6 Password Reset

Standard secure flow, stated as requirements: a reset request issues a time-limited, single-use token to the verified email on file; completing the reset sets a new password and — per §14.3 — revokes every other active session for that `User` immediately, without exception. A reset request for an unregistered email is indistinguishable, from the requester's point of view, from one for a registered email (prevents account enumeration via the reset flow).

### 14.7 Tenant Isolation

The concrete mechanism preventing cross-institution data leakage, and the reason §10.1's `Project` is described as belonging to exactly one `Tenant`: every data-access check resolves Tenant scope first, Project scope second (§6.1's two-level model), and a `User`'s `TenantMembership` in Tenant A grants **zero** implicit access to Tenant B, even for the same `User` holding memberships in both (diagram, §14). This is enforced as an invariant at the Domain/Persistence boundary (§12.1) — every repository query is implicitly Tenant- and/or Project-scoped; an unscoped, cross-tenant query is not a valid operation the Persistence Layer exposes at all, not merely one the API happens not to call. This is also what makes the External Collaborator role (§6) safe: a scoped grant into one Project, without the Tenant-wide access a full membership would imply.

### 14.8 Project Membership

Already modeled in §10.1/§6; the authentication-specific point is that a session does **not** pre-select a Project. There is no "currently active Project" baked into the session credential — every Project-scoped request is authorized against the specific resource's Project ID at request time, via `ProjectMembership` lookup (§14.10). The frontend's "current Project context" (§13.2) is UI convenience state, not a security boundary — restating §13.5's rule from the authentication side: a user cannot gain access to a Project by manipulating which one the UI thinks is "current," because the server never asked the UI which Project was current in the first place.

### 14.9 Invitation Workflow

Two flows, same underlying pattern: `TenantMembership` invitation (Institution Owner/Admin, SCR-ADM-02) and `ProjectMembership` invitation (PI, SCR-SET-02). Inviting an email that matches an existing, verified `User` grants a pending membership the invitee accepts; inviting an unregistered email creates a pending `User` and folds signup + verification (§14.5) + membership acceptance into one flow. `InviteMember` (§11.2) is naturally idempotent — re-inviting an already-invited email is a no-op, already established, not re-derived here. The one workflow-specific addition: an **External Collaborator** (§6) invitation carries a mandatory expiry date, distinguishing it at the workflow level from the indefinite grant every other Project role receives.

### 14.10 Role Resolution

The algorithm behind `CheckAuthorization` (§11.2, §12.1) made explicit, since a `User` may simultaneously hold a `TenantMembership` role and several `ProjectMembership` roles across Tenants:

1. For a **Tenant-scoped** action (billing, tenant member management), resolve directly via that Tenant's `TenantMembership` role.
2. For a **Project-scoped** action, look up a `ProjectMembership` for that specific `User` + `Project`. If one exists, its role governs.
3. If no `ProjectMembership` exists, fall back to the `User`'s `TenantMembership` role for the Project's owning Tenant — **only** Institution Owner/Admin's tenant-wide override (§6's table) grants access this way; every other Tenant-level role (e.g., a future Lab/Department Manager without explicit Project membership) resolves to no access, not partial access, unless explicitly added to the Project.
4. If neither resolves, the action is denied — there is no implicit default-allow anywhere in this algorithm.

### 14.11 Security Principles

- **Least privilege**, already reflected in §6.1's permission matrix — restated here as the principle that matrix exists to serve.
- **Defense in depth**: authorization is checked server-side on every request regardless of client-side state (§13.5) — a compromised or modified frontend cannot grant itself access the API wouldn't independently verify.
- **Credential validation vs. authorization decision, kept distinct**: Infrastructure's token service (§12.2/§12.3) answers "is this credential real"; Domain's `AuthorizationPolicy` (§12.1) answers "is this identity allowed to do this." The two are never merged into one component — merging them is a common source of authorization bugs, where a valid-but-unauthorized credential is mistaken for permission.
- **No plaintext credentials in logs or audit trails**: `ILogger` (§12.2) and `IAuditWriter` (§12.2, §14.12) must never receive raw passwords or session tokens — a concrete, named rule, not an assumed default, since logging infrastructure already exists and this is a realistic, common defect class to guard against explicitly.
- **Internal staff authentication stays isolated** from the customer Identity Service path (§12.3's Admin/Ops Service) — already established, restated here as a security principle in its own right, not merely a service-boundary convenience.
- **Rate limiting and lockout** on authentication endpoints specifically (§14.4), distinct from general API rate limiting (§11.2's Gateway) — brute-force protection deserves its own, stricter threshold.

### 14.12 Audit Requirements

**A genuine gap in §10.1, surfaced and resolved here rather than carried forward silently.** §10.1 defined `AuditLogEntry` as belonging to exactly one `Project` **or** one `Tenant`, never both — but authentication events (login success/failure, password reset, session revocation) are scoped to a `User`, not to any single Project or Tenant; a `User` might authenticate before selecting a Tenant context at all, or hold memberships in several. Forcing a login event onto a Project or a Tenant would be inaccurate, not just awkward.

**Resolution:** a distinct, lightweight **`AuthenticationEvent`** log — User-scoped, append-only, immutable (the same immutability reasoning as `AuditLogEntry`, §10.1) — separate from `AuditLogEntry` because authentication events have different retention and access-pattern needs (a security/compliance audience, typically, rather than a research-provenance one) and a different natural scope (User, not Project/Tenant). `AuditLogEntry` continues to cover membership grants/revocations and role changes (§10.1's `ProjectMembership`/`TenantMembership` audit notes are unaffected); `AuthenticationEvent` covers login, logout, password reset, and session revocation specifically.

### 14.13 Future External Identity Providers

A v2 capability, and the concrete proof that this section's design is extensible without a database redesign, as instructed: federated login (SSO/SAML/OIDC-style, protocol unnamed deliberately) is added as a new Infrastructure Layer adapter — conceptually an `IIdentityProvider` implementation (§12.1's Infrastructure extension-point pattern, reused here exactly as it was for the AI provider and content-platform provider in §12), translating an external identity assertion into an existing `User` + `TenantMembership`. **This changes only how a session is established (§14.2), never what a `User`, `Tenant`, or `Membership` is (§14.1, §10.1)** — the distinction §14.2 drew on purpose is what makes this extension free of schema change.

### 14.14 Migration Strategy for Enterprise Authentication

How a Tenant "graduates" from individual credential-based auth to institutional federation without a redesign:

1. **Authentication mode is Tenant-level configuration**, not a schema fork — a flag/setting on the `Tenant` record (credential-based vs. federated), read by the API Layer (§12.1) to select which Infrastructure adapter (§14.13) authenticates that Tenant's members. Adding federation to one Tenant has zero effect on any other Tenant's authentication mode.
2. **Identity linking, not duplication**: when a Tenant enables federation, existing individual `User` records are linked to the incoming federated identity by verified email (§14.5's verification is what makes this trustworthy) rather than a new `User` being created — a common, real migration failure mode (SSO rollouts silently forking accounts) named explicitly so it isn't repeated by omission.
3. **This is Infrastructure plus an Application-layer linking workflow, never a Domain change** (§12.1's layering, applied here directly) — consistent with the instruction's core requirement: individual → group → institutional → enterprise is a progression of Infrastructure adapters and Tenant configuration, not of the data model established in §10.

---

## 15. AI Integration Strategy

The complete AI architecture, not a description of LLM usage. Every decision below is derived from, and constrained by, everything already approved (§1–§14) — nothing here reopens the Vision, the Database Concept, the API/Backend/Frontend Architectures, or Authentication Strategy; it fills in the one layer those documents deliberately left for this pass.

### 15.1 Purpose of the AI layer

AI exists to help a researcher understand already-computed, immutable analysis output faster than reading raw results alone — nothing more. It serves the Vision's "Auditable" pillar (§1.2) by making results easier to interpret; it must never compete with the "Reproducible" pillar by becoming a second, informal source of findings alongside the Analysis Engine's actual output. An `InterpretationRecord` is commentary a researcher can cite as commentary — never a finding in its own right.

### 15.2 Architectural position inside the system

Exactly where §12's layered architecture already placed it, restated precisely rather than left implicit: the AI Interpretation Service (§11.2) is realized as an Application orchestrator (`RequestInterpretationOrchestrator`), a Domain policy (`InterpretationProvenance`, plus §15.17's new `InterpretationVerification`), and an Infrastructure adapter (`infrastructure.ai.llm_adapter`, implementing Domain-defined `IAIProvider`). It is a **consumer of Analysis Engine's output, never a peer to it** — it sits downstream only, with no path back into Analysis, Collection, or Reporting except the one-way citation relationship already established in §10 (Reporting reads existing `InterpretationRecord`s; it never asks for new ones). The frontend never communicates with an LLM directly; every request passes through the single API surface (§4.1, §11.2) exactly like every other request in the system, with no side channel.

### 15.3 AI Service responsibilities

Accept a request scoped to exactly one `AnalysisRun` (or, v2, a follow-up within an existing interpretation thread — §15.20); confirm eligibility (§15.5 step 4); construct context from that run's persisted, immutable output only (§15.15); assemble a versioned prompt (§15.6–§15.7); call a versioned model via an adapter (§15.8, §15.19); validate the response's claims against source data before it is ever shown as fact (§15.17–§15.18); persist the result as a new, immutable `InterpretationRecord` carrying complete provenance (§15.11); return it.

### 15.4 AI Service boundaries

What it never does, several of these restating AIG-001/003 in this document's own terms rather than leaving them only in §9/§11: never computes, adjusts, or supplies analytical results (AIG-001 Rule 1); never mutates `AnalysisRun`, `CollectionRun`, or any existing `InterpretationRecord` (AIG-003); is never invoked by Reporting Service, which only ever reads an already-created record by ID (§11.2, unchanged); is never reachable directly from the frontend — only through the API Gateway (§4.1); has no authority to accept, reject, or validate a scientific result — that authority doesn't exist anywhere in this system, by any actor, which is precisely why AI cannot have it either; never runs against an `AnalysisRun` that is not `completed` (enforced at the Domain layer, not merely checked at the API).

### 15.5 AI request lifecycle

Diagram above; stages named precisely:

1. **Frontend request** — SCR-ANLY-04 (§13.7.F), triggered by any role with view access to the parent `AnalysisRun`.
2. **API Gateway** — authenticates, delegates authorization to Identity Service's `CheckAuthorization` (§11.2, §14.10).
3. **Application orchestrator** — `RequestInterpretationOrchestrator` sequences the remaining steps; contains no business rules itself (§12.1).
4. **Domain eligibility check** — confirms the target `AnalysisRun.status == completed`; refuses otherwise, unconditionally.
5. **Context construction** — assembles the prompt payload from the `AnalysisRun`'s persisted output and its pinned `CollectionRun`'s manifest hash (§15.15) — never a live query, never anything mutable.
6. **AI provider adapter** — Infrastructure Layer, implements `IAIProvider`; the only component in the entire system permitted to call an external AI provider (§12.1).
7. **Claim validation** — the response is checked against source data before it is trusted (§15.17–§15.18, AIG-004).
8. **Immutable persistence** — a new `InterpretationRecord` is created (create-only repository, §12.1); `InterpretationCreated` is published (§11.2); the record is returned to the frontend, which renders it exactly as §13.7.F specifies — never editable, provenance always visible.

### 15.6 Prompt architecture

Prompts are versioned, structured artifacts — never ad hoc strings assembled inline in application code. **`PromptTemplate`** *(new conceptual entity, not previously defined in §10.1 — added here with the same discipline used for `ServiceAccountToken`/`AuthenticationEvent` in §14, not silently assumed)*: belongs to an interpretation scope (today, "explain this AnalysisRun's results"; future scopes follow new `AnalysisType`s, §5's pluggable design extended here rather than re-argued). A prompt sent to a provider is always the composition of exactly three things: the `PromptTemplate`'s fixed instruction text, the constructed context (§15.15), and — v2 only — a user-supplied follow-up question, itself scoped to the same `AnalysisRun`.

### 15.7 Prompt versioning

Every `PromptTemplate` carries an immutable version identifier. Editing a template creates a new version; it never mutates an existing one in place — the identical versioning discipline §10.1 already applied to `VerticalTemplate` and `AnalysisType`, reused rather than reinvented. `InterpretationRecord`'s provenance bundle (§15.11) always cites the exact `PromptTemplate` version used, which is what makes "prompt version... always recorded" (this turn's constraint) a structural guarantee rather than a documentation convention.

### 15.8 Model versioning

The AI provider's model identity and version are captured per request, already required by AIG-001/003. One honest limitation stated plainly rather than glossed over: **model versioning is only partially within this platform's control.** A `PromptTemplate` version is ours to freeze forever; a third-party model version is not — providers deprecate and retire model versions on their own schedule. When a cited model version becomes unavailable upstream, the correct behavior is to preserve the original `InterpretationRecord` exactly as recorded (immutable, per AIG-003) while marking its "regenerate" action unavailable for that specific record — **never silently substituting a different model's output and presenting it as the same interpretation.** This is the concrete reason §15.10 distinguishes provenance reproducibility from output determinism instead of promising both unconditionally.

### 15.9 Interpretation pipeline

The concrete data flow, stages 5–8 of §15.5 expanded: persisted `AnalysisRun` output → context construction (size/cost-bounded, §15.14) → prompt assembly (§15.6) → provider call (§15.19) → raw response → claim validation / hallucination check (§15.17–§15.18) → `InterpretationRecord` persistence. Every arrow in this pipeline reads from something immutable or produces something immutable; nothing in the middle is a place a mutable, uncontrolled state could enter.

### 15.10 Reproducibility strategy

Stated precisely, because the honest answer has two parts, not one: **provenance reproducibility is always guaranteed, structurally** — given any `InterpretationRecord`, the exact `AnalysisRun`, `CollectionRun` manifest hash, `PromptTemplate` version, model version, and context-construction version (§15.15) that produced it are always recoverable, by construction (§15.11). **Output determinism is best-effort, not promised** — most AI providers do not guarantee byte-identical output even when re-run with pinned model version and low/zero temperature; "reproducible whenever technically possible" (this turn's own constraint, adopted verbatim as the honest standard) means regenerating against the same inputs is expected to be *semantically consistent*, not necessarily textually identical. Overclaiming determinism a provider doesn't actually offer would be a worse failure than stating the limitation directly — consistent with the Vision's own "Auditable" principle, which depends on the platform's claims being true, not merely reassuring.

### 15.11 Traceability

The complete provenance bundle every `InterpretationRecord` carries, immutably, listed precisely (extending AIG-001 Rule 2 / AIG-003's requirement with the specific fields this deliverable's detail makes necessary, not redefining either): `AnalysisRun` ID; `CollectionRun` ID (transitive, via the pinning rule, §10.1); Reproducibility Service manifest hash (§12.2); `AnalysisType` + version (§10.1); `PromptTemplate` ID + version (§15.7); **context-construction strategy version** (§15.15 — named explicitly here rather than left to an implied "execution metadata" catch-all, since it changes what the model sees exactly as a prompt-template change does, and deserves the same explicit treatment); AI provider identity + model version (§15.8); request timestamp; response latency; token counts where available (§15.14).

### 15.12 AI audit requirements

`InterpretationRecord` creation is already a `Project`-scoped `AuditLogEntry` event (§10.1). One addition, surfaced rather than assumed: **a failed AI request produces no `InterpretationRecord`** (nothing to create), but should still generate an audit event — for cost tracking (§15.14) and abuse monitoring, not just successful interpretations. Failure-path auditing is handled by the orchestrator (§15.5 step 3) directly writing an audit entry on failure, independent of whether persistence (step 8) is ever reached.

### 15.13 Failure handling

A named taxonomy, not one undifferentiated "AI failed" state: **provider unavailable/timeout** (transient, safe to retry as an *identical* re-attempt — never a silently modified one, which would corrupt the provenance-honesty §15.8 depends on); **malformed/unusable provider response** (a validation failure, not auto-retried without a change in circumstance); **provider-side rate limit/quota** (distinct from this platform's own cost controls, §15.14); **provider content-policy refusal** (a legitimate "no answer," surfaced honestly to the user, never hidden or reframed as a generic error). Every case terminates in the explicit failure state already specified at the screen level (§9.3, §13.7.F, §13.10) — never a silently degraded or fabricated-looking answer, restated here as the backend-side half of that same rule.

### 15.14 Cost management

AI requests cost money per call; this needs architecture, not just a billing afterthought. Pre-call: context size is bounded before a request is sent (§15.15), giving a request-level cost estimate. Post-call: token counts and latency are recorded (§15.11) as the metering input a future Billing & Licensing extension (§8.7, §12.3) would consume — a connection point named here, not designed further, since Billing itself isn't being redesigned in this pass. Plan-tier volume limits per Tenant (the same role/plan-gating pattern already used for NAV-10/NAV-12, §9.2/§13.3) are the primary lever for cost control. **One explicit constraint, because it's the obvious-looking wrong answer:** cost control must never be achieved by caching or deduplicating identical requests into a single shared result — that would directly violate AIG-003, which requires every request to produce its own, separately-provenanced record even against unchanged input. Cost is controlled *before* a request is made (size limits, rate limits, plan tiers), never by silently reusing a prior one.

### 15.15 Context construction

The subset of an `AnalysisRun`'s output actually sent to the provider — necessary because real analysis output (hundreds of topics, thousands of comments) cannot simply be dumped into a prompt against cost and provider context-window limits. Context construction is a deterministic, **versioned** selection/summarization strategy (§15.11's newly-named provenance field) — versioned for the same reason a `PromptTemplate` is: changing *how* context is selected changes what the model can possibly say, which affects reproducibility exactly like changing the prompt text would, so it cannot be silently free-floating, unversioned logic. Reads only from persisted, immutable `AnalysisRun` output — never a live or mutable query, restating AIG-001's "consumes immutable outputs" constraint at this specific, concrete point in the pipeline.

### 15.16 Citation strategy

An interpretation's claims should be traceable to specific result elements, not just prose that asserts a connection. The response is expected to reference structured identifiers (a specific topic ID, a specific video/sentiment data point) rather than only natural-language description; these references are extracted and validated (§15.17) and stored as structured metadata on the `InterpretationRecord`, not left embedded only in free text — this is what lets the frontend (§13.7.F) render "this claim relates to this specific data point" as a real, backend-verifiable link rather than a cosmetic footnote, and is the concrete mechanism FG-002 (§13.14) depends on for AI content specifically: a citation must point to a backend-verifiable ID, not merely prose that claims one.

### 15.17 AI guardrails

The full guardrail set already governing this layer, consolidated here rather than re-derived: **AIG-001** (§9.4, AI is never the source of truth), **AIG-003** (§11.4, AI operations are stateless, full provenance always), **BKG-001** (§12.5, business rules stay in Domain/Application — the AI adapter itself contains none), **FG-001/FG-002** (§13.14, the frontend never reasons and only presents reproducible backend state). One new, genuinely distinct constraint emerges from this deliverable's depth and is formalized as **AIG-004** (§15.21) — everything else considered in this pass (frontend never calling an LLM directly; all requests through the API layer) is already fully entailed by the single-API-surface decision (§4.1/§11.2) and FG-001 together, and does not need a new ID of its own; issuing one would cheapen the register rather than strengthen it.

### 15.18 Hallucination prevention

The mechanism behind AIG-004 (§15.21): a post-response validation step, distinct from and complementary to prompt-level mitigation (instructing the model to discuss only the provided context is a **§15.6 prompt-architecture concern**, not a substitute for verification — defense in depth, the same pattern already used for authentication in §14.11). Every structured citation (§15.16) in a response is checked against the `AnalysisRun`'s actual persisted output. A citation that cannot be matched is **flagged as unverifiable, not silently stripped and not silently accepted** — silently removing content would itself be an undisclosed alteration of what the model returned, which is its own kind of dishonesty about provenance; the correct response is to surface the claim as explicitly unverified, preserving an honest record of exactly what the model said and exactly what could and couldn't be confirmed against the data.

### 15.19 Multi-provider architecture

Already structurally supported by `IAIProvider` (§12.1) — Domain defines the contract, Infrastructure supplies implementations, and nothing above Infrastructure knows or needs to know which provider answered. Multiple implementations can coexist (different vendors, cost tiers, or redundancy), and **which model/provider backs a given `PromptTemplate` is itself versioned catalog configuration** (§15.6–§15.7), not a hardcoded adapter choice — the same pattern `VerticalTemplate`/`AnalysisType` already established for extensibility (§10.1, §5) applied to model selection specifically. Failover, if implemented, must record the *actual* provider/model that answered in provenance (§15.11) — never the originally-intended one dressed up as if nothing changed; a silent substitution disguised as the original request would violate AIG-001/AIG-003 as directly as an outright fabricated answer would.

### 15.20 Future extensibility

The v2 conversational Research Assistant (flagged since §8.5) extends this exact model without a redesign: a conversation is a sequence of individually immutable `InterpretationRecord`s, each still bound to one `AnalysisRun` (§10.1's pinning, unchanged), linked by an additive "prior interpretation" reference for threading — a new field, not a new entity, not a schema fork. Future `AnalysisType`s bring their own `PromptTemplate`s through the same catalog mechanism (§15.6) automatically; no new integration pattern is needed per new analysis capability, mirroring exactly how §5 designed `AnalysisType` extensibility in the first place.

### 15.21 AIG-004 — AI Claims Must Be Content-Verifiable Against Source Data (new)

*(A genuinely new architectural constraint, not a restatement of AIG-001 or AIG-003 — AIG-001 governs AI's structural role in the system; AIG-003 governs statefulness and provenance; AIG-004 governs the truthfulness of what an interpretation actually asserts. AIG-002 remains unassigned, per instruction, and is not invented here either.)*

| Field | Value |
|---|---|
| ID | AIG-004 |
| Title | AI-generated interpretations must be content-verifiable against the source AnalysisRun output |
| Status | Formalized, binding on AI Interpretation Service and any future extension |
| Applies to | AI Interpretation Service, `InterpretationRecord` (`kind: ai_generated`), the Claim Validation stage (§15.5 step 7) |
| Depends on | AIG-001 (AI is not the source of truth — AIG-004 is what makes that enforceable at the content level, not just the architectural level); AIG-003 (provenance the validation step relies on) |

**Rule.** Any specific, checkable claim an AI-generated interpretation makes about the underlying analysis — a topic label, a statistic, a data point — must be matched against the `AnalysisRun`'s actual persisted output before the interpretation is returned as complete. A claim that cannot be matched is flagged as unverifiable, not silently removed and not silently presented as fact. This is the architectural difference between "AI never computes results" (AIG-001, a structural guarantee about where authority lives) and "AI does not get to say false things about results that do exist" (AIG-004, a content guarantee about what's actually asserted) — the system needs both; one does not imply the other.

---

## 16. Deployment Architecture

This section defines how the architecture approved in §1–§15 is deployed, operated, and executed. It is a *logical* deployment architecture: it defines deployable units, their responsibilities, and the network/trust boundaries between them — not a specific cloud vendor, container runtime, or orchestration product. Where a name is needed for a capability, it is described by what the capability must do ("a structured, transactional datastore," "a blob/object store," "a secret store"), not by which product provides it. Which concrete technology realizes each unit is a **Technology Stack** decision, deliberately deferred and out of scope here — exactly as a Database Concept (§10) was kept separate from any specific database product, and a Frontend Architecture (§13) was kept separate from any specific JavaScript framework.

### 16.1 Deployment philosophy

Two commitments govern everything below:

1. **Logical layering (§12) is a dependency discipline, not a deployment mandate.** BKG-001 ("business rules belong exclusively to the Application and Domain layers") is enforced by *dependency direction in code* — Infrastructure and Persistence depend on Domain-defined interfaces, never the reverse. That enforcement mechanism does not require the six layers to run as six separate network services. Collapsing multiple logical services into one physical deployment unit does not weaken BKG-001, FG-001, or any layering guarantee already established; splitting them into separate physical services later is a *scaling* decision, not a prerequisite for architectural compliance. This document does not assume, and does not require, a microservices topology.
2. **Self-hosted and cloud are both first-class, permanently.** §1.5 already established that the buyer includes university IT departments who may require on-premises deployment for procurement or data-residency reasons, alongside buyers who prefer a managed cloud deployment. Every decision below is written so both are satisfiable by the same logical architecture — no unit described here presumes a specific cloud provider's managed service exists.

### 16.2 Logical deployment architecture

Six logical tiers, derived from the module and service boundaries already approved (§4, §8, §11, §12):

| Tier | Responsibility | Derived from | v1 physical grouping |
|---|---|---|---|
| **Edge Tier** | The single public-facing entry point; routes/authenticates every external request | §11 API Gateway service contract | Always its own deployable unit — this *is* the "single API surface" decision (§4.1, §11.2), physically enforced |
| **Application Tier** | Identity, Reproducibility, Collection, Analysis, Reporting, Billing, Admin/Ops service contracts (§11.2) — Application + Domain + Infrastructure/Persistence code for each | §11.2, §12.1 | Co-deployed as one unit for v1 (see §16.6) |
| **AI Interpretation Tier** | The AI Interpretation service contract (§11.2) — the only unit permitted to call an external AI provider | §11.2, §15.4 | Its own deployable unit even in v1 (see §16.8) |
| **Worker Tier** | Asynchronous execution of Collection, Analysis, and Export jobs | §12.2 `IJobDispatcher`, §13.9 long-running job UX | Its own deployable unit even in v1 (see §16.9) |
| **Data Tier** | The structured datastore (§10 entities) and the blob/file store for raw content and artifacts | §10, §12.1 Persistence Layer | Two logically distinct stores, physically may be co-located |
| **Frontend Delivery Tier** | Serves the compiled presentation-layer artifacts (§13) to browsers | §13.1–§13.13 | Independent from every backend tier |

This is not six new decisions — it is the runtime expression of decisions already made: the single API surface (§4.1), the AI Service boundary (§15.4), the job-dispatch abstraction (§12.2), and the Persistence Layer's own raw-content/metadata split (§12.1).

### 16.3 Runtime topology

Request flow, by path:

- **Static asset requests** (loading the app shell, §13.2): browser → Frontend Delivery Tier directly. No backend involvement.
- **Synchronous API requests** (reads, and writes that complete quickly, per §11.2's sync/async classification): browser (via frontend-issued calls) → Edge Tier → Application Tier → Data Tier → response.
- **Asynchronous job requests** (`StartCollectionRun`, `StartAnalysisRun`, export generation, §11.2/§13.9): browser → Edge Tier → Application Tier (validates, creates the run record, enqueues) → returns immediately → Worker Tier picks up the job asynchronously → Worker Tier → Data Tier (and, for interpretation jobs, → AI Interpretation Tier) → status polled or pushed back through Edge Tier.
- **AI interpretation requests**: Application Tier or Worker Tier → AI Interpretation Tier (internal call only) → external AI provider (outbound) → response persisted as a new `InterpretationRecord` (§10.1, §15) via the Data Tier.

No tier other than the Edge Tier and the Frontend Delivery Tier is reachable from outside the private network boundary (formalized in §16.24 as DAG-001). The Data Tier in particular has no route to the public internet in either direction.

### 16.4 Application components

The concrete list of deployable units implied by §16.2–§16.3:

| Component | Tier | Contains |
|---|---|---|
| API Gateway | Edge | Routing, request authentication (§14.2), rate limiting, request-correlation assignment (§16.13) |
| Core Application Service | Application | Identity, Reproducibility, Collection, Analysis, Reporting, Billing, Admin/Ops (§11.2) — six-layer internal structure per §12.1 preserved as package boundaries |
| AI Interpretation Service | AI Interpretation | AI Interpretation service contract (§11.2), the AI provider adapter (§15.4), `PromptTemplate` resolution (§15) |
| Background Worker(s) | Worker | `IJobDispatcher` consumers (§12.2) executing Collection/Analysis/Export jobs |
| Structured Datastore | Data | Entities in §10.1 |
| Blob/File Store | Data | Raw collected content, generated artifacts (§16.11–§16.12) |
| Frontend Bundle | Frontend Delivery | Compiled presentation-layer artifacts (§13) |

### 16.5 Frontend deployment

The Frontend Delivery Tier serves compiled, static presentation-layer artifacts (§13.1's Presentation Layer). Whether those artifacts are produced at build time, request time, or purely client-side is a Technology Stack decision (out of scope here, per the framework-agnostic commitment already made in §13). What *is* architectural: the frontend deployment unit is **independent of every backend deployment unit** — it can be redeployed without redeploying the Application, AI, Worker, or Data tiers, and vice versa. This independence is only safe because §13.1 already committed the frontend to talking to the Edge Tier through a versioned API contract (§11.3); version compatibility between a deployed frontend bundle and the deployed API Gateway is what makes independent release cadences safe, not a coincidence of the topology.

### 16.6 Backend deployment

The Core Application Service (§16.4) may be deployed as a single physical unit in v1 — this is the pragmatic reading of Deployment Philosophy Commitment 1 (§16.1). The internal boundaries between the six services it hosts (Identity, Reproducibility, Collection, Analysis, Reporting, Billing, Admin/Ops) and between the six architectural layers within each (§12.1) remain enforced by code-level dependency direction regardless of this physical grouping. Splitting any of these into an independently-deployed physical service later — because it needs independent scaling, independent release cadence, or stronger isolation — requires no architectural change, only a deployment-topology change, because the service contracts (§11.2) were already defined as if they were independent.

For horizontal scaling, Application Tier instances must be stateless between requests: no in-process session state beyond what is re-derivable from the access token and the Data Tier (consistent with §14.3's session model), so any instance can serve any request behind the Edge Tier.

### 16.7 Database deployment

The Data Tier's structured store must be a transactional datastore capable of enforcing the relationships, immutability constraints, and versioning behavior specified per-entity in §10.1 — in particular, the immutability of `InterpretationRecord`, `CollectionRun`, and `AnalysisRun` snapshots must be enforceable at the datastore level, not just by application-code discipline, since §10.1 already treats immutability as a hard entity property. A single logical datastore is sufficient for v1; read-replica or partitioning strategies are a scaling concern (§16.21), not a v1 requirement. Backup and disaster-recovery requirements for this store are addressed in §16.16–§16.17, not here.

### 16.8 AI service deployment

The AI Interpretation Tier is deployed as its own logical unit, distinct from the general Application Tier, for two reasons: (1) it is the *only* component permitted a network path to an external AI provider — isolating it makes that boundary enforceable at the network level, not just the code level (§15.4, formalized as DAG-001 in §16.24); (2) AI calls have latency, cost, and failure characteristics fundamentally different from database-backed request/response calls (§15.13, §15.14's cost-control requirement), so this tier needs independent scaling and throttling policy that would be wrong to apply to the rest of the Application Tier. The AI Interpretation Tier has outbound-only network access to approved AI provider endpoints; no AI provider is ever permitted to initiate an inbound connection into any part of this system.

### 16.9 Background workers

The Worker Tier executes every job dispatched through `IJobDispatcher` (§12.2): Collection runs, Analysis runs, and Export generation (§13.9's long-running-operation UX is the frontend-visible half of this same mechanism). It is deployed and scaled independently of the Application Tier because job duration (minutes to hours for a Collection run, per the existing engine's real-world behavior) is a fundamentally different resource-allocation problem than request/response latency; co-locating them would let a backlog of long jobs degrade interactive API responsiveness, which would violate no formal decision but would be a straightforward operational mistake this topology avoids by design.

### 16.10 Job execution architecture

Jobs must be resumable, not merely retryable: the existing engine's checkpoint/manifest system (already integrated at the architecture level in §12.2, §12.4) is what allows a Worker Tier instance to crash or restart mid-run without losing progress or corrupting a `CollectionRun`/`AnalysisRun`'s provenance chain. Given that checkpointing already provides resumability, this architecture recommends **at-least-once job dispatch with idempotent handlers**, not exactly-once delivery infrastructure — the idempotency-key requirements already placed on `StartCollectionRun` and `StartAnalysisRun` (§11.3) exist precisely so that a duplicate dispatch is safe rather than something that must be prevented at the messaging layer. This is a deliberate choice against a more expensive guarantee that the architecture does not need.

### 16.11 File storage strategy

Raw collected content (comment text, video metadata payloads) is stored in the Data Tier's blob/file store, not the structured datastore — this is the deployment-level realization of the split already flagged in §12.1's Persistence Layer note. The store is described as a content- or path-addressable blob store; which product provides it is a Technology Stack decision. This store has no direct public-internet exposure; it is reachable only from the Application and Worker tiers.

### 16.12 Artifact storage

Distinct in lifecycle from §16.11: generated Exports (§10.1's `Export` entity, immutable once produced) live in the same class of storage but a separate namespace, because their retention lifecycle is tied to Report and Project lifecycle rather than to Collection/Analysis provenance. Tenant-level retention policy for artifacts remains an open item, consistent with the gap already flagged and left open in §10.2 — this document does not resolve it, only confirms where it would be enforced (at the Data Tier's artifact namespace, not the structured store).

### 16.13 Logging architecture

Every tier (§16.2) uses the structured logger already established in §12.2/§12.4 (`infrastructure.logging.structured_logger`, a direct wrap of the existing engine's `core/logging.py`). The deployment-level requirement this section adds: logs from every tier must be centrally aggregated and correlatable, because a single user action can span the Edge Tier synchronously and the Worker/AI tiers asynchronously — without a shared request-correlation identifier threaded through Edge → Application → Worker → AI, tracing a single failure across tiers would be impossible. This correlation identifier is assigned at the Edge Tier (§16.4) and propagated through every downstream call, including asynchronous job dispatch. No plaintext credentials appear in any tier's logs — §14.11 already established this for authentication events; this section extends the same rule to logging across the full topology, not just Identity.

### 16.14 Monitoring

Distinct from logging: each tier exposes operational metrics appropriate to its role — request latency and error rate for the Edge and Application tiers; queue depth and job duration for the Worker Tier; request cost, latency, and failure rate for the AI Interpretation Tier specifically, since §15.14 already requires cost visibility as an architectural concern, not just an ops nicety. Which monitoring product ingests these metrics is a Technology Stack decision; that each tier must expose them is architectural.

### 16.15 Health checks

Every deployable component (§16.4) exposes two distinct signals: **liveness** (is the process running at all) and **readiness** (can it currently serve traffic — e.g., does it have a working connection to the Data Tier). Conflating the two causes exactly the failure mode this distinction prevents: a component that is alive but unable to reach its dependencies should be removed from rotation, not restarted.

### 16.16 Backup strategy

Backup is not a generic operational best practice here — it is the direct mechanical requirement of a product commitment already made. §7's User Journey stage 7 (Project Archival) commits to a project being "permanently retrievable... including by a peer reviewer years later." A backup and retention policy for the Data Tier (both the structured store and the blob/artifact store) must be designed to honor that commitment specifically, not derived independently from generic ops practice. This means retention windows for backups must be long enough to plausibly cover the peer-review and post-publication timelines academic research operates on, not the shorter windows typical of consumer SaaS.

### 16.17 Disaster recovery

Recovery from a Data Tier failure must restore not only data but **provenance**: a restored system must still be able to verify that an `AnalysisRun`'s manifest hash and its chain back to a specific `CollectionRun` are intact (§10, §15's reproducibility guarantees). A recovery that restores rows but loses the ability to verify this chain has not actually satisfied AIG-001's traceability requirement or the reproducibility commitments in §1.2 and §15.10 — disaster recovery validation must include re-verifying at least one restored `AnalysisRun`'s provenance chain, not just confirming the database is queryable again.

### 16.18 Configuration management

Per §12.2's `infrastructure.config.settings_loader`: configuration is environment-specific (§16.20) but must never encode business rules. BKG-001's boundary applies here directly — *which* AI provider endpoint to call is configuration; *whether* an `AnalysisRun` is currently valid to start is not, and must never be expressed as a configuration toggle. This is the same distinction §12.5 already drew between the Application/Domain layers and everything else, restated as a constraint on what configuration is permitted to contain.

### 16.19 Secret management

Distinct from §16.18: credentials — database connection strings, AI provider API keys, payment-processor credentials (§11.2 Billing service), token-signing keys (§14.2) — are never stored in source control, in plaintext configuration, or in logs. §14.11 already prohibited plaintext credentials in authentication logs specifically; this section generalizes that prohibition across every tier and every credential type. A secret-store capability (name withheld deliberately — a Technology Stack decision) is required wherever any tier needs a credential at runtime; credentials are injected into a running component, never baked into a deployable artifact.

### 16.20 Environment strategy (Development / Staging / Production)

A minimum of three environments, each capable of exercising the full topology in §16.2–§16.4 at reduced scale. This is not solely a performance-testing concern: because AIG-001, AIG-003, AIG-004, and the reproducibility guarantees in §10 and §15 are *correctness* guarantees, not performance ones, Staging must be populated with realistic-enough data to actually exercise the manifest-hash/provenance chain (§9.5, §15) before a Production release — a Staging environment that only smoke-tests "does the service start" does not validate the guarantees this platform's credibility depends on.

### 16.21 Scaling strategy

Each tier scales along its own dimension, independently:

| Tier | Scales with | Notes |
|---|---|---|
| Edge | Concurrent request volume | Stateless by construction (§16.6) |
| Application | Concurrent request volume | Stateless (§16.6); horizontal scaling requires no session affinity |
| Worker | Job volume and duration | Independent of Application Tier load (§16.9) |
| AI Interpretation | Interpretation request volume, *bounded by cost policy* | §15.14's cost-control requirement means this tier may throttle below raw demand deliberately — a different scaling logic than "add capacity until load is served" |
| Data | Read/write volume | Read-replica or partitioning strategies deferred to implementation; not a v1 requirement (§16.7) |
| Frontend Delivery | Static request volume | Trivially horizontal; no state |

### 16.22 High availability assumptions

An honest, evidence-grounded call consistent with the MVP-sequencing discipline already established in §1.3 and §3: v1 does **not** require multi-region active-active availability. The actual usage pattern — researchers running analyses during working hours, not a continuously-online operational system — does not justify the cost and complexity of multi-region HA at the beachhead stage. v1's assumption is single-region deployment with redundant instances *within* that region for each tier in §16.2. Multi-region HA is deferred to the v2+/enterprise stage flagged in §3's MVP-sequencing table and §14.14's enterprise-migration pattern — this is a restatement of an already-established sequencing discipline applied to availability specifically, not a new decision.

### 16.23 Security boundaries

Consolidating boundaries established individually across §16.3–§16.9 into one statement: the Edge Tier and Frontend Delivery Tier are the only components reachable from the public internet. The Application, AI Interpretation, Worker, and Data tiers are reachable only from within the private network boundary — from the Edge Tier inbound, or from each other. The AI Interpretation Tier is the only component with outbound access to external AI providers (§16.8); no AI provider has any inbound path. Secrets (§16.19) are isolated from application code and from logs (§16.13). Authentication remains centralized in the Identity service within the Application Tier (§14.2) even across a multi-component deployment — no other component performs independent authentication of its own; this is the deployment-level guarantee that makes §14.2's "centralized" claim actually true at runtime, not just true of the code's logical structure.

### 16.24 Deployment governance

**DAG-001 — Network topology must enforce, not merely assume, the access boundaries already approved at the application layer.**

Specifically: (1) no network path may allow a client to reach the Application, AI Interpretation, Worker, or Data tiers except through the Edge Tier (the physical enforcement of the "single API surface" decision in §4.1/§11.2); (2) no component other than the AI Interpretation Tier may be granted outbound network access to an external AI provider endpoint (the physical enforcement of the AI Service boundary in §15.4). This is formalized as a distinct governance decision, separate from the application-level decisions it enforces, because a deployment can technically satisfy both of those decisions at the code level while a misconfigured network still permits direct access — e.g., a database left reachable from the public internet violates DAG-001 even though no application code was changed. DAG-001 is a checkable property of the *deployment*, not of the *source code*, which is why it did not already exist as one of the application-layer decisions it now backs.

No other new governance decisions are introduced in this section. Candidates considered and deliberately not issued as new IDs: "workers must be idempotent" (already fully entailed by §11.3's idempotency-key requirement plus §16.10's resumability discussion — restating it as a new ID would cheapen the register); "logs must not contain credentials" (already established in §14.11, generalized in §16.13, not a new constraint). AIG-002 remains unassigned and is not fabricated here.

### 16.25 Future cloud portability

Because every tier in this section is described by responsibility (§16.2–§16.4) rather than by product, cloud portability is a consequence of how this document is written, not an additional feature to build later. The same logical architecture can be realized as: fully self-hosted on institution-owned hardware (the real procurement scenario flagged in §1.5); a single managed-cloud provider's services; or a portable, provider-movable deployment. This document deliberately does not choose among these — that choice, and the specific technology that realizes each tier, belongs to the future **Technology Stack** decision, kept out of scope here exactly as instructed.

---

## 17. Product Evolution & Commercialization Architecture

This section closes the architecture-first phase. It does not add architecture — it explains how the architecture already approved in §1–§16 carries the product from MVP to a mature, sustainable platform. Every mechanism referenced below already exists in a prior section; this document's job is to show which lever each stage of growth pulls, not to design a new one. Where a genuine open fork exists — the way DAD-001 (branding) was a genuine, undecided fork rather than something to pick silently — it is named as such rather than resolved here. This is not a financial plan: no numbers, no revenue projections, no cost structure appear below. It is the architectural-strategic connective tissue between "the platform as designed" and "the platform as it will be sold and operated over time."

### 17.1 Product evolution vision

The vision statement in §1.2 already describes the end state: a reproducible, auditable research platform that generalizes from the influencer/creator-content wedge to computational communication research as a category, once that wedge is commercially validated. §1.3's three-stage sequencing (Beachhead → Expansion → Horizontal) is not revised here — it is the spine this entire section elaborates. Nothing in this section changes *what* the platform becomes; it specifies *how* the already-approved architecture is switched on, stage by stage, to become it.

### 17.2 MVP definition

The MVP is not redefined here. §3.2 already defines it, and §3's scoring table already draws the v1 / v1.x / v2+ line item by item. This section takes that boundary as fixed input: v1 is a single-researcher-or-small-lab, single-vertical (YouTube financial-influencer research), fully reproducible research tool, deployable either self-hosted or as hosted SaaS (§16), with the ten modules of §4 and the 22 screens of §9.3 as its complete v1 surface. Everything below describes what happens *after* that boundary is reached, not a redefinition of it.

### 17.3 Post-MVP evolution

§1.3's "Expansion (v1.x–v2)" stage activates architecture that already exists but is dormant at v1 scale: the Tenant/Project two-level model (§10.1, §14.7) already supports multiple Projects per Tenant, but v1's target user typically runs one; the Institution Owner/Admin and Lab/Department Manager roles (§6) already exist in the permission matrix but have no multi-project surface to manage yet; cross-project comparison, flagged explicitly in §7.3 as *not* a v1 journey stage, is the first genuinely new user-facing capability this stage adds. Post-MVP evolution is therefore primarily a matter of building new screens and reporting views against entities and roles that already exist, not extending the Database Concept or the API contracts.

### 17.4 Vertical expansion strategy

"Vertical" here means *collection platform* — YouTube today, TikTok/Instagram/X later, per §1.3's horizontal-expansion step. The mechanism for this is already built: the `providers/platform/` abstraction boundary (§1.1, §1.3) is not YouTube-specific in the current codebase, and the Collection service contract (§11.2) is written against that abstraction rather than against YouTube specifically. Adding a platform is adding a new provider adapter behind an existing Infrastructure Layer interface (§12.1) — it does not touch the Application or Domain layers, and it does not require a new service contract. This is BKG-001 doing exactly the job it was designed to do: a new data source is infrastructure, not business logic.

### 17.5 Multi-domain research strategy

Distinct from §17.4: "domain" means *subject matter* — financial-influencer research today, political or health communication later, per §1.3's step 3. The mechanism is the Vertical Template concept introduced in §5 specifically to decouple domain-specificity from the data model, plus the `AnalysisType`-as-plugin pattern (§5, §10.1). A new research domain is a new `VerticalTemplate` and a new set of `AnalysisType` entries instantiated against the existing `Project` aggregate (§10.1) — not a new aggregate, not a new database shape. Platform expansion (§17.4) and domain expansion (§17.5) are independent axes and can be combined freely (e.g., political-communication research on TikTok) without either one requiring the other.

### 17.6 Academic vs. commercial editions

There is one architecture, not two. "Edition" is a licensing/entitlement distinction expressed through the `Subscription` entity (§10.1) and the role/permission matrix (§6.1), not a fork in the codebase or the database schema. An "Academic" edition and a "Commercial" edition differ in which modules a `Subscription` entitles a `Tenant` to (§10.1's Subscription already models tier), not in which modules exist. This preserves §1.5's explicit instruction that commercial-grade should not be read as "enterprise SaaS on day one" — the same instance of the platform can serve a single grant-funded researcher and a paying institutional lab from the same deployment, distinguished only by entitlement data, not by separate builds.

### 17.7 Licensing strategy

This is a genuine open fork, not a decision to make silently — the same discipline DAD-001 required for branding applies here. Whether the platform ships as source-available/open-core (self-hosted deployments run the full or near-full codebase, SaaS sells hosting and convenience) versus fully proprietary (self-hosted deployments require a commercial license) has real downstream consequences for §17.13's Marketplace strategy, for community contribution, and for how credible the self-hosted option in §16 actually is to a university IT buyer. The architecture in §1–§16 is compatible with either branch — nothing about the Database Concept, API, or Deployment Architecture presumes a license model — so this fork is recorded and deferred rather than picked:

**DAD-002 — Source-availability / licensing model.** Deferred. Depends on: resolution of DAD-001 (branding affects how a public repository would be perceived) and a go-to-market decision outside this document's scope. Safeguard: no architectural decision made in §1–§16 depends on a specific answer to DAD-002; both branches are satisfiable by the current design.

### 17.8 Deployment models

§16 already specifies the technical shape of self-hosted and SaaS deployment in full — this section only maps those technical models onto product offerings. Three product-facing deployment models follow directly from §16 without any redesign: **Hosted SaaS** (the operator runs all six tiers of §16.2, tenant isolates via §14.7); **Self-hosted** (an institution runs the same six tiers on its own infrastructure, per §16.1's portability commitment); **Hybrid** (an institution self-hosts the Data Tier for data-residency reasons while consuming the AI Interpretation Tier or Application Tier as a hosted service) — the tier-level decomposition in §16.2 is precisely what makes a hybrid split possible without inventing a fourth deployment architecture.

### 17.9 SaaS roadmap

v1: single hosted deployment, one `Tenant` typically mapping to one lab or individual (§10.1, §14.7). v1.x: multi-project institutional tenants activate (§17.3), Billing service (§11.2) begins metering at the Tenant/seat level rather than a flat individual rate. v2+: the multi-region high-availability posture explicitly deferred in §16.22 becomes relevant once SaaS tenant count and geographic distribution justify it — §16.22 already named this as the correct trigger, not an arbitrary later decision.

### 17.10 Self-hosted roadmap

The explicit constraint that existing CLI capabilities become internal platform services, not discarded, is realized directly through the API-first design already in place: every CLI operation the current engine supports maps to an Application-Layer use case that is now also exposed through the API Gateway's service contracts (§11.2, §12.1). A self-hosted, single-researcher deployment can therefore continue to be operated via a thin CLI client that talks to the same API Gateway a browser would — the CLI becomes an alternate Presentation Layer client (consistent with FG-001's presentation/orchestration boundary), not a separate code path. Nothing about §12's layering privileges the browser frontend over a CLI frontend; both are equally valid Presentation Layer implementations of the same Application Layer.

### 17.11 Enterprise roadmap

Every mechanism this stage needs is already named, not newly invented: external identity provider federation is explicitly scoped as future work in §14.13; the enterprise authentication migration path is explicitly defined in §14.14; stronger audit requirements build on the existing `AuditLogEntry` and `AuthenticationEvent` entities (§10.1, §14.12) rather than new ones; multi-region availability is the same deferred capability named in §16.22. Enterprise readiness is therefore a matter of *activating* already-designed extension points, in the order §14.14 already lays out, not a new architectural undertaking.

### 17.12 AI provider strategy

Preserves AIG-001, AIG-003, and AIG-004 without modification. The AI Interpretation Tier's provider-adapter pattern (§15.4, §16.8) already anticipates supporting more than one AI provider or model over time — §15.8 already declined to over-promise exact model-version stability for precisely this reason. Product evolution here means adding provider adapters behind the existing AI Interpretation Service boundary; it never means giving the frontend or any other tier a direct path to a provider (that would violate the AI Service boundary formalized in §15.4 and enforced at the network level by DAG-001). A future capability worth naming explicitly, because enterprise buyers with data-residency requirements will ask for it: per-tenant AI provider selection. This is already expressible as `Tenant`-scoped configuration (§16.18's configuration-management boundary — *which* provider is configuration, not business logic) and requires no new governance ID.

### 17.13 Marketplace / plugin strategy

Builds directly on §5's "analysis-types-as-plugins" framing and the Extension Points already named per-layer in §12.1. A marketplace, when it exists, is a distribution mechanism for third-party or community-contributed `VerticalTemplate` and `AnalysisType` definitions (§10.1) — it does not add a new extension mechanism, it exposes the one already there. The safeguard worth stating explicitly: a contributed `AnalysisType` still executes inside the Domain Layer's existing contracts and still produces an `AnalysisRun` subject to the same immutability, provenance, and pinning rules as any built-in analysis type (§10.1). A marketplace changes *who* writes analysis logic; it does not relax any guarantee about what happens to that logic's output once it runs. This is why no new AIG or BKG entry is required for this section — the existing ones already bind third-party-contributed code exactly as they bind first-party code.

### 17.14 API commercialization

§11's constitutional-contract framing explicitly anticipated this: "future Public API exposure" was named as directly derivable from the service contracts in the API Architecture turn. Commercializing the API means exposing a governed subset of the existing API Gateway surface (§11.2) to external developers/integrators, authenticated the same way any other client is authenticated (§14, via the `ServiceAccountToken` mechanism already introduced in §14.1 for exactly this purpose), and metered through the existing Billing service contract (§11.2). No new API surface is designed here — external commercialization is a matter of which already-contracted endpoints are opened, and to whom, not a new endpoint layer.

### 17.15 Collaboration roadmap

Builds on roles already defined for exactly this purpose — Researcher/Collaborator, Analyst/Contributor, External Collaborator/Guest (§6) — and on `ProjectMembership` (§10.1). The one real design constraint future collaboration features must respect, worth stating explicitly because it is easy to violate by accident: any comment, annotation, or discussion thread attached to an `InterpretationRecord` or `AnalysisRun` must be modeled as a new, separate entity that *references* the immutable record rather than one that extends or mutates it — the same discipline already applied to `Report` in §10.1. Collaboration features add references to the graph; they do not add mutability to anything already declared immutable.

### 17.16 Institution features

Activates the Institution Owner/Admin and Lab/Department Manager roles already defined in §6 and the Tenant entity already scoped for multi-project ownership in §10.1. Concretely: cross-project dashboards and institutional billing (via the existing `Subscription` entity, §10.1) are the two features this stage adds — both are reporting/aggregation surfaces over data the architecture already owns, not new data the architecture needs to start owning.

### 17.17 Research lab features

Distinct from institution-wide features: a lab is typically a scoped group of Projects within one Tenant rather than the whole Tenant. Shared `VerticalTemplate`/`AnalysisType` reuse across a lab's Projects is already possible because those entities are not Project-owned in §10.1's aggregate model. One genuinely open question is flagged here rather than resolved: reuse of a `Dataset` or `CollectionRun` *across* Projects within a lab would cut against §10.1's "Project as root aggregate" design, where Datasets are owned by exactly one Project — cross-Project dataset sharing, if ever required, is a future decision this document deliberately leaves open rather than silently deciding by extending an entity relationship that was fixed in §10.1.

### 17.18 Internationalization

Not previously addressed anywhere in this document; genuinely new ground, though it requires no new governance. The current engine is grounded in Turkish financial content (§1.1), but nothing in §10.1's entity design encodes language or locale — `Dataset` and `CollectionRun` are language-agnostic. Internationalization decomposes cleanly along layer boundaries already established: UI localization is a Presentation Layer concern (FG-001-compliant — it is presentation, not business logic) and touches only the Frontend; multi-language NLP/topic-modeling support is a model-adapter concern within the existing Analysis service contract (§11.2), analogous to how a new AI provider is added in §17.12. Neither requires a new architectural layer or a new governance decision.

### 17.19 Pricing philosophy

Strictly a principle, not a plan — no figures appear here, consistent with this document's explicit non-goal. The structural commitment already made in §1.5 governs: a price point and procurement path a single grant or a university subscription can clear, with institutional accounts functioning as a retention and expansion mechanism (a lab renews as a lab) rather than a compliance checkbox. Architecturally, this requires only that pricing tiers map onto entitlements already modeled by the `Subscription` entity and the role/permission matrix (§10.1, §6.1) — no new entity is needed to express a pricing philosophy, only policy data layered onto structures that already exist.

### 17.20 Customer segmentation

Not a new segmentation — a restatement, for completeness, of the sequencing §1.3 already fixed: individual researchers and small labs (v1) → research centers and think tanks running multiple concurrent Projects (v1.x) → the wider named categories from §1.3's original market map (universities, graduate programs, media researchers, computational social science researchers, think tanks) once the platform generalizes past the YouTube/finance wedge (v2+). This document does not introduce a different segmentation model.

### 17.21 Go-to-market strategy

Kept intentionally short: this is the architectural precondition list for GTM, not a GTM plan. Two architectural facts gate go-to-market sequencing directly: horizontal-market GTM (targeting the full §1.3 market map) is not credible until DAD-001's branding fork is resolved, because a vertical-specific name undercuts a horizontal pitch (§1.4); and multi-vertical/multi-domain GTM (§17.4–§17.5) is only low-risk once the Vertical Template mechanism has been proven by at least one real second vertical or domain, not merely designed. Everything else about go-to-market — channels, messaging, sales motion — is outside this document's scope by the user's explicit instruction.

### 17.22 Migration strategy

Generalizes the pattern already established narrowly in §14.14 (Migration Strategy for Enterprise Authentication) into a platform-wide principle: every stage transition (v1 → v1.x → v2 → v3) must migrate existing tenants' data forward in place; none may require re-onboarding or re-ingesting a researcher's prior work. This is not a new commitment — it is §1.2's reproducibility principle applied across time instead of across a single run: an archived Project (§7's journey stage 7) must remain valid and independently reproducible not only today but after every future platform upgrade. A migration that breaks a past `AnalysisRun`'s provenance chain (§10, §15) is a regression against a core product promise, not merely an inconvenience.

### 17.23 Long-term product governance

This document series — Product Vision through this section — is the system of record for architectural decisions, and it has followed one discipline throughout that is now made explicit as a permanent process commitment: governance IDs (DAD-, AIG-, BKG-, FG-, DAG-xxx) are append-only. An approved entry is never renumbered, redefined, or silently reused (the AIG-002 gap, left open since §11.1 and still open here, is the standing proof of this discipline — it has not been filled in across six subsequent deliverables and is not filled in now). New entries are added only when a candidate constraint is genuinely new; where an idea is already covered by an existing entry, that is stated explicitly rather than issuing a redundant ID (§16.24 and §17.12/§17.13 above both did this). This mirrors, deliberately, the immutability principle already applied to `InterpretationRecord` and other entities in §10.1: the architecture's own decision record follows the same append-only, non-mutating discipline it requires of the data the platform produces.

### 17.24 Architectural stability

A consolidated view of what is settled versus what remains genuinely open, for the benefit of whatever implementation planning follows this document:

**Stable and load-bearing across every future stage** — not expected to change: the Project-as-root-aggregate model (§10.1); `InterpretationRecord` immutability and its `kind` discriminator (§10.0, §10.1); `AnalysisRun` pinning to a specific `CollectionRun` (§10.1); the single API surface and contract-first service design (§11); the six-layer backend with Domain Layer isolation (§12, BKG-001); the frontend's presentation-only boundary (§13, FG-001/FG-002); centralized authentication and the four-step role-resolution algorithm (§14.10); the AI Service boundary and every AIG guardrail (§15); the tier decomposition and network-boundary enforcement of Deployment Architecture (§16, DAG-001).

**Explicitly still open**, carried forward rather than resolved here: DAD-001 (branding — deferred since §1.4, resolution trigger technically reached but not yet requested); DAD-002 (licensing model — newly deferred in §17.7); the unresolved owning-module for `VerticalTemplate` flagged in §10.2; the artifact/export tenant-retention-policy gap flagged in §16.12; the AIG-002 numbering gap, standing open since §11.1; cross-Project dataset reuse within a lab, flagged as open in §17.17.

### 17.25 Future roadmap (v1, v1.x, v2, v3)

| Stage | Scope | Primary architecture activated |
|---|---|---|
| **v1 — Beachhead** | Individual researcher / small lab; YouTube financial-influencer research; single Project per Tenant in practice | §3.2 MVP; §4 modules; §9.3 screens; self-hosted or single-tenant SaaS (§16, §17.8) |
| **v1.x — Institutional** | Multi-project labs and research centers; cross-project comparison; institutional billing | Tenant/Project two-level model (§10.1, §14.7); Institution/Lab roles (§6); Subscription entitlements (§17.6, §17.16) |
| **v2 — Horizontal** | Additional collection platforms (§17.4) and research domains (§17.5); category-wide market map (§1.3 step 3) | `providers/platform/` abstraction; Vertical Template + AnalysisType mechanism (§5, §10.1); DAD-001 resolution as a GTM precondition (§17.21) |
| **v3 — Enterprise & Marketplace** | External identity federation; multi-region availability; third-party plugin/marketplace; API commercialization | §14.13–§14.14; §16.22's deferred HA posture; §17.13's extension points; §17.14's Public API exposure |

---

**This concludes the architecture-first phase.** Sixteen deliverables — Product Vision through Product Evolution & Commercialization Architecture — now form one coherent, cross-referenced design covering product scope, information architecture, system modules, roles, user journey, navigation and screens, the database concept, API contracts, backend and frontend architecture, authentication, AI integration, deployment, and product evolution. Every governance guardrail introduced (AIG-001, AIG-003, AIG-004, BKG-001, FG-001, FG-002, DAG-001) remains intact and unmodified; AIG-002 remains, deliberately, unfilled; DAD-001 and DAD-002 remain deliberately deferred. The next phase this document set enables is **Implementation Planning** — translating §10–§16 into package structure, a build sequence, and a testing strategy — which is out of scope for this document and was not requested here.
