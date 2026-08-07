# Sprint 2.7 — Release Hardening Roadmap

**Role:** Chief Software Architect / Technical Program Manager / Release Manager / QA Lead / DevOps Engineer.
**Purpose:** Take the repository from its current, uncommitted, CI-unvalidated state to a genuine, publicly-releasable `v0.2.0` Release Candidate, and lay out Sprint 3 and the path to `v1.0` beyond it.
**Constraint on this document:** planning and analysis only — no code was written, no file was modified, no patch was produced to create this roadmap.
**Independent re-verification performed before writing this roadmap:** `git status`/`git tag`/`git branch`/`git remote` re-checked live; `pyproject.toml` version, `CHANGELOG.md`, and `CITATION.cff` cross-read; `hypothesis`/`pytest-mock`/`responses` dev-dependency usage grepped against the actual test suite (all three: zero usage found). Two corrections to the prior Architecture Review and one new finding came out of this re-check — both are called out explicitly below rather than silently folded in, per the instruction to treat the prior findings as a backlog to re-evaluate, not a ground truth to restate.

---

# Executive Assessment

**Current maturity:** Late-stage feature-complete for the "research analysis application" scope Sprint 1–2 targeted. The statistical core (Sprint 1), the orchestration/CLI/GUI-adapter layer (Sprint 2), and the underlying reproducibility infrastructure (pre-Sprint-1) are all functionally sound and well-tested in isolation. What is missing is not features — it is the release-engineering scaffolding around those features: version control, CI validation, a coherent versioning policy, and a small number of concurrency/compliance gaps that only matter because of what Sprint 2 just made possible (concurrent `AnalysisJob` execution).

**Current completion percentage (qualitative, not a precision metric — see note below):**
- Sprint 1 (statistical core): **100%** complete and previously approved.
- Sprint 2 (orchestration/CLI/GUI adapter): **100%** functionally complete and previously approved.
- Release readiness (what this document exists to close): **~30%** — the process/infrastructure work (git history, CI, versioning policy, docs, packaging) is almost entirely still ahead, even though the code it needs to validate already exists and works.

*Note on precision:* no single "% done" number can be defended to two significant figures for a release-readiness gap that is mostly process debt rather than code debt; the figure above is a judgment call meant to communicate "the hard engineering is done, the release plumbing is not," not a metric to be tracked literally.

**Production readiness:** Not yet. Confirmed unchanged from the Architecture Review: the code is production-quality, the repository is not yet in a production-releasable state (TD-0 alone is disqualifying regardless of code quality).

**Remaining effort to a defensible `v0.2.0` tag:** Small-to-Medium in aggregate — the roadmap below sequences it into 18 milestones, the large majority of which are Tiny/Small individually. Nothing in this roadmap requires new statistical logic, a redesign of the orchestrator, or new architecture — it is entirely hardening, process, and documentation work layered on top of what Sprint 1/2 already built correctly.

---

# Independent Re-Verification Notes

Per the instruction not to assume the prior Architecture Review is correct, three things changed on re-inspection:

1. **Correction to TD-7 / the property-based-testing gap.** The prior review stated "hypothesis is not a dependency, not used." Re-checked: `hypothesis = "^6.98"` **is** already declared in `[tool.poetry.group.dev.dependencies]` — it was simply never adopted (zero usage anywhere in `tests/`). This changes the recommendation from "add a new dependency and build property-based test infrastructure" (Medium effort) to "write property-based tests against tooling that is already installed" (Small effort) — a materially cheaper and more actionable finding than originally stated. Folded into Milestone 2.7.17 below.
2. **New finding not in the original backlog — TD-10: versioning is currently three-way inconsistent.** `pyproject.toml` declares `version = "0.1.0"`; `CHANGELOG.md` and `CITATION.cff` both already declare `version: 1.0.0` / `## [1.0.0] - 2026-07-26`; the only git tag in the repository is `v0.1.0-phase1`. These are not three attempts at the same number that drifted — they appear to be **two different, legitimately separate versioning axes that were never explicitly decoupled**: a *research-citation version* (CITATION.cff/CHANGELOG, tracking when the underlying study/manuscript reached completeness, dated July 26) and a *software-package SemVer* (pyproject.toml, tracking the Python package's own API/behavior stability, currently pre-1.0 because the CLI/orchestration surface is still actively evolving — which Sprint 2 itself proves). This is directly load-bearing for this document's own request to "design Semantic Versioning" and must be resolved explicitly, not silently, before any tag is cut. See Milestone 2.7.7 and Phase 3.
3. **Non-finding, confirmed correct, not re-litigated:** TD-0 through TD-9 as stated in the Architecture Review were all independently re-confirmed live (126 untracked/modified paths in `git status` at time of writing, `.github/workflows/ci.yml` still untracked, `finfluencer.ethics` package still does not exist, `core.logging._CONFIGURED` singleton unchanged, no Windows/matrix CI, `market/` still uses `print()`). No git remote is currently configured (`git remote -v` returns empty) — this is upstream of TD-0/TD-5/TD-6 and is folded into Phase 1/2 below since none of "push," "CI runs," or "tag and release" are possible without one.

---

# Release Hardening Roadmap

Each phase lists Objectives, Files affected, Expected risks, Expected benefits, Estimated effort, Dependencies, Blocking items, and Success criteria, as required. Phases are ordered by dependency, not just priority — Phase 1 must complete before anything downstream can be validated at all.

## Phase 1 — Repository Safety & Hygiene

- **Objectives:** Get Sprint 1 and Sprint 2 into git history as a reviewable commit sequence; establish (or confirm) a remote; resolve the untracked-file sprawl so `git status` becomes a meaningful signal again; tag a clean pre-hardening baseline.
- **Files affected:** All of `src/finfluencer/reporting/`, `src/finfluencer/migration/`, `tests/unit/test_reporting/`, `tests/unit/test_cli.py`, `tests/unit/test_migration/`, `.github/`, `pyproject.toml`, `poetry.lock`, `src/finfluencer/cli.py`, `src/finfluencer/__init__.py` (all currently modified/untracked per `git status`); the ~115 other untracked root-level files (legacy build scripts, versioned analysis exports, review documents, images) need a per-file keep/archive/delete decision, not a blanket commit.
- **Expected risks:** Committing indiscriminately (`git add -A`) would permanently enshrine scratch files, duplicate analysis exports, and multi-hundred-KB images in git history. Under-committing (cherry-picking too conservatively) would leave the exact same TD-0 problem half-solved.
- **Expected benefits:** Every subsequent phase becomes independently reviewable, revertable, and — critically — actually testable by CI instead of only by this session's sandbox.
- **Estimated effort:** Small (the commits themselves are tiny; the judgment calls about what belongs in git are the actual work).
- **Dependencies:** None — this is the root of the dependency graph for the entire roadmap.
- **Blocking items:** None currently outstanding; this phase is unblocked and should start immediately.
- **Success criteria:** `git status` is clean or shows only genuinely-in-progress work; `reporting/`, `job.py`, and their tests are in git history across a reviewable commit sequence; a `pre-hardening-baseline` tag exists; a remote is configured and reachable.

## Phase 2 — Continuous Integration

- **Objectives:** Make CI actually run (it never has), and make it actually gate what it claims to gate (lint, types, multi-platform, multi-version).
- **Files affected:** `.github/workflows/ci.yml`.
- **Expected risks:** Adding `ruff`/`mypy` as hard gates for the first time may surface pre-existing violations across the whole codebase (not just Sprint 2) that have never been checked — this could be a non-trivial, possibly noisy, first run. Adding a Windows runner may surface environment-specific failures beyond the already-known torch/DLL issue.
- **Expected benefits:** Converts every claim of "tests pass" made in this project's history (including this session's own) from "verified in one person's sandbox" to "verified reproducibly, on a clean runner, for every future change."
- **Estimated effort:** Small for wiring the steps; Medium if the first real run surfaces a backlog of pre-existing lint/type violations that need triage (expect this — it has never run before).
- **Dependencies:** Phase 1 (nothing can be validated by CI until it exists in git and is pushed).
- **Blocking items:** Phase 1 completion (remote + push).
- **Success criteria:** A CI run is visible in the repository's Actions tab, green, on `ubuntu-latest` and `windows-latest`, across at least Python 3.11 and one newer minor version, including `ruff check` and `mypy` as separate, named, gating steps.

