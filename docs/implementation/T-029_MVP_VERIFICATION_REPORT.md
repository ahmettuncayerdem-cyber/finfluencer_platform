# T-029 — MVP Acceptance Verification Report

**Date:** 2026-08-03
**Nature of this task:** verification, not implementation. Zero production or test code
changed (`git diff --stat <Sprint-4-closure-commit>..HEAD` on `src/`/`tests/` is empty,
confirmed directly, not assumed).
**Scope:** everything BACKLOG.md's own T-029 entry names — full-loop, reproducible MVP
acceptance — audited against `PRODUCT_ARCHITECTURE.md`, `IMPLEMENTATION_ROADMAP.md` §6,
`IMPLEMENTATION_PLAYBOOK.md`, and `BACKLOG.md` itself, then exercised end to end against the
real, running application.

---

## 1. Implementation Audit (Phase 1)

Every implemented capability, classified against its own architecture citation. "Fully
implemented" means the code exists, is tested, and matches the cited section's wording with no
caveat. Anything short of that is one of the other three categories, never silently rounded up.

| Capability | Architecture ref | Classification |
|---|---|---|
| Six-layer boundary, IG-001 mechanical enforcement | §12.1 | Fully implemented |
| `Tenant`/`Project`/`Dataset`/`CollectionRun` Domain entities | §10.1 | Fully implemented (deliberate 4/15-entity Sprint 0 slice, not a partial implementation of these four) |
| `AnalysisType`/`AnalysisRun` Domain entities, pinning + immutability | §10.1 | Fully implemented |
| `InterpretationRecord`/`Report`/`Export`, citation-only (never `AnalysisRun`) rule | §10.0 | Fully implemented, ast-enforced |
| Collection Engine wraps `collect/`+`youtube.py` unmodified, fixture-backed | §8.1 | Fully implemented |
| Collection Engine wired to real YouTube Data API | §8.1 | Implemented, **live-network half unverified** (T-015/T-017, environment-blocked, re-confirmed this session — see §3) |
| Topic Analysis wraps BERTopic unmodified | §8.2 | Fully implemented, **not reachable via any API route** (see below) |
| Sentiment Analysis wraps `sentiment/` unmodified | §8.2 | Fully implemented, **not reachable via any API route** (see below) |
| Plugin pattern (`IAnalysisEngine`) generalizes with zero orchestrator diff | §5 | Fully implemented, structurally proven (T-023) |
| `StartAnalysisRun` exposed over HTTP | §11.3 line 779 | Implemented differently — real orchestrator, but injected with a demo engine (`_DemoTopicAssignmentEngine`, ADR-0004), not `TopicsAnalysisAdapter`/`SentimentAnalysisAdapter` |
| `GenerateReport`/`GetReport`/`FinalizeReport`/`GenerateExport`(PDF)/table export, all over HTTP | §11.2/§11.3 | Fully implemented |
| PDF rendering, `Export` entity | §8.4/§10.1 | Fully implemented |
| CSV/table export via `master_table.py` | §8.4 | Fully implemented (documented limitation: needs both topics- and sentiment-shaped source, inherent to `build_master_table()`, not a defect) |
| FG-001 (frontend: presentation/orchestration/interaction only) | §13.14 | Fully implemented |
| FG-002 (every rendered value reproducible from backend state) | §13.14 | Fully implemented, verified directly this session (every value in every HTTP response traced to what the route returned) |
| Idempotent dispatch (`CollectionRun`, `AnalysisRun`, `FinalizeReport`, `GenerateExport`) | §4, §11.2 | Fully implemented, proven this session (see §2) |
| Interruption/checkpoint-resume, real `SIGKILL` | §1.2 | Fully implemented (T-013 fixture, T-017 live-wired-but-network-stubbed) |
| Persistence Layer | §12.1 | **Missing relative to a production release**, but this is a documented, deliberate Roadmap-Phase deferral, not a surprise — every repository across all four sprints is an in-memory stand-in |
| Authentication/authorization beyond one dev-user | §14 | Deferred intentionally — EPIC-07/Sprint 5, not yet started, exactly as scheduled |
| AI Interpretation Layer | §8.5, §15 | Deferred intentionally — Phase 2, not yet started, exactly as scheduled |
| React frontend | ADR-0001 | Deferred intentionally — static HTML stand-in since T-012, flagged every task since |

**No unexpected-and-previously-undocumented gap was found during this audit.** Every deviation
below traces to a finding already on record somewhere in `BACKLOG.md` (F-002, TD-03/TD-04, the
`click` version drift, the demo-engine ADR-0004, the missing Persistence Layer) — this session's
contribution is compiling them against the MVP acceptance bar specifically and re-verifying each
one directly rather than trusting the prior write-up.

