# Repository Risk Consolidation & Architecture Decision Records — Phase 2

**Scope:** Consolidation of the architecture audit conducted across this review (Providers layer: `youtube.py`; Infrastructure layer: `logging.py`, `checkpoint.py`, `io.py`; Core layer: `contracts.py`, `config.py`, `hashing.py`, `reproducibility.py`, re-verified against the handover). `collect/` subpackage (`channels.py`, `videos.py`, `comments.py`, `transcripts.py`, `quota.py`, `main.py` business logic) has **not** yet been independently audited beyond confirming its role in the import-order evidence for R7 — this is stated explicitly wherever it matters below, per the no-invented-evidence rule.

## Verification Provenance Legend

Every finding below is tagged with where its evidence comes from:

- **[Verified this session]** — I opened the file myself, in this conversation, and cite exact line numbers.
- **[Handover, re-verified this session]** — the handover reported this; I independently re-opened the file and confirmed (or corrected) it.
- **[Handover, not re-verified]** — carried forward for continuity only; I have not opened the underlying file myself in this session. Per your instruction, the repository — not the handover — is the source of truth, so these are marked low-confidence until re-checked.

One correction surfaced by this process: the handover rated `reporting/orchestrator.py` **🟢 Low** ("good orchestration, one small duplication"). My independent re-read this session found a **🟠 High** contract-violating bug in that same file (R8 below). Per your rule — repository overrides handover on disagreement — R8 supersedes the handover's rating. This is flagged, not silently merged.

---

## Amendment Log

Nothing below is a silent rewrite. Each entry says what changed and why.

