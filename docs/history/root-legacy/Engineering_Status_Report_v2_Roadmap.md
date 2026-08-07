# Finfluencer Research Platform — Engineering Status Report

**Prepared as:** Lead Software Architect review, version-planning basis for v2.0
**Method:** This report is grounded in a direct inspection of the actual repository (`D:\Projects\finfluencer_platform`) conducted for this review — the source tree (`src/finfluencer/`, 55 files, ~8,700 lines), the test suite (24 test files), `pyproject.toml`, `coverage.xml`, `README.md`, and three existing internal design documents (`entity_centric_platform_architecture.md`, `service_oriented_multiplatform_architecture.md`, `basaran_rebuild_orchestration_plan.md`). Nothing below is inferred from the paper alone; every claim about the codebase is traceable to a specific file. Where a claim could not be verified from the code (e.g. exact current test-pass count on this machine), it is stated as such rather than assumed.

---

## PART 1 — CURRENT PLATFORM INVENTORY

The package is organized as ten subpackages under `src/finfluencer/`. One important structural fact up front, because it conditions every maturity rating below: **the statistical analysis that actually produced the submitted manuscript's numbers — mixed-effects models, the message-vs-messenger variance decomposition, the R4–R7 robustness suite, the market Granger analysis orchestration, and every manuscript table/figure builder — does not live inside the installable package.** It lives as roughly 15 standalone scripts in the repository root (`run_inferential_tests.py`, `run_R4.py`…`run_R7.py`, `build_stats_tables.py`, `build_stats_figures.py`, `build_manuscript_data.py`, `build_e5_e6_tables.py`, `build_e7_tables.py` / `build_e7_tables_final.py` / `build_e7_tables_complete.py`, `export_master_table.py`, `pub_data_pull.py`, etc.). This is listed below as its own inventory item ("Shadow Analysis Pipeline") because, functionally, it is the single most consequential piece of software in the project — and architecturally it is the platform's largest liability. Everything else is assessed against that baseline.

### 1.1 Core Infrastructure (`src/finfluencer/core/`)

| Module | Purpose | Inputs | Outputs | Maturity | Dependencies | Reusable | Documented |
|---|---|---|---|---|---|---|---|
| `config.py` (292 lines) | Loads and validates `settings.yaml` + `analysts.yaml` + env overrides into a single typed config object | YAML files, env vars | `LoadedConfig` (Pydantic) | Stable | pydantic, pydantic-settings, pyyaml | Yes | Docstrings only, no external doc |
| `contracts.py` (671 lines) | Pydantic data contracts for videos, comments, sentiment records, topic records, etc. | — | Typed schemas used platform-wide | Stable, but structurally dated | pydantic | Yes, with caveat below | Docstrings only |
| `registry.py` (200 lines) | `(kind, key) → class` plugin registry; supports in-tree `@register()` decorators *and* out-of-tree discovery via Python entry-points (group `finfluencer.providers`) | Registration calls at import time | Provider classes on lookup | Production-ready | stdlib `importlib.metadata` | Yes — this is the platform's best-designed component | Docstrings only |
| `checkpoint.py` (187 lines) | Content-hash-keyed caching so pipeline stages can resume without recomputation | Stage inputs, cache dir | Cached `.npy`/parquet artifacts | Stable | — | Yes | Partial (one platform-specific bug found and fixed post-hoc, see §2) |
| `budgets.py` (267 lines) | Memory-budget enforcement during long-running stages (embeddings/sentiment inference) | Process memory via `psutil` | Raises/warns on budget breach | Stable | psutil (added to fix a POSIX-only `resource` dependency) | Yes | Docstrings only |
| `logging.py` (166 lines) | Structured logging (structlog, key-value fields, not string interpolation) | — | JSON-structured log lines | Stable | structlog | Yes | Docstrings only |
| `reproducibility.py` (264 lines) | Captures exact git commit hash per run; can refuse to proceed on a dirty working tree in strict mode; seed control | git state, config | Run manifest / refusal | Stable — notably rigorous for research software | gitpython | Yes | Docstrings only |
| `exceptions.py` (424 lines) | Custom exception hierarchy across the platform | — | Typed exceptions | Stable | — | Yes | Docstrings only |

**Contracts caveat:** `contracts.py`'s data model bakes in `analyst_key` as an implicit partition key across videos/comments/sentiment/topics. The project's own `entity_centric_platform_architecture.md` (dated within this project, status "Proposal — design only, no implementation") documents a concrete, already-diagnosed correctness consequence of this: 144 videos in the actual corpus are attributed to more than one analyst, so `collect_comments()` — keyed on `(analyst_key, video_id)` — legitimately fetches and stores ~4,750 comments twice, which then propagates into two independently-computed BERTopic fingerprints that silently disagree. This is a known, self-documented bug in the current data model, not a hypothetical one.

