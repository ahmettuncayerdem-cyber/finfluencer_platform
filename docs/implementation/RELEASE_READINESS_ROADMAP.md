# Release Readiness Roadmap

**Date:** 2026-08-03
**Status:** Planning artifact — Temporary Practice, same classification as `BACKLOG.md` (Playbook
Part K). Not constitutional, not an ADR, not a redesign of anything in `PRODUCT_ARCHITECTURE.md`.
**Trigger:** `T-029_MVP_VERIFICATION_REPORT.md`'s three named release blockers.
**Explicitly out of scope for this document:** implementation, architecture change, constitutional
document edits. This roadmap classifies and sequences remediation work; it authorizes none of it.
**Task numbering:** new items are labeled `RR-01`...`RR-10` to avoid colliding with `BACKLOG.md`'s
own `T-0XX` numbering, since folding these into that sequence is an operator decision, not made
here. Two items (RR-02, RR-03) are the same work already named `T-002`/`T-003` — referenced by
both labels below.

---

## 0. Framing note, before classification

The three blockers are not equally binding on the same gate. `IMPLEMENTATION_ROADMAP.md` §6's own
MVP definition text — "a researcher can create a Project, collect real YouTube data, run topic and
sentiment analysis, view and export results with citations to raw analysis output" — names nothing
about surviving a restart. That means:

- **Blocker 1** (Python 3.11/Poetry path) and **Blocker 2** (real collection + real analysis) sit
  directly on the literal path to re-running T-029 for a genuine human sign-off.
- **Blocker 3** (in-memory Persistence) does **not** block a literal §6 MVP sign-off performed in
  one continuous live session. It blocks something else, real and worth fixing, but a different
  gate: a *safe, credible, multi-session release* — and, not previously stated this plainly, it is
  also a **practical prerequisite for Sprint 5's own T-030** ("real user registration and login"
  is not a meaningful feature if the registered user vanishes on restart), even though
  `BACKLOG.md`'s current dependency graph does not name this dependency. This is flagged as a
  genuine finding of this roadmap, not asserted as already-decided.

This distinction drives the execution order in §3.

## 1. Classification

Working definitions used below (none of these are formalized governance IDs — this is
operational vocabulary for this roadmap only, not a constitutional addition):

- **Sprint 5 task** — sits inside EPIC-07 (Identity Widening) per `BACKLOG.md`'s own critical path.
- **Release Engineering task** — implementation work that fills in an already-specified
  architectural box (no new ADR, no new Domain concept) but is nontrivial code, needed to make
  the existing, approved design actually production-real.
- **Infrastructure task** — provisioning or verifying the underlying compute/network/runtime
  environment itself; no application code changes.
- **Deployment task** — packaging and standing up the running system in a real, reachable
  environment, including operational tooling (migrations, secrets, network topology per DAG-001).
- **Architecture task** — requires a genuinely new architectural decision. **None of the three
  blockers require this category** — itself a finding worth stating plainly: all three are
  environment or implementation gaps, not design gaps, which is consistent with T-029's own
  conclusion that the architecture holds.

