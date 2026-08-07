# Gate 2B — Execution Specification

**Mode:** Specification only. No repository-changing command has been generated or executed in producing this document. No branch was checked out, no file was edited, no commit was created. All evidence below was already gathered, read-only, during Gate 2 (`git branch -a`, `git rev-parse`, `git merge-base`, `git cat-file -e`, `git diff`, `git show`, `git ls-tree`) and is reproduced here without re-querying the repository.

**Basis:** `Gate2_Repository_Reconciliation_Plan.md` (approved).

---

## FILE 1 — `pyproject.toml`

**Current Version:** `0.1.0` package version; no Sprint-2.7A-scoped `per-file-ignores` block for `reporting`/`cli.py`/test paths; `[[tool.mypy.overrides]]` module list does not include `openpyxl.*`, `scipy.*`, `pymannkendall.*`, `scikit_posthocs.*`.

**Target Version:** Same base content plus two additive blocks from `phase2-development` (`e18e9b0`).

**Repository Evidence:** `git diff --stat HEAD phase2-development -- pyproject.toml` → `1 file changed, 32 insertions(+)`. Zero deletions confirmed.

**Reason For Adoption:** Purely additive lint/type-check scoping; no dependency, version, or lockfile impact; target paths already exist verbatim on HEAD.

**Expected File Change:** `pyproject.toml` grows by 32 lines in two locations — inside `[tool.ruff.lint.per-file-ignores]` and inside the `[[tool.mypy.overrides]]` module list. No existing line is altered or removed.

**Expected Git Diff:**
```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -310,6 +310,34 @@ ignore = [
 "tests/**/*.py"   = ["S101", "PLR2004"]
 "scripts/**/*.py" = ["T201"]

+# --- Sprint 2.7A scoped quality gate (reporting/cli.py deliverables only) ---
+"src/finfluencer/reporting/**/*.py" = [
+    "E501", "RUF001", "UP035", "UP037", "PLR2004", "RUF005", "I001",
+]
+"src/finfluencer/reporting/main.py" = [
+    "B008",
+]
+"tests/unit/test_reporting/**/*.py" = [
+    "E501", "UP037", "N806",
+]
+"tests/unit/test_cli.py" = [
+    "E501", "PLW1510", "S603",
+]
+
 [tool.ruff.format]
@@ -355,6 +383,10 @@ module = [
     "sentence_transformers.*",
     "responses.*",
     "statsmodels.*",
+    "openpyxl.*",
+    "scipy.*",
+    "pymannkendall.*",
+    "scikit_posthocs.*",
 ]
 ignore_missing_imports = true
```
(Full inline rationale comments per code omitted here for brevity; complete text recorded in `Gate2_Repository_Reconciliation_Plan.md`, Section 1.)

**Verification Method:** After adoption, a diff of the working file against `phase2-development`'s version of `pyproject.toml` must be empty. A diff of the working file against the original HEAD content must match exactly the hunk shown above.

**Rollback Method:** Restore the file's pre-adoption content from the current working tree (no commit involved at this stage) or, if needed, from the Gate 1 patch/archive/safety-branch recovery assets.

**Risk Level:** Low.

**Confidence:** High.

---

## FILE 2 — `src/finfluencer/__init__.py`

**Current Version:** Docstring references `ARCHITECTURE_v2.1.md` ("Architecture version: 2.1 (frozen)"). `__version__ = "0.1.0"`.

**Target Version:** Docstring references `Software_Product_Architecture_v1.0.md` and adds a paragraph on the `__version__` / `CITATION.cff` axis split, cross-referencing `docs/VERSIONING.md`. `__version__` value unchanged.

**Repository Evidence:** `git diff HEAD phase2-development -- src/finfluencer/__init__.py` — docstring-only hunk; the `__version__ = "0.1.0"` line falls outside the changed region in both versions.

**Reason For Adoption:** Removes a dangling reference to a file that does not exist in either ref, and adds accurate policy cross-reference consistent with the (also-adopted) `docs/VERSIONING.md`.

**Expected File Change:** Docstring text replaced/extended (net +9/-4 lines per the earlier diff stat). No change to any executable statement.

