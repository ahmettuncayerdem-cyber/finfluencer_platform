# Product Engineering Program
## Sprint 1A — Repository State Verification Plan
### Version 1.0

---

## 1. Repository State Verification

Commands (operator-executed, read-only):

```
git branch --show-current
git rev-parse HEAD
git status -sb
git diff --stat
git ls-files --others --exclude-standard | wc -l
```

Document: active branch (expected `phase2-development`), current HEAD hash, full `git status` output, the list of modified tracked files, the count of untracked files, and an explicit cleanliness statement (clean / modified / mixed). This must be captured fresh — the ten previously-identified modified files and prior untracked-file counts are prior-session facts and are not to be assumed still accurate.

---

## 2. Environment Verification

Commands:

```
python --version
poetry --version
poetry env info
poetry show click
poetry show pytest
poetry check
```

Document: operating system (from `poetry env info`), Python version, Poetry version, which virtual environment is active and whether it matches the project's declared interpreter range (`>=3.11,<3.14` per `pyproject.toml`), dependency lock status (`poetry check` — confirms `poetry.lock` is consistent with `pyproject.toml`), resolved Click version, resolved pytest version. This determines whether the environment itself is a valid basis for test evidence before any test is run.

---

## 3. Test Verification

Command:

```
poetry run pytest -v --cov=src --cov-report=term-missing -W default --durations=20 2>&1 | tee pytest_current.txt
```

Rationale for each flag: `-v` for per-test pass/fail visibility; `--cov` with `term-missing` to capture coverage against the existing 75% gate; `-W default` to surface warnings rather than suppress or escalate them, so warning-related behavior (relevant to R17's second mechanism) is visible; `--durations=20` to flag any timing anomalies; output piped to a fresh, uniquely-named log file rather than overwriting or being confused with the four existing `pytest_output*.txt` artifacts.

Evidence to collect: total tests collected, pass count, fail count, error count, full traceback for any failure, coverage percentage, list of warnings emitted with source location, total run duration.

---

## 4. Quality Verification

Commands:

```
poetry run ruff check .
poetry run mypy src
poetry run ruff format --check .
python -c "import finfluencer" 
```

Document: Ruff findings (count and rule IDs), MyPy findings (count and error categories), formatting compliance (pass/fail), and whether the package imports cleanly with no `ImportError`/`ModuleNotFoundError`. These are independent of R17 but establish whether any other latent issue exists that could confound interpretation of the test results.

---

## 5. Evidence Collection

Artifacts to preserve, each timestamped and named to avoid collision with prior artifacts:

- `pytest_current.txt` — full verbose pytest output with coverage and warnings.
- `ruff_current.txt` — Ruff check output.
- `mypy_current.txt` — MyPy output.
- Environment snapshot: `poetry env info` and `poetry show` output saved to `environment_current.txt`.
- `git status -sb` and `git diff --stat` output saved to `git_state_current.txt`.

Every artifact must record the exact command used and the timestamp it was generated, so future reference (unlike the prior `pytest_output*.txt` files) can be correlated against the working-tree file timestamps without ambiguity.

---

## 6. Evidence Evaluation

**A. Repository Healthy**
- Test Verification: 0 failed, 0 errored tests.
- Coverage ≥75%.
- Quality Verification: no Ruff or MyPy findings that were not already present and accepted prior to this sprint.
- Environment Verification: `poetry check` passes, no dependency resolution errors.

**B. Repository Requires Engineering Work**
- Test Verification: one or more failed or errored tests, reproducible on a second run (not a one-off flake).
- Failure signatures can be attributed to a specific, identifiable cause (e.g., matches or does not match R17's previously-described mechanisms).

**C. Repository State Inconclusive**
- Environment Verification fails before tests can run (e.g., `poetry check` fails, wrong Python version active, dependency install errors).
- Test Verification produces non-deterministic results across repeated runs (different failures or different counts each time) without an identified cause.
- Required tools (pytest, Ruff, MyPy) are unavailable or misconfigured in the active environment.

---

## 7. Decision Matrix

| Condition | Outcome |
|---|---|
| All tests pass, coverage ≥75%, no unexplained quality findings | Repository classified Healthy. Sprint 1B (R17 Resolution) is cancelled. No engineering work is justified. |
| Failures reproduce on a repeated run with an identifiable, consistent signature | Repository classified Requires Engineering Work. Sprint 1B (R17 Resolution) begins, scoped to the specific reproduced failures. |
| Failures reproduce but do not match R17's previously-described mechanisms | Repository classified Requires Engineering Work. Sprint 1B begins, but its Root Cause Investigation must treat the failure as newly observed rather than assume it is R17. |
| Environment cannot be established, or results are non-deterministic across repeated runs | Repository classified Inconclusive. An Environment Verification Sprint is required before any further test-based engineering work. |

---

## 8. Deliverables

- `Sprint1A_Repository_State_Verification_Plan.md` (this document).
- `pytest_current.txt`, `ruff_current.txt`, `mypy_current.txt`, `environment_current.txt`, `git_state_current.txt` (raw evidence artifacts, produced by the operator running Section 1–4's commands).
- A short Sprint 1A Findings summary (produced after evidence is collected) stating the classification (A/B/C per Section 6) and citing the specific evidence each conclusion rests on.

No implementation artifacts (no code diffs, no test changes, no documentation edits to `KNOWN_ISSUES.md` or the governance backlog) are in scope for Sprint 1A. Those remain contingent on the classification reached here.

---

## 9. Exit Criteria

Sprint 1A is complete when the repository's active branch, HEAD, working-tree cleanliness, environment configuration, and full test/quality results have all been captured as fresh, current evidence per Sections 1–5, evaluated against the objective criteria in Section 6, and resolved to exactly one classification (A, B, or C) with the Decision Matrix outcome stated. No conclusion about R17's status may be drawn from any document, log, or report that predates this sprint's own evidence collection.

---

*Product Engineering Program / Sprint 1A — Repository State Verification Plan / Version 1.0*
