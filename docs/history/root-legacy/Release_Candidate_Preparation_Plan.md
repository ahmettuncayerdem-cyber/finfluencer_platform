# Release Candidate Preparation Plan

**Mode:** Release Candidate Preparation. The repository is treated here as a product approaching publication, not a project under active development. **No production code, tests, or R17 were touched to produce this document** — every command run to gather evidence was read-only (`git status`, `git diff`, `git log`, `git show`, `diff`, `wc -l`). All recommendations below are execution plans for a human to run (or approve running); per this repository's own established convention (stated explicitly in the pre-existing `v0.2.0_Release_Package.md:11`, "I never execute git writes; you do"), no `git commit`, `git tag`, `git checkout`, or `git push` was executed while producing this plan.

---

## 0. The central fact this entire plan is built on

`git merge-base 643c770 phase2-development` returns `643c770` itself. **The current detached HEAD is a strict ancestor of `phase2-development`** — `phase2-development` is 7 commits, 12 files, and 2,020 lines ahead of the exact commit this working tree is checked out from:

```
e18e9b0 docs: close architecture-doc staleness, document reporting CLI, link new docs
146c0d8 docs: persist ADR-Sprint2-01 (AnalysisJob composes over the orchestrator)
60aec54 docs(release): add release engineering process
ee94d73 feat(release): add two-axis versioning policy and regression guard
fb911a4 build(config): scope Ruff/MyPy quality gate to Sprint 1/2 deliverables
ce555e9 ci: add lint and test workflow
8a9b01a feat(reporting): add AnalysisJob GUI adapter
```

Files changed in those 7 commits: `.github/workflows/ci.yml`, `docs/history/release/v0.2.0/ADR-Sprint2-01_AnalysisJob_Composes_Over_Orchestrator.md`, `CONTRIBUTING.md`, `README.md`, `Software_Product_Architecture_v1.0.md`, `docs/RELEASING.md`, `docs/VERSIONING.md`, `pyproject.toml`, `src/finfluencer/__init__.py`, `src/finfluencer/reporting/job.py`, `tests/unit/test_reporting/test_job.py`, `tests/unit/test_version_sync.py`.

**This changes the shape of the reconciliation problem materially.** R14's verification (previous document) was accurate for the checked-out commit, but three of its findings — the CI workflow being a thin 6-step file, `docs/RELEASING.md`/`docs/VERSIONING.md` being the versions I read, `tests/unit/test_version_sync.py` being entirely absent — describe a state that **already has a more mature, already-committed alternative sitting on `phase2-development`**, seven commits away, in the same repository. The correct reconciliation is not "commit what's in the working tree" in isolation; it is "reconcile the working tree's changes against `phase2-development`'s already-more-advanced tip," which is a genuine three-way merge problem for a small number of specific files, and a clean fast-forward layer for everything else.

I checked, file by file, whether `phase2-development`'s 7 commits touch any file this session (R1/R2/R7/R8) modified: **they do not.** `collect/comments.py`, `core/checkpoint.py`, `core/exceptions.py`, `core/logging.py`, `providers/platform/youtube.py`, `reporting/orchestrator.py`, and their four corresponding test files are untouched by `phase2-development` since `643c770`. This session's code-level work has **zero file-level overlap** with `phase2-development`'s own advances. Only five files require manual reconciliation (Group A below).

---

## 1. Reconciliation of Every Uncommitted Change

`git status --porcelain` reports 11 modified tracked files and 132 untracked paths. Grouped by what they are and what they need:

### Group A — Overlap conflicts: both the working tree and `phase2-development` changed these since `643c770`. Require manual, not mechanical, reconciliation.