**Expected Git Diff:**
```diff
--- a/src/finfluencer/__init__.py
+++ b/src/finfluencer/__init__.py
@@ -3,12 +3,17 @@ finfluencer — A reusable computational research platform for empirical studies
 of financial YouTube communities, retail investor behaviour, and finfluencer
 discourse.

-Architecture version: 2.1 (frozen)
-See ARCHITECTURE_v2.1.md for the module inventory and freeze policy.
+See Software_Product_Architecture_v1.0.md (repository root) for the module
+inventory and dependency graph.

 The `__version__` attribute is the ONLY value below that end users should
 depend on before the public API stabilises. Additional public exports will
 be declared here as subpackages reach stability.
+
+``__version__`` always mirrors this package's SemVer software version in
+``pyproject.toml``'s ``[tool.poetry].version`` -- it is a distinct axis
+from the research/citation version in ``CITATION.cff``. See
+docs/VERSIONING.md for the full policy and rationale.
 """

 __version__ = "0.1.0"
```

**Verification Method:** Diff against `phase2-development`'s version must be empty. `finfluencer.__version__` must still evaluate to `"0.1.0"` (unchanged value, confirmed by import or direct read).

**Rollback Method:** Restore the file's pre-adoption content from the working tree, or from Gate 1 recovery assets.

**Risk Level:** Low.

**Confidence:** High.

---

## FILE 3 — `docs/VERSIONING.md`

**Current Version:** Does not exist on HEAD (`git cat-file -e HEAD:docs/VERSIONING.md` → not a valid object).

**Target Version:** 113-line new file establishing the two-axis versioning policy (software version vs. research/citation version), documenting the prior real incident that motivated it, and including a Mermaid relationship diagram.

**Repository Evidence:** `git ls-tree -r --name-only HEAD` contains no `docs/` entries at all; `git ls-tree -r --name-only phase2-development` lists `docs/VERSIONING.md` and `docs/RELEASING.md`.

**Reason For Adoption:** This file is the referenced dependency of the other four reconciliation files (directly referenced by `docs/RELEASING.md` and by the adopted `__init__.py` docstring; indirectly the policy that `tests/unit/test_version_sync.py` enforces). It must exist before those references are meaningful.

**Expected File Change:** New file created at `docs/VERSIONING.md`, 113 lines, no existing file touched.

**Expected Git Diff:** New-file addition (`git diff` reports as `new file mode 100644`, 113 insertions, 0 deletions). Representative excerpt (opening section; full text already reproduced verbatim in `Gate2_Repository_Reconciliation_Plan.md`, Section 4, and retrievable via `git show phase2-development:docs/VERSIONING.md`):
```diff
--- /dev/null
+++ b/docs/VERSIONING.md
@@ -0,0 +1,113 @@
+# Versioning Policy
+
+This project tracks **two independent version numbers**. They are not
+related, must not be inferred from one another, and are allowed to diverge
+indefinitely. Conflating them previously produced a real bug (documented
+below); this document exists to prevent that from happening again.
+
+## 1. Software version — `pyproject.toml`
+...
```

**Verification Method:** File exists at the expected path, line count = 113, diff against `phase2-development`'s version is empty.

**Rollback Method:** Remove the newly created file (no data loss risk — the file has no prior content on this ref to lose).

**Risk Level:** Low.

**Confidence:** High.

---

## FILE 4 — `docs/RELEASING.md`

**Current Version:** Does not exist on HEAD.

**Target Version:** 205-line new file: SemVer policy, version decision matrix, branch strategy, 8-step release process with Mermaid diagram, tag strategy, CHANGELOG policy (including the `[1.0.0]`-is-not-a-software-release clarification and the `[0.2.0]`-is-first-software-release statement), release-readiness checklist, "Open gaps" section.

**Repository Evidence:** Same absence/presence pattern as `docs/VERSIONING.md`, confirmed via the same `git ls-tree` comparison.

**Reason For Adoption:** Closes a gap explicitly flagged in the earlier R14 release-engineering verification (No-Go, citing absent release documentation). Its factual claims about repository state (`master` at `v0.1.0-phase1`, no remote configured) were cross-checked against evidence independently gathered in this session and were not contradicted.

**Expected File Change:** New file created at `docs/RELEASING.md`, 205 lines.

