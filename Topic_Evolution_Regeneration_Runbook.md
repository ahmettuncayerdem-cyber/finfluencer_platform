# Topic Evolution Regeneration — Execution Runbook

**Purpose.** `data/processed/topic_evolution.parquet` was corrupted to 0 rows by a pre-existing test bug during Step 3.2 of the entity-centric migration (`tests/unit/test_topics/test_topic_evolution.py::test_empty_topics_is_handled` previously called `run_topic_evolution()` without an explicit `output_path`, silently overwriting the real file). The test bug is fixed. The file has never been regenerated, because `bertopic` is not installed in the sandbox this migration has been executed in, and `run_topic_evolution()` requires a real, loadable BERTopic model. This document is a step-by-step procedure for regenerating it in a real environment. **No code was modified to produce this document; every command below targets the current, unmodified codebase.**

Everything in this plan was verified by direct inspection of the live repository (not assumed): `topics/pipeline.py`, `collect/main.py`, `pyproject.toml`, `config/settings.yaml`, the real `cache/topics_model/` and `checkpoints/` contents, and the real current schema of `data/processed/topics.parquet` and `data/processed/topic_evolution.parquet`.

---

## 1. Preconditions

- **`bertopic` must actually import.** It is already a pinned *core* dependency in `pyproject.toml` (`bertopic = "^0.16"`, line 116) — not an optional extra. The sandbox this migration has run in simply never had it installed; a standard `poetry install` against the existing `pyproject.toml` should already bring it in, along with its transitive `umap-learn`/`hdbscan` dependencies (declared as untyped-stub-only in the `[tool.mypy]` overrides, confirming they're expected to be present at runtime).
- **`config/settings.yaml` must not be modified before running**, specifically:
  - `topics.embedding_model.revision` is currently the literal placeholder string `"REPLACE_WITH_HF_COMMIT_SHA"`. This value feeds `_model_fingerprint()`. If it's "fixed" to a real commit SHA before this run, the computed fingerprint will no longer match the cached model, forcing an expensive full refit instead of a cheap cache read. Leave it exactly as-is for this run.
  - `topics.umap`, `topics.hdbscan`, `topics.merge_similarity_threshold`, `topics.reduce_outliers`, and `study.root_seed` all feed the same fingerprint. None of these may differ from the values used for the original fit.
- **`data/processed/topics.parquet` must be the current, already-verified file** (35,132 rows, `scope_id` fully populated across 5 distinct groups — confirmed in this session). Do not regenerate or re-backfill it as part of this procedure.
- **`data/raw/comments.parquet` and `data/processed/embeddings_index.parquet` must be unchanged** from their current state — they are read-only inputs to this stage.
- **The Tier-3 model cache (`cache/topics_model/`) and all five `checkpoints/topics_*.done` markers must be present and untouched.** Confirmed in this session: `checkpoints/topics_pooled.done`, `checkpoints/topics_within__satiroglu.done`, `checkpoints/topics_within__gecer.done`, `checkpoints/topics_within__basaran.done`, `checkpoints/topics_within__yesilada.done` all exist, and `cache/topics_model/` contains 9 content-addressed hash-bucket directories. This is strong evidence the required models are cached — but not proof; Step 3 below verifies it directly before any real work happens.
- **If running on a different machine than this sandbox**, `checkpoints/`, `cache/`, and `data/` must be copied over exactly as they are — the cache is content-addressed by fingerprint, and any drift in the source files above will change the fingerprint and cause a cache miss.

## 2. Required Environment

- Python matching `pyproject.toml`'s constraint, with the project installed via `poetry install` (or `pip install -e .` against the same lockfile) — this alone should resolve `bertopic`, `umap-learn`, `hdbscan`, `sentence-transformers`, since none of them require special extras.
- Read-write access to the real repository checkout — not a mounted sandbox copy — with `checkpoints/`, `cache/`, and `data/` in place exactly as committed/present.
- No GPU is required. `run_topic_evolution()` never fits UMAP/HDBSCAN or refits BERTopic — it only loads an already-fitted, cached model and calls `topics_over_time()` on it, which is comparatively cheap.

## 3. Required Commands

**Step 3.1 — Environment sanity check (read-only).**
```bash
cd <repo_root>
poetry install
PYTHONPATH=src python -c "import bertopic; print('bertopic', bertopic.__version__)"
PYTHONPATH=src python -m pytest tests/unit/test_topics/test_bertopic_runner.py -v
```
The last command was skipped throughout this entire migration (`could not import 'bertopic'`). In a correct environment it must now run and pass — if it still skips, `bertopic` isn't actually importable and nothing further should proceed.

**Step 3.2 — Backup current state.**
```bash
cp data/processed/topic_evolution.parquet data/processed/topic_evolution.parquet.pre_regen.bak
find checkpoints -name "*.done" -printf "%T@ %s %p\n" | sort > /tmp/checkpoints_before_regen.txt
sha256sum data/processed/topics.parquet data/raw/comments.parquet data/processed/embeddings_index.parquet > /tmp/inputs_sha_before_regen.txt
```

**Step 3.3 — Verify the cached model fingerprint resolves before doing anything else (read-only, cheap).**
```bash
PYTHONPATH=src python - <<'EOF'
from pathlib import Path
from finfluencer.core.config import load_settings
from finfluencer.collect.main import build_checkpoint_manager
from finfluencer.topics.pipeline import _model_fingerprint
from finfluencer.core.reproducibility import derive_seed
import pandas as pd

cfg = load_settings(Path("config/settings.yaml"), Path("config/analysts.yaml"))
checkpoint = build_checkpoint_manager(cfg)
comments = pd.read_parquet("data/raw/comments.parquet")
embeddings = pd.read_parquet("data/processed/embeddings_index.parquet")
topics = pd.read_parquet("data/processed/topics.parquet")
stage_seed = derive_seed(cfg.settings.study.root_seed, "topics")

for config, analyst in [("pooled", None), *[("within_analyst", a) for a in sorted(comments["analyst_key"].unique())]]:
    ids = topics.loc[topics["configuration"] == config, "comment_id"]
    if analyst:
        analyst_ids = set(comments.loc[comments["analyst_key"] == analyst, "comment_id"])
        ids = ids[ids.isin(analyst_ids)]
    fp = _model_fingerprint(
        ids.tolist(), embeddings["model_name"].iloc[0], embeddings["revision"].iloc[0],
        cfg.settings.topics, config, stage_seed,
    )
    print(config, analyst, "cached:" , checkpoint.cache_has("topics_model", fp, ".pkl"))
EOF
```
Every line must print `cached: True`. **If any line prints `False`, stop.** That means the corpus or config has drifted since the original fit, and this becomes a full BERTopic refit — a materially larger, riskier operation not covered by this runbook. Do not proceed to Step 3.4 in that case; escalate instead.

**Step 3.4 — Regenerate the pooled group (writes directly to the real output path).**
```bash
PYTHONPATH=src python -m finfluencer.collect.main run \
    --settings config/settings.yaml --analysts config/analysts.yaml \
    --stage topic_evolution --verbose
```
This is the only CLI-reachable path — `collect/main.py`'s CLI hardcodes `configuration="pooled"` for this stage (within-analyst evolution is explicitly documented as "reachable via the Python API directly," not the CLI). This command overwrites `data/processed/topic_evolution.parquet` with pooled-only rows — expected and fine, since Step 3.2 already backed up the prior (empty) state.

**Step 3.5 — Regenerate the four within-analyst groups (direct Python API, to separate temp files — do NOT point these at the real output path).**

`run_topic_evolution()` calls `write_parquet()`, which fully overwrites its `output_path` — it does not append or upsert. Writing each analyst directly to the real file would destroy every group written before it, including the pooled rows just written in Step 3.4. Each group must be written to its own temporary file and combined in Step 3.6.
```bash
PYTHONPATH=src python - <<'EOF'
from pathlib import Path
from finfluencer.core.config import load_settings
from finfluencer.collect.main import build_checkpoint_manager
from finfluencer.topics.pipeline import run_topic_evolution

cfg = load_settings(Path("config/settings.yaml"), Path("config/analysts.yaml"))
checkpoint = build_checkpoint_manager(cfg)
comments_path = Path("data/raw/comments.parquet")
embeddings_path = Path("data/processed/embeddings_index.parquet")
topics_path = Path("data/processed/topics.parquet")

for analyst in ["satiroglu", "gecer", "basaran", "yesilada"]:
    out = Path(f"/tmp/topic_evolution_{analyst}.parquet")
    df = run_topic_evolution(
        cfg.settings, comments_path, embeddings_path, topics_path, checkpoint,
        configuration="within_analyst", analyst_key=analyst,
        output_path=out,
    )
    print(analyst, "->", out, len(df), "rows")
EOF
```

**Step 3.6 — Combine all five groups into the real output file, once.**
```bash
PYTHONPATH=src python - <<'EOF'
import pandas as pd
from pathlib import Path
from finfluencer.utils.io import write_parquet

pooled = pd.read_parquet("data/processed/topic_evolution.parquet")  # written in Step 3.4
parts = [pooled] + [
    pd.read_parquet(f"/tmp/topic_evolution_{a}.parquet")
    for a in ["satiroglu", "gecer", "basaran", "yesilada"]
]
combined = pd.concat(parts, ignore_index=True)
write_parquet(combined, Path("data/processed/topic_evolution.parquet"))
print("combined rows:", len(combined))
print("by configuration:", combined["configuration"].value_counts().to_dict())
EOF
```

## 4. Expected Outputs

- `data/processed/topic_evolution.parquet` with 5 groups' worth of rows (1 pooled + 4 within-analyst), non-empty. The pre-corruption historical reference was 1,231 rows — expect the same order of magnitude, not necessarily the exact figure (bin count depends on `nr_bins`, which defaults to 10 unless overridden, and on the actual comment timestamp distribution, neither of which has changed).
- **A schema detail to expect, not to mistake for a new bug:** the output will contain a `scope_id` column (it's part of `TopicEvolutionRecord`'s schema, added additively in Step 3.1), but every value in it will be null. Direct inspection of `topics/pipeline.py`'s record-building code (the list comprehension feeding `pd.DataFrame.from_records`) confirms `scope_id` is never actually set on any record — the column exists because `_EVOLUTION_INDEX_COLUMNS` is derived from the full contract, not because the pipeline populates it. This is present, current, unmodified behavior — wiring `scope_id` through to `topic_evolution.parquet`'s own rows would be new work (plausibly bundled with Step 3.4 of the migration, `analysis/topic_sentiment.py`, or a small follow-up), not something this regeneration run does.
- `configuration` will contain both `"pooled"` and `"within_analyst"`; `analyst_key` will be null for pooled rows and one of the four analyst names for within-analyst rows.

## 5. Validation Steps

1. Row count: `len(combined) > 0` and roughly consistent with the ~1,231-row historical baseline (order of magnitude, not exact match required).
2. `combined["configuration"].value_counts()` shows both `"pooled"` and `"within_analyst"` present.
3. `combined.loc[combined["configuration"]=="within_analyst", "analyst_key"].unique()` shows exactly the four expected analysts: `satiroglu`, `gecer`, `basaran`, `yesilada`.
4. `combined["scope_id"].isna().all()` is `True` — confirms the expected (not corrupted) all-null state described in §4, rather than a partially-populated, inconsistent column.
5. `combined["topic_id"].isin(pd.read_parquet("data/processed/topics.parquet")["topic_id"])` — every topic ID appearing in the evolution output should also appear in `topics.parquet`; no orphaned topic IDs.
6. Re-run the two scripts stabilized earlier in this session:
   ```bash
   PYTHONPATH=src python pub_data_pull.py > pub_data.json
   PYTHONPATH=src python final_health_report.py
   ```
   Both must now complete without raising `CorpusValidationError` — this is the direct, end-to-end confirmation that the original blocker is resolved.

## 6. Rollback Strategy

- If Step 3.3's fingerprint check fails for any group: stop before Step 3.4. Nothing has been written yet; no rollback needed.
- If Steps 3.4–3.6 complete but validation (§5) fails: restore the backup taken in Step 3.2:
  ```bash
  cp data/processed/topic_evolution.parquet.pre_regen.bak data/processed/topic_evolution.parquet
  ```
- Confirm no other file was touched by this procedure: re-hash the three read-only inputs and diff against the pre-run snapshot:
  ```bash
  sha256sum data/processed/topics.parquet data/raw/comments.parquet data/processed/embeddings_index.parquet
  diff <(cat /tmp/inputs_sha_before_regen.txt) <(sha256sum data/processed/topics.parquet data/raw/comments.parquet data/processed/embeddings_index.parquet)
  ```
  This must show zero diff — `run_topic_evolution()` never writes to any of these three files by design.
- Confirm checkpoint state is unchanged:
  ```bash
  find checkpoints -name "*.done" -printf "%T@ %s %p\n" | sort > /tmp/checkpoints_after_regen.txt
  diff /tmp/checkpoints_before_regen.txt /tmp/checkpoints_after_regen.txt
  ```
  This must also show zero diff — this stage reads the checkpoint cache, it never writes `.done` markers.

## 7. Post-Run Verification

1. Full test suite, in the real environment:
   ```bash
   PYTHONPATH=src python -m pytest tests/ -q
   ```
   Expect the previously-skipped `test_bertopic_runner.py` test to now run and pass (not skip) — a direct, independent signal the environment precondition in §1 actually held.
2. Both §5.6 scripts (`pub_data_pull.py`, `final_health_report.py`) run to completion and produce non-trivial output — spot-check `pub_data.json`'s `time_bin_min`/`time_bin_max` are real dates, not the string `"nan"` that motivated this whole runbook.
3. §6's rollback-verification diffs (inputs unchanged, checkpoints unchanged) both come back clean — this confirms the regeneration was additive-only to `topic_evolution.parquet` and touched nothing else.
4. Once 1–3 all pass, delete `data/processed/topic_evolution.parquet.pre_regen.bak` and the `/tmp/topic_evolution_*.parquet` intermediate files — they were single-use scaffolding for this procedure.
5. Report back: row count, per-configuration/per-analyst breakdown, and confirmation that both stabilized scripts ran clean. That closes this blocker and clears the way to reassess Step 3.4's priority against a healthy `topic_evolution.parquet`.
