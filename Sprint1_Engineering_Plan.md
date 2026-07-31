# Product Engineering Program
## Sprint 1 Engineering Plan
### Version 1.0

---

## 1. Sprint Goal

Restore the repository to a fully passing test suite by resolving R17, with the resolution verified by evidence (a clean, current test run) rather than assumed from historical reports.

---

## 2. Current Situation

`phase2-development` (currently at `3604d1d5d15153cd5bcbd4c56691f3d4196fb04d`) carries ten uncommitted, modified files, none related to the recently-integrated release-infrastructure reconciliation: `poetry.lock`, `src/finfluencer/collect/comments.py`, `src/finfluencer/core/checkpoint.py`, `src/finfluencer/core/exceptions.py`, `src/finfluencer/core/logging.py`, `src/finfluencer/providers/platform/youtube.py`, `src/finfluencer/reporting/orchestrator.py`, `tests/unit/test_core/test_checkpoint.py`, `tests/unit/test_providers/test_youtube.py`, `tests/unit/test_reporting/test_orchestrator.py`.

R17 was characterized by the R14 Release Engineering Verification report as 13 failing tests across two mechanisms: 10 attributed to an R7-related interaction between `core/logging.py` and `CliRunner()`'s `mix_stderr=True` default (which merges stdout and stderr in Typer/Click CLI tests), and 3 attributed to real `statsmodels`/`numpy` warnings leaking into that merged output and breaking output assertions in `test_cli.py` and `test_reporting/test_main.py`.

Reading the current `src/finfluencer/core/logging.py` confirms R7's fix is present: the module and `configure()`'s own docstring explicitly describe the idempotency bug and its correction. `tests/unit/test_cli.py` and `tests/unit/test_reporting/test_main.py` both instantiate `runner = CliRunner()` with no explicit `mix_stderr` argument — the behavior depends on whichever click version is resolved (`poetry.lock` currently constrains click to `>=7.1.1,<9.0.0`, a wide range across which `CliRunner` defaults and semantics have changed).

The repository also contains four untracked local pytest logs (`pytest_output.txt` through `pytest_output4.txt`, dated 2026-07-29 21:47–22:56) showing a progression from 28 failures down to a full pass (0 failures, 82.74% coverage) in the final log. This looks like it could mean R17 is already resolved. It is not treated as evidence of that here: `ls -la --time-style=full-iso` on the ten working-tree files shows all nine source/test files were last modified 2026-07-30 between 12:25 and 13:55 — 14 to 16 hours *after* the newest log. The logs predate the code they would need to have tested and most likely correspond to R14's own disclosed revert/restore experiment on `core/logging.py`, not the current working tree.

**Net position: R17's current status is unverified.** It is neither confirmed broken nor confirmed fixed. This sprint treats that as the starting fact, not the 13-failure count from R14.

---

## 3. Root Cause Investigation Plan

Do not assume the causes reported by R14 still apply. Confirm or refute them against the current working tree.

**What to investigate**
- Whether the current working tree reproduces any test failures at all, and if so, exactly which ones.
- If failures reproduce, whether they match R14's two named mechanisms (mix_stderr merging; statsmodels/numpy warning leakage) or differ.
- The actual resolved click version in the environment and its current `CliRunner`/`mix_stderr` behavior.

**Where to investigate**
- `tests/unit/test_cli.py`, `tests/unit/test_reporting/test_main.py` — `CliRunner` instantiation and assertion logic on `result.output` / `result.stdout` / `result.stderr`.
- `src/finfluencer/cli.py`, `src/finfluencer/reporting/main.py` — the composed CLI apps under test.
- `src/finfluencer/core/logging.py` — R7's fix, and the shared trigger point for mechanism (a).

**Evidence to collect**
- A fresh, full `pytest -v` run against the current, unmodified working tree (must be executed by the operator; the sandbox has Python 3.10.12 with no Poetry and no usable virtualenv for a project requiring Python >=3.11).
- Resolved click version (`poetry show click` or equivalent) at the time of that run.
- Full tracebacks and captured output for any test that fails.

**How to confirm root cause**
- If failures reproduce, use the same toggle-and-observe method R14 used: rerun the affected tests with `CliRunner(mix_stderr=False)` substituted at the call sites. If failures disappear, mechanism (a) is confirmed as still active. Independently, suppress the statsmodels warning for the 3 specifically-named tests and rerun; if only those pass as a result, mechanism (b) is confirmed. A fix is not written until this toggle test isolates the actual mechanism in the current codebase — the R14 characterization is a lead, not a conclusion.

---

## 4. Technical Work Breakdown

**Task 1 — Establish ground truth**
Objective: Run the full test suite against the current, unmodified working tree.
Expected Output: A complete, current pytest log with an accurate pass/fail count.
Dependencies: None. Must be run by the operator (sandbox cannot execute pytest for this project).
Validation Method: Compare result against both R14's 13-failure claim and the historical `pytest_output4.txt` full-pass log; explicitly reconcile whichever one it does or doesn't match.