| File | Working tree has | `phase2-development` has | Reconciliation needed |
|---|---|---|---|
| `pyproject.toml` | The Typer/Click pin (`click = ">=7.1.1,<8.2.0"`), which `phase2-development` **does not have** (confirmed: `git show phase2-development:pyproject.toml \| grep click` finds no such dependency line — its `poetry.lock` still resolves `click` to `8.4.2`, the broken version per the RCA) | 31 additional lines: `[project]`-adjacent metadata additions, dependency/version-policy scaffolding tied to the two-axis versioning feature | Merge: take `phase2-development`'s version as the base (it is 389→420 lines, additive and more complete), re-apply the one-line `click` pin on top. Not a discard-one-side situation. |
| `src/finfluencer/__init__.py` | Old docstring referencing "Architecture version: 2.1 (frozen)" / `ARCHITECTURE_v2.1.md` | New docstring pointing at `Software_Product_Architecture_v1.0.md` and documenting the two-axis versioning policy (`__version__` vs. `CITATION.cff`) | Take `phase2-development`'s version — it is a documentation-only superset that also fixes a stale cross-reference (`ARCHITECTURE_v2.1.md` vs. the now-current `Software_Product_Architecture_v1.0.md`, itself only present on `phase2-development`). |
| `docs/RELEASING.md` | 136-line draft (different title: "Releasing finfluencer-platform"), authored independently in an earlier, separate session — never committed | 205-line version (title: "Releasing"), committed at `60aec54` | **Not a superset relationship — genuinely different documents.** Both need side-by-side content review before merge; this plan does not silently prefer one, see §1a below. |
| `docs/VERSIONING.md` | 73-line draft, same situation as above | 113-line version, committed at `ee94d73`, explicitly implements a "two-axis versioning policy" (SemVer package version vs. `CITATION.cff` research version) that the working-tree draft does not mention at all | `phase2-development`'s version is functionally more complete (it's the one that actually reconciles the version-identity question this plan's §5 depends on) — recommend it as the base, working-tree draft archived, not silently deleted. See §1a. |
| `.github/workflows/ci.yml` | Untracked, 31 lines, single job (checkout → setup Python 3.11 → install Poetry → `poetry install` → `pytest -q`) | Committed at `ce555e9`, 95 lines, two jobs (scoped `ruff`+`mypy` lint gate, then a Python 3.11/3.12 × ubuntu/windows test matrix with coverage-artifact upload) | `phase2-development`'s version is strictly more capable and was evidently written with this exact repository's own quirks in mind (its comments cite `KNOWN_ISSUES.md`'s Windows-specific torch failure as the reason the OS axis isn't thinned). Recommend it as the base. |

**§1a — On the two divergent `docs/RELEASING.md` / `docs/VERSIONING.md` drafts specifically:** I read both in full (this session, for R14) and both again just now for this comparison. They are not near-duplicates with minor wording differences — they have different structures, different section counts, and the `phase2-development` version is the only one that implements the two-axis versioning policy this plan's version-reconciliation section (§5) actually needs. I am not discarding the working-tree draft's content sight-unseen: it should be diffed line-by-line by a human (or a follow-up pass, if you want me to do that diff) before being deleted, in case it contains a checklist item or process step the committed version lacks. That diff was not performed as part of this pass — flagging its absence rather than skipping it silently.

### Group B — Clean layer: modified only in the working tree, untouched by `phase2-development` since `643c770`. No conflict; safe to commit directly.

