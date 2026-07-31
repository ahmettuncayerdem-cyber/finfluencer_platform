# Production Validation Checklist — Topic Evolution Regeneration

**Role:** Release Manager, Finfluencer Research Platform
**Purpose:** Execute on the real, BERTopic-enabled production machine. Packages `Topic_Evolution_Production_Execution_Guide.md` into a strict PASS/FAIL checklist with evidence-collection requirements, so results feed directly into `Version_1.0_Release_Checklist.md`.
**Type:** Operational execution only. No source code, configuration, or migration artifact should be modified while running this checklist. If any step requires a code change to pass, stop and escalate — do not fix it inline and continue.

---

## 0. Pre-flight

| # | Action | Command | PASS criteria |
|---|---|---|---|
| 0.1 | Checkout the exact repository state validated in the Production Execution Guide | `git status`, `git log -1` | Working tree matches the state this checklist was issued against; no unexplained local changes beyond the known-dirty baseline already documented in the Release Readiness Report |
| 0.2 | Confirm Python version | `python --version` | `>=3.11,<3.15` |
| 0.3 | Install dependencies | `poetry install` (repo root) | Exits 0, no dependency resolution errors |
| 0.4 | Confirm `bertopic` importable | `PYTHONPATH=src python -c "import bertopic; print(bertopic.__version__)"` | Prints a version string in the `0.16.x` line, no `ModuleNotFoundError` |
| 0.5 | Confirm `finfluencer` importable | `PYTHONPATH=src python -c "import finfluencer; print('ok')"` | Prints `ok` |

**FAIL at any of 0.1–0.5 → stop.** Do not proceed to §1. This is the same gate the Execution Guide's Step 3.1 already specifies; §0 here only adds the checkout/version checks around it.

---

## 1. Execution — step-by-step, referencing the Execution Guide

