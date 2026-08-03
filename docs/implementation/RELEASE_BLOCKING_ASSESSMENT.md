# Release Blocking Assessment

**Date:** 2026-08-03
**Status:** Planning/assessment artifact — Temporary Practice, same classification as
`BACKLOG.md`/`RELEASE_READINESS_ROADMAP.md`. Not constitutional. Does not modify the Roadmap and
does not redesign anything in it.
**Method:** every open item in `BACKLOG.md`, `GOVERNANCE_REGISTER.md`,
`IMPLEMENTATION_ROADMAP.md` §7/§10, every module `CONTEXT_PACK.md`'s "Known technical debt"
section, and `pyproject.toml`'s own inline comments was re-read for this pass. Resolved/closed
items are excluded — this is an inventory of what remains open only.

---

## 0. Critical findings not previously surfaced this plainly

Reviewing the Roadmap critically, against the full repository rather than against `BACKLOG.md`
alone, surfaced five items the Roadmap did not account for:

1. **`KNOWN_ISSUES.md` exists, is real, dated 2026-07-27 — predates this entire engagement — and
   has never been referenced by `BACKLOG.md`, `GOVERNANCE_REGISTER.md`, or last turn's Roadmap.**
   It documents a confirmed, upstream-verified Windows-specific `torch` bug
   (`OSError: [WinError 1114]`, [pytorch/pytorch#166628](https://github.com/pytorch/pytorch/issues/166628),
   still open upstream): `torch >=2.9.0` fails to import on Windows when `pandas`/`pyarrow` is
   imported first in the same process — which is exactly the import order this repository's own
   test collection uses. Mitigated today by a temporary pin (`torch >=2.8.0,<2.9.0`,
   `pyproject.toml` line 140), confirmed still in effect (`poetry.lock` pins `torch==2.8.0`
   directly, checked this pass). **This means: someone already ran real dependency work on a real
   Windows, Python 3.12.10 environment, with `poetry`, before this engagement started** — a more
   precise finding than the Roadmap's "no true editable install has ever happened." What that
   session did *not* confirm (its own criteria for lifting the pin say so explicitly): a full
   `poetry run pytest` has never been confirmed to pass on that environment. So the real open
   question is narrower than the Roadmap stated, but not closed.
2. **`poetry.lock` is not uniformly stale.** It was genuinely regenerated on 2026-07-27 (the
   `torch` pin commit) and is correct as of that date. It has only drifted since for the two
   dependencies T-027 added (`reportlab`, `pypdf` — confirmed absent from `poetry.lock` this
   pass) — a narrower, more precise gap than "never regenerated."
3. **The embeddings pipeline is not wrapped, and `TopicsAnalysisAdapter` requires a caller-supplied
   `embeddings_index_path`.** No task has ever built anything that produces one. This means the
   Roadmap's RR-05 (real analysis engines behind `StartAnalysisRun`) cannot actually run
   end-to-end against real data yet, even once collection and dispatch are solved — a real,
   previously under-weighted dependency (`GOVERNANCE_REGISTER.md`'s TD-05 calls it
   "non-blocking, unticketed," which undersells it once RR-05 is actually attempted).
4. **`bertopic`/`umap-learn`/`hdbscan`/`sentence-transformers`/`torch` (topics) and
   `transformers`/`torch` (sentiment) have never been installed together and exercised for real,
   anywhere, this entire engagement** — every one of this session's and every prior session's
   "passing" adapter tests inject fake runners/loaders by design (confirmed directly in both
   adapters' own `CONTEXT_PACK.md` files). Combined with finding 1's Windows DLL bug, this is a
   materially higher-risk item than the Roadmap's RR-05 entry implied.
5. **`.github/workflows/ci.yml` has never executed on real GitHub Actions infrastructure, across
   all five sprints of this engagement** (T-005's own outcome text: "no remote configured... the
   workflow file is correct and locally proven but has never run on GitHub's own infrastructure").
   Every "regression: clean" claim this entire engagement has produced, including this session's,
   is a self-reported local run, never independently confirmed by the CI gate the project itself
   built specifically for this purpose.
6. **The roster-wide collection granularity vs. per-`Dataset` `CollectionRun` mismatch,
   flagged and explicitly deferred at T-010/T-011, was never resolved by any later task** —
   confirmed this pass by reading `CollectionEngineAdapter.__init__`: it still takes one
   `AnalystRoster` (the entire configured roster) with no per-`Dataset` subset mechanism.
   Every `CollectionRun`, regardless of which `Dataset` it belongs to, collects the identical
   full roster today.
7. **`GOVERNANCE_REGISTER.md` is itself stale** — its `CVR-01` entry lists 9 tasks
   (`T-008/010/011/012/013/015/016/017/018`) but omits `T-024`, even though `T-024`'s own
   `BACKLOG.md` outcome text says it was "added to the existing outstanding batch." The register's
   own stated "Next Review Point" for `CVR-01` ("before MVP acceptance, T-029") has now passed —
   T-029's implementation-side verification completed without this review occurring, per the
   operator's own repeated, explicit non-blocking rulings at every prior gate.

None of these six are new architectural problems — all fit inside categories the Roadmap already
named (Infrastructure/Release Engineering). They change *severity and precision*, not scope.

## 1. Full inventory and classification

Every open item, classified into exactly one category. "Evidence" cites where it is recorded.

| # | Item | Category | Evidence |
|---|---|---|---|
| 1 | Python ≥3.11/Poetry install path never proven with a full `pytest` run (narrowed by finding 0.1: real dependency-level work *has* happened, full-suite proof has not) | **Release blocker** | `BACKLOG.md` T-002/T-003; `KNOWN_ISSUES.md` |
| 2 | `torch >=2.9.0` Windows DLL failure, upstream bug, currently pinned | **Release blocker** | `KNOWN_ISSUES.md`; `pyproject.toml:130-140`; directly gates any real environment choice for RR-01/04/05 |
| 3 | Live YouTube network collection unverified (T-015/T-017 live halves) | **Release blocker** | `BACKLOG.md` T-015/T-017; `GOVERNANCE_REGISTER.md` TD-01/RISK-01 |
| 4 | ~~Embeddings pipeline unwrapped~~ — **Resolved 2026-08-03.** `EmbeddingsEngineAdapter` wraps `run_embeddings`/`SentenceTransformerProvider` unmodified; fixture-tested, IG-001 clean. See `RB4_EMBEDDINGS_ADAPTER_MIGRATION_RISK_CHECKLIST.md`. **New dependency surfaced while resolving this item, not yet resolved:** `comments.parquet` has no `text_clean` until `preprocess/` is wrapped ("Adaptation required," Roadmap R-6) — blocks a real end-to-end run regardless of this fix. | **Release blocker** (partially resolved; preprocess gap remains) | `infrastructure/analysis/CONTEXT_PACK.md`; `RB4_EMBEDDINGS_ADAPTER_MIGRATION_RISK_CHECKLIST.md` |
| 5 | `bertopic`/`transformers`/`torch` stack never installed+run together anywhere | **Release blocker** | Both analysis `CONTEXT_PACK.md` files, "Known technical debt" |
| 6 | `StartAnalysisRun`'s only reachable engine is the ADR-0004 demo stand-in (TD-03/TD-04 dispatch gap) | **Release blocker** | `docs/adr/0004-...md`; `GOVERNANCE_REGISTER.md` ARB-01 |
| 7 | CI (`ci.yml`) has never executed on real GitHub Actions infrastructure | **Release blocker** | `BACKLOG.md` T-005 outcome |
| 8 | In-memory Persistence Layer; Sprint 5's `T-030` (real registration/login) is not meaningful without it, even though `BACKLOG.md`'s graph doesn't say so | **Sprint 5 prerequisite** | `BACKLOG.md` T-009; `RELEASE_READINESS_ROADMAP.md` §0 |
| 9 | Tenant isolation untested (no adversarial test yet) | **Sprint 5 prerequisite** | `IMPLEMENTATION_ROADMAP.md` R-5; = `T-032` exactly |
| 10 | Authentication/authorization beyond one dev-user | **Sprint 5 prerequisite** | `BACKLOG.md` EPIC-07 (`T-030`/`T-031`) |
| 11 | Roster-wide collection granularity vs. per-`Dataset` scoping, unreconciled | **Production-only prerequisite** | `infrastructure/collection/CONTEXT_PACK.md`; confirmed unresolved this pass (§0.6) |
| 12 | `api.middleware.idempotency` not implemented — duplicate `CreateProject` calls create duplicate Projects | **Production-only prerequisite** | `api/CONTEXT_PACK.md` "Known technical debt" |
| 13 | `click 8.4.1` vs. `pyproject.toml`'s `<8.2.0` — 2 CLI test files broken at collection | **Production-only prerequisite** | Confirmed broken again this session (T-029 Phase 3) |
| 14 | React frontend deferred; static HTML dev page stands in | **Production-only prerequisite** | `BACKLOG.md` T-012 Scope Decision 4 |
| 15 | No `GetCollectionRun`/`GetAnalysisRun`/`ListDatasets` query endpoints | **Production-only prerequisite** | `BACKLOG.md` F-002 context; T-012 outcome |
| 16 | `StartCollectionRun` synchronous, not per §11.2's async/`queued` contract | **Production-only prerequisite** | `BACKLOG.md` T-011/T-012 Scope Decision 5 |
| 17 | Cross-vendor AI review outstanding on 10 tasks (`CVR-01`, including the missing `T-024`) | **Quality improvement** | `GOVERNANCE_REGISTER.md` CVR-01; operator has ruled non-blocking at every gate to date, including T-029's own closure |
| 18 | `AnalysisScope`/`Dataset` reconciliation (Roadmap R-2) | **Quality improvement** | `IMPLEMENTATION_ROADMAP.md` §7 R-2; no task has hit a real wall over it yet |
| 19 | Manual browser click-through never performed (automated substitute exists) | **Quality improvement** | `BACKLOG.md` T-012 |
| 20 | PDF report layout is raw-content-only; `jinja2` declared, unused | **Quality improvement** | `BACKLOG.md` T-027; Sprint 4 Retrospective |
| 21 | Retry-after-failure cache-miss (TD-02) | **Quality improvement** | `GOVERNANCE_REGISTER.md` TD-02 — explicitly "not a defect" |
| 22 | Reuse-confidence Risk R-3 (new integration tests needed) | **Documentation only** | `IMPLEMENTATION_ROADMAP.md` §7 R-3 — substantively addressed in practice by 5 sprints of real integration tests; the Risk Register line is stale, not the underlying risk |
| 23 | AI reproducibility/cost (Roadmap R-4) | **Documentation only** | Phase 2 concern, correctly not yet relevant |
| 24 | Vertical coupling in `preprocess/financial_tr.py` (Roadmap R-6) | **Documentation only** | Phase 3, untouched by any Phase 1/2 work so far |
| 25 | `AnalysisOutcome.topic_count` naming reused for sentiment (TD-03/DI-01) | **Cosmetic** | `GOVERNANCE_REGISTER.md`; ARB-01's own "Generalize, low priority" classification |
| 26 | Context Pack file-naming asymmetry (TD-04/DI-02) | **Cosmetic** | `GOVERNANCE_REGISTER.md` |
| 27 | `api/routes/reporting.py` `ValueError`→404 conflation | **Cosmetic** | `BACKLOG.md` T-028; still returns a correct 4xx family |
| 28 | `F-002` — `GetCollectionRunStatus` naming mismatch in the frozen Roadmap | **Documentation only** | `BACKLOG.md` F-002; pending operator decision, zero code impact |
| 29 | `T-033` — ~90 untracked research/publication files at repo root | **Cosmetic** | `BACKLOG.md` T-033 |
| 30 | `DAD-001` (branding), `DAD-002` (licensing model) | **Documentation only** | `IMPLEMENTATION_ROADMAP.md` §10 — explicitly "does not block Phase 0 or Phase 1" |
| 31 | `AIG-002` unfilled governance-ID numbering gap | **Cosmetic** | `PRODUCT_ARCHITECTURE.md` §16.24 note |
| 32 | Standing question: is a routine `IMPLEMENTATION_ROADMAP.md` Risk-Register status-note edit authorized, distinct from reopening architecture? (raised at T-010, unresolved since) | **Documentation only** | `BACKLOG.md` T-010/T-011 |
| 33 | `GOVERNANCE_REGISTER.md` itself is stale (`T-024` missing from `CVR-01`; `CVR-01`'s own review trigger has passed unactioned) | **Documentation only** | Confirmed this pass, §0.7 |
| 34 | AI Interpretation Layer entirely absent | **Documentation only** | Correctly out of MVP scope, Phase 2 — nothing actionable before then |

## 2. Prioritized Release Blocking Matrix

Ordered by category, then by how directly each item sits on the path to the next real milestone
(a literal T-029 re-run with real data).

### Release blockers (7) — must clear before a literal MVP/research-grade sign-off is credible

| Priority | Item | Depends on |
|---|---|---|
| 1 | #2 — `torch` Windows DLL bug awareness/mitigation carried into whatever environment is chosen | none — already mitigated, just must not be reverted carelessly |
| 2 | #1 — Full `poetry install --sync` + full `pytest` run, real environment | #2 (same environment) |
| 3 | #7 — CI actually executes once on real GitHub Actions infrastructure | a configured remote (human action) |
| 4 | #3 — Live YouTube collection verified | #1's environment (real egress) |
| 5 | #4 — Embeddings pipeline produces a real `embeddings_index_path` | none — can start now, fixture-testable |
| 6 | #5 — `bertopic`/`transformers`/`torch` stack installs and runs for real | #1's environment; #2's pin respected |
| 7 | #6 — Real dispatch behind `StartAnalysisRun` | #4, #5 |

### Sprint 5 prerequisites (3)

#8 (Persistence — practical prerequisite for `T-030`, not blocking `T-029` itself), #9 (tenant
isolation, = `T-032`), #10 (auth/authz, = `T-030`/`T-031`).

### Production-only prerequisites (6)

#11 (roster/Dataset granularity), #12 (idempotency middleware), #13 (CLI test collection), #14
(React frontend), #15 (query endpoints), #16 (async collection contract).

### Quality improvements (5)

#17 (cross-vendor review), #18 (AnalysisScope reconciliation), #19 (manual click-through), #20
(PDF layout polish), #21 (retry cache-miss).

### Documentation only (8)

#22–24, #28, #30, #32, #33, #34.

### Cosmetic (5)

#25, #26, #27, #29, #31.

## 3. Production Readiness Checklist

Everything a genuine production release needs, beyond the literal MVP definition — every Release
blocker resolved, every Sprint 5 prerequisite resolved (production release implies real Identity),
plus every Production-only prerequisite:

- [ ] All 7 Release blockers resolved (§2)
- [ ] `T-030`/`T-031`/`T-032` (EPIC-07) complete — real auth, roles, tenant-isolation adversarial
      test passing
- [ ] Real Persistence Layer in production use, migrations tested with a proven rollback path
- [ ] `CollectionRun`↔`Dataset` roster-scoping reconciled (item #11) — otherwise every Dataset in a
      real multi-Dataset product silently collects identical data
- [ ] `api.middleware.idempotency` implemented (item #12) — real clients will retry
- [ ] `click`/CLI test collection fixed or the CLI formally declared out of the supported surface
      (item #13)
- [ ] React frontend replaces the static dev page (item #14) — or an explicit operator decision to
      ship the static page as the real product UI, recorded as an ADR
- [ ] Query endpoints (`GetCollectionRun`/`GetAnalysisRun`/`ListDatasets`) exist (item #15)
- [ ] Async collection dispatch (`IJobDispatcher`) if real collection latency requires it (item #16)
- [ ] CI green on real infrastructure, on a real remote, for at least one full clean run
- [ ] `poetry.lock` fully current for every declared dependency (`reportlab`/`pypdf` included)

Quality-improvement and Documentation-only items are explicitly **not** on this checklist — they
do not block a production release by this assessment's own classification, though several
(cross-vendor review in particular) remain worth doing on their own merits.

## 4. Release Candidate Definition

`IMPLEMENTATION_ROADMAP.md` §6 already defines "Release Candidate" abstractly (mid-Phase 3:
billing, external API, full security/compliance). This section makes that concrete against
*today's* actual repository state, without redefining or contradicting it — a Release Candidate
for this project's own near-term path is:

**A build that has:** every Release blocker in §2 resolved and independently re-verified (not
self-reported — a real CI run, on a real remote, is part of the definition, not optional
polish); a literal T-029 re-run completed, live, by the operator, against real collected data and
real (non-demo) analysis output, with a recorded outcome; every Sprint 5 prerequisite resolved,
since a Release Candidate implies real multi-user, tenant-isolated identity — an MVP running on a
single dev-user is definitionally not yet a Release Candidate even if every other blocker clears;
every item on the Production Readiness Checklist (§3) either resolved or explicitly, individually
waived by the operator with a recorded reason (not silently dropped); zero open Release blockers,
zero open Sprint 5 prerequisites, and every Production-only prerequisite either done or
consciously deferred with an ADR recording why.

**A build does not need**, to qualify as a Release Candidate under this definition: every
Quality-improvement item resolved (cross-vendor review remains valuable but, per the operator's
own consistent ruling across five sprints, not release-gating); every Documentation-only or
Cosmetic item resolved — these can trail a Release Candidate without invalidating it.

This definition is narrower and more concrete than Roadmap §6's own phase-based one specifically
because it is anchored to this repository's actual, evidenced state today, not to the abstract
Phase 3 feature set (Billing, Public API hardening) — those remain correctly out of scope for a
Release Candidate under this narrower, nearer-term reading, and would need their own, later
reconciliation with §6's fuller definition before a real v1.0 claim.

## 5. Go / No-Go Decision Matrix

| Completed work | Continue Sprint 5? | Internal demo? | Research demo (real data)? | Production release? |
|---|---|---|---|---|
| **Nothing beyond today (T-029 implementation-side only)** | **No-Go** — `T-030` depends in practice on Persistence (finding, §0/item 8), not yet built | **Go** — proven this session, 31/31 checks, fixture/demo data | **No-Go** — 7 Release blockers open | **No-Go** |
| **+ All 7 Release blockers resolved (§2), literal T-029 re-run signed off (RR-09)** | **Conditional Go** — technically unblocked, but Persistence still recommended first (item 8) | **Go** | **Go** | **No-Go** — Sprint 5/Persistence/Production-only items still open |
| **+ Sprint 5 (`T-030`/`031`/`032`) complete** | N/A — Sprint 5 itself now done | **Go** | **Go** | **No-Go** — Production-only prerequisites (§3) still open |
| **+ Persistence Layer (RR-06/07/08) in real use** | N/A | **Go** | **Go**, now durable across sessions | **Conditional Go** — remaining items are the rest of §3's checklist |
| **+ All items in §3 Production Readiness Checklist resolved or explicitly waived** | N/A | **Go** | **Go** | **Go** — meets this document's own Release Candidate Definition (§4) |

**Reading the matrix:** an internal demo has been achievable since last session and remains so
regardless of everything else in this document — nothing here changes that. A credible research
demo (the literal MVP, real data, defensible to show outside this engagement) requires clearing
the 7 Release blockers only — Sprint 5 and Persistence are not required for that specific claim,
only for what comes after it. Sprint 5 is unblocked by BACKLOG's own graph once T-029 is signed
off, but this assessment recommends against starting `T-030` before Persistence exists, since a
registration flow whose registrations vanish on restart is not a credible feature to build against.
Production release is gated on everything — it is deliberately the narrowest Go condition in this
matrix, consistent with §4's own definition.

---

**This document classifies, prioritizes, and defines gates. It authorizes no work.** Per
instruction: the Roadmap (`RELEASE_READINESS_ROADMAP.md`) was reviewed but not modified; no
implementation was begun; no constitutional document was touched. Stopping here, awaiting
authorization.
