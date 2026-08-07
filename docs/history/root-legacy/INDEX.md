# Root-Legacy Documents — Index

**Added:** 2026-08-07, as part of the Version 1.0 Research Readiness freeze
(`docs/implementation/V1.0_RESEARCH_READINESS_AUDIT.md`).

These 49 files were relocated here from the repository root without modification (`git mv`,
history preserved). They are **not current**. Every one of them predates this engagement's
Sprint 0-4 build (the one that produced T-001 through T-029 and the live MVP sign-off,
`docs/implementation/PROGRAM_DIRECTOR_REPORT.md`) — several explicitly reference a much earlier
repository state (missing CI, missing `poetry.lock`, missing `.gitignore`, a failing coverage
gate, an unimplemented CLI entry point) that no longer describes this repository in any way.

**Do not treat any document in this directory as authoritative for the current state of the
platform.** For current, accurate references, use instead:

| Topic | Current authoritative source |
|---|---|
| Architecture | `docs/product/PRODUCT_ARCHITECTURE.md` |
| Task/backlog state | `docs/implementation/BACKLOG.md` |
| Release blocker status | `docs/implementation/RELEASE_BLOCKING_ASSESSMENT.md` |
| Engagement history / deltas | `docs/implementation/PROGRAM_DIRECTOR_REPORT.md` |
| Research/publication readiness | `docs/implementation/V1.0_RESEARCH_READINESS_AUDIT.md` |

**One item flagged for the operator's attention, not merely archival:**
`Hakem_Raporu_Brutal_Inceleme.md` is a real referee-style critique of a specific manuscript draft
(`finfluencer_tr_2025_BIR_Methods_Results_FINAL_with_discussion.docx`) and documents what it calls
a desk-reject-level defect — an AI-editing changelog left inside the article body itself (its
§1) — plus a second, corrupted-citations issue. This audit found no evidence either was
subsequently fixed. This is a manuscript-content issue, not a software issue, and is out of scope
for this platform's engineering freeze — but it is a real, apparently still-open finding that
predates and is independent of this repository's software history, and is preserved here rather
than silently buried in a bulk file move.

Kept for historical record only; not deleted, since it is real project history.
