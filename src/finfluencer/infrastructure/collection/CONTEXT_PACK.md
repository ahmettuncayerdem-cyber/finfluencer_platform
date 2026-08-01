# Context Pack — Collection Engine Infrastructure Adapter

Full workflow: `IMPLEMENTATION_PLAYBOOK.md` Part B.2.

## Purpose

Implements `finfluencer.domain.collection_engine.ICollectionEngine` by wrapping the existing,
tested four-stage Collection Engine (`finfluencer.collect.channels/videos/comments/transcripts`)
and `finfluencer.core.checkpoint.CheckpointManager`, unmodified, behind one adapter class
(`CollectionEngineAdapter`). Exists so a future Application-layer orchestrator (`StartCollectionRun`,
BACKLOG.md T-011) can trigger a full collection run through one Domain-safe method call
(`ICollectionEngine.run(run_id)`) without knowing or caring that the implementation is `collect/`
+ a `PlatformProvider`, per `PRODUCT_ARCHITECTURE.md` §11.2's Collection Service contract.

## Domain entities and invariants owned or touched

Owns no `PRODUCT_ARCHITECTURE.md` §10.1 entity directly. Touches none of `Tenant`/`Project`/
`Dataset`/`CollectionRun` (`finfluencer.domain.entities`) -- this adapter runs collection and
returns a plain `CollectionOutcome` summary; mapping that outcome onto a `CollectionRun`'s
lifecycle (`queued -> running -> completed | failed`, §10.1 line 567) is Application/Domain's
job in a future task (T-011), not this one's.

## API Contract operations implemented

None directly. This adapter is what a future `StartCollectionRunOrchestrator` will call
internally to satisfy the `StartCollectionRun` command (§11.2 line 683) — it implements the
Infrastructure seam that command's Application-layer implementation will depend on, not the
command itself.

## Guardrails that bind this module

- **IG-001** (layer-direction): this adapter imports `finfluencer.collect.*`,
  `finfluencer.core.*`, `finfluencer.providers.platform.base`, and
  `finfluencer.domain.collection_engine` only. It does not import Presentation or API — not
  mechanically checked for the `infrastructure` layer by `scripts/check_layer_dependencies.py`
  today (only `presentation`/`api`/`domain` are), but enforced here by a dedicated `ast`-based
  test (`tests/unit/test_infrastructure/test_collection/test_collection_engine_adapter.py::
  test_adapter_module_does_not_import_presentation_or_api`), honoring
  `PRODUCT_ARCHITECTURE.md` §12.1 line 845's textual rule regardless of the checker's current
  coverage.
- **BKG-001** (business rules stay in Application/Domain): the stage sequencing inside
  `CollectionEngineAdapter.run()` (channels → videos → comments → transcripts) is the
  *existing*, already-tested order `collect/main.py::run_pipeline` already used — reused
  verbatim, not a new business rule authored at this layer. See "Integration decisions" below
  for the judgment call this required.

## Integration decisions (existing-engine code, if any)

- `finfluencer.collect.channels/videos/comments/transcripts` + `finfluencer.core.checkpoint.
  CheckpointManager` — **Wrapper required** (`IMPLEMENTATION_ROADMAP.md` §3's Collection Engine
  row). Called unmodified, exactly as they exist today; zero lines changed in any of these
  files by BACKLOG.md T-010.
- `finfluencer.providers.platform.youtube.YouTubePlatformProvider` — **wrapped as of T-015**
  (`live_provider.py`, `build_live_collection_engine`). Confirms the prediction made when this
  line was first written: the swap required zero changes to `CollectionEngineAdapter` itself.
  T-015 reuses `finfluencer.collect.main.build_provider_and_quota(cfg)` — the same factory
  `run_pipeline` already used — rather than hand-constructing `YouTubePlatformProvider`, so the
  registry lookup (`cfg.settings.providers.platform == "youtube"`) and `QuotaTracker`
  construction stay centralized in one place. `FixtureCollectionProvider` remains the default
  wiring for `bootstrap.py` (T-012, Sprint 0, untouched) — the live path is opt-in, constructed
  explicitly by a caller (see `scripts/t015_live_smoke_test.py`), not a replacement default,
  since standing it up by default would spend real API quota on every dev-page load.
- **Judgment call, flagged explicitly:** `PRODUCT_ARCHITECTURE.md` §12.1 describes Application
  as owning "sequencing" (line 827) and Infrastructure as implementing interfaces (lines
  842-848). `CollectionEngineAdapter.run()` sequences four stage calls internally, which could
  be read as sequencing belonging one layer up. The reasoning for keeping it here: this is not
  a *new* sequencing decision — it is the legacy engine's own, already-established,
  already-tested stage order, reused wholesale as one Infrastructure capability ("run a
  collection"), matching `IMPLEMENTATION_ROADMAP.md` §3's own framing ("an Application-layer
  orchestrator... around the existing Infrastructure logic — not a rewrite of the logic
  itself"). If a fresh-context/cross-vendor review (`IMPLEMENTATION_PLAYBOOK.md` Part B.1,
  mandatory for this diff and not yet performed) disagrees, splitting `run()` into four
  separately-callable single-stage methods for T-011 to sequence itself is a low-cost
  follow-up, not a sign BKG-001 was violated — no new business *rule* was authored either way.

## Known technical debt

