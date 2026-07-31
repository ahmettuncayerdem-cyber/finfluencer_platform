# R14 — Release Engineering Re-Verification

**Scope:** Independent verification of every release-engineering claim previously marked "Handover only" or "Not re-verified" in `Phase2_Repository_Risk_Matrix_and_ADRs.md` / `Phase3_Engineering_Governance_Sprint_Backlog.md`. This is not a code review and not an architecture review — no production code was modified during this pass (one temporary, disclosed exception: `core/logging.py` was reverted and restored twice, in the same mutate→observe→revert pattern used for R7/R8/R1, solely to attribute the R17 test failures precisely; diffed clean before and after).

**Method:** Every claim below was checked directly against the repository as it exists on disk in this session, not against any prior report's summary of it. Where a prior document's claim could not be reproduced or is contradicted by direct repository evidence, that is recorded as an Amendment, not silently corrected in place.

---

## 1. Release Verification Report

### 1.1 Version identity is internally inconsistent

`pyproject.toml` declares `version = "0.1.0"` and `src/finfluencer/__init__.py` declares `__version__ = "0.1.0"` — these two agree with each other. But `CHANGELOG.md`'s only entry reads:

> `## [1.0.0] - 2026-07-26` — "Initial public release. Entity-centric migration v2 ..., the Run Manifest System, and the Market subsystem ... are complete and verified."

