# Repository Governance Standard

**Status:** Active
**Scope:** This repository, all present and future contributors, all present and future engineering events.
**Nature:** This document defines a durable governance *model*. It contains no file names, sprint numbers, or dates — those belong to project-specific reports (see `docs/engineering/`, `docs/history/`). When this standard and a project-specific report disagree, this standard governs the decision-making process; the report governs what actually happened.

---

## 1. Governance Principles

**Evidence over intuition.** A disposition decision (commit, archive, ignore, exclude) must be justified by direct inspection of the object in question — its content, its provenance, its consumers — not by its file type, its name, or an assumption about what it probably is.

**Irreversibility deserves proportionate caution.** Git history, once pushed or shared, is effectively permanent. The caution applied to a decision should scale with how hard it is to undo — a `.gitignore` entry is trivially reversible; committing human-subject data is not. When in doubt about reversibility, treat the action as irreversible.

**Traceability over convenience.** Every artifact in the repository should be explicable: what produced it, why it exists, what depends on it. An artifact that cannot be traced to a producer or a decision is a governance gap, not a neutral fact of life.

**Narrate, then discard the raw evidence.** Ephemeral proof of work (logs, command output, intermediate captures) earns its keep by informing a permanent, narrated record. Once narrated, the raw form has no further governance value and should not be retained in version control.

**Supersede, don't delete.** A decision that is later reversed or replaced is marked superseded, with a pointer to what replaced it. Deletion erases the ability to answer "why did we once think this," which is itself engineering-relevant information.

**One canonical document per decision.** Where multiple documents describe the same decision or the same state, exactly one is canonical at any time. Others are either merged, explicitly marked as superseded, or explicitly marked as a distinct, non-overlapping decision.

**Sensitive-by-default is the safe default.** When an object's sensitivity is unverified, it is treated as sensitive until verified otherwise. The burden of proof is on clearing an object for inclusion, not on flagging it for exclusion.

**Governance follows engineering intent, not file extension.** Two files of the same type (e.g., two `.csv` files) may warrant entirely different treatment depending on what engineering decision produced them. Classification by intent precedes classification by format.

---

## 2. Repository Lifecycle

**Creation.** An object enters the repository's scope the moment it is written to the working tree, regardless of whether it is later committed. Creation triggers no automatic obligation, but establishes the object as something the governance model must eventually classify — it cannot remain permanently unclassified.

**Active Development.** The object is modified, tested, and iterated on. Governance's role here is light-touch: ensure the object's purpose remains inferable (via naming, an accompanying note, or proximity to related work) so that a later governance review does not have to reconstruct intent from scratch.

**Release.** The object is evaluated for inclusion in a defined, shippable state of the repository. This is the first point at which "should this exist in git" becomes a binding question rather than a working assumption. Objects not clearing Release either move to Archive, are excluded permanently, or are held for a named future decision.

**Replication.** A subset of Release-stage objects is packaged for external reproducibility (journal supplementary material, archival deposit, third-party verification). Replication has a stricter bar than Release: an object must be not just present but *sufficient* — a reader with only the replication package and no access to the rest of the repository must be able to reproduce the claimed result. Replication packaging is additive (it draws from Release-stage objects) and must never be the first time an object is evaluated for sensitivity.

**Archive.** The object is retained for historical record but is no longer active, canonical, or expected to be built upon. Archival is a deliberate, documented transition (superseded-by pointer, reason, date), not a passive drift into disuse.

**Retirement.** The object's continued presence — even in archive — no longer serves a purpose, or its presence has become a liability (e.g., a governance review later determines archived material is sensitive). Retirement is the only lifecycle stage that may involve removal from active branches, and it requires the same approval authority as the object's original inclusion required, at minimum.

---

## 3. Repository Decision Matrix

| Object Type | Owner | Default Disposition | Review Authority | Approval Requirement | Retention Policy |
|---|---|---|---|---|---|
| Production source code | Repository Maintainer | Commit, once tested | Principal Architect (architectural fit) + Repository Maintainer (hygiene) | Passing test suite; no unreviewed diff | Permanent, subject to normal version history |
| Test code | Repository Maintainer | Commit alongside the production code it covers | Repository Maintainer | Must accompany, not follow, its production counterpart | Permanent |
| Generated / regenerable artifacts | Research Lead (if research output) or Repository Maintainer (if build output) | Exclude by default (`.gitignore` or replication packaging) | Principal Architect (if proposed as a fixed snapshot) | Governance Review, if inclusion is proposed | If included: versioned as a snapshot, not treated as source; regeneration procedure must be documented alongside it |
| Research artifacts (human-subject / annotator / participant-derived data) | Research Lead | Exclude until cleared | Research Lead + Governance Review (joint) | Mandatory Governance Review before first commit | If cleared: retention period and access scope defined explicitly at approval time, not left open-ended |
| Temporary / ephemeral files (logs, command captures, backups) | Whoever produced them | Never commit | N/A — self-enforcing | None (exclusion is automatic) | Not retained in version control under any circumstance; narrate into a permanent report instead |
| Internal engineering reports (sprint, release, phase, gate reports) | Documentation Owner | Commit, one canonical document per topic | Documentation Owner | De-duplication check against existing reports before commit | Permanent; superseded reports marked, not deleted |
| ADRs | Principal Architect | Commit | Principal Architect | Must include Status field; superseding an ADR requires a new ADR referencing it | Permanent, immutable once Accepted (amendments are new ADRs) |
| Engineering notes (cross-cutting, technology-agnostic) | Documentation Owner | Commit, living document | Principal Architect | Additive changes only; no rewriting prior entries' conclusions | Permanent, append-only in substance |
| Release documentation | Release Engineer | Commit, one canonical set per release | Release Engineer | Must reference the Release lifecycle stage's exit criteria | Permanent, organized per-release |
| Migration documentation | Principal Architect | Commit as a complete set (plan + closeout + any ADRs together) | Principal Architect | Status language must match verified code/data state at commit time | Permanent; a migration's documentation set is never partially committed |
| Configuration / dependency manifests | Repository Maintainer | Commit | Repository Maintainer | Must correspond to a verified, reproducible install/build | Permanent, full version history retained |
| Superseded design drafts (e.g., prior architecture documents) | Principal Architect | Archive, not delete | Principal Architect | None beyond confirming supersession | Permanent in archive location |

