# Production-Grade Code Audit

**Scope:** Hidden bugs, edge cases, exception handling, resource leaks, race conditions, packaging, maintainability, technical debt, API consistency, configuration risks, logging quality. Code style explicitly excluded. Only issues realistically worth fixing before v1.0 are reported.
**Method:** Direct reading of the highest-risk, least-covered modules (the four collection stages, the YouTube provider, the checkpoint manager, the pipeline orchestrator) plus targeted repository-wide searches for known anti-patterns (bare/broad excepts, mutable defaults, debug prints, undeclared imports). No files were modified.

---

## Critical

### 1. `collect/transcripts.py` depends on a package that isn't declared anywhere in `pyproject.toml`

`_default_fetcher()` does `from youtube_transcript_api import YouTubeTranscriptApi` (line 68) and, on `ImportError`, raises `RuntimeError("youtube-transcript-api is not installed; run \`poetry install\` or \`pip install youtube-transcript-api\`")`. But `youtube-transcript-api` does not appear anywhere in `[tool.poetry.dependencies]` — verified by reading the full dependency list and grepping `pyproject.toml` directly. A clean, correctly-executed `poetry install` will never install this package, which means the transcripts stage — one of the four core collection stages, per `collect/main.py`'s own docstring — is **permanently broken** on any properly-provisioned installation, and the error message it raises tells the user to do the one thing (`poetry install`) that will not fix it. This isn't a theoretical edge case; it will reproduce on the very first attempt to run `--stage transcripts` or `--stage all` on a fresh install.

**Fix:** add `youtube-transcript-api` to `[tool.poetry.dependencies]` (or an extras group, if transcripts collection is meant to be opt-in) and regenerate `poetry.lock`.

---

## Major

### 2. Debug `print()` statements left inside the YouTube provider's exception handler

`providers/platform/youtube.py::_execute()`, lines 121-124:

```python
print("\n================ DEBUG ================")
print("STATUS:", status)
print("MESSAGE:", msg)
print("=======================================\n")
```

This runs on *every* exception the googleapiclient raises — which in normal operation includes routine, expected events like comments-disabled videos and quota exhaustion, not just genuine bugs. Two concrete problems: (a) it's unstructured stdout output sitting inside a codebase whose entire logging design (`core/logging.py`) is built around JSON-structured, machine-parseable records "ingested by provenance" — these prints bypass that system entirely and, if anything downstream treats stdout as a JSON log stream, will corrupt it; (b) it's visibly leftover debugging scaffolding, not intentional diagnostics (no log level, no structured fields, ASCII-art banner). Should be removed or converted to a proper `_log.debug(...)` call.

### 3. Dead code in the same function silently disables `RateLimitError` classification

Still in `_execute()` (lines 126-161), the `status == 403` branch is:

```python
if status == 403:
    lower_msg = msg.lower()
    if ("commentsdisabled" in lower_msg or ...):
        raise ResourceNotFoundError(...)
    if ("quota" in lower_msg or "dailylimit" in lower_msg or "quotaexceeded" in lower_msg):
        raise QuotaExhaustedError(...)
    raise CollectionError(msg, status_code=status) from e
      
    if "quota" in msg.lower() or "dailyLimit" in msg:      # <- unreachable
        raise QuotaExhaustedError(...) from e               # <- unreachable
    raise RateLimitError(                                    # <- unreachable
        "YouTube API rate-limited (429)", status_code=status,
    ) from e
```

Everything after the unconditional `raise CollectionError(...)` is unreachable — this reads as leftover code from an incomplete refactor (the lowercase-normalized checks above appear to be the intended replacement for the mixed-case checks below, but the old branch was never deleted). The practical effect: **any 403 that isn't specifically "comments disabled" or quota-related now always raises generic `CollectionError`, and `RateLimitError` can never be raised from this function at all.** Combined with finding #4 below, this means transient rate-limiting is neither correctly classified nor retried.

### 4. `tenacity` is declared as a dependency and documented as providing retry logic, but is never used anywhere