## Phase 3 — Release Engineering Process Design

- **Objectives:** Resolve TD-10 (decouple research-citation versioning from software SemVer, explicitly and in writing); define branch strategy, tag conventions, and the release checklist that Phase 8 will execute; define the CHANGELOG convention going forward.
- **Files affected:** `pyproject.toml` (version field only), `CHANGELOG.md`, a new `docs/RELEASING.md` (or equivalent), `CONTRIBUTING.md` (branch-strategy section).
- **Expected risks:** Getting this wrong (e.g., silently overwriting `CITATION.cff`'s already-published `1.0.0`) would corrupt an already-external-facing citation identity for the research artifact. Getting the branch strategy wrong (e.g., committing to `master` directly) would undermine the "small reviewable milestones" discipline this entire roadmap depends on.
- **Expected benefits:** A single, unambiguous, written answer to "what does v0.2.0 mean, and how do we get there" that this document, `CHANGELOG.md`, and every future release both depend on and can be checked against.
- **Estimated effort:** Small — this is a decision-and-document phase, not an implementation phase.
- **Dependencies:** Phase 1 (branch strategy needs a real git history to branch from).
- **Blocking items:** None beyond Phase 1.
- **Success criteria:** `docs/RELEASING.md` exists and unambiguously states: (a) `pyproject.toml`/git tags follow standard SemVer for the software package, currently pre-1.0 (`0.x.y`, breaking changes allowed between minors until `1.0.0`); (b) `CITATION.cff` tracks the research artifact's own citation version independently and is *not* touched by software releases unless the underlying study itself changes; (c) branch strategy (`master` = last release, `phase2-development` retired in favor of short-lived milestone branches merged via PR, or an equivalent explicit policy); (d) tag convention (`vX.Y.Z`, annotated tags with release notes).

## Phase 4 — Concurrency Hardening

- **Objectives:** Close TD-1 (logging singleton) and TD-2 (checkpoint single-writer) — the two gaps that are invisible today but directly contradict the concurrent-execution model `AnalysisJob` was built to enable.
- **Files affected:** `src/finfluencer/core/logging.py`, `src/finfluencer/core/checkpoint.py`, `src/finfluencer/reporting/job.py` (docstring only, to state the constraint or the fix), new test files under `tests/unit/test_core/` and `tests/unit/test_reporting/`.
- **Expected risks:** A full fix to the logging singleton (per-job/per-study scoped loggers) is an API-shape decision that could ripple into every module using `get_logger()` — this needs to be scoped carefully (interim documentation-and-test fix now, larger redesign only if Sprint 3's GUI work actually needs it). The checkpoint lock, if implemented as a cross-process file lock, adds a new dependency (`filelock` or similar) and a new failure mode (stale locks after a crash) that needs its own test coverage.
- **Expected benefits:** Removes the single most concrete correctness gap between the codebase and the concurrent, multi-job future it is explicitly being built toward.
- **Estimated effort:** Small (interim fix: document + test the current single-configure behavior explicitly) to Medium (full fix: scoped logging and/or a real lock).
- **Dependencies:** Phase 2 (needs CI to validate a concurrency-sensitive change with confidence).
- **Blocking items:** Decision on interim-vs-full fix (recommend interim now, full fix scoped into Sprint 3 once real GUI usage patterns are known — see Sprint 3 Roadmap).
- **Success criteria:** A test exists that asserts and documents `core.logging.configure()`'s current call-once behavior (turning a silent gap into an explicit contract); a test exists that exercises two `AnalysisJob`s sharing a `checkpoint_root` and demonstrates either safe serialization or a clear, typed error — never a silent race.

## Phase 5 — Data Governance / Ethics Resolution

- **Objectives:** Resolve TD-3 — decide whether `EthicsConfig.retention_days`/`.sensitive_topic_detection` get real enforcement or get explicitly marked as reserved/not-yet-enforced, and act on that decision everywhere it's referenced (config docstrings, `README.md`'s configuration table, `core/exceptions.py`'s `RetentionPolicyError`/`SensitiveContentError` docstrings).
- **Files affected:** `src/finfluencer/core/contracts.py` (docstrings), `src/finfluencer/core/exceptions.py` (docstrings), `config/settings.yaml` (comments), `README.md`, and — only if the "implement" path is chosen — new `src/finfluencer/ethics/retention.py` / `sensitive.py` modules plus tests.
- **Expected risks:** Implementing real enforcement is the larger, riskier path (new module, new integration points in the collection pipeline, new tests) and could scope-creep well beyond "release hardening" into new feature work. Marking as reserved is cheap but is a product decision, not just an engineering one, and should be made deliberately rather than defaulted into.
- **Expected benefits:** Either real compliance behavior (preferred if in scope) or, at minimum, an accurate, non-misleading representation of what the platform currently guarantees — closing the gap between what `settings.yaml`'s own comments imply and what the code does.
- **Estimated effort:** Tiny (mark as reserved) or Medium (implement minimally).
- **Dependencies:** None technical; depends on a product decision (recommend: mark as reserved for `v0.2.0`, implement in Sprint 3 once a real retention/sensitivity workflow is specified — see Sprint 3 Roadmap).
- **Blocking items:** The product decision itself (this document recommends "mark as reserved" as the `v0.2.0`-appropriate choice; implementing real enforcement is Sprint 3+ scope).
- **Success criteria:** No config field or exception class in the repository implies enforcement that does not exist; `README.md`'s configuration table accurately reflects what's active today.

## Phase 6 — Documentation

- **Objectives:** Close TD-4 and produce the full documentation set requested: README updates, Architecture v1.1, ADR-Sprint2-01 as a real file, Developer Guide, User Guide, API Reference, Installation Guide, GUI integration guide.
- **Files affected:** `README.md`, `Software_Product_Architecture_v1.0.md` (superseded by or extended into a v1.1), a new `ADR-Sprint2-01_AnalysisJob_Hybrid_API.md`, and a new `docs/` tree (`docs/developer-guide.md`, `docs/user-guide.md`, `docs/api-reference.md` or Sphinx/mkdocs-generated equivalent — `mkdocs`/`mkdocs-material` are already declared in `[tool.poetry.group.docs]`, currently unused, matching the same "declared-but-unused tooling" pattern as `hypothesis`), `docs/installation.md`, `docs/gui-integration.md` (the latter specifically documenting `AnalysisJob`'s contract for a future GUI author: lifecycle, the logging-singleton constraint from Phase 4, the coarse progress model, cancellation latency).
- **Expected risks:** Documentation debt compounds if this phase is treated as optional polish rather than a release blocker for an *external, public* release — a public `v0.2.0` with no reporting-CLI documentation and a stale architecture doc actively misleads anyone evaluating the project.
- **Expected benefits:** Restores documentation as a reliable onboarding and evaluation path; gives ADR-Sprint2-01's design rationale permanence beyond this chat session; the GUI-integration guide specifically de-risks Sprint 3's desktop-GUI work by writing down `AnalysisJob`'s real contract (including its current limitations) before a GUI developer discovers them the hard way.
- **Estimated effort:** Medium in aggregate (Small per individual document, but there are seven of them).
- **Dependencies:** Phase 4 (the GUI-integration guide needs to describe the *actual*, hardened concurrency contract, not the pre-hardening one).
- **Blocking items:** None beyond Phase 4's completion for the GUI-integration guide specifically; the other six documents can start immediately in parallel with Phases 2–5.
- **Success criteria:** A new contributor can go from `git clone` to running both `finfluencer run` and `finfluencer analyze/report/validate/export` using only `README.md`; `mkdocs build` (or equivalent) succeeds against the new `docs/` tree; ADR-Sprint2-01 exists as a committed file.

## Phase 7 — Packaging & Dependency Hardening

- **Objectives:** Close TD-8 — introduce a lightweight install path for the reporting/analysis surface that does not require `torch`/`transformers`/`sentence-transformers`/`bertopic`; assess and document PyInstaller readiness for a future desktop build.
- **Files affected:** `pyproject.toml` (`[tool.poetry.extras]` and dependency grouping), `README.md` (installation section), a new `docs/packaging-notes.md` capturing the PyInstaller readiness assessment (spec file itself is Sprint 3 scope, not this phase — see below).
- **Expected risks:** Splitting dependencies retroactively risks breaking the existing "install everything, `finfluencer run` end to end" default workflow if the split is not backward-compatible; needs to default to the current full install and make the lightweight path opt-in, not the other way around, to avoid a breaking change disguised as a packaging improvement.
- **Expected benefits:** A materially smaller, faster, more reliable install for exactly the workflow ("regenerate reports from already-collected data") most likely to be the first desktop-GUI build target in Sprint 3.
- **Estimated effort:** Medium (dependency-graph surgery needs care; every `reporting/` module's actual import set should be re-verified against the new extras boundary, not assumed).
- **Dependencies:** None technical; benefits most from happening before Sprint 3's GUI packaging work begins.
- **Blocking items:** None.
- **Success criteria:** `poetry install --extras reporting` (or equivalent) installs and runs `analyze`/`report`/`validate`/`export` successfully with `torch` absent from the environment; the default `poetry install` behavior is unchanged; a documented PyInstaller readiness note exists (even if the actual spec file is Sprint 3 work).

## Phase 8 — v0.2.0 Release Candidate

- **Objectives:** Execute the process Phase 3 designed: bump `pyproject.toml` to `0.2.0`, write the real `CHANGELOG.md` entry (correctly scoped as the software package's changelog, not conflated with the research-artifact `1.0.0`), run the full release checklist (below), tag, and publish release notes.
- **Files affected:** `pyproject.toml`, `CHANGELOG.md`, a new annotated git tag `v0.2.0`, GitHub Release notes.
- **Expected risks:** Cutting this before Phases 1–7 are genuinely complete would repeat exactly the mistake this whole roadmap exists to prevent (a tag that doesn't correspond to validated, documented, committed reality).
- **Expected benefits:** A `v0.2.0` that is actually true — installable, documented, CI-validated, and versioned coherently.
- **Estimated effort:** Tiny (the mechanics), contingent on everything upstream being genuinely done.
- **Dependencies:** Phases 1–7, all of them.
- **Blocking items:** Every phase above.
- **Success criteria:** See the Release Checklist section below in full — this phase's success criteria *is* that checklist, executed and green.

---

# Milestone Breakdown

Eighteen milestones, numbered sequentially within Sprint 2.7, each scoped to touch as few files as possible, contain one logical change, and be independently testable and commitable — the same discipline used throughout Sprint 2.

### Milestone 2.7.1 — Commit the Sprint 1 baseline
- **Objective:** Get `reporting/{master_table,inferential,manuscript_data,manuscript_figures,manuscript_tables,__init__}.py` and their tests into git as their own reviewable commit(s), reflecting the real Sprint 1 step boundaries.
- **Files:** `src/finfluencer/reporting/{master_table,inferential,manuscript_data,manuscript_figures,manuscript_tables,__init__}.py`, `tests/unit/test_reporting/{test_master_table,test_inferential,test_manuscript_data,test_manuscript_figures,test_manuscript_tables}.py`.
- **Implementation plan:** Stage and commit in Sprint 1's own original step order (1A → 1B.1 → 1B.2 → 1B.3 → closing exports), one commit per step, matching the granularity already used for prior history (`git log` shows this project already commits at this granularity).
- **Testing strategy:** Re-run the full Sprint 1 suite (97 tests) locally immediately before each commit as a pre-commit sanity check.
- **Regression strategy:** None needed yet — this is the first time this code enters history; regression protection begins with Milestone 2.7.4 (CI).
- **Expected commit message(s):** `feat(reporting): add master_table + inferential (Sprint 1A)`, `feat(reporting): add manuscript_data (Sprint 1B.1)`, `feat(reporting): add manuscript_figures (Sprint 1B.2)`, `feat(reporting): add manuscript_tables (Sprint 1B.3)`, `feat(reporting): close Sprint 1 public exports`.
- **Rollback strategy:** `git revert` per commit; no downstream dependents exist yet at this point in the sequence.

### Milestone 2.7.2 — Commit the Sprint 2 orchestration/CLI/GUI-adapter layer
- **Objective:** Same treatment for `orchestrator.py` → `main.py` → `cli.py` composition → `replication.py` extraction → `job.py`, in their own original step order.
- **Files:** `src/finfluencer/reporting/{orchestrator,main,replication,job}.py`, `src/finfluencer/cli.py`, `tests/unit/test_reporting/{test_orchestrator,test_main,test_replication,test_job}.py`, `tests/unit/test_cli.py`, `pyproject.toml`/`poetry.lock` (the `pymannkendall`/`scikit-posthocs` addition).
- **Implementation plan:** Six commits mirroring Sprint 2.1–2.6 exactly.
- **Testing strategy:** Re-run the full reporting + CLI suite (136 + 21 tests, per this session's own prior verification) before each commit.
- **Regression strategy:** After 2.7.1, verify Sprint 1's own 97 tests are unaffected by each Sprint 2 commit (they should be, since Sprint 2 never modified Sprint 1 files — this is the check that proves that constraint held).
- **Expected commit message(s):** `feat(reporting): add orchestrator engine (Sprint 2.1)`, `feat(reporting): add CLI — analyze/report/validate/export (Sprint 2.3)`, `feat(cli): compose reporting commands onto root app (Sprint 2.4)`, `refactor(reporting): extract replication.py from main.py (Sprint 2.5)`, `feat(reporting): add AnalysisJob GUI adapter (Sprint 2.6)`.
- **Rollback strategy:** `git revert` per commit, in reverse order if multiple need reverting; `job.py`'s commit is safely revertable independent of the others since nothing yet depends on it.

### Milestone 2.7.3 — Repository hygiene pass
- **Objective:** Resolve the ~115 non-`reporting`/non-`cli` untracked root-level files: keep (commit), archive (`.gitignore`'d local directory), or delete, decided file-by-file.
- **Files:** Root-level `.md`/`.csv`/`.json`/`.xlsx`/`.png`/`.py`/`.zip` files currently shown as `??` in `git status`; `tests/unit/test_topics/_pipeline_OLD_*_snapshot.py`.
- **Implementation plan:** Classify into three buckets: (a) genuinely source/config/docs → commit; (b) historical research-analysis exports and review documents with standalone value → move to a new `.gitignore`'d `archive/` or a separate `finfluencer-research-artifacts` location, not `git rm`'d blindly if they have citation/provenance value; (c) pure scratch (build-once scripts already superseded by `reporting/`, zip files, lock files) → delete. Legacy test snapshots move to `tests/legacy/` with a README explaining their purpose.
- **Testing strategy:** Full suite re-run after moves/deletes to confirm nothing in `tests/` silently depended on a root-level script or data file being present at that exact path.
- **Regression strategy:** Do this only after 2.7.1/2.7.2 are committed, so a mistake here can be diffed against a known-good baseline.
- **Expected commit message:** `chore(repo): repository hygiene pass — archive/remove legacy scratch files`.
- **Rollback strategy:** Files moved to `archive/` are trivially recoverable; files deleted are recoverable via `git revert` only if this milestone's own commit is reverted before any subsequent commit — call this out explicitly in the PR description.

### Milestone 2.7.4 — Establish remote and push
- **Objective:** Confirm/create the GitHub remote, push `master` and the milestone branch history, confirm the CI workflow file itself is now tracked.
- **Files:** None (git operations only) — this milestone is explicitly the one where a human, not this agent, performs the `git remote add`/`git push` per this engagement's standing rule that git writes are never executed by the agent.
- **Implementation plan:** User-executed; this document specifies *what* needs to happen, not that the agent performs it.
- **Testing strategy:** Confirm the Actions tab shows a triggered run.
- **Regression strategy:** N/A.
- **Expected commit message:** N/A (no new commit; this is a push of Milestones 2.7.1–2.7.3's commits).
- **Rollback strategy:** N/A.

### Milestone 2.7.5 — Add `ruff check` and `mypy` to CI
- **Objective:** Close TD-5.
- **Files:** `.github/workflows/ci.yml`.
- **Implementation plan:** Add two steps before the test step: `poetry run ruff check .` and `poetry run mypy src`, both hard-failing the job.
- **Testing strategy:** First real run is the test — expect and triage any pre-existing violations surfaced for the first time (see Phase 2 risk note); do not silently loosen the ruff/mypy config to make them pass if genuine issues are found — fix or explicitly, individually suppress with a comment explaining why.
- **Regression strategy:** None applicable (additive CI step); the existing test step is untouched.
- **Expected commit message:** `ci: run ruff and mypy as gating steps`.
- **Rollback strategy:** Revert the workflow-file diff; does not affect any runtime code.

### Milestone 2.7.6 — Add Windows runner and Python-version matrix
- **Objective:** Close TD-6.
- **Files:** `.github/workflows/ci.yml`.
- **Implementation plan:** Add `strategy.matrix` over `os: [ubuntu-latest, windows-latest]` and `python-version: ["3.11", "3.12"]` (staying inside the declared `>=3.11,<3.14` range without immediately chasing the newest, least-battle-tested minor); mark any test class known to be slow/ML-heavy as optionally skippable on the matrix's non-primary legs if total runtime becomes a real constraint (assess after the first run, don't pre-optimize).
- **Testing strategy:** Expect the Windows leg to surface real, previously-manual-only findings (torch DLL ordering is already pinned around per `KNOWN_ISSUES.md`, but this is the first time that pin is actually verified in CI rather than by a human).
- **Regression strategy:** Keep the pre-matrix single-Python/single-OS job as a required check until the matrix job is proven stable, then retire the single-leg job to avoid duplicate signal.
- **Expected commit message:** `ci: add Windows runner and Python version matrix`.
- **Rollback strategy:** Revert to the single-leg job if the matrix proves too flaky/slow to be useful as a hard gate; downgrade to a non-blocking informational job rather than dropping Windows coverage entirely.

### Milestone 2.7.7 — Resolve versioning policy (TD-10)
- **Objective:** Write `docs/RELEASING.md` establishing the two-axis versioning policy (software SemVer vs. research-citation version), and confirm `pyproject.toml` is the only place software version bumps happen going forward.
- **Files:** New `docs/RELEASING.md`; `CONTRIBUTING.md` (cross-reference).
- **Implementation plan:** Document explicitly: `CITATION.cff`'s `1.0.0` stands as the published research-artifact citation version and is not touched by this or future software releases unless the study itself is revised; `pyproject.toml`/git tags follow SemVer starting from the existing `0.1.0`, with `v0.2.0` being the first tag this roadmap produces.
- **Testing strategy:** N/A (documentation-only); success is measured by the absence of ambiguity in a future contributor reading it.
- **Regression strategy:** N/A.
- **Expected commit message:** `docs: establish versioning policy — decouple software SemVer from research-citation version (resolves TD-10)`.
- **Rollback strategy:** Revert the doc; does not touch any version field yet (that happens in Milestone 2.7.18).

### Milestone 2.7.8 — Branch and release-process design
- **Objective:** Formalize branch strategy and the release checklist template referenced throughout this roadmap.
- **Files:** `docs/RELEASING.md` (extends 2.7.7), `CONTRIBUTING.md`.
- **Implementation plan:** Document: feature/milestone branches off `master` (retiring the long-lived `phase2-development` pattern going forward now that Sprint 2 is merging in), PR-based merge to `master`, annotated tags (`vX.Y.Z`) cut only from `master`, release notes generated from `CHANGELOG.md`'s `[Unreleased]` section at tag time.
- **Testing strategy:** N/A.
- **Regression strategy:** N/A.
- **Expected commit message:** `docs: define branch strategy and release checklist template`.
- **Rollback strategy:** Revert the doc.

### Milestone 2.7.9 — Document and test the logging-singleton constraint (interim TD-1 fix)
- **Objective:** Turn the currently-silent `core.logging.configure()` call-once behavior into an explicit, tested contract, and state the constraint in `AnalysisJob`'s docstring.
- **Files:** `src/finfluencer/core/logging.py` (docstring only), `src/finfluencer/reporting/job.py` (docstring only), new `tests/unit/test_core/test_logging.py`.
- **Implementation plan:** No behavior change in this milestone (interim fix only, per Phase 4's risk note) — add the first-ever test file for this module, asserting that a second `configure(log_dir=..., verbose=...)` call with different arguments is a documented no-op; add one paragraph to both docstrings stating "the embedding application must call `configure()` exactly once, before creating any `AnalysisJob`."
- **Testing strategy:** The new test file *is* the testing strategy — this milestone's entire deliverable is closing the "zero tests for `core/logging.py`" gap identified in the Testing Assessment.
- **Regression strategy:** Purely additive; no existing behavior changes.
- **Expected commit message:** `test(core): add logging module tests; document configure() singleton contract (interim TD-1)`.
- **Rollback strategy:** Revert; no functional risk.

### Milestone 2.7.10 — Checkpoint concurrency guard and tests (TD-2)
- **Objective:** Prevent silent races when two `AnalysisJob`s share a `checkpoint_root`.
- **Files:** `src/finfluencer/core/checkpoint.py`, new tests in `tests/unit/test_core/test_checkpoint.py` (extending the existing file) and/or `tests/unit/test_reporting/test_job.py`.
- **Implementation plan:** Add an in-process `threading.Lock` around `CheckpointManager`'s marker read/write path as the minimal fix (cross-process locking via `filelock` is explicitly deferred to Sprint 3 as a larger, separately-justified change — seeMedium-effort call-out in Phase 4).
- **Testing strategy:** A new test that starts two `AnalysisJob`s (or two direct `CheckpointManager.should_run`/`mark_done` sequences) against the same `checkpoint_root` from two threads and asserts no corrupted/partial marker file results.
- **Regression strategy:** Re-run all existing `test_checkpoint.py` and `test_orchestrator.py`/`test_job.py` tests — the lock must be transparent to single-threaded callers (the overwhelming majority of existing tests).
- **Expected commit message:** `fix(core): guard CheckpointManager marker read/write with a lock (TD-2)`.
- **Rollback strategy:** Revert; single-writer behavior returns to its previous (undocumented-race) state, which is why this should not be deferred past `v0.2.0` if concurrent `AnalysisJob` use is being advertised in that release's documentation (Phase 6).

### Milestone 2.7.11 — Resolve `EthicsConfig` enforcement gap (TD-3)
- **Objective:** Execute Phase 5's recommended "mark as reserved" decision for `v0.2.0`.
- **Files:** `src/finfluencer/core/contracts.py` (docstrings), `src/finfluencer/core/exceptions.py` (docstrings), `config/settings.yaml` (comments), `README.md`.
- **Implementation plan:** Add "Reserved, not yet enforced — see Sprint 3 roadmap" to every relevant docstring/comment; no behavior change.
- **Testing strategy:** N/A (documentation-only); optionally add a test asserting `EthicsConfig` still validates correctly (regression guard that the docstring-only change didn't touch the Pydantic model itself).
- **Regression strategy:** Run `test_config.py` to confirm the schema itself is untouched.
- **Expected commit message:** `docs(core): mark EthicsConfig fields as reserved/not-yet-enforced (TD-3)`.
- **Rollback strategy:** Revert; purely documentation.

### Milestone 2.7.12 — README Quick Start for the reporting CLI
- **Objective:** Close the specific README gap identified in TD-4.
- **Files:** `README.md`.
- **Implementation plan:** Mirror the existing `finfluencer run` Quick Start section with a parallel `analyze`/`report`/`validate`/`export` section, including the `--dry-run`/`--force`/`--json` conventions.
- **Testing strategy:** Manually verify every command shown in the new section actually runs as documented against a fresh `poetry install`.
- **Regression strategy:** N/A (documentation-only).
- **Expected commit message:** `docs(readme): document the reporting CLI (analyze/report/validate/export)`.
- **Rollback strategy:** Revert.

### Milestone 2.7.13 — Architecture v1.1 addendum and ADR-Sprint2-01
- **Objective:** Close the remainder of TD-4.
- **Files:** `Software_Product_Architecture_v1.0.md` (extended with a Sprint 2 section, or superseded by a new `Software_Product_Architecture_v1.1.md`), new `ADR-Sprint2-01_AnalysisJob_Hybrid_API.md`.
- **Implementation plan:** Write ADR-Sprint2-01 from this engagement's own chat record (the hybrid-API decision, the alternatives considered, why `AnalysisJob` composes rather than reimplements); add the orchestrator/CLI/job architecture diagram (already drafted in the prior Architecture Review's "Layering" section) to the canonical architecture document.
- **Testing strategy:** N/A.
- **Regression strategy:** N/A.
- **Expected commit message:** `docs(architecture): add Sprint 2 addendum and persist ADR-Sprint2-01`.
- **Rollback strategy:** Revert.

### Milestone 2.7.14 — Developer Guide, User Guide, API Reference, Installation Guide, GUI Integration Guide
- **Objective:** Produce the remaining documentation set.
- **Files:** New `docs/developer-guide.md`, `docs/user-guide.md`, `docs/api-reference.md`, `docs/installation.md`, `docs/gui-integration.md`; `mkdocs.yml` (activating the already-declared-but-unused `mkdocs`/`mkdocs-material` docs group).
- **Implementation plan:** Developer Guide covers contribution workflow, test methodology (the "no mocks, real synthetic data" convention established throughout Sprint 1/2), and the Sprint-based incremental delivery discipline itself (worth documenting as a repeatable practice, not just this engagement's habit). User Guide covers both CLIs end to end. API Reference can be `mkdocs` + `mkdocstrings` auto-generated from the already-thorough docstrings (Sprint 1/2's docstrings are consistently strong enough to support this with minimal extra authoring). GUI Integration Guide is written last, after Phase 4, and documents `AnalysisJob`'s real, hardened contract.
- **Testing strategy:** `mkdocs build --strict` as a CI check (new, optional addition to Phase 2's CI work) catches broken cross-references.
- **Regression strategy:** N/A.
- **Expected commit message:** `docs: add developer/user/API/installation/GUI-integration guides`.
- **Rollback strategy:** Revert; no runtime impact.

### Milestone 2.7.15 — Reporting-only dependency extras split (TD-8)
- **Objective:** Close TD-8.
- **Files:** `pyproject.toml`.
- **Implementation plan:** Introduce a `reporting` extras group covering exactly `reporting/`'s real import set (`pandas`, `pyarrow`, `scipy`, `statsmodels`, `scikit-learn` if actually used by `inferential.py`, `openpyxl`, `matplotlib`, `seaborn` if used, `pymannkendall`, `scikit-posthocs`, plus `core`/`utils` infra deps) with `torch`/`transformers`/`sentence-transformers`/`bertopic`/`prince` excluded; keep the current unqualified `poetry install` behavior as the default (full install), making the lightweight path opt-in via `poetry install --extras reporting --without <collection-only-groups>` or an equivalent documented incantation.
- **Testing strategy:** A new CI job (or a manual, documented verification step if a full second CI job is judged too costly for `v0.2.0`) that installs only the `reporting` extras into a clean venv and runs the `analyze`/`report`/`validate`/`export` test suite against it, confirming `torch` is genuinely absent (`python -c "import torch"` should fail).
- **Regression strategy:** Full default-install test suite must remain 100% green — this milestone must not change default behavior.
- **Expected commit message:** `build: add reporting-only extras group, decoupled from ML/collection dependencies (TD-8)`.
- **Rollback strategy:** Revert `pyproject.toml`; no runtime code affected.

### Milestone 2.7.16 — Extract shared reporting test fixtures (TD-7)
- **Objective:** De-duplicate `_load_cfg_with_tmp_paths`/`_synthetic_reporting_corpus`/`_write_corpus`/`_expected_paths` across `test_orchestrator.py`, `test_main.py`, `test_job.py`.
- **Files:** New `tests/unit/test_reporting/_fixtures.py` (or promoted into `tests/conftest.py` if judged broadly enough useful); `test_orchestrator.py`, `test_main.py`, `test_job.py` (import changes only, no logic changes).
- **Implementation plan:** Move the four helper functions verbatim into the new shared module; replace each file's own copy with an import; re-run the exact same tests to confirm byte-identical behavior (this is a pure refactor, zero logic change).
- **Testing strategy:** The entire reporting test suite (136 tests) must produce identical pass/fail results before and after — this is the regression test.
- **Regression strategy:** Diff the three files before/after to confirm only import statements changed, not assertions.
- **Expected commit message:** `test(reporting): extract shared corpus/config fixtures (TD-7)`.
- **Rollback strategy:** Revert; each file's own inline copy is preserved in git history and can be restored independently if the shared module causes an unexpected coupling issue.

### Milestone 2.7.17 — Add property-based tests using the already-declared `hypothesis` dependency
- **Objective:** Close the Testing Assessment's property-based-testing gap, now known (per the re-verification above) to be cheaper than originally scoped since the dependency already exists.
- **Files:** `tests/unit/test_reporting/test_inferential.py` (extended, not replaced), possibly a new `tests/unit/test_reporting/test_inferential_properties.py`.
- **Implementation plan:** Target the numerical edge cases the Architecture Review specifically called out — all-zero-variance input, single-analyst corpora, extreme class imbalance — as `hypothesis`-generated strategies feeding `run_all_inferential_tests`, asserting it never crashes uncontrollably (raises a typed, documented exception or returns a well-formed result, never an unhandled exception) across the generated input space.
- **Testing strategy:** This milestone *is* new tests; run them repeatedly (hypothesis re-shrinks on failure) to confirm stability before committing the discovered edge cases as permanent regression fixtures.
- **Regression strategy:** N/A (purely additive).
- **Expected commit message:** `test(reporting): add property-based tests for inferential.py edge cases`.
- **Rollback strategy:** Revert; no production code touched.

### Milestone 2.7.18 — Cut `v0.2.0`
- **Objective:** Execute Phase 8.
- **Files:** `pyproject.toml` (`version = "0.2.0"`), `CHANGELOG.md` (new `## [0.2.0]` entry summarizing Sprint 1 + Sprint 2 + Sprint 2.7 for the software package specifically, not conflated with the `1.0.0` research-citation entry already present).
- **Implementation plan:** Execute the Release Checklist below in full; only then bump the version, tag `v0.2.0` (annotated), push the tag, publish GitHub Release notes generated from the CHANGELOG entry.
- **Testing strategy:** Full CI matrix green on the exact commit being tagged (not a later commit) — this is the final gate.
- **Regression strategy:** N/A (this milestone doesn't change runtime behavior, only metadata).
- **Expected commit message:** `release: v0.2.0`.
- **Rollback strategy:** A tag is not force-moved after publication if a problem is found — a `v0.2.1` patch release corrects it instead, per standard SemVer practice; this expectation should be stated in `docs/RELEASING.md` (Milestone 2.7.7/2.7.8).

---

# Risk Matrix

| Severity | Item | Why |
|---|---|---|
| **Critical** | TD-0 — Sprint 1/2 uncommitted, CI never run | Nothing downstream is verifiable by anyone but this session until this is fixed; disqualifying for any release regardless of code quality |
| **High** | TD-1 — logging singleton | Silent, hard-to-diagnose bug in exactly the concurrent-GUI scenario Sprint 2.6 was built for |
| **High** | TD-2 — checkpoint single-writer race | Same category as TD-1; corrupts on-disk state rather than just misrouting logs, so the failure mode is worse |
| **High** | TD-10 (new) — inconsistent versioning | Directly blocks a coherent answer to "what does v0.2.0 mean," which this entire engagement was asked to produce |
| **Medium** | TD-3 — EthicsConfig unenforced | Compliance-adjacent, but resolvable at Tiny effort by being honest about scope in `v0.2.0`; only High if silently shipped as-is with misleading documentation |
| **Medium** | TD-4 — stale docs | Real onboarding/evaluation cost for a *public* release; not a correctness risk |
| **Medium** | TD-5 — CI missing lint/type gates | Cheap to fix, meaningful ongoing quality-gate value once fixed |
| **Medium** | TD-6 — no Windows/matrix CI | This project's own history shows Windows issues are real and non-obvious; medium because the current pin (`torch <2.9.0`) is a working mitigation, not an open bug |
| **Low** | TD-7 — test fixture duplication | Maintenance cost only, no correctness risk |
| **Low** | TD-8 — heavy dependency footprint | Real cost for future GUI packaging, not a `v0.2.0`-blocking correctness issue |
| **Low** | TD-9 — repository hygiene | Cognitive/onboarding cost, no functional risk |

---

# Release Checklist

Everything required before `v0.2.0` is tagged:

- [ ] All Sprint 1/2 code and tests committed to git (Milestones 2.7.1–2.7.2)
- [ ] Repository hygiene pass complete; `git status` clean (Milestone 2.7.3)
- [ ] Remote configured, all branches/tags pushed (Milestone 2.7.4)
- [ ] CI green on `ubuntu-latest` + `windows-latest`, at least two Python versions, including `ruff check` and `mypy` as hard gates (Milestones 2.7.5–2.7.6)
- [ ] `docs/RELEASING.md` published, versioning policy unambiguous (Milestones 2.7.7–2.7.8)
- [ ] Logging-singleton constraint documented and tested (Milestone 2.7.9)
- [ ] Checkpoint concurrency guard implemented and tested (Milestone 2.7.10)
- [ ] `EthicsConfig` fields explicitly marked reserved, or implemented (Milestone 2.7.11)
- [ ] README Quick Start covers both CLIs (Milestone 2.7.12)
- [ ] Architecture v1.1 addendum + ADR-Sprint2-01 committed (Milestone 2.7.13)
- [ ] Developer/User/API/Installation/GUI-integration guides published (Milestone 2.7.14)
- [ ] Reporting-only extras group installs and runs without `torch` (Milestone 2.7.15)
- [ ] Shared reporting test fixtures extracted, full suite still green (Milestone 2.7.16)
- [ ] Property-based tests added for `inferential.py` edge cases (Milestone 2.7.17)
- [ ] Zero regressions across the full suite (Sprint 1's 97 + Sprint 2's 136 + Sprint 2.7's additions) on the exact commit being tagged
- [ ] `pyproject.toml` version bumped to `0.2.0`; `CHANGELOG.md` `[0.2.0]` entry written, correctly scoped (not conflated with the `1.0.0` research-citation entry)
- [ ] Annotated tag `v0.2.0` created and pushed; GitHub Release notes published

---

# Sprint 3 Roadmap

Sprint 3 begins only after Sprint 2.7's checklist is fully green. Focus areas per the user's brief: Desktop GUI, Packaging, User Experience, Plugin architecture, Performance, Web API readiness.

### Sprint 3.1 — Desktop GUI Foundation
- **Deliverable:** A minimal desktop shell (framework decision — e.g., PyQt/PySide vs. a web-view-based approach — is itself the first task) that instantiates `AnalysisJob`, drives it through `start()`/`cancel()`/`join()`, and renders `summary()`'s fields (status, progress, current_stage, timeline) live.
- **Effort:** Large.
- **Risk:** Medium — framework choice has long-tail consequences (packaging story, cross-platform look-and-feel, PyInstaller compatibility); get this decision right before building on top of it.
- **Dependencies:** Sprint 2.7 Phase 4 (concurrency hardening) and Phase 6 (GUI integration guide) must be genuinely done first — building a GUI against an undocumented, unhardened `AnalysisJob` contract would just rediscover TD-1/TD-2 the hard way.

### Sprint 3.2 — Fine-Grained Progress Model
- **Deliverable:** Replace `AnalysisJob`'s coarse stage-count progress with a weighted or sub-stage-aware model (at minimum, weight `manuscript_figures`/`manuscript_tables` higher than `master_table` in the progress fraction, since the Architecture Review identified this exact mismatch).
- **Effort:** Medium.
- **Risk:** Low — purely additive to `AnalysisJob`, orchestrator-internal changes not required if weighting is done at the `job.py` layer using known per-stage output counts.
- **Dependencies:** None beyond Sprint 2.7.

### Sprint 3.3 — Job Registry / Persistence Layer
- **Deliverable:** A `dict[str, AnalysisJob]`-backed (or, if web-service work starts in earnest, a lightweight persisted store) job registry so a job's state survives beyond the lifetime of whoever created it — the concrete gap identified in the Architecture Review's AnalysisJob section.
- **Effort:** Medium.
- **Risk:** Low for the in-memory version; Medium-High if persistence-across-restarts is pulled forward from "future" to "now" — recommend staying in-memory for Sprint 3 and deferring persistence to the web-API work explicitly.
- **Dependencies:** Sprint 3.1 (the GUI is the first real consumer that needs this).

### Sprint 3.4 — PyInstaller Packaging
- **Deliverable:** A working PyInstaller spec producing a signed(-if-applicable), installable Windows build of the GUI from Sprint 3.1, built against the lightweight `reporting` extras from Sprint 2.7 Milestone 2.7.15 wherever the GUI's first release doesn't need the full ML/collection stack.
- **Effort:** Large — PyInstaller + `torch`/`transformers` (if the full-featured GUI variant is targeted) is a genuinely hard packaging problem (hidden imports, native extension bundling, antivirus false-positives on unsigned executables); the lightweight-extras path from Sprint 2.7 directly de-risks this by giving a smaller, simpler first target.
- **Risk:** High if attempting the full ML stack in the first pass; Medium if scoped to the reporting-only build first, ML-stage collection GUI deferred to a later milestone.
- **Dependencies:** Sprint 2.7 Milestone 2.7.15; Sprint 3.1.

### Sprint 3.5 — Plugin Architecture Extension
- **Deliverable:** Extend `core.registry`'s existing entry-point mechanism (already solid, per the Architecture Review) to reporting stages themselves — allow a third party to register a new reporting stage/analysis via entry points rather than editing `orchestrator.py`'s `_STAGE_SPECS` table directly, generalizing the table-driven design Sprint 2.1 already built.
- **Effort:** Medium.
- **Risk:** Medium — needs careful boundary design so third-party stages can't silently violate the checkpoint/manifest contract the built-in five stages honor.
- **Dependencies:** None beyond Sprint 2.7.

### Sprint 3.6 — Performance Baseline and Profiling
- **Deliverable:** The stress/performance test gap identified in the Testing Assessment, closed: benchmark `run_reporting_pipeline`/`AnalysisJob` against a realistically large corpus (the project's own real ~4.8 MB `master_table.csv` scale, not the 4×5–4×40 synthetic fixtures used throughout Sprint 1/2's tests), establish a memory/runtime baseline, and identify the first real optimization target if one exists.
- **Effort:** Medium.
- **Risk:** Low (measurement work); becomes higher-risk only if a real bottleneck is found and needs a redesign to fix — treat that as a separate, later milestone if it happens.
- **Dependencies:** None beyond Sprint 2.7.

### Sprint 3.7 — Web API Readiness Spike
- **Deliverable:** Not a full web service — a scoped spike wrapping the job registry from Sprint 3.3 in a minimal FastAPI (or equivalent) surface (`POST /jobs`, `GET /jobs/{run_id}`) to validate the `AnalysisJob`/asyncio integration path identified as architecturally sound but unverified in the Architecture Review.
- **Effort:** Medium.
- **Risk:** Medium — this is explicitly a spike/validation exercise, not a production web service; scope discipline matters here more than anywhere else in Sprint 3 to avoid quietly becoming a full product pivot mid-sprint.
- **Dependencies:** Sprint 3.3.

---

# Long-term Roadmap

- **v0.3 — "GUI Ships."** Sprint 3's desktop GUI reaches a usable, packaged (PyInstaller), documented state for at least the reporting/analysis workflow (collect-and-process remains CLI-only if the ML-stack packaging problem from Sprint 3.4 isn't fully solved yet — better to ship a smaller, real GUI than delay for a larger one). Plugin architecture (Sprint 3.5) lands. Performance baseline (Sprint 3.6) is established and any found bottlenecks are fixed.
- **v0.4 — "Multi-Study, Multi-Researcher."** The per-researcher settings-overlay gap identified in the Architecture Review is closed — multiple researchers can run independent studies against the same installation without config collisions. The full concurrency hardening deferred from Sprint 2.7 (cross-process checkpoint locking, if still needed given real usage patterns) lands here if Sprint 3's real-world GUI usage shows it's actually needed.
- **v0.5 — "Web API, for real."** Sprint 3.7's spike, if validated, graduates into an actual, documented, authenticated web service with the job registry backed by real persistence — the first version where "possibly a web service" from this review's original framing becomes concretely true rather than architecturally-compatible-but-unbuilt.
- **v1.0 — "Production Research Platform."** All three surfaces (CLI, desktop GUI, web API) are stable, documented, and mutually consistent; the `EthicsConfig` enforcement gap (deferred at Sprint 2.7 as "reserved") is closed for real if a multi-researcher/web-service deployment makes it a genuine requirement rather than a nice-to-have; full CI matrix (OS × Python version × install-extras combination) is green; the versioning policy from Sprint 2.7's `docs/RELEASING.md` has been followed consistently across every `0.x` release with no further drift, which is itself the evidence that the software is mature enough to make and keep a `1.0.0` API-stability promise as a *software* version — independently of `CITATION.cff`'s already-existing `1.0.0` research-citation identity, which this document has deliberately kept decoupled throughout.

---

# Final Recommendation

**Should Release Hardening (Sprint 2.7) begin immediately? YES.**

Every phase in this roadmap is either already-unblocked (Phase 1) or unblocked immediately after its one dependency completes (everything else cascades from Phase 1 within one or two steps). There is no open design question, no unresolved architectural debate, and no missing information blocking the start of Milestone 2.7.1 today. The engineering substance Sprint 1 and Sprint 2 produced is sound; what stands between that work and a real `v0.2.0` is process discipline, not further design — and this repository has already demonstrated, across fourteen prior Sprint steps, that it can execute exactly that kind of small-milestone, test-gated, independently-reviewable discipline reliably. Sprint 2.7 asks for nothing this project hasn't already proven it can do.