This is a direct, in-repository contradiction: the changelog asserts a completed 1.0.0 public release while the package metadata says 0.1.0, and `docs/VERSIONING.md` (the project's own versioning policy, presumably from a similar timeframe) states explicitly: *"This project is currently pre-1.0 (0.x)."* Two of the project's own governance documents disagree with each other, independent of anything I bring to this. `git tag -l` shows exactly one tag, `v0.1.0-phase1` — no `v1.0.0` tag exists anywhere in the repository. No public release, in the sense the changelog describes, has occurred.

Separately, `CHANGELOG.md` has no `[Unreleased]` section, despite `docs/RELEASING.md`'s own pre-release checklist requiring one ("CHANGELOG.md has an `[Unreleased]` section with all user-facing changes recorded"). The changelog does not comply with the release process document sitting next to it in the same repository.

### 1.2 The repository is not on a releasable branch, and nothing this session (or several prior sessions) has produced is committed

`git status` shows **HEAD detached** at commit `643c770`. Two real branches exist — `master` (tip `8a2a015`, "Phase 1 baseline") and `phase2-development` (tip `e18e9b0`, several commits ahead of the current detached HEAD). `643c770` is an ancestor of `phase2-development`, not of `master` — meaning the checkout is sitting at an *older* point in `phase2-development`'s own history, and `phase2-development` has already moved past it.

`git status --porcelain` shows 11 tracked files modified and roughly 120 untracked files/paths at the repository root — including `.github/` (the CI workflow directory), `docs/` (containing `RELEASING.md` and `VERSIONING.md` themselves), `Phase2_...md`/`Phase3_...md` (this engagement's own governance output), and every R1/R2/R7/R8 code and test change made this session. **None of it is committed.** `git remote -v` returns nothing — no remote is configured, a fact `docs/RELEASING.md` itself discloses under "Open gaps."

Concretely, this means: the CI workflow at `.github/workflows/ci.yml` has **never actually executed** — GitHub Actions only runs workflows present in a pushed commit, and this file has never been committed, let alone pushed. Every "CI passing" claim in prior documents describes a workflow definition that has never once run for real.

### 1.3 The Typer/Click dependency fix is real, but only exists as an uncommitted working-tree edit

`docs/history/release/v0.2.0/Root_Cause_Analysis_v0.2.0_CLI_Test_Failures.md` (dated 2026-07-29, one day before this session) documents a genuine, well-evidenced investigation: `click` 8.2.0+ breaks `typer` 0.9.x's `make_metavar()` call, which was traced from 34 failing tests down to a single root cause and corrected by explicitly pinning `click = ">=7.1.1,<8.2.0"` in `pyproject.toml`, then regenerating `poetry.lock` (which downgraded resolved `click` from 8.4.2 to 8.1.8). I independently confirm this pin is present in both files — but `git diff -- pyproject.toml poetry.lock` shows both changes are **uncommitted**. The fix is real and correctly reasoned; it has just never been committed, exactly like everything else in §1.2.

### 1.4 A second, more recent regression exists in the same test surface the RCA investigated, and my own diagnostic corrects an undercount in this engagement's own prior report

Running `tests/unit/test_cli.py` + `tests/unit/test_reporting/test_main.py` in this session's scratch venv (Python 3.10.12; see §1.6 for why this matters) produces **13** failing tests, not the 12 this engagement's own R2/R1 Implementation Log entries stated — a miscount on my part, corrected here. All 13 show `JSONDecodeError`, superficially matching the RCA's Signature B, but the RCA's own corrected environment (`click` 8.1.8, `typer` 0.9.4 — the exact versions already active in my venv) does **not** exhibit this failure per the RCA's own verification evidence table (0 failed, 82.74% coverage). I re-verified this distinction directly rather than assuming it:

- **10 of the 13** are attributable, with direct causal proof, to this session's own R7 fix (`ADR-P2-003`): temporarily reverting `core/logging.py`'s fix (restoring the `if _CONFIGURED: return` guard) makes exactly these 10 pass again; restoring the fix reproduces the identical failure. Mechanism: `configure()` now correctly re-attaches a stderr log handler on every call (the fix's entire point); when this happens mid-test inside Typer's `CliRunner()` (default `mix_stderr=True`), the new handler binds to the same captured stream `CliRunner` uses for `result.output`, so a structlog JSON line leaks in before or after the command's own JSON output.
- **The remaining 3** (`TestAnalyzeCommand::test_all_runs_both_stages_and_produces_expected_files`, `TestAnalyzeCommand::test_second_run_skips_via_checkpoint_third_run_forces`, `TestReportCommand::test_report_all_after_analyze_produces_expected_files`) still fail even with R7's fix reverted — proving a **second, independent mechanism**. Direct reproduction (`/tmp/repro_r14b.py`, a 10-line script using bare `click.testing.CliRunner`) confirms: Python's `warnings.warn()` — triggered here by real `statsmodels` `ConvergenceWarning`/`RankWarning` output during these three tests' actual MLE/polyfit computations — also writes to `sys.stderr` by default, and `CliRunner`'s `mix_stderr=True` merges it into `result.output` exactly the same way. This mechanism is **unrelated to R7, R8, R2, or R1** — it would occur in this test suite regardless of any change made this engagement, purely as a function of `CliRunner`'s own default and these three tests' underlying numerical computations occasionally emitting a library warning.

Both mechanisms share one root enabler (`CliRunner()`'s `mix_stderr=True` default merging stdout and stderr) but have two distinct triggers. This refines, not replaces, this engagement's existing R17 finding — see the Amendment in §3.

### 1.5 `poetry check` passes, but against a deprecated metadata format

`poetry check` (Poetry 2.4.1, installed fresh in this scratch environment) exits 0 — no hard failure — but emits fifteen deprecation warnings, all of the same shape: `pyproject.toml` uses the legacy `[tool.poetry]` metadata table (name, version, description, authors, classifiers, scripts, etc.) rather than PEP 621's `[project]` table, which Poetry 2.x treats as deprecated going forward. This is not a defect the project's own tooling would have caught with an older Poetry version (the repository doesn't pin a Poetry version anywhere, only `poetry-core>=1.5.0` under `[build-system]`), so whether this matters depends entirely on which Poetry version a real release is cut with.

`poetry lock --check` could not run at all in this environment: *"The currently activated Python version 3.10.12 is not supported by the project (`>=3.11,<3.14`)."* This is not a repository defect — see §1.6.

Separately, and independent of Poetry's own check: `pyproject.toml`'s package metadata contains unresolved placeholders — `authors = ["Finfluencer Research Group <replace-with-project-email@example.org>"]`, `homepage`/`repository`/`documentation` all pointing at `https://github.com/REPLACE-ORG/finfluencer-platform`. These would need to be filled in before any real publication (PyPI or GitHub) regardless of the `[tool.poetry]`/`[project]` table question.

### 1.6 Methodological caveat applying retroactively to every test run this engagement (R7, R8, R2, R1, and this pass)

This sandbox has only Python 3.10.12 available (`/usr/bin/python3.10`; no 3.11/3.12/3.13 binary present). `pyproject.toml` declares `python = ">=3.11,<3.14"` — **every test run performed in this engagement, across all five remediation items, was executed on a Python version outside the project's own declared supported range.** This was not disclosed with this explicit framing in the R7/R8/R2/R1 Implementation Log entries (they disclosed the *missing-ML-dependency* scope limitation, but not this one), and it should have been. It does not mean any prior result is wrong — nothing in R1/R2/R7/R8's changes is Python-3.10-vs-3.11+-sensitive on inspection — but it is a real, previously-under-disclosed gap in this session's verification confidence, and is recorded here rather than left implicit. `docs/KNOWN_ISSUES.md`'s own diagnostic table shows a *different* prior investigation session had access to Python 3.12.10 (evidently on the user's actual Windows machine, not this Linux sandbox), so this is a sandbox-specific limitation for my own verification, not evidence the project lacks a properly-versioned environment elsewhere.

### 1.7 Coverage threshold is stale relative to the project's own stated plan

`[tool.coverage.report] fail_under = 75` in `pyproject.toml`, with the adjacent comment: *"Phase 1 target 75%; rises to 85% as Phase 2 concrete providers land."* Phase 2 concrete providers (`youtube.py`) have landed — R1, resolved earlier in this session, is direct evidence of that — but `fail_under` is still 75, not 85. This is a minor, low-severity finding: the project's own documented intent to raise its bar has not been executed even though its own stated trigger condition has been met.

### 1.8 CI workflow content itself, independent of the fact that it has never run

`.github/workflows/ci.yml` (6 steps: checkout, setup Python 3.11, install Poetry, `poetry install --no-interaction`, `poetry run pytest tests/ -q`) is minimal but internally consistent — it targets Python 3.11 (matching `pyproject.toml`'s floor, unlike this session's own 3.10 sandbox), and relies on `pyproject.toml`'s own `addopts`/`[tool.coverage]` configuration for coverage enforcement rather than duplicating a `--cov-fail-under` flag on the command line, which is correct and avoids drift between the two. It has no separate lint (`ruff`) or type-check (`mypy`) job, despite both being configured in `pyproject.toml` — meaning a change that passes tests but fails lint or type-checking would currently merge cleanly through this pipeline, if the pipeline were running at all (§1.2).

---

## 2. Evidence Table

| # | Claim (source) | Verdict | Evidence |
|---|---|---|---|
| 1 | "Typer/Click pinned `>=7.1.1,<8.2.0`" (original handover; RCA) | **Partially Verified** | Present in `pyproject.toml:89` and `poetry.lock` (click 8.1.8 resolved) — but uncommitted (`git diff` shows both as modified, unstaged). Real fix, not yet real in git history. |
| 2 | "0 failing tests, 82.74% coverage" (handover; `v0.2.0_Release_Package.md:678,787`; RCA §Verification Evidence) | **Contradicted (as of this session)** | RCA's own figures were accurate *at the time it was written* (before R7 existed). This session's own R7 fix (implemented after the RCA) reintroduces 10 CLI JSON-parsing failures via a different mechanism (§1.4); a further 3 fail for a reason unrelated to either the RCA's bug or R7. Current state: 13 failing in `test_cli.py`+`test_main.py` alone. |
| 3 | "Release docs authored" (handover) | **Verified** | `docs/RELEASING.md` (137 lines) and `docs/VERSIONING.md` (74 lines) both exist, are substantive, cross-reference each other and `docs/history/release/v0.2.0/`, and are self-aware of their own gaps (§1.2's "no remote" is disclosed in `RELEASING.md` itself, not something I found despite it). |
| 4 | "CI configured" (handover) | **Partially Verified** | `.github/workflows/ci.yml` exists and is internally reasonable (§1.8) — but is untracked by git, so it has never executed against any commit. "Configured" is true of the file on disk; "operative" is not. |
| 5 | Project is versioned / release-tagged as v0.2.0 or v1.0.0 | **Contradicted** | `pyproject.toml`/`__init__.py` both say `0.1.0`. Only git tag is `v0.1.0-phase1`. `CHANGELOG.md` claims a `[1.0.0]` release that `VERSIONING.md`, the tag list, and the package version all contradict. |
| 6 | "`poetry check` reports no dependency or metadata issues" (`RELEASING.md`'s own checklist item) | **Partially Verified** | Exit code 0 (no hard failure), but 15 deprecation warnings for legacy `[tool.poetry]` metadata format under Poetry 2.4.1. Whether this blocks a real release depends on the Poetry version used to cut it — unpinned in this repo. |
| 7 | "`poetry lock --check` confirms the lock file matches `pyproject.toml`" (`RELEASING.md`'s own checklist item) | **Not Present / Not Executable** | Could not run in this session's environment: Python 3.10.12 is below the project's declared `>=3.11` floor (§1.6). Not a repository defect; a verification-environment limitation, disclosed as such. |
| 8 | `tests/unit/test_version_sync.py` exists and is runnable (`RELEASING.md` step 1.1) | **Contradicted** | Only stale `.pyc` cache files exist (`tests/unit/__pycache__/test_version_sync.cpython-310...pyc` and `...cpython-312...pyc`); the source file itself is absent from the tests directory. The release checklist references a test that no longer exists. |
| 9 | Build backend / package metadata (`[build-system]`, `[tool.poetry.scripts]`) | **Verified** | `poetry-core>=1.5.0` backend declared; `finfluencer = "finfluencer.cli:app"` entry point verified against `src/finfluencer/cli.py`, which does define and compose a Typer `app` object (confirmed by direct read, matching commit `643c770`'s message). |
| 10 | Coverage threshold reflects current project phase | **Contradicted (minor)** | `fail_under = 75`, with an adjacent comment stating it should rise to 85% "as Phase 2 concrete providers land" — which has happened (R1, this session). Threshold was not updated. |
| 11 | Remote / publishable release exists or is imminent | **Contradicted** | `git remote -v` empty; `RELEASING.md` §6 self-discloses this; no path to an actual GitHub Release or PyPI publication exists today regardless of any other finding above. |

---

## 3. Contradictions With Previous Governance Documents (Amendment)

**Amendment 4 to `Phase2_Repository_Risk_Matrix_and_ADRs.md` / Amendment to R17 in `Phase3_Engineering_Governance_Sprint_Backlog.md`, recorded here and cross-referenced there, not silently edited into the original R17 text:**

1. **R17's failure count was 13, not 12.** The Implementation Log entries for R2 and R1 both stated "12 tests" / "the same 12 known R17 failures" — an undercount, caught during R14's independent re-run. Corrected here to 13.
2. **R17 is two mechanisms, not one.** 10 of the 13 are R7-attributable (confirmed via revert/restore). The other 3 (`test_all_runs_both_stages_and_produces_expected_files`, `test_second_run_skips_via_checkpoint_third_run_forces`, `test_report_all_after_analyze_produces_expected_files`) fail for an independent reason — real `statsmodels`/`numpy` warnings leaking through the same `CliRunner(mix_stderr=True)` default — and are not fixed by reverting R7. This does not change R17's severity classification or v0.2.1 routing, but it does mean "fix R17" is not a single one-line change; it requires addressing the shared `CliRunner` default (e.g., `mix_stderr=False` or asserting on `result.stdout`) which would fix both sub-mechanisms at once, rather than treating them as unrelated.
3. **This engagement's own R7/R8/R2/R1 test verification was performed on Python 3.10.12, outside the project's declared `>=3.11` range.** Not disclosed with this explicit framing at the time. No evidence found that this invalidates any specific prior result, but it is a real confidence caveat on all of them, recorded now rather than left implicit.

**Independent of this engagement's own documents — contradictions found between the repository's own pre-existing files:**

4. `CHANGELOG.md`'s `[1.0.0]` entry contradicts `docs/VERSIONING.md`'s "currently pre-1.0" statement, `pyproject.toml`'s `0.1.0`, and the absence of any `v1.0.0` git tag. All three of the latter agree with each other; the changelog is the outlier.
5. `docs/RELEASING.md`'s pre-release checklist references `tests/unit/test_version_sync.py`, which does not exist in the current tree (only stale bytecode cache remains).
6. `v0.2.0_Release_Package.md` (a prior session's fully-prepared, never-executed commit/tag plan) asserts "206/206 tests pass" and "the repository is ready for v0.2.0" — both claims were accurate for the RCA's investigation window (2026-07-29) but predate this session's R7 fix, which reopened part of the same test surface. Neither claim reflects the repository's current, directly-observed state.

None of items 4-6 are new defects I am introducing into the governance record — they are pre-existing inconsistencies between documents already in the repository, surfaced by direct comparison rather than by trusting any single one of them.

---

## 4. Updated Release Readiness

| Gate | Prior status (this engagement, pre-R14) | Updated status | Basis |
|---|---|---|---|
| R1/R2/R7/R8 (code-level blockers) | Resolved | **Unchanged — still Resolved** | R14 did not touch application code; out of scope by design. |
| R14 (Release Engineering) | Handover only / not re-verified | **Re-verified — mixed result, not a clean pass** | See Evidence Table. Real, substantive release-engineering work exists (RELEASING.md, VERSIONING.md, the click pin, CI workflow content) but none of it is committed, tagged, or connected to a remote, and the version/changelog story is internally contradictory. |
| Security | Unscored | **Still unscored** | Out of R14's stated scope; not addressed this pass. |
| Performance | Unscored | **Still unscored** | Out of R14's stated scope; not addressed this pass. |
| R17 | Test-harness artifact, 12 tests, single mechanism (R7) | **Corrected: 13 tests, two mechanisms** (§1.4, §3) | Direct re-run + revert/restore experiment this pass. |

**What "v0.2.0" would require, concretely, that does not exist today:**
- A version bump (`pyproject.toml` + `__init__.py`, currently both `0.1.0`) with a matching `CHANGELOG.md` entry replacing its current, contradicted `[1.0.0]` claim.
- Every uncommitted change on the current detached HEAD (11 modified tracked files, ~120 untracked paths, including `.github/`, `docs/`, and this entire engagement's own governance output) committed to `phase2-development` — or, given the detached-HEAD state, first reconciled with wherever `phase2-development`'s own tip (`e18e9b0`) has already gone, since the current checkout is behind it.
- A remote configured, so the eventual tag and merge can actually be pushed — `RELEASING.md` itself states this doesn't exist yet.
- R17 fixed or explicitly accepted as a known, documented test-infrastructure gap (it does not block the *application*, only the CI signal's trustworthiness).

---

## 5. Go / No-Go Recommendation for v0.2.0

**No-Go**, on the evidence gathered this pass — for reasons distinct from, and more fundamental than, the R1/R2/R7/R8 code-level blocker set this engagement has otherwise fully resolved.

The application-level engineering work is in good shape: all four originally-identified Critical/High findings are resolved with regression tests, and the two release-process documents (`RELEASING.md`, `VERSIONING.md`) that exist are genuinely well-written and self-aware of some of their own gaps. But release engineering is not just "the docs exist" — it is the actual, executable path from a working tree to a published artifact, and that path is currently broken at nearly every step an external verifier would check: nothing is committed, there is no remote, the CI that would gate a merge has never run once, the changelog contradicts the versioning policy sitting next to it, and the CLI test suite — the one thing closest to an end-to-end smoke test — is failing again for reasons unrelated to the bug it was already fixed for once.

None of this requires a large amount of engineering effort to close — a commit sequence already exists in `v0.2.0_Release_Package.md` (unverified by me this pass beyond noting its existence and its now-stale test-count claim), a remote is a five-minute `git remote add`, and R17 shares one root cause across both its sub-mechanisms. The recommendation is **No-Go as of this evidence**, not "extensive rework required" — this is closer to "execute the release process that has already been written down" than to "solve a new engineering problem."

**Recommended next steps, not started, awaiting your direction (per this task's own "do not modify code" instruction):**
1. Decide whether to commit this session's (and prior sessions') accumulated working-tree changes, and onto which branch — `phase2-development` is ahead of the current detached HEAD, so this needs a deliberate reconciliation decision, not a default assumption.
2. Fix or explicitly accept R17 (both sub-mechanisms) before treating the CLI test suite as a trustworthy release gate.
3. Resolve the `CHANGELOG.md` vs. `VERSIONING.md`/tag-list contradiction — likely by removing or correcting the `[1.0.0]` entry, since every other piece of evidence says the project is pre-1.0.
4. Fill the `pyproject.toml` metadata placeholders (`authors`, `homepage`, `repository`, `documentation`) before any real publication.
5. Decide, independent of this repository, whether Security and Performance gates need to be scored before v0.2.0, or are explicitly deferred to v1.0 — this document does not make that call.
