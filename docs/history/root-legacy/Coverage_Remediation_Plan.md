# Coverage Remediation Plan

**Role:** Implementation Engineer, Finfluencer Research Platform
**Corresponds to:** R6 in `Repository_Hygiene_and_Release_Remediation_Plan.md` ("Raise test coverage on collection modules"), referred to as R5 in this planning cycle.
**Type:** Planning only. No tests were written to produce this document. Every module and line reference below was read directly from the current source and a freshly-run coverage report — not inferred or estimated from an earlier report.
**Target:** Real, current coverage `68.74%` (2,644/3,661 statements covered), configured gate `75.0%`. Closing the gate requires approximately **102 additional covered statements** (0.75 × 3,661 ≈ 2,746 vs. 2,644 today). This number is the actual planning constraint the ranking below optimizes against — not "cover everything."

---

## 1. Every module with a coverage deficit, ranked by expected gain per unit of test effort

Effort is rated qualitatively (Low/Medium/High) based on what a test actually requires: pure-logic modules needing only fixtures and `tmp_path` are Low effort; modules requiring mocked external I/O (API clients, `git`, `importlib.metadata`) are Medium; modules requiring a live or heavily-mocked network/provider stack (YouTube Data API) are High.

| Rank | Module | Missing stmts | Coverage | Effort | Why this rank |
|---|---|---|---|---|---|
| 1 | `utils/io.py` | 57 | 48.92% | **Low** | Pure file I/O (`read_yaml`, `write_yaml`, `write_excel`, `write_csv`, exception-cleanup branches). No mocking at all — just `tmp_path` and real data. Single highest Low-effort yield in the codebase. |
| 2 | `market/run_confirmatory_analysis.py` | 41 | 0.00% | **Low–Medium** | Thin orchestrator; every function it calls (`confirmatory_analysis.py`, `figures.py`, `sentiment_index.py`) is already 95%+ covered elsewhere, so this is wiring/argument-passing/output-writing, not new logic to validate. |
| 3 | `market/ingest_manual_bist100.py` | 36 | 0.00% | **Low** | Pure pandas transform logic (comma-number parsing, date parsing, dedup, threshold check). Fully testable with an in-memory Excel fixture written to `tmp_path` — no network, no mocking. |
| 4 | `core/reproducibility.py` | 27 | 58.72% | **Low–Medium** | `verify_environment()`, `enforce_clean_tree()`, `enforce_publication_reproducibility()` are entirely untested. All pure logic over dicts/objects already in scope; `get_git_state()`'s success path needs one `monkeypatch` of `git.Repo`. |
| 5 | `providers/language/english.py` | 27 | 38.60% | **Low** | Pure string/regex logic (`strip_noise`, `tokenize`, `is_language`, `extract_emojis`). No network — `langdetect` runs locally and deterministically (seeded). |
| 6 | `providers/market/tcmb_evds_provider.py` | 36 | 63.83% | **Medium** | Real HTTP provider; needs response mocking (`requests`-style), but the codebase likely already has a mocking pattern from `yfinance_provider.py`'s own tests (83.05%) to extend rather than invent. |
| 7 | `market/collect_market_data.py` | 27 | 68.32% | **Medium** | Depends on `yfinance`; needs the same provider-mocking pattern as item 6. |
| 8 | `core/registry.py` | 20 | 67.05% | **Low–Medium** | `discover()`'s entry-point loading path is entirely untested — real extensibility infrastructure (Architecture v1.0's Plugin System depends on it), testable by monkeypatching `importlib.metadata.entry_points()`, no real package installation needed. |
| 9 | `collect/quota.py` | 21 | 32.50% | **Low** | Pure arithmetic/date logic over a JSON state file. No network — `load_persisted_tracker`/`persist_tracker`/rollover logic all testable with `tmp_path`. |
| 10 | `core/budgets.py` | 20 | 75.65% | **Low** | `QuotaTracker`'s validation/exception paths (`ensure_capacity` raising, negative-units rejection) and `MemoryBudget`'s `raise`-mode path are pure logic, already partially tested — closing the remainder is cheap. |
| 11 | `core/config.py` | 14 | 78.86% | **Low** | Already near the gate individually. Remaining gaps are specific, enumerable exception/edge branches (below) — not broad new surface. |
| 12 | `collect/channels.py` | 38 | 22.39% | **Medium–High** | Needs a mocked `PlatformProvider`; smallest of the four heavy collection modules. |
| 13 | `collect/videos.py` | 92 | 12.75% | **High** | Same provider-mocking requirement as channels.py, larger surface (pagination, dedup, multi-entity linking). |
| 14 | `collect/comments.py` | 94 | 14.48% | **High** | Provider mocking plus anonymization/hashing paths. |
| 15 | `collect/transcripts.py` | 93 | 11.19% | **High** | Provider mocking plus its own bespoke fetcher (flagged separately in Architecture v1.0 §6/§21 as needing eventual protocol generalization — not this item's job to fix, only to test as-is). |
| 16 | `collect/main.py` | 102 | 44.88% | **High** | Remaining gaps are the `channels`/`videos`/`comments`/`transcripts` CLI stage-branches specifically — cannot be closed without items 12–15's mocking infrastructure existing first. |
| 17 | `providers/platform/youtube.py` | 160 | 11.46% | **High** | Largest absolute deficit in the codebase, but requires mocking the full YouTube Data API v3 client surface — the single most expensive item here per statement. |

**Smaller finishing-touch items** (each under 10 missing statements, Low effort, worth sweeping up opportunistically rather than sequencing separately): `market/sentiment_index.py` (7), `providers/market/yfinance_provider.py` (8), `core/logging.py` (7), `topics/bertopic_runner.py` (9, partially blocked — see note below), `utils/dedup.py` (4), `utils/time.py` (5), `core/checkpoint.py` (2), `embeddings/sentence_transformer.py` (3), `market/figures.py` (1), `market/confirmatory_analysis.py` (1), `topics/pipeline.py` (29, mostly branch-coverage on already-well-tested paths).

**Explicitly out of scope for this plan:** `src/finfluencer/__main__.py` (11 missing, 0%) is not a coverage target — it runs `examples/language_demo.py` and is unrelated to the packaging entry point fixed in R2; raising its coverage would not improve production confidence and is not recommended.

---

## 2. The strategic finding this ranking produces

Summing just the Low/Low-Medium effort items (ranks 1–5, 8–11): `utils/io.py` (57) + `run_confirmatory_analysis.py` (41) + `ingest_manual_bist100.py` (36) + `reproducibility.py` (27) + `english.py` (27) + `registry.py` (20) + `quota.py` (21) + `budgets.py` (20) + `config.py` (14) = **263 statements**, against a target of ~102.

**This means the coverage gate can plausibly be closed without writing a single new test for `collect/channels.py`, `videos.py`, `comments.py`, `transcripts.py`, or `providers/platform/youtube.py`** — the five modules the original Remediation Plan (and the Release Readiness Report before it) named as the headline gap. Even assuming well under 100% coverage achieved within each Low-effort target (realistically 60–80% of each), the Low-effort tier alone comfortably clears 102 statements.

This is stated as a finding for you to weigh, not a recommendation to silently skip those five modules. There is a legitimate argument for testing them anyway that this ranking's efficiency-only metric doesn't capture: they are the modules that actually touch the live YouTube API and process real, currently-flowing production data, so tests there carry risk-reduction value beyond their statement count. §3's implementation order sequences the Low-effort tier first (fastest path to closing the gate) and treats the collection modules as a second, separately-justified phase — not because they're unimportant, but because bundling them into gate-closing work would overstate what's actually required to hit 75%.

---

## 3. Per-module detail — functions, edge cases, exception paths, expected gain

### `utils/io.py` (57 missing → target ~45 covered)

| Function | Edge cases | Exception paths | Expected gain |
|---|---|---|---|
| `read_yaml` | Well-formed YAML round-trips `write_yaml` → `read_yaml` | N/A (delegates to `yaml.safe_load`, no custom handling here) | ~3 stmts |
| `write_yaml` | Nested dict, list values, unicode content (`allow_unicode=True`) | N/A | ~7 stmts |
| `write_excel` | Multiple sheets, a sheet name >31 chars (truncation logic) | Write failure mid-stream → temp file cleanup (`tmp.unlink()` in `except`) | ~17 stmts |
| `write_csv` | `decimal_places` set vs. `None` (two distinct `kwargs` branches) | Same temp-file-cleanup-on-exception pattern as `write_excel` | ~16 stmts |
| `_atomic_write_bytes` | N/A (already partially covered via `write_json`/`write_parquet` callers) | Write failure → `os.unlink(tmp_name)` cleanup path, including `OSError` inside the cleanup itself | ~6 stmts |
| `read_jsonl` | Blank-line skipping; a truncated last line after a simulated crash (`lineno > 1` vs. `lineno == 1` branches) | `JSONDecodeError` on a non-first line (silently stops) vs. on the first line (re-raises) | ~8 stmts |

**Expected coverage gain: ~50–55 statements.** Test pattern: standard `tmp_path`-based round-trip tests, no mocking. This should be the first module implemented.

### `market/run_confirmatory_analysis.py` (41 missing → target ~35 covered)

| Function | Edge cases | Exception paths | Expected gain |
|---|---|---|---|
| `main()` | Default paths vs. explicit paths; output directory creation when it doesn't yet exist | None of its own — propagates whatever the four imported functions raise (not this module's concern to re-test) | ~30 stmts |
| `_cli()` | `argparse` default values vs. explicit CLI args | `SystemExit` on missing/malformed args (argparse's own behavior — worth one smoke test, not exhaustive argparse testing) | ~10 stmts |

**Expected coverage gain: ~35 statements.** Test pattern: mock the five imported functions (`build_pooled_sentiment_index`, `build_analysis_panel`, `descriptive_table`, `run_confirmatory_analysis`, `regression_table`, `granger_table`, `plot_sentiment_vs_bist100`) with `unittest.mock.patch`, since their own internal correctness is already validated by `test_confirmatory_analysis.py`/`test_sentiment_index.py` elsewhere — this module's job is only to prove the wiring and file-writing, not re-derive statistical correctness.

### `market/ingest_manual_bist100.py` (36 missing → target ~32 covered)

| Function | Edge cases | Exception paths | Expected gain |
|---|---|---|---|
| `_parse_yahoo_number` | Comma-thousands values (`"11,249.70"`), already-clean floats, non-numeric junk → `NaN` via `errors="coerce"` | N/A (coerces, never raises) | ~3 stmts |
| `ingest_manual_bist100_xlsx` | Rows dropped on parse (triggers the `_log.warning` branch); exactly 10 valid rows (boundary) vs. 9 (raises) | `pd.read_excel` failure → `DataError`; missing `"Date"` or no `"Close"`-prefixed column → `DataError`; `<10` valid rows after cleaning → `DataError` | ~29 stmts |

**Expected coverage gain: ~32 statements.** Test pattern: build a small `pd.DataFrame`, write it via `.to_excel(tmp_path / "source.xlsx")`, call the function against that path — no mocking, real pandas I/O. Three explicit `DataError` cases (bad file, missing columns, too few rows) plus the happy path plus the dropped-rows-warning path.

### `core/reproducibility.py` (27 missing → target ~24 covered)

| Function | Edge cases | Exception paths | Expected gain |
|---|---|---|---|
| `verify_environment` | Matching pinned snapshot (no raise); Python-version mismatch (raises even in non-strict mode); package-version-only mismatch in strict vs. non-strict mode (raises vs. tolerated) | `EnvironmentMismatchError` — both trigger conditions | ~13 stmts |
| `get_git_state` | Success path — needs `monkeypatch` on `git.Repo` to return a fake repo object (commit hexsha, branch, dirty flag) rather than relying on this sandbox's real git state | Detached HEAD (`branch: None`) as its own explicit case | ~12 stmts (success-path branch currently entirely unexercised) |
| `enforce_clean_tree` | N/A | `git_state["available"] is False` → raises; `git_state["dirty"] is True` → raises; clean+available → no raise | ~10 stmts |
| `enforce_publication_reproducibility` | `replication.stage != publication` → early return; `ethics.strict_reproducibility is False` → early return; both true, clean tree, package present → no raise | Dirty tree at publication stage → raises (via `enforce_clean_tree`); `finfluencer-platform` absent from `environment.packages` → `ReproducibilityError` | ~14 stmts |

**Expected coverage gain: ~24–27 statements.** Test pattern: `monkeypatch` for `git.Repo`/`importlib.metadata.version`; everything else is dict/object construction, no real I/O.

### `providers/language/english.py` (27 missing → target ~24 covered)

| Function | Edge cases | Exception paths | Expected gain |
|---|---|---|---|
| `strip_noise` | URLs, `@handles`, non-letter characters, multiple-whitespace collapsing — each regex substitution independently | N/A | ~5 stmts |
| `tokenize` | Empty string, multiple-whitespace input | N/A | ~1 stmt |
| `is_language` | Empty/whitespace-only text (`False`); short text (<3 words, regex fallback); long text routed through `langdetect.detect` | `LangDetectException` on genuinely undetectable input (e.g. pure punctuation/numbers) → caught, returns `False` | ~10 stmts |
| `extract_emojis` | Mixed emoji + text; emoji-only; text with no emoji at all; boundary Unicode code points (`0x1F300`, `0x2600`) | N/A | ~8 stmts |

**Expected coverage gain: ~24 statements.** Test pattern: identical in shape to whatever the existing `providers/language/turkish.py` tests already do (96.72% covered) — extend that pattern to the English provider rather than inventing a new one.

### `core/registry.py` (20 missing → target ~18 covered)

| Function | Edge cases | Exception paths | Expected gain |
|---|---|---|---|
| `_register_class` | N/A | Empty `kind` or `key` → `ValueError` | ~2 stmts |
| `discover` | Entry point name without a `:` separator (skipped); entry point `kind` not matching the requested `kind` (skipped) | `ep.load()` raising during a plugin's own import — collected into `errors`, does not abort discovery of other plugins; the `TypeError` fallback path for older `importlib.metadata` APIs | ~16 stmts |
| `list_registered` | Called with `kind=None` (all registrations) vs. a specific `kind` | N/A | ~1 stmt |

**Expected coverage gain: ~18 statements.** Test pattern: `monkeypatch` `importlib.metadata.entry_points` to return a small, fake, controllable set of entry points (some valid, some malformed, one whose `.load()` raises) — this is real extensibility-mechanism testing, not incidental.

### `collect/quota.py` (21 missing → target ~19 covered)

| Function | Edge cases | Exception paths | Expected gain |
|---|---|---|---|
| `_quota_day` | A timestamp just before vs. just after the UTC-8 reset boundary (date rolls over correctly) | N/A | ~2 stmts |
| `load_persisted_tracker` | State file absent (fresh tracker); state file present but stale `quota_day` (rollover → fresh tracker); state file present, same day, valid `used_units` restored | Corrupted/unreadable state file → falls back to a fresh tracker (caught `except Exception`) | ~19 stmts |
| `persist_tracker` | Round-trips with `load_persisted_tracker` (write then immediately reload, same-day) | N/A | (covered incidentally by the above) |

**Expected coverage gain: ~19–21 statements.** Test pattern: `tmp_path`-based JSON state files, `freezegun`-style or manual `datetime` construction for the day-boundary case — no network, no provider.

### `core/budgets.py` (20 missing → target ~18 covered)

| Function | Edge cases | Exception paths | Expected gain |
|---|---|---|---|
| `QuotaTracker.ensure_capacity` | Exactly at the effective ceiling (boundary — should raise); comfortably under | `QuotaBudgetExceededError` | ~6 stmts |
| `QuotaTracker.spend` | Crossing the ceiling mid-spend (triggers the warning log branch, does not raise) | Negative `units` → `ValueError` | ~4 stmts |
| `QuotaTracker.__init__` | `daily_units < 1`; `safety_margin < 0`; `safety_margin >= daily_units` | Three distinct `ValueError`s | ~3 stmts |
| `MemoryBudget` (`raise` mode) | `sample()` exceeding `max_gb` in `mode="raise"` | `MemoryBudgetExceededError` | ~5 stmts |

**Expected coverage gain: ~18 statements.** Test pattern: pure object construction and method calls — no mocking needed at all; this is the cheapest item on the entire list per statement.

### `core/config.py` (14 missing → target ~12 covered)

| Function | Edge cases | Exception paths | Expected gain |
|---|---|---|---|
| `_enforce_stage_policy` | `replication.stage == publication` with an unpinned revision present | `UnpinnedRevisionError`, listing every unpinned field | ~7 stmts |
| `load_settings` | Roster validation failure (malformed `analysts.yaml`, distinct from the settings-validation error path already tested in `test_config.py`) | `ConfigValidationError` from the roster branch specifically | ~4 stmts |
| `load_settings` (salt validation) | `ANON_SALT` env var set (non-empty) at both `strict` and non-strict replication stages | `validate_salt`'s own `ConfigError` propagating through | ~5 stmts |

**Expected coverage gain: ~12–14 statements.** Test pattern: extend `tests/unit/test_core/test_config.py`'s existing pattern (it already builds malformed YAML fixtures for the settings-validation case) to the roster and salt branches specifically.

---

## 4. Implementation order

Sequenced by §1's ranking, grouped into phases with a running cumulative-gain estimate against the ~102-statement target:

**Phase 1 — close the gate (Low effort, no mocking beyond simple `monkeypatch`):**
1. `utils/io.py` (~50) — cumulative ~50
2. `market/ingest_manual_bist100.py` (~32) — cumulative ~82
3. `core/budgets.py` (~18) — cumulative ~100
4. `collect/quota.py` (~19) — cumulative ~119, **gate exceeded**

Phase 1 alone, on this plan's own conservative per-module estimates, closes the gate. Everything below is recommended for platform quality and risk-reduction, not because the numeric gate still requires it.

**Phase 2 — round out the Low/Low-Medium tier (finish what Phase 1 started, build margin above 75% rather than sitting exactly on it):**
5. `core/reproducibility.py` (~24)
6. `providers/language/english.py` (~24)
7. `core/registry.py` (~18)
8. `core/config.py` (~12)
9. `market/run_confirmatory_analysis.py` (~35)

**Phase 3 — Medium effort, provider-mocking modules:**
10. `providers/market/tcmb_evds_provider.py`
11. `market/collect_market_data.py`

**Phase 4 — the collection/provider stack (High effort; risk-justified, not gate-justified per §2's finding):**
12. `collect/channels.py` (smallest of the four — build the `PlatformProvider`-mocking fixture here first)
13. `collect/videos.py`
14. `collect/comments.py`
15. `collect/transcripts.py`
16. `collect/main.py` (the remaining CLI stage-branches, once 12–15's mocks exist to reuse)
17. `providers/platform/youtube.py` (largest, most expensive; last, using every mocking pattern built in this phase)

**Phase 5 — opportunistic finishing touches** (the sub-10-statement items listed in §1), swept up alongside whichever neighboring module in Phases 1–3 shares a test file, not scheduled as standalone work.

No tests were written to produce this plan. Ready for review before any implementation begins.
