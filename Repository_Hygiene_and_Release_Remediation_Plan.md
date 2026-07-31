# Repository Hygiene & Release Remediation Plan

**Role:** Release Engineering Lead, Finfluencer Research Platform
**Purpose:** Close every open Gate B item from `Version_1.0_Release_Checklist.md` / `Release_Readiness_Report.md`. This is the final document before Version 1.0 — after this plan is executed and re-verified, `Version_1.0_Release_Checklist.md` §1 (git status verification) should pass cleanly for the first time.
**Type:** Plan only. No source code, configuration, or migration artifact was modified to produce this document. Every remediation below is specified precisely enough to execute without further design work, but execution is a separate, subsequent action — consistent with every document in this release track.
**Scope boundary:** Covers Gate B items only (repository hygiene, packaging, testing, documentation staleness). Does not cover Gate A (topic evolution regeneration) — that has its own dedicated, already-accepted track (`Topic_Evolution_Production_Execution_Guide.md`, `Production_Validation_Checklist.md`) and is not duplicated here.

---

## 1. Remediation items

Ordered by the sequencing dependencies in §2, not by severity — see the severity column for prioritization within a given sequencing slot.

### R1 — Untrack `.env`; add `.gitignore`

- **Gate B ref:** items 1, 8 · **Severity:** Critical / Medium
- **Root cause:** No `.gitignore` has ever existed in this repository. `.env` has been tracked since the very first commit (`8a2a015 Phase 1 baseline`).
- **Remediation:**
  1. Create `.gitignore` at repo root with, at minimum: `.env`, `data/`, `cache/`, `checkpoints/`, `outputs/`, `.venv/`, `__pycache__/`, `*.pyc`, `.coverage`, `htmlcov/`, `coverage.xml`. (Full recommended content in Appendix A.)
  2. `git rm --cached .env` (removes it from tracking, leaves the local working copy untouched — do not `rm .env` itself).
  3. Commit both changes together: `.gitignore` addition and `.env` untracking, in one commit with a message that states plainly what happened, e.g. `"Untrack .env; add .gitignore (Release Remediation R1)"`.
  4. **Separately from this repository change:** independently determine whether any value currently or previously in `.env` (`YT_API_KEY`, `ANON_SALT`, or anything else) is a live credential. If so, rotate it. This determination and any rotation is outside this plan's scope — it requires reading a file this plan deliberately does not open, and requires access to the actual API/account consoles involved.
- **Acceptance criteria:** `git ls-files .env` returns empty; `git status --porcelain` no longer lists any file inside `data/`, `cache/`, `checkpoints/`, `outputs/`, or `__pycache__/` as untracked-and-should-be-tracked.
- **Effort:** Low (git mechanics: <15 minutes). The credential-rotation follow-up (step 4) is unscoped and may take longer depending on findings — do not let it block steps 1–3.
- **Risk of the fix itself:** Near zero. `git rm --cached` does not delete the local file; anyone who needs `.env` locally for development still has it, they simply stop committing changes to it going forward.

### R2 — Fix the broken CLI entry point

- **Gate B ref:** item 4 · **Severity:** High
- **Root cause:** `pyproject.toml`'s `[tool.poetry.scripts]` declares `finfluencer = "finfluencer.cli:app"`; `src/finfluencer/cli.py` does not exist.
- **Remediation:** Create `src/finfluencer/cli.py` as a thin re-export of the already-working Typer app in `finfluencer.collect.main` — do not duplicate or reimplement any CLI logic. Exact recommended content in Appendix B. This is a one-file, ~10-line addition; nothing in `collect/main.py` needs to change.
- **Acceptance criteria:** After `poetry install` (or `pip install -e .`), the installed `finfluencer` console script runs and produces the same output as `python -m finfluencer.collect.main` for an equivalent invocation (e.g. `finfluencer --dry-run --stage topic_sentiment` behaves identically to the module-form invocation already verified in `Release_Readiness_Report.md` §3).
- **Effort:** Low (<30 minutes, including verification).
- **Risk:** Near zero — purely additive, no existing module is touched.

### R3 — Generate and commit `poetry.lock`

