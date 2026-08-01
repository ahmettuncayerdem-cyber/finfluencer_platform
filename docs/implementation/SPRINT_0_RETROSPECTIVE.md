# Sprint 0 Retrospective

**Date:** 2026-08-01
**Scope:** T-001 through T-014 (EPIC-00 through EPIC-02), plus the Foundation Freeze that preceded numbered-task execution.
**Status:** Sprint 0 complete. The Release Verification Checklist (`SPRINT_0_RELEASE_VERIFICATION_CHECKLIST.md`) is operator-approved; T-014 is closed in `BACKLOG.md` as of this document.

---

## What went well

The layer-by-layer build order held up completely. Each task added exactly one layer's worth of Sprint-0-minimal implementation — Domain (T-007), Presentation DTOs (T-008), Application (T-009, T-011), Infrastructure (T-010), API (T-012) — and every later task was able to depend on the previous one's interface without needing to reopen it. Nothing built in an earlier task had to be redesigned once a later task actually used it. `IProjectRepository` (T-009) and `ICollectionRunRepository` (T-011) both turned out to be the right minimal shape on the first attempt; `ICollectionEngine` (T-010) was consumed by `StartCollectionRunOrchestrator` (T-011) exactly as designed.

The "wrapper, not rewrite" discipline for the Legacy Collection Engine worked as intended. `collect/channels.py`, `videos.py`, `comments.py`, `transcripts.py`, and `core/checkpoint.py` were never modified — verified explicitly at every relevant task close via `git status`/`git diff` and a static check that the adapter never monkeypatches or reloads the wrapped modules. The existing checkpoint/resume machinery, built long before this engagement, needed zero changes to support the product-level `CollectionRun` state machine layered on top of it.