`poetry.lock` (the `click` re-lock; also has zero overlap with `phase2-development`'s own `poetry.lock` changes because `phase2-development` never re-locked), `src/finfluencer/collect/comments.py`, `src/finfluencer/core/checkpoint.py`, `src/finfluencer/core/exceptions.py`, `src/finfluencer/core/logging.py`, `src/finfluencer/providers/platform/youtube.py`, `src/finfluencer/reporting/orchestrator.py`, `tests/unit/test_core/test_checkpoint.py`, `tests/unit/test_providers/test_youtube.py`, `tests/unit/test_reporting/test_orchestrator.py` — this is R7+R8+R2+R1's actual code and test diff, already fully verified in this engagement's own Implementation Log entries.

### Group C — New, untracked files that are this engagement's own output. Belong in this release's commit sequence.

`tests/unit/test_collect/test_comments.py` (R2), `tests/unit/test_core/test_logging.py` (R7), and this engagement's four governance documents: `Phase2_Repository_Risk_Matrix_and_ADRs.md`, `Phase3_Engineering_Governance_Sprint_Backlog.md`, `R14_Release_Engineering_Verification.md`, and this document.

### Group D — Pre-existing, untracked, out-of-scope application code. Requires a separate decision, not silent inclusion.

`src/finfluencer/migration/` (`backfill_entity_model.py`, `backfill_topic_scope.py`, `__init__.py`) and its test suite `tests/unit/test_migration/` (two test files + `__init__.py`) — a real, substantial, already-exercised (stale `.pyc` caches exist for both Python 3.10 and 3.12) application subpackage implementing the entity-centric migration backfill referenced by `ADR-0001_TopicEvolutionRecord_ScopeId_Deferral.md` and `Entity_Centric_Migration_Plan_v2.md`. **This is not part of v0.2.0's scope** as defined by this engagement's own Version Roadmap (Phase 3, §2: v0.2.0 = R1/R2/R7/R8 + R15 audit + R14) — bundling an unrelated, unreviewed feature subpackage into this release's commit sequence would violate the same scope discipline this engagement has applied throughout (e.g., R16/`collect/videos.py` deliberately excluded from R2). Recommend: a separate commit sequence and its own version/milestone decision, not silently folded into v0.2.0.

### Group E — Untracked, non-code clutter at the repository root. A `.gitignore` gap, not a commit-planning question.

The remaining ~115 untracked paths are almost entirely research/manuscript artifacts, not software: 33 CSV files (gold-standard samples, adjudication logs, manuscript figure data), 13 JSON result files, 10 XLSX workbooks, 6 PNG/3 SVG graphical-abstract images, one `.zip` + `.sha256`, ~21 standalone Python scripts at the repo root (`build_*.py`, `run_R4.py`...`run_R7.py`, `export_master_table.py`, etc. — one-off manuscript-data-generation scripts, not part of the `src/finfluencer` package), and ~34 additional markdown reports from prior sessions (`RC1_Release_Readiness_Report.md`, `v0.2.0_RC_Audit.md`, `v0.2.0_Release_Package.md`, `Sprint2_Architecture_and_Release_Review.md`, etc.). `docs/RELEASING.md`'s own pre-release checklist item 1.1 — *"`git status` shows no unexpected untracked or modified tracked files"* — currently fails against this pile by a wide margin. None of this is a commit-planning decision (these files should almost certainly never be committed to a software package's release history); it is a `.gitignore` scope decision, out of this plan's remit to make unilaterally, flagged here as a precondition for that checklist item ever passing.

---

## 2. Detached HEAD Reconciliation

**Recommendation: rebase this session's Group B + Group C changes onto `phase2-development`'s tip (`e18e9b0`), do not attempt to commit them onto the current detached HEAD and merge afterward.**

Evidence for this recommendation, not just a default preference:
- `phase2-development` is a strict descendant of the current HEAD (§0) — there is no divergence to reconcile in the version-control sense, only working-tree changes that were never moved forward when the branch advanced past this commit.
- Group B (7 source + 3 test files) has zero file-level overlap with anything `phase2-development` changed — a mechanical `git stash` / checkout-branch / `git stash pop` sequence is sufficient for this group; no merge tool is needed.
- Group A (5 files) requires the manual reconciliation already specified in §1's table, but this is true *regardless* of which branch these changes eventually land on — it does not change whether rebasing or a merge commit is used.
- `master` is not a candidate base: it is not an ancestor relationship with the current HEAD at all (`git merge-base --is-ancestor 643c770 master` returns false) — `master` is still at `8a2a015`, "Phase 1 baseline," a much earlier point with none of the reporting/CLI/provider work this repository has since built. Landing this release on `master` directly would require reconstructing all of `phase2-development`'s history there first, which is a separate, much larger undertaking than this plan addresses.

**Mechanical sequence (for a human to execute; not run by me):**
1. `git branch wip/pre-rc-snapshot 643c770` — preserve the exact current state as a named ref before touching anything, since it is currently unreachable by name (detached HEAD is fragile: an accidental `git checkout` elsewhere without first branching risks this state becoming unreachable and eventually garbage-collected).
2. `git diff` the working tree's Group A files against both `643c770` (current base) and `phase2-development` (target base) using the comparisons already tabulated in §1, and hand-apply the specific deltas (the `click` pin into the new `pyproject.toml`; a human content decision on the two `RELEASING.md`/`VERSIONING.md` drafts).
3. `git checkout phase2-development` (moves HEAD to a named branch at `e18e9b0`, discarding nothing yet — working tree changes for files `phase2-development` already touched will show as conflicts or need the Group A merge from step 2 applied on top).
4. Re-apply Group B's already-clean diffs (they touch files `phase2-development` never changed, so this is a simple copy-forward, not a merge).
5. Add Group C's new files.
6. Leave Group D and Group E untouched pending the separate decisions flagged in §1.

---

## 3. Commit Plan