## 2. End-to-End Verification (Phase 2)

Executed via a real `TestClient` against the real `create_app()` FastAPI app (real routing, real
orchestrators, real adapters — fixture/demo data, since live YouTube network egress remains
blocked in this sandbox, the same constraint T-015/T-017 already found and this session
re-confirms rather than re-discovers). Script and full pass/fail evidence available on request;
summary below.

**31/31 checks passed.** Project creation → Collection Run (real fixture pipeline, 4
analysts/4 videos/8 comments/4 transcripts) → duplicate-dispatch idempotency (same run id
returned, no re-collection) → Analysis Run via the real `StartAnalysisRunOrchestrator` (demo
engine, `topic_count=3`) → second Analysis Run cited into the same Report → Report retrieval →
Finalize (idempotent, second call is a no-op) → CSV/table export on a topics-only Report
(correctly 422, not a crash) → PDF export (real 2686-byte `%PDF-1.4` file, correct
`Content-Disposition`) → idempotent replay (byte-identical second response, same file on disk) →
restart-where-applicable (fresh `create_app()` against the same data directory: in-memory Report
state is correctly gone — expected, no Persistence Layer — but the collected parquet files
survive on disk, since those are real file writes, not repository bookkeeping) → five failure
scenarios (export-before-finalize rejected, unknown report/analysis-run rejected, malformed
request body rejected, path/body mismatch rejected) — all behaved exactly as the architecture and
prior tasks' own tests already specified, none silently swallowed.

## 3. Quality Gates (Phase 3)

| Gate | Result |
|---|---|
| Full regression (`tests/unit`, excluding 2 pre-existing `click`-drift-broken CLI files) | **1087 passed, 1 skipped** — identical to the count already on record after T-028, confirming zero regression from this verification pass (which changed no source) |
| `tests/integration` | **5 passed** |
| Walking Skeleton regression subset (`test_domain`+`test_presentation`+`test_application`+`test_infrastructure/test_collection`+`test_api`+`test_integration`) | **248 passed** |
| IG-001 (`scripts/check_layer_dependencies.py`) | **Clean** |
| Architecture conformance (`test_architectural_conformance.py`, ast-based) | **6/6 passed** |
| API conformance / presentation smoke (`test_ui_page.py`) | **2/2 passed** |
| Excluded CLI files (`test_cli.py`, `test_reporting/test_main.py`) | Re-run, still fail at collection with the same pre-existing `CliRunner(mix_stderr=...)`/`click` 8.4.1 mismatch — confirmed unrelated to this session (zero source files touched) |

No failure was ignored or hidden; the one excluded pair is the same, already-documented,
pre-existing environment drift carried since T-027.

## 4. MVP Gap Analysis (Phase 4)