### 1.2 Data Collection (`src/finfluencer/collect/`)

| Module | Purpose | Inputs | Outputs | Maturity | Dependencies | Reusable | Documented |
|---|---|---|---|---|---|---|---|
| `channels.py` (176 lines) | Resolves analyst channel handles to YouTube channel IDs/metadata | Config, YouTube Data API v3 | Channel metadata records | Production-ready | `PlatformProvider` protocol | Yes (platform-agnostic interface) | Docstrings only |
| `videos.py` (281 lines) | Enumerates and fetches video metadata per channel, applies the sampling ceiling logic used in the paper (100-video cap, month-stratified) | Channel IDs | Video metadata table | Production-ready | same | Yes | Docstrings only |
| `comments.py` (270 lines) | Fetches top-level comments per selected video, per-commenter cap, hashing at ingest | Video IDs | Comment table | Production-ready — this is the code that built the 17,566-comment corpus | same | Yes | Docstrings only |
| `transcripts.py` (299 lines) | Fetches video transcripts | Video IDs | Transcript text | Present but **not used anywhere in the published manuscript's methods** | same | Unclear — orphaned or reserved-for-future | Docstrings only |
| `quota.py` (100 lines) | YouTube API daily-quota tracking/enforcement | API call log | Remaining-quota gate | Stable | — | Yes | Docstrings only |
| `main.py` (474 lines) | Typer CLI + `run_pipeline()` orchestration across all stages | CLI args or programmatic call | Runs selected pipeline stage(s) | Functionally stable, **packaging broken** (see Part 2) | typer | Yes as a Python function; CLI entry point currently non-functional as installed | Docstrings only |

### 1.3 Preprocessing (`src/finfluencer/preprocess/`)

| Module | Purpose | Inputs | Outputs | Maturity | Dependencies | Reusable | Documented |
|---|---|---|---|---|---|---|---|
| `base.py` / `pipeline.py` (45 + 282 lines) | Orchestrates the cleaning pipeline | Raw comments | Cleaned comment table | Production-ready | — | Yes | Docstrings only |
| `financial_tr.py` (92 lines) | Turkish-specific tokenization, correct İ/I → i/ı casefolding, Turkish stopword removal, Jaccard near-dup filtering | Raw Turkish text | Cleaned tokens | Production-ready — directly underlies the manuscript's Section 3.4 corpus statistics | `providers/language/turkish.py` | Partially — Turkish-specific logic is not reusable for other languages without the parallel `english.py` provider, which exists but is unvalidated in this study | Docstrings only |

### 1.4 Embeddings (`src/finfluencer/embeddings/`)

| Module | Purpose | Inputs | Outputs | Maturity | Dependencies | Reusable | Documented |
|---|---|---|---|---|---|---|---|
| `base.py`, `sentence_transformer.py`, `pipeline.py` (35+84+239 lines) | Multilingual sentence embeddings feeding BERTopic (`paraphrase-multilingual-MiniLM-L12-v2`) | Cleaned comments | Embedding matrix | Stable | sentence-transformers, torch | Yes | Docstrings only |
### 1.5 Sentiment Classification (`src/finfluencer/sentiment/`)

| Module | Purpose | Inputs | Outputs | Maturity | Dependencies | Reusable | Documented |
|---|---|---|---|---|---|---|---|
| `base.py`, `transformer_classifier.py`, `pipeline.py` (33+157+264 lines) | Wraps `savasy/bert-base-turkish-sentiment-cased`, batch inference, pseudo-neutral banding | Cleaned comments | Sentiment probability per comment | Production-ready | transformers, torch | Yes | Docstrings only |

**Gap:** the classifier's own reported validation numbers (accuracy 0.857, MCC 0.719, κ=0.947 against human coders) were computed by root-level scripts, not by any test or module inside `sentiment/`. Re-running the package alone does not reproduce the paper's validation claim — the validation logic itself is not packaged.

### 1.6 Topic Modelling (`src/finfluencer/topics/`)

| Module | Purpose | Inputs | Outputs | Maturity | Dependencies | Reusable | Documented |
|---|---|---|---|---|---|---|---|
| `bertopic_runner.py` (227 lines) | BERTopic wrapper: UMAP + HDBSCAN configuration, c-TF-IDF outlier reduction | Embeddings | Topic assignments | Stable | bertopic, umap-learn, hdbscan | Yes | Docstrings only |
| `pipeline.py` (683 lines — largest file in the package) | Orchestrates topic modelling plus "topic evolution" over time | Embeddings, timestamps | Topic table, evolution table | Stable to run, **known correctness bug** | — | Yes | Docstrings only |

