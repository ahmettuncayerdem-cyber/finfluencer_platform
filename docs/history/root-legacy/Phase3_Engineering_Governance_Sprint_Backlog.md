# Engineering Governance — Technical Debt Backlog, Version Roadmap, Sprint Plan & Quality Gates

**Role note:** This document is governance, not a new audit. It builds on `Phase2_Repository_Risk_Matrix_and_ADRs.md` (Risk Matrix, ADR-P2-001..005) without recreating it. Where this document's judgments differ from Phase 2, the difference is stated explicitly, with reason — nothing is silently overwritten.

**Confidence key used throughout:** **Verified** (I opened the file, this session or the last, and cite line numbers) / **Likely** (reasoned inference from verified evidence, not itself directly observed) / **Unknown** (no evidence gathered yet — stated as such, not guessed).

---

## 1. Technical Debt Backlog

Consolidated from Phase 2's R1-R15, reclassified by engineering category. This is the live backlog — new findings get appended here, not folded silently into old rows.

| ID | Category | Severity | Business Impact | Engineering Impact | Probability | Release Gate | Confidence |
|---|---|---|---|---|---|---|---|
| R1 | Testing | Critical | High — undetected corruption of the research dataset itself | High — 5 methods with zero regression protection | High | v0.2.0 | ✅ **RESOLVED** this pass — see §6 Implementation Log |
| R2 | Bug | High | High — silent data loss undermines the platform's core reproducibility claim | Medium — single method, clear fix | Medium | v0.2.0 | ✅ **RESOLVED** this pass — see §6 Implementation Log |
| R3 | Bug | Medium | Low — confusing error, no data loss | Low | Low-Medium | v0.2.1 | Verified |
| R4 | Technical Debt | Medium | Medium — fragile against upstream (Google) message-text drift | Low | Medium | v0.2.1 | Verified |
| R5 | Architecture | Medium | High if triggered — silent under-collection | Medium — needs a design decision, not just a patch | Low | v1.0 | Verified |
| R6 | Technical Debt | Low | Low | Trivial | — | Future | Verified (handover, re-observed) |
| R7 | Bug / Infrastructure | Critical | High — breaks a documented provenance guarantee on every run | Medium — one file, but a real design fix | **Certain** | v0.2.0 | ✅ **RESOLVED** this pass — see §6 Implementation Log |
| R8 | Bug / Architecture | High | High — a "safe preview" feature silently isn't safe | Medium | Medium | v0.2.0 | ✅ **RESOLVED** this pass — see §6 Implementation Log |
| R9 | Bug / Infrastructure | High | High — undetected loss of checkpoint records | Low-Medium — cheap fix, real value | Low-Medium | v0.2.1 | Verified |
| R10 | Technical Debt | Medium | Low today (self-documented non-breaking WIP) | High (multi-file migration) | — | Future — already tracked via `ADR-0001` | Verified |
| R11 | Bug / Security-adjacent | Medium | Medium — fails mid-run, wastes quota; **no data-leakage confirmed** | Low | Medium | v0.2.1 | Verified |
| R13 | Testing (process) | Medium | High — coverage numbers currently overstate real safety | Medium (needs new integration-test category) | — | v0.2.1 / v1.0 | Verified |
| R14 | Release Engineering | Medium (process) | High for release credibility, zero for application correctness | Low-Medium (commit reconciliation, changelog fix, remote setup) | Certain | v0.2.0 (Blocker — process) | **Re-verified this pass — see `R14_Release_Engineering_Verification.md`. Mixed result: real docs, uncommitted everything, no remote, changelog/version contradiction.** |
| R15 | Testing / Audit coverage | — | — | — | — | **CLOSED** — `collect/` subpackage audited this pass; see Phase 2 Amendment 1 | Verified |
| R16 | Bug / Architecture | High | Medium — operational friction, not data loss (loud failure, resumable) | Medium — one file, mirrors an existing correct pattern | Medium | v0.2.1 | Verified — new finding, `collect/` audit |
| R17 | Testing (test-harness artifact) | Medium | Low — zero production impact (separate OS streams outside `CliRunner`) | Low — **13 tests** (corrected from 12), **two mechanisms** sharing one fix (`mix_stderr=False` or assert on `result.stdout`): 10 from R7, 3 from an independent `statsmodels`/`numpy` warnings leak | **Certain** in current test suite | v0.2.1 | Verified — root-caused during R2's sweep, count/mechanism-split corrected during R14 (`R14_Release_Engineering_Verification.md` §1.4, §3) |
| — | Security | Unknown | Unknown | Unknown | — | Gate cannot pass until scoped | **No dedicated security pass performed in this audit to date** |
| — | Performance | Unknown | Unknown | Unknown | — | Gate cannot pass until scoped | **No dedicated performance pass performed in this audit to date** |

Two rows added this turn that did not exist in Phase 2: the explicit **Security** and **Performance** gate rows. Phase 2's audit never targeted these dimensions — I did not, at any point, review dependency versions for known CVEs, review input-validation/injection surfaces systematically, or profile any hot path. Carrying an implicit "presumably fine" assumption into a release-readiness document would violate the "never speculate" instruction, so these are logged as open, unscored gates rather than left out.

---

## 2. Version Roadmap

| Version | Contains | Status |
|---|---|---|
| **v0.2.0** | R1, R2, R7, R8 resolved; R15 (`collect/` audit) closed; R14 re-verified; Security/Performance gates at minimum *scoped* (not necessarily fully remediated, but no longer "Unknown") | **Blocked** — R1/R2/R7/R8 resolved, R15 closed, **R14 re-verified and is now itself the active blocker** (process, not code — see `R14_Release_Engineering_Verification.md`); Security/Performance remain unscored |
| **v0.2.1** | R3, R4, R9, R11, R13, R16, R17 | Planned, not started |
| **v1.0** | R5 (fix or documented limitation), R13 hardening, full open-source-readiness re-check | Planned |
| **Future** | R6, R10 (already tracked via `ADR-0001`) | Tracked, not urgent |

---

## 3. Sprint Plan

### Sprint 1 — v0.2.0 Blocker Remediation + Audit Closure
**Objectives:** Close every confirmed v0.2.0 blocker; close the one remaining unaudited module (`collect/`) so v0.2.0 scope is based on complete evidence, not a partial audit.