| # | Guide step | Command class | Expected output | PASS criteria |
|---|---|---|---|---|
| 1.1 | Guide §3 Step 3.1 | `pytest tests/unit/test_topics/test_bertopic_runner.py -v` | Test(s) **run and pass**, not skip | Exit 0; zero `SKIPPED` in output |
| 1.2 | Guide §3 Step 3.2 | Backup + hash snapshot commands | `topic_evolution.parquet.pre_regen.bak` created; `/tmp/checkpoints_before_regen.txt` and `/tmp/inputs_sha_before_regen.txt` populated | Both files non-empty; backup file size matches the pre-run `topic_evolution.parquet` (0 rows is fine — it's a backup of the empty state, not a defect) |
| 1.3 | Guide §3 Step 3.3 | Fingerprint re-verification script | 5 lines, each `cached: True` | **All 5 must read `True`.** Compare each fingerprint hash against the recorded values in the Execution Guide §2 — they must match exactly, not just all say `True` independently |
| 1.4 | Guide §3 Step 3.4 | `run --stage topic_evolution --verbose` | Structured log lines including `stage_start`, `stage_done`, `pipeline_complete`; a new file under `checkpoints/run_manifests/` | Exit 0; `topic_evolution.parquet` row count > 0 immediately after; a `run_manifests/<run_id>.json` file exists with `status: "SUCCESS"` |
| 1.5 | Guide §3 Step 3.5 | Within-analyst regeneration script | Four lines printed, one per analyst, each with a row count > 0 | All four `/tmp/topic_evolution_<analyst>.parquet` files exist and are non-empty |
| 1.6 | Guide §3 Step 3.6 | Combine script | `combined rows: <N>`, `by configuration: {...}` printed | `N > 0`; both `"pooled"` and `"within_analyst"` present in the printed breakdown |

**FAIL at 1.3 → stop before 1.4, no rollback needed (nothing written yet).**
**FAIL at 1.4, 1.5, or 1.6 → proceed to §4 Rollback below before doing anything else.**

---

## 2. Validation — PASS/FAIL criteria for every check

Run every command in Execution Guide §4. Record results against these explicit criteria (the Guide's own inline `assert` statements already encode most of these — this table exists so a human reviewer can confirm each one without re-reading the script):

| # | Validation | PASS criteria | FAIL criteria |
|---|---|---|---|
| 2.1 | Row count | `len(topic_evolution.parquet) > 0` | 0 rows (regeneration silently did nothing) |
| 2.2 | Order-of-magnitude sanity | Row count in the same order of magnitude as the ~1,231-row historical baseline | Off by more than roughly 1 order of magnitude in either direction (investigate before treating as PASS even if technically `> 0`) |
| 2.3 | Configuration coverage | Both `"pooled"` and `"within_analyst"` present in `configuration` value counts | Either missing |
| 2.4 | Analyst coverage | `analyst_key` for within-analyst rows is exactly `{satiroglu, gecer, basaran, yesilada}` | Any analyst missing, or an unexpected analyst present |
| 2.5 | `scope_id` all-null | `scope_id.isna().all() == True` | Any non-null value (unexpected — per ADR-0001 this field is never populated by this stage; a non-null value means something changed that this checklist doesn't account for — escalate, don't treat as an improvement) |
| 2.6 | No orphaned `topic_id` | Every `topic_id` in `topic_evolution.parquet` also appears in `topics.parquet` | Any `topic_id` absent from `topics.parquet` |
| 2.7 | Input files untouched | `sha256sum` diff against the Step 3.2 snapshot is empty, for all three of `topics.parquet`/`comments.parquet`/`embeddings_index.parquet` | Any non-empty diff |
| 2.8 | Checkpoint markers untouched | `find checkpoints -name "*.done"` timestamp/size diff against the Step 3.2 snapshot is empty | Any non-empty diff |
| 2.9 | `pub_data_pull.py` completes clean | Exits 0, no `CorpusValidationError` | Raises `CorpusValidationError` or any other exception |
| 2.10 | `final_health_report.py` completes clean | Exits 0, no `CorpusValidationError` | Raises `CorpusValidationError` or any other exception |
| 2.11 | `pub_data.json` content sanity | `time_bin_min`/`time_bin_max` are real ISO dates | Either field is the literal string `"nan"` (the original bug this whole procedure exists to fix) |
| 2.12 | Run manifest written and clean | A `checkpoints/run_manifests/*.json` file exists with `status: "SUCCESS"` and `stage: "topic_evolution"` | No manifest file exists, or `status != "SUCCESS"` |
| 2.13 | Full suite green | `pytest tests/ -q` reports 0 failures, and `test_bertopic_runner.py` now **passes** rather than **skips** | Any failure; or `test_bertopic_runner.py` still skipping (proves the environment precondition didn't actually hold, even if earlier steps appeared to succeed) |

**Overall PASS for the regeneration = all 13 rows above PASS.** A single FAIL anywhere in this table means the regeneration is not validated — proceed to rollback (§4), not to the Version 1.0 Release Checklist.

---

## 3. Evidence to collect

Archive all of the following after execution, regardless of outcome — this is the audit trail for the release record (Document 2, §"Artifact Archive"):

1. **Run manifest** — the full contents of the new `checkpoints/run_manifests/<run_id>.json` file (copy it, don't just note its existence). Contains `run_id`, `status`, `config_hashes`, `environment` snapshot, `git` state, and `checkpoints` (every stage's `config_slice_sha256` at run time).
2. **Regenerated `topic_evolution.parquet`** — the file itself, plus the printed output of §2.1–2.6's validation script (row count, configuration breakdown, analyst list).
3. **Checkpoint verification** — both diff outputs from §2.7/§2.8 (expected: empty), plus a fresh `find checkpoints -name "*.done" | wc -l` count (expected: unchanged from the pre-run count, since this stage never writes markers).
4. **`pub_data` output** — the full `pub_data.json` produced in §2.9, plus the console output of that command (exit code, any warnings).
5. **Final health report** — the console output of `final_health_report.py`, plus `health_report.json` if the script writes one.
6. **Pytest results** — full console output of `pytest tests/ -q` from §2.13, including the pass/skip/fail counts and specific confirmation that `test_bertopic_runner.py` ran (not skipped).

Store all six under a single dated evidence folder (e.g. `release_evidence/v1.0.0/topic_evolution_regen/`) — do not scatter them across the repository or leave them only in terminal scrollback.

---

## 4. Rollback (if any validation in §2 fails)

Identical to Execution Guide §6 — reproduced here so this checklist is self-contained:

1. `cp data/processed/topic_evolution.parquet.pre_regen.bak data/processed/topic_evolution.parquet`
2. Re-run §2.7/§2.8's diffs to confirm no other file was touched — both must still come back empty even after a failed run, since `run_topic_evolution()` only ever writes to its declared `output_path`.
3. If a `FAILED` run manifest exists, capture it as evidence (§3 item 1) before deciding whether to retry — its `error.type`/`error.message` fields are the fastest path to the actual cause.
4. Do not delete `.pre_regen.bak` or any `/tmp/` scaffolding until §2 fully passes on a subsequent attempt.
5. A failed regeneration does **not** by itself invalidate anything else in the repository — `topics.parquet`, checkpoints, and the rest of the test suite are unaffected by design. Escalate the specific failure; do not treat it as a platform-wide issue.

---

## 5. Sign-off

| Field | Value |
|---|---|
| Executed by | _________________ |
| Date/time (UTC) | _________________ |
| Production machine identifier | _________________ |
| `bertopic` version confirmed (§0.4) | _________________ |
| §2 overall result | PASS / FAIL (circle one) |
| Run manifest `run_id` | _________________ |
| Evidence archived at | _________________ |

**If §2 overall = PASS: proceed to `Version_1.0_Release_Checklist.md`.**
**If §2 overall = FAIL: do not proceed to release. File the failure with the collected evidence (§3) and escalate — this checklist's constraints do not permit fixing the underlying cause inline.**