- **Gate B ref:** item 5 · **Severity:** High
- **Root cause:** `pyproject.toml`'s own header states the lockfile "MUST be committed"; it is absent.
- **Remediation:** Run `poetry lock` in a real environment capable of resolving every dependency in `pyproject.toml`, including `bertopic`, `torch`, `transformers`, `sentence-transformers` — **this should be done on the same production machine used for the Gate A topic-evolution regeneration**, since that machine has already been confirmed (via `Production_Validation_Checklist.md` §0) to have a working, complete dependency resolution. Doing it there, rather than in a separate environment, avoids introducing a second, potentially different dependency-resolution result before either has even been verified once. Commit the resulting `poetry.lock` file.
- **Acceptance criteria:** `poetry.lock` exists, is committed, and `poetry check` reports it consistent with `pyproject.toml`. A subsequent `poetry install --sync` on a clean checkout reproduces the same dependency versions.
- **Effort:** Low (mechanical), but **sequencing-dependent** — see §2. Should happen during or immediately after the Gate A production run, not before, and not on an unrelated machine.
- **Risk:** Low. The only way this introduces risk is if it's generated on a machine with a materially different dependency resolution than the one Gate A was actually validated against — mitigated by the sequencing note above.

### R4 — Add CI

- **Gate B ref:** item 6 · **Severity:** High
- **Root cause:** No `.github/workflows/` directory exists; nothing automatically runs the test suite or enforces the coverage gate.
- **Remediation:** Add a minimal workflow that installs dependencies (via the `poetry.lock` from R3) and runs `pytest` with the project's own already-configured `addopts` (which already includes `--cov=finfluencer --cov-fail-under=75.0` per `pyproject.toml` — confirmed in `Release_Readiness_Report.md` §3; CI does not need to reconfigure the coverage gate, only run the suite normally). Reference workflow in Appendix C.
- **Acceptance criteria:** A workflow file exists that runs on every push/PR; a deliberately-introduced failing test or coverage regression (tested once, then reverted) is shown to fail the workflow, not just the local run.
- **Effort:** Low–Medium (a few hours including one real verification cycle).
- **Risk:** Low. CI configuration is additive and does not touch application code; the main risk is CI itself being misconfigured (e.g., wrong Python version) — mitigated by pinning the same version range already declared in `pyproject.toml` (`>=3.11,<3.15`).
- **Dependency note:** Should land after R3 (a lockfile makes CI dependency installation deterministic) but does not strictly require R6/R7 (coverage-raising) to be merged first — CI can be added while the gate is still failing, as long as that failure is expected and tracked, not silently ignored. Recommend landing CI in a state where it is *allowed* to fail on the coverage gate until R6/R7 close it, rather than delaying CI until coverage is already fixed.

### R5 — Apply ADR-0001's roadmap patch; correct stale Step 3.3/3.4 status

- **Gate B ref:** item 7 · **Severity:** Medium
- **Root cause:** `Entity_Centric_Migration_Plan_v2.md` still describes Step 3.3 as "🛑 Attempted, rolled back," despite it having been completed, verified, and followed by Step 3.4.
- **Remediation:** Apply the two patches `ADR-0001_TopicEvolutionRecord_ScopeId_Deferral.md` already specifies verbatim, ready to insert — no new drafting needed:
  - **Patch A** — insert after §4's "`TopicSentimentRecord` and `TopicEvolutionRecord` generalization — same change..." paragraph, the status-note block disambiguating `TopicRecord`/`TopicSentimentRecord`/`TopicEvolutionRecord`'s actually-different timelines (full text: ADR-0001 lines 59–61).
  - **Patch B** — append to §10's existing Step 3.3 entry, directly after the "Breaking changes (pending, not yet made)..." line, the correction block stating that change was never executed (full text: ADR-0001 lines 63–65).
  - Additionally (not part of ADR-0001's patch, but the same category of staleness, found in this plan's own review): §10 should also gain a Step 3.4 entry recording its actual completion (`analysis/topic_sentiment.py` generalized to `scope_id`, verified against real production data — per `Entity_Centric_Migration_v2_Closeout_Report.md` §1), since the roadmap currently has no Step 3.4 entry at all.
- **Acceptance criteria:** `Entity_Centric_Migration_Plan_v2.md` no longer contains the string "pending, not yet made" in reference to `TopicEvolutionRecord`'s schema change; ADR-0001's own Architectural Consistency Review "Documentation consistency" rating (currently 🔴 Red) is re-assessed and updated to 🟢 Green once the patch is applied.
- **Effort:** Low (<30 minutes — the text is already written, this is insertion only).
- **Risk:** Near zero — documentation-only change to a planning document, not a contract or code file.

### R6 — Raise test coverage on collection modules (primary gate-closing work)

