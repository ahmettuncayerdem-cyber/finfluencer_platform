# Finfluencer Research Platform

A reusable computational research platform for empirical studies of financial YouTube communities, retail investor behaviour, and finfluencer discourse. Collects YouTube channel/video/comment data for a configured analyst roster, runs a reproducible NLP pipeline (preprocessing, embeddings, sentiment, topic modelling, topic evolution) over it, and optionally cross-references the results against market data (BIST100/TCMB EVDS).

License: [MIT](LICENSE). See [`CITATION.cff`](CITATION.cff) if you use this platform in academic work.

---

## Requirements

- Python `>=3.11,<3.15`
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
```

## Testing

```bash
poetry run pytest
```

Runs the full suite with coverage (configured in `pyproject.toml`; gate is 75%). A subset of tests requiring `bertopic`/GPU are skipped automatically if those aren't installed in your environment.

## Troubleshooting

**Windows: `MemoryBudget` tests fail with `AttributeError`, or a `checkpoint` test fails on a path-separator mismatch.** `core/budgets.py`'s memory tracking prefers `psutil` (cross-platform) with a fallback to the POSIX-only `resource` module; make sure `psutil` is installed (it's a transitive dependency, but confirm with `poetry show psutil`). Path-comparison tests use `pathlib.Path.parts` rather than string matching specifically to be platform-independent — if you hit a path-related failure, it's worth checking whether a newer test was written with a POSIX-only string assumption.

**`poetry install` fails with a Python-version error.** Check `python --version` — the project requires `>=3.11,<3.15`. Use `poetry env use <path-to-3.11+-interpreter>` if your default `python` doesn't satisfy that.

**`collect` stage fails with an authentication/configuration error.** Check `.env` is populated (see Configuration above) and that `config/settings.yaml`'s placeholder revisions/handles have been resolved if you're running at `replication.stage: publication`.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md).
