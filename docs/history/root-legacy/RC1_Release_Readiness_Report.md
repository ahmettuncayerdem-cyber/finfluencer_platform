# RC1 Release Readiness Report

**Role:** Release Validation Engineer, Finfluencer Research Platform
**Candidate:** Release Candidate 1 (RC1), targeting v1.0.0
**Method:** Direct inspection and live command execution against the repository — `git status`/`git tag`/`git ls-files`, `poetry check`/`poetry check --lock`/`poetry build` (via `python3 -m poetry`), a full `pytest --cov` run, YAML parsing of the CI workflow, and manual review of `pyproject.toml`, `core/logging.py`, `core/config.py`, and the config files. No files were modified to produce this report.

---

## Executive summary

**This RC1 has Critical issues and is NOT ready for v1.0 release.** The engineering substance (coverage, test suite, CLI wiring, reproducibility system) is genuinely strong, but the release cannot ship in its current state because a large share of that engineering work — the CI workflow, the CLI entry point, and the entire coverage-remediation test suite — is not actually committed to git. A tag cut right now would not contain the artifacts it claims to.

---

## 1. Findings by area

### Project structure — **Major issues**

- All 11 subpackages (`analysis`, `collect`, `core`, `embeddings`, `market`, `migration`, `preprocess`, `providers` + its 3 sub-namespaces, `sentiment`, `topics`, `utils`) have correct `__init__.py` files. `src/` layout is standard and correctly configured in `pyproject.toml` (`packages = [{ include = "finfluencer", from = "src" }]`).
- **Major:** 108 compiled `__pycache__`/`.pyc` files are tracked in git (`git ls-files | grep -c "__pycache__\|\.pyc$"` → 108), despite `.gitignore` (added in R1) now excluding them going forward. The pre-existing tracked copies were never removed — this was explicitly deferred during R1, not an oversight, but it's still open. Shipping platform/interpreter-specific bytecode in version control is a real hygiene defect for a v1.0 tag.
- **Major:** 17 data/checkpoint files (`data/raw/*.parquet`, `checkpoints/*.jsonl`, `checkpoints/quota_state.json`) are tracked in git — local run state and raw data checked into version control. Also deferred from R1, still open.
- **Minor:** `src/finfluencer/__init__.py`'s docstring references `ARCHITECTURE_v2.1.md` ("See ARCHITECTURE_v2.1.md for the module inventory") — this file does not exist anywhere in the repository. Broken internal doc pointer.
- **Cosmetic:** `config/analysts_backup.yaml` is tracked in git and contains unresolved `@REPLACE_WITH_VERIFIED_HANDLE` placeholders. Unclear whether this is intentional scaffolding or leftover clutter; either way it's unlabeled.

### pyproject.toml — **Major issues**

- Metadata is complete and thorough (description, keywords, classifiers, dependency grouping with clear rationale comments).
- **Major:** Uses the legacy `[tool.poetry.*]` metadata format rather than PEP 621's `[project]` table. `poetry check` (run live) confirms this with 14 distinct deprecation warnings — not errors, but on a version of Poetry that eventually drops the legacy format entirely, this will break. Not urgent for v1.0 but should be tracked.
- **Major:** No `py.typed` marker file exists anywhere under `src/finfluencer/`, yet `classifiers` declares `"Typing :: Typed"` (line 57). This is a direct, verifiable inconsistency — per PEP 561, a package claiming inline-typed status must ship a `py.typed` marker or downstream type checkers will silently treat it as untyped.
- **Major:** `homepage`, `repository`, and `documentation` URLs are all literal placeholders (`https://github.com/REPLACE-ORG/finfluencer-platform`), and `authors` contains `replace-with-project-email@example.org`. Confirmed unchanged since the prior documentation audit.
- **Minor:** `[tool.poetry.group.docs.dependencies]` declares `mkdocs`/`mkdocs-material`, but no `mkdocs.yml` and no `docs/` directory exist. The docs tooling is configured for documentation that doesn't exist yet.
- **Minor:** `pre-commit` is listed as a dev dependency but no `.pre-commit-config.yaml` exists — the tool is declared but not wired up.

### Dependency consistency — **Minor issues**

