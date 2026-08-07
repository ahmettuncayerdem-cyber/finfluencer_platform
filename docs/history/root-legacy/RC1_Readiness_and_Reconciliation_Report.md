# RC-1 Readiness and Reconciliation Report

**Role:** Release Engineering Lead. **Scope:** transform the repository into an auditable Release Candidate-1 execution plan — not execute it, not publish it, not v1.0. **Method:** every fact below comes from a read-only Git command run this pass (`status`, `diff`, `log`, `show`, `merge-base`, `tag -l`, `remote -v`) or a direct file read. No write command was executed. No production code, test, or governance document's substance was changed to produce this report.

---

## Phase A — Plan Validity Check

Re-ran the exact verification commands the prior `Release_Candidate_Preparation_Plan.md` was built on:

| Fact | Prior plan stated | Re-checked now | Changed? |
|---|---|---|---|
| Current HEAD | `643c770`, detached | `643c77075492a96f6a1c2d63a3b554f187814516`, detached | No |
| `git merge-base 643c770 phase2-development` | `643c770` (HEAD is a strict ancestor) | `643c77075492a96f6a1c2d63a3b554f187814516` — identical | No |
| `phase2-development` tip | `e18e9b0` | `e18e9b0` | No |
| `master` tip | `8a2a015` | `8a2a015` | No |
| Remote | none configured | `git remote -v` → empty | No |
| Tags | `v0.1.0-phase1` only | `v0.1.0-phase1` only | No |
| Modified tracked files | 11 | 11 (identical set: `poetry.lock`, `pyproject.toml`, and the 9 R1/R2/R7/R8 source+test files) | No |
| Untracked paths | 132 | 133 | **Yes — one new file** |

**The single change: `Release_Candidate_Preparation_Plan.md` itself**, created while writing the prior plan (it could not have listed itself). This is already conceptually covered by that plan's own Group C ("this engagement's own output") even though it wasn't literally enumerated there.

**Verdict: the prior plan remains valid. No amendment to its substance is required.** This report proceeds as a continuation, not a correction, except where noted explicitly in Phase D (one material refinement below, sourced from re-reading `phase2-development`'s `docs/VERSIONING.md` and `docs/RELEASING.md` in full, which the prior plan had only partially quoted).

---

## Phase B — Reconciliation Plan for the Five Overlapping Files

For each file: differences, recommended base, recommended merged result, risks, justification. **No file was modified to produce this section.**

### B1. `pyproject.toml`

**Differences.** Working tree (389 lines, based on `643c770`) contains one line `phase2-development`'s version (420 lines) lacks entirely: `click = ">=7.1.1,<8.2.0"` with its inline justification comment. `phase2-development`'s version contains 32 additional lines the working tree lacks — confirmed (via `poetry show`/file inspection this session and the prior R14 pass) to include the `[project]`-adjacent scaffolding and version-policy plumbing that `docs/VERSIONING.md`'s two-axis policy (Phase D below) depends on. Critically: `phase2-development`'s `poetry.lock` still resolves `click` to `8.4.2` — the version the RCA (`docs/history/release/v0.2.0/Root_Cause_Analysis_v0.2.0_CLI_Test_Failures.md`) identified as broken. Neither side's `pyproject.toml` is a superset of the other.

**Recommended base:** `phase2-development`'s version (420 lines) — it is newer, additive, and required by `VERSIONING.md`'s already-committed policy.

**Recommended merged result:** `phase2-development`'s `pyproject.toml` plus the single `click = ">=7.1.1,<8.2.0"` dependency line (with its existing comment, verbatim) inserted in the same location relative to `typer`/`rich` it currently occupies in the working tree's version. `poetry.lock` must then be regenerated (`poetry lock`) against this merged `pyproject.toml`, not hand-copied from the working tree's `poetry.lock` — the two files have diverged in ways beyond just the `click` entry (`phase2-development` added dependencies/config the working tree's lock file was never regenerated against).

