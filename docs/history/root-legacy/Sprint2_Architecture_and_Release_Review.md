# Sprint 2 Architecture and Release Review

**Role:** Lead Software Architect, final technical review ahead of Sprint 3 planning.
**Scope:** Full repository as it exists after Sprint 2 (2.1–2.6): `core/`, `collect/`, `reporting/` (including `orchestrator.py`, `main.py`, `replication.py`, `job.py`), `cli.py`, `config/`, `utils/`, `tests/`, documentation, packaging, CI.
**Method:** Direct inspection of source (14,639 lines across `src/`), tests (12,389 lines, 754 collected tests), `pyproject.toml`, `.github/workflows/ci.yml`, `git status`/`git log`, and targeted execution of representative test batches. No files were modified and no code was written to produce this report.
**Assumed future:** research platform → desktop GUI → possibly a web service, multiple researchers.

---

# Executive Summary

| Dimension | Score (0–10) |
|---|---|
| Overall architecture | 7.0 |
| Code quality | 7.5 |
| API design | 7.0 |
| Maintainability | 6.0 |
| Test quality | 7.5 |
| Production readiness | 3.5 |

Sprint 2's own deliverable — `orchestrator.py` → `main.py` → `replication.py` → `job.py` → `cli.py` composition — is genuinely well-engineered: consistent layering, real (non-mocked) tests, honest docstrings that record *why* a decision was made, and disciplined reuse of Sprint 1's pure functions and Architecture v1.0's checkpoint/manifest infrastructure. That part of the codebase would pass a strict internal review on its own merits.

The **production-readiness score is low for reasons almost entirely outside Sprint 2's own code**: the two sprints of work this review covers are not committed to git, the CI workflow that would have validated them has itself never run, a config-declared ethics/retention subsystem is silently unenforced, and two process-wide global-state singletons (`core.logging`, `core.checkpoint`'s single-writer assumption) are latent landmines for the exact multi-job, multi-researcher GUI/service future this review is asked to evaluate against. None of these are hard to fix; all of them are currently unfixed.

**Top strengths**
1. The Sprint 1 → orchestrator → CLI → `AnalysisJob` layering has a clean, consistently-enforced dependency direction (statistics never know about orchestration; orchestration never knows about CLI/GUI) and every layer boundary is enforced by a real test (`"master_table" not in job_module.__dict__`-style architecture-compliance tests), not just a docstring promise.
2. Reproducibility infrastructure (run manifests, checkpoint config-slice hashing, git-state capture) is more rigorous than most research codebases at this stage — every pipeline run leaves an auditable, content-addressed trail.
3. Test discipline is unusually strong for a research codebase: 754 collected tests, real synthetic data instead of mocks throughout Sprint 1/2, and a documented sandbox-timeout-driven batching methodology that never silently skipped a slow test.
4. Exception hierarchy (`core/exceptions.py`) is complete, well-documented, and actually distinguishes recoverable from non-recoverable failure classes — this is the kind of groundwork that pays off once retry/backoff logic gets more sophisticated.

**Top weaknesses**
1. **Sprint 1 and Sprint 2 exist only in the working tree.** `git status` shows the entire `reporting/` package, `job.py`, `test_reporting/`, `test_cli.py`, and `.github/workflows/ci.yml` as untracked; `pyproject.toml`, `poetry.lock`, `cli.py` show as modified-but-uncommitted. The CI pipeline that is supposed to gate this work has literally never executed against it.
2. `core.logging.configure()` is a process-wide, call-once singleton — the very first `AnalysisJob`/CLI invocation in a process wins, permanently, and every subsequent job's `log_dir`/`verbose` request is silently ignored. This is invisible today (one CLI invocation = one process) and becomes a real bug the moment a GUI runs two jobs against two different studies in the same process.
3. `EthicsConfig.retention_days` / `.sensitive_topic_detection` are validated, required schema fields with a matching exception vocabulary (`RetentionPolicyError`, `SensitiveContentError`) referencing a `finfluencer.ethics` package that does not exist. The config *looks* like it enforces a data-governance policy; it enforces nothing.
4. Documentation has not kept pace with code: `Software_Product_Architecture_v1.0.md` (the canonical architecture document) contains zero mentions of `reporting`, `orchestrator`, or `AnalysisJob`; `README.md`'s Quick Start section only documents `finfluencer run`, not `analyze`/`report`/`validate`/`export`. The Sprint 2 architecture proposal and ADR-Sprint2-01 (the actual design rationale for the hybrid `AnalysisJob` API) were delivered in chat only and never written to a file — `ADR-0001` remains the only ADR in the repository.
5. The full dependency set (`torch`, `transformers`, `sentence-transformers`, `bertopic`) is installed unconditionally even though `reporting/` — the package this review centers on — imports none of them. This is a real cost for the stated PyInstaller/desktop-GUI future, not a style preference.

---

# Architecture Review

## Layering and dependency direction

The reporting subsystem's dependency graph is exactly what was designed and is easy to verify because Sprint 2 wrote tests that assert it directly rather than just documenting it:

