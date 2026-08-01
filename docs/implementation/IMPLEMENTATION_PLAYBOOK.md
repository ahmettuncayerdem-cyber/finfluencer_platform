# Implementation Playbook — Engineering Constitution of the Implementation Phase

**Status:** Permanent repository document. Governs engineering behavior only.
**Relationship to other documents:** `PRODUCT_ARCHITECTURE.md` defines *what* is being built and is frozen. `IMPLEMENTATION_ROADMAP.md` defines *what order* it's built in and is frozen. This document defines *how* work is performed, by a human or an AI agent, every day, for the life of the project. It is deliberately not frozen — it is living documentation, expected to be edited as real practice reveals what's missing, following the same append-and-supersede discipline this document itself prescribes for ADRs (Part E).
**Audience:** every future coding session, human or AI — Claude, ChatGPT, Copilot, and successors — reads this document before touching code.

---

## 0. First Task: Is This Document the Correct Next Deliverable?

Confirmed, with one caveat and one governance decision made in the course of writing it, not before.

The caveat: `IMPLEMENTATION_ROADMAP.md`'s own Architect's Review flagged that the existing test suite's current pass/fail state has not actually been verified — an attempt failed for want of installed dependencies, not because the tests were run and failed. That is a five-minute command, not a document, and it does not block this one; it should happen before Phase 0 execution begins, in parallel with or immediately after this document, not gating it.

The governance decision: this document is what operationalizes architecture conformance as an enforced, not merely described, property of the codebase — so it is the right place, not a new document, to formalize the first Implementation Governance record. **IG-001 — no package in `presentation` or `api` may import from `infrastructure` or `persistence`; no package in `domain` may import from `infrastructure`, `persistence`, `api`, or `presentation`.** This is the concrete, CI-enforced expression of BKG-001, FG-001, and DAG-001 — it did not exist as a checkable rule before this document made it one. Two other Implementation Governance candidates named in earlier planning rounds — a migration provenance-integrity gate and an AI citation-verifiability gate — remain deliberately unformalized: no migration code and no AI code exists yet, and minting a rule for work that hasn't started would be exactly the speculative governance this project has repeatedly declined to do. They get formalized when the module that needs them is actually built, not before.

No other document is missing. What follows is a redesign of the playbook itself, not a continuation of an earlier outline.

### 0.1 Amendment — "Engineering OS" Proposal Declined as a Separate Document

A later proposal asked whether a fourth constitutional document — an "Engineering OS" — should be created to orchestrate architecture, roadmap, playbook, Context Packs, AI agents, human decisions, git workflow, reviews, testing, releases, and knowledge preservation. Declined, on direct comparison against this document's actual content: the AI Responsibility Matrix and its challenge questions (one AI performing multiple roles, roles changing by phase, vendor specialization) are Part B.1. The human intervention model is Part B.1's mandatory-approval list and Part A's scaling model. The feature lifecycle, walked through every trigger, actor, document, and gate the proposal asked for, is Part G, worked against a real example rather than an abstract flow diagram. Knowledge preservation is Parts B.2, B.7, and B.8. Creating a second document to re-describe the same mechanics would have produced exactly the two-sources-of-truth drift this project has repeatedly avoided elsewhere. What the proposal surfaced that genuinely did not exist yet — metrics, a rule-permanence taxonomy, and an explicit failure-feedback loop — is added below as Parts I, J, and K, in this document, not a new one. Full reasoning: see the response accompanying this amendment.

---

## Part A — Development Philosophy and Operating Model

Architecture-Validated Development, per `IMPLEMENTATION_ROADMAP.md` §1: the architecture is trusted and frozen; how well it survives contact with real code is proven by building, not by further planning. This document assumes one architect working with AI agents as the current operating model — every rule below is written to be fully executable by that model alone, not written for a team that doesn't exist yet.

**Daily workflow:** check the task list → confirm Definition of Ready (Part D) → build, with the relevant Context Pack loaded (Part B) → confirm Definition of Done (Part D) → merge. No sprint ceremony beyond this loop at current scale — a standing backlog re-groomed on a schedule is overhead nobody benefits from yet.