- **Gate B ref:** item 3 · **Severity:** High
- **Root cause:** Real, current coverage is 68.74% against a configured 75% gate. The shortfall is concentrated, not diffuse — five files account for most of it:

| File | Coverage | Missing lines |
|---|---|---|
| `collect/channels.py` | 22.39% | 51, 92–173 |
| `collect/comments.py` | 14.48% | 50–55, 81–101, 115–123, 136–268 |
| `collect/videos.py` | 12.75% | 50, 77–121, 153–278 |
| `collect/transcripts.py` | 11.19% | 67–125, 140–145, 194–296 |
| `providers/platform/youtube.py` | 11.46% | 70–437 (nearly the entire provider) |

  - **Arithmetic, so the target is concrete, not open-ended:** total statements 3,661; currently 1,017 missing (68.74%). Reaching 75% requires roughly 102 additional statements covered (≈0.75×3,661 ≈ 2,746 covered, vs. 2,644 today) — **not** near-100% coverage of these five files. A partial pass focused on pure-logic branches (argument validation, dedup/pagination logic, quota-tracker interaction, error-handling paths) rather than exhaustively mocking every YouTube API call, is sufficient to close the numeric gate.
- **Remediation approach:** For each of the five files, add unit tests that exercise logic *without* live network calls — mock `PlatformProvider`/quota-tracker responses (the pattern already exists elsewhere in the test suite for other providers; extend it, don't invent a new mocking approach). Do not attempt to test actual YouTube API connectivity in unit tests — that remains, correctly, outside `tests/unit/`'s scope.
- **Acceptance criteria:** `pytest --cov=finfluencer --cov-report=term` (the project's own configured invocation) exits 0, i.e. the `--cov-fail-under=75.0` gate passes, with all 370+ existing tests still passing (no regression).
- **Effort:** Medium–High — the single largest item in this plan. Estimate 2–4 engineering days, given five files and the need to build or extend provider-mocking fixtures.
- **Risk:** Low to the running system (test-only changes), but real risk of scope creep if the reviewer starts refactoring `collect/`'s production code to make it "more testable" while doing this — **explicitly out of scope**: write tests against the current, stable implementation; do not modify `collect/channels.py`, `videos.py`, `comments.py`, `transcripts.py`, or `providers/platform/youtube.py` themselves as part of this item.

### R7 — Verify/fix package installability

- **Gate B ref:** item 9 · **Severity:** Medium (rising to High once `replication.stage` ever advances past `exploratory`)
- **Root cause:** `finfluencer-platform` is not installed/importable as a package in a clean environment; only reachable via `PYTHONPATH=src`. `core/reproducibility.py`'s own `enforce_publication_reproducibility()` already checks for this and will raise once triggered.
- **Remediation:** In practice this is very likely resolved as a side effect of R3 + R4 — a correct `poetry install` (already run for R3, and run automatically by CI in R4) against the existing, already-correct `packages = [{ include = "finfluencer", from = "src" }]` declaration in `pyproject.toml` should register the package properly. Treat this as a **verification item**, not a presumed-separate code fix: only investigate `pyproject.toml`'s packaging declaration further if `pip show finfluencer-platform` still fails after R3/R4 land.
- **Acceptance criteria:** In the environment where R3's `poetry install` was run, `pip show finfluencer-platform` / `importlib.metadata.version("finfluencer-platform")` succeeds.
- **Effort:** Low, contingent on R3 (likely zero additional work; a five-minute check).
- **Risk:** None — verification only.

### R8 — Migrate latent `configuration`-string dependencies to `scope_id`

- **Gate B ref:** item 10 · **Severity:** Medium, not urgent
- **Root cause:** Confirmed by direct inspection this session — `export_master_table.py` lines 14 and 17 (`tp["configuration"] == "pooled"` / `"within_analyst"`), and `final_health_report.py` lines 71, 73–74 (same pattern) — both still filter by the `configuration` string rather than joining against `scope_id`.
- **Remediation:** Not urgent, and explicitly **not required to close Gate B for v1.0** — `configuration` remains present and correctly populated in `topics.parquet` (confirmed: 35,132/35,132 rows), so these scripts are not currently broken. Recommend scheduling this as the **first post-v1.0 task**, not part of this release, since it touches shadow scripts outside the core service layer and carries no active risk today. Listed here for completeness and traceability, consistent with `Release_Readiness_Report.md`'s own classification of this item as "not urgent."
- **Acceptance criteria (deferred to post-v1.0):** Both scripts join `topics.parquet` on `scope_id` rather than filtering on the literal `configuration` string, with a regression test proving identical output on the current real data before and after the change.
- **Effort:** Low–Medium, deferred.
- **Risk:** None to this release, since it is not being done as part of it.

---

## 2. Sequencing

```
R1 (.env / .gitignore)  ──────────────────────────────┐
                                                         ├──►  Gate B re-verification (§3)
R2 (CLI entry point)  ─────────────────────────────────┤        │
                                                         │        ▼
R5 (ADR-0001 patch)  ───────────────────────────────────┤   Version_1.0_Release_Checklist.md
                                                         │   §1 git status verification
[production machine, same session as Gate A] ──►  R3 (poetry.lock)
                                                    │
                                                    ▼
                                                   R4 (CI) ──► R7 (installability check, ~free)
                                                    │
R6 (coverage) ──────────────────────────────────────┘ (can proceed in parallel with R3/R4;
                                                         only needs to land before CI is
                                                         *expected* to pass, not before CI exists)

R8 (scope_id migration in shadow scripts) — explicitly deferred to post-v1.0, not on this
                                             critical path at all.
```

**Parallelizable immediately, no dependencies:** R1, R2, R5, R6 (test-writing can start against the current codebase right away — it doesn't need R3/R4 to exist first).
**Sequenced:** R3 must happen on the Gate A production machine, in the same session as (or immediately after) the topic-evolution regeneration, per R3's own note — do not generate it speculatively beforehand on a different machine.
**R4 depends on R3** (a lockfile makes CI installation deterministic) but may land in a state where the coverage gate is expected to fail until R6 completes — do not block CI's existence on coverage being fixed first.
**R7 is nearly free once R3/R4 land** — verification, not new work.
**R8 is explicitly not on the v1.0 critical path.**

---

## 3. Gate B re-verification (Definition of Done for this plan)

Re-run exactly these checks — the same ones already used in `Release_Readiness_Report.md` and `Version_1.0_Release_Checklist.md` Gate B — after R1–R7 land:

```bash
git ls-files .env                              # must be empty (R1)
cat .gitignore                                  # must exist and cover data/cache/checkpoints/outputs/.env (R1)
PYTHONPATH=src python -c "import finfluencer.cli; print('ok')"   # must succeed (R2)
ls poetry.lock                                  # must exist (R3)
ls .github/workflows/                           # must be non-empty (R4)
grep "pending, not yet made" Entity_Centric_Migration_Plan_v2.md  # must return nothing (R5)
python -m pytest -q                             # must exit 0, including the coverage gate (R6)
pip show finfluencer-platform                   # must succeed (R7)
git status --porcelain                          # must be empty on a clean checkout (overall)
```

**This plan is complete when every line above passes.** At that point, re-run `Version_1.0_Release_Checklist.md` §1 (git status verification) — it should now pass for the first time, and the release can proceed exactly as that document already specifies, without any further changes to it.

---

## Appendix A — Recommended `.gitignore` content

```gitignore
# Secrets
.env

# Data (regenerable / not source)
data/
cache/
checkpoints/
outputs/

# Python
__pycache__/
*.pyc
.venv/

# Coverage / test artifacts
.coverage
htmlcov/
coverage.xml
.pytest_cache/
```

## Appendix B — Recommended `src/finfluencer/cli.py` content

```python
"""finfluencer.cli
==================

Packaging entry point for the ``finfluencer`` console script
(``pyproject.toml``'s ``[tool.poetry.scripts]``: ``finfluencer =
"finfluencer.cli:app"``).

This module intentionally contains no logic of its own. The Typer
application lives in :mod:`finfluencer.collect.main`, which is also
directly invocable via ``python -m finfluencer.collect.main`` — both
paths must resolve to the exact same ``app`` object, not two
independently maintained CLIs.
"""

from __future__ import annotations

from finfluencer.collect.main import app

__all__ = ["app"]
```

## Appendix C — Reference CI workflow (`.github/workflows/ci.yml`)

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install Poetry
        run: pipx install poetry
      - name: Install dependencies
        run: poetry install --sync
      - name: Run test suite (coverage gate enforced via pyproject.toml addopts)
        run: poetry run pytest
```

Note: this workflow deliberately does not pass `--cov-fail-under` explicitly — that threshold is already configured once, in `pyproject.toml`'s `addopts`, and should stay defined in exactly one place. Duplicating it into the CI YAML would create the same kind of two-sources-of-truth risk this entire release track has been working to eliminate elsewhere in the platform.