**Amendment 4 (this pass — R14 Release Engineering re-verification complete; see `R14_Release_Engineering_Verification.md` for the full report).**
R14 is re-verified — result is mixed, not a clean pass. Real release-process documents exist (`docs/RELEASING.md`, `docs/VERSIONING.md`) and the Typer/Click pin is genuinely correct, but **nothing is committed to git** (HEAD is detached at `643c770`, behind `phase2-development`'s own tip; 11 modified + ~120 untracked paths, including `.github/` and `docs/` themselves), **no remote is configured**, and **`CHANGELOG.md`'s claimed `[1.0.0]` release directly contradicts** `docs/VERSIONING.md` ("currently pre-1.0"), `pyproject.toml`'s actual `version = "0.1.0"`, and the tag list (only `v0.1.0-phase1` exists — no `v1.0.0`). Full evidence table and Go/No-Go in the dedicated report.

**R17 correction, found while re-verifying R14's test-suite claims:** the count was **13** failing tests, not 12 as stated in this document's own R2/R1-adjacent entries and in Phase 3's Implementation Log — corrected here. Also, R17 is **two independent mechanisms**, not one: 10 of the 13 are caused by R7 (confirmed via revert/restore); the remaining 3 fail even with R7 reverted, due to a separate, R7-independent leak of real `statsmodels`/`numpy` warnings through the same `CliRunner(mix_stderr=True)` default. Neither correction changes R17's severity or v0.2.1 routing. Detail in `R14_Release_Engineering_Verification.md` §1.4 and §3.

**Amendment 3 (this pass — R1/ADR-P2-001 implemented; Sprint 1's four approved v0.2.0 blockers are now all resolved).**
R1 is now **Resolved**. All five previously-0%-covered methods (`channel_metadata`, `enumerate_videos`, `fetch_video_metadata`, `_to_video_record`, `_contains_promo`) now have dedicated happy-path, boundary-condition, and failure-path tests, designed against each method's behavioural contract rather than against its current implementation (three of the trickiest boundary/precedence assertions were verified against a temporarily-mutated implementation and confirmed to fail, then the mutation was reverted — see Phase 3 §6 for the three cases and exact mutation/failure pairs). Measured in this session's scratch venv, `youtube.py` coverage rose from 54.02% to 91.95% (missed-line detail in Phase 3 §6). The residual 91.95%-not-100% gap is not incidental: it consists entirely of lines outside ADR-P2-001's five-method scope (the never-exercised-by-design `_default_client_factory`, the constructor's `AuthenticationError` branch, three `resolve_channel` gaps, and four `fetch_top_level_comments` edge branches) — named explicitly, not glossed over, in Phase 3 §6.

**Amendment 2 (this pass — R2/ADR-P2-002 implemented; new finding R17 surfaced during its regression sweep).**
R2 is now **Resolved**. `CommentsDisabledError` added to `core/exceptions.py` (subclass of `CollectionError`, sibling of `ResourceNotFoundError`); `youtube.py::_execute`'s comments-disabled 403 branch now raises it instead of `ResourceNotFoundError` (`youtube.py:135`); `fetch_top_level_comments` catches only `CommentsDisabledError` and returns `[]` (`youtube.py:400-403`), so a genuine `ResourceNotFoundError` (404) now propagates uncaught, exactly as ADR-P2-002 specified. `collect/comments.py` gained the confirmed-necessary `except ResourceNotFoundError as e: ... continue` clause (line 246-258), mirroring `collect/channels.py`'s pattern. `collect/videos.py` was **not** touched, per instruction — it remains R16/ADR-P2-006's scope. All four required behavioural cases (comments enabled → collected; disabled → empty; deleted video → `ResourceNotFoundError`; one bad video in a batch → logged, skipped, rest continue) are demonstrated by dedicated tests — see Phase 3 §6 for the full list.

New, independent finding surfaced during R2's regression sweep — **R17** (below): a pre-existing test-suite fragility in `tests/unit/test_cli.py` and `tests/unit/test_reporting/test_main.py` (12 tests), unrelated to R2's own code paths. Root-caused this pass, not left as an open question: R7's fix (ADR-P2-003, resolved last pass) correctly makes `configure()` re-apply on every call instead of silently no-op'ing. `reporting/main.py`'s `validate` command calls `configure(log_dir=..., verbose=...)` as part of its own body; when this executes inside a test using Typer's `CliRunner()` (which defaults to `mix_stderr=True` — confirmed via `inspect.signature(CliRunner.__init__)` against the installed `click==8.1.8`), the freshly-created stderr `StreamHandler` binds to the *same captured stream* CliRunner uses for `result.output`. `run_reporting_pipeline`'s `_log.info("dry_run_plan", plan=plan)` call (`orchestrator.py:589`) then writes a structlog JSON line into that same buffer, so the test's own `json.loads(result.output)` sees two concatenated JSON objects and fails with `JSONDecodeError: Extra data`. Confirmed by direct experiment: temporarily reverting R7's fix (restoring the `if _CONFIGURED: return` guard) makes the exact same test pass again; restoring R7's fix reproduces the failure again, identically. **This is not a production bug** — real terminal/file usage keeps stdout and stderr as separate streams, so `finfluencer validate --json > out.json` is unaffected; it is `CliRunner`'s test-only stream-merging default interacting with R7's now-correct behavior. It is also **not caused by R2** — none of the 12 failing tests touch comments/`CommentsDisabledError` code paths, and the mechanism is fully explained by R7 + `CliRunner` alone, independently of any R2 change. Filed as R17 rather than silently fixed, per instruction not to expand scope beyond an approved ADR.

**Amendment 1 (this pass — `collect/` subpackage audit completed).**
R15 ("not yet audited") is now closed. New evidence:
- `collect/channels.py` correctly isolates per-item failures (`except ResourceNotFoundError as e: ... continue`, line 157-164) — this is the *reference-correct* pattern in this codebase.
- `collect/comments.py` and `collect/videos.py` wrap their per-item provider calls in `try:/finally:` with **no `except` clause at all** (`comments.py:199-247`, `videos.py:201-276`) — any exception from the provider aborts the entire stage for all remaining items in that invocation, unlike `channels.py`.
- `collect/transcripts.py` avoids the issue by construction — its injected `fetcher` callable is explicitly designed and documented to never raise for expected failure modes (`transcripts.py:64-65`), so the same `try:/finally:`-without-`except` pattern there is lower-risk, not a parallel bug.
- Net effect on **R2**: confirmed dependency. `collect/comments.py` has no handler for `ResourceNotFoundError` today, so today's silent-empty-list behavior never surfaces an exception to this loop. Implementing ADR-P2-002 as originally scoped (make a genuine 404 raise) would, without a matching fix in `collect/comments.py`, convert R2 from "silently wrong data" into "one bad video aborts the whole comments stage." **R2's scope is revised to include `collect/comments.py`** (add an `except` clause mirroring `channels.py`'s pattern) — this is a scope clarification of the same fix, not a new finding.
- New, independent finding: **R16** (below) — `collect/videos.py`'s identical missing-`except` pattern, unrelated to R2's exception-type split, filed separately per your instruction to treat remediations independently.
- Everything else read this pass (`collect/quota.py`, the full `collect/main.py` orchestration and CLI wrapper) is clean: no new Critical/High findings. `run_pipeline`'s single top-level `except Exception` (main.py:488-494) does correctly catch whatever propagates, write a `FAILED` manifest, and re-raise; the CLI wrapper (`main.py:546`) gives a clean one-line message for typed `FinfluencerError`s. This means R2/R16's actual failure mode is "loud abort, clean error message, resumable on re-run" — not a crash, not silent — which is why both are scored **High**, not **Critical**, and routed to different release gates below.

---

## PART 1 — Repository Risk Matrix

| ID | Subsystem | Module | Issue | Severity | Probability | Impact | Tech Debt (1-10) | Eng. Cost | Recommended Release | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| R1 | Providers | `providers/platform/youtube.py` | `channel_metadata`, `enumerate_videos`, `fetch_video_metadata`/`_to_video_record`, `_contains_promo` had **0% test coverage** | 🔴 Critical | High — untested code paths in the core data-collection surface | High — silent corruption of research dataset, undetectable by CI | 9 (was) → 1 (residual, out-of-scope lines only) | ~2-3 eng-days (actual: within estimate) | ✅ **RESOLVED** (was v0.2.0 Blocker) | [Verified this session] Coverage 54.02% → 91.95% (this session's scratch venv); all 5 target methods' previously-missed line ranges (219-235, 261-294, 305-317, 320-344, 362-365) now covered; 34 new behavioural tests across `tests/unit/test_providers/test_youtube.py` |
| R2 | Providers | `providers/platform/youtube.py::fetch_top_level_comments` | 404 ("video not found") and "comments disabled" both map to `ResourceNotFoundError` and are both silently swallowed as "0 comments" | 🟠 High | Medium — requires an invalid/deleted video ID reaching this call, plausible over a multi-year corpus | High — silent data loss in a reproducibility-focused pipeline | 7 | ~0.75 eng-day (actual) | ✅ **RESOLVED** (was v0.2.0 Blocker) | [Verified] `youtube.py:135` (`CommentsDisabledError`, new), `:158` (`ResourceNotFoundError`, unchanged semantics), `:400-403` (narrowed catch); `collect/comments.py:246-258` (new except clause) |
| R17 | Testing / Infrastructure interaction | `tests/unit/test_cli.py`, `tests/unit/test_reporting/test_main.py` | 12 tests assert `json.loads(result.output)` from a Typer `CliRunner()` invocation of `validate`/`analyze`/`report`/`export`; a structlog `dry_run_plan` log line leaks into that same captured stream and breaks JSON parsing | 🟡 Medium (test-only; no production code path affected) | **Certain** in any test run using unpatched `CliRunner()` | Low in production (separate OS streams); Medium for CI signal (12 tests newly red, obscuring real regressions) | 4 | ~few hours (patch `CliRunner(mix_stderr=False)` or assert on `result.stdout`, in each of the 12 tests, or once at a shared fixture level) | v0.2.1 (Strong Recommendation — CI hygiene, not a release blocker) | [Verified this session] Root-caused by direct experiment: reverting R7's fix makes all 12 pass again; restoring it reproduces the failure identically. `CliRunner.__init__` signature confirms `mix_stderr: bool = True` default (click 8.1.8). `reporting/main.py::validate` → `configure(...)` → `orchestrator.py:589 _log.info("dry_run_plan", ...)` is the exact call chain. |
| R3 | Providers | `providers/platform/youtube.py::resolve_channel` | Unrecognized `http` URL shapes (not `/channel/`, `/@`, `/c/`, `/user/`) fall through silently into a garbage handle lookup instead of a clear error | 🟡 Medium | Low-Medium — depends on how channel identifiers are sourced | Medium — confusing error, wasted quota unit, no data corruption | 4 | ~few hours | v0.2.1 | [Verified] `youtube.py:176-191` |
| R4 | Providers | `providers/platform/youtube.py` | Comments-disabled detection duplicated across `_execute()` and `fetch_top_level_comments`'s `except CollectionError` block, with different substring sets | 🟡 Medium | Medium — Google's error-message text is not a stable contract | Medium — inconsistent classification if Google's wording drifts | 5 | ~0.5 eng-day | v0.2.1 | [Verified] `youtube.py:124-133` vs `:398-402` |
| R5 | Providers | `providers/platform/youtube.py::enumerate_videos` | Early-exit windowing assumes strict newest-first playlist ordering, which YouTube does not contractually guarantee | 🟡 Medium (methodological) | Low | High if it occurs — silent under-collection of the corpus | 6 | ~0.5-1 eng-day (needs a design decision, not just a patch) | v1.0 (Strong Recommendation) | [Verified] `youtube.py:282-284` |
| R6 | Providers | `providers/platform/youtube.py::_execute` | Minor duplication in 403/429 `RateLimitError` branching | 🟢 Low | — | Low | 2 | trivial | Future / Nice to Have | [Handover, re-observed this session, unchanged] |
| R7 | Infrastructure | `core/logging.py` + all modules calling `get_logger(__name__)` at import time | `configure(log_dir=..., verbose=...)` is a **no-op on every real CLI invocation** — any transitively-imported module's module-level `get_logger()` call locks in default (no-file, INFO) config first | 🔴 Critical | **Certain** — happens on every run of both CLI entry points, not an edge case | High — silently breaks a documented guarantee ("dual-emitted to rotating file and stderr"); no error surfaced | 8 | ~1 eng-day (redesign init order or make `configure()` re-apply) | **v0.2.0 (Blocker)** | [Verified] `logging.py:60-61,131-132`; `collect/channels.py:42`; `collect/main.py:57` (import) vs `:543` (real call, now inert); same pattern confirmed in `reporting/main.py:98/101/133` |
| R8 | Reporting | `reporting/orchestrator.py::_build_dry_run_plan` | Function's own docstring guarantees "never touches disk"; it calls `checkpoint.should_run()`, which can `unlink()` a stale `.done` marker as a side effect | 🟠 High | Medium — triggers on any `--dry-run` after a config change, a normal workflow moment | High — destroys a completion record with zero actual work performed, forcing an unnecessary (possibly costly) re-run | 7 | ~0.5-1 eng-day | ✅ **RESOLVED** (was v0.2.0 Blocker) | [Verified] `reporting/orchestrator.py:441-445` (docstring) + `:458` (call, now routed to `has_valid_marker`); `core/checkpoint.py:99-101` (original unlink side effect, now isolated to `should_run()` only) |
| R9 | Infrastructure | `utils/io.py::read_jsonl` | Any `JSONDecodeError` past line 1 is treated as "crash-truncated last line" and iteration silently stops — without confirming it actually was the last line | 🟠 High | Low-Medium — reachable via the concurrent-write scenario `checkpoint.py` itself documents as unsupported-but-not-prevented | High — silent, undetected loss of valid Tier-1 checkpoint records | 6 | ~0.5 eng-day | v0.2.1 | [Verified] `io.py:160-166`; `checkpoint.py:21-29` (documents the concurrency risk that makes this reachable) |
| R10 | Core | `core/contracts.py::AnalysisScope` / `TopicRecord.scope_id` | Phase-3 migration step is additive-only; not yet read/written by `topics/pipeline.py` or `analysis/topic_sentiment.py` | 🟡 Medium (tracked WIP, not a latent bug) | n/a — known, staged | Low today (self-documented as non-breaking); Medium if the migration stalls | 5 | High (multi-file, per repo's own `Entity_Centric_Migration_Plan_v2.md`) | Future — already tracked | [Verified] `contracts.py:673-682, 746-748`. **Note:** repo already carries `ADR-0001_TopicEvolutionRecord_ScopeId_Deferral.md` for this exact decision — no new ADR written below; refer to the existing one. |
| R11 | Core | `core/config.py::load_settings` + `utils/hashing.py` | Empty `ANON_SALT` skips `validate_salt()` at config-load time ("dev mode"); the failure is deferred to the first `hash_identifier`/`fetch_top_level_comments` call at runtime | 🟡 Medium | Medium — a common misconfiguration (forgotten env var) | Medium — fails mid-run, potentially after spending real API quota on channels/videos; **confirmed no raw-ID leakage** | 4 | ~few hours | v0.2.1 | [Verified] `config.py:272-279`; `hashing.py:208-209`; `youtube.py:374-375` (defense-in-depth confirmed) |
| R12 | Core | `core/reproducibility.py` | No issues found — deterministic seeding, defensive git-state capture, clean-tree enforcement, comprehensive provenance record | 🟢 Low | — | — | 1 | — | — | [Verified] Confirms handover's rating unchanged. |
| R13 | Testing (cross-cutting) | project-wide | High line coverage (85-99%) on the exact files carrying R7/R8/R9 did not catch any of them — these are cross-module import-order and contract-level bugs that line coverage structurally cannot see | 🟡 Medium (process, not a code defect) | n/a | High — creates false confidence from coverage numbers | 6 | ~1-2 eng-days (targeted integration tests: cold-import + CLI-entrypoint test, dry-run-then-real-run test) | v0.2.1 / v1.0 | [Verified] `coverage.xml` line-rates: `logging.py` 0.8571, `checkpoint.py` 0.9846, `orchestrator.py` 0.9828 — all "well covered" by the metric, all host a Critical/High finding above |
| R14 | Release Engineering | `pyproject.toml`, `poetry.lock`, `RELEASING.md`, `VERSIONING.md`, `CHANGELOG.md`, `ci.yml` | **Re-verified this pass — mixed result, No-Go.** Click pin real but uncommitted; CI workflow untracked (never executed); no git remote; `CHANGELOG.md`'s `[1.0.0]` claim contradicted by `VERSIONING.md`, `pyproject.toml` (`0.1.0`), and the tag list | 🟡 Medium (process/governance, not application defect) | **Certain** — directly observed, not inferred | High for release credibility; zero for application correctness | 5 | ~1-2 eng-days (commit reconciliation + changelog fix + remote setup; R17 fix shared with existing estimate) | **v0.2.0 (Blocker — process, not code)** | [Verified this session] Full detail, evidence table, and Go/No-Go: `R14_Release_Engineering_Verification.md` |
| R15 | CLI, `collect/` business logic | `collect/channels.py`, `videos.py`, `comments.py`, `transcripts.py`, `quota.py`, `collect/main.py` | **CLOSED — audited.** No new Critical/High findings beyond R16. `channels.py`, `quota.py`, `main.py` orchestration/CLI wrapper are clean. | — | — | — | — | — | — | [Verified] See Amendment 1 above. |
| R16 | Bug / Architecture | `collect/videos.py` (loop over `collect_videos`) | `try:/finally:` around `provider.enumerate_videos()`/`.fetch_video_metadata()` has **no `except` clause** — any provider exception (quota, network, not-found) aborts the entire stage for all remaining analysts in that invocation, unlike the reference-correct pattern already used in `collect/channels.py` | 🟠 High | Medium — any transient API error on one analyst's videos costs progress on every remaining analyst in that run | Medium — not silent (top-level catch + `FAILED` manifest + clean CLI message per `main.py:488-494,546`) and not data-destructive (checkpoint resume works on re-run), but real operational friction on a multi-analyst, long-running collection | 5 | ~0.5 eng-day (mirror `channels.py`'s pattern) | v0.2.1 (Strong Recommendation — not bundled with R2; independent file, independent fix, per instruction to treat remediations independently) | [Verified] `videos.py:201-276` (no `except`) vs `channels.py:157-164` (correct pattern, same subpackage, same architecture) |

---

## PART 2 — Architecture Decision Records

Written for every Critical/High finding (R1, R2, R7, R8, R9). R10 already has a repo-native ADR (`ADR-0001_TopicEvolutionRecord_ScopeId_Deferral.md`) and is not duplicated here.

---

### ADR-P2-001
**Title:** Provider-layer test coverage gap in `YouTubePlatformProvider`
**Status:** ✅ **RESOLVED** (implemented this pass — see Phase 3 §6 Implementation Log for full verification detail, including the three mutation-testing falsifiability checks)

**Context**
`youtube.py` is the sole boundary between the platform and an external, rate-limited, quota-metered third-party API, and the sole point where raw research data enters the system.

**Problem**
Five of the class's methods — `channel_metadata`, `enumerate_videos`, `fetch_video_metadata`, `_to_video_record`, `_contains_promo` — have zero executed test lines. This includes the video eligibility classifier (shorts/made-for-kids/promo exclusion), which directly determines what enters the analytical corpus.

**Evidence**
`coverage.xml`: file line-rate 0.5385 (vs. 0.95-0.99 typical for Core-layer files reviewed this session); missed line ranges 214-239, 256-289, 300-339, 357-360.

**Current Design**
Client-injection pattern (`client_factory`) already makes these methods testable without hitting the real API — the seam exists, it's simply unused for these five methods.

**Consequences**
A regression in eligibility logic (e.g., a boundary error in the shorts-duration check, or a promo-keyword false negative) would silently change which videos are included in a published study, with no test to catch it.

**Alternative Solutions**
1. Write unit tests using the existing stub `client_factory` seam (matches the codebase's own established pattern).
2. Add integration tests against YouTube API test fixtures/cassettes (e.g., VCR-style recorded responses).
3. Accept the gap and rely on downstream data-quality checks instead.

**Recommended Solution**
(1), because the seam already exists and is used elsewhere in the codebase (per the module's own docstring: "Tests inject a stub factory"). This is the lowest-cost option consistent with the existing architecture.

**Migration Strategy**
No migration — additive test-writing only, no production code path changes required.

**Compatibility Risk**
None — test-only change.

**Estimated Effort**
2-3 engineer-days.

**Priority**
P0 — v0.2.0 blocker.

**Affected Files**
`src/finfluencer/providers/platform/youtube.py`; new test file(s) under `tests/providers/platform/`.

---

### ADR-P2-002
**Title:** `fetch_top_level_comments` conflates "video not found" with "comments disabled"
**Status:** ✅ **RESOLVED** (implemented this pass — see Phase 3 §6 Implementation Log for full verification detail)

**Context**
`_execute()` maps both a 404 ("video not found," e.g. a deleted video) and a specific 403 ("comments disabled") message pattern to the same `ResourceNotFoundError` type.

**Problem**
`fetch_top_level_comments` catches `ResourceNotFoundError` broadly and returns an empty list, treating both causes identically. A deleted/invalid video ID silently yields "0 comments collected" instead of a surfaced error — indistinguishable, in the resulting dataset, from a video that genuinely has comments disabled.

**Evidence**
`youtube.py:130-133` (comments-disabled → `ResourceNotFoundError`); `:152-155` (404 → same type); `:393-397` (single catch, both treated as empty).

**Current Design**
Single exception type carries two semantically different outcomes; the catch site cannot distinguish them.

**Consequences**
For a reproducibility-focused platform, an audit trail that cannot tell "comments were disabled" from "the video itself was missing" undermines the ability to explain gaps in the collected corpus — a real concern if a reviewer or replicator asks "why is this video's comment count zero?"

**Alternative Solutions**
1. Split the mapping in `_execute()` into two distinct exception types (keep `ResourceNotFoundError` for missing resources — this already matches its own docstring, "channel, video, or comment does not exist" — introduce `CommentsDisabledError` for the disabled case).
2. Attach a `reason` field to `ResourceNotFoundError` and branch on it at the call site.
3. Leave as-is and document the ambiguity.

**Recommended Solution**
(1) — confirmed against `core/exceptions.py`'s actual hierarchy and its own stated design rationale ("recoverable vs non-recoverable errors are distinct classes"). `CommentsDisabledError` should subclass `CollectionError` as a sibling of `ResourceNotFoundError`, matching the existing pattern exactly.

**Migration Strategy — REVISED (`collect/` audit, Amendment 1)**
Original plan (add exception type + update `_execute()` + update `fetch_top_level_comments`'s catch) still stands, **plus one confirmed addition**: `collect/comments.py`'s per-video loop (`comments.py:199-247`) has no `except` clause at all today. Once `fetch_top_level_comments` starts raising `ResourceNotFoundError` for genuine 404s, that exception will propagate uncaught out of `collect_comments`, aborting the stage for every remaining video in that invocation. `collect/comments.py` must gain an `except ResourceNotFoundError as e: _log.error("video_not_found", video_id=video_id, error=str(e)); continue` block, mirroring `collect/channels.py:157-164`'s already-correct pattern. Without this addition, the fix is incomplete — this is not a new finding, it's the originally-flagged dependency now confirmed and scoped.

**Compatibility Risk**
Low — additive exception type; the two call sites whose behavior changes (`youtube.py`'s catch, `collect/comments.py`'s new catch) both change from silent-swallow to logged-and-skipped, which is corrective, not breaking, for any caller of `collect_comments`.

**Estimated Effort**
0.5 engineer-day for the provider-layer split (unchanged) + 0.25 engineer-day for `collect/comments.py`'s new except-clause and its test ≈ **0.75 engineer-day total**, revised up from the original 0.5-day estimate now that the full blast radius is confirmed.

**Priority**
P0 — v0.2.0 blocker. Status unchanged by this revision — only effort and file scope changed.

**Affected Files**
`src/finfluencer/providers/platform/youtube.py`; `src/finfluencer/core/exceptions.py`; **`src/finfluencer/collect/comments.py`** (added this pass).

---

### ADR-P2-003
**Title:** `configure()` is a no-op in production due to import-order / lazy-init interaction
**Status:** ✅ **RESOLVED** (implemented this pass — see Implementation Report below)

**Context**
`core/logging.py` is designed to be idempotent (`configure()` guarded by a global `_CONFIGURED` flag) and lazy (`get_logger()` calls `configure()` with defaults if not yet configured), explicitly to be "safe for interactive notebook use."

**Problem**
Both CLI entry points (`collect/main.py`, `reporting/main.py`) import multiple submodules at module scope before their own explicit `configure(log_dir=..., verbose=...)` call executes (which only runs inside a function body, at CLI-invocation time). Several of those submodules call `get_logger(__name__)` at their own module scope (e.g. `collect/channels.py:42`). Because module-level code runs at import time — before any function in the entry-point module has executed — the very first such call anywhere in the import chain locks in the *lazy default* configuration (no `log_dir`, `verbose=False`) via the idempotency guard. The entry point's later explicit `configure()` call is then a guaranteed no-op.

**Evidence**
`logging.py:60-61` (`if _CONFIGURED: return`); `:131-132` (`get_logger()`'s lazy fallback); `collect/channels.py:42` (module-level `get_logger()` call); `collect/main.py:57` (imports `channels.py`) vs. `:543` (real `configure()` call, deep inside a function, executes after import phase completes); identical pattern independently confirmed in `reporting/main.py:98/101/133`.

**Current Design**
Global mutable singleton (`_CONFIGURED: bool`) combined with implicit self-configuration inside a getter function. This design silently privileges whichever call happens first — which, given Python's import semantics and this codebase's convention of module-level loggers, is never the entry point's own intentional call.

**Consequences**
File logging (`output.paths.logs`) never activates in any real run of the shipped CLI. This directly contradicts `logging.py`'s own documented invariant ("dual-emitted to (a) rotating file... and (b) stderr"). For a platform whose logs are described as "ingested by provenance," this silently degrades the provenance/audit trail with no error, warning, or test failure anywhere in the pipeline.

**Alternative Solutions**
1. Remove the lazy-default behavior from `get_logger()` entirely; require every entry point to call `configure()` explicitly before any other project import (enforced by import order, fragile).
2. Make `configure()` always apply the given parameters, dropping the idempotency guard, and instead make it safe to call multiple times by having it reset/replace handlers each time (already partially done — the handler-removal loop at `logging.py:101-103` already supports re-configuration; the guard is what's blocking it).
3. Move the two CLI entry points' `configure()` call to the very first line of `main()`/the Typer callback, and move ALL project imports (including the ones now at module scope) to occur only after that call — a much larger, more invasive restructuring across every entry point and its transitive imports.

**Recommended Solution**
(2) — remove the `if _CONFIGURED: return` early exit and let `configure()` simply reconfigure handlers each time it's called (the removal-then-add handler pattern already present makes this safe against handler duplication); keep a separate, smaller guard only to prevent redundant *first-call-with-defaults* churn if desired. This preserves the "safe for notebooks" goal without silently discarding a real caller's explicit intent.

**Migration Strategy**
Change `configure()` to always run its body; add a regression test that imports the full `collect.main` (or `reporting.main`) module and asserts a rotating file handler with the expected `log_dir` is attached to the root logger after the CLI's `configure()` call — this is exactly the class of bug line-coverage alone won't catch (see R13), so the test must assert on `logging.getLogger().handlers`, not just "no exception raised."

**Compatibility Risk**
Low-Medium — any code relying on the current (undocumented, accidental) "first configure wins" behavior would change. Given the behavior is undocumented and contradicts the module's own docstring, this risk is acceptable.

**Estimated Effort**
1 engineer-day, including the cross-module regression test.

**Priority**
P0 — v0.2.0 blocker.

**Affected Files**
`src/finfluencer/core/logging.py`; regression test touching `src/finfluencer/collect/main.py` and `src/finfluencer/reporting/main.py`.

---

### ADR-P2-004
**Title:** `_build_dry_run_plan` violates its own "never touches disk" contract
**Status:** ✅ **RESOLVED** (implemented per the exact plan below — see Phase 3 §6 Implementation Log for verification detail)

**Context**
`reporting/orchestrator.py::_build_dry_run_plan` exists specifically to give users visibility into what a run would do without side effects — its docstring states this as an explicit guarantee: "Introspection-only: never touches disk, never calls a Sprint 1 function."

**Problem**
The function calls `checkpoint.should_run(ckpt_name, config_slice)` to decide whether to report `"would_run"` or `"up_to_date"`. `CheckpointManager.should_run()` (`core/checkpoint.py:99-101`) deletes (`marker.unlink()`) the stage's `.done` marker whenever the recorded config-slice hash no longer matches — a real disk mutation, contradicting the calling function's documented contract.

**Evidence**
`reporting/orchestrator.py:441-445` (docstring); `:458` (the call); `core/checkpoint.py:99-101` (the `unlink()` side effect).

**Current Design**
`should_run()` is a combined query-and-mutate method: it both answers "should this run?" and, as a side effect, invalidates a stale marker so the *next* real run doesn't need to re-check the hash. This is a reasonable design for the real execution path, but it was reused, unmodified, inside a function whose entire purpose is to promise no mutation.

**Consequences**
A user who only wants a preview (`--dry-run`) after changing config can silently destroy a valid stage's completion record before deciding whether to actually re-run anything — turning a "safe look" into an accidental forced re-run, which for API-quota-metered or compute-expensive stages (comment collection, embeddings) has a real cost.

**Alternative Solutions**
1. Add a read-only `has_valid_marker(stage_name, config_slice) -> bool` method to `CheckpointManager` that mirrors `should_run()`'s hash comparison but never calls `unlink()`; use it from `_build_dry_run_plan` only.
2. Keep one method, add a `mutate: bool = True` parameter, and pass `mutate=False` from the dry-run path.
3. Document the side effect in `should_run()`'s docstring and accept that "dry run" cannot be perfectly side-effect-free.

**Recommended Solution**
(1) — a dedicated read-only method is the clearest fix and makes the dry-run path's own "never touches disk" claim actually true, rather than conditionally true depending on a caller-supplied flag that's easy to forget at a new call site in the future.

**Migration Strategy**
Add `has_valid_marker()` to `checkpoint.py` (extract the read-only comparison logic already inside `should_run()`); have `should_run()` call it internally before performing its mutation; switch `_build_dry_run_plan`'s call from `should_run()` to `has_valid_marker()`.

**Compatibility Risk**
Low — additive method; `should_run()`'s existing contract and callers (`collect/channels.py`, `videos.py`, `comments.py`, `transcripts.py`, `embeddings/pipeline.py`, `topics/pipeline.py`, `sentiment/pipeline.py`, `preprocess/pipeline.py` — all confirmed real-run call sites via this session's grep) are unaffected.

**Estimated Effort**
0.5-1 engineer-day, including a regression test that runs `_build_dry_run_plan` against a stage with a changed config and asserts the `.done` marker file still exists afterward.

**Priority**
P0 — v0.2.0 blocker.

**Affected Files**
`src/finfluencer/core/checkpoint.py`; `src/finfluencer/reporting/orchestrator.py`.

---

### ADR-P2-005
**Title:** `read_jsonl` cannot distinguish "clean crash truncation" from "corrupted mid-file record"
**Status:** Current (unresolved)

**Context**
`utils/io.py::read_jsonl` is the reader for Tier-1 streamed checkpoint records (`core/checkpoint.py`'s append-only JSONL log), which the pipeline's crash-recovery/resume story depends on.

**Problem**
On any `JSONDecodeError`, if it isn't the very first line, the function silently stops iterating and returns — treating this as "the last line was truncated by a crash mid-write," a correct assumption only if the bad line genuinely is the last one. It never checks whether more lines follow. `checkpoint.py`'s own docstring documents a scenario (concurrent runs against the same `checkpoint_root`, explicitly called "unsupported" but not locked or prevented) where "appends may interleave" — exactly the condition that could corrupt a line in the *middle* of the file, not just the end.

**Evidence**
`io.py:160-166`; `checkpoint.py:21-29` (the concurrency caveat that makes this reachable).

**Current Design**
Single heuristic (`lineno > 1` → assume clean truncation, stop) with no verification and no logging of the decision.

**Consequences**
If triggered, this silently drops every valid record after the corrupted line, with zero warning anywhere — for a platform whose central value proposition is reproducibility, silently losing collected data during a resume is a direct threat to the thing the platform is for.

**Alternative Solutions**
1. On any decode error, log a warning with the file path and line number regardless of position, so the failure is at least visible in logs (cheap, doesn't fix the data loss but surfaces it).
2. Peek ahead: if a decode error occurs and more non-blank content follows in the file, raise instead of silently stopping (distinguishes "true last-line truncation" from "corruption with valid data after it").
3. File-lock Tier-1 appends to make the interleaving scenario itself impossible, closing the root cause rather than the symptom.

**Recommended Solution**
(2) as the immediate fix (cheap, correct, matches the existing function's already-established defensive intent), plus (1) always-log regardless of outcome. (3) is a larger concurrency-control change worth considering separately, since `checkpoint.py` already documents wanting to support only single-writer usage — a lock would make that guarantee enforced rather than advisory.

**Migration Strategy**
Change the `except json.JSONDecodeError` branch: read the rest of the file (or peek at the next non-blank line) before deciding to `return` vs `raise`; add a `_log.warning(...)` call in both the "trailing truncation, stopping cleanly" and "mid-file corruption, raising" paths.

**Compatibility Risk**
Low — the only behavior change is that a previously-silent mid-file corruption now raises instead of silently truncating; this is a corrective, intentional behavior change for a genuinely dangerous silent-data-loss path.

**Estimated Effort**
0.5 engineer-day, including a test fixture with a corrupted mid-file line followed by valid records.

**Priority**
P1 — v0.2.1 (not certain to trigger under the currently-documented single-writer usage pattern, but cheap, high-value, and directly tied to a risk the codebase already acknowledges).

**Affected Files**
`src/finfluencer/utils/io.py`.

---

### ADR-P2-006
**Title:** `collect_videos` has no per-item exception isolation (unlike `collect_channels`)
**Status:** Current (unresolved) — new finding, Amendment 1 (`collect/` audit)

**Context**
`collect/channels.py`, `collect/videos.py`, and `collect/comments.py` share one architectural pattern: iterate a collection, call the provider per-item inside `try: ... finally: clear_context()`. Only `channels.py` adds an `except ResourceNotFoundError as e: ... continue` around that pattern.

**Problem**
`collect/videos.py`'s loop (lines 201-276) calls `provider.enumerate_videos()` and `provider.fetch_video_metadata()` with no `except` clause. Any exception these raise (`QuotaExhaustedError`, `NetworkError`, `ResourceNotFoundError`, `CollectionError`) propagates immediately, aborting video collection for every remaining analyst in that invocation — not just the one that failed.

**Evidence**
`videos.py:201-276` (no `except`) vs. `channels.py:157-164` (correct pattern, same subpackage). `main.py:488-494` confirms the top-level catch turns this into a loud, clean failure (writes a `FAILED` run manifest, clean CLI message) rather than a crash or silent loss — the checkpoint/resume design means a re-invocation continues from `already_done_pairs`, so this is an availability/friction problem, not a correctness or data-loss problem.

**Current Design**
Inconsistent: the correct per-item isolation pattern already exists once in this exact subpackage (`channels.py`) but was not applied to `videos.py` (or, before this fix, `comments.py` — see ADR-P2-002's revision).

**Consequences**
On a real multi-analyst run, one analyst's video enumeration hitting a transient network error or a single malformed video ID currently costs progress on every other analyst's videos in that invocation, requiring the operator to notice the failure and manually re-invoke — where `channels.py`'s pattern would have logged, skipped, and let the other analysts complete in the same run.

**Alternative Solutions**
1. Add `except (ResourceNotFoundError, NetworkError, RateLimitError) as e: log + continue` around the per-analyst body, matching `channels.py`; let `QuotaExhaustedError` and other non-recoverable `CollectionError`s propagate (quota exhaustion should stop the run — that's the exceptions module's own documented intent).
2. Catch bare `Exception` and always continue (simpler, but risks masking programmer errors as skippable data issues — inconsistent with `exceptions.py`'s own stated design rationale against broad catches).
3. Leave as-is; rely on the top-level catch + manual re-invocation.

**Recommended Solution**
(1) — matches `channels.py`'s existing, working pattern and respects the exception hierarchy's own recoverable/non-recoverable distinction (`exceptions.py:42-46`) rather than treating all failures identically.

**Migration Strategy**
Add the `except` clause to `collect/videos.py`'s per-analyst loop; no changes to `youtube.py` or the exception hierarchy required — this is a call-site fix only, independent of ADR-P2-002.

**Compatibility Risk**
Low — the change only affects behavior on the error path (currently: hard-abort; after: log-and-continue for recoverable errors), and only for `collect_videos` callers.

**Estimated Effort**
0.5 engineer-day, including a test that injects a per-analyst provider failure and asserts the remaining analysts still complete.

**Priority**
P1 — v0.2.1 (Strong Recommendation). Not bundled with R2/ADR-P2-002 despite the structural similarity — different file, different root cause (missing handler vs. conflated exception type), independent fix, per your instruction to treat every remediation as its own engineering change.

**Affected Files**
`src/finfluencer/collect/videos.py`.

---

## PART 3 — Release Readiness Assessment

| Finding | v0.2.0 | v0.2.1 | v1.0 | Classification |
|---|---|---|---|---|
| R1 — 0% coverage on core provider methods | ✅ resolved | — | — | ~~Release Blocker~~ **Resolved** |
| R2 — 404/disabled conflation | ✅ resolved | — | — | ~~Release Blocker~~ **Resolved** |
| R3 — URL misrouting in `resolve_channel` | ✅ | fix here | — | Strong Recommendation |
| R4 — duplicated error-string matching | ✅ | fix here | — | Nice to Have / Strong Recommendation |
| R5 — playlist-ordering assumption | ✅ | ✅ | fix or document here | Strong Recommendation |
| R6 — 429/403 minor duplication | ✅ | ✅ | ✅ | Nice to Have |
| R7 — `configure()` no-op | ❌ blocks | — | — | **Release Blocker** |
| R8 — dry-run disk mutation | ✅ resolved | — | — | ~~Release Blocker~~ **Resolved** |
| R9 — `read_jsonl` silent truncation | ✅ | fix here | — | Strong Recommendation |
| R10 — `AnalysisScope` WIP | ✅ | ✅ | already tracked (ADR-0001) | Nice to Have / Future |
| R11 — deferred `ANON_SALT` validation | ✅ | fix here | — | Strong Recommendation |
| R13 — coverage/correctness gap (process) | ✅ | add integration tests | harden further | Strong Recommendation |
| R14 — release-engineering closure | ❌ blocks | fix here | — | **Release Blocker (process)** — re-verified this pass, mixed result: nothing committed, no remote, changelog/version contradiction. See `R14_Release_Engineering_Verification.md` |
| R15 — `collect/` business logic | ✅ CLOSED this pass | — | — | Resolved (see Amendment 1) |
| R16 — `collect/videos.py` no per-item isolation | ✅ | fix here | — | Strong Recommendation |
| R17 — `CliRunner` stderr-mixing breaks 12 JSON-output CLI tests | ✅ | fix here | — | Strong Recommendation (CI hygiene, not a release blocker) |

**All four originally-identified code-level v0.2.0 blockers (R1, R2, R7, R8) are resolved, but v0.2.0 is not releasable on current evidence — the blocker has shifted from code to release process.** R14, re-verified this pass, is now itself a Blocker (process, not code): nothing is committed to git, no remote exists, and `CHANGELOG.md` contradicts `VERSIONING.md`/`pyproject.toml` on whether the project is even pre-1.0. Security and Performance gates remain unscored (out of R14's stated scope; never addressed in this audit). R16 and R17 (13 tests, two mechanisms — see Amendment 4) remain routed to v0.2.1 and do not independently block v0.2.0, though R17 undermines confidence in the CLI test suite as a release gate until fixed.

---

## PART 4 — Repository Health Dashboard

Each bar is evidence-anchored below it; this is a qualitative 0-10 scale, not a computed metric.

```
Architecture            ██████░░░░  6/10
Testing                 ███████░░░  7/10  [updated this pass — R1 resolved]
Documentation            █████████░  9/10
Infrastructure           █████░░░░░  5/10
Providers                ███████░░░  7/10  [updated this pass — R1 resolved]
Reporting                ██████░░░░  6/10
Release Engineering      ███████░░░  7/10  [low confidence — handover-sourced, not re-verified]
Developer Experience     ██████░░░░  6/10
Open Source Readiness    █████░░░░░  5/10
```

- **Architecture (6/10).** Real, principled patterns confirmed firsthand: the Adapter pattern isolating Google API errors into typed domain exceptions (`youtube.py::_execute`), the three-tier checkpoint design with its concurrency limits explicitly documented rather than hidden (`checkpoint.py:21-29`), Pydantic contracts with `extra="forbid"` enforced on every single schema (`contracts.py`). Held back by two confirmed cross-module contract violations (R7 global-init ordering, R8 side-effecting "read-only" method) — the same class of bug in two different subsystems suggests a pattern (shared mutable state / methods that both query and mutate) worth a repo-wide pass, not just two isolated fixes.
- **Testing (7/10, updated this pass).** Core-layer files reviewed this session sit at 95-99% (`config.py` 0.9892, `contracts.py` 0.9887, `checkpoint.py` 0.9846, `orchestrator.py` 0.9828). `youtube.py`, previously the single highest-risk file in the repository at 53.85% coverage, is now at 91.95% following R1's implementation this pass — its five previously-untested methods (including the video eligibility classifier, directly determining what enters the analytical corpus) now have behavioural-contract tests. R13's underlying observation still stands and is not erased by this: three of the highest-severity bugs found (R7, R8, R9) hid inside files with *high* coverage numbers before they were found, which is why R1's tests were deliberately designed against behavioural contracts (happy/boundary/failure-path per method, three assertions independently verified against mutated implementations) rather than written merely to move the percentage.
- **Documentation (9/10).** Every single file opened this session — seven of them, across three subsystems — carried a substantive module-level docstring explaining *why*, not just *what* (e.g. `hashing.py`'s truncation-length justification via birthday-paradox math, `io.py`'s explicit statement of format invariants, `checkpoint.py`'s explicit concurrency-limitation callout). This is a genuine, consistent strength, not a spot-check artifact.
- **Infrastructure (5/10).** Two Critical/High findings (R7, R8) in a three-file sample is a concerning density, even though the individual files (`checkpoint.py`, `io.py`) show careful atomic-write engineering elsewhere.
- **Providers (7/10, updated this pass).** R1 (the one Critical finding in this subsystem) is resolved. Three Medium findings remain open (R3, R4, R5, all routed to v0.2.1/v1.0) in the single file examined — real but non-blocking, unlike R1's silent-corruption risk which is now mitigated by tests.
- **Reporting (6/10).** One High finding (R8) in the one file examined; the surrounding dry-run/manifest design intent (from its own docstrings) is otherwise sound.
- **Release Engineering (7/10, low confidence).** Per handover only — Typer/Click pin, release docs, CI config. Not re-opened this session; score should be treated as provisional until independently re-checked.
- **Developer Experience (6/10).** Clear CLI structure (Typer), a real typed-exception taxonomy instead of bare exceptions, excellent docstrings — all aid a new contributor. Directly undercut by R7: a developer who sets `log_dir` and gets silent stderr-only output has no way to discover why without reading `logging.py`'s internals.
- **Open Source Readiness (5/10).** Capped by the outstanding v0.2.0 blockers (R1, R2, R7, R8) regardless of documentation quality — these are exactly the class of bug that burns early external contributors and erodes trust in a "reproducibility-focused" pitch.

---

## PART 5 — Executive Engineering Review

**Top strengths.** Documentation discipline is the standout, evidenced consistently across every file this session touched, not just the polished ones. Design patterns are deliberate and correctly applied where I looked — the Adapter pattern in the API client, the tiered checkpoint system, strict schema validation throughout `contracts.py`. Technical debt that does exist is, in at least one case (R10), already self-documented with its own ADR in the repository — that is a mature engineering habit, not a gap.

**Top weaknesses.** A coverage-correctness gap: the metric the team is tracking (line coverage, 82.74% project-wide per handover) is not catching the bugs that matter most. All three Infrastructure/Reporting findings (R7, R8, R9) sit in files with 85-98% coverage. The actual highest-risk file (`youtube.py`, the external-data boundary) has the lowest coverage of anything reviewed (53.85%). And there's a repeated architectural pattern across two subsystems — a method or function that looks read-only/idempotent but silently mutates shared state (`get_logger()`'s implicit `configure()` call; `should_run()`'s implicit `unlink()`) — worth treating as one systemic issue, not two unrelated bugs.

**Highest risks.** R1, R7, R8 — all Critical or High, all confirmed with exact file:line evidence, all currently unmitigated by any test in the suite.

**Most urgent fixes.** R7 and R2 have the best cost-to-severity ratio: R7 is Critical and fixable in ~1 day; R2 is High and fixable in ~0.5 day. Both should be first in any remediation sprint. R8 (~0.5-1 day) is the third — a "safe preview" feature that silently isn't safe is a trust-eroding bug worth fixing before any external user relies on `--dry-run`.

**Recommended release strategy.** Hold `v0.2.0` for R1, R2, R7, R8 (combined estimate ~5-6 engineer-days — a focused one-week sprint, not a re-architecture). Ship `v0.2.1` shortly after with R3, R4, R9, R11, and the R13 integration-test additions. Treat R5 and R10 as `v1.0`/Future, with R5 at minimum requiring an explicit documented-limitation note if not fixed outright, given the platform's reproducibility claims.

**Expected engineering effort.** Blocker set (R1, R2, R7, R8): ~5-6 engineer-days. Strong-recommendation set (R3, R4, R9, R11, R13): ~3-4 additional engineer-days. This is a rough, evidence-grounded estimate from the individual ADRs above, not a formal estimation exercise — treat it as ballpark, not a committed schedule.

**Overall maturity.** Late-stage pre-release: architecturally sound, unusually well-documented for a research codebase, with a small and well-scoped set of real correctness bugs typical of the transition from single-author exploratory research code to a hardened, externally-releasable v1.0. Not "beginner" work by any measure in what was reviewed — the bugs found are the kind that survive precisely *because* the surrounding code is sophisticated enough that they hide in the gaps between well-tested modules, not within any single module's obvious logic.

---

## Continuation

Per your instruction, the audit continues from exactly where it stopped: the `collect/` subpackage (`channels.py`, `videos.py`, `comments.py`, `transcripts.py`, `quota.py`, `main.py`) — the last remaining piece of the Infrastructure/Providers pass, listed as R15 above pending review.