```
master_table / inferential / manuscript_data / manuscript_figures / manuscript_tables   (Sprint 1, pure functions)
                    ^
                    |  (imported, never modified)
              orchestrator.py   (stage DAG, checkpoint/manifest coordination)
                    ^
        +-----------+-----------+
        |                       |
    reporting/main.py      reporting/job.py   (two independent consumers)
        |                       |
    replication.py          (no CLI/Typer dependency)
        |
      cli.py   (composes collect.main's app + reporting.main's commands)
```

This is a genuinely good shape: `orchestrator.py` has exactly one reason to change (the stage DAG), `main.py` has exactly one reason to change (CLI surface), `job.py` has exactly one reason to change (stateful GUI adapter behaviour), and none of the three know about each other except through the one function (`run_reporting_pipeline`) that all of them call. `job.py`'s own test suite enforces this with `inspect.getsource` assertions rather than trusting the docstring — a good pattern worth generalizing.

**Where the layering is weaker:** `core/logging.py` and `core/checkpoint.py` sit "below" this stack as shared infrastructure, but both carry assumptions (process-wide singleton configuration; single-writer-per-`checkpoint_root`) that were reasonable when the only caller was a single `finfluencer run` CLI invocation and are not reasonable once `AnalysisJob` makes concurrent, same-process, multi-study execution a first-class use case. Sprint 2.6 built a correct *cancellation* and *progress* story for concurrent jobs but did not touch (and was correctly instructed not to touch) the two lower-level singletons that concurrent jobs will actually collide on. See Technical Debt items TD-1 and TD-2.

## Coupling and cohesion

Cohesion inside `reporting/` is high — every module does one thing (one Sprint 1 statistical concern each; one orchestration concern; one CLI concern; one packaging concern; one adapter concern). Coupling *between* `reporting/` and the rest of the platform is appropriately narrow: it depends on `core.config`, `core.checkpoint`, `core.reproducibility`, `core.logging`, `core.exceptions`, `core.contracts`, `utils.io`, `utils.hashing` — all core infrastructure, nothing lateral into `collect/`, `topics/`, `sentiment/`, etc. `cli.py` is the one deliberate coupling point between `collect/` and `reporting/`, and it was built to avoid mutating either module's own file, minimizing blast radius.

Elsewhere in the repository, cohesion is uneven: `market/` mixes CLI scripts, data collection, statistical modelling, and plotting in five same-sized files with `print()`-based output (inconsistent with the structlog convention used everywhere else — see MD-Market below); `topics/pipeline.py` at 834 lines and `core/contracts.py` at 812 lines are both large single files carrying multiple responsibilities (topic modelling has at least four distinct configurations/algorithms in one file; contracts.py is the entire settings schema in one module, which is defensible for a Pydantic schema file but is already the single largest file in the codebase and will keep growing with every new config field).

## Extensibility

The `_StageSpec`/`_STAGE_SPECS` table-driven design in `orchestrator.py` is a strong extensibility pattern: adding a sixth reporting stage means adding one dict entry and one `_execute` function, not touching the generic `_execute_stage()` skip/force/checkpoint/manifest/logging/progress skeleton. The provider registry (`core/registry.py`) similarly supports both in-tree and entry-point-based third-party registration, which is exactly what a "used by multiple researchers" future needs (a researcher can register a custom language/platform/market provider without forking the repo).

The weaker extensibility point is `Settings` (`core/contracts.py`): it is a single monolithic Pydantic model with `extra="forbid"` on every sub-model. This is good for correctness (catches YAML typos) but means every new researcher-specific setting requires a core schema change, a `settings.yaml` update, and — per Sprint 2.2's own conclusion — usually no orchestrator/CLI change, which is fine. The real extensibility gap is that there is no notion of a *per-study* or *per-user* settings overlay: `Settings.study.name` identifies one study, but nothing in the schema or `load_settings()` supports "load researcher A's overrides on top of the shared defaults," which a multi-researcher web service will eventually need (see Sprint 3 recommendations).

## AnalysisJob — GUI readiness in more depth

This deserves separate treatment since it's Sprint 2's newest and most forward-looking component.

**Lifecycle:** clean and correctly one-directional (`pending → running → {success, failed, cancelled}`, enforced by a `RuntimeError` on double-start). This matches the state-machine hygiene a GUI needs to drive a progress bar/status badge without ambiguity.