Ordered, atomic, dependency-respecting. Each commit is scoped to one logical change, matching this repository's own existing commit-message convention (seen throughout `git log`: `type(scope): summary`).

| # | Commit message | Files | Depends on |
|---|---|---|---|
| 1 | `fix(deps): pin click to a typer-0.9.x-compatible range` | `pyproject.toml` (click line only, merged onto `phase2-development`'s version per §1 Group A), `poetry.lock` | `phase2-development` checked out (step 2 of §2) |
| 2 | `fix(logging): make configure() re-apply on every call (ADR-P2-003)` | `src/finfluencer/core/logging.py`, `tests/unit/test_core/test_logging.py` (new) | 1 |
| 3 | `fix(checkpoint): add read-only has_valid_marker for dry-run (ADR-P2-004)` | `src/finfluencer/core/checkpoint.py`, `src/finfluencer/reporting/orchestrator.py`, `tests/unit/test_core/test_checkpoint.py`, `tests/unit/test_reporting/test_orchestrator.py` | 2 (both touch logging-adjacent test infra; sequencing avoids interleaved diffs, not a hard technical dependency) |
| 4 | `fix(providers): split comments-disabled from resource-not-found (ADR-P2-002)` | `src/finfluencer/core/exceptions.py` (new `CommentsDisabledError`), `src/finfluencer/providers/platform/youtube.py`, `src/finfluencer/collect/comments.py`, `tests/unit/test_providers/test_youtube.py`, `tests/unit/test_collect/test_comments.py` (new) | 3 |
| 5 | `test(providers): add behavioural-contract coverage for youtube.py (ADR-P2-001)` | `tests/unit/test_providers/test_youtube.py` (the R1 additions specifically — note this is the *same file* as commit 4's test changes; if the tool used cannot stage hunks within one file across two commits, commits 4 and 5 should be combined rather than force a fragile partial-file split) | 4 |
| 6 | `docs(governance): add Phase 2/3 risk matrix, ADRs, sprint backlog, and R14/RC verification reports` | `Phase2_Repository_Risk_Matrix_and_ADRs.md`, `Phase3_Engineering_Governance_Sprint_Backlog.md`, `R14_Release_Engineering_Verification.md`, `Release_Candidate_Preparation_Plan.md` | 5 |

Commits 1-5 mirror exactly the four already-completed, already-regression-tested remediation items this engagement performed (R7 → R8 → R2 → R1, in the approved order) plus the pre-existing click pin; commit 6 is this engagement's paper trail. **Not included in this sequence, by design:** Group D (`migration/` subpackage — separate decision, §1) and Group E (research-artifact clutter — `.gitignore` decision, not a commit, §1).

---

## 4. Tag Plan

**No tag should be created until the version reconciliation (§5) and changelog reconciliation (§6) are both executed as real commits, and R17 is either fixed or explicitly accepted as a documented, non-blocking gap** — per `docs/VERSIONING.md`'s own stated rule, "Never bump the version without a corresponding changelog entry," and per this session's own No-Go finding (R14) that the CLI test suite currently cannot be trusted as a release gate.

When ready, `docs/RELEASING.md`'s own Section 2 (whichever version of the file is adopted per §1a) already specifies the correct mechanics: an annotated tag, `git tag -a v0.2.0 -m "<summary>"`, created on the fast-forward merge commit into `master`, only after confirming `git merge-base --is-ancestor master HEAD` (i.e., the release branch is a strict descendant of `master`, which after §2's reconciliation it will be). This plan does not re-derive that mechanic — it is already correctly specified in the repository — it only sequences *when* it becomes safe to run:

1. Commits 1-6 (§3) land on `phase2-development`.
2. Version reconciliation (§5) lands as its own commit.
3. Changelog reconciliation (§6) lands as its own commit, in the same commit as the version bump per `VERSIONING.md`'s rule 2 ("Update both `pyproject.toml` and `__init__.py` in the same commit" — extend this to include the changelog move, since `RELEASING.md`'s own Section 2 step 3 already bundles version bump + changelog into one `chore(release): vX.Y.Z` commit).
4. `phase2-development` fast-forward-merges into `master`.
5. Tag `v0.2.0` is created on that merge commit.
6. A remote is configured (does not exist today — `git remote -v` is empty) before any push is attempted; `RELEASING.md`'s own "Open gaps" section already discloses this precondition.