**Tasks**
1. ~~ADR-P2-001 implementation — provider test coverage (R1)~~ — **DONE this pass.** Final item in the approved Sprint 1 sequence. See §6 Implementation Log.
2. ~~ADR-P2-002 implementation — 404/disabled conflation fix (R2)~~ — **DONE this pass.** See §6 Implementation Log. Surfaced one new finding during its regression sweep, R17 (test-harness artifact, routed to v0.2.1, not a blocker).
3. ADR-P2-003 implementation — `configure()` no-op fix (R7) — done, prior pass
4. ADR-P2-004 implementation — dry-run side-effect fix (R8) — done, prior pass
5. ~~Complete architecture audit of `collect/` subpackage (R15)~~ — **DONE this pass.** Result: `channels.py`, `quota.py`, `main.py` clean; confirmed R2's scope must extend to `collect/comments.py`; found one new independent High finding, R16 (`collect/videos.py`), routed to v0.2.1 per ADR-P2-006. Full detail: Phase 2, Amendment 1.
6. ~~Re-verify R14 (Release Engineering claims) against the repository directly~~ — **DONE this pass.** Result: mixed, No-Go for v0.2.0 on release-engineering grounds. Full report: `R14_Release_Engineering_Verification.md`.

**Dependencies:** None of tasks 1-4 depend on each other (four independent files/fixes). Task 5 (collect/ audit) may surface new blockers that change Sprint 1's exit criteria — flagged as a risk below, not hidden.

**Estimated Effort:** ~5-6 engineer-days for tasks 1-4 (per ADR-P2-001..004 estimates) + audit time for task 5 (unscoped until performed — 6 files, comparable in size to `youtube.py`, so budget roughly 1 audit-session) + ~1 hour for task 6.

**Expected Risk Reduction:** Removes all four Critical/High findings currently blocking release; closes the last audit gap so "v0.2.0 ready" is a claim backed by a complete review, not a partial one.

**Exit Criteria:** R1/R2/R7/R8 status = Resolved with passing regression tests per their ADR's "Required Tests" — **met**; R15 audit complete with any new findings triaged into this backlog — **met**; R14 re-verified (confirmed or corrected) — **met this pass (mixed result — see `R14_Release_Engineering_Verification.md`). All of Sprint 1's own exit criteria are now met; this does not mean v0.2.0 is ready to ship, since R14's re-verification itself surfaced a new, unresolved release-process blocker.**

---

### Sprint 2 — v0.2.1 Hardening
**Objectives:** Close the Strong-Recommendation backlog; convert the R13 coverage/correctness gap from an observation into an actual test-suite improvement.

**Tasks**
1. R3 — `resolve_channel` URL-fallthrough fix
2. R4 — centralize comments-disabled detection
3. R9 — `read_jsonl` mid-file corruption handling
4. R11 — eager `ANON_SALT` validation at config-load time
5. R13 — add the two integration-test categories this audit's own findings prove are missing: (a) cold-import + CLI-entrypoint test asserting the real logging config takes effect, (b) dry-run-then-inspect-marker test

**Dependencies:** Sprint 1 must land first — R13's tests are specifically regression tests *for* R7 and R8, so they need R7/R8's fixes to exist first.

**Estimated Effort:** ~3-4 engineer-days.

**Expected Risk Reduction:** Removes remaining known Medium/High findings; closes the specific gap (coverage metric not catching cross-module bugs) that let R7/R8 ship unnoticed in the first place — this is the sprint that prevents a repeat of Sprint 1's category of bug, not just fixes the instances found.

**Exit Criteria:** R3/R4/R9/R11 resolved; the two new integration tests exist, pass, and are confirmed (by manual inspection, since this is exactly the class of test that can pass vacuously if written carelessly) to actually fail against the pre-fix code.

---

### Sprint 3 — v1.0 Readiness
**Objectives:** Resolve or formally accept R5; scope and execute the Security and Performance gates that have never been run; final Open Source Readiness pass.

**Tasks**
1. R5 — design decision on `enumerate_videos` ordering assumption (fix vs. documented limitation)
2. Scope and run a Security pass (dependency audit, secrets handling beyond R11, input validation surfaces) — **currently fully unscoped; this sprint's first task is defining what "done" means here, not executing an assumed checklist**
3. Scope and run a Performance pass — **same caveat**
4. Full Open-Source-Readiness re-check against all prior gates

**Dependencies:** Sprints 1-2 complete.

**Estimated Effort:** Unknown — tasks 2 and 3 cannot be estimated honestly until scoped (task 0 of this sprint is producing that scope). R5 alone: ~0.5-1 engineer-day.

**Expected Risk Reduction:** Closes the two gate categories this audit has carried as "Unknown" since Phase 2 — currently the largest source of uncertainty in any v1.0 go/no-go decision.

**Exit Criteria:** R5 resolved or explicitly documented as an accepted limitation in user-facing docs; Security and Performance gates have moved from Unknown to a scored, evidenced state (pass or a new, triaged backlog).

---

## 4. Quality Gate Assessment — Current State, v0.2.0 Candidate