**Scaling to a second engineer:** three things change, and only three. Module ownership stops being conceptual (whoever's Context Pack it is) and becomes literal (a named person). Human review requires someone who did not author the change — today the same person authors and approves, which Part H names honestly as a real, structural limitation of solo operation, not a solved problem. And the emergency hotfix process (Part F) gains an actual rotation instead of "whoever's available." Nothing else in this document changes at that trigger — it was written to still be correct, not rewritten, when that day comes.

---

## Part B — AI Collaboration System

This is the part of the playbook most worth designing deliberately rather than inheriting from habit.

### B.1 AI Responsibility Matrix

| Tool | Primary role | Typical work | Never does |
|---|---|---|---|
| Claude, via Claude Code | Primary architect and implementer | Domain Model work, cross-layer changes, orchestrators, the default architecture-review pass | Merge without human approval, ever |
| A cross-vendor model (ChatGPT or equivalent) | Independent second-opinion reviewer | A second, mandatory review pass specifically on Domain Model changes, API Contract changes, and any diff touching a named guardrail | Author the primary implementation of what it is reviewing |
| Copilot | Fast local completion | In-file boilerplate, repetitive test scaffolding, DTO-shaped code — once a pattern is established by the primary architect | Cross-module decisions, anything touching a Domain invariant or the API Contract's public shape |
| Future agents | Assigned by the same test used to derive every row above | — | — |

The assignment is not brand preference. Claude sits at primary architect because this project already has direct, sustained evidence of it holding broad cross-referenced context correctly across the entire architecture-first phase — that's a testable property, not a default. Copilot is scoped to local completion because its typical working context is a single file, not a codebase's invariants — asking it to make a cross-module call is asking it to do a job it isn't positioned to see. The cross-vendor reviewer role exists for one specific reason: a fresh Claude session is independent of the *session* that generated a change, but it shares the *weights* — if Claude has a systematic blind spot in how it reads a particular rule, a fresh Claude session inherits the same blind spot. A different model doesn't share it. This role is strongly recommended wherever a second AI vendor is actually available, and is a genuine upgrade, not a hard requirement the workflow collapses without — Part H is explicit that this is a hypothesis, not yet validated by evidence from this codebase.

**Role weight shifts by Roadmap phase**, not role existence: Phase 0–1 work (Domain Model, orchestrator wrappers, the Walking Skeleton) is architect-heavy by necessity — there isn't yet a stable pattern for Copilot to complete against. Phase 2–3 work, once Collection and Analysis wrappers have established a repeatable shape, shifts real weight toward Copilot-eligible completion, with the primary architect moving toward integration and review rather than authoring every line.

**Mandatory human approval, no exception, regardless of how clean an AI-generated diff looks:** any change to the Domain Model's aggregate or invariant shape. Any change to the API Contract's public shape. Any new Implementation Governance or Architecture Governance ID. Any diff an AI review pass flags as touching more than one module's boundary. And merging to trunk itself — no fully autonomous AI merge exists in this project at its current stage, full stop.

### B.2 Context Pack Workflow

Bootstrapping: one pack per module, written the moment that module is first touched, never speculatively ahead of time — the discipline established in the prior planning round, unchanged here. Format and location: `docs/context-packs/_TEMPLATE.md` defines the structure; a module's actual pack lives co-located inside its own package directory so an agent opening that directory cannot miss it.

Maintenance: AI-drafted, human-approved, same PR as the code change that made it stale — never a follow-up task, never optional. The agent that just did the work has the most current understanding of it; the human approves the same way they approve any other file in the diff. This is deliberate, not automatic in the sense of unreviewed: an inaccurate Context Pack is more dangerous than an inaccurate line of application code, because it silently misleads every future session that trusts it.

### B.3 Fresh-Context Policy

Architecture-conformance review never happens in the session that generated the change — this is a hard rule, not a preference. A continued session has already spent turns justifying its own approach; asking it to grade that approach in the same breath biases the answer toward consistency with what it already said, not toward correctness. A fresh session, loaded with only the diff, the relevant Context Pack, and the specific guardrails at stake, has no such anchor.

### B.4 Long-Session, New-Chat, and Context-Recovery Strategy

A session is scoped to one module or one feature — the same boundary the Definition of Ready already requires (Part D). When a session's context grows long, or a new chat is needed, the new session loads exactly three things: this playbook, the relevant Context Pack, and the task description — nothing else, and specifically not a summary of the prior session's reasoning. If something from an earlier session actually mattered, it was already written into a Context Pack or an ADR by the end of that session, per the rules above; if it wasn't written down, it wasn't trusted enough to carry forward, and re-deriving it fresh is safer than trusting a summary that may have drifted from what actually happened.

### B.5 Repository Synchronization Strategy

Trunk is the single source of truth across every session and every tool. Every session starts by pulling latest trunk. No session persists uncommitted working state across more than one sitting — either commit it or explicitly discard it before ending the session. No long-lived personal branches, for the same reason short-lived branches exist at all (Part C): a branch that outlives a few days is a branch whose relationship to trunk nobody can reason about anymore.

### B.6 AI Guardrails During Coding

An AI agent writes code under the same architecture a human would, with no exception for "scaffolding, cleaned up later." An agent must not weaken, skip, reinterpret, or route around a Conformance Baseline or IG- rule to make a task easier. A rule that is genuinely blocking legitimate work is an ADR-worthy conversation with a human — never something quietly worked around in the diff.

### B.7 Prompt Governance

Standing, reusable prompts — the ones used repeatedly, like "wrap an existing pipeline as a `StartAnalysisRun` orchestrator" or "run an architecture-review pass" — are versioned repository artifacts in `docs/prompts/`, not disposable chat text. This isn't a new idea introduced for its own sake: it is the same discipline AIG-003 already requires of the *product's* own prompts — versioned, provenance-tracked, never silently mutated — applied to the engineering team's prompts. It would be inconsistent to demand that discipline of the product while treating the prompts that build the product as scratch. One-off, single-use messages do not need to be saved; a prompt used more than once does.

### B.8 Knowledge Management

Chat history is not a knowledge store, by design. Anything worth remembering lives in exactly one of three places: a Context Pack (current truth about a module), an ADR (a point-in-time implementation decision), or a versioned prompt (a reusable instruction). Nothing else persists, and no session — human or AI — should assume otherwise.

---

## Part C — Version Control and Change Flow

**Branch strategy:** trunk-based, short-lived feature branches — days, not weeks, matching the walking-skeleton philosophy of small, provable increments. **Commit strategy:** Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`) — this is what lets a changelog be generated rather than hand-written. **PR discipline:** one logical change per PR; a PR touching two unrelated modules is two PRs. **PR workflow:** every PR uses `.github/PULL_REQUEST_TEMPLATE.md`, which mirrors the Definition of Done (Part D) as checkboxes — the canonical explanation of each item lives here, in Part D; the template is the terse, at-the-point-of-use copy, and the two are kept in sync deliberately, not assumed to drift safely.

**Dependency upgrade policy:** upgrades are their own PR, never bundled with feature work. Security patches take priority and may bypass ordinary batching. A major-version upgrade of a core dependency gets a short ADR entry — it's a lasting decision, not routine maintenance, and deserves the same record-keeping any other lasting decision gets.

---

## Part D — Review and Quality Gate

Every PR, human- or AI-authored, passes the same four stages, in order: automated tests and the Conformance Baseline's CI rules including IG-001 → an AI architecture-review pass, in a fresh context per Part B.3, using the cross-vendor reviewer for Domain Model, API Contract, or guardrail-adjacent diffs → human review, focused on product and design judgment rather than re-deriving what the first two stages already covered → the Definition of Done, below. One narrow exception: a change touching only comments, documentation, or a Context Pack skips the AI architecture-review stage — there is no architecture in scope to violate — but still requires CI and human approval.

### Definition of Ready

Work is ready to start when: the Domain entities and invariants it touches already exist as code, or their addition is the explicit first step of the work. The relevant API Contract slice exists or is being authored as part of the same work. A Context Pack exists for the module, or gets created as step one. The work maps to one architectural layer's responsibility, not several. Any existing-engine code being wrapped has its integration decision (reuse / wrap / adapt / rewrite, with a reason) recorded before code is written. Acceptance criteria are stated as tests.

### Definition of Done

A PR merges when: CI is green — type-check, lint, IG-001's layer-direction rule, unit and integration tests for the touched module. No plaintext secret, credential, or PII appears anywhere in the diff. Tenant-scoped queries are actually scoped. Any job-handling or long-running code is idempotent and checkpoint-resumable, respecting the single-writer-per-`checkpoint_root` constraint documented in the existing `core/checkpoint.py` and recorded as Risk R-1 in `IMPLEMENTATION_ROADMAP.md`. No immutable entity is mutated in place. The AI architecture-review pass has run with no unresolved guardrail flag. A human has approved. The module's Context Pack is updated in the same PR.

### Testing Policy

The growing test suite is the testing strategy — there is no separate document describing tests that don't exist yet. One standing rule: reproducibility-chain verification and cross-tenant isolation tests require a human-designed oracle and may not be accepted from AI generation without one; routine validation and boilerplate coverage may be AI-generated and reviewed like any other code.

---

## Part E — Engineering Hygiene and Change Management

**Repository hygiene:** no commented-out code on trunk, no secrets ever, dead branches deleted rather than archived, the repo root stays limited to what this document set and the module tree require. **Refactoring policy:** welcome inside a module's existing boundaries at any time, no gate beyond the ordinary one; a refactor that changes a module's boundary or a Domain invariant goes through the full review gate like any other change, with no "just cleanup" exception. **Technical debt policy:** deliberate shortcuts are recorded in the affected Context Pack with a reason and, where possible, a revisit trigger — never a bare `TODO`.

**Documentation map**, so nobody has to guess which file is canonical for what: `PRODUCT_ARCHITECTURE.md` for what the system is; `IMPLEMENTATION_ROADMAP.md` for what order it's built in; this playbook for how work is performed; a module's Context Pack for that module's current truth; `docs/adr/` for point-in-time implementation decisions; `docs/prompts/` for reusable instructions.

**ADR policy:** any implementation-level decision with lasting consequence gets a three-to-six-sentence, dated entry in `docs/adr/` — never edited after the fact, only superseded by a new entry. This is distinct from an IG- record: an ADR documents a decision that was made once; an IG- record is a standing, CI-enforced constraint on every future change.

**Change management:** an architecture-level change follows the same explicit tension-and-resolution discipline `PRODUCT_ARCHITECTURE.md` itself was written with — name the conflict, don't silently pick a side — and requires reopening that document deliberately, which nothing in this playbook authorizes on its own. An implementation-level change goes through the standing four-stage gate in Part D.

**Emergency hotfix process:** a hotfix still requires the AI review pass and human approval — no exception, even under incident pressure. What changes is scope, not rigor: human review narrows to "does this resolve the incident without violating an immutable-entity or tenant-isolation rule," and a full-scope follow-up PR (tests, Context Pack update, any cleanup deferred in the moment) is required before the next unrelated merge touches the same module — preventing a "temporary" fix from quietly becoming a permanent, undocumented exception.

---

## Part F — Safety and Release

**Security checklist:** the Definition of Done's secret and tenant-scoping rules apply to every PR without exception; two defect classes are release-blocking regardless of severity triage elsewhere — an immutable-entity violation and a tenant-isolation violation. **Reproducibility checklist:** any change touching Collection or Analysis execution must preserve the interruption-and-resume guarantee proven in the Walking Skeleton (`IMPLEMENTATION_ROADMAP.md` §5, Phase 0) — this is not a one-time proof, it's an ongoing property every relevant change must not silently break.

**Release preparation workflow:** Conformance Baseline green on trunk, Definition of Done satisfied on every included PR, the reproducibility check run once more end to end, changelog generated from Conventional Commits, version bumped per the scheme recorded in `docs/adr/`.

**Bug triage:** anything affecting reproducibility or tenant isolation is P0, fixed before new feature work continues; everything else is triaged against whichever module is currently being worked, not a separate backlog ritual this team's size doesn't benefit from. **Issue management:** the standing task list is the issue tracker at current scale; a dedicated tracker is introduced at the same trigger a second engineer joins, not before. **Risk escalation:** a newly discovered risk is added to `IMPLEMENTATION_ROADMAP.md` §7, not tracked separately; a risk that becomes a live incident follows the emergency hotfix process above.

---

## Part G — The Engineering Quality System: Feature Lifecycle

Not a checklist — the operating loop every feature actually runs through, worked here against a real example: wrapping the Collection Engine (`IMPLEMENTATION_ROADMAP.md` §5, Phase 1).

**1. How it starts.** The task list carries an entry referencing Phase 1 and the Collection Engine reuse row in the Roadmap's §3. Definition of Ready is checked before anything is written.

**2. Which AI participates.** Claude, primary architect — this is Phase 1, cross-layer, orchestrator-shaping work, squarely in the architect-heavy end of the phase-weighted matrix (Part B.1).

**3. Which Context Pack is loaded.** The Collection Engine's — drafted as step one of this work if it doesn't exist yet, per Definition of Ready.

**4. Which constraints are checked.** IG-001's layer-direction rule, mechanically, on every commit. BKG-001 (business rules stay in Application/Domain — the orchestrator, not the wrapped Infrastructure code, owns the `StartCollectionRun` contract). Risk R-1 from the Roadmap — the checkpoint manager's single-writer assumption — checked explicitly against how this orchestrator partitions `checkpoint_root` across runs.

**5. Which tests must pass.** CI's standard suite, plus a new integration test at the orchestrator boundary — the existing 68 test files prove the current CLI-invoked behavior; they do not prove this wrapped, API-invoked behavior, per Risk R-3, so new coverage is required regardless of what already exists.

**6. Which reviews occur.** AI architecture-review pass, fresh context — cross-vendor, since this touches an orchestrator pattern other modules will imitate. Human review, focused on whether the wrapping decision itself (§3's "wrapper required" classification) held up in practice.

**7. Which documents are updated.** The Collection Engine's Context Pack, in the same PR. An ADR entry only if a genuinely lasting decision was made along the way — for instance, how `checkpoint_root` gets partitioned per run, which resolves Risk R-1 and deserves a record. The Roadmap's Risk Register only if something new was discovered; R-1 gets a status update, not a rewrite.

**8. When it's complete.** Definition of Done, fully satisfied.

**9. When it may be merged.** Definition of Done plus human approval, trunk green — no exception for how confident the AI review pass was.

**10. How the knowledge is preserved.** In the updated Context Pack, durably. If a genuinely reusable prompt pattern emerged from doing this — "wrap an existing pipeline as an orchestrator" is exactly the kind of thing likely to recur for the sentiment and topic-modeling wrappers next — it becomes a `docs/prompts/` entry. Nothing that mattered is left to live only in this session's chat history.

---

## Part I — Metrics

Kept deliberately small. A metric nobody looks at is worse than no metric — it's a maintenance cost that produces false confidence. Four, all mechanically derivable from artifacts this playbook already requires, no new instrumentation:

**Architecture Conformance Rate** — the share of PRs that pass IG-001 and the Conformance Baseline on the first CI run, not after a fix-up commit. Read directly from CI history. **Reproducibility Verification Rate** — the share of Collection/Analysis-touching PRs where the interruption-and-resume check (Part F) was actually run and passed, not skipped under time pressure. **Bug Escape Rate**, narrowly scoped to the two release-blocking classes named in Part F — immutable-entity violations and tenant-isolation violations found *after* merge rather than caught by the gate. **Context Pack Staleness** — PRs that touched a module without updating its Context Pack in the same PR; per the Definition of Done this should be zero, and a nonzero count is the signal that matters, not a trend line.

Deliberately not tracked, and named explicitly rather than silently omitted, because each requires either a baseline this project doesn't have yet or instrumentation not worth building for one person: Prompt Quality, AI Productivity, Human Productivity, Engineering Velocity, Knowledge Growth. These are reasonable metrics for an organization with enough history to compare against and enough people for productivity to be a meaningful unit of measure — neither is true here yet. Revisit at the same trigger Part A already names for process changes generally: a second engineer, or a real trend in one of the four metrics above that demands more resolution to diagnose.

## Part J — Feedback Loop

A failure — a bug that escapes, a regression, an AI review pass that misses something a human catches — is fixed first, through the ordinary gate or the emergency hotfix process (Part E), then routed to exactly one of four places, never left to just be "fixed in the code" with nothing else updated:

A gap in what an AI session knew about a module updates that module's Context Pack's "Gotchas" section (Part B.2). A systematically wrong or incomplete review prompt updates the relevant file in `docs/prompts/` as a new dated entry, the old one marked superseded (Part B.7) — never edited in place. A genuinely missing rule of engineering behavior — not caught by any existing Part of this playbook — is added to this document directly, by ordinary PR, since it is living documentation by design (see header). A failure that traces back to the *architecture* itself, not to how it was implemented, is never silently patched here — it becomes an explicitly named tension, surfaced for a human decision to reopen `PRODUCT_ARCHITECTURE.md` deliberately, the same discipline that document was written with in the first place.

## Part K — Rule Permanence

Three tiers, so it's never ambiguous how hard a given rule is to change.

**Constitutional** — changes only by reopening the document it lives in, deliberately, through the explicit tension-and-resolution discipline: every decision in `PRODUCT_ARCHITECTURE.md`, the AIG/BKG/FG/DAG/DAD governance register, `IMPLEMENTATION_ROADMAP.md`'s execution sequencing, and every IG- record including IG-001. **Operational policy** — changes by an ordinary PR to this playbook, deliberately but without special ceremony: branch strategy, the review gate's composition, the AI Responsibility Matrix, which metrics are tracked, and the collaboration protocol (Part L). **Temporary practice** — changes freely, no process required: the current task list, which prompts currently live in `docs/prompts/`, a Context Pack's specific "known debt" entries, and the current *values* of the metrics in Part I, as distinct from the decision to track them at all.

---

## Part L — Collaboration Protocol

Governs how the acting Engineering Lead session (human or AI) communicates project state and hands work off between sessions. Added by amendment after several rounds of live-tested refinement during Sprint 0 planning. Operational Policy under Part K — changes by ordinary PR, no governance ID minted for a revision.

**Role.** The acting Engineering Lead's job is to move the project toward a working, maintainable, production-quality platform, not to produce documentation for its own sake. Self-review is expected before a recommendation is presented, but as one reasoning pass — not staged as separate personas performing the same critique twice.

**Rule 1 — Intelligent Session Transfer.** At the end of a response, two questions decide whether a copy-paste-ready handoff prompt for a fresh session is warranted, in addition to the standing Session Resume Context (Rule 3): has anything changed in Rule 3's schema fields that a fresh session would need to know to continue correctly, and is the current session likely to end, restart, or lose context before the next meaningful step. If both are confidently no, produce only the Session Resume Context. If either is yes, or genuinely uncertain, produce both — the tie-breaker favors producing the handoff prompt, since an unneeded one costs mild repetition while a missing one costs lost context, a real failure mode for long sessions, not a hypothetical one.

**Rule 2 — Language Policy.** Engineering discussion with the operator — explanations, reviews, architecture discussion, implementation advice, critiques, progress summaries — is conducted in Turkish, the project's working language for engineering conversations. Engineering artifacts are not translated: this document, `PRODUCT_ARCHITECTURE.md`, `IMPLEMENTATION_ROADMAP.md`, `BACKLOG.md`, ADRs, Context Packs, the prompt library, API contracts, code, commit messages, terminal commands, and technical identifiers stay in English regardless of the discussion language, since their audience is the codebase and future contributors, not the participants in a given conversation. A quoted excerpt from an English artifact stays in its original English form inside Turkish discussion; only the surrounding commentary is translated.

**Rule 3 — Standard Session Resume Context.** A fixed schema, populated only with applicable fields, never fabricated: Repository, Branch, Last Commit, Current Epic, Current Sprint, Current Task, Critical Path, Blocked Tasks, Pending Human Decisions, Open Findings, Environment Limitations. A field with no change since it was last stated says so rather than being re-explained in full. Reserved fields are added only once their trigger fires, not speculatively: Owner/Assignee at the second regular contributor, CI Status once IG-001 is wired into CI, Active PR once a real PR workflow is in use rather than direct-to-trunk commits.

**Rule 4 — Protocol Persistence.** This Part is the canonical source of the collaboration protocol. Conversation history is advisory context only; where it disagrees with this Part, this Part governs. Protocol updates are made through ordinary PRs to this document, per the Operational Policy tier above — no governance ID is minted for a protocol revision unless it affects constitutional architecture.

---

## Part H — Engineering Review

Written by the same hand that wrote the rest of this document, held to the same standard.

**What's weak:** the AI Responsibility Matrix is a reasoned argument, not yet an empirical finding — nothing has actually measured whether a cross-vendor reviewer catches errors Claude misses in this specific codebase. Revisit once there's real data from a handful of review passes, not before.

**What's still missing:** a real incident postmortem process. The emergency hotfix process (Part E) covers the fix; nothing here covers writing up what caused it afterward. At one person's scale that's an acceptable, deliberate gap — a postmortem template for a team of one is close to theater — but it should be added the first time an actual customer-facing incident happens, not left for a calendar trigger.

**What a world-class organization would do differently:** they would not tolerate the gap that exists right now between this document describing IG-001 and IG-001 actually being wired into CI. That gap should close in Sprint 0, immediately, not remain a described aspiration for more than a day.

**What I'd remove, if forced to cut for length:** the "scaling to a second engineer" language throughout Part A. It's kept brief and clearly marked here, but writing process for a team that doesn't exist yet is the exact mistake this whole engagement has repeatedly flagged as the highest risk in earlier rounds — if anything here is premature, it's this, not any of the currently-solo-operable rules.

**What I'd merge:** Repository Hygiene and Refactoring Policy are close enough in spirit that a smaller team could reasonably fold them into one "codebase health" section. They're kept separate here because they trigger at different moments — hygiene on every PR, refactoring as a deliberate, scoped activity — but that's a judgment call, not a hard requirement.

**What I'd postpone:** populating `docs/prompts/` beyond the convention and one real example. The library should grow from observed repetition, not be pre-filled speculatively — the same just-in-time discipline applied everywhere else in this project.

**What's over-engineered:** the full four-stage review gate applied without exception was too rigid before the documentation/comment carve-out added in Part D — a one-line typo fix does not need an architecture-review pass, and pretending otherwise would have been ceremony for its own sake.

**What's under-engineered:** "fresh context" is asserted, not fully operationalized — this document says a review session loads exactly three things, but that convention hasn't been tested against a real review session yet, and it may need refinement once one actually happens.

**What I'd redesign if this were a company on a path to a $100M outcome instead of an academic platform:** the human-approval gate in Part B.1 currently means the same person authors and approves — that is a real, unsolved structural weakness this document cannot fix alone, and no amount of AI review substitutes for a second accountable person once real customer data and real money are involved. The emergency hotfix process would need an actual on-call rotation and an incident-commander role, not "whoever's available" — and the postmortem process flagged as missing above would need to exist before the first incident, not after it.

**Would I approve this for implementation, as CTO?** Yes — for exactly the company this is today: one architect, AI-assisted, pre-revenue, proving a research platform's core loop. I would not approve it as the permanent constitution of a funded company with paying customers. Several of its gates — single-person approval chief among them — are correct scaffolding for right now and a genuine liability the moment either of those two facts changes. This document should be revisited explicitly at that trigger, not on a schedule.
