# T-016 Migration Risk Checklist — Quota/rate-limit handling and retry policy

**Scope:** implement the retry behavior `youtube.py`'s own docstring already documents but never
implements ("Only transient errors (RateLimit, NetworkError) are retried; `QuotaExhaustedError`
and `ResourceNotFoundError` propagate") and the `PlatformProvider` Protocol's own contract
(`base.py`: "Transient errors are retried inside the implementation before propagating").

## Design decision, flagged explicitly

Two options were possible: (A) add the retry loop inside `youtube.py::_execute` directly, or
(B) a new decorator class wrapping any `PlatformProvider`. **Chosen: (A).** The Protocol's own
docstring states retries happen "inside the implementation," not at a wrapping layer — a decorator
would contradict that already-documented contract, not just add to it. This keeps the change
surgical: `_execute`'s existing HTTP-error → typed-exception classification is reused verbatim;
only the retry loop around calling it is new. No new abstraction, no new file, no change to
`CollectionEngineAdapter`, `live_provider.py`, or `collect/*.py`.

## Retry semantics — reusing documented behavior, not inventing new rules

- Retried: `RateLimitError`, `NetworkError` (exactly the two named in `youtube.py`'s own
  docstring).
- Not retried, propagate immediately: `QuotaExhaustedError`, `ResourceNotFoundError`,
  `CommentsDisabledError`, `AuthenticationError`, generic `CollectionError` — matches "only
  transient errors are retried."
- `tenacity` (`^8.2`, already an approved dependency, Baseline Report §3) provides the loop.
  Bounded attempts + exponential backoff, both new constructor kwargs with conservative defaults
  (`retry_max_attempts=3`, small initial/max wait) so no test or caller is forced to opt in.

## Checkpoint / idempotency / interruption guarantees

Unchanged. Retry happens entirely inside one provider method call, below
`CollectionEngineAdapter` and `CheckpointManager` — from their perspective a retried call that
eventually succeeds is indistinguishable from one that succeeded on the first attempt, and a
retried call that eventually fails is indistinguishable from an immediate failure. Reproducibility
Checklist (Playbook Part F) is satisfied by construction, not re-verified by new interruption
testing — that remains T-017's job.

## Test impact

`tests/unit/test_providers/test_youtube.py::TestExecuteErrorClassification`'s existing cases use a
`_RaisingRequest` that always raises — with retry added, the `RateLimitError`/`NetworkError`
cases will now retry `retry_max_attempts` times before propagating the same exception type, adding
bounded, small latency (conservative defaults keep this on the order of ~1-2s total across the
affected cases) but not changing the asserted exception type. Left unmodified; new tests added
alongside for actual retry-then-succeed and no-retry-on-non-transient-error behavior.

## Decision

Proceed: modify `_execute` only, add three optional keyword constructor parameters with defaults
that preserve current behavior for every existing caller (`build_provider_and_quota`, the
registry, `live_provider.py`, all existing tests).