`pyproject.toml` lists `tenacity = "^8.2"` with the comment "tenacity provides declarative retry logic; used by core/logging and utils." A full search of `src/` for `tenacity`, `@retry`, and `retry_if` returns zero matches. `providers/platform/youtube.py`'s own module docstring states as a design decision: *"Retry policy: Only transient errors (RateLimit, NetworkError) are retried."* This retry behavior does not exist anywhere in the codebase — the documentation describes an intended design that was never implemented. In practice, any transient network blip or rate-limit response during a multi-hour collection run hard-fails that stage outright (recoverable only via checkpoint-based resume, i.e. re-running the whole command), not automatically retried as documented.

**Fix:** either implement the documented retry wrapping using the already-declared `tenacity` dependency around the provider calls in `collect/channels.py`/`videos.py`/`comments.py`, or correct the docstring and dependency comment to stop claiming a capability that doesn't exist.

### 5. No per-item exception isolation across the three online collection stages

- `collect/channels.py` (lines 122-166): only catches `ResourceNotFoundError` around the per-analyst resolve+metadata calls. Any other exception — including the now-mislabeled `CollectionError` from finding #3, or `QuotaExhaustedError`, or a raw `KeyError` from an unexpected API response shape — aborts channel resolution for every remaining analyst in the roster, not just the one that failed.
- `collect/videos.py` (lines 187-262) and `collect/comments.py` (lines 199-247): the per-item loop is wrapped in `try: ... finally: clear_context()` with **no `except` clause at all**. Any exception from the provider call aborts the entire remaining batch (all other videos/analysts in that run).

