# T-017 Migration Risk Checklist — Real-world interruption test against a live run

**Scope:** prove T-013's interruption/resume guarantee holds when the injected provider is the
real, retry-wrapped `YouTubePlatformProvider` (T-015, T-016) instead of `FixtureCollectionProvider`
— and, separately, that T-016's retry logic operates transparently inside that same real chain.

## What "live" means here, precisely

Two distinct things are commonly conflated under "live," kept separate deliberately:
1. **Real code path** (registry → `build_provider_and_quota` → `YouTubePlatformProvider` →
   `CollectionEngineAdapter` → `collect/*.py`), with only the network transport
   (`googleapiclient.discovery.build`) stubbed at the child-process boundary — the same technique
   `test_live_provider.py` (T-015) already used, moved into a subprocess so a real `SIGKILL` can be
   delivered without also killing the test runner. **This is deterministic and CI-safe.**
2. **Real network egress** to `googleapis.com`, with genuine variable timing. **Confirmed
   unavailable in this sandbox** (T-015: proxy returns `403` on `CONNECT`, verified by `curl` and
   by a real `httplib2.socks.HTTPError` deep in `scripts/t015_live_smoke_test.py`). Nothing has
   changed about this constraint since T-015; not re-verified here, per operator instruction to
   preserve unchanged environment limitations rather than re-litigate them.

## Assumptions

- T-013's own scope note applies unchanged: the repository record showing a run as `failed` is
  pre-seeded (test double stands in for Persistence), modeling a worker process crashing while a
  separate orchestrator process holds the record. Not re-litigated.
- Single analyst (`satiroglu`, same pilot channel as T-015/T-016) — minimizes any real quota spend
  for the eventual real-network run, consistent with T-015's own Migration Risk decision. Trade-off
  flagged: this makes the "no duplicate rows" assertion after resume less rich than T-013's
  (4 analysts) — still correctly proves no duplication, just with less redundancy.
- Interruption window is opened between the channels stage (single call, one analyst) completing
  its checkpoint and the videos stage beginning — using the same test-only sleep-injection
  technique as `_t013_worker.py`'s `_SlowProvider`, now wrapping the live-wired provider instead of
  the fixture one. Not a retry/backoff mechanism; a timing device only.
- Retry-under-real-chain is proven by injecting a controlled transient failure (429) into the stub
  network response for the first call only — the resulting behavior (call succeeds on retry, run
  completes) is what T-016 already guarantees at the unit level; this test proves it survives
  being run through the full subprocess/adapter/checkpoint chain, not just in isolation.

## Provider contract stability

`PlatformProvider` Protocol (`providers/platform/base.py`) is not modified. `YouTubePlatformProvider`
is not modified by this task (T-016 already added retry; T-017 adds no new provider code, only a
test-only sleep-wrapper decorator, same shape as T-013's `_SlowProvider`).

## Checkpoint / idempotency guarantees

Unchanged — proven again, not re-designed, exactly as T-013 already established for the fixture
path. `CollectionEngineAdapter`, `CheckpointManager`, `StartCollectionRunOrchestrator`,
`CollectionRun` are not modified.

## Decision

Proceed with a deterministic, stub-network subprocess test (kill+resume, and retry-survives-the-
real-chain) as the CI-safe half of this task's Verification line. Provide a small manual script
(`scripts/t017_live_interruption_manual.py`, not a pytest test, reusing the same worker script with
`stub_network=0`) for the operator to run personally in an environment with real egress — mirroring
the T-014/T-015 human-verification precedent. Stop there; do not attempt to simulate "real, variable
network timing" artificially, since that would be speculative, not evidence.