---

## 4. Governance Roles

**Repository Maintainer.** Owns day-to-day repository hygiene: what's tracked, what's ignored, whether the working tree matches the Decision Matrix's defaults. Escalates ambiguous cases to the relevant authority rather than deciding unilaterally outside their remit. Does not have unilateral authority over research artifacts, ADRs, or migration documentation.

**Release Engineer.** Owns the Release and Replication lifecycle stages. Defines and enforces exit criteria for a release; verifies that a Replication package is self-sufficient before it is presented as such. Has authority to block a release on governance grounds even if all technical checks pass.

**Principal Architect.** Owns architectural coherence across the repository: ADRs, migration documentation, and whether a proposed generated-artifact snapshot is architecturally justified to commit. Final authority on whether an engineering decision's documentation accurately represents the decision.

**Research Lead.** Owns anything derived from or referencing human subjects, annotators, or study participants. Sole authority to clear a research artifact for inclusion; this authority cannot be delegated to the Repository Maintainer or exercised implicitly by silence.

**Documentation Owner.** Owns the internal-report and engineering-notes categories: ensures one canonical document per topic, flags duplication, and maintains the cross-cutting engineering-notes document as a living artifact rather than letting it fragment into per-event copies.

A single person may hold multiple roles in a small team; the separation above defines *authority boundaries*, not headcount. Where one person holds conflicting roles (e.g., Repository Maintainer and Research Lead), the higher-caution disposition governs.

---

## 5. Policy Enforcement

| Mechanism | Enforces |
|---|---|
| **Git** (`.gitignore`, hooks) | Temporary/ephemeral file exclusion; generated-artifact exclusion by default; backup-file exclusion. Mechanical, pattern-based — cannot make judgment calls, only block known-bad patterns. |
| **CI** | Test-suite pass/fail as a precondition for production/test code commits; lint/type-check gates where defined; detection of newly-added large binary files or newly-added files matching sensitive-data naming heuristics, surfaced for human review rather than auto-blocked (false positives are expected and acceptable here). |
| **Manual Review** | Diffs for production source, test code, and configuration/dependency manifests — a human confirms the change does what it claims before it is treated as "verified" rather than "assumed correct." |
| **Release Checklist** | Release and Replication lifecycle exit criteria; de-duplication of release documentation; confirmation that a replication package is self-sufficient. |
| **Governance Review** | Research artifact clearance; any object flagged sensitive by default; any cross-role conflict (see Section 4); retirement decisions. This is the only enforcement mechanism that cannot be automated or delegated downward. |

No single mechanism is sufficient on its own — Git and CI catch mechanical violations; Manual Review and Release Checklist catch correctness and completeness; Governance Review catches judgment calls that the other four are structurally unable to make.

---

## 6. Repository Quality Gates

Mandatory before any Git execution (commit, merge, or release tag), in order:

1. **Classification completeness.** Every object being acted on has an explicit disposition under Section 3's Decision Matrix — no object proceeds on an implicit "probably fine" assumption.
2. **Sensitivity clearance.** No object flagged as research artifact or otherwise sensitive-by-default is included without a recorded Governance Review approval.
3. **Test verification.** Any production source or test code change is backed by a passing, relevant test run performed in an environment representative of where the code actually executes (not a substitute environment that cannot exercise the same failure modes).
4. **Traceability check.** Every included object can be traced to a producer, an author, or an explicit engineering decision. Objects that fail this check are routed to Governance Review, not committed provisionally.
5. **Duplication check.** No two included objects represent the same decision or the same state without one being explicitly marked canonical and the other explicitly marked superseded or distinct.
6. **Ephemeral-content check.** No raw logs, command captures, or backup files are present among the objects proceeding to commit.
7. **Role sign-off.** Each object's Review Authority (per Section 3) has approved its inclusion — a maintainer cannot clear an object that requires Principal Architect, Research Lead, or Governance Review sign-off.

A repository state that fails any gate above is **not ready for Git execution**, regardless of how much of the surrounding work is otherwise complete.