The recurring pattern of "IG-001's mechanical checker doesn't cover this layer, so write a dedicated `ast`-based test instead of silently trusting the gap" held up consistently across five separate boundaries (Application in T-009, Infrastructure in T-010, Application again in T-011, and the API Layer's two separate rules in T-012) without ever needing a new kind of test infrastructure — the same fifteen-line `ast.walk` pattern, copied and adapted, every time.

T-013's real-`SIGKILL` interruption test is the single piece of work this sprint is proudest of. It would have been easy to settle for T-010's and T-011's in-process simulated-exception tests and call the reproducibility promise proven. Building a genuine subprocess-kill test instead — with real, unignorable proof (`proc.returncode == -signal.SIGKILL`) that the interruption was uncooperative, not simulated — is a meaningfully stronger claim about the one guarantee `PRODUCT_ARCHITECTURE.md` §1.2 treats as non-negotiable.

## What was harder than expected

Getting T-012's API layer stood up required solving a problem none of the constitutional documents name directly: who is allowed to construct the concrete objects an orchestrator needs injected, when every layer's own forbidden-dependency rule (read literally) forbids it from doing so. `PRODUCT_ARCHITECTURE.md` §12.2's "injected... at startup" line implies a composition root exists, but nothing names it as a seventh thing outside the six layers. Reasoning this out — and then documenting it thoroughly enough that `bootstrap.py`'s placement outside `src/finfluencer/api|application|domain|infrastructure|persistence` reads as a deliberate, load-bearing decision rather than an accidental architecture violation — took real effort and produced the single largest module docstring of the sprint.

The synchronous-vs-asynchronous tension for `StartCollectionRun` surfaced three separate times before it was fully resolved. T-011 first flagged that the orchestrator runs synchronously rather than matching §11.2's stated async contract. T-012 then hit the same tension concretely at the HTTP boundary: `CollectionRunAccepted`'s `status` field is hard-locked to the literal `"queued"`, and a synchronous orchestrator's result is never `"queued"` by the time a response is sent — forcing that literal anyway would have been a wire-level lie, not just an incomplete implementation. Recognizing that early enough to choose `GetCollectionRunResponse` instead, rather than discovering it via a failing Pydantic validation at the last minute, required carrying the T-011 flag forward deliberately rather than treating each task's scope trims as forgotten once the task closed.

The sandbox's own environment (Python 3.10.12 only, no path to a 3.11+ interpreter; a FUSE mount that cannot `unlink()` git lock files) was a constant low-grade tax on every single task, not a one-time cost. Every commit needed a manual lock-clearing step; every test run needed `PYTHONPATH=src` instead of a real editable install; several dependencies needed on-demand `pip install --break-system-packages` rather than a clean `poetry install --sync`. None of this ever blocked correctness, but it added friction to literally every verification step across all fourteen tasks, and the httpx 0.28.1-vs-`^0.27` mismatch discovered during T-012 is a direct symptom of this same underlying constraint (a standalone `pip install` had drifted from what `pyproject.toml` actually declares, with nothing enforcing the two stay in sync in this environment).

## Assumptions validated

The Roadmap's own confidence classification — Collection Engine as "Wrapper required," the highest-confidence reuse category — held up under direct, adversarial testing, not just inspection. T-013's real-crash test is exactly the kind of evidence §12's Architect's Review asked for ("reuse confidence does not transfer automatically to the ported form... new integration tests required regardless of existing unit-test coverage," Risk R-3) and it passed.

The Domain-defines/Infrastructure-implements interface pattern (established for `IAIProvider` in the architecture, replicated here for `ICollectionEngine`, `IProjectRepository`, `ICollectionRunRepository`) generalized cleanly to a third and fourth case with no friction. This is reasonably strong evidence the pattern will keep working as more repositories/adapters are added in later sprints.

ADR-0002's per-`run_id` checkpoint partitioning, designed in T-010 against Risk R-1's stated concern, turned out to compose perfectly with T-011's later need for "every `CollectionRun` owns its own checkpoint_root" — no rework was needed when the two tasks' concerns actually met. Using the `CollectionRun` entity's own `id` as the `run_id` was the obvious, correct choice once both pieces existed, exactly as ADR-0002 anticipated it would be.

## Assumptions disproved

The original assumption that a "minimal frontend" (T-012) would be a small, self-contained UI task turned out to be wrong — it was actually the task that finally forced the API Layer and a composition-root pattern into existence, work that earlier tasks had been implicitly deferring onto it without saying so explicitly. T-012's effort was closer to "stand up the first cross-cutting layer" than "add a form to an existing page."

The assumption that `StartCollectionRunOrchestrator`'s synchronous-execution simplification was a narrow, contained trade-off (flagged once in T-011 and forgotten) was also wrong — it had a second, concrete consequence one layer up (the `CollectionRunAccepted` vs. `GetCollectionRunResponse` choice in T-012) that had to be reasoned through again, not just cited.

## Technical debt introduced

No Persistence Layer implementation exists anywhere yet. Every repository this sprint (`IProjectRepository`, `ICollectionRunRepository`) has only ever been satisfied by in-memory test doubles or, in T-012's `bootstrap.py`, an in-memory stand-in relocated into a runnable process — non-durable, single-process, lost on restart. This is the largest single piece of debt carried out of Sprint 0, and it is the direct cause of several smaller items below.

`api.middleware.idempotency` does not exist — `CreateProject` submitted twice with the same idempotency key creates two Projects (proven, not hidden, by `test_routes_identity.py`). `StartCollectionRun` does not share this gap, since T-011's orchestrator already performs idempotent dispatch internally, independent of any API-layer middleware.

`StartCollectionRunOrchestrator` runs synchronously rather than matching §11.2's asynchronous contract — no `IJobDispatcher` exists yet. `ResumeCollectionRun` (named as its own orchestrator in §12.3) has no standalone implementation; resume is only reachable through `StartCollectionRun`'s own idempotent-replay-of-a-failed-run path.

No `IDatasetRepository` exists, and `StartCollectionRunOrchestrator` constructs `CollectionRun` directly against a `dataset_id` rather than loading and mutating a live `Dataset` aggregate via `add_collection_run()` — the full aggregate-consistent pattern §10.1 describes needs real Persistence to exist first.

Eleven of `PRODUCT_ARCHITECTURE.md` §10.1's fifteen Domain entities remain unimplemented (`User`, `TenantMembership`, `ProjectMembership`, `VerticalTemplate`, `AnalysisType`, `AnalysisRun`, `InterpretationRecord`, `Report`, `Export`, `Subscription`, `AuditLogEntry`) — each has a TODO comment citing its exact future attachment point, but none exist in code.

The frontend is a single static HTML file with vanilla JS, not the ADR-0001-decided React+TypeScript stack — a deliberate, flagged deferral, not an oversight, but still a gap between what ADR-0001 accepted and what exists.

No live, network-backed `PlatformProvider` exists — `FixtureCollectionProvider` is the only implementation wired in anywhere. This is squarely Sprint 1's first task (T-015), not a surprise, but it means nothing in this sprint has ever actually talked to the real YouTube Data API.

## Technical debt retired

F-001 (no constitutional or governance document had ever been committed to version control) was resolved via the Foundation Freeze, before numbered-task execution began — nine planning/governance files committed across eight commits, tagged `platform-foundation-v1`.

The `GetCollectionRun`/`GetCollectionRunStatus` naming inconsistency was resolved in `BACKLOG.md` and in code comments during the pre-T-009 architectural preparation pass — the canonical name (`GetCollectionRun`, matching `PRODUCT_ARCHITECTURE.md` §11.2 line 684 exactly) is now used consistently everywhere except `IMPLEMENTATION_ROADMAP.md` itself, which remains frozen (see F-002, still open, below).

The missing `AnalysisType` TODO citation (T-007's one Recommended finding from its architectural review) was added, closing that review's single open item.

The `httpx` 0.28.1-vs-`pyproject.toml`'s-own-`^0.27`-constraint mismatch, discovered during T-012, was corrected by downgrading the sandbox's installed version to comply with what the project already declares — an environment drift fixed, not a new decision made.

## Risk register updates

Risk R-1 (checkpoint concurrency assumption vs. a horizontally-scaled Worker Tier) is resolved for the Collection Engine adapter specifically, via ADR-0002's per-`run_id` partitioning, proven by a dedicated isolation test. R-1 itself — the general assumption inside `core/checkpoint.py` — remains open as a standing constraint on that file; this sprint resolved one consumer of it, not the underlying assumption.

Risk R-3 ("reuse confidence does not transfer automatically to the ported form") is now backed by the strongest evidence this sprint produced: not just T-010's in-process simulated-crash test, but T-013's genuine subprocess `SIGKILL`, run and passed five consecutive times with no flakiness.

Risks R-2 (AnalysisScope reconciliation), R-4 (AI cost), R-5 (tenant isolation), and R-6 (vertical coupling) are unchanged — none were in scope for any Sprint 0 task, and none were touched.

`IMPLEMENTATION_ROADMAP.md` itself was never edited to record any of the above, despite Playbook Part G's own worked example treating Risk-Register status updates as routine, non-ceremonial edits. This engagement held the stricter line (frozen constitutional document, no edits without explicit operator authorization) throughout, established via the F-002 precedent and reaffirmed at T-010's close. The operator has not yet responded to the standing question of whether to grant a routine exception for this specific kind of edit — carried forward, unresolved, into this retrospective.

## Lessons learned

Flagging a scope trim once, in the task that first makes it, is not enough if a later task will concretely depend on the same trim — T-011's synchronous-execution flag needed to be actively re-applied, not just cited, when T-012 hit its HTTP-boundary consequence. Carrying flagged simplifications forward by name, not just by reference, is worth the extra sentence every time.

Writing the "why doesn't the mechanical checker cover this" explanation directly into the module docstring — not just the test file — made every later instance of the same pattern faster to write and easier to trust, since the reasoning was already there to copy from rather than being re-derived from scratch each time.

A composition root is not an edge case this architecture happened to need once; it is a structural requirement of strict layer-inversion designs, and it would have been better to name it explicitly somewhere in `PRODUCT_ARCHITECTURE.md` §12 rather than discovering the need for it mid-implementation. Worth surfacing to the operator as a documentation gap in the constitutional document itself, distinct from anything this sprint's code needed to solve.

## Recommendations for Sprint 1

Resolve the accumulated cross-vendor review debt before Sprint 1's live-API work compounds it further — see the Sprint 1 Readiness Assessment for the specific reasoning on why this matters more once real quota and real external credentials are involved.

Decide F-002 (the `IMPLEMENTATION_ROADMAP.md` naming error) and the standing Risk-Register-edit-authorization question — both are cheap, contained decisions that have been sitting open since T-008 and T-010 respectively, with no technical urgency but growing archival awkwardness the longer they're deferred.

Treat the Persistence Layer as the highest-leverage piece of technical debt to retire early in Sprint 1 or Sprint 2, even though no currently-scheduled task forces it yet — nearly every other deferred item this retrospective lists (`IDatasetRepository`, `api.middleware.idempotency`, genuine async dispatch, multi-process deployment) is blocked on it existing.