- `python3 -m poetry check --lock` (run live) passes cleanly (only the same 14 legacy-format warnings, no lock-mismatch errors) — `poetry.lock` is internally consistent with `pyproject.toml`'s declared ranges. This confirms R3's lock generation was valid.
- **Minor, informational:** the ambient sandbox Python environment used to run this audit has several packages at versions well outside the project's pinned caret ranges (e.g. `pytest` 9.1.1 vs. the pinned `^7.4`, `structlog` 26.1.0 vs. `^24.1`, `typer` 0.26.8 vs. `^0.9`). This is **not a project defect** — this sandbox is not the Poetry-managed virtualenv, just an unrelated ambient Python install used because `poetry install` cannot run here (see below). Flagging only so this isn't mistaken for a real dependency-drift finding.

### Poetry installation — **Major issue (environment-limited, unverified)**

- `poetry install --dry-run` and `poetry build` both fail identically: *"The currently activated Python version 3.10.12 is not supported by the project (>=3.11,<3.15)."* This sandbox's Python (3.10.12) is below the project's floor.
- **Consequence:** neither a full dependency install nor a wheel/sdist build has been verified end-to-end in this audit, or in any audit so far this engagement — this has been a standing, environment-imposed blocker, not a newly discovered one. It remains genuinely unverified whether `poetry install` succeeds cleanly on a real 3.11+ environment. The now-written CI workflow would be the first real verification — except it isn't committed yet (see Versioning consistency, Critical).

### CLI — **Complete**

- `finfluencer.cli.app is finfluencer.collect.main.app` → `True`, verified live in this audit. The thin re-export pattern works correctly.
- `[tool.poetry.scripts] finfluencer = "finfluencer.cli:app"` is correctly wired.
- **Critical (see Versioning consistency):** `src/finfluencer/cli.py` itself is untracked in git. The CLI "working" is only true of the working tree, not of what would actually ship in a tagged release.

### GitHub Actions — **Critical issue**

