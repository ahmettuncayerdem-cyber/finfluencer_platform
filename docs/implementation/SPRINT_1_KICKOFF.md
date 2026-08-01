# Sprint 1 Kickoff

**Date:** 2026-08-01
**Scope of this sprint:** EPIC-03, Live Collection (`BACKLOG.md` T-015 → T-016 → T-017).

---

## 1. Sprint objective

Prove the Walking Skeleton's Collection path against real, live YouTube data instead of the fixture dataset — replacing `FixtureCollectionProvider` with a real `PlatformProvider` implementation, hardening it against genuine external-API failure modes, and re-proving T-013's interruption/resume guarantee against live, variable-timing data.

## 2. Scope

- **T-015** — Replace the fixture adapter with a live YouTube Data API v3-backed `PlatformProvider`, wired into the existing, unmodified `CollectionEngineAdapter`.
- **T-016** — Quota/rate-limit handling and retry policy on top of T-015's live provider.
- **T-017** — Real-world interruption test: T-013's exact correctness bar (real `SIGKILL`, verified checkpoint resume, no data loss or duplication), run against a live collection instead of fixture data.

## 3. Success criteria

A real, small YouTube channel's data (channels → videos → comments → transcripts) is collected end to end through the existing `StartCollectionRunOrchestrator` → `ICollectionEngine` → live provider path, with no changes to `collect/*.py` or `core/checkpoint.py`. Transient failures (network errors, rate limits) retry with backoff; quota exhaustion fails loudly, not silently. A real interruption of a live run resumes correctly, matching T-013's proof exactly, just against live data instead of fixtures.

## 4. Deliverables

A live-backed `PlatformProvider` implementation (Infrastructure). Quota/retry handling using `tenacity` (already a dependency — no new library). An updated Collection Context Pack (`src/finfluencer/infrastructure/collection/CONTEXT_PACK.md`) in the same PR as T-015, per that task's own instruction. A live-run interruption/resume test (T-017), following T-013's own pattern. Updated `BACKLOG.md` entries for T-015, T-016, T-017.

## 5. Explicit non-goals

No architecture changes. No new Domain entities, no new orchestrators, no new repository interfaces. No Persistence Layer. No authentication or authorization. No AI/analysis functionality (EPIC-04+). No rewrite of `collect/*.py`, `core/checkpoint.py`, or any already-closed Sprint 0 code — adapters wrap, they do not replace. No resolution of F-002 or the standing Risk-Register-edit question unless the operator raises them.

## 6. Known risks

Real API credentials and real quota are now in play for the first time this engagement — mistakes cost more than CPU time. `IMPLEMENTATION_ROADMAP.md` §7 Risk R-4 (external dependency risk) applies directly to T-016. Cross-vendor review remains outstanding for T-010/T-011/T-012 (the exact patterns T-015 extends) — a governance gap, not a technical blocker, tracked in `BACKLOG.md`, not gating start. This sandbox's own environment (Python 3.10, no live network egress to the real YouTube API in some environments) may require live-run verification to happen outside this sandbox.

## 7. Review gates

IG-001 must remain clean at every task close, as in Sprint 0. Each task follows the same nine-step discipline: read Architecture/Roadmap sections, read the Context Pack, produce a Migration Risk Checklist, implement, test, run IG-001, update `BACKLOG.md`, commit, explain any deviation explicitly. Cross-vendor review remains a recorded governance requirement (`BACKLOG.md`), not a hard gate — it blocks only if it surfaces an actual architectural contradiction.

## 8. Exit criteria

T-015, T-016, and T-017 all closed in `BACKLOG.md` with passing tests and clean IG-001. A live channel's data collected end to end at least once, verified. A live interruption/resume proof matching T-013's correctness bar. No unresolved architectural contradiction discovered along the way (if one is, work stops and it is reported before continuing, per standing policy).
