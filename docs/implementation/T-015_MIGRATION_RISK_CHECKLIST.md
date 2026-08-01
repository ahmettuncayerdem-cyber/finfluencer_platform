# T-015 Migration Risk Checklist — Replace fixture adapter with live YouTube Data API calls

**Scope:** wire `YouTubePlatformProvider` (already implemented, already tested, `src/finfluencer/providers/platform/youtube.py`) into `CollectionEngineAdapter` (T-010, unmodified) in place of `FixtureCollectionProvider`, for real collection against a live channel.

## Assumptions

- `CollectionEngineAdapter` needs zero code changes — it already depends on `PlatformProvider` as a Protocol (T-010's own Context Pack: "a real, network-backed provider adapter is a pure constructor-argument swap... no change to this class"). Confirmed correct on inspection.
- A real `YT_API_KEY` exists in this repository's `.env` (verified present, non-empty).
- **This sandbox's network egress does not reach `googleapis.com`** — verified directly: `curl` to `www.googleapis.com` returns `403 from proxy after CONNECT`, distinct from an API-level 403 (quota/auth). This is an environment constraint, not a code defect, and it means the actual live-network half of this task's Verification line ("live collection run against a small real channel") cannot be executed to completion inside this sandbox.

## Legacy contracts being reused, not rewritten

- `finfluencer.providers.platform.youtube.YouTubePlatformProvider` — concrete, tested `PlatformProvider` implementation. Already handles channel resolution, video enumeration/metadata, comment fetching, anonymization at ingest, and typed error classification (`QuotaExhaustedError`, `RateLimitError`, `CommentsDisabledError`, `NetworkError`, `ResourceNotFoundError`).
- `finfluencer.collect.main.build_provider_and_quota(cfg)` — the *existing*, already-used factory that instantiates the configured platform provider (via the registry, `cfg.settings.providers.platform == "youtube"`) together with a persisted `QuotaTracker`. T-015 calls this directly rather than hand-constructing `YouTubePlatformProvider` itself.
- `config/analysts.yaml`'s pilot analyst (`satiroglu`, real, verified `channel_id`) is the "small real channel" this task targets for any live smoke test — not the full four-analyst roster, to keep quota spend minimal.

## Checkpoint behavior

Unchanged. `CollectionEngineAdapter._paths_for(run_id)` and `CheckpointManager` are not touched by this task; ADR-0002's per-`run_id` partitioning applies identically regardless of which `PlatformProvider` is injected.

## Retry semantics

**Finding, not yet acted on (T-016's job):** `youtube.py`'s own module docstring states "Retry policy. Only transient errors (RateLimit, NetworkError) are retried" — but no retry loop or `tenacity` usage exists anywhere in `providers/platform/youtube.py` or `collect/*.py` today (confirmed via search). The docstring describes intended behavior that `T-016` has not yet been implemented to satisfy. Not addressed by T-015 — noted here so it is not mistaken for new information discovered later.

## Idempotency expectations

Unchanged. Idempotent dispatch is proven at the Application layer (T-011) and does not depend on which provider is wired into the adapter.

## Interruption/resume guarantees

T-013 proved this against fixture data with a real `SIGKILL`. T-015 does not re-prove it against live data — that is T-017's explicit job. T-015 only needs to confirm the wiring is correct; a live interruption/resume proof is out of this task's scope.

## Decision

Proceed with implementation: build the live-provider wiring, prove it with a stubbed-client test (matching the existing test technique in `tests/unit/test_providers/test_youtube.py` — a fake `client_factory`, no real network), attempt the genuine live smoke test and document its actual outcome (expected: blocked by this sandbox's proxy), and hand off completion of the live-network verification to the operator or a CI environment with real egress. This is an environment gap, the same category already established for T-002/T-003/T-014 — not a reason to stop implementation.