| Gate | Status | Evidence | Confidence |
|---|---|---|---|
| Architecture | ✅ **PASS for v0.2.0 scope** | R7 and R8 — the two confirmed contract violations — are both **resolved**. R16 (`collect/videos.py`, ADR-P2-006) remains open but is routed to v0.2.1, not part of the v0.2.0 candidate's evidence for this gate | Verified |
| Testing | ⚠️ **CONDITIONAL** (upgraded from FAIL this pass) | R1 resolved — all 5 previously-0%-covered provider methods now have behavioural-contract tests (54.02% → 91.95%, this session's measurement). R13 (coverage metric not catching cross-module bugs like R7/R8/R9) remains open and is a process gap, not a blocker in itself — no longer graded FAIL since the specific instance it was warning about (R1) is now closed | Verified |
| Documentation | ✅ **PASS** | Every file opened across two sessions carried a substantive rationale docstring; no documentation-blocking finding surfaced | Verified |
| Security | ⚪ **UNSCORED — Unknown** | No dedicated security pass has been performed at any point in this audit | Unknown, stated as such |
| Performance | ⚪ **UNSCORED — Unknown** | No dedicated performance pass has been performed at any point in this audit | Unknown, stated as such |
| Developer Experience | ⚠️ **CONDITIONAL** | Clear CLI/typed-exception design, undercut by R7 (silent, undebuggable logging failure) | Verified |
| Release Engineering | ❌ **FAIL** (re-verified this pass, downgraded from CONDITIONAL) | Real docs exist (`RELEASING.md`, `VERSIONING.md`) and the Click pin is genuinely correct, but nothing is committed (detached HEAD, ~130 modified/untracked paths), no git remote configured, CI has never executed (workflow untracked), and `CHANGELOG.md` contradicts `VERSIONING.md`/`pyproject.toml` on release status. Full detail: `R14_Release_Engineering_Verification.md` | Verified this session |
| Open Source Readiness | ❌ **FAIL** (reverted from CONDITIONAL — R14's re-verification changed this) | No longer capped by any *code-level* v0.2.0 blocker — R1/R2/R7/R8 all resolved. But re-opened by R14: an open-source release requires a committed, tagged, pushed, publicly-visible repository state, none of which currently exists | Verified (derived from R14) |

**Verdict: v0.2.0 is still NOT ready to release, and the reason has now been directly verified, not just flagged as unknown.** R1, R2, R7, and R8 — every originally-identified *code-level* blocker — are resolved. R14, re-verified this pass (not deferred — see `R14_Release_Engineering_Verification.md`), turns out to be a Blocker in its own right: this session confirmed, by direct repository inspection, that nothing is committed (HEAD detached, behind `phase2-development`'s own tip), no remote is configured, the CI workflow has never executed because it was never pushed, and `CHANGELOG.md` asserts a completed `[1.0.0]` release that `VERSIONING.md`, `pyproject.toml`, and the git tag list all contradict. This is a **Go/No-Go: No-Go** verdict for v0.2.0 on release-engineering grounds, independent of and in addition to the (now-closed) code-level blocker set. R17 was also corrected during this pass: 13 tests (not 12), two mechanisms (not one) — see Amendment 4 in Phase 2. Security and Performance gates remain unscored — out of R14's stated scope, not addressed this pass.

**Recommended next action:** R14's own report ends with five concrete, not-yet-started next steps (commit reconciliation, R17 fix, changelog correction, metadata placeholder cleanup, Security/Performance scoping decision) — none executed per this task's explicit "do not modify code" instruction. Awaiting your direction on which to prioritize.

---

## 5. Sprint 1 — Implementation Readiness Packets

Per your process: full packet before any code is touched, approval required before implementation begins. These build directly on ADR-P2-001/002/003/004 (Phase 2) rather than re-deriving evidence — cross-referenced, not duplicated in full.

### Packet 1 — R1: Provider test coverage gap — ✅ **IMPLEMENTED this pass, see §6**

- **Problem Summary:** `YouTubePlatformProvider.channel_metadata`, `.enumerate_videos`, `.fetch_video_metadata`/`._to_video_record`, `._contains_promo` have zero test coverage.
- **Evidence:** `coverage.xml` line-rate 0.5385 for `youtube.py`; missed lines 214-239, 256-289, 300-339, 357-360. (Full detail: ADR-P2-001.)
- **Root Cause:** The client-injection seam (`client_factory`) that makes these methods testable exists and is presumably used for the *other* tested methods in this same file (`resolve_channel`, parts of `fetch_top_level_comments`) — this looks like incomplete test-writing, not a missing testing capability.
- **Affected Modules:** `src/finfluencer/providers/platform/youtube.py` only.
- **Dependencies:** None — self-contained.
- **Architecture Impact:** None. Test-only change.
- **Alternative Solutions:** (1) unit tests via existing stub factory [recommended, ADR-P2-001]; (2) recorded-cassette integration tests; (3) accept the gap.
- **Recommended Solution:** (1), per ADR-P2-001.
- **Migration Risk:** None.
- **Regression Risk:** None — adding tests cannot itself introduce a regression; the risk is *false confidence* if the tests are shallow (e.g., only happy-path). Acceptance criteria below guards against this.
- **Acceptance Criteria:** Each of the five methods has at least one happy-path test AND at least one error-path test (e.g., empty API response, malformed item, boundary duration values for the shorts classifier). Coverage on `youtube.py` rises from 53.85% to a level demonstrably covering the previously-missed line ranges (verified by re-running `coverage.xml` generation, not assumed from test count).
- **Required Tests:** New test file(s) under `tests/providers/platform/`, using the existing stub `client_factory` pattern already established elsewhere in this test suite (exact existing pattern to be confirmed by reading the current `youtube.py` test file before writing new tests — not yet done).
- **Estimated Engineering Effort:** 2-3 engineer-days.
- **Implementation Order:** 1st or 2nd within Sprint 1 (no dependency on the other three; can run in parallel with R7/R8).

### Packet 2 — R2: 404 / comments-disabled conflation — **REVISED after `collect/` audit**

- **Problem Summary:** A deleted/invalid video (404) and a video with comments disabled both silently return an empty comment list.
- **Evidence:** `youtube.py:130-133` vs `:152-155` vs `:393-397`. **Confirmed dependency:** `collect/comments.py:199-247` has no `except` clause today, so this call site currently never sees an exception from `fetch_top_level_comments` — that's precisely why this bug has been invisible in production. (Full detail: ADR-P2-002, revised.)
- **Root Cause:** Both cases were mapped to the same `ResourceNotFoundError` type at the `_execute()` layer; the call site cannot recover which case it was.
- **Affected Modules:** `src/finfluencer/providers/platform/youtube.py`; `src/finfluencer/core/exceptions.py` (new `CommentsDisabledError` type, sibling of `ResourceNotFoundError` under `CollectionError`); **`src/finfluencer/collect/comments.py` (confirmed addition — new `except ResourceNotFoundError` clause required, mirroring `collect/channels.py:157-164`'s already-correct pattern)**.
- **Dependencies:** None on other Sprint 1 items. (The `collect/` audit dependency flagged last turn is now resolved — see Amendment 1.)
- **Architecture Impact:** Minor, additive — one new exception class in the existing typed-exception taxonomy, applied consistently with the pattern `channels.py` already uses; no structural change.
- **Alternative Solutions:** (1) new `CommentsDisabledError` type [recommended]; (2) `reason` field on existing exception; (3) leave as-is.
- **Recommended Solution:** (1), per ADR-P2-002 (revised).
- **Migration Risk:** Low — additive exception type.
- **Regression Risk:** Confirmed and scoped, no longer open: the behavior change (silent-empty → logged-and-skipped for real 404s) requires `collect/comments.py` to gain the new `except` clause in the same change, or the fix would convert a silent-wrong-data bug into a whole-stage-abort bug. This is now built into the plan, not a residual risk.
- **Acceptance Criteria:** A genuinely-disabled-comments video still returns `[]`; a 404/missing video raises `ResourceNotFoundError`, is caught by `collect/comments.py`'s new handler, logged, and that one video is skipped **without aborting the remaining videos in the run**.
- **Required Tests:** Unit tests for both exception branches at the `youtube.py` level; a test on `collect/comments.py` asserting one bad video ID doesn't stop collection for the rest of the batch.
- **Estimated Engineering Effort:** 0.75 engineer-day (revised up from 0.5, now that the full blast radius — including the `collect/comments.py` handler — is confirmed rather than estimated).
- **Implementation Order:** 3rd in the approved sequence (after R7, R8), per your explicit ordering.

### Packet 3 — R7: `configure()` no-op

- **Problem Summary:** Real CLI runs never activate file logging or the `verbose` flag; both entry points' explicit `configure()` call is silently inert.
- **Evidence:** `logging.py:60-61,131-132`; `collect/channels.py:42`; `collect/main.py:57` vs `:543`; same pattern in `reporting/main.py:98/101/133`. (Full detail: ADR-P2-003.)
- **Root Cause:** Global idempotency guard (`_CONFIGURED`) combined with a lazy self-configuring getter (`get_logger()`), triggered by module-level logger instantiation that Python's import system runs before either entry point's own `configure()` call.
- **Affected Modules:** `src/finfluencer/core/logging.py` (fix); `collect/main.py`, `reporting/main.py` (regression tests only, no source change expected).
- **Dependencies:** None on other Sprint 1 items.
- **Architecture Impact:** Behavioral fix to a documented-but-broken invariant; no interface change (`configure()`'s signature is unchanged).
- **Alternative Solutions:** (1) drop the idempotency guard, let `configure()` always re-apply [recommended]; (2) restructure every entry point's import order (invasive); (3) remove `get_logger()`'s lazy self-configure entirely (breaks the documented "safe for notebooks" goal).
- **Recommended Solution:** (1), per ADR-P2-003.
- **Migration Risk:** Low-Medium — any code (inside or outside this repo, if used as a library) relying on "first `configure()` call wins, rest are ignored" changes behavior. This behavior is undocumented and contradicts the module's own docstring, so the risk is judged acceptable, not zero.
- **Regression Risk:** Must verify `configure()` being called multiple times (e.g., once implicitly via an early `get_logger()`, once explicitly by the entry point) doesn't duplicate log handlers — the existing handler-removal loop (`logging.py:101-103`) is designed for this, but must be confirmed under the new "always reconfigure" behavior, not assumed.
- **Acceptance Criteria:** After the fix, a cold-import of `collect.main` followed by its CLI's `configure(log_dir=X)` call results in a `RotatingFileHandler` targeting `X` attached to the root logger — asserted directly on `logging.getLogger().handlers`, not inferred from "no exception raised."
- **Required Tests:** New regression test per ADR-P2-003 (cold-import + entrypoint-configure + handler-assertion), for both `collect.main` and `reporting.main`.
- **Estimated Engineering Effort:** 1 engineer-day.
- **Implementation Order:** High priority — cheapest Critical-severity fix in the backlog; recommended first in Sprint 1.

### Packet 4 — R8: dry-run disk mutation

- **Problem Summary:** `_build_dry_run_plan`'s documented "never touches disk" guarantee is violated by `checkpoint.should_run()`'s marker-deletion side effect.
- **Evidence:** `reporting/orchestrator.py:441-445,458`; `checkpoint.py:99-101`. (Full detail: ADR-P2-004.)
- **Root Cause:** `should_run()` is a combined query-and-mutate method, correct for its real-run callers but reused, unmodified, by a caller that explicitly promises no mutation.
- **Affected Modules:** `src/finfluencer/core/checkpoint.py` (new method); `src/finfluencer/reporting/orchestrator.py` (call-site swap).
- **Dependencies:** None on other Sprint 1 items, but shares `checkpoint.py` with no other current Sprint 1 task — safe to parallelize.
- **Architecture Impact:** Additive method (`has_valid_marker()`); `should_run()`'s existing contract for its other 8 confirmed call sites (`channels.py`, `videos.py`, `comments.py`, `transcripts.py`, `embeddings/pipeline.py`, `topics/pipeline.py`, `sentiment/pipeline.py`, `preprocess/pipeline.py`) is unchanged.
- **Alternative Solutions:** (1) new read-only `has_valid_marker()` method [recommended]; (2) `mutate: bool` flag on `should_run()`; (3) document the side effect and accept it.
- **Recommended Solution:** (1), per ADR-P2-004.
- **Migration Risk:** Low — additive; existing callers untouched.
- **Regression Risk:** Must confirm the extracted read-only comparison logic in `has_valid_marker()` and the mutation logic remaining in `should_run()` stay behaviorally identical to today's `should_run()` for its 8 existing callers — a refactor-equivalence risk, not a new-behavior risk.
- **Acceptance Criteria:** Running the dry-run path against a stage with a changed config leaves the `.done` marker file on disk untouched (byte-for-byte, not just "still exists") while still correctly reporting `"would_run"`.
- **Required Tests:** New test asserting file mtime/content stability across a dry-run call; existing `should_run()`/`require_done()` tests must continue passing unmodified (proves no behavior change for real-run callers).
- **Estimated Engineering Effort:** 0.5-1 engineer-day.
- **Implementation Order:** Can run in parallel with R1/R2/R7 — fully independent files.

---

## 6. Implementation Log

### R7 — `configure()` no-op (ADR-P2-003) — ✅ Implemented

**Files Changed**
- `src/finfluencer/core/logging.py` — removed the `if _CONFIGURED: return` early exit from `configure()`; added a docstring `Notes` section explaining why (points to ADR-P2-003). `_CONFIGURED` is still set at the end so `get_logger()`'s lazy-default behavior is unchanged.
- `tests/unit/test_core/test_logging.py` — new file, 6 tests.

**Reason**
Per ADR-P2-003's recommended solution: the idempotency guard was blocking every real, explicit `configure()` call whenever any transitively-imported module had already called `get_logger()` at module scope — which happens on effectively every CLI invocation (`collect/channels.py:42` alone guarantees it for `collect/main.py`).

**Side Effects**
Any code that was relying on the old (undocumented, bug-driven) "first configure wins, later calls are ignored" behavior would now see later calls take effect. No such reliance was found in the codebase — the two real entry points (`collect/main.py`, `reporting/main.py`) both call `configure()` expecting it to work, which is exactly what was broken.

**Regression Risks**
- Handler duplication across repeated `configure()` calls — checked directly; `configure()`'s existing handler-removal loop (`logging.py:113-115`, unchanged) already prevents this, and a dedicated test (`test_stderr_handler_not_duplicated_across_repeated_configure_calls`) confirms it.
- `get_logger()`'s lazy-default / notebook-safety contract — checked directly; a dedicated test (`test_get_logger_after_configure_does_not_reconfigure`) confirms `get_logger()` still never overrides an already-configured setup.

**Tests Added**
6 new tests in `tests/unit/test_core/test_logging.py`, covering: the exact real-world bug sequence (get_logger-before-configure), repeated explicit configure() calls, clean handler replacement (both directions: adding and removing a file handler), and the pre-existing lazy-default contract.

**Tests Updated**
None existing needed changes.

**Verification performed**
- New tests: 6/6 pass against the fixed code.
- Same 6 tests re-run against the pre-fix code (temporarily reverted via a scratch edit, then restored): **3/6 fail**, confirming the suite actually detects the bug rather than passing vacuously.
- Regression sweep: `tests/unit/test_core/`, `tests/unit/test_utils/`, `tests/unit/test_collect/` (the real production callers of `core.logging` via `collect/main.py`) — all green, 0 failures.
- **Scope limitation, stated plainly:** this verification ran in a scratch Linux virtual environment assembled for this session (the repository's own `.venv` is Windows-targeted and not usable from this sandbox). Heavy ML dependencies (`torch`, `transformers`, `bertopic`, `sentence-transformers`) were not installed, so `tests/unit/test_topics/`, `tests/unit/test_embeddings/`, `tests/unit/test_sentiment/`, and similar suites were **not** run. This is a low-risk gap for this specific change (`core/logging.py` has no relationship to those subsystems), but it is a real gap, not a clean full-suite green light, and is disclosed as such rather than implied.

**Coverage Impact**
`core/logging.py` had no dedicated test file before this change. Exact before/after line-rate not measured (coverage tooling wasn't run in this scratch environment — `pytest-cov`'s HTML/XML output was disabled with `--no-cov` to avoid writing into the real repo's `coverage.xml`/`htmlcov`, which belong to the maintainers' own CI, not this session). The qualitative impact is unambiguous: five of `configure()`/`get_logger()`'s previously entirely-untested behaviors (idempotency-guard interaction, handler replacement in both directions, lazy-default contract) now have direct assertions.

**Release Impact**
R7 moves from Blocker to Resolved in the v0.2.0 blocker set. Three remain: R8, R2, R1.

---

### R8 — dry-run disk mutation (ADR-P2-004) — ✅ Implemented

Followed the workflow you specified exactly: tests first, verified failing, smallest fix, verified passing, regression sweep, then this update.

**1. Regression tests written first**
- `tests/unit/test_core/test_checkpoint.py` — new `TestHasValidMarker` class, 6 tests at the `CheckpointManager` unit level (no-marker, matches, corrupted, and the core case: changed config leaves the marker file byte-identical rather than deleted). Plus one confirmation test that `should_run()`'s existing mutation is unchanged.
- `tests/unit/test_reporting/test_orchestrator.py` — one new integration test in `TestDryRun`, driving the real public `run_reporting_pipeline(..., dry_run=True)` API: complete a stage for real, change its input content (making the checkpoint stale), dry-run it, assert the `.done` marker still exists with byte-identical content, then run for real and confirm it still correctly re-executes.

**2. Verified failing against current implementation**
- `test_checkpoint.py`'s 5 new tests: `AttributeError: 'CheckpointManager' object has no attribute 'has_valid_marker'` (method didn't exist yet — correct failure mode for "not implemented").
- `test_orchestrator.py`'s new test: genuine assertion failure — `assert marker.exists()` failed because the marker was, in fact, deleted by the dry run. This is the bug reproduced live through the real API, not a hypothetical.

**3. Smallest change satisfying ADR-P2-004**
- `src/finfluencer/core/checkpoint.py`: added `has_valid_marker(stage_name, config_slice) -> bool` — the exact read-only comparison logic extracted from `should_run()`. Refactored `should_run()` to call `has_valid_marker()` internally, then perform the unlink-and-return-True mutation only when it's False. Traced all four cases (no marker / corrupted / valid+matching / valid+stale) by hand against the original implementation to confirm byte-for-byte identical behavior for every `should_run()` caller — no caller of `should_run()` was touched.
- `src/finfluencer/reporting/orchestrator.py`: `_build_dry_run_plan` now calls `checkpoint.has_valid_marker(...)` instead of `checkpoint.should_run(...)`, with the ternary polarity correctly flipped (`has_valid_marker` returning `True` means `"up_to_date"`, the inverse of `should_run` returning `True` meaning `"would_run"`).
- **No checkpoint format change.** **No marker file semantics change** (the `.done` file's structure, the `config_slice_sha256` field, and what "valid" means are all identical). **No hashing change** (`hash_config_dict` untouched). **No `CheckpointManager` redesign** — one new method, one internal refactor of an existing method's body with proven-identical external behavior.
- **No discrepancy with ADR-P2-004 surfaced during implementation** — the plan as written was directly implementable; nothing here required stopping to flag a contradiction.

**4. Verified new tests pass**
All 6 new `test_checkpoint.py` tests and the new `test_orchestrator.py` test pass after the change (24/24 in the combined run covering both files' relevant classes).

**5. Regression sweep — every `CheckpointManager` consumer**
Ran (in the same scratch Linux venv used for R7, same disclosed scope limitation):
- `tests/unit/test_core/test_checkpoint.py` full file — 20/20 pass, including all pre-existing `TestShouldRun` tests unchanged.
- `tests/unit/test_core/test_reproducibility.py` — pass (uses `checkpoint.all_markers()`, untouched).
- `tests/unit/test_reporting/test_orchestrator.py` full file (21 tests, not just `TestDryRun`) — pass, including `TestMasterTableStageSkipAndForce`, `TestResumeAfterInterruption`, and the full-pipeline integration test — all of which exercise `should_run()`/`mark_done()`/`invalidate()` through `_execute_stage`.
- `tests/unit/test_collect/` full suite (`channels`, `videos`, `quota`, `run_pipeline_manifest`) — pass. These are the real production callers of `should_run()` outside the reporting subsystem.
- `tests/unit/test_preprocess/` — pass (also calls `checkpoint.should_run()`).
- **Not run, disclosed:** `tests/unit/test_embeddings/`, `tests/unit/test_topics/`, `tests/unit/test_sentiment/` — these also call `should_run()`, but installing `torch`/`sentence-transformers`/`bertopic` in this scratch environment was too slow to complete within the session's tool constraints. Risk assessment: **low**. `should_run()`'s behavior was proven identical by hand-traced case analysis (above) and is exercised unchanged by every suite that *did* run; these three suites call the same unmodified method the same way collection and reporting stages do.

**Files Changed**
`src/finfluencer/core/checkpoint.py`, `src/finfluencer/reporting/orchestrator.py`, `tests/unit/test_core/test_checkpoint.py`, `tests/unit/test_reporting/test_orchestrator.py`.

**Side Effects**
None on `should_run()` callers (proven above). `_build_dry_run_plan`'s output is unchanged in every case except the one it was wrong in before (a stale-but-previously-completed stage now correctly stays completed after a preview).

**Regression Risks**
Covered by the sweep above; residual risk confined to the three untested ML-pipeline suites, judged low for the reasons stated.

**Tests Added:** 7 (6 unit-level + 1 integration-level). **Tests Updated:** 0 (all pre-existing tests pass unmodified — the strongest available evidence of behavior preservation). **Coverage Impact:** `has_valid_marker()` now has direct positive/negative/corrupted-input coverage; `should_run()`'s stale-marker path gained an explicit "still mutates, unchanged" assertion it didn't have before. **Release Impact:** R8 moves from Blocker to Resolved. Two remain: R2, R1.

---

### R2 — 404/comments-disabled conflation (ADR-P2-002) — ✅ Implemented

Followed the same workflow as R7/R8: tests first, verified failing, smallest fix, verified passing, regression sweep, then this update. Additional constraints from your approval message (exactly one new exception, `ResourceNotFoundError` semantics unchanged, `collect/videos.py` untouched, four dedicated behavioural-case tests) were all honored — traced explicitly below.

**1. Regression tests written first**
- `tests/unit/test_providers/test_youtube.py` — added `CommentsDisabledError` to imports; changed the existing `test_403_comments_disabled` to assert `pytest.raises(CommentsDisabledError)` instead of `ResourceNotFoundError`; added a note to `test_404_resource_not_found` confirming its semantics are unchanged by this fix; added a new `TestFetchTopLevelCommentsBehaviouralCases` class (with a `_StubCommentThreadsRaisingClient` helper) covering cases 1-3: comments enabled → collected, comments disabled → empty list (not an error), video deleted (404) → `ResourceNotFoundError` propagates.
- `tests/unit/test_collect/test_comments.py` — new file. `TestOneInvalidVideoInBatchDoesNotAbortTheRest` covers case 4 at the `collect_comments` loop level: a `_StubProvider` with per-video-ID controllable behavior (return a list or raise) drives three tests — a middle video 404'ing while the other two still collect (the core case-4 assertion, including a `structlog.testing.capture_logs()` check that the failure is actually logged as `video_not_found`, not silently dropped), all videos 404'ing yields zero rows without raising, and a constraint check that a *different* `CollectionError` (`QuotaExhaustedError`) still propagates and aborts the run — proving the new `except` clause is narrow, not a blanket catch.

**2. Verified failing against current implementation**
- `test_youtube.py`'s changed/new tests: `test_403_comments_disabled` failed with `Failed: DID NOT RAISE <class 'CommentsDisabledError'>` (the type didn't exist / wasn't raised yet — correct failure mode). The three new behavioural-case tests failed similarly before the fix (the "disabled" case raised `ResourceNotFoundError`, not `CommentsDisabledError`; `CommentsDisabledError` itself didn't exist as an importable name until the exceptions.py change).
- `test_comments.py`'s case-4 tests: `ResourceNotFoundError` propagated uncaught out of `collect_comments` (no `except` clause existed), aborting the test's own call — confirmed by running against the pre-fix `collect/comments.py` (no try/except around the provider call besides `finally: clear_context()`).

**3. Smallest change satisfying ADR-P2-002**
- `src/finfluencer/core/exceptions.py`: added exactly one new class, `CommentsDisabledError(CollectionError)`, placed immediately after `ResourceNotFoundError`, with a docstring explaining the distinction; added to `__all__`. `ResourceNotFoundError` itself was **not modified** — its docstring and semantics ("channel, video, or comment does not exist") are unchanged.
- `src/finfluencer/providers/platform/youtube.py`: `_execute()`'s comments-disabled 403 branch (previously falling through to a `ResourceNotFoundError` raise shared with the genuine-404 branch) now raises `CommentsDisabledError` instead (line 135). `fetch_top_level_comments`'s except block, previously two branches (`except ResourceNotFoundError: return results` plus a substring-sniffing `except CollectionError` branch), collapsed to one: `except CommentsDisabledError: return results` (lines 400-403) — a genuine `ResourceNotFoundError` is deliberately not caught here and propagates.
- `src/finfluencer/collect/comments.py`: added `except ResourceNotFoundError as e: _log.error("video_not_found", video_id=video_id, analyst_key=analyst_key, error=str(e)); continue` (lines 246-258), placed before the existing `finally: clear_context()`, mirroring `collect/channels.py:157-164`'s already-established pattern exactly (same log-and-continue shape, same field names adapted to this module's context).
- `src/finfluencer/collect/videos.py`: **not touched**, per your explicit instruction — confirmed by re-reading the file after the change; it retains its own separate missing-`except` gap, tracked exclusively under R16/ADR-P2-006/v0.2.1.
- No other provider behavior changed; no redesign of the exception hierarchy beyond the one new class.

**4. Verified new tests pass**
`test_youtube.py`'s relevant classes (17 tests, including the 3 new behavioural-case tests and the 2 modified/confirmed ones) and `test_comments.py` (3 new tests) — 20/20 pass after the change.

**5. Regression sweep**
Ran (same scratch Linux venv as R7/R8, same disclosed scope limitation regarding heavy ML dependencies):
- `tests/unit/test_providers/` — pass.
- `tests/unit/test_collect/` — pass (all of `channels`, `videos`, `quota`, `comments`, `run_pipeline_manifest`).
- `tests/unit/test_core/test_exceptions.py`, `tests/unit/test_core/` (full) — pass; the new `CommentsDisabledError` class did not disturb any existing exception-hierarchy test.
- `tests/unit/test_utils/`, `tests/unit/test_reporting/test_orchestrator.py`, `tests/unit/test_preprocess/` — pass.
- **New finding surfaced here, not silently absorbed:** extending the sweep to `tests/unit/test_cli.py` and `tests/unit/test_reporting/test_main.py` produced 12 failures, all `json.decoder.JSONDecodeError: Extra data`. Investigated directly rather than assumed unrelated: root-caused to R7's fix interacting with Typer's `CliRunner()` defaulting to `mix_stderr=True` (confirmed via `inspect.signature`), which merges a leaked `structlog` log line into the same captured stream the tests parse as JSON. Confirmed by experiment — reverting R7's fix makes all 12 pass again; restoring it reproduces the failure identically — that this is attributable to R7, not to R2 (none of the 12 failing tests exercise comments/`CommentsDisabledError` code paths) and not to R8. Filed as **R17** (Phase 2 Amendment 2, Risk Matrix, Release Readiness) rather than fixed here, since fixing it would mean touching `reporting/main.py` or `tests/unit/test_cli.py`/`test_main.py` — outside ADR-P2-002's approved scope. Per your standing instruction to stop and flag rather than silently expand scope, this is disclosed here and left for separate approval.
- **Not run, disclosed (same as R7/R8):** `tests/unit/test_embeddings/`, `tests/unit/test_topics/`, `tests/unit/test_sentiment/` — heavy ML dependencies not installed in this scratch environment. Risk assessment: low — none of these suites touch `collect/comments.py`, `youtube.py`, or `core/exceptions.py`.

**Files Changed**
`src/finfluencer/core/exceptions.py`, `src/finfluencer/providers/platform/youtube.py`, `src/finfluencer/collect/comments.py`, `tests/unit/test_providers/test_youtube.py`, `tests/unit/test_collect/test_comments.py` (new file).

**Reason**
Per ADR-P2-002 (revised): split a single conflated exception type into two, so a genuinely missing video and a video with comments merely turned off are distinguishable in the corpus's provenance trail, and so a batch collection run survives one bad video instead of aborting.

**Side Effects**
None on any other provider behavior. `collect/videos.py` is explicitly unaffected (not modified). Any caller previously relying on `fetch_top_level_comments` never raising for a 404 (there were none found — `collect/comments.py` was the only caller, and it previously had no `except` clause at all, meaning a 404 would have crashed the whole stage even before this fix, just via an unhandled propagation rather than a typed one) now sees that same 404 handled gracefully instead.

**Regression Risks**
Covered by the sweep above. The one residual, explicitly disclosed risk is R17 — a test-infrastructure issue, not a production regression, attributable to R7 rather than this change, and not fixed as part of this item per scope discipline.

**Tests Added:** 3 new in `test_youtube.py` (behavioural cases 1-3) + 3 new in `test_comments.py` (behavioural case 4 + 2 constraint checks) = 6. **Tests Updated:** 2 in `test_youtube.py` (`test_403_comments_disabled` retargeted to the new exception type; `test_404_resource_not_found` annotated to confirm unchanged semantics). **Coverage Impact:** `CommentsDisabledError`'s raise/catch paths and `collect/comments.py`'s new except branch are now directly exercised; previously-untested "one bad video in a batch" behavior at the collection-loop level now has explicit coverage. **Release Impact:** R2 moves from Blocker to Resolved. One remains: R1. New, non-blocking finding filed: R17 (v0.2.1).

---

### R1 — Provider test coverage gap (ADR-P2-001) — ✅ Implemented

The final item in the approved Sprint 1 sequence (R7 → R8 → R2 → R1). Per your explicit instruction, this was **not** treated as a coverage exercise: each test was designed against the target method's behavioural contract (what it must do, observably, from the outside) before being implemented, following the four-step process you specified.

**1. Behavioural contracts identified, before any test was written**

For each of the five previously-0%-covered methods, I read the method body directly (`youtube.py`) and its data contract (`VideoRecord` in `core/contracts.py`), then enumerated every externally observable behaviour — not implementation steps — before writing anything:

- `channel_metadata`: return a flat dict of 8 fields from the API's snippet/contentDetails/statistics response, coercing string counters to `int` and defaulting missing/absent statistics to 0; raise `ResourceNotFoundError` (with `channel_id` in context) when the API returns no items.
- `enumerate_videos`: yield video IDs published within `[window_start, window_end]` (both bounds inclusive) from a playlist assumed newest-first; stop scanning immediately (not just skip) the first time an item older than `window_start` is seen — a distinct behaviour from simply skipping an item *newer* than `window_end`, which does not stop the scan; silently skip items missing `videoId`/`videoPublishedAt` or carrying an unparseable timestamp; paginate via `nextPageToken` until exhausted.
- `fetch_video_metadata`: fetch `VideoRecord`s for arbitrarily many IDs, batching at exactly 50 per API call (YouTube's own limit), preserving input order and concatenating results across batches; zero IDs → zero API calls.
- `_to_video_record` (observed via `fetch_video_metadata`, its only caller): decide eligibility by a **fixed precedence** — shorts, then made-for-kids, then promo, first match wins — not independent flags; the shorts check (`0 < duration_sec <= shorts_max_duration_sec`) has a real edge case at `duration_sec == 0` (missing/unparseable duration), which is *not* classified as a short, because `0 < 0` is false; `likes` has no zero-fallback (`None` when absent, unlike `views`/`comment_count` which default to 0); a malformed item missing the required `id` key must fail loudly (`KeyError`), not silently produce a corrupted record.
- `_contains_promo` (observed via the same path): case-insensitive substring match against `title + " " + description`, gated entirely by `promo_keywords` — empty/default keywords never match anything, and an accidentally-configured empty-string keyword must never match either (guarded explicitly in the source).

**2. Tests designed against these contracts, then implemented**

New test classes in `tests/unit/test_providers/test_youtube.py`: `TestChannelMetadata` (4 tests), `TestEnumerateVideos` (7 tests), `TestFetchVideoMetadataBatching` (5 tests), `TestToVideoRecordEligibilityRules` (11 tests), `TestContainsPromoKeywordMatching` (5 tests) — 32 tests, plus 2 supporting helper classes' worth of stub API clients (`_StubChannelMetadataClient`, `_StubPlaylistItemsClient` with pagination/failure support, `_StubVideosClient`/`_StubVideosRaisingClient`), all following the existing file's established `client_factory`-injection pattern — no real network or `googleapiclient` calls anywhere. Every one of the five methods has at least one happy-path, one boundary-condition, and one failure-path test, per your requirement; several (`enumerate_videos`, `_to_video_record`) have multiple boundary tests because their contracts have multiple independent edge cases (window-inclusivity at both ends, skip-vs-stop distinction, precedence ordering, the `duration_sec==0` quirk).

**3. Falsifiability verified directly, not assumed**

Per your requirement that every new test be able to fail against a realistic faulty implementation, I empirically verified this for the three highest-value/least-obvious assertions by temporarily mutating the source, confirming the corresponding test failed, then reverting:
- `enumerate_videos`'s early-exit (`return` → `continue`): `test_boundary_item_older_than_start_triggers_early_exit` failed (the mutated code tried to fetch a nonexistent next page, surfacing as a wrapped `CollectionError` from the stub).
- `_to_video_record`'s elif precedence (swapped `made_for_kids` ahead of `shorts`): `test_boundary_shorts_takes_precedence_over_made_for_kids` failed directly — `assert 'made_for_kids' == 'shorts'`.
- `_contains_promo`'s empty-string guard (`kw and kw in lower` → `kw in lower`): `test_boundary_empty_string_keyword_never_matches` failed directly — `assert 'promo' == ''`.

All three mutations were reverted immediately after confirming failure; the full 51-test file was re-run clean afterward to confirm no unintended residual change.

**4. Verified all new tests pass**

51/51 tests in `tests/unit/test_providers/test_youtube.py` pass against the real (unmutated) implementation (19 pre-existing + 32 new).

**5. Coverage regenerated, before/after measured with matched methodology**

Both numbers below were measured in this session's scratch venv using the identical command against the identical source file, differing only in which version of the test file was active — this session's own edit was temporarily swapped out and back in (not a separate/older measurement mixed with a newer one), so the comparison is apples-to-apples:

- **Before** (test file as it stood after R2, before any R1 test was added): **54.02%** (191 statements, 84 missed; 70 branches, 12 partial). Missing: 71-73, 94, 106, 110, 178, 181->199, 186->199, 200, 211, **219-235, 261-294, 305-317, 320-344, 362-365**, 380, 427, 430-431, 433, 455->389.
- **After** (with all 32 new R1 tests): **91.95%** (191 statements, 11 missed; 70 branches, 10 partial). Missing: 71-73, 94, 178, 181->199, 186->199, 200, 211, 380, 427, 430-431, 433, 455->389.

**Newly covered line ranges:** 106, 110 (quota `ensure_capacity`/`spend` branches — an incidental but real gain from two tests that inject a real `QuotaTracker` to assert quota is actually debited, since the module's own docstring documents quota accounting as an explicit contract); **219-235** (`channel_metadata` body); **261-294** (`enumerate_videos` body); **305-317** (`fetch_video_metadata` body); **320-344** (`_to_video_record` body, including the eligibility precedence chain). These are exactly and only the five ADR-P2-001 target methods (plus the incidental quota-accounting bonus) — nothing outside that scope was touched.

**Remaining intentionally-uncovered lines (12 line-ranges, all confirmed out of ADR-P2-001's scope, none silently left unexplained):**
- `71-73` (`_default_client_factory`): the real `googleapiclient.discovery.build()` call. Structurally, permanently uncovered by this test suite's own design — every test injects a stub `client_factory` specifically so the real one is never exercised; this is the seam working as intended, not a gap.
- `94` (constructor's `AuthenticationError` when no API key is provided): not one of ADR-P2-001's five named methods.
- `178, 181->199, 186->199, 200, 211` (`resolve_channel`): not one of ADR-P2-001's five methods; had partial coverage already (from this file's pre-existing legacy-URL and channel-URL tests) and remains partially covered — a real, named, correctly out-of-scope residual gap, not claimed as closed.
- `380, 427, 430-431, 433, 455->389` (`fetch_top_level_comments`): not one of ADR-P2-001's five methods; R2 already added its own dedicated behavioural tests for this method's core cases (comments enabled/disabled/deleted) — these remaining branches are secondary edge cases (empty-salt validation, comment-window filtering edges, pagination) outside both R1's and R2's approved scope.

**6. Regression sweep**

Ran (same scratch Linux venv, same disclosed ML-dependency scope limitation as R7/R8/R2):
- `tests/unit/test_providers/` — 51/51 pass.
- `tests/unit/test_collect/`, `tests/unit/test_core/`, `tests/unit/test_utils/`, `tests/unit/test_reporting/test_orchestrator.py`, `tests/unit/test_preprocess/` — combined **460/460 pass**, zero regressions from R1's purely-additive change (no production code was modified; `youtube.py`'s only edits during this pass were the three temporary mutate-verify-revert cycles in step 3, confirmed reverted to original before this sweep ran).
- `tests/unit/test_cli.py`, `tests/unit/test_reporting/test_main.py` — same 12 known R17 failures as before this pass, byte-for-byte the same failing test names and error, confirming R1 introduced zero new failures and has no relationship to R17's cause (R1 never touches `reporting/`, `core/logging.py`, or the CLI layer).
- **Not run, disclosed (same as R7/R8/R2):** `tests/unit/test_embeddings/`, `tests/unit/test_topics/`, `tests/unit/test_sentiment/` — heavy ML dependencies not installed in this scratch environment. Risk: negligible for this specific change — none of these suites import or exercise `providers/platform/youtube.py`.

**Files Changed**
`tests/unit/test_providers/test_youtube.py` only. **No production code file was modified** — R1 is purely additive test coverage for existing, already-correct behaviour, exactly as ADR-P2-001 specified ("no redesign implied").

**Reason**
Per ADR-P2-001: close the last v0.2.0 blocker — five methods on the sole external-data boundary, including the eligibility classifier that decides what enters the published corpus, had zero regression protection.

**Side Effects**
None. No behaviour changed; only new tests were added.

**Regression Risks**
None from this change itself (test-only). The three temporary mutations used to verify falsifiability were confirmed reverted (diffed against the pre-mutation state) before the regression sweep ran, and the sweep itself is the confirmation that reversion was clean.

**Tests Added:** 32. **Tests Updated:** 0. **Coverage Impact:** `youtube.py` 54.02% → 91.95% (this session's measurement); all five ADR-P2-001 target methods now have happy/boundary/failure-path coverage; residual gaps are fully enumerated above and are all outside this ADR's scope. **Release Impact:** R1 moves from Blocker to Resolved. **All four of Sprint 1's approved v0.2.0 blockers (R1, R2, R7, R8) are now resolved.** Per your explicit instruction, R14 (Release Engineering) verification has **not** been started and awaits separate approval.

---

## 7. Governance Checkpoint — Status

Both prior open questions are now resolved by your direction:

1. **`collect/` audit sequencing:** Done. Result summarized in §1/§3 above and in full in Phase 2 Amendment 1. Packet 2 (R2) is revised and its dependency on `collect/comments.py` is now confirmed, not speculative.
2. **Implementation order:** Set by you as R7 → R8 → R2 → R1, one at a time, with regression tests + governance-doc updates + an approval wait after each. No batching. This supersedes this document's earlier "implementation order" notes on individual packets where they conflict — the sequence above is authoritative.

**New items requiring a future decision, not blocking Sprint 1:** R16 (`collect/videos.py`, ADR-P2-006), found during the `collect/` audit, and R17 (`CliRunner` stderr-mixing, no dedicated ADR — classified as a test-infrastructure fix, not architecture), found during R2's regression sweep. Neither is part of the four approved Sprint 1 items; neither will be implemented until it separately comes up for approval.

**Sprint 1 status: fully closed.** All four approved implementation items (R7, R8, R2, R1) are resolved, and R14 — the last item on Sprint 1's own task list — has now been re-verified (§6 above; full report `R14_Release_Engineering_Verification.md`). Closing Sprint 1 does not mean v0.2.0 is ready: R14's own re-verification is a **No-Go** finding on release-engineering grounds (nothing committed, no remote, `CHANGELOG.md` contradicts `VERSIONING.md`/`pyproject.toml`), independent of and in addition to the now-fully-resolved code-level blocker set.

**Next action:** Release Candidate Preparation is complete as a planning artifact — see `Release_Candidate_Preparation_Plan.md` for the full commit/tag/version/changelog reconciliation plan and RC checklist (currently 0/13 items pass cleanly, consistent with R14's No-Go). Nothing in that plan has been executed (no commits, no tags, no code changes). Awaiting your direction on execution, plus the still-open candidates: R17 fix, Group D (`migration/` subpackage) scope decision, Sprint 2 (R3/R4/R9/R11/R13), and R16.