- `.github/workflows/ci.yml` is syntactically valid YAML (parsed live with `yaml.safe_load`) and its structure is sound: checkout → setup-python 3.11 → `pipx install poetry` → `poetry install --sync` → `pytest` (relying on `pyproject.toml`'s own coverage gate) → `upload-artifact` for coverage reports with `if: always()`.
- **Critical:** `.github/` is entirely untracked (`git status --short .github/` → `?? .github/`). No CI run has ever actually executed against this workflow, because it has never been pushed. Its correctness is confirmed only by static review, not by an actual green/red run. This is the same root issue flagged in the prior documentation audit — it has not been resolved since.

### Packaging — **Major issues**

- `[tool.poetry.packages]` correctly scopes the build to `finfluencer` under `src/`.
- **Major:** No `py.typed` marker (see pyproject.toml section) — this is fundamentally a packaging defect, not just a metadata one, since it affects what actually ships in the built wheel.
- **Informational:** `config/` (settings/analysts YAML) is not included as package data, which is appropriate — these are study-specific and meant to be supplied by the user, not shipped with the library. Not a defect, but also not explicitly documented as a deliberate choice anywhere.
- **Major:** No wheel or sdist has ever been built (`dist/` does not exist), and `poetry build` cannot be verified in this environment (see Poetry installation). The actual installability of the package via `pip install .` or from a built artifact remains unverified.

### MANIFEST — **N/A / Minor note**

- Poetry-based projects do not use `MANIFEST.in` (that's a setuptools convention); Poetry uses `include`/`exclude` keys in `[tool.poetry]`, none of which are declared here. No `MANIFEST.in` exists, which is correct for this build backend — not a defect.
- **Cosmetic:** a stray `manifest.txt` exists at the repo root — unrelated to packaging, it's a SHA-256 checksum log for the Windows test-fix patch (`README.txt`'s companion file). Naming collision with the packaging concept of "MANIFEST" is confusing but harmless.

### Typing — **Major issues**

- `[tool.mypy]` is configured with `strict = true` and a thorough, sensible list of `ignore_missing_imports` overrides for untyped third-party libraries (bertopic, prince, langdetect, etc.).
- **Unable to execute `mypy` in this environment** — it is not installed in this sandbox (only `mypy_extensions`, a stub package, is present); this audit could not run a live type-check pass. This should be run in CI once the workflow is actually committed.
- **Major (already noted above):** no `py.typed` marker despite the `"Typing :: Typed"` classifier — this is the single most concrete, verifiable typing defect found.
- Manual spot review of `core/reproducibility.py`, `core/config.py`, `core/budgets.py`, and `collect/quota.py` (all recently brought to 100%/98%+ test coverage) shows consistent, complete type annotations throughout — no obvious `Any`-laundering or missing return types in the modules actually reviewed this session.

### Logging — **Complete**

- `core/logging.py` is well-designed: idempotent `configure()` (safe for repeated/notebook use), JSON-by-default with an explicit human-readable opt-in, dual stderr+rotating-file emission, `contextvars`-based binding for cross-boundary context, and a documented test-only reset hatch (`_reset_for_testing`).
- Currently at 79.63% coverage (7 statements missing — the verbose/dev-console-renderer branch and part of the file-logging setup). Not a defect, but a reasonable next coverage-remediation candidate (previously ranked #6 in the ROI list from the last coverage audit).

### Reproducibility — **Complete**

- `core/reproducibility.py` is now at 100% test coverage (verified live in this session's full-suite run). The Run Manifest System (`RunStatus`, `generate_run_id`, `build_provenance`/`write_provenance`), environment snapshotting, git-state capture, and publication-stage enforcement (`enforce_clean_tree`, `enforce_publication_reproducibility`) are all implemented and tested, including exception paths.
- **Minor, pre-existing and by design:** `config/settings.yaml` still carries 3 placeholder model revisions (`REPLACE_WITH_HF_COMMIT_SHA` at lines 175, 202, 224). This is intentional at the current `replication.stage: exploratory` — the system correctly refuses to proceed at `publication` stage while these remain unpinned (tested). Not a defect; flagged here only because "reproducibility" was explicitly in scope and this is the one open item against it.

### Configuration — **Minor issues**

- `core/config.py` is at 98.37% coverage; env-var overlay, YAML loading, schema-mismatch detection, roster validation, and salt validation are all implemented and tested.
- **Minor:** no `.env.example`/`.env.template` file exists anywhere in the repo, despite the codebase referencing three environment variables a new operator would need to know about: `ANON_SALT` (`core/config.py`, `collect/comments.py`, `collect/main.py`), `EVDS_API_KEY` (`providers/market/tcmb_evds_provider.py`), and `YT_API_KEY` (`providers/platform/youtube.py`). Nothing documents these for a new contributor beyond reading source code.

### Documentation — **Unchanged since last audit; still largely Missing**

- Per the prior `V1.0_Documentation_Audit_and_Remediation_Plan.md`: README, CHANGELOG, CONTRIBUTING, LICENSE, Release Notes, Citation instructions, Data Availability Statement, Quick Start, Troubleshooting, and FAQ remain unaddressed. Re-verified live in this audit — no new files have appeared for any of these since that report was filed. Not re-litigated in full detail here; see that report for the item-by-item breakdown. Classified **Critical** here specifically because of the LICENSE gap (see Versioning consistency) — the rest remain Major/Minor as previously classified.

### Tests — **Complete**

- Full suite: **526 passed, 1 skipped, 0 failed**, run live in this audit.
- The 1 skip is environment-imposed, not a defect: `test_bertopic_runner.py:171` skips because `bertopic` isn't installed in this sandbox — expected, matches the standing "sandbox lacks bertopic/Python 3.11+" limitation documented throughout this engagement.
- 14 warnings observed, all traced to a single source: `statsmodels.tsa.stattools.grangercausalitytests` emits a `FutureWarning` ("verbose is deprecated") regardless of the value passed — `market/confirmatory_analysis.py:148` already calls it with `verbose=False`, so this is unavoidable from our side until statsmodels removes the parameter. **Cosmetic**, third-party in origin.

### Coverage — **Complete**

- **75.71%**, confirmed live, exceeding the configured `fail_under = 75` gate. `pytest` reports `Required test coverage of 75.0% reached.` with no `FAIL`.
- Margin above the gate is thin (0.71 points) and concentrated in modules that were reachable specifically because they're pure-logic/no-network (per the R5 remediation work). The five heaviest-effort, YouTube-API-facing modules (`providers/platform/youtube.py` 11.46%, `collect/comments.py` 14.48%, `collect/transcripts.py` 11.19%, `collect/videos.py` 12.75%, `collect/main.py` 44.88%) remain largely untested. This was flagged as an open risk in the R5 completion report and remains true today — not a blocker for the 75% gate itself, but worth stating plainly in the release notes rather than leaving implicit.

### Release artifacts — **Critical issue**

- No `dist/` directory, no built wheel, no sdist exists anywhere in the repository.
- `poetry build` (run live) fails with the same Python-version error as `poetry install` — cannot be verified in this environment.
- No `v1.0.0` git tag exists (`git tag -l` → only `v0.1.0-phase1`). `Version_1.0_Release_Checklist.md` §2 specifies the exact tag command to run, but it has not been run.
- Repository is currently on branch `phase2-development` (not `master`/`main`), with only 4 commits total (`8a2a015`, `e3121e4`, `356230f`, `91f151e`). No release-branch or merge-to-main decision has been made or documented.

---

## 2. Consolidated issue list by severity

**Critical (release-blocking):**
1. CI workflow (`.github/`) is not committed to git — no CI run has ever verified this repository end-to-end.
2. CLI entry point (`src/finfluencer/cli.py`) is not committed to git.
3. The entire R5/R6 coverage-remediation test suite (the work that produced the 75.71% figure this report just verified) is uncommitted or only partially committed — `git status` shows it as modified/untracked across `tests/unit/test_core/*.py`, `tests/unit/test_utils/test_io.py`, `tests/unit/test_collect/test_quota.py`, `tests/unit/test_providers/test_english.py`, and related production-code modifications.
4. No `LICENSE` file exists despite `pyproject.toml` declaring `license = "MIT"` — real legal-clarity gap.
5. No `v1.0.0` tag exists, and per items 1-3, cutting one right now would not contain the code this report validated.

**Major:**
6. No `py.typed` marker despite the `"Typing :: Typed"` classifier.
7. 108 tracked `.pyc`/`__pycache__` files and 17 tracked data/checkpoint files in git (deferred from R1, still open).
8. `pyproject.toml` placeholder URLs/author email never filled in.
9. No wheel/sdist has ever been built or verified installable.
10. Legacy `[tool.poetry.*]` metadata format (14 deprecation warnings from `poetry check`).
11. `mkdocs`/`pre-commit` declared as dependencies with no corresponding config files.
12. `mypy` could not be executed in this environment — static type-checking is unverified beyond config review.

**Minor:**
13. Broken doc reference to nonexistent `ARCHITECTURE_v2.1.md`.
14. No `.env.example` documenting `ANON_SALT`/`EVDS_API_KEY`/`YT_API_KEY`.
15. `core/logging.py` at 79.63% coverage (untested verbose/file-handler branches).
16. Documentation gaps carried forward from the prior audit (README, CHANGELOG, CONTRIBUTING, etc. — see that report).

**Cosmetic:**
17. `config/analysts_backup.yaml` tracked with unresolved placeholder handles.
18. Stray `manifest.txt` at repo root, unrelated to packaging, confusing name.
19. Third-party `statsmodels` `FutureWarning` on every test run (unfixable from our side).

---

## 3. Verdict

Five Critical issues remain, all converging on one root cause: **the work that was done this engagement (CI, CLI fix, coverage remediation) exists on disk but not in git history.** The coverage figure, the passing test suite, and the working CLI are all real — but none of it is captured in a state that could actually be tagged and shipped today.

The repository is **not** ready for v1.0 release. Recommended sequence before re-running this audit: (1) commit the CI workflow, CLI entry point, and full test suite; (2) add a real `LICENSE` file; (3) resolve the `pyproject.toml` (0.1.0) vs. `config/settings.yaml` (1.0.0) version mismatch and fill in the real repository URLs; (4) only then cut and verify the `v1.0.0` tag, ideally letting the now-committed CI workflow run once as the first true end-to-end verification this project has had.