**Task 2 — Confirm or refute root cause**
Objective: If Task 1 reproduces failures, isolate the mechanism using the toggle-and-observe method in Section 3.
Expected Output: An evidence-backed root-cause statement, or a statement that no failures reproduced and the sprint moves directly to documentation (Task 5).
Dependencies: Task 1.
Validation Method: Failures must appear/disappear in lockstep with the toggle.

**Task 3 — Fix the shared root cause (if confirmed)**
Objective: Set `CliRunner(mix_stderr=False)` (or the click-version-correct equivalent) at both call sites in `test_cli.py` and `test_reporting/test_main.py`; update any assertions that relied on merged stdout/stderr to check the correct stream.
Expected Output: Updated test files; no change to production code unless the investigation shows one is required.
Dependencies: Task 2.
Validation Method: Full suite rerun — previously-failing tests pass, no new failures introduced.

**Task 4 — Address warning leakage (if still present after Task 3)**
Objective: For the 3 statsmodels/numpy-warning tests, confirm whether separating stdout/stderr alone resolves them. If not, add a scoped `filterwarnings` suppression limited to the specific warning and test module.
Expected Output: All 3 tests pass without silencing unrelated warnings elsewhere.
Dependencies: Task 3.
Validation Method: Temporarily run the affected modules with warnings elevated to errors to confirm nothing else is being masked.

**Task 5 — Document resolution**
Objective: Record the confirmed root cause and fix in `KNOWN_ISSUES.md` (create the file if it does not exist) and update R17's entry in the governance backlog to Resolved, in the same Implementation Log format used for R7/R8/R2/R1.
Expected Output: Documentation reflecting the actual, verified final state — including the case where Task 1 finds R17 already resolved, which must be documented as such rather than left silent.
Dependencies: Task 1 at minimum; Tasks 3–4 if a fix was required.
Validation Method: Documentation cross-checked against the actual diff and the actual pytest log.

---

## 5. Testing Strategy

**Unit Tests:** `tests/unit/test_cli.py` and `tests/unit/test_reporting/test_main.py`, the two files directly implicated by R17.

**Integration Tests:** full `pytest` run across the entire suite, not just the previously-named 13 tests, to catch regressions outside the two implicated files.

**Regression Tests:** every test passing before the change must still pass after — zero net-new failures.

**Smoke Tests:** manual invocation of `python -m finfluencer.cli --help` and `python -m finfluencer.reporting.main --help` outside pytest, to confirm the `mix_stderr` change doesn't alter real CLI behavior.

**Acceptance Criteria:** 0 failed / 0 errored tests; coverage ≥75% (existing `--cov-fail-under` gate, last recorded at 82.74%); no new ruff/mypy findings.

---

## 6. Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Resolved click version behaves differently than R14 assumed, so the mix_stderr toggle doesn't reproduce the old symptom | Medium | Medium | Confirm exact resolved click version before drawing conclusions (Section 3). |
| Separating stdout/stderr exposes previously-hidden, output-order-dependent assertions elsewhere in the suite | Medium | Low–Medium | Full regression sweep (Section 5) before declaring done. |
| `core/logging.py`, the fix's likely location, is one of the ten uncommitted working-tree files not yet reconciled with `phase2-development` | High (already known) | Medium | Keep this sprint scoped to R17 only; do not let it expand into full working-tree reconciliation, which is a separate, already-identified backlog item. |
| Suppressing the statsmodels/numpy warning masks a genuine, unrelated numerical issue | Low | High if it occurs | Task 4's validation step: temporarily elevate warnings to errors to confirm nothing else is silently swallowed. |

---

## 7. Definition of Done

- A fresh, full pytest run against the current working tree shows 0 failed, 0 errored tests.
- No regression relative to the pre-change passing baseline.
- Coverage remains ≥75%.
- R17's actual, verified status (fixed, or found already resolved) is recorded in `KNOWN_ISSUES.md` and the governance backlog.
- No unrelated files touched — this sprint's diff is limited to what Section 4 requires.

---

## 8. Deliverables

**Technical:** fix (if required) to `tests/unit/test_cli.py` and `tests/unit/test_reporting/test_main.py`; fresh, complete pytest log confirming final state.

**Documentation:** `KNOWN_ISSUES.md` entry for R17 (new or updated); governance backlog R17 status updated to reflect the verified outcome.

---

## 9. Success Metrics

- Failing tests: unverified current count → 0 (confirmed by a fresh run, not by historical logs).
- Coverage: maintained at or above 75% (baseline: 82.74% per the last available log, to be reconfirmed).
- Zero new lint/type findings introduced.
- Zero flaky reruns — the resolution must be deterministic.

---

*Product Engineering Program / Sprint 1 Engineering Plan / Version 1.0*