**Cancellation:** correctly modeled as cooperative and stage-boundary-only, inherited unchanged from the orchestrator's own `cancel_event` contract. This is the right design given Sprint 1's functions are not (and per the roadmap, should not be) individually interruptible — but it does mean a GUI's "Cancel" button has a worst-case latency equal to the *slowest single stage* (in the current corpus sizes, `manuscript_figures`/`manuscript_tables` are the long poles). Nothing wrong with this as a v1 design; it is worth stating explicitly in `AnalysisJob`'s public docs (it currently says "cooperative" but doesn't state the worst-case latency implication for a GUI author who will want to set expectations in their own UI copy).

**Progress model:** `progress` is a coarse fraction of *stages* completed, not *work* completed. For `stage="all"`, `manuscript_figures` (12 output files, several regression fits and volcano-plot computations) and `master_table` (a handful of Parquet joins) both count as "1 stage" toward the denominator — a GUI progress bar built directly on `job.progress` will visibly stall during the expensive stages and jump during the cheap ones. This is a legitimate v1 simplification, not a bug, but it should be flagged now rather than discovered by a future GUI developer who assumes linear progress.

**Async readiness:** the threading-based design is compatible with a future `asyncio`-based web service (an async endpoint can `await loop.run_in_executor(None, job.start, background=False)` or simply poll `job.summary()` after calling `job.start(background=True)`), so this is not a blocking issue for the "possibly a web service" future. What *is* missing is any notion of job identity beyond the in-process object reference — `AnalysisJob.run_id` is a string, but there is no job *registry* (`dict[str, AnalysisJob]`) or any persistence of a job's state beyond the lifetime of the Python object holding it. A web service needs "GET /jobs/{run_id}" to work after the request that created the job has returned; today that requires the *caller* to keep every `AnalysisJob` instance alive and indexed themselves, which is a reasonable Sprint 2 scope boundary but a concrete Sprint 3+ gap.

**One correctness question worth resolving explicitly, not just documenting:** `AnalysisJob` never calls `core.logging.configure()` itself (correctly — that's a CLI/embedding-application concern), but because `configure()` is a global call-once singleton, a GUI that instantiates `AnalysisJob` directly (bypassing `reporting.main`'s CLI, which is the whole point of `AnalysisJob` existing) will get *whatever logging configuration happened to be active first* — possibly the default bare `configure()` triggered by `get_logger()`'s own fallback, going to stderr only, with no `log_dir`. `AnalysisJob`'s docstring should say explicitly "the embedding application is responsible for calling `core.logging.configure()` once, before creating any `AnalysisJob`" — right now this is an implicit requirement discoverable only by reading `core/logging.py`.

---

# Module-by-module Review

### `core/config.py` + `core/contracts.py`
Solid: Pydantic v2, `extra="forbid"` everywhere (catches typos), environment-variable overlay (`FINFLUENCER_SECTION__KEY`) used consistently and correctly by every Sprint 2 test suite. `contracts.py` at 812 lines is the largest file in the repo and will only grow; it has no sub-module split (e.g., collection-config vs. statistics-config vs. output-config), which is fine today but worth watching. No per-researcher settings overlay (see Architecture Review above).

### `core/checkpoint.py`
Well-documented three-tier design; the module's own docstring is unusually honest about its own limitation ("this manager assumes a single writer per `checkpoint_root` at a time... running two `finfluencer run` invocations concurrently... is unsupported and can race"). That honesty is good practice, but the limitation itself is now directly relevant given `AnalysisJob` makes concurrent same-process execution a supported use case for the first time — see TD-1.

### `core/logging.py`
166 lines, well-structured around `structlog`, but **has zero dedicated unit tests** (`find tests -iname "*logging*"` returns nothing). The process-wide `_CONFIGURED` singleton (see Executive Summary) is the single most consequential piece of "old" code that Sprint 2's new concurrent-execution model exposes as a problem. A `_reset_for_testing()` escape hatch exists, confirming the module's own author was aware idempotency could be an issue for tests — but the same idempotency is now a *production* issue for `AnalysisJob`, not just a test-isolation concern.

### `core/exceptions.py`
424 lines, complete and well-organized hierarchy, docstrings explain *why* each distinction exists (e.g., `QuotaExhaustedError` vs `QuotaBudgetExceededError`). Two classes (`RetentionPolicyError`, `SensitiveContentError`) reference an `finfluencer.ethics` package that was never built — see TD-3.

### `core/registry.py`
200 lines, clean plugin architecture (in-tree `@register` + entry-point discovery), correctly used by `providers/` and matches how a "used by multiple researchers" extension model should work. Minor: `discover(kind)` only ever attempts entry-point discovery once per kind per process (`_DISCOVERED_KINDS`) — a plugin installed into the environment *after* a failed first discovery attempt in the same process will never be found without a process restart. Low-severity, plausible in a long-lived GUI/service process.

### `core/reproducibility.py`
344 lines; run-manifest and provenance system is the strongest reproducibility story in the repo — `RunStatus` lifecycle, `generate_run_id()`, `get_git_state()`/`enforce_clean_tree()`, content hashing throughout. `derive_seed` presumably backs deterministic random-seed derivation (not independently re-verified in this pass, but its presence and use from `Settings.study.root_seed` is architecturally correct). Well-tested per the task history (R6 Phase 1 Module 5).

### `core/budgets.py`
267 lines; module-level global (`_MEMORY_TRACKING_WARNED`) for a one-time warning — low risk, but same category of process-global state as `core/logging.py`; worth normalizing during any future concurrency hardening pass.

### `collect/`
`main.py` (561 lines) is the largest single CLI module and does a lot: 9+ stages inline in one `run_pipeline()` function, each with its own `if stage in (...)` block and repeated `if not X.exists(): raise FileNotFoundError(...)` boilerplate. This is the *opposite* of `orchestrator.py`'s table-driven `_StageSpec` design and was written before that pattern existed. It works and is well-tested, but it is now the odd one out architecturally — two different orchestration styles exist in the same repository for structurally similar problems (a linear stage DAG with checkpointing). Not urgent to unify, but worth naming as inconsistency, not two independently-justified designs.

### `reporting/` (Sprint 1 + Sprint 2)
Already covered in depth above. One cross-cutting observation not yet mentioned: `reporting/__init__.py` re-exports 39 public symbols flatly from five modules via `from .module import *`-equivalent explicit imports. This is fine at the current scale but is already large enough that a symbol collision between two future reporting modules (e.g., two modules both wanting to export a `save_summary` function) would be silent until it broke something — no test currently guards against export-name collisions across the five source modules (Sprint 1's own closing step verified the export *set* was complete, not that it was collision-free, because at 39 symbols across 5 modules collisions happened not to occur).

### `cli.py`
62 lines, deliberately thin, correctly preserves the pre-Sprint-2 "one canonical Typer app object" invariant. The one subtlety (documented in the module's own docstring, verified by `tests/unit/test_cli.py`) is that mutating the shared `app` object means any code path that imports `finfluencer.cli` *before* `finfluencer.collect.main` standalone will see the composed 5-command surface even when only collection was intended. This is intentional and tested, but it is import-order-sensitive global state — the same category of risk as the logging singleton, on a smaller scale.

### `utils/`
`hashing.py` (368 lines) and `io.py` (274 lines) are solid, well-tested utility layers. `utils/time.py`'s `truncate_to_day` explicitly implements an ethics/anonymisation requirement ("Methods §3.11") entirely on its own, without any connection to `EthicsConfig.retention_days`/`.sensitive_topic_detection` — i.e., the *one* ethics control that is actually implemented (day-truncation) lives disconnected from the *declared* ethics config surface, reinforcing TD-3's point that the ethics story is fragmented rather than centrally enforced.

### `market/`
Five modules, inconsistent conventions relative to the rest of the platform: `run_confirmatory_analysis.py` and `collect_market_data.py` use `print()` for user-facing output instead of `structlog` (every other CLI-adjacent module in the repo uses structured logging). Test coverage is partial — `market/figures.py`, `market/sentiment_index.py`, and `market/collect_market_data.py` have no dedicated test file (only `confirmatory_analysis`, `ingest_manual_bist100`, and `run_confirmatory_analysis` do). This module was explicitly optional/extras-gated (`poetry install --extras market`) and predates Sprint 1/2, which explains but doesn't excuse the drift.

### `tests/`
754 tests collected, real (non-mocked) methodology throughout Sprint 1/2, disciplined batching to work around sandbox constraints. Two concrete, fixable issues:
1. `tests/unit/test_topics/_pipeline_OLD_3_3_snapshot.py` and `_pipeline_OLD_snapshot.py` are legacy snapshot files sitting in the active test tree with a leading underscore (presumably to exclude them from collection) — dead weight that should either be deleted or moved to a clearly-labeled `tests/legacy/` or `tests/fixtures/` location so their purpose (and non-collection) is structural, not naming-convention-dependent.
2. Every one of `test_orchestrator.py`, `test_main.py`, and `test_job.py` (this session's own three newest files) independently redefines near-identical `_load_cfg_with_tmp_paths` / `_synthetic_reporting_corpus` / `_write_corpus` / `_expected_paths` helpers. This was a deliberate per-file choice at the time (keeping each Sprint step's test file self-contained during incremental review), but three sprints later it is now ~150 lines of duplicated fixture code across the reporting test suite with no single source of truth — a change to the corpus generator's statistical preconditions (e.g., raising `n_per_analyst` requirements) would need to be made in three places and could silently drift.

### Documentation
`KNOWN_ISSUES.md` is a genuine strength — the torch/Windows DLL investigation is rigorous, evidence-tagged (`[Confirmed]`/`[Verified upstream]`), and exactly the kind of record that saves a future engineer from re-discovering the same bug. By contrast, `Software_Product_Architecture_v1.0.md` (the canonical architecture reference) and `README.md` have not been updated for two full sprints of new functionality — see Executive Summary weakness #4. `ADR-0001` is the only architecture decision record in the repository despite this session alone having produced at least one more decision (ADR-Sprint2-01, the `AnalysisJob` hybrid-API decision) that was delivered in chat and never persisted.

### Packaging
`pyproject.toml` is well-organized (37 direct dependencies, clearly commented by category, `[tool.ruff]`/`[tool.mypy]` configured) but the CI workflow only runs `pytest` — **it never runs `ruff check` or `mypy`**, despite both being configured and declared as dev dependencies. Combined with the fact that the CI workflow file itself is untracked (see TD-0), the net effect is that lint/type checks have never gated a single change in this repository's actual history. CI also runs a single Python version (3.11, the floor of the declared `>=3.11,<3.14` range) on `ubuntu-latest` only — no Windows runner, despite the Windows-specific torch/DLL issue being significant enough to warrant its own `KNOWN_ISSUES.md` section and a temporary dependency pin.

---

# Technical Debt

Ordered by priority (severity × how much it blocks Sprint 3 / a real release).

### TD-0 — Sprint 1 and Sprint 2 are not committed to git; CI has never run against them
- **Severity:** Critical
- **Effort:** Tiny (<1 hour) — this is a `git add`/`git commit`/`git push` operation, not an engineering task
- **Risk of not fixing:** Total loss of two sprints of work if the working tree is lost; zero code review trail; zero CI validation of anything claimed "tested and passing" in this and the preceding session; a `v0.2.0` tag cut today would not correspond to any commit
- **Why it matters:** This is the same class of finding the repository's own `RC1_Release_Readiness_Report.md` raised before Sprint 1/2 began ("a large share of that engineering work... is not actually committed to git") — it has recurred, meaning it is a process gap (nobody commits after an engineering session ends), not a one-off oversight
- **Suggested solution:** Commit `reporting/`, `job.py`, `test_reporting/`, `test_cli.py`, `.github/`, and the modified `cli.py`/`pyproject.toml`/`poetry.lock` as a reviewed sequence of commits (Sprint 2's own step-by-step history is a natural commit boundary: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6), push, and confirm CI actually runs and passes on the real GitHub Actions runner — not just in this sandbox
- **Expected benefit:** The rest of this report's findings become independently verifiable by a reviewer other than the person who wrote the code

### TD-1 — `core.logging.configure()` is a process-wide, call-once singleton, incompatible with `AnalysisJob`'s own concurrent-multi-job design goal
- **Severity:** High
- **Effort:** Small
- **Risk of not fixing:** Silent, hard-to-diagnose bug the first time a GUI/service runs two `AnalysisJob`s against different studies (different `log_dir`) in the same process — the second job's logs go to the first job's configured destination, or nowhere
- **Why it matters:** This is precisely the scenario Sprint 2.6 was built to enable ("used by multiple researchers," desktop GUI); the gap is invisible in every test written so far because every test process configures logging at most once
- **Suggested solution:** Either (a) make `configure()` support safe reconfiguration/multiple named loggers scoped per-job (larger change), or (b) as a minimal fix, document the constraint explicitly in `AnalysisJob`'s docstring and `core.logging.configure()`'s own docstring, and add a test that asserts calling `configure()` twice with different `log_dir` values is a documented no-op (turning the silent gap into an explicit, tested contract) as an interim step before (a)
- **Expected benefit:** Removes a class of bug that will otherwise only be found in production, by a GUI user, not in this repository's own test suite

### TD-2 — `CheckpointManager`'s documented single-writer-per-`checkpoint_root` assumption is now directly exercised by concurrent `AnalysisJob` execution
- **Severity:** High
- **Effort:** Medium
- **Risk of not fixing:** Two `AnalysisJob`s targeting the same study concurrently (a plausible GUI action — "run analyze and validate at the same time") can race on `.done`-marker read/write, corrupting checkpoint state or causing a spurious re-run
- **Why it matters:** The risk was correctly documented when written (collection-CLI context, one process at a time by construction) but the precondition ("single writer") is no longer guaranteed once `AnalysisJob` exists specifically to enable concurrent execution within one process
- **Suggested solution:** At minimum, add a `threading.Lock` (or `filelock`-based cross-process lock, if multi-process is also a goal) around `CheckpointManager`'s marker read/write path, or document at the `AnalysisJob` level that two jobs sharing a `checkpoint_root` must not run concurrently and add a runtime guard (e.g., a lock file) that raises a clear error rather than racing silently
- **Expected benefit:** Converts a silent race condition into either a safe serialization or a clear, actionable error

### TD-3 — `EthicsConfig` (retention, sensitive-topic detection) is validated but never enforced
- **Severity:** High (compliance/ethics-adjacent for a platform explicitly built around "ethics-in-design" language throughout its own docstrings)
- **Effort:** Medium
- **Risk of not fixing:** `settings.yaml`'s `ethics.retention_days`/`ethics.sensitive_topic_detection` fields create the impression of an active data-governance policy; researchers configuring them get silent no-ops, not the described self-explanatory-in the settings.yaml comments described behavior
- **Why it matters:** The codebase already implements one real ethics control (`utils.time.truncate_to_day`, explicitly tied to "Methods §3.11") disconnected from this config surface — the pieces exist but were never wired together, and the matching exception classes (`RetentionPolicyError`, `SensitiveContentError`) reference a `finfluencer.ethics` package that was never created
- **Suggested solution:** Either implement the minimal `finfluencer.ethics.retention`/`.sensitive` modules the exception docstrings already promise, wired into the collection/preprocessing pipeline, or — if genuinely out of scope for now — mark the config fields and exceptions as reserved/not-yet-enforced in their own docstrings and in `README.md`'s configuration table, so nobody mistakes declaration for enforcement
- **Expected benefit:** Either real enforcement (preferred) or, at minimum, an accurate representation of what the platform currently guarantees

### TD-4 — Architecture and README documentation is stale relative to Sprint 1/2
- **Severity:** Medium
- **Effort:** Small
- **Risk of not fixing:** A new contributor or researcher reading `Software_Product_Architecture_v1.0.md` or `README.md` today would not learn that `reporting`, `orchestrator`, `AnalysisJob`, or the `analyze`/`report`/`validate`/`export` commands exist at all
- **Why it matters:** Documentation debt compounds — the longer it's stale, the more expensive the eventual catch-up, and the more likely two sources of truth (docs vs. code) silently diverge further
- **Suggested solution:** Add a "Reporting & Analysis" section to `README.md`'s Quick Start (mirroring the existing collection Quick Start), and either extend `Software_Product_Architecture_v1.0.md` with a Sprint 2 addendum section or explicitly supersede it with a v1.1/v2.0 architecture document; persist ADR-Sprint2-01 as a real file alongside `ADR-0001`
- **Expected benefit:** Restores documentation as a reliable onboarding path, and gives ADR-Sprint2-01's design rationale (why `AnalysisJob` is a thin wrapper, not a reimplementation) permanence beyond this chat session

### TD-5 — CI never runs `ruff check` or `mypy` despite both being configured
- **Severity:** Medium
- **Effort:** Tiny (<1 hour)
- **Risk of not fixing:** Lint/type regressions can merge silently; the configuration in `pyproject.toml` currently signals a guarantee ("this code is linted and type-checked") that the pipeline does not actually enforce
- **Why it matters:** Combined with TD-0 (CI has never run at all yet), this is close to zero-cost to fix and immediately raises the bar for every subsequent change
- **Suggested solution:** Add `poetry run ruff check .` and `poetry run mypy src` as CI steps before the test step (fail fast on cheap checks before the expensive test suite runs)
- **Expected benefit:** Automated enforcement of standards that are already defined but currently aspirational

### TD-6 — No CI matrix coverage for Windows or for the full declared Python range
- **Severity:** Medium
- **Effort:** Small
- **Risk of not fixing:** The single most time-consuming debugging thread in this project's recent history (the `torch`/Windows DLL issue, the `pymannkendall`/`scikit-posthocs` packaging gap, the interactive-vs-pytest interpreter mismatch) was *only* caught because a human manually tested on Windows and reported back — none of it would have been caught by the current CI, which only runs Python 3.11 on `ubuntu-latest`
- **Why it matters:** The project's own `KNOWN_ISSUES.md` and this session's own packaging-audit history both demonstrate Windows is a first-class target, not an afterthought — CI does not reflect that
- **Suggested solution:** Add a Windows runner (`windows-latest`) to the CI matrix at minimum for the test suite (full ML-stage tests can be marked slow/optional there if runtime is a concern), and add Python 3.12/3.13 to the matrix to actually exercise the declared `>=3.11,<3.14` range
- **Expected benefit:** Converts manual, ad-hoc Windows verification (as happened multiple times this session) into automated, repeatable coverage

### TD-7 — Reporting test suites duplicate ~150 lines of fixture/corpus-generation code across three files
- **Severity:** Low
- **Effort:** Small
- **Risk of not fixing:** A future change to the synthetic corpus's statistical preconditions (e.g., a new stage requiring a different minimum sample size) must be made in `test_orchestrator.py`, `test_main.py`, and `test_job.py` independently, risking silent drift between them
- **Why it matters:** This is self-inflicted debt from this session's own incremental, single-file-per-step delivery discipline — a reasonable tradeoff at the time (keeping each reviewable step self-contained) that should now be paid down now that all three files exist and are stable
- **Suggested solution:** Extract `_load_cfg_with_tmp_paths`, `_synthetic_reporting_corpus`, `_write_corpus`, `_expected_paths` into a shared `tests/unit/test_reporting/_fixtures.py` (or promote the most-used ones into `tests/conftest.py` as fixtures) and have all three files import from it
- **Expected benefit:** One source of truth for the reporting test corpus; smaller diffs for future reporting test changes

### TD-8 — Heavy ML dependency footprint installed unconditionally despite `reporting/` needing none of it
- **Severity:** Medium (specifically because of the stated PyInstaller/desktop-GUI future)
- **Effort:** Medium
- **Risk of not fixing:** A desktop build that only needs to run `analyze`/`report`/`validate`/`export` against already-collected data still bundles `torch`, `transformers`, `sentence-transformers`, and `bertopic` — multi-gigabyte, slow to build/sign/distribute, and a larger attack surface for DLL/version issues (exactly the class of bug `KNOWN_ISSUES.md` already documents for `torch` on Windows)
- **Why it matters:** This review is explicitly asked to evaluate PyInstaller readiness; dependency footprint is the single largest lever on installer size and build reliability
- **Suggested solution:** Introduce a `reporting`/`analysis`-only extras group (or split into two packages/entry points long-term) so a "reporting workstation" install pulls only `pandas`/`scipy`/`statsmodels`/`openpyxl`/`matplotlib`/`pymannkendall`/`scikit-posthocs` and the `core`/`utils` infrastructure — no `torch` stack at all
- **Expected benefit:** A materially smaller, faster, more reliable installer path for exactly the GUI use case ("regenerate the manuscript tables/figures from data someone else already collected") that is most likely to be a desktop-GUI-first workflow

### TD-9 — Legacy snapshot test files and untracked working-tree clutter
- **Severity:** Low
- **Effort:** Tiny (<1 hour)
- **Risk of not fixing:** `tests/unit/test_topics/_pipeline_OLD_3_3_snapshot.py`/`_pipeline_OLD_snapshot.py` and 121 untracked root-level files (old build scripts, versioned analysis exports, review documents, image assets, two `.zip` archives) make it hard for a new contributor to tell what is live source vs. historical scratch work
- **Why it matters:** Low functional risk, but real cognitive/onboarding cost, and a real risk that an unreviewed `git add -A` sweeps all of it into permanent history
- **Suggested solution:** Move legacy snapshots to a clearly-named `tests/legacy/` (or delete if truly superseded), and do a deliberate pass deciding, file by file, what belongs in git (source, config, docs) vs. what belongs in a `.gitignore`'d `artifacts/` directory vs. what should simply be deleted — this is exactly the exercise `Repository_Hygiene_and_Release_Remediation_Plan.md` already scoped; it appears not to have been executed to completion
- **Expected benefit:** A working tree where `git status` is a meaningful signal again

---

# Testing Assessment

**What's strong:** 754 tests, real synthetic data (no mocks) throughout Sprint 1/2, deliberate differential testing against a reference `.xlsx` workbook (including LibreOffice-resave artifact handling — a genuinely subtle bug class caught and documented), disciplined regression re-verification after every refactor (Sprint 2.4's composition change, Sprint 2.5's extraction both re-ran the full dependent suite rather than assuming safety).

**What's missing:**

1. **No integration/end-to-end test tier separate from unit tests.** `TestFullPipelineHappyPath`-style tests exist but live under `tests/unit/`, sharing a directory (and implicitly, a "fast" expectation) with true unit tests. A dedicated `tests/integration/` tier — explicitly allowed to be slower, explicitly run less frequently in CI (e.g., nightly) — would make the fast/slow split a structural fact instead of a naming convention.
2. **No concurrency/threading tests for `AnalysisJob` beyond the happy path.** `test_job.py` proves background execution *works*, but does not test two `AnalysisJob`s running concurrently against the same or different `checkpoint_root`s — exactly the scenario TD-1/TD-2 identify as a real risk. This is the single most important testing gap relative to where the project says it's headed.
3. **No property-based tests anywhere** (`hypothesis` is not a dependency, not used). The statistical modules (`inferential.py` especially) would benefit from property-based tests for numerical edge cases (all-zero variance, single-analyst corpora, extreme class imbalance) that are easy to under-specify with hand-picked synthetic fixtures.
4. **No performance/stress tests.** Nothing in the suite exercises a realistically large corpus (the project's own real `master_table.csv` in the working tree is ~4.8 MB / tens of thousands of rows; test fixtures use 4×5 to 4×40 synthetic rows). Memory/runtime behavior at real scale is entirely unverified by the test suite.
5. **Zero tests for `core/logging.py`.** Given TD-1's finding, this is not a coverage nitpick — the exact singleton behavior that's now a production risk has no test asserting its current behavior, so a future fix (or accidental regression) has no safety net.
6. **Filesystem robustness is only lightly covered.** Tests cover missing files (`FileNotFoundError` paths) well, but not permission errors, disk-full conditions, or partially-written files from a killed process mid-write (relevant given `CheckpointManager`'s own docstring already flags interleaved-write races as a known gap).
7. **Market module coverage gaps** (`market/figures.py`, `market/sentiment_index.py`, `market/collect_market_data.py` — no dedicated test files).

---

# Release Readiness

## Can Sprint 2 be considered production-ready?

**NO.**

Not because the Sprint 2 engineering is weak — it isn't; the orchestrator/CLI/job design is the strongest part of this review — but because "production-ready" requires more than working code:

1. **It is not in version control.** Nothing that isn't committed can be released, audited, or safely reproduced by anyone other than the person with this exact working directory. This alone is disqualifying regardless of code quality.
2. **CI has never validated it.** Every "97/97 tests pass" or "136/136 tests pass" claim made during this engagement (including by this same reviewer, in this same session's earlier work) was verified in a sandbox, never on the project's actual CI runner, because the CI workflow that would run it is itself uncommitted.
3. **A declared config surface (ethics) is inert**, which is a real problem for a platform whose own documentation repeatedly invokes "ethics-in-design" as a design principle.
4. **The concurrency model `AnalysisJob` was built to enable is not yet safe** against two of the platform's own pre-existing global-state assumptions (logging singleton, checkpoint single-writer).

None of these are large engineering efforts (TD-0 is under an hour; TD-1/TD-2 are Small/Medium; TD-5 is under an hour). They are, however, all *currently unaddressed*, and every one of them is the kind of gap that is invisible until exactly the moment it matters (a lost machine, a merged lint violation, a GUI running two jobs at once, a researcher relying on a retention policy that silently does nothing).

---

# Sprint 3 Recommendations

Ordered highest to lowest priority. Effort estimates: Tiny (<1h), Small (1 session), Medium (2–4 sessions), Large (1+ week), Very Large (multi-week).

1. **Commit and push Sprint 1/2 (TD-0).** Effort: Tiny. Impact: Unblocks everything else — code review, CI validation, and every subsequent recommendation depends on this existing in git history first.
2. **Wire `ruff check` + `mypy` into CI (TD-5), and confirm the CI workflow itself is committed and actually runs on GitHub (part of TD-0's verification).** Effort: Tiny. Impact: Immediate, permanent quality gate at near-zero cost.
3. **Add a Windows runner and Python-version matrix to CI (TD-6).** Effort: Small. Impact: Converts this project's single largest historical source of manual debugging (Windows/torch issues) into automated coverage.
4. **Resolve the `core.logging` singleton / document-and-test the constraint (TD-1).** Effort: Small (interim fix) to Medium (full fix). Impact: Directly de-risks the concurrent-`AnalysisJob` use case Sprint 2.6 exists to enable.
5. **Add a lock (or explicit documented+guarded restriction) around `CheckpointManager`'s single-writer assumption (TD-2), plus a concurrency test for two `AnalysisJob`s sharing a `checkpoint_root` (Testing Assessment #2).** Effort: Medium. Impact: Closes the most concrete correctness gap between the current codebase and its own stated concurrent-execution goal.
6. **Decide and act on `EthicsConfig` (TD-3): implement or explicitly mark as not-yet-enforced.** Effort: Medium (implement) or Tiny (mark as reserved). Impact: Removes a compliance-adjacent gap between what the config promises and what the code does.
7. **Documentation catch-up (TD-4): README Quick Start for reporting commands, architecture doc addendum, persist ADR-Sprint2-01 as a real file.** Effort: Small. Impact: Restores documentation as a trustworthy onboarding path before the gap widens further in Sprint 3.
8. **Introduce a `reporting`-only extras/dependency split (TD-8).** Effort: Medium. Impact: Directly serves the PyInstaller/desktop-GUI future by shrinking the installer path most likely to be built first (a lightweight "regenerate reports" GUI, not a full collection-pipeline GUI).
9. **Extract shared reporting test fixtures (TD-7).** Effort: Small. Impact: Lower ongoing maintenance cost for the test suite this review otherwise rates highly.
10. **Repository hygiene pass: legacy snapshots, untracked working-tree cleanup (TD-9).** Effort: Small. Impact: Restores `git status` as a meaningful signal; low urgency but compounds if deferred again (it already has been once, per `Repository_Hygiene_and_Release_Remediation_Plan.md`).
11. **(Sprint 3+, not blocking) Begin scoping a job registry / persistence layer for `AnalysisJob`** (`dict[str, AnalysisJob]` at minimum, a durable store if a web service is genuinely near-term) and a per-researcher settings-overlay mechanism, both identified in the Architecture Review as gaps for the "multiple researchers" / "web service" future but not urgent for a desktop-GUI-first Sprint 3.

---

# Final Verdict

**Would I approve releasing v0.2.0 today? No.**

Not because of a single defect in the Sprint 2 code — the orchestrator/CLI/replication/AnalysisJob design is genuinely good work and I would approve *that specific code* in a normal PR review with only minor comments. I would not approve a **release** because a release is a claim about what is in version control, validated by CI, and safe to build on, and right now:

- There is no commit that contains this work.
- There is no CI run that has validated this work.
- The platform's own declared ethics-config surface does nothing.
- The concurrency model the release would be advertising (`AnalysisJob`, GUI-ready) is not yet safe against two of the platform's existing global-state assumptions.

**What I would change before releasing, in order:**
1. Commit, push, and get a green CI run — on the real CI, not a sandbox — for everything currently in the working tree (TD-0).
2. Turn on lint/type-check gates and a Windows/multi-version CI matrix before merging anything else (TD-5, TD-6) — cheap, and every day without them increases the chance the next change introduces something these gates would have caught.
3. Fix or explicitly document-and-test the two concurrency landmines (TD-1, TD-2) — not because they're likely to bite in a single-user desktop app tomorrow, but because a release tag is a promise about the *documented* use case (multi-job, GUI-ready), and today that promise is not fully backed by the code.
4. Make a real decision on `EthicsConfig` (TD-3) — implement it or mark it reserved; "declared but silently inert" is the one finding in this report closest to being a trust problem rather than an engineering problem.

Everything else in this report (documentation catch-up, dependency-footprint trimming, test-fixture deduplication, repository hygiene) is real, worth doing, and appropriately sequenced into Sprint 3 — but none of it should block a v0.2.0 tag the way the four items above do.