**No tag exists yet.** The only tag in the repository is `v0.1.0-phase1` (a phase marker, not a release per `VERSIONING.md`'s own "Tag naming" section, which explicitly excludes phase tags from "the public release sequence").

---

## 5. Version Reconciliation Plan

**The conflict, precisely stated:** `pyproject.toml` and `src/finfluencer/__init__.py` both say `0.1.0`. `CHANGELOG.md` and `CITATION.cff` both say `1.0.0` (dated `2026-07-26`, and — critically — this is not an uncommitted draft: both files are committed, at `fbb275f` and an earlier commit respectively, long before the current detached HEAD). `docs/VERSIONING.md` (the `phase2-development` version, §1) states the project is "currently pre-1.0" and separately describes a **two-axis versioning policy**: `__version__`/`pyproject.toml` track the *software package's* SemVer version, while `CITATION.cff` tracks a *distinct, research-citation* version, explicitly called out as "a distinct axis from the research/citation version in CITATION.cff."

**This means `CITATION.cff`'s `1.0.0` is very plausibly correct as written** — it is a citation/manuscript version, not a software release claim, and `VERSIONING.md` (once merged in per §1 Group A) already documents this distinction. **`CHANGELOG.md` is the one file that does not fit either axis cleanly:** its file header says "All notable changes to this project are documented in this file" (a software-changelog framing) but its one entry describes software features (Run Manifest System, Market subsystem integration) using release language ("Initial public release... complete and verified") that reads as a software claim, while the software's own version file says `0.1.0`. This is the actual contradiction — not `CITATION.cff` vs. `pyproject.toml` (which `VERSIONING.md`'s two-axis policy already reconciles), but `CHANGELOG.md` vs. everything else, including the two-axis policy sitting in the same repository.

**Recommended reconciliation (a plan, not executed here):**
1. Adopt `phase2-development`'s `VERSIONING.md` (already committed, already implements the two-axis distinction) as authoritative — no new policy needs inventing, it already exists seven commits away from the current checkout.
2. Treat `pyproject.toml`'s `0.1.0` / `__init__.py`'s `0.1.0` as the correct current *software* version — consistent with the tag list (only `v0.1.0-phase1` exists), with `VERSIONING.md`'s "pre-1.0" statement, and with this entire engagement's own v0.2.0-labeled governance work.
3. Bump to `0.2.0` only as part of the actual release commit (§4 step 3), once R1/R2/R7/R8 (already resolved) and the R14 process blockers (§3 of `R14_Release_Engineering_Verification.md`) are closed — not before, per `VERSIONING.md`'s rule against bumping without a corresponding changelog entry.
4. Leave `CITATION.cff`'s `1.0.0` / `2026-07-26` alone if it is confirmed (by whoever owns the citation, not by me — I have no evidence either way beyond the text itself) to refer to the research/manuscript milestone rather than the software package. If it is *not* intentional — if it was meant to track the software version and is simply stale — it needs its own correction, and `VERSIONING.md`'s two-axis framing would need to be revisited as describing an aspiration rather than a fact. **This plan does not resolve which of these two is true; it identifies the fork and the evidence on each side, per the "no assumptions" instruction.**
5. Re-run `tests/unit/test_version_sync.py` (exists on `phase2-development`, absent from the current working tree — see R14 §Evidence Table item 8) once the reconciliation lands, as the mechanical check `VERSIONING.md`'s own policy already prescribes.

---

## 6. Changelog Reconciliation Plan

1. **Do not delete `CHANGELOG.md`'s existing `[1.0.0]` entry unilaterally.** Per §5, whether it is simply wrong or is a legitimate citation-axis entry that's merely mislabeled is not resolved by evidence gathered this pass. Recommended action, pending a human decision: either (a) relabel it explicitly, e.g. `## [Research Milestone 1.0.0] - 2026-07-26`, with a one-line note distinguishing it from the software package version and cross-referencing `CITATION.cff` and `docs/VERSIONING.md`'s two-axis policy, or (b) if it is confirmed stale/erroneous, replace it with a corrective note explaining the correction (per `docs/RELEASING.md`'s own rollback-documentation convention, Section 4) rather than silently deleting history.
2. **Add an `[Unreleased]` section**, currently entirely absent, listing every user-facing change this engagement has made and verified: the `CommentsDisabledError` split (ADR-P2-002), the `configure()` re-apply fix (ADR-P2-003), the dry-run read-only marker check (ADR-P2-004), and the click dependency pin — grouped under `Fixed`, per Keep a Changelog format (which `RELEASING.md` already specifies as the target format). R1 (test coverage) is not a user-facing change and would not normally get its own changelog line under Keep a Changelog conventions, though `RELEASING.md`'s own checklist wording ("all user-facing changes recorded") leaves this as a judgment call.
3. **At release time** (§4 step 3), move `[Unreleased]`'s contents into a new `## [0.2.0] - <date>` section, in the same commit as the `pyproject.toml`/`__init__.py` version bump, per `VERSIONING.md`'s rule 2 and `RELEASING.md`'s Section 2 step 3.
4. This reconciliation is **not yet executed** — no changelog edits were made producing this document, consistent with the "do not modify production code" instruction (a changelog is documentation, but the instruction's spirit — no unapproved production-artifact edits — is treated as covering it too, pending your go-ahead).

---

## 7. Release Candidate Checklist

Adapted from `docs/RELEASING.md`'s own pre-release checklist (the `phase2-development` version, §1), annotated against this session's direct verification rather than restated blindly:

- [ ] `git status` shows no unexpected untracked or modified tracked files. **Currently fails** — 11 modified + 132 untracked (§1). Requires §2's reconciliation plus a Group E `.gitignore` decision.
- [ ] Full test suite passes: `poetry run pytest tests/ -q`. **Currently fails** — 13 known failures in `test_cli.py`/`test_main.py` (R17, two mechanisms, not yet fixed per this task's explicit "do not implement R17" instruction) plus untested ML-dependent suites this session's scratch environment could never run (`test_embeddings/`, `test_topics/`, `test_sentiment/`).
- [ ] Coverage meets the configured threshold (75%, `pyproject.toml`). **Not independently re-measured project-wide this pass** — R1's own measurement (§ of Phase 3 Implementation Log) was scoped to `youtube.py` only, not the full suite.
- [ ] `poetry check` reports no dependency or metadata issues. **Partially verified** — exits 0, but with 15 deprecation warnings for the legacy `[tool.poetry]` metadata format under Poetry 2.4.1 (R14 §1.5). Not a hard failure; worth a decision on whether to migrate to `[project]` before release.
- [ ] `poetry lock --check` confirms the lock file matches `pyproject.toml`. **Not executable in this session's environment** — Python 3.10.12 is below the project's declared `>=3.11` floor (R14 §1.6). Must be run in a properly-versioned environment before this box can be checked honestly.
- [ ] `CHANGELOG.md` has an `[Unreleased]` section with all user-facing changes recorded. **Currently fails** — no such section exists (§6).
- [ ] Documentation cross-references are internally consistent. **Currently fails** — `CHANGELOG.md` vs. `VERSIONING.md`/`CITATION.cff`/tag list (§5); two divergent `RELEASING.md`/`VERSIONING.md` drafts not yet reconciled (§1a).
- [ ] Any dependency pins added since the last release are documented with an inline comment explaining why. **Verified** — the `click` pin already carries exactly this (`pyproject.toml:89`, cites the `make_metavar()` incompatibility directly).
- [ ] Working tree is on the intended release branch, not a detached HEAD. **Currently fails** (§0, §2).
- [ ] A remote is configured. **Currently fails** — `git remote -v` is empty; disclosed in `RELEASING.md` itself.
- [ ] Version bump applied consistently (`pyproject.toml`, `__init__.py`, `CITATION.cff` if applicable) with a matching tag. **Not yet applicable** — no bump has been made; §5 is a plan, not an execution.
- [ ] Out-of-scope, uncommitted feature work (Group D: `migration/` subpackage) explicitly deferred or excluded, not silently bundled. **Decision not yet made** — flagged in §1, awaiting direction.
- [ ] R17 (13 CLI-JSON-test failures, two mechanisms) fixed, or explicitly accepted as a documented, non-blocking known issue with a dated entry in `KNOWN_ISSUES.md`. **Neither has happened yet** — explicitly out of scope for this task per your instruction not to implement R17 this pass.

**Zero of these currently pass cleanly.** This is consistent with, not a contradiction of, R14's No-Go finding — this checklist is the executable form of that same verdict, itemized so each gap can be closed and re-checked independently rather than re-litigated as a whole.