**Known bug (self-documented by the project):** the topic-evolution path is exactly what surfaced the 144-video multi-analyst duplication problem described in §1.1 — `run_topics` and `run_topic_evolution` independently re-join the same duplicated comment rows through different paths and produce two BERTopic fingerprints that disagree. `migration/backfill_entity_model.py` (302 lines) appears to be a partial, in-progress remediation, not a completed fix.

### 1.7 Analysis (`src/finfluencer/analysis/`)

| Module | Purpose | Inputs | Outputs | Maturity | Dependencies | Reusable | Documented |
|---|---|---|---|---|---|---|---|
| `topic_sentiment.py` (191 lines) | Per-topic sentiment aggregation and two-proportion z-tests with FDR correction | Topic + sentiment tables | Per-topic effect sizes | Stable | scipy, statsmodels | Yes | Docstrings only |

This is the *entire* contents of the `analysis/` subpackage. Everything else the paper calls "analysis" — mixed-effects modelling (Table 4), the message-vs-messenger variance decomposition (Table 5), the four-part robustness suite (Table 7 / R4–R7), and the manuscript table/figure generation — is not here. See §1.10.

### 1.8 Market Integration (`src/finfluencer/market/`)

| Module | Purpose | Inputs | Outputs | Maturity | Dependencies | Reusable | Documented |
|---|---|---|---|---|---|---|---|
| `collect_market_data.py` (254 lines) | Fetches BIST100 historical prices | Date range | Price series | Stable | — | Yes | Docstrings only |
| `ingest_manual_bist100.py` (120 lines) | Manual-fallback ingestion path (used per the manuscript's note that Yahoo Finance access was restricted in the analysis environment) | CSV/manual file | Price series | Stable, functions as designed fallback | — | Yes | Docstrings only |
| `sentiment_index.py` (151 lines) | Builds the pooled daily sentiment index | Sentiment table | Daily index series | Stable | pandas | Yes | Docstrings only |
| `confirmatory_analysis.py` (239 lines) + `run_confirmatory_analysis.py` (108 lines) | Stationarity tests, Pearson/Spearman correlation, HAC-OLS, bidirectional Granger causality | Sentiment index, price series | Statistical results | Stable — this is the best-tested, best-abstracted analytical subpackage in the platform | statsmodels, scipy | Yes | Docstrings only |
| `figures.py` (78 lines) | Produces the sentiment-vs-BIST100 figure | Results | PNG/figure | Stable | matplotlib | Yes | Docstrings only |

`market/` is, notably, the one analytical area where the paper's actual statistics *are* packaged and (per `tests/unit/test_market/test_confirmatory_analysis.py`) tested — a useful existence proof that the platform's design supports doing this properly. It shows the rest of the analysis layer's ad-hoc-script pattern was a choice under time pressure, not a technical limitation.

### 1.9 Providers, Migration, Utilities

| Module | Purpose | Maturity | Reusable | Documented |
|---|---|---|---|---|
| `providers/platform/{base,youtube}.py` | `PlatformProvider` protocol + one implementation | Stable, under-populated | Yes — protocol is genuinely platform-agnostic | Docstrings only |
| `providers/language/{base,turkish,english}.py` | Language-specific preprocessing providers | Turkish stable/validated, English present but unvalidated in this study | Yes | Docstrings only |
| `providers/market/{base,yfinance_provider,tcmb_evds_provider}.py` | Two market-data providers behind one protocol | Stable | Yes | Docstrings only |
| `migration/backfill_entity_model.py` (302 lines) | One-off migration script toward the entity-centric data model | In progress, not completed | No (one-off by nature) | Minimal |
| `utils/{dedup,hashing,io,time}.py` (113+368+274+171 lines) | Shared helpers (deduplication, commenter hashing, I/O, date handling) | Stable, proportionally the best-tested subpackage | Yes | Docstrings only |

### 1.10 The Shadow Analysis Pipeline (repository root, NOT part of the package)

Roughly 15 standalone Python scripts sit at the repository root and are what actually produced the manuscript's Tables 2–10 and Figures 1–4: `run_inferential_tests.py`, `run_R4.py`, `run_R5.py`, `run_R6.py`, `run_R7.py`, `build_stats_tables.py`, `build_stats_figures.py`, `build_manuscript_data.py`, `build_e5_e6_tables.py`, `build_e7_tables.py`, `build_e7_tables_final.py`, `build_e7_tables_complete.py`, `export_master_table.py`, `pub_data_pull.py`, `recover_basaran_only.py`, `diagnose_sentiment_memory.py`.

| Purpose | Inputs | Outputs | Maturity | Dependencies | Reusable | Documented |
|---|---|---|---|---|---|---|
| Mixed-effects models, variance decomposition, robustness checks (R4–R7), human-validation tables, manuscript-ready CSV/XLSX exports | `master_table.csv` and siblings | JSON results, CSV/XLSX tables, figures | **Prototype** — functional once, not designed for reuse | statsmodels, scipy, pandas, openpyxl | No — no shared functions, no tests, no CLI, no importable API | Not documented beyond inline comments |

Three near-identical scripts — `build_e7_tables.py`, `build_e7_tables_final.py`, `build_e7_tables_complete.py` — are a visible duplication smell: each is a full copy-edit of the last rather than a parameterized version of one function. This pattern (write a new file rather than edit the old one) is the same one used defensively in this chat session to work around a sandbox file-corruption bug — evidence that the scripts were produced under iterative, deadline-driven conditions rather than designed.
---

## PART 2 — ARCHITECTURE REVIEW

### 2.1 Strengths

- **The provider/registry pattern is genuinely well-designed, not just adequate.** `core/registry.py` implements `(kind, key) → class` lookup with both in-tree decorators and out-of-tree entry-point discovery. `providers/platform/base.py` defines a clean `PlatformProvider` protocol that `collect/channels.py`, `videos.py`, and `comments.py` call exclusively — no direct YouTube API calls leak into business logic anywhere in `collect/`. Adding Reddit or X support is register-a-class-not-invent-a-plugin-system work. This is the platform's best asset and should not be touched in any refactor, only extended.
- **Stage functions are already pure services.** `collect_channels`, `collect_videos`, `collect_comments`, `run_preprocessing`, `run_embeddings`, `run_sentiment`, `run_topics` take typed arguments and return `pd.DataFrame` — no `sys.argv` reads, no `print()`-as-control-flow. They are already callable from a notebook, a future GUI, or a future REST handler with zero adaptation. This is a rare and valuable property for research software and is the main reason a GUI/API layer (Part 3) is additive work, not a rewrite.
- **Reproducibility is treated as a first-class concern, not an afterthought.** `core/reproducibility.py` captures the exact git commit per run and can refuse to proceed on a dirty working tree in strict mode. Root seed 42 is threaded through every stochastic step per the manuscript's Section 3.1. This is above the bar most academic codebases clear.
- **The market subpackage demonstrates the platform's design works when followed through.** It is provider-abstracted (two data sources), fully packaged, and is the one analytical area with real unit tests (`tests/unit/test_market/`). It's the existence proof that the shadow-script pattern elsewhere (§1.10) was a time-pressure choice, not a limitation of the architecture.
- **Two serious internal design documents already exist**, `entity_centric_platform_architecture.md` and `service_oriented_multiplatform_architecture.md`, both explicitly scoped as "design only, no implementation" and both grounded in a real prior audit of this exact codebase rather than written in the abstract. This means a meaningful fraction of the v2.0 roadmap work is already thought through in detail — the risk is discarding this thinking, not lacking it.

### 2.2 Weaknesses, Technical Debt, and Duplicated Logic

- **The shadow analysis pipeline (§1.10) is the platform's single largest architectural liability.** The code that generated the submitted paper's actual numbers is untested, unversioned as reusable software, and not callable from anywhere except "run this exact script by hand in this exact order." If a reviewer requests a re-analysis with a changed specification, there is no clean entry point to do it — someone has to read and hand-edit one of ~15 scripts.
- **Visible duplication:** `build_e7_tables.py` → `build_e7_tables_final.py` → `build_e7_tables_complete.py` is the same logic copy-edited three times rather than parameterized once. This pattern likely recurs elsewhere in the root scripts (not exhaustively verified, but the naming convention across the ~15 files suggests it).
- **A live packaging defect:** `pyproject.toml` declares the console-script entry point as `finfluencer = "finfluencer.cli:app"`, but no `cli.py` exists anywhere in `src/finfluencer/`. The real, working Typer app lives at `finfluencer.collect.main:app`. Anyone who runs `pip install -e .` and then `finfluencer --help`, exactly as a new contributor or reviewer would, gets a `ModuleNotFoundError`. `python -m finfluencer` doesn't help either — `__main__.py` is wired to run `examples/language_demo.py`, not the real pipeline. This is a one-line fix but it is the literal first-impression of the software for anyone who installs it.
- **The contracts/data-model debt is self-diagnosed and unresolved.** The `analyst_key`-as-partition-key design in `contracts.py` causes real, quantified data duplication (144 videos, ~4,750 double-counted comments) that has already produced disagreeing BERTopic fingerprints between two functions computing what should be the same thing. `migration/backfill_entity_model.py` is a partial remediation in progress, not a completed fix.
- **Zero CI/CD.** No `.github/workflows`, no CI configuration of any kind was found. `ruff`, `mypy`, and `pre-commit` are declared dev dependencies in `pyproject.toml` but nothing enforces them running on every change. The two-Windows-test-fix episode documented in `README.txt` (POSIX-only `resource` import breaking on Windows) is exactly the class of bug CI on multiple OSes would have caught before it shipped.
- **Documentation is close to absent.** `README.md` is a single line — the project's name and nothing else. The two rich architecture documents describe a *proposed future* state, not how to install, configure, or run the *current* platform. There is no generated API reference despite `mkdocs`/`mkdocs-material` being declared as a docs dependency group in `pyproject.toml` — the tooling is chosen but never invoked.
- **Test coverage is uneven and, on the last recorded run, moderate.** 24 test files cover roughly 8 of the package's 18 leaf modules by direct correspondence; `coverage.xml` (dated to an earlier run in this project, not re-verified live in this review) reports 48.6% line coverage. The `analysis/`, `migration/`, and — critically — the entire shadow pipeline have no or minimal test coverage.
- **Only two git commits recorded in the repository's history** despite the evident scale of development that produced ~8,700 lines of package code, 236+ passing tests at one point, and a full empirical paper. This means the platform currently has no meaningful commit-level history to review, bisect, or roll back against — version control is present but not really being used as version control.

### 2.3 Component Ratings (1–10)

| Component | Rating | Basis |
|---|---|---|
| `core/registry.py` | 9 | Best-designed component; extensible, already generalizes, praised in the project's own prior audit |
| `core/reproducibility.py` | 8 | Git-hash capture + strict-mode dirty-tree refusal is genuinely rigorous |
| `core/logging.py` | 8 | Structured, consistent, no string-interpolation anti-pattern |
| `core/config.py` | 8 | Pydantic-validated, single-load-then-thread pattern, well-tested |
| `preprocess/` | 8 | Production-validated; Turkish-specific correctness (İ/I casefolding) is a real quality signal |
| `collect/` (channels, videos, comments, quota) | 8 | Production-proven against real quota-constrained API; built the actual corpus |
| `market/` | 8 | Best-abstracted analytical subpackage; provider-based; actually tested |
| `providers/` (design) | 8 | Clean, protocol-based, genuinely platform-agnostic |
| `core/checkpoint.py` | 7 | Works, content-hash based; had a platform-specific bug already found and patched |
| `core/budgets.py` | 7 | Sound intent, memory-only (no CPU/disk/GPU budget), recently patched for portability |
| `core/exceptions.py` | 7 | Thorough; possibly over-built (424 lines) relative to how much of it is exercised |
| `embeddings/` | 7 | Solid standard wrapper, no novel contribution but reliable |
| `sentiment/` | 7 | Production-quality inference; its own validation numbers live outside the package |
| `utils/` | 7 | Proportionally the best-tested subpackage |
| `topics/` | 6 | Central to the paper, but has a known, self-documented correctness bug (duplicate-video counting) |
| `core/contracts.py` | 6 | Comprehensive but structurally dated relative to the entity-centric redesign the project has already proposed |
| `collect/main.py` (CLI) | 5 | Functionally solid Typer app; packaging entry point is broken as installed |
| `migration/` | 5 | Necessary and in progress, but its existence signals an incomplete transition |
| `providers/` (utilization) | 5 | Only 1 of N platform providers populated (YouTube only); protocol is ready, ecosystem isn't |
| `analysis/` | 4 | A stub relative to what "analysis" means for the actual published paper |
| Shadow analysis pipeline | 3 | Functionally critical, architecturally the weakest part of the whole platform |
| Documentation | 2 | README is a title only; no current-state docs; docs tooling declared but unused |
| CI/CD | 1 | Absent |
---

## PART 3 — FEATURE GAP ANALYSIS

Assessed against the goal of a leading open academic platform for computational social science research on financial influencers. Each item states whether it is fully missing, partially present, or already designed-but-unbuilt.

| Capability | Status | Evidence |
|---|---|---|
| GUI | Missing | Not present; `service_oriented_multiplatform_architecture.md` explicitly designs for one ("GUI (future)") without building it |
| Dashboard | Missing | No dashboard code anywhere in the repo |
| Interactive visualization | Missing | `market/figures.py` and the root `build_stats_figures.py` produce static matplotlib PNGs only; no Plotly/Bokeh/D3 output |
| Cross-platform collection (Reddit/X/TikTok/Telegram) | Designed, not built | `PlatformProvider` protocol is platform-agnostic by construction; only `providers/platform/youtube.py` exists |
| Network analysis (commenter graphs, cross-analyst audience overlap) | Missing | No graph/network code found; commenters are hashed per-video only, no cross-video identity linkage is attempted |
| LLM-assisted topic labeling | Missing | Topics are hand-mapped to five categories via keyword matching (per the manuscript's Section 3.5); `openai`/`anthropic` are declared as *optional* dependencies in `pyproject.toml` but no code in `src/` calls either |
| Automatic report generation | Partially present, not packaged | The entire manuscript-table/figure generation exists, but as the unpackaged shadow scripts (§1.10), not as a reusable reporting module |
| Temporal event detection | Missing | Topic evolution exists (`topics/pipeline.py`) but there is no changepoint/event-detection layer on top of it |
| Financial market APIs | Partially present | Two providers exist (`yfinance`, TCMB EVDS) but only for BIST100-level daily data; no order-book, no intraday, no multi-index/multi-asset support |
| Plugin system | Present, under-utilized | This is arguably already solved (`core/registry.py`) — the gap is population, not mechanism |
| Experiment manager | Missing | No experiment-tracking layer (no MLflow/W&B-style run registry); reproducibility is handled at the git-commit level only |
| Model registry | Missing | Model choices (BERTopic config, sentiment classifier checkpoint) are hardcoded in config/YAML, not versioned as registered, swappable model artifacts |
| Database layer | Missing | All data is parquet/CSV on disk; `entity_centric_platform_architecture.md` explicitly proposes a proper relational model (Entity/Video/Comment with many-to-many membership) as the fix for the duplication bug in §1.1/1.6, but it has not been implemented |
| Caching | Partially present | `core/checkpoint.py` provides stage-level content-hash caching; there is no query-level or cross-run artifact cache beyond that |
| Cloud execution | Missing | No cloud-runner abstraction, no batch/job-queue integration |
| Containerization | Missing | No `Dockerfile`, no `docker-compose.yml` anywhere in the repository |
| CI/CD | Missing | Confirmed absent — no `.github/workflows` directory |
| Benchmark suite | Missing | No standardized benchmark for e.g. sentiment classifier accuracy across languages/domains beyond the one-off n=462 validation |
| Replication package generator | Missing | The manuscript's replication materials exist as manually-assembled scripts and CSVs, not as a one-command "generate replication package" tool |
| Version control for data | Missing | No DVC/lakeFS/similar; large data artifacts (`master_table.csv` at ~4.8MB, `master_table_with_category.csv` at ~5.1MB) sit as plain files in the repo working tree |
| Metadata management | Partially present | `core/reproducibility.py` captures run-level git/seed metadata; there is no dataset-level metadata catalog (schema versions, collection dates, provenance per record) |

### 3.1 Reading this table

Two patterns matter more than the individual line items. First, a meaningful share of "missing" capabilities are not blank slates — they are things the project has already designed on paper (`service_oriented_multiplatform_architecture.md` for GUI/API/multi-platform; `entity_centric_platform_architecture.md` for the database/metadata layer) and simply not built yet. Building against those documents is materially cheaper than designing from scratch. Second, the capabilities that touch the shadow analysis pipeline (automatic report generation, replication package generation, experiment management) are gated behind the same root cause: that pipeline has to be pulled into the package and given a real API before any of them can be built cleanly on top of it. Prioritizing that migration (see Part 4, v2.0) unlocks more of this table than any single other piece of work.
---

## PART 4 — DEVELOPMENT ROADMAP

### Version 2.0 — "Make it real software" (consolidation, not expansion)

**Goal:** every number in a published or submitted paper must be reproducible by running packaged, tested, importable code — zero exceptions. This version adds no new research capability; it pays down the debt identified in Parts 1–2 so that v3.0's new features have something solid to stand on.

**New/changed modules:**
- `finfluencer.reporting` — absorb the shadow analysis pipeline (§1.10) into the package: mixed-effects models, variance decomposition, the R4–R7 robustness suite, and manuscript table/figure export become tested, importable functions with a stable API, following the exact pattern `market/confirmatory_analysis.py` already demonstrates.
- Fix the `cli.py` entry-point mismatch in `pyproject.toml` (point it at `finfluencer.collect.main:app`, or add a real `cli.py` that composes collection *and* the new reporting module into one entry point).
- Implement the `Entity`/`Video`/`Comment` relational model from `entity_centric_platform_architecture.md`, closing the 144-video duplication bug at its root rather than patching around it in `migration/`.
- Stand up CI (lint + type-check + full test suite on Linux and Windows, given the Windows-specific bugs already found once) and a minimal `Dockerfile` for reproducible execution.
- Write real documentation: an actual `README.md` (install, configure, run, reproduce-a-result), and stand up the already-declared `mkdocs` site.

**Expected scientific value:** none directly — this is infrastructure. Its value is that it makes the *next* paper's replication package a `git clone && make replicate` away instead of a hand-assembled zip, and it removes the single largest source of quiet correctness risk (duplicated comments) from every future analysis built on this corpus.

**Publication opportunity:** none yet, but this version is the prerequisite for the software paper in Part 6.

### Version 3.0 — "Generalize the platform" (multi-platform, multi-language)

**Goal:** prove the entity-centric, provider-based architecture generalizes beyond "four Turkish YouTube channels" — the explicit long-term framing already present in `entity_centric_platform_architecture.md`'s own title ("domain-agnostic YouTube computational communication research platform").

**New modules:**
- Second and third `PlatformProvider` implementations (Reddit and X/Twitter are the natural choices given existing academic API access patterns), validating that the registry pattern from v1 actually holds under a real second implementation rather than a theoretical one.
- `finfluencer.network` — commenter/cross-analyst network analysis, building on the anonymized-but-consistent commenter hashing already in `utils/hashing.py`.
- LLM-assisted topic labeling as an optional, swappable step (using the already-declared but unused `openai`/`anthropic` extras) — replacing the manual keyword-to-category mapping described in the manuscript's Section 3.5 with a documented, auditable, still-human-verifiable alternative.
- `finfluencer.experiments` — a lightweight experiment/run registry (model version, config hash, data snapshot, results) so that "which BERTopic config produced Table 3" is answered by metadata, not memory.
- A REST API layer over the now-stable service functions, per the layering model already drafted in `service_oriented_multiplatform_architecture.md`.

**Expected scientific value:** enables comparative, cross-platform, cross-language studies of financial influencer communication (e.g. does the message-vs-messenger pattern replicate on Reddit's r/wallstreetbets or on English-language FinTok?) — a substantially larger and more citable research program than a single-platform, single-language study.

**Publication opportunity:** a second empirical paper (cross-platform replication) becomes possible almost for free once the second provider exists, plus the software-paper opportunity in Part 6 gets materially stronger with a demonstrated second platform.

### Version 4.0 — "Open research infrastructure"

**Goal:** move from "a platform one lab uses" to "a platform a field uses" — this is where the GUI/dashboard, containerized cloud execution, and community-facing tooling belong, because they only make sense once v2/v3 have made the underlying pipeline trustworthy and generalizable.

**New modules:**
- A dashboard/GUI (per the "Interface Adapters" layer already designed in `service_oriented_multiplatform_architecture.md`) for non-programmer researchers to configure and run studies.
- Cloud execution + containerized batch runners, so a study over e.g. 50 channels doesn't require a researcher's own machine to stay on for days.
- A benchmark suite (sentiment classifier accuracy, topic model stability) that other groups can run against their own language/domain to certify the platform for their use case — the mechanism that would make this genuinely "one of the best open platforms" rather than "this lab's tool that others could theoretically reuse."
- A replication-package generator: one command that bundles code version, config, data snapshot manifest, and results into a citable, DOI-able archive.
- Formal dataset versioning (DVC or equivalent) once data volumes and multi-platform corpora make plain-file version control genuinely painful.

**Expected scientific value:** positions the platform as shared research infrastructure rather than a single project's output — the difference between one lab publishing with it and a field citing it.

**Publication opportunity:** infrastructure/methods papers aimed explicitly at other researchers adopting the tool (see Part 6), plus the credibility to support a broader claim of "the platform this literature runs on."
---

## PART 5 — MODULE PRIORITIZATION

Each proposed module scored 1 (low) – 5 (high) on Scientific Impact, Novelty, Reusability, Publication Potential, and Return on Investment; Difficulty and Time Required scored 1 (low/fast) – 5 (high/slow) — so for those two columns, *lower is better*. ROI is judged qualitatively against effort, not computed mechanically from the other columns.

| Module | Sci. Impact | Novelty | Reusability | Difficulty | Time Req. | Pub. Potential | ROI |
|---|---|---|---|---|---|---|---|
| Package the shadow analysis pipeline (`reporting`) | 5 | 1 | 5 | 2 | 2 | 2 | **Very High** |
| Fix CLI entry point + basic CI | 2 | 1 | 4 | 1 | 1 | 1 | **Very High** |
| Entity/Video/Comment relational model | 5 | 2 | 5 | 4 | 4 | 2 | **High** |
| Real documentation + mkdocs site | 3 | 1 | 5 | 1 | 2 | 2 | **High** |
| Second `PlatformProvider` (Reddit or X) | 4 | 3 | 5 | 3 | 3 | 4 | **High** |
| Market data expansion (intraday, multi-index) | 3 | 2 | 4 | 3 | 3 | 3 | Medium |
| Network analysis (`finfluencer.network`) | 4 | 4 | 4 | 3 | 3 | 4 | **High** |
| LLM-assisted topic labeling | 3 | 4 | 4 | 2 | 2 | 3 | **High** |
| Experiment/model registry | 3 | 2 | 4 | 3 | 3 | 2 | Medium |
| REST API layer | 2 | 2 | 4 | 3 | 3 | 1 | Medium |
| Containerization (Docker) | 2 | 1 | 5 | 1 | 1 | 1 | **High** |
| Benchmark suite | 4 | 3 | 5 | 3 | 3 | 4 | **High** |
| Replication package generator | 4 | 3 | 5 | 2 | 2 | 3 | **High** |
| GUI / Dashboard | 2 | 2 | 3 | 4 | 5 | 2 | Low (until v4) |
| Cloud execution / batch runners | 2 | 2 | 3 | 4 | 4 | 1 | Low (until scale demands it) |
| Dataset version control (DVC) | 2 | 1 | 4 | 2 | 2 | 1 | Medium |
| Temporal event detection | 3 | 4 | 3 | 3 | 3 | 3 | Medium |

### Reading the matrix

The five "Very High"/top "High" ROI items — package the shadow pipeline, fix the CLI/CI, build the relational data model, write documentation, and add a second platform provider — are not a coincidence: they are exactly the v2.0/early-v3.0 items from Part 4. Low-difficulty, high-reusability items (documentation, CI, containerization) belong first regardless of scientific glamour, because every other module's ROI is discounted by how unreliable the foundation under it currently is. The GUI and cloud-execution items are correctly low priority right now — not because they're unimportant, but because building them on top of an unpackaged shadow analysis pipeline would mean building a nice interface onto something that isn't yet trustworthy enough to expose to end users.
---

## PART 6 — PUBLICATION STRATEGY

The platform itself is publishable, but only after v2.0's consolidation — a software paper describing infrastructure that is 48.6%-tested with an unpackaged core analysis pipeline would draw exactly the same category of criticism this project already knows how to anticipate (see the manuscript's own referee reports produced earlier in this project). Each suggestion below states its realistic prerequisite.

- **Software paper** ("finfluencer: an open, provider-based platform for computational social science research on financial social media"), targeting **SoftwareX** or the **Journal of Open Source Software (JOSS)**. Prerequisite: v2.0 complete (packaged reporting module, real docs, CI, reasonable test coverage) — JOSS in particular has an editorial review process that explicitly checks for installability, documentation, and test coverage, all three of which currently fail.
- **Computational methods paper** ("A message-versus-messenger computational pipeline for social-media investor sentiment: topic modelling, transformer sentiment, and mixed-effects decomposition"), targeting **Journal of Computational Social Science** or **Behavior Research Methods**. This is closer to submittable now, since it can describe the *method* (already implemented, even if partly as scripts) rather than the *software product* — but it's stronger, and more defensible under review, once the shadow pipeline is packaged and the method it describes is literally installable by a reader.
- **Reproducibility / replication paper**, targeting a venue like **Research Synthesis Methods** or a dedicated reproducibility track (e.g. **ReScience C**, or a replication-focused special issue). Prerequisite: the replication-package generator and the fixed entity-relational data model from v2.0/v3.0 — the paper's honest hook would be "here is what we found when we tried to make our own prior study fully reproducible, including the duplication bug we found and fixed," which is a more interesting and citable paper than a generic "we made our code available" note, and is directly grounded in the real bug already documented in `entity_centric_platform_architecture.md`.
- **Digital finance infrastructure paper**, targeting **Borsa Istanbul Review** (a natural fit given the current manuscript is already headed there) or **Journal of Behavioral and Experimental Finance**, framed around the *market* subpackage specifically — provider-abstracted market data ingestion plus confirmatory sentiment-return analysis as a reusable toolkit for behavioral-finance researchers working on emerging markets, where tooling is generally weaker than for US/EU markets. This is close to submittable now, since `market/` is already the platform's most mature analytical subpackage.
- **Communication research methods paper**, targeting **Communication Methods and Measures** or **Computational Communication Research**, framed around the message-versus-messenger decomposition itself as a generalizable *method* for separating content effects from source effects in any social-media corpus with named, recurring communicators — independent of the finance domain. Prerequisite: at least a second, non-financial validation corpus (a natural fallout of the v3.0 cross-platform work), since a method paper claiming generalizability on a single four-channel, single-domain corpus invites the same "n=1 of 4" critique already leveled at the empirical paper's messenger-effect claim.

## PART 7 — FINAL RECOMMENDATION

**If you were the Lead Architect of this project, what would you build next, and why?**

Package the shadow analysis pipeline into `finfluencer.reporting` and fix the CLI entry point — before anything else, including anything on the v3.0/v4.0 list.

Every other gap in this report is either downstream of that one (the replication-package generator, the experiment registry, the software paper, and the reproducibility paper all require it as a precondition) or independent of it but lower-value in comparison (a GUI on top of unreliable analysis code is a nicer way to produce unreliable results faster). The platform's actual research output — the numbers in the submitted manuscript — currently exists in a form that only the person who wrote those ~15 scripts can fully reproduce or extend, on a machine set up exactly the way theirs was. That is the single point of failure for everything this platform is trying to be: a reusable, citable, field-serving piece of research infrastructure rather than one study's disposable scaffolding. It is also, by a wide margin, the cheapest fix on this entire roadmap relative to its impact — the code already exists and works; it needs to be moved, tested, and given a stable API, not invented. Fixing it first is what turns "we have a codebase" into "we have a platform."