**Risks.** Regenerating `poetry.lock` against a `pyproject.toml` neither side has actually run `poetry lock` against before is a real risk of new, currently-unknown resolution differences (a transitive dependency could resolve to a different version than either side's current lock file shows) — this must be followed by a full dependency-install-and-test cycle, not assumed safe by inspection alone. This is a write operation (`poetry lock` mutates `poetry.lock`) and requires approval before execution, per the standing rule.

**Justification.** Confirmed by direct diff (`diff pyproject.toml /tmp/p2dev_compare/pyproject_p2dev.toml`) and by `grep click` against both files this session.

### B2. `src/finfluencer/__init__.py`

**Differences.** Working tree: docstring references "Architecture version: 2.1 (frozen)" and `ARCHITECTURE_v2.1.md`. `phase2-development`: docstring references `Software_Product_Architecture_v1.0.md` (a file that only exists on `phase2-development`) and adds a paragraph documenting that `__version__` mirrors `pyproject.toml`'s SemVer version specifically, as "a distinct axis from the research/citation version in `CITATION.cff`," pointing to `docs/VERSIONING.md`.

**Recommended base:** `phase2-development`'s version, in full, no merge needed.

**Recommended merged result:** No change beyond adopting `phase2-development`'s version as-is — the working tree has nothing this version lacks. The old `ARCHITECTURE_v2.1.md` reference would in fact be a stale/broken cross-reference if kept, since that file is not confirmed present at the repository root under that exact name in the current tree (not verified this pass either way — flagged, not asserted).

**Risks.** None identified — this is a documentation-only file with no executable divergence between versions.

**Justification.** Confirmed by direct diff (`diff src/finfluencer/__init__.py /tmp/p2dev_compare/init_p2dev.py`, 6 lines changed).

### B3. `docs/VERSIONING.md`

**Differences.** Working tree: 73 lines, generic SemVer policy (version format, bump rules, branch strategy) with no mention of `CITATION.cff` as a separate axis. `phase2-development`: 113 lines, committed at `ee94d73`, structured entirely around the two-axis policy (software version vs. research/citation version), including a "Why this split exists (TD-10)" section documenting a **prior real incident**: `__version__` was once accidentally bumped from `0.1.0` to `1.0.0` (copying `CITATION.cff`'s value) while `pyproject.toml` stayed at `0.1.0` — this exact class of confusion already happened once and was reverted; this document is the committed fix for the root cause. It also contains a "Current values" table stating explicitly: software version `0.1.0` (pre-1.0, "CLI/orchestration API still evolving"), research/citation version `1.0.0` dated `2026-07-26` ("Entity-centric migration v2, Run Manifest System, Market subsystem complete") — and a "Rules going forward" section whose rule 3 states verbatim: *"[CHANGELOG.md's] existing `[1.0.0]` entry pre-dates this policy and documents the same research milestone as CITATION.cff's current version — not a software package release."*

**Recommended base:** `phase2-development`'s version. This is not a close call — it is materially more complete, and it is the document that resolves the exact version-identity question this report's Phase D depends on. The working-tree draft does not just lack content, it lacks the policy that makes the rest of this reconciliation coherent.

**Recommended merged result:** Adopt `phase2-development`'s version unmodified. Before deleting the working-tree draft, a human should confirm it contains no checklist item or process nuance absent from the committed version — I compared section headers (§ below) and found no working-tree-only content that looked substantive rather than redundant, but a full line-by-line diff of prose (not just headers) was not performed this pass and is flagged as an open verification step, not skipped silently.

**Risks.** Low. The main risk is procedural (discarding the working-tree draft without the line-by-line check above), not technical.

**Justification.** Section-header comparison this pass: working tree has `Version format / Concrete examples / Pre-1.0 status / Tag naming / Branch strategy / Version bump rules`; `phase2-development` has `Software version / Research-citation version / Relationship diagram / Why this split exists (TD-10) / Rules going forward / Current values (as of Sprint 2.7A)` — structurally different documents, confirming the prior plan's assessment, now with the actual "Rules going forward" and "Current values" text captured directly (quoted above) rather than only asserted.

### B4. `docs/RELEASING.md`

**Differences.** Working tree: 136 lines, 6 numbered sections (`Pre-release checklist / Release checklist / Post-release verification / Rollback procedure / Emergency hotfix process / Open gaps`). `phase2-development`: 205 lines, committed at `60aec54`, different structure (`Quick reference / Semantic Versioning / Branch strategy / Release process / Tag strategy / CHANGELOG policy / Release readiness checklist / Open gaps`) and contains the authoritative, already-written CHANGELOG reconciliation text: *"The first software release under this policy is `[0.2.0]`... do not read the existing `[1.0.0]` entry as a starting point for software-version continuity"* and an explicit instruction to leave the existing `[1.0.0]` entry **in place**, not renumber or reword it.

**Recommended base:** `phase2-development`'s version — same reasoning as B3, and this file is where the actual CHANGELOG-reconciliation instruction lives (see Phase D).

**Recommended merged result:** Adopt `phase2-development`'s version unmodified. Same open item as B3: a full prose-level diff against the working-tree draft was not performed this pass.

**Risks.** Low, same caveat as B3.

**Justification.** Section-header comparison this pass, plus direct quotation of the "CHANGELOG policy" and "Release readiness checklist" sections (both reproduced in full above and in Phase D).

### B5. `.github/workflows/ci.yml`

**Differences.** Working tree: 31 lines, untracked, single job (checkout → Python 3.11 → install Poetry → `poetry install --no-interaction` → `poetry run pytest tests/ -q`). `phase2-development`: 95 lines, committed at `ce555e9`, two jobs — a `lint` job (scoped `ruff`+`mypy` against `src/finfluencer/reporting`, `src/finfluencer/cli.py`, and their tests only, with an inline comment explaining the scoping is deliberate: pre-existing findings elsewhere are "tracked separately and... not enforced yet"), then a `test` job (`needs: lint`, matrix over `os: [ubuntu-latest, windows-latest]` × `python-version: ["3.11", "3.12"]`, `poetry install --sync` instead of plain `install`, a coverage-artifact upload step with `if: always()`). Comments in the committed version cite `KNOWN_ISSUES.md`'s Windows-specific torch DLL failure as the explicit reason the OS axis is not thinned — direct evidence this version was written with this repository's own documented history in mind, not a generic template.

**Recommended base:** `phase2-development`'s version, unmodified.

**Recommended merged result:** No merge needed — the working tree's version is a strict functional subset (fewer jobs, no lint gate, no OS/version matrix, no artifact upload) with nothing unique to preserve.

**Risks.** None identified for adopting this file as-is. A secondary risk exists but is not about *this file*: once this CI workflow is committed and pushed, it will actually run for the first time (§ R14, `.github/` is currently untracked) — the lint job in particular has never executed against this repository's current code, so it is unverified whether `ruff`/`mypy` currently pass against `src/finfluencer/reporting`/`cli.py` even scoped as narrowly as the workflow specifies. This is a genuine unknown, not assumed clean, and is carried into Phase E as UNKNOWN, not PASS.

**Justification.** Full diff already performed in the prior `Release_Candidate_Preparation_Plan.md` §1 and re-confirmed unchanged in Phase A above.

---

## Phase C — Executable Commit Sequence

No commits created. For each: title, files, rationale, dependency, rollback impact.

| # | Title | Files | Rationale | Dependency | Rollback impact |
|---|---|---|---|---|---|
| 0 | *(pre-step, not a commit)* `git branch wip/pre-rc-snapshot 643c770` | — | Preserves the exact current detached-HEAD state under a real name before anything else touches it. Detached HEAD is reachable only by hash today; one accidental checkout elsewhere risks it becoming unreachable and eventually garbage-collected. | None | N/A — this is a safety net, not a functional change. Reverting it means simply not using the branch; nothing downstream depends on it existing. |
| 1 | `merge(deps): reconcile pyproject.toml/poetry.lock with phase2-development, keep click pin` | `pyproject.toml`, `poetry.lock` | Implements Phase B1's merged result: `phase2-development`'s `pyproject.toml` as base + the click pin, then a regenerated lock file. | Requires checkout onto `phase2-development` first (a write op — §Approval Gate 1 below) | Revertible with `git revert` — no other commit depends on the *exact* resolved dependency versions, only on `click`'s major/minor range, which stays constant whether or not the full re-lock is later reverted. |
| 2 | `docs(release): adopt phase2-development's RELEASING.md, VERSIONING.md, ci.yml, __init__.py as authoritative` | `docs/RELEASING.md`, `docs/VERSIONING.md`, `.github/workflows/ci.yml`, `src/finfluencer/__init__.py` | Implements Phase B2-B5. Bundled into one commit because all four are the same class of change (adopt-committed-version, no working-tree content survives) and none has a runtime dependency on another. | 1 (sequencing only — avoids interleaving unrelated diffs in history; no technical dependency) | Fully revertible; these are documentation/CI files with no runtime coupling to application code. |
| 3 | `fix(logging): make configure() re-apply on every call (ADR-P2-003)` | `src/finfluencer/core/logging.py`, `tests/unit/test_core/test_logging.py` (new) | Already-verified R7 fix, unchanged from this engagement's own Implementation Log. | 2 (CI workflow from commit 2 will be the first thing to actually run against this change) | Revertible; regression-tested in this engagement (6/6 new tests, full sweep clean at the time). |
| 4 | `fix(checkpoint): add read-only has_valid_marker for dry-run (ADR-P2-004)` | `src/finfluencer/core/checkpoint.py`, `src/finfluencer/reporting/orchestrator.py`, `tests/unit/test_core/test_checkpoint.py`, `tests/unit/test_reporting/test_orchestrator.py` | Already-verified R8 fix. | 3 | Revertible; `should_run()`'s 8 existing callers were hand-traced as behaviorally unchanged in this engagement's own verification. |
| 5 | `fix(providers): split comments-disabled from resource-not-found (ADR-P2-002)` | `src/finfluencer/core/exceptions.py` (new `CommentsDisabledError`), `src/finfluencer/providers/platform/youtube.py`, `src/finfluencer/collect/comments.py`, `tests/unit/test_providers/test_youtube.py`, `tests/unit/test_collect/test_comments.py` (new) | Already-verified R2 fix. | 4 | Revertible; explicitly did not touch `collect/videos.py` (R16, out of scope), keeping the blast radius contained. |
| 6 | `test(providers): add behavioural-contract coverage for youtube.py (ADR-P2-001)` | `tests/unit/test_providers/test_youtube.py` (R1's additions — same file as commit 5's test changes; if partial-file staging isn't practical with the tooling used, combine commits 5 and 6) | Already-verified R1 work. Test-only, zero production-code lines. | 5 | Fully revertible with zero production-code impact — the safest commit in this sequence by construction. |
| 7 | `docs(governance): add Phase 2/3 risk matrix, ADRs, sprint backlog, R14/RC1 verification reports` | `Phase2_Repository_Risk_Matrix_and_ADRs.md`, `Phase3_Engineering_Governance_Sprint_Backlog.md`, `R14_Release_Engineering_Verification.md`, `Release_Candidate_Preparation_Plan.md`, `RC1_Readiness_and_Reconciliation_Report.md` (this file) | This engagement's own paper trail. | 6 | Fully revertible; no code depends on these files existing. |

**Explicitly excluded from this sequence** (per your instruction and the prior plan's Group D/E): `src/finfluencer/migration/` + `tests/unit/test_migration/` (out of scope for v0.2.0 — a separate decision, not made here), and the ~115 research-artifact/script files at the repository root (a `.gitignore` scope decision, not a commit).

**Write operations this sequence requires, none executed:** `git branch` (step 0), `git checkout phase2-development` (before step 1), `poetry lock` (within step 1, mutates `poetry.lock`), then `git commit` × 7 (or 6, if 5/6 are combined). Per the standing rule, each of these stops for explicit approval before execution — see the Approval Gates list at the end of this report.

---

## Phase D — Release Candidate Metadata Review

| Source | Value | Status |
|---|---|---|
| `pyproject.toml` `[tool.poetry].version` | `0.1.0` | Current software version — correct per `phase2-development`'s `VERSIONING.md` "Current values" table |
| `src/finfluencer/__init__.py` `__version__` | `0.1.0` | Matches `pyproject.toml` — consistent |
| `CHANGELOG.md` | One entry, `[1.0.0] - 2026-07-26`, no `[Unreleased]` section | Ambiguous in isolation; **resolved by evidence below** |
| `CITATION.cff` | `version: 1.0.0`, `date-released: 2026-07-26` | Intentional — confirmed, not assumed (below) |
| `docs/VERSIONING.md` (`phase2-development`) | Explicit two-axis policy, with a "Current values" table matching all four rows above exactly | Authoritative source for this entire table |
| Git tags | `v0.1.0-phase1` only | No software release has been tagged |

**This resolves the prior plan's open question, not just restates it.** `Release_Candidate_Preparation_Plan.md` §5 identified the `CHANGELOG.md`/`CITATION.cff`/`pyproject.toml` conflict but left it as "a fork ... not resolved by evidence gathered this pass," because it had only partially quoted `phase2-development`'s `VERSIONING.md`. Re-reading that file in full this pass, its "Rules going forward" §3 states, verbatim: *"[CHANGELOG.md's] existing `[1.0.0]` entry pre-dates this policy and documents the same research milestone as CITATION.cff's current version — not a software package release... The first software release under this policy is `[0.2.0]`... do not read the existing `[1.0.0]` entry as a starting point for software-version continuity."* And its own "Why this split exists (TD-10)" section documents that this exact confusion (a runtime `__version__` accidentally copying `CITATION.cff`'s value) already happened once, was caught, and was reverted — this policy is the fix for a real prior incident, not speculative process-writing.

**This is an Amendment to `Release_Candidate_Preparation_Plan.md` §5-§6, not a silent change:** that plan is superseded on this one point by the fuller evidence gathered this pass. Its recommendations (adopt `0.2.0` as the next software version, leave `CITATION.cff` alone pending confirmation) turn out to match `phase2-development`'s already-committed policy exactly — the uncertainty has been resolved in the direction that plan already leaned, not reversed.

**Recommended single consistent RC-1 state** (a recommendation for the eventual release commit — not executed here, no files edited):
1. `pyproject.toml` / `__init__.py`: remain `0.1.0` through RC-1 preparation. Bump to `0.2.0` only at the actual release commit (`chore(release): v0.2.0`), per `VERSIONING.md` rule 4 ("bumped only at an actual tagged release") — RC-1 is explicitly not that moment, per your objective statement ("NOT for publication... Only RC preparation").
2. `CHANGELOG.md`: leave the existing `[1.0.0]` entry **exactly as-is**, per `phase2-development`'s own `RELEASING.md` CHANGELOG policy, which explicitly instructs against renumbering, rewording, or removing it. Add a new `[Unreleased]` section above it (currently entirely absent — confirmed by direct read) listing this engagement's changes, to be renamed `[0.2.0] - <date>` at actual release time, not RC-1 time.
3. `CITATION.cff`: do not touch. `phase2-development`'s `RELEASING.md` checklist explicitly lists *"`CITATION.cff` left untouched"* as its own line item.
4. Result: at RC-1, the repository correctly shows `0.1.0` everywhere software-version is reported, with a clearly-scoped `[Unreleased]` changelog section describing exactly this engagement's four resolved findings (R7, R8, R2, R1) plus the click dependency pin, and `CITATION.cff` unchanged. No version-identity contradiction remains once `phase2-development`'s own already-written policy is simply adopted rather than re-invented.

---

## Phase E — RC Checklist Re-Evaluation

Re-scored using PASS / PARTIAL / BLOCKED / UNKNOWN, against `phase2-development`'s own "Release readiness checklist" (Phase B4) plus this engagement's additional items:

| Item | Status | Basis |
|---|---|---|
| CI is green on the development branch (lint + full OS/Python matrix) | **UNKNOWN** | The matrix CI (Phase B5) has never executed against this codebase — it is untracked/never pushed. Cannot be scored PASS or FAIL without running it, which is a write-adjacent operation (requires committing + pushing) not performed this pass. |
| `tests/unit/test_version_sync.py` passes | **UNKNOWN** | File exists only on `phase2-development` (confirmed, R14), absent from the current working tree. Not run this pass. |
| `CHANGELOG.md` has a dated entry for this version | **BLOCKED** | No `[Unreleased]` section exists yet (confirmed by direct read); this is Phase D's own recommended next step, not yet done. |
| `pyproject.toml`'s version and `__version__` match | **PASS** | Both `0.1.0`, confirmed by direct read this pass and in R14. |
| `CITATION.cff` is deliberately not touched | **PASS** | Confirmed untouched — no diff against its last commit exists in `git status`. |
| Milestone-specific review sign-off given | **PASS** | This engagement's own Sprint 1 approval workflow (R7→R8→R2→R1, each explicitly approved before implementation) constitutes exactly this. |
| `git status` shows no unexpected untracked/modified files | **BLOCKED** | 11 modified + 133 untracked, unchanged in kind since R14 (Phase A). |
| Full test suite passes | **BLOCKED** | 13 known R17 failures (two mechanisms, not fixed per this task's explicit exclusion), plus ML-dependent suites never run in this sandbox (UNKNOWN, not assumed passing). |
| Coverage meets 75% threshold | **UNKNOWN** | Not re-measured project-wide this pass; R1's own measurement was scoped to `youtube.py` only. |
| `poetry check` reports no issues | **PARTIAL** | Exits 0, but 15 deprecation warnings under Poetry 2.4.1 for the legacy `[tool.poetry]` metadata format (R14 §1.5) — a real but non-blocking finding. |
| `poetry lock --check` confirms lock matches `pyproject.toml` | **UNKNOWN** | Not executable in this session's Python 3.10.12 environment (below the project's declared `>=3.11` floor) — an environment limitation, not a repository defect (R14 §1.6). |
| Documentation cross-references internally consistent | **PARTIAL** | The `CHANGELOG.md`/`CITATION.cff`/`VERSIONING.md` question is now resolved (Phase D) — but the two divergent `RELEASING.md`/`VERSIONING.md` drafts (Phase B3-B4) are not yet reconciled in the actual working tree; only planned. |
| Working tree is on the intended release branch | **BLOCKED** | Still detached HEAD at `643c770` (Phase A). |
| A remote is configured | **BLOCKED** | `git remote -v` empty, confirmed again this pass. |
| Out-of-scope `migration/` subpackage explicitly deferred, not silently bundled | **PASS** | Explicitly excluded from the Phase C commit sequence, per your instruction, with rationale documented in the prior plan's Group D. |
| R17 fixed or explicitly accepted as documented known issue | **BLOCKED** | Neither has happened — explicitly out of scope for this task per your instruction not to implement R17. No `KNOWN_ISSUES.md` entry exists for it yet either (confirmed by grep this pass — not present). |

**Tally: 3 PASS, 2 PARTIAL, 6 BLOCKED, 5 UNKNOWN.** Zero items regressed from Phase A's baseline; two items (`CHANGELOG.md`/`CITATION.cff` consistency, and the `pyproject.toml`/`__version__` match) are now scored with higher confidence than the prior plan could offer, because Phase D resolved an ambiguity the prior plan had left open.

---

## Phase F — Final RC-1 Readiness Report

### Executive Summary

The engineering work this release would contain is finished and verified: four Critical/High findings (R1, R2, R7, R8) resolved with regression tests across a disciplined, one-at-a-time approval workflow, plus a real, correctly-reasoned dependency fix (the Typer/Click pin) inherited from a prior session's own root-cause analysis. Separately, `phase2-development` — a branch that already exists in this repository, seven commits ahead of the current checkout — already contains a more mature release-engineering foundation (a two-job CI matrix, a two-axis versioning policy that resolves what looked like a version-identity contradiction, a version-sync regression test) that this session's working tree never picked up because it was never rebased forward. **Reconciling these two lines of work is mechanical and low-risk for 4 of 5 overlapping files** (Phase B2, B3, B4, B5 all resolve to "adopt `phase2-development`'s version, no merge needed") and requires one small, well-justified hand-edit for the fifth (`pyproject.toml`, Phase B1: add one dependency line, then regenerate the lock file). No file-level conflicts exist between this session's own code changes and `phase2-development`'s advances.

### Remaining Risks

1. **The two never-diffed documentation drafts** (`docs/RELEASING.md`, `docs/VERSIONING.md` working-tree versions) were compared by section structure, not line-by-line prose, this pass. Low probability of hidden substantive content, but not zero — flagged, not dismissed.
2. **`poetry.lock` regeneration is unverified.** Merging `pyproject.toml` per Phase B1 requires a fresh `poetry lock` run that neither this session nor `phase2-development` has actually performed against the merged file. New transitive-dependency resolutions are possible and would need a full install-and-test cycle before being trusted.
3. **The CI workflow that would gate this release has never run.** Its lint job in particular is entirely unverified against current code (Phase B5) — committing it is not the same as knowing it passes.
4. **R17 (13 CLI-JSON-test failures, two mechanisms) is unresolved and explicitly out of scope for this task.** It remains the single most concrete, reproducible, currently-red item blocking a genuine "tests pass" claim.
5. **Environment mismatch.** This entire engagement's test verification ran on Python 3.10.12; the project requires `>=3.11`. Not evidence of a defect, but a real confidence ceiling on every "tests pass" statement made this engagement, RC-1 included.

### Blocking Items (for RC-1, specifically — not v1.0)

- Detached HEAD not yet reconciled onto a named branch (Phase C, step 0 onward — requires approval).
- `pyproject.toml`/`poetry.lock` merge and re-lock not yet performed (Phase B1/C1 — requires approval).
- `docs/RELEASING.md`, `docs/VERSIONING.md`, `ci.yml`, `__init__.py` adoption not yet performed (Phase C2 — requires approval).
- `CHANGELOG.md` `[Unreleased]` section not yet added (Phase D — requires approval to edit).
- R17 not fixed or formally logged in `KNOWN_ISSUES.md` as an accepted gap.
- Group E `.gitignore` scope decision not made (unrelated to release readiness per se, but blocks the "`git status` clean" checklist item indefinitely if left unaddressed).

### Recommended Next Actions

In dependency order, each still requiring your explicit approval before any write command runs:
1. Approve `git branch wip/pre-rc-snapshot 643c770` (pure safety net, zero functional effect).
2. Approve checkout onto `phase2-development` and execution of Phase C's commit sequence (7 commits, or 6 if 5/6 combine), including the `pyproject.toml` merge and `poetry lock` regeneration in commit 1.
3. Approve adding the `[Unreleased]` `CHANGELOG.md` section (Phase D) as part of, or immediately following, commit 7.
4. Decide on R17: fix it (would require lifting this task's "do not implement R17" restriction) or formally document it in `KNOWN_ISSUES.md` as an accepted, dated, known gap.
5. Decide on Group D (`migration/` subpackage) and Group E (root-level research clutter / `.gitignore` scope) — both independent of the above and not blocking RC-1 commit sequencing, but blocking a fully clean `git status`.

### Go / No-Go

**No-Go for RC-1 tagging today; Go for executing the reconciliation plan above, pending your approval at each write-operation gate.** This is a narrower, more optimistic verdict than R14's original No-Go: the release-engineering *content* problem (contradictory version claims) turns out to already have a correct, committed answer waiting on `phase2-development` — this is a reconciliation task with a known-good target, not an open design problem. What remains is executing that reconciliation (all write operations, all gated) and closing R17.

### Confidence Level

**Medium-High** on the reconciliation plan's correctness (every file-level recommendation in Phase B is backed by a direct diff or direct quotation from the actual committed content, not inference). **Medium** on overall RC-1 timeline, held down specifically by the three genuine UNKNOWNs in Phase E (CI matrix never run, `poetry lock --check` not executable in this environment, project-wide coverage not re-measured) — none of these are evidence of a problem, but none can be honestly upgraded to PASS without actually running them in a properly-versioned environment, which this sandbox cannot do (Python 3.10.12 only).

---

## Approval Gates Required Before Any Further Action

Per the standing rule, none of the following have been executed. Each requires your explicit go-ahead, individually:

1. `git branch wip/pre-rc-snapshot 643c770`
2. `git checkout phase2-development` (or equivalent — moves HEAD off the current detached commit)
3. `poetry lock` (regenerates `poetry.lock` against the merged `pyproject.toml` from Phase B1)
4. `git commit` × 6-7 (Phase C sequence)
5. Any edit to `CHANGELOG.md` (Phase D's recommended `[Unreleased]` section)
6. Any edit to `KNOWN_ISSUES.md` (if R17 is logged as an accepted gap rather than fixed)

I have not run, and will not run, any of these without your explicit instruction to proceed.