**Expected Git Diff:** New-file addition, 205 insertions. Representative excerpt (full text already reproduced verbatim in `Gate2_Repository_Reconciliation_Plan.md`, Section 3):
```diff
--- /dev/null
+++ b/docs/RELEASING.md
@@ -0,0 +1,205 @@
+# Releasing
+
+This document covers the **process and mechanics** of cutting a software
+release: branching, tagging, and the CHANGELOG. It assumes the versioning
+*policy* explained in [`docs/VERSIONING.md`](VERSIONING.md) — read that
+first if the distinction between the software version and the
+research/citation version is not already clear.
+...
```

**Verification Method:** File exists, line count = 205, diff against `phase2-development`'s version is empty, internal link to `docs/VERSIONING.md` resolves (i.e., File 3 must be adopted first or simultaneously).

**Rollback Method:** Remove the newly created file.

**Risk Level:** Low.

**Confidence:** High.

---

## FILE 5 — `.github/workflows/ci.yml`

**Current Version:** Does not exist; the entire `.github/` directory is absent from HEAD.

**Target Version:** 95-line workflow: `lint` job (ruff + mypy scoped to the same paths as File 1's `pyproject.toml` additions) and `test` job (matrix: `ubuntu-latest`/`windows-latest` × Python `3.11`/`3.12`, `poetry install --sync`, `poetry run pytest`, coverage artifact upload).

**Repository Evidence:** `git ls-tree -r --name-only HEAD | grep '^\.github'` → empty. `git ls-tree -r --name-only phase2-development | grep '^\.github'` → `.github/workflows/ci.yml`. Target lint paths (`src/finfluencer/reporting`, `src/finfluencer/cli.py`, `tests/unit/test_reporting`, `tests/unit/test_cli.py`) confirmed present on HEAD via `git ls-tree`.

**Reason For Adoption:** Closes the "no CI" gap flagged in R14; structurally compatible with HEAD's file layout (verified, not assumed).

**Expected File Change:** New file created at `.github/workflows/ci.yml`, 95 lines.

**Expected Git Diff:** New-file addition, 95 insertions. Representative excerpt (full text already reproduced verbatim in `Gate2_Repository_Reconciliation_Plan.md`, Section 5):
```diff
--- /dev/null
+++ b/.github/workflows/ci.yml
@@ -0,0 +1,95 @@
+name: CI
+
+on:
+  push:
+  pull_request:
+
+jobs:
+  lint:
+    name: Lint (ruff + mypy)
+    runs-on: ubuntu-latest
+    ...
```

**Verification Method:** File exists, line count = 95, diff against `phase2-development`'s version is empty, YAML syntax is well-formed. Actual job execution cannot be verified at this stage — no remote is configured, so this workflow will not run anywhere until that separate, unapproved gap is closed. Do not treat "workflow file present" as equivalent to "CI passing."

**Rollback Method:** Remove the newly created file.

**Risk Level:** Medium — the file itself is low-risk to add, but its `test` job would fail on first real execution if the previously documented R17 test failures (13, per R14) are still present. This is a pre-existing condition the file would merely expose, not one it creates.

**Confidence:** Medium (downgraded from the other four files specifically because this file's real-world pass/fail outcome depends on current test-suite health, not re-verified within Gate 2/2B).

---

## Execution Order

1. `docs/VERSIONING.md` — foundational; referenced by files 2 and 4.
2. `docs/RELEASING.md` — depends on file 1 above for its internal link to resolve meaningfully.
3. `src/finfluencer/__init__.py` — depends on `docs/VERSIONING.md` existing for its new cross-reference to be meaningful.
4. `pyproject.toml` — independent of the other four; scoped lint/mypy configuration only.
5. `.github/workflows/ci.yml` — last, deliberately: it is the only file with a residual, pre-existing risk (R17), so the other four should be independently verified as clean before introducing it.

## Operator Checkpoints

- After each file: operator confirms the file's post-adoption content, operator runs the file's Verification Method, operator reports the result before the next file is prepared.
- No file's adoption instructions will be issued until the prior file's checkpoint is confirmed.
- This specification does not itself authorize proceeding past File 1 — each file's actual write step is a separate approval gate under the standing ROC protocol.

## Verification Checkpoints

- Per-file: working file vs. `phase2-development`'s version of that file → diff must be empty.
- Per-file: working file vs. original HEAD content → diff must match the "Expected Git Diff" recorded above exactly (no unexpected additional changes).
- After all five: a scoped diff limited to these five paths, working tree vs. `phase2-development`, must be empty. (A diff of the *entire* tree against `phase2-development` will still show differences — other files such as `CHANGELOG.md`'s `[Unreleased]` section, `CONTRIBUTING.md`, `README.md`, `Software_Product_Architecture_v1.0.md`, `ADR-Sprint2-01...md`, and `src/finfluencer/reporting/job.py` are intentionally out of this gate's five-file scope and remain unreconciled by design.)

## Rollback Sequence

In order of increasing scope:
1. **Single file:** discard the one file's working-tree changes, restoring it to its pre-adoption (HEAD) content.
2. **Multiple files, partial adoption:** discard working-tree changes across all files touched so far in this gate, restoring each to its pre-adoption content.
3. **Full gate rollback:** restore the entire working tree to the state captured by the Gate 1 recovery assets — named branch `wip/pre-rc-snapshot` (fastest), the tracked-file patch (for the 11 originally modified files), or the full archive (for untracked files too, if any were disturbed).

No step in this sequence involves a commit, since no commit is created during this gate — rollback at every level is a working-tree-only operation.

## Success Criteria

- All five files, post-adoption, diff empty against `phase2-development`.
- No file outside the five-file scope is altered.
- The 11 pre-existing modified files and 134 pre-existing untracked files (from the original detached-HEAD state) remain exactly as they were, except for the three that are newly created (`docs/VERSIONING.md`, `docs/RELEASING.md`, `.github/workflows/ci.yml` — which become new untracked-then-added entries) and the two that are modified in place (`pyproject.toml`, `src/finfluencer/__init__.py`).
- HEAD remains detached at `643c77075492a96f6a1c2d63a3b554f187814516` throughout — no checkout, no commit.
- Safety branch `wip/pre-rc-snapshot` continues to resolve to `643c770`, unaffected.

## Failure Criteria

- Any post-adoption diff against `phase2-development` for one of the five files is non-empty.
- Any file outside the five-file scope changes unexpectedly.
- Any of the Gate 1 recovery assets (patch, archive, hashes file, safety branch) is found altered.
- Any step turns out to require a command from the ROC "never execute" list (checkout, branch, merge, commit, reset, clean, stash, etc.) without a separate, explicit approval having been obtained first.

## Expected Repository State (post-Gate-2B execution, pre-commit)

- HEAD: still `643c77075492a96f6a1c2d63a3b554f187814516`, still detached.
- Working tree: previous 11 modified + 134 untracked files, plus 3 new files (`docs/VERSIONING.md`, `docs/RELEASING.md`, `.github/workflows/ci.yml`) and 2 further-modified files (`pyproject.toml`, `src/finfluencer/__init__.py`).
- No new commits, no new branches beyond the existing `wip/pre-rc-snapshot`, no tags.
- `poetry.lock` unchanged (no dependency additions are indicated by any of the five files).

## Post-Execution Validation Checklist

- [ ] `git status -sb` shows HEAD still detached at `643c770`, same branch/ref state as before this gate.
- [ ] Diff of each of the five files against `phase2-development` is empty.
- [ ] Diff of each of the five files against the original HEAD content matches the "Expected Git Diff" recorded in this document.
- [ ] No file outside the five-file scope shows an unexpected change (`git diff --stat` reviewed in full, not just the five paths).
- [ ] `wip/pre-rc-snapshot` still resolves to `643c77075492a96f6a1c2d63a3b554f187814516`.
- [ ] Gate 1 recovery assets (patch, archive, manifest, hashes file, snapshots) untouched — sizes/hashes unchanged from the Gate 1 Report.
- [ ] `poetry.lock` unchanged.
- [ ] Test suite re-run is explicitly deferred to a later gate — not a pass/fail condition of Gate 2B itself.

---

**No command has been generated. No repository modification has occurred. Waiting for approval before proceeding to execution.**
