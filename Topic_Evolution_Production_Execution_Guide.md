# Topic Evolution Regeneration — Production Execution Guide

**Role:** Release Engineer, Finfluencer Research Platform
**Status:** Operational verification only. No repository code, configuration, or migration artifact was modified to produce this document. It packages the already-approved `Topic_Evolution_Regeneration_Runbook.md` for direct execution — every command below is that runbook's own command, unmodified. Where this guide adds anything, it is fresh, live-verified evidence gathered in this session (see §2), not a redesign.
**Baseline:** `Release_Readiness_Report.md` (accepted). Its one open finding relevant here — the regeneration is Critical-severity but requires no repository change — is the premise of this document.

---

## 1. Environment Requirements

| Requirement | Value | Source |
|---|---|---|
| Python | `>=3.11,<3.15` | `pyproject.toml` line 73 |
| BERTopic | `^0.16` (resolves `>=0.16.0,<0.17.0`) | `pyproject.toml` line 116 — core dependency, not optional |
| sentence-transformers | `^2.3` | `pyproject.toml` line 115 |
| transformers | `^4.36` | `pyproject.toml` line 114 |
| torch | `^2.2` | `pyproject.toml` line 117 — CPU-only is sufficient; see below |
| numpy / pandas / pyarrow | `^1.26` / `^2.1` / `^15.0` | `pyproject.toml` lines 95–97 |
| scipy / scikit-learn | `^1.11` / `^1.3` | `pyproject.toml` lines 125, 127 |
| umap-learn, hdbscan | Not directly pinned — transitive dependencies of `bertopic`. Whatever version `bertopic ^0.16` resolves. **This is exactly why the missing `poetry.lock` (Release Readiness Report item 5) matters for this specific operation** — without it, two `poetry install` runs on two machines are not guaranteed to resolve the same transitive versions. Not a hard blocker for this run (the cache-fingerprint check in §2 does not depend on umap/hdbscan's exact version, only on `bertopic` being importable), but worth having the same lockfile if at all practical. |
| GPU | **Not required.** `run_topic_evolution()` never fits UMAP/HDBSCAN or refits BERTopic — it loads an already-fitted, cached model and calls `topics_over_time()`, which is cheap. |
| Network access | **Not required**, conditional on §2's cache check passing. If it passes, nothing is downloaded — the embedding model and the fitted BERTopic models are both read from local cache. |
| Installation | `poetry install` (or `pip install -e .` against the same environment) from repo root, so `finfluencer` is importable. Sandbox note: this session's own environment is Python 3.10.12 with `bertopic` not installed — it does not meet the constraint above and cannot run this operation; use only the real target machine. |
| Filesystem | Read-write on the real repository checkout — not a copy. `checkpoints/`, `cache/`, and `data/` must be exactly as committed/present; do not sync a partial subset. |

---

## 2. Go / No-Go Checklist

Every line below was executed live, in this session, against the real repository — not inferred from prior documents.

| # | Check | Result | Command class |
|---|---|---|---|
| 1 | `data/processed/topics.parquet` is the verified, complete source | **GO** — 35,132 rows, `scope_id` 100% populated across 5 groups | `pd.read_parquet` |
| 2 | `data/raw/comments.parquet` unchanged, complete | **GO** — 17,566 rows | `pd.read_parquet` |
| 3 | `data/processed/embeddings_index.parquet` present, resolved revision recorded | **GO** — 17,566 rows; `model_name = sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`; `revision = main` (the resolved fallback for the still-placeholder config value — expected, not an error) | `pd.read_parquet` |
| 4 | All 5 required checkpoint markers present | **GO** — `topics_pooled.done`, `topics_within__{satiroglu,gecer,basaran,yesilada}.done` all present | `ls` |
| 5 | Tier-3 model cache populated | **GO** — 9 content-addressed hash-bucket directories under `cache/topics_model/` | `ls` |
| 6 | **Live fingerprint resolution** — the exact fingerprint `_model_fingerprint()` computes right now from current `topics.parquet`/`embeddings_index.parquet`/`config/settings.yaml` resolves to a real cache hit, for every group | **GO — all 5 groups `cached: True`**, verified by running the runbook's own Step 3.3 script directly (see exact fingerprints and file sizes below) | Live Python execution, this session |
| 7 | Cached model files are real, non-empty artifacts, not placeholders | **GO** — all 5 `.pkl` files exist with substantial sizes (1.2 MB – 106 MB) | `ls -la` |
| 8 | No stale artifact from a prior attempt | **GO** — `topic_evolution.parquet.pre_regen.bak` does not exist | `ls` |
| 9 | `config/settings.yaml` fingerprint-relevant fields unmodified | **GO** — `topics.embedding_model.revision` still the placeholder string (must stay that way, per §1 of the runbook — do not "fix" it before this run); `study.root_seed = 42`; `topics.umap`/`topics.hdbscan`/`topics.merge_similarity_threshold`/`topics.reduce_outliers` all present at their original values | direct file read |
| 10 | `bertopic` importable in the execution environment | **NO-GO in this sandbox** (not installed, and this sandbox is Python 3.10.12, below the `>=3.11` floor) — **this is the only unmet precondition, and it is an environment fact, not a repository defect.** Re-run check 10 on the actual production machine before proceeding past this guide's §3. | `python -c "import bertopic"` |

**Live fingerprint evidence (record these — cross-check against your production machine's own Step 3.3 output before proceeding; they must match exactly, since a mismatch here would mean the corpus or config drifted between this verification and your execution):**

```
pooled            None       fp=f8cfadada5189f2e5c1076a02149a63ea91f807d20bbaf44e1ba10edb45d1ce9   cache/topics_model/f8/…  106,508,414 bytes
within_analyst    basaran    fp=7c2645bbafcd73623bb6b6d0847cf6fa3bb5993a42baa3a7ae8ffdb6a2a4e293   cache/topics_model/7c/…   32,493,141 bytes
within_analyst    gecer      fp=baa67b73c80e48cb0bbaa30688144e414ba33a78515c1bb1010b34265374e2ff  cache/topics_model/ba/…    8,122,651 bytes
within_analyst    satiroglu  fp=972d545986d56de2de802acb5012b98771a7145ef3ebeeb2fcf128f05e3bda32   cache/topics_model/97/…   49,659,561 bytes
within_analyst    yesilada   fp=49be60f09bcc0ecf78e1f7d525d35d6d061c3071c42d1ef142d5eed02bd7331a   cache/topics_model/49/…    1,206,333 bytes
```

**Go/No-Go decision: GO, conditional on check 10 passing on the actual production machine.** Every repository-side precondition (data, checkpoints, cache, config) is independently, freshly verified consistent. The only gate this guide cannot clear from this sandbox is confirming `bertopic` actually imports in the real execution environment — that is Step 3.1 below, and it is the literal first command to run.

---

## 3. Execution Commands

In order. Unmodified from the approved runbook (`Topic_Evolution_Regeneration_Runbook.md` §3), reproduced here for direct execution. The Run Manifest System, already implemented and verified, will operate automatically and needs no separate invocation — `run_pipeline()` writes it as a side effect of Step 3.4 below.

**Step 3.1 — Environment sanity check (read-only). Stop here if this fails.**
```bash
cd <repo_root>
poetry install
PYTHONPATH=src python -c "import bertopic; print('bertopic', bertopic.__version__)"
PYTHONPATH=src python -m pytest tests/unit/test_topics/test_bertopic_runner.py -v
```
If the last command still skips (`could not import 'bertopic'`), stop. Nothing past this point should run.

**Step 3.2 — Backup current state.**
```bash
cp data/processed/topic_evolution.parquet data/processed/topic_evolution.parquet.pre_regen.bak
find checkpoints -name "*.done" -printf "%T@ %s %p\n" | sort > /tmp/checkpoints_before_regen.txt
sha256sum data/processed/topics.parquet data/raw/comments.parquet data/processed/embeddings_index.parquet > /tmp/inputs_sha_before_regen.txt
```

**Step 3.3 — Re-verify the cached model fingerprint on the production machine itself (read-only, cheap). Compare its output against §2's recorded fingerprints above — they must match exactly.**
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
    print(config, analyst, "cached:", checkpoint.cache_has("topics_model", fp, ".pkl"))
EOF
```
Every line must print `cached: True`. **If any line prints `False`, stop.** That means the corpus or config has drifted since this guide was produced — a full BERTopic refit is a materially larger, riskier operation not covered by this guide. Escalate instead of proceeding.

**Step 3.4 — Regenerate the pooled group.**
```bash
PYTHONPATH=src python -m finfluencer.collect.main run \
    --settings config/settings.yaml --analysts config/analysts.yaml \
    --stage topic_evolution --verbose
```
This is the CLI-reachable path — `configuration="pooled"` is hardcoded at this call site. Overwrites `data/processed/topic_evolution.parquet` with pooled-only rows — expected, already backed up in Step 3.2. **As a side effect, this also writes `checkpoints/run_manifests/<run_id>.json`** (`RUNNING` then `SUCCESS`, or `FAILED` with an `error` field if the command errors) — this is the Run Manifest System operating exactly as designed; note the `run_id` it prints/logs for your execution record, but no separate action is needed.

**Step 3.5 — Regenerate the four within-analyst groups (Python API, to temp files — never the real output path directly).**
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
This call goes directly through `run_topic_evolution()`, not `run_pipeline()` — it does **not** produce its own run manifest (only `run_pipeline()`-level invocations do, per Architecture v1.0 §10). This is expected: Step 3.4's manifest already covers this execution window at the pipeline level.

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

---

## 4. Validation Commands

Run all of these after Step 3.6. Every one must pass before declaring success.

```bash
# 1. Row count and shape
PYTHONPATH=src python - <<'EOF'
import pandas as pd
df = pd.read_parquet("data/processed/topic_evolution.parquet")
assert len(df) > 0, "still empty — regeneration did not work"
print("rows:", len(df))
print("by configuration:", df["configuration"].value_counts().to_dict())
print("analysts present:", sorted(df.loc[df["configuration"]=="within_analyst","analyst_key"].dropna().unique()))
assert set(df.loc[df["configuration"]=="within_analyst","analyst_key"].dropna().unique()) == {"satiroglu","gecer","basaran","yesilada"}
assert df["scope_id"].isna().all(), "scope_id should be all-null (ADR-0001 deferral) — non-null here is unexpected, investigate before proceeding"
topics_ids = set(pd.read_parquet("data/processed/topics.parquet")["topic_id"])
orphans = set(df["topic_id"]) - topics_ids
assert not orphans, f"orphaned topic_ids not present in topics.parquet: {orphans}"
print("ALL VALIDATION ASSERTIONS PASSED")
EOF

# 2. Row-count sanity against the pre-corruption historical baseline (order of magnitude, not exact)
#    Historical reference: ~1,231 rows.

# 3. Re-run the two scripts this blocker was stopping
PYTHONPATH=src python pub_data_pull.py > pub_data.json
PYTHONPATH=src python final_health_report.py
# Both must complete without raising CorpusValidationError.
# Spot-check pub_data.json's time_bin_min/time_bin_max are real dates, not "nan".

# 4. Rollback-verification diffs — confirm nothing else was touched
sha256sum data/processed/topics.parquet data/raw/comments.parquet data/processed/embeddings_index.parquet
diff <(cat /tmp/inputs_sha_before_regen.txt) <(sha256sum data/processed/topics.parquet data/raw/comments.parquet data/processed/embeddings_index.parquet)
find checkpoints -name "*.done" -printf "%T@ %s %p\n" | sort > /tmp/checkpoints_after_regen.txt
diff /tmp/checkpoints_before_regen.txt /tmp/checkpoints_after_regen.txt
# Both diffs must be empty.

# 5. Confirm the run manifest was written and reflects a clean SUCCESS
PYTHONPATH=src python - <<'EOF'
import json, glob
files = sorted(glob.glob("checkpoints/run_manifests/*.json"))
assert files, "no run manifest found — Run Manifest System did not fire as expected"
latest = json.load(open(files[-1]))
print("run_id:", latest["run_id"], "status:", latest["status"], "stage:", latest["stage"])
assert latest["status"] == "SUCCESS", f"expected SUCCESS, got {latest['status']}: {latest.get('error')}"
EOF

# 6. Full test suite — the previously-skipped bertopic test must now run and pass, not skip
PYTHONPATH=src python -m pytest tests/ -q
```

---

## 5. Expected Outputs

- `data/processed/topic_evolution.parquet`: non-empty, order-of-magnitude consistent with the ~1,231-row historical baseline. Exact count depends on the real comment-timestamp distribution and `nr_bins` (default 10) — not required to match exactly.
- `configuration` column contains both `"pooled"` and `"within_analyst"`; `analyst_key` is null for pooled rows, one of `satiroglu`/`gecer`/`basaran`/`yesilada` for within-analyst rows.
- `scope_id` column present, **all values null** — this is expected, current, unmodified behavior (`topics/pipeline.py`'s record-building code never sets it; ADR-0001 documents this as an intentional, zero-consumer deferral). A partially-populated `scope_id` column would indicate something unexpected and should be investigated before trusting the output, not treated as an improvement.
- `checkpoints/run_manifests/<run_id>.json`: one new manifest, `status: "SUCCESS"`, `stage: "topic_evolution"`, containing config hashes, environment snapshot, git state, and (via `checkpoint=`) every current `.done` marker's `config_slice_sha256`.
- `pub_data.json` and the health report now contain real, non-placeholder `time_bin_min`/`time_bin_max` values — the direct, end-to-end proof the original blocker is closed.
- No change whatsoever to `topics.parquet`, `comments.parquet`, `embeddings_index.parquet`, or any `.done` marker — `run_topic_evolution()` only reads these by design.

---

## 6. Rollback Procedure

- **If Step 3.3's fingerprint re-check fails for any group:** stop before Step 3.4. Nothing has been written yet; no rollback action is needed.
- **If Steps 3.4–3.6 complete but §4's validation fails:**
  ```bash
  cp data/processed/topic_evolution.parquet.pre_regen.bak data/processed/topic_evolution.parquet
  ```
- **If Step 3.4 itself raises an exception:** the Run Manifest System will already have written a `FAILED` manifest with `error.type`/`error.message` before the exception propagates — read that manifest first (`checkpoints/run_manifests/<run_id>.json`) for the exact failure cause before deciding whether to retry or escalate. `topic_evolution.parquet` itself is untouched in this case (the backup in Step 3.2 is a precaution, not a requirement, for this specific failure mode — `write_parquet()` only replaces the file on a completed write).
- **Always confirm, regardless of outcome:** the two diff checks in §4 item 4 (input file hashes, checkpoint marker timestamps) come back empty. A non-empty diff on either means something touched a file this procedure should never touch — treat that as a separate incident, not a normal rollback case.
- **Cleanup, only after §4 fully passes:** delete `data/processed/topic_evolution.parquet.pre_regen.bak` and the five `/tmp/topic_evolution_*.parquet`/`/tmp/checkpoints_*.txt`/`/tmp/inputs_sha_before_regen.txt` scaffolding files. Do not delete them before validation passes.

---

## 7. Final Release Decision

**GO — execute on the production machine, starting at §3 Step 3.1.**

Every repository-side precondition is freshly, independently verified in this session: source data (35,132/17,566/17,566-row inputs), all 5 checkpoint markers, all 5 cache artifacts (confirmed by live fingerprint resolution, not just file presence, plus non-trivial file sizes), unmodified fingerprint-relevant config, and a clean absence of stale prior-attempt artifacts. The Run Manifest System is already implemented, tested, and will operate automatically during Step 3.4 with no separate action required.

The only unresolved item is environment-external, not repository-internal: confirming `bertopic` actually imports on the real production machine (§3 Step 3.1, §2 check 10) — this guide cannot verify that from this sandbox, and Step 3.1 is deliberately the first command specifically so that this is confirmed, cheaply and safely, before anything is written.