This is a defensible design if the intent is "quota exhaustion should halt everything" — but it applies uniformly to every exception type, including ones that plausibly should be isolated to a single bad item (a single malformed API response, one video's comments returning an odd shape). The checkpoint/resume system is the only recovery path, which means a single flaky item can turn a multi-hour run into a full restart-and-skip-ahead cycle rather than a one-item skip.

### 6. Systematic sampling can silently under-deliver the target sample size

`collect/videos.py::_month_stratified_sample()`, line 118:

```python
indices = sorted({min(int(start + i * step), n - 1) for i in range(k)})
```

The candidate indices are deduplicated via a Python `set`. When `step` is small (i.e. the quota `k` for a month is close to that month's bucket size `n`), floating-point rounding can cause two different `i` values to collide on the same integer index, silently producing **fewer than `k` indices** for that month — and there is no check afterward that `len(selected) == target_n` for the function as a whole. The module's own docstring promises "the same corpus is drawn on every re-run" and a specific target sample size (Methods §3.2.3); this bug means the actual delivered sample count can quietly drift below the configured `max_videos_per_analyst` with no warning logged, which matters for a platform whose whole purpose is producing a defensible, reproducible research sample.

**Fix:** either use a collision-free systematic-sampling scheme, or add a post-hoc check/log when `len(selected) < target_n` so the drift is at least visible rather than silent.

### 7. A late, non-critical failure can mark an otherwise fully successful pipeline run as `FAILED`

`collect/main.py::run_pipeline()`, lines 465-474: `persist_tracker(quota, quota_state_path)` runs inside the main `try` block, after every actual collection/processing stage has already completed and written its output to disk. It is not wrapped in its own try/except (unlike `_write_manifest_safe`, which is explicitly designed to never let manifest-writing failures propagate). If this one call fails — e.g. a transient disk-write issue — the outer `except Exception` catches it and writes a run manifest with `status: FAILED`, even though every real pipeline stage succeeded and all data is safely on disk. Since the Run Manifest System was just built and fully tested this engagement specifically to give an honest signal of run success/failure, this is a real gap in that signal's reliability: an operator (or downstream automation) checking manifest status would see `FAILED` for a run that actually produced complete, correct output.

**Fix:** wrap the `persist_tracker` call in the same best-effort try/except pattern already used for manifest writes.

### 8. The CLI only gives clean error handling for one exception type

`collect/main.py::run()` (the Typer command, lines 531-535):

```python
try:
    run_pipeline(cfg, stage=stage, dry_run=dry_run)
except FileNotFoundError as e:
    typer.echo(f"Pipeline aborted: {e}", err=True)
    raise typer.Exit(code=1)
```

Every other exception type the pipeline can raise — `AuthenticationError` (missing API key), `QuotaExhaustedError`, `CollectionError`, a pydantic `ValidationError` from bad config, etc. — is not caught here, so it propagates as a raw Python traceback to whoever ran the CLI. For a tool meant to be operated by researchers who may not be Python developers, this is a real usability/API-consistency gap: one category of failure gets a clean one-line message, everything else dumps a stack trace.

### 9. Legacy YouTube URL formats are silently mishandled

`providers/platform/youtube.py::resolve_channel()` (lines 186-190) explicitly handles `/channel/UC...` and `/@handle` URL forms, but not the still-common legacy `/c/CustomName` or `/user/Username` forms. For those, the `if h.startswith("http")` block does nothing, and the full URL string falls through into the handle-lookup path, becoming something like `"@https://youtube.com/c/SomeName"`, which the API will simply not find. The resulting `ResourceNotFoundError` message doesn't hint at "unsupported URL format" — it just reports the mangled pseudo-handle as if it were a real lookup that failed, which will confuse whoever is debugging a new analyst's config entry.

---

## Minor

### 10. Inconsistent defensive coding within one function risks an unhandled `KeyError`

`providers/platform/youtube.py::fetch_top_level_comments()`, line 405: `top = thread["snippet"]["topLevelComment"]["snippet"]` uses raw bracket indexing, while every other field access in the same function uses `.get()` with a fallback. A single API response with an unexpected shape for one comment thread would raise `KeyError` here — and per finding #5, that would abort the entire comments-collection run rather than skipping just that one malformed record.

### 11. A defensive fallback check that can never actually catch what it's checking for

`collect/comments.py`, lines 397-401:

```python
except CollectionError as e:
    if "commentsDisabled" in str(e) or "disabled" in str(e).lower():
        return results
    raise
```

`_execute()` in `youtube.py` already classifies comments-disabled 403s as `ResourceNotFoundError` (caught separately, one except-clause above this one) via a `.lower()`-normalized check, before it ever falls through to the generic `CollectionError` raise. This second, mixed-case string-match against `CollectionError` is effectively dead defensive code — it duplicates logic that's already handled correctly one level down, in a way that's easy to mistake for working as intended.

### 12. No documented single-writer guarantee for the checkpoint directory

`core/checkpoint.py`'s Tier-1 JSONL appends (`utils.io.append_jsonl`, plain `open(path, "a")`) and Tier-2 `.done`-marker read-then-write pattern (`should_run()` / `mark_done()`) have no file locking. Two concurrent `finfluencer run` invocations against the same `checkpoints/` directory (e.g. an accidental double-launch or an overlapping scheduled job) could race: both could pass `should_run()`'s check before either writes the marker, or both could append to the same JSONL file with interleaved writes. Likelihood is low for the platform's typical single-operator usage pattern, but there's no comment or doc anywhere warning against concurrent invocations, and no lock file to make the failure mode loud instead of silent.

### 13. Broken internal documentation pointer next to the version source of truth

`src/finfluencer/__init__.py`'s docstring: *"See ARCHITECTURE_v2.1.md for the module inventory and freeze policy."* This file does not exist anywhere in the repository (confirmed via search). Low severity on its own, but it sits directly above the `__version__ = "0.1.0"` line — the one attribute the module's own docstring says "end users should depend on" — so it's a visible piece of documentation debt in a very prominent location.

---

## What's genuinely solid (worth stating, not just what's wrong)

No threading, multiprocessing, or asyncio usage anywhere in the codebase — the single-process, synchronous design substantially limits in-process race-condition surface area, which is why the race-condition findings above are limited to cross-process/filesystem concerns rather than in-process ones. `utils/io.py`'s atomic-write pattern (temp file + `os.replace`) is used consistently everywhere state is persisted. No mutable default arguments anywhere in `src/`. The TCMB EVDS provider's custom SSL context (`providers/market/tcmb_evds_provider.py`) starts from Python's secure default context and only adjusts a documented, narrowly-scoped legacy-renegotiation option — not a certificate-verification bypass. `collect/transcripts.py`'s exception mapping in `_default_fetcher()` is genuinely thorough and a good model for how the other three collection stages' error handling could be brought up to the same standard.