| Blocker | Sub-parts | Primary classification | Why not the others |
|---|---|---|---|
| **1. Python 3.11/Poetry path never validated on a clean environment** | none — single-piece | **Infrastructure task** (already `T-002`/`T-003`, open since Sprint 0) | Not Architecture (no design decision pending — `pyproject.toml`'s constraint is already chosen, just unverified); not Release Engineering (there is no code to write, only an environment to obtain and a command to run); not Deployment (this is "can it install," not "can it run in production topology"); not Sprint 5 (unrelated to Identity scope) |
| **2. Real YouTube collection + real BERTopic + real Sentiment, never completed in an unrestricted environment** | **2a.** Live YouTube network collection (`T-015`/`T-017`'s already-built, already-tested, network-stubbed-only code) | **Infrastructure task** | Zero new code needed — `T-015`/`T-017` already proved the code path with only the network transport stubbed; this is purely "run it somewhere with real egress" |
| | **2b.** Real `TopicsAnalysisAdapter`/`SentimentAnalysisAdapter` reachable via `StartAnalysisRun` (replacing the `ADR-0004` demo engine, i.e. resolving `ARB-01`'s TD-03/TD-04) | **Release Engineering task** | Not Architecture — §5's plugin pattern (`IAnalysisEngine` Protocol) already covers this; `T-023` already proved it generalizes with zero orchestrator diff for the *engine* itself. What's missing is only the *dispatch/wiring* — a composition-root/bootstrap concern, not a new Domain concept. Not Infrastructure alone — real code must be written (see RR-05 below) |
| **3. In-memory repositories instead of a production Persistence Layer** | **3a.** Real Persistence implementations (SQLAlchemy/PostgreSQL, `ADR-0001`'s already-accepted choice) for all 6 repository Protocols | **Release Engineering task** | Not Architecture — `ADR-0001` already chose the technology; building the adapters is the same "Domain defines, Infrastructure/Persistence implements" pattern every prior adapter task (`T-010`, `T-019`, `T-022`) already used without needing new architecture |
| | **3b.** Schema-migration tooling + real DB provisioning | **Deployment task** (migrations, secrets, DAG-001's Data-Tier network isolation) blocked on an **Infrastructure task** (a reachable Postgres instance) | Migrations and real-DB standup are packaging/operations concerns, not application code |

## 2. Remediation task inventory

| ID | Task | Category | Effort |
|---|---|---|---|
| **RR-01** | Provision a clean, unrestricted verification environment: real Python ≥3.11 interpreter, network egress to PyPI + GitHub release assets + `googleapis.com`, enough resources for a local Postgres and BERTopic model downloads | Infrastructure | Not Claude-measurable — pure availability/access, outside this sandbox entirely |
| **RR-02** (= `T-002`) | Run `poetry install --sync` in RR-01's environment; run the full test suite through the *declared* install path (no `PYTHONPATH=src` workaround); record real pass/fail counts | Infrastructure / verification | XS |
| **RR-03** (= `T-003`) | Run a real `poetry lock` in RR-01's environment to reconcile `poetry.lock` to `pyproject.toml`'s `>=3.11,<3.14` constraint | Infrastructure / verification | XS |
| **RR-04** (= `T-015`/`T-017` live halves) | Run `scripts/t015_live_smoke_test.py` and `scripts/t017_live_interruption_manual.py` in RR-01's environment against a real, quota-configured YouTube Data API key | Infrastructure | S |
| **RR-05** | Build an `AnalysisType`-keyed dispatch so `StartAnalysisRun` can invoke real `TopicsAnalysisAdapter`/`SentimentAnalysisAdapter`. Cheapest viable shape, consistent with `ARB-01`'s own non-blocking classification of this gap: **not** a general plugin registry — one dedicated `StartAnalysisRunOrchestrator` instance per `AnalysisType`, selected in `bootstrap.py`/the route layer by `analysis_type_id`, zero orchestrator code changes (mirrors `T-023`'s own already-proven zero-diff finding) | Release Engineering | M (implementation, fixture-testable now) + additional S for real-data verification once RR-01/RR-04 exist |
| **RR-06** | Build real Persistence-layer implementations (SQLAlchemy models + repository adapters) for `IProjectRepository`, `ICollectionRunRepository`, `IAnalysisRunRepository`, `IReportRepository`, `IInterpretationRecordRepository`, `IExportRepository` | Release Engineering | L — largest single item; six repositories, schema design, integration tests |
| **RR-07** | Choose and wire a schema-migration tool (e.g. Alembic); establish backup/restore discipline before any real data exists | Deployment | S–M |
| **RR-08** | Update `bootstrap.py`'s composition root to select real Persistence vs. the existing in-memory stand-ins via configuration, preserving the dev/demo path unchanged | Release Engineering | S |
| **RR-09** | Re-run T-029 itself for real: literal §6 acceptance, live, once, human-performed, against RR-04's real collected data and RR-05's real analysis engines | Release Engineering (gating) — **Role: Human sign-off**, per `BACKLOG.md`'s own T-029 entry, unchanged | XS effort, gated entirely by human availability and RR-04/RR-05 completion |
| **RR-10** | `T-030`/`T-031`/`T-032` (EPIC-07, Identity Widening) | **Sprint 5 task** | Out of this roadmap's scope — listed only to show where remediation work reconnects to the existing critical path |

## 3. Dependency graph

```
RR-01 (provision environment)
  ├──> RR-02 (poetry install --sync + real suite run)
  ├──> RR-03 (poetry lock reconciliation)
  ├──> RR-04 (live YouTube verification)          ──┐
  └──> RR-05 real-data verification half            │
                                                       ├──> RR-09 (literal T-029 sign-off)
RR-05 implementation half (fixture-testable now) ─────┘        │
                                                                  │
[independent branch, no RR-01 dependency]                        │
RR-06 (Persistence implementations)                              │
  └──> RR-07 (migrations, needs a reachable Postgres)             │
        └──> RR-08 (bootstrap wiring)                             │
                                                                    ▼
                                          RR-08 (recommended, not textually required) ──> RR-10 (T-030, Sprint 5)
                                          RR-09 ─────────────────────────────────────────> RR-10 (T-030, Sprint 5, per BACKLOG's existing graph)
```

**Read this graph as two independent tracks that only need to converge before Sprint 5, not
before each other:** the collection/analysis track (RR-01→02/03/04/05→09) and the persistence
track (RR-06→07→08). Nothing in the persistence track blocks RR-09's literal sign-off; nothing in
the collection track blocks starting RR-06.

## 4. Execution order

**Phase A (can start immediately, this sandbox or any sandbox):**
RR-05's implementation half (build the dispatch mechanism, test against fixtures — the same
technique `T-019`/`T-022` already used successfully) and RR-06 (Persistence implementations,
schema design, tested against a local/dev database if any Postgres-capable environment is
reachable — does not require RR-01's full unrestricted-network profile, only a database).

**Phase B (requires RR-01, the environment gate — outside this sandbox):**
RR-02, RR-03 (can run together, same environment, independent files) and RR-04 (needs RR-01 plus a
real, quota-configured YouTube Data API key — a separate human action from RR-01 itself). RR-05's
real-data verification half also lands here.

**Phase C (requires Phase B's collection/analysis results, or Phase A's persistence work):**
RR-07 (needs a real reachable Postgres, lighter requirement than full RR-01 — could start as soon
as RR-06 is code-complete and any DB instance is reachable) then RR-08.

**Phase D (gating, human-performed, requires Phase B complete):**
RR-09 — the literal T-029 re-run. Per §0's framing note, RR-06/07/08 are not textually required to
reach RR-09, but are strongly recommended to be complete or near-complete first, since Sprint 5's
own T-030 depends on them in practice even though `BACKLOG.md`'s graph doesn't say so today.

**Phase E:**
RR-10 (Sprint 5 / EPIC-07) — outside this roadmap's authorization scope entirely, listed only for
continuity.

## 5. Technical risks

**RR-01/02/03.** This entire engagement's every green test result, across five sprints, ran under
`PYTHONPATH=src` against Python 3.10.12 — never through the declared `>=3.11` install path. Real
dependency resolution on 3.11+ is genuinely untested territory; a version conflict among
`pandas`/`pyarrow`/`bertopic`/`transformers`/`sentence-transformers` surfacing only now, five
sprints in, is a real possibility, not a formality to rubber-stamp.

**RR-04.** Real network timing variance (unlike deterministic fixtures); YouTube Data API quota
limits; possible ToS/rate-limit friction on repeated verification runs.

**RR-05.** Real BERTopic output is non-deterministic and unbounded in shape (topic labels/counts)
in a way the current deterministic demo engine (`topic_id = hash(comment_id) % 3`) never exercised
downstream code against. `reporting/master_table.py`'s schema assumptions and the PDF renderer's
content-escaping have only ever been proven against demo-shaped or fixture-shaped data — a
genuinely new topic label containing markup-unsafe characters, for instance, is untested territory
for `PdfRendererAdapter._escape()`.

**RR-06.** The largest single scope item and the highest-stakes one to get wrong: schema mistakes
are expensive to unwind once real data exists. The in-memory repositories have never had their own
implicit invariants (e.g. `IExportRepository`'s natural-key `(report_id, report_version, format)`
uniqueness) stress-tested under real concurrent access — a real database enforces this differently
than a Python dict does, and could surface either a false "clean" idempotency proof from the
in-memory tests, or a genuine constraint-violation bug real Persistence would newly expose.

**RR-07.** No migration tool has ever been used in this project; first adoption always carries
tooling-fit risk independent of the schema itself.

**RR-09.** The single highest-stakes task in this entire roadmap by consequence, not by effort: a
live, once-performed, human-executed run with no automated safety net beyond everything already
tested. A failure here is a genuine finding, not a retry-and-forget event.

## 6. Acceptance criteria

- **RR-01:** a shell in the target environment reports Python ≥3.11, `poetry --version` succeeds,
  and `curl` (or equivalent) reaches both `pypi.org` and `googleapis.com`.
- **RR-02:** `poetry install --sync` exits 0; the full test suite (no `--ignore`, no `PYTHONPATH`
  workaround) runs to completion with a pass/fail count recorded, whatever it is — a lower pass
  count than 1087 is itself the acceptance evidence this task exists to produce, not a failure of
  the task.
- **RR-03:** `poetry.lock`'s declared Python constraint matches `pyproject.toml`'s exactly; `git
  diff` of the lock file is the artifact of record.
- **RR-04:** both scripts complete against a real channel with no `403`/proxy error; collected
  parquet row counts are nonzero and match the target channel's real content.
- **RR-05:** an `AnalysisRun` created via `StartAnalysisRun` against a real `AnalysisType` produces
  real, non-demo topic or sentiment output, verified by a human spot-check of at least one real
  topic label/sentiment score against the source comments — not just a passing automated test.
- **RR-06:** every existing repository-level unit test (currently run against `Fake*Repository`
  test doubles) passes unmodified against the real Persistence implementation, plus new tests for
  behavior the in-memory version couldn't exercise (real uniqueness-constraint violations, real
  transaction rollback on a mid-write failure).
- **RR-07:** a fresh, empty database reaches current schema via migration alone (no hand-applied
  SQL); a rollback migration is proven to reverse it cleanly.
- **RR-08:** `bootstrap.py`'s existing dev/demo path (in-memory, fixture-backed) still works
  unmodified when Persistence is not configured — this is the rollback mechanism, not a separate
  feature.
- **RR-09:** the operator personally completes the full researcher workflow — Project, real
  collection, real topic analysis, real sentiment analysis, view, export — once, live, and records
  the outcome, per `BACKLOG.md`'s own T-029 Verification line, unchanged by this roadmap.

## 7. Rollback strategy

**RR-02/03.** No production state exists to roll back — these are read-only verification runs
against a disposable environment. If `poetry lock` produces an unexpected resolution, the change
is confined to `poetry.lock` alone and is a plain `git revert`.

**RR-05.** Wire the real dispatch behind the *same* composition-root seam the demo engine already
uses (`bootstrap.py`), not a replacement of it — keep `_DemoTopicAssignmentEngine` available and
selectable, so a defect in real-engine wiring is a configuration flip back to the demo path, not a
code revert, and the existing 45 T-028 tests built against the demo engine keep passing throughout.

**RR-06/RR-08.** Same pattern: real Persistence and the in-memory stand-ins coexist behind
configuration, exactly like RR-05. This is not a new idea introduced here — it is the same
dev/demo-vs-real split `bootstrap.py` has used since T-012. A Persistence-layer defect is a
configuration rollback to in-memory mode, with the caveat that any real data written in the
interim needs its own backup/restore plan (RR-07's job specifically).

**RR-07.** Standard practice, newly adopted here: every migration must have a tested down-migration
before being applied to any environment holding real data; a backup is taken immediately before
the first migration ever applied to a non-empty database.

**RR-09.** Not a code change — nothing to roll back. If the live run surfaces a defect, the
correct response is a new Finding and a new remediation task, the same discipline this engagement
has used at every prior gate, not a rollback of anything.

## 8. Required human actions

- **RR-01:** provisioning the environment itself — entirely outside Claude's own capability, the
  same constraint that has stood since `T-001`.
- **RR-04:** supplying/configuring a real YouTube Data API key with adequate quota; approving the
  live network calls (this touches real external credentials — per this engagement's own standing
  rule, Claude does not handle API keys/secrets directly and should not be asked to).
- **RR-06/RR-07:** approving and provisioning real production database hosting/credentials —
  same credential-handling boundary as above.
- **RR-09:** the actual live run and sign-off — `BACKLOG.md`'s own T-029 Role line ("Human
  sign-off"), unchanged by anything in this roadmap.

## 9. Parallelizable tasks

RR-02 and RR-03 (same environment, disjoint files). RR-05's implementation half and RR-06 in full
(genuinely independent verticals — collection/analysis vs. persistence — sharing no code path).
RR-04 and RR-05's implementation half (RR-05 doesn't need RR-04's results to be written and
fixture-tested, only to be *fully* verified against real data).

## 10. Tasks requiring a fresh environment

RR-01 itself, and everything gated behind it: RR-02, RR-03, RR-04, RR-05's real-data verification.
RR-06/RR-07 need at minimum a reachable Postgres instance — a materially lighter requirement than
full RR-01 (no Python-version or YouTube-egress dependency), and could plausibly be satisfied
without waiting for RR-01 if any database-capable environment becomes available sooner.

## 11. Tasks that must be executed outside the current sandbox

RR-01 (this sandbox's own network/Python-version restriction is the reason `T-002`/`T-003` have
been open since Sprint 0 — nothing about this sandbox has changed). RR-02, RR-03, RR-04, and
RR-05's real-data verification inherit this directly. RR-09, by its own nature (a live, human-
performed run), was never going to be executable from within any automated session at all.
RR-05's implementation half and RR-06 (schema/adapter code, fixture- or local-DB-tested) are the
two items on this entire roadmap that **can** proceed inside a constrained sandbox like this one,
if authorized.

---

**This roadmap classifies and sequences; it authorizes nothing.** Per instruction, no
implementation has begun, no architecture has been redesigned, and no constitutional document has
been touched. Stopping here, awaiting explicit authorization for any RR-item above.