- **Roster-wide run granularity, not yet reconciled with per-`Dataset` `CollectionRun`.** The
  legacy engine collects for the *entire configured analyst roster* in one invocation;
  `PRODUCT_ARCHITECTURE.md` §10.1 scopes one `CollectionRun` to one `Dataset`. This mapping is
  explicitly deferred to T-011 (Application-layer sequencing, per BKG-001) — not resolved here.
  Revisit trigger: when T-011 is implemented.
- **`anon_salt` sourced from an environment variable by default** (`ANON_SALT`, matching
  `collect/main.py::run_pipeline`'s existing behavior exactly) — unchanged legacy behavior, not
  a new secret-handling decision, but worth a fresh look whenever secret management is
  formalized (`PRODUCT_ARCHITECTURE.md` §16.19).
- **Retry loop implemented (T-016), closing the gap T-015 found.** `youtube.py::_execute` now
  wraps the existing HTTP-error → typed-exception classification (`_execute_once`, renamed from
  the old `_execute` body) in a `tenacity.Retrying` loop, retrying only `RateLimitError`/
  `NetworkError` with bounded attempts and exponential backoff; `QuotaExhaustedError`,
  `ResourceNotFoundError`, `CommentsDisabledError`, `AuthenticationError` propagate on the first
  attempt, unchanged. Three new optional constructor kwargs (`retry_max_attempts`,
  `retry_wait_initial_sec`, `retry_wait_max_sec`), all with conservative production defaults —
  no existing caller (`build_provider_and_quota`, `live_provider.py`, the registry) needed to
  change. Deliberately implemented *inside* `youtube.py` rather than as a wrapping decorator: the
  `PlatformProvider` Protocol's own docstring (`providers/platform/base.py`) already states
  "Transient errors are retried inside the implementation before propagating" — a decorator would
  have contradicted that existing contract rather than fulfilled it.
- **Live-network half of T-015's own Verification line could not be executed in the
  implementation sandbox** — that sandbox's outbound proxy returns `403` on `CONNECT` to
  `googleapis.com` (confirmed via direct `curl`, and again via a real `httplib2.socks.HTTPError`
  deep inside `scripts/t015_live_smoke_test.py`'s own execution). This is an environment
  constraint, not a code defect: the entire wiring chain (registry → `YouTubePlatformProvider`
  construction → `QuotaTracker` → `CollectionEngineAdapter` → `collect/*.py` stages) is proven
  correct up to the network boundary by `tests/unit/test_infrastructure/test_collection/
  test_live_provider.py`'s stubbed-client tests. Revisit trigger: run
  `scripts/t015_live_smoke_test.py` in an environment with real egress to `googleapis.com`.
- **T-017: real-`SIGKILL` interruption/resume proven against the live-wired chain, network
  transport stubbed.** `tests/integration/test_t017_live_interruption.py` + `_t017_worker.py`
  extend T-013's real-subprocess-kill technique to the live-provider path (T-015/T-016) instead
  of `FixtureCollectionProvider` — only `googleapiclient.discovery.build` is stubbed (same
  boundary `test_live_provider.py` already stubs), so the registry, `YouTubePlatformProvider`
  (including T-016's retry loop), `QuotaTracker`, `CollectionEngineAdapter`, and
  `CheckpointManager` all run for real. Also proves a transient 429 on the very first network
  call still lets the run complete, through this same full chain. The genuine real-network,
  real-timing half remains environment-blocked in this sandbox (same proxy constraint as T-015,
  re-confirmed via `scripts/t017_live_interruption_manual.py`, not a new finding) — revisit
  trigger: run that script in an environment with real egress.

## Gotchas

- `collect_comments` raises `CollectionError` if `anon_salt` resolves to an empty string —
  tests must pass a non-empty `anon_salt` explicitly (a test fixture value, not a real secret);
  relying on the `ANON_SALT` environment variable being unset will fail loudly, by design
  (matches legacy `collect/main.py` behavior exactly).
- Fixture data (`fixture_data.py`) is keyed to the *real* `config/analysts.yaml` roster
  (`satiroglu`/`yesilada`/`basaran`/`gecer`) so tests can load real `config/settings.yaml` /
  `config/analysts.yaml` via `finfluencer.core.config.load_settings` exactly as the existing
  test suite already does — there is no separate, parallel fixture Settings object. Adding a
  fifth analyst to `config/analysts.yaml` without adding matching fixture data will make
  `FixtureCollectionProvider.resolve_channel` raise `ResourceNotFoundError` for that analyst.
- `CollectionEngineAdapter._paths_for(run_id)` is the one place Roadmap Risk R-1's
  checkpoint-partitioning discipline is enforced — do not add a code path that lets two
  distinct `run_id`s resolve to the same `checkpoint_root`.
- **`tests/conftest.py`'s `autouse=True` `_reset_registry` fixture only re-imports the
  `language` provider subpackage after clearing the registry, not `platform`** (T-015 finding).
  Any test that exercises registry-based `platform` lookup (i.e. `build_provider_and_quota`,
  hence `build_live_collection_engine`) in isolation must re-register `platform:youtube` itself
  — see `test_live_provider.py::_ensure_youtube_provider_registered` for the pattern (an
  `autouse` fixture that depends on `_reset_registry` by name, then calls
  `register("platform", "youtube")(YouTubePlatformProvider)` directly). `conftest.py` itself was
  deliberately left unmodified — this is shared test infrastructure outside T-015's scope, and
  the local workaround is sufficient.
