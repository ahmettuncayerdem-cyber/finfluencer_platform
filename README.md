# Finfluencer Research Platform

A reusable computational research platform for empirical studies of financial YouTube communities, retail investor behaviour, and finfluencer discourse. Collects YouTube channel/video/comment data for a configured analyst roster, runs a reproducible NLP pipeline (preprocessing, embeddings, sentiment, topic modelling, topic evolution) over it, and optionally cross-references the results against market data (BIST100/TCMB EVDS).

License: [MIT](LICENSE). See [`CITATION.cff`](CITATION.cff) if you use this platform in academic work.

---

## Requirements

- Python `>=3.11,<3.14`
- [Poetry](https://python-poetry.org/) `>=1.5`

## Installation

```bash
git clone <this repository>
cd finfluencer_platform
poetry install
```

This installs the base NLP/collection pipeline. Two optional extras are available:

```bash
poetry install --extras market   # BIST100/TCMB EVDS market-integration analysis
poetry install --extras llm      # reserved for future LLM-assisted coding (not yet wired in)
```

## Configuration

The pipeline is driven by two YAML files (`config/settings.yaml`, `config/analysts.yaml`) and a small number of environment variables. Copy [`.env.example`](.env.example) to `.env` and fill in real values:

| Variable | Required for | Notes |
|---|---|---|
| `ANON_SALT` | comment collection | HMAC salt for hashing commenter identifiers before anything touches disk. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `YT_API_KEY` | channel/video/comment collection | [YouTube Data API v3 key](https://console.cloud.google.com/apis/credentials). |
| `EVDS_API_KEY` | market extra only | [TCMB EVDS](https://evds3.tcmb.gov.tr/) registration. |

`config/settings.yaml` ships with placeholder `REPLACE_WITH_HF_COMMIT_SHA` model revisions and `REPLACE_WITH_VERIFIED_HANDLE` analyst handles by design — these are only enforced (and the pipeline refuses to run with them unresolved) once `replication.stage` is set to `publication`. Earlier stages (`exploratory`, `internal`, `submission`) tolerate them.

## Quick start

```bash
# Validate config and provider construction without hitting any API:
poetry run finfluencer run --dry-run

# Run the full collection + processing pipeline:
poetry run finfluencer run

# Run a single stage (see the CLI's own --help for the full list):
poetry run finfluencer run --stage channels
```

The same commands work via `python -m finfluencer.collect.main run ...` if you're not using the installed console script.

Stages run in dependency order — `channels` → `videos` → `comments`/`transcripts` → `preprocess` → `embeddings`/`sentiment` → `topics` → `topic_sentiment`/`topic_evolution` — and each stage checkpoints its progress under `output.paths.checkpoints` (see `config/settings.yaml`), so an interrupted run resumes rather than restarting from scratch.

## Reporting & analysis

Once the collection/processing pipeline above has produced data, a separate `reporting` CLI turns it into statistics and manuscript-ready output:

```bash
# Statistical computation (master table + inferential tests):
poetry run finfluencer analyze

# Manuscript output (data package, figures, tables):
poetry run finfluencer report

# Non-mutating diagnostics: config validity, package availability, per-stage readiness:
poetry run finfluencer validate

# Package the current report-stage outputs into a timestamped replication snapshot:
poetry run finfluencer export
```

Every command accepts `--settings`/`--analysts` (same config files as `run`), `--dry-run`, `--force`, `--verbose`, and `--json`; `analyze`/`report` additionally accept `--stage <name>` to run a single stage instead of their whole group. `finfluencer <command> --help` lists each command's exact options. These commands are thin CLI wrappers over `finfluencer.reporting.orchestrator.run_reporting_pipeline()`, the single reporting-pipeline engine — a GUI-facing equivalent (`AnalysisJob`) composes over the same engine rather than duplicating it (see [`ADR-Sprint2-01`](ADR-Sprint2-01_AnalysisJob_Composes_Over_Orchestrator.md)).

## Project structure

```
src/finfluencer/
    core/         config, contracts, checkpointing, reproducibility/provenance, logging
    collect/      the four collection stages + CLI entry point
    providers/    pluggable platform (YouTube), language (Turkish/English), and market data backends
    preprocess/   text cleaning pipeline
    embeddings/   embedding generation
    sentiment/    sentiment classification
    topics/       BERTopic-based topic modelling + topic evolution
    market/       BIST100/TCMB EVDS confirmatory analysis (optional extra)
    reporting/    statistics, manuscript export, and the reporting CLI (analyze/report/validate/export)
```

For the full module inventory, dependency graph, and product roadmap, see
[`docs/product/PRODUCT_ARCHITECTURE.md`](docs/product/PRODUCT_ARCHITECTURE.md) (the current
canonical architecture reference; the earlier `Software_Product_Architecture_v1.0.md` this link
used to point to predates the Sprint 0-4/T-029 build and is archived at
[`docs/history/root-legacy/`](docs/history/root-legacy/) for historical reference only).

## Testing

```bash
poetry run pytest
```

Runs the full suite with coverage (configured in `pyproject.toml`; gate is 75%). A subset of tests requiring `bertopic`/GPU are skipped automatically if those aren't installed in your environment.

## Troubleshooting

**Windows: `MemoryBudget` tests fail with `AttributeError`, or a `checkpoint` test fails on a path-separator mismatch.** `core/budgets.py`'s memory tracking prefers `psutil` (cross-platform) with a fallback to the POSIX-only `resource` module; make sure `psutil` is installed (it's a transitive dependency, but confirm with `poetry show psutil`). Path-comparison tests use `pathlib.Path.parts` rather than string matching specifically to be platform-independent — if you hit a path-related failure, it's worth checking whether a newer test was written with a POSIX-only string assumption.

**`poetry install` fails with a Python-version error.** Check `python --version` — the project requires `>=3.11,<3.14`. Use `poetry env use <path-to-3.11+-interpreter>` if your default `python` doesn't satisfy that.

**`collect` stage fails with an authentication/configuration error.** Check `.env` is populated (see Configuration above) and that `config/settings.yaml`'s placeholder revisions/handles have been resolved if you're running at `replication.stage: publication`.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Versioning and releases

This project tracks two independent version numbers (the software package version and a separate research/citation version) — see [`docs/VERSIONING.md`](docs/VERSIONING.md). For the release process itself (branching, tagging, CHANGELOG policy), see [`docs/RELEASING.md`](docs/RELEASING.md).

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md).