| Deviation | Architecture ref | Evidence | Risk | Recommendation |
|---|---|---|---|---|
| `StartAnalysisRun`'s only reachable engine is a demo stand-in, not real BERTopic/sentiment | §6 (MVP requires "topic *and* sentiment analysis") | ADR-0004; `bootstrap.py::_DemoTopicAssignmentEngine`; ARB-01 TD-03/TD-04 | **High** — this is the single largest gap between what runs today and the literal MVP acceptance criterion | Resolve TD-03/TD-04 (AnalysisType-keyed dispatch) and wire the real adapters behind `StartAnalysisRun` before attempting a literal T-029 sign-off |
| Live YouTube network collection unverified in this sandbox | §6 ("collect real YouTube data") | T-015/T-017 `httplib2.socks.HTTPError: 403` against `googleapis.com`, re-confirmed this session by inspection (not re-attempted, since the constraint is already twice-proven and this session made no network changes) | **High** for literal MVP sign-off, **zero** for the fixture-backed path (fully proven) | Run `scripts/t015_live_smoke_test.py`/`t017_live_interruption_manual.py` in an environment with real egress |
| `StartCollectionRun` runs synchronously, not per §11.2's async/`queued` contract | §11.2 | `GetCollectionRunResponse` used instead of `CollectionRunAccepted` (T-012's own documented substitution) | Low — functionally correct for MVP scale, diverges from the stated contract | Build `IJobDispatcher` only once synchronous latency is a real product problem |
| No Persistence Layer — every repository is in-memory | §12.1 | Directly reproduced this session (§2, restart check 10a): a fresh process loses all Report/Export/AnalysisRun/Project state | **High for any real, multi-session researcher workflow**; **zero for a single continuous demo session** | Persistence Layer is not yet a numbered task on the critical path; needs one before a real release, independent of T-029 |
| No `GetCollectionRun`/`GetAnalysisRun`/`ListDatasets` query endpoints | §11.2 line 684 (F-002) | `grep '@router\.' api/routes/*.py` — only `GetReport` exists as a query route | Medium — combined with no Persistence, a researcher who navigates away mid-session cannot look their run back up (though the underlying data files remain on disk) | Add these queries alongside whichever task adds real Persistence |
| `api/routes/reporting.py` conflates "not found" and "invalid state" under HTTP 404 | n/a (implementation precision) | T-028's own documented flag; re-observed directly in checks 11a/11b/11c this session (all return 404 regardless of cause) | Low, cosmetic | Introduce typed exceptions distinguishing the two cases in a future pass |
| `pyproject.toml` requires Python `>=3.11`; this sandbox (and every verification this entire engagement has run) uses 3.10.12 via `PYTHONPATH=src`, never a real `pip install -e .`/`poetry install --sync` | T-002/T-003 (open, environment-blocked since Sprint 0) | Confirmed still open in `BACKLOG.md`; no session this entire engagement has closed it | **High for "can another developer clone and run this"** specifically — every green test result on record, including this session's, was produced through the same workaround, never through the declared installation path | Verify a real `poetry install --sync` + full suite pass in a genuine Python 3.11+ environment before treating any test result (including this one) as a substitute for that proof |
| Cross-vendor AI review outstanding on ~13 tasks (Domain Model and orchestrator-pattern changes) | Playbook Part B.1 | Never performed this entire engagement; operator has repeatedly ruled it non-blocking | Medium, accepted and carried by explicit operator decision each time | Standing item, not newly raised here |

## 5. Release Readiness (Phase 5)

**Can Sprint 4's deliverable be released internally, as a demo?** Yes. The fixture/demo-data
path is fully proven — real HTTP, real orchestrators, real file I/O, real idempotency, zero
regressions.

**Can it be demonstrated live?** Yes, over fixture/demo data — proven directly this session (§2)
and previously via T-014's real `uvicorn` process check.

**Can another developer clone and execute it?** **Not proven, and this session found the clearest
evidence yet that it should not be assumed.** Every single test result this entire engagement has
ever produced, including this session's, ran under `PYTHONPATH=src` against Python 3.10.12 — never
through the `pyproject.toml`-declared `>=3.11` installation path (T-002/T-003, still open). A
clone-and-run by someone using the declared toolchain (`poetry install`) has never actually been
attempted.

**Can another researcher reproduce the workflow?** Yes, for the fixture-backed workflow
(deterministic, checkpoint/resume proven twice over — T-013 fixture, T-017 live-wired). **No**,
for the literal MVP promise with real YouTube data — blocked on live network egress and the
demo-engine limitation above.

**Is every critical architectural promise actually demonstrated?** Citation-immutability
(§10.0), the six-layer boundary (IG-001 + ast checks), plugin-pattern generalization (T-023),
idempotency, and interruption/resume are all directly demonstrated with real evidence, this
session and prior ones. The one promise **not** demonstrated is §6's own MVP definition itself:
real YouTube data plus real topic-and-sentiment analysis, run live, once, by a human. That is
what BACKLOG's own T-029 entry requires (**Role: Human sign-off; Verification: the end-to-end run
itself, performed once, live**) and what this verification pass — thorough as it is — cannot
substitute for.

## 6. Documentation (Phase 6)

No constitutional document modified. This report and `BACKLOG.md`'s T-029 entry (see below) are
the only documents this task touches. No new numbered Finding was needed — every deviation found
traces to an existing one.

## Conclusion

**"Can this repository honestly be called a working MVP?"** Honestly: **not yet, by the
architecture's own literal §6 definition** — because that definition specifically requires real
collected YouTube data and real topic-and-sentiment analysis, and neither is reachable today
(live collection is network-blocked in every environment tried so far; the only API-reachable
analysis path is an intentionally-scoped demo stand-in). What **is** honestly true, and now
verified with direct evidence rather than assumed: every piece of engineering built across
Sprints 0–4 works correctly, together, over real HTTP, with zero regressions, zero unexpected
architectural gaps, and complete idempotency/interruption guarantees, against the best data this
sandbox can produce. The distance remaining to a literal MVP sign-off is exactly two known,
already-named items — a real network-capable environment, and wiring the real analysis adapters
behind `StartAnalysisRun` — not a rediscovery of new problems.
