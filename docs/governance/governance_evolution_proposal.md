# Governance Evolution Proposal

**THIS DOCUMENT IS NON-BINDING.** Every item below is: **"Proposed — Not Yet Adopted."** Nothing in this document alters the Repository Governance Standard until it passes through a future, formally adopted amendment to that Standard. This document collects governance improvements identified during the baseline audit that are not yet part of the Repository Governance Standard.

## Artifact Metadata

| Field | Value |
|---|---|
| Artifact ID | GEP-001 |
| Title | Governance Evolution Proposal |
| Version | 1.0.0 |
| Status | Draft — Proposed, Not Yet Adopted |
| Classification | Governance Policy Proposal (non-binding) |
| Owner | Repository Operator |
| Created Date | 2026-07-31 |
| Last Updated | 2026-07-31 |
| Source Authority | Content identified during the Governance Baseline Declaration's boundary review; none of it currently forms part of the Repository Governance Standard |
| Related Artifacts | GBD-001 (Governance Baseline Declaration — the baseline this proposal builds on) |
| Supersedes | None |
| Superseded By | None |

This proposal is based on the governance baseline declared in GBD-001 (v1.0.0).

---

## 1. Change Categorization (Proposed)

Proposed three-way taxonomy for future Repository Governance Standard revisions. Adoption requires a future Governance-category revision of the Repository Governance Standard.

| Category | Definition | Versioning Impact | Review Rigor |
|---|---|---|---|
| Editorial | No change to rules, states, roles, decision outcomes, or FSM structure | PATCH or MINOR | Governance Review only |
| Governance | Changes requirements, decision-makers, or compliance measures without altering fundamental structure | MINOR or MAJOR (per Repository Governance Standard §7.7) | Governance Review + Operator Approval |
| Architectural | Changes the fundamental structure of the governance model itself | Always MAJOR | Full multi-phase review |

## 2. Governance Change Control Policy (Proposed)

Proposed process for revising the Repository Governance Standard itself. Adoption requires a future Governance-category revision of the Standard.

| Stage | Definition |
|---|---|
| Proposal | A categorized change is drafted against the current baseline, citing affected sections and any resolved GB-NNN. |
| Review | Governance Review (Repository Governance Standard §7.2) verifies correct categorization. |
| Approval | Operator Approval (§7.3); Architectural changes require the same rigor used to originally produce Section 7. |
| Publication | Per §7.6 — Revision History entry, version increment, commit. |
| Supersession | Per §7.8 — prior version marked Superseded only once the new version is itself Published. |

This proposal does not claim to introduce "no new behavior." Adopting it as written would itself be a Governance-category change to the Repository Governance Standard, requiring its own Proposal → Review → Approval cycle once such a cycle exists.

## 3. Backlog Policy Enhancements (Proposed)

Adoption requires a future Governance-category revision of the Repository Governance Standard.

- **ID scheme:** `GB-NNN`, sequential, never reused — already reflects existing practice (GB-001, GB-002); could reasonably be adopted as an Editorial change.
- **Priority semantics (new):** Critical = affected section cannot be relied on for its stated purpose until resolved; High = resolve before the next Architectural revision; Medium = tracked, no deadline; Low = cosmetic.
- **Resolution rule (new):** an item is Resolved only when a Published, categorized revision references its GB-NNN.
- **Registry consolidation (new):** all GB-NNN items to be recorded in a single `docs/governance/backlog.md`, rather than referenced ad hoc across documents.

## 4. Supersession Reference Requirement (Proposed)

Adoption requires a future Governance-category revision of the Repository Governance Standard.

Proposed addition to Publication Prerequisites (Repository Governance Standard §7.1): a revision of an *existing* artifact must populate a non-empty "Supersedes" field to satisfy publication. This explicitly excludes first-of-their-kind artifacts (which correctly carry "Supersedes: None") — GBD-001 and GEP-001 themselves are examples of valid first-of-kind artifacts under this proposed rule.

## 5. Future Governance Review Cycle (Proposed)

Adoption requires a future Governance-category revision of the Repository Governance Standard.

The Repository Governance Standard defines no self-review cadence for itself, unlike individual artifacts (e.g., GBD-001), which specify review conditions explicitly. Proposed: the Standard should state its own review cadence — for example, triggered by every third resolved backlog item, or a fixed interval, whichever comes first. No specific cadence is recommended here; this is an open question for whoever adopts this proposal.

## 6. No Silent Semantic Alteration (Proposed)

Adoption requires a future Governance-category revision of the Repository Governance Standard. Depends on Section 1 (Change Categorization) being adopted first.

Proposed rule: every future revision to the Repository Governance Standard must explicitly declare its Section-1 category in its Revision History entry. A revision that alters governance semantics without declaring a Governance or Architectural category is non-compliant with this proposal, once adopted.

---

## Revision History

| Version | Date | Author | Summary | Approval Status |
|---|---|---|---|---|
| 1.0.0 | 2026-07-31 | Repository Operator | Initial publication-ready Governance Evolution Proposal | Draft — Proposed, Not Yet Adopted |
