# ADR 0001-A — SQLite Backend for v1 Persistence (Amendment to ADR-0001)

**Date:** 2026-08-07
**Status:** Accepted — 2026-08-07 (BACKLOG.md EPIC-07'; operator instruction: "Approved... using
SQLite as the initial persistence backend. This is a deliberate product decision, not a
temporary shortcut.")
**Drafted by:** Claude, grounded in direct inspection of `domain/repositories.py`'s six
interface Protocols and `bootstrap.py`'s in-memory stand-ins, per the operator's explicit
instruction to preserve those interfaces exactly.
**Relationship to ADR-0001:** amendment, not a reversal. ADR-0001's own Decision table named
PostgreSQL for the eventual multi-tenant SaaS deployment; this ADR scopes the *first* concrete
Persistence implementation to a different, earlier deployment stage that ADR-0001 did not yet
distinguish from the eventual production one.

## Context

`persistence/` has been empty since Sprint 0 by deliberate operator instruction ("No Persistence
implementation," BACKLOG.md T-012). `bootstrap.py`'s six in-memory repositories
(`_InMemoryProjectRepository` etc.) are non-durable — state is lost on every process restart.
The operator has now authorized real persistence, explicitly scoped: "Do not introduce
authentication, multi-user assumptions, or cloud-specific complexity at this stage. The primary
objective is durable storage of projects, collection runs, analysis runs, reports, and
provenance while maintaining the current architecture."

ADR-0001 already named PostgreSQL + SQLAlchemy 2.0 (async) for the platform's eventual database.
Read literally, that appears to conflict with using SQLite now. It does not, for a reason worth
stating precisely rather than glossed over: ADR-0001's own reasoning for rejecting SQLite was
explicit — "SQLite is disqualified by BKG-001/multi-tenant concurrency needs **past Sprint 0**"
(emphasis added; ADR-0001 §Reasoning). That sentence is a claim about the *multi-tenant,
concurrent-write* production deployment ADR-0001 was scoping — a deployment stage that, per the
operator's own instruction above, is explicitly *not* what is being built right now. ADR-0001
did not separately evaluate "what should back a single-user research tool with no concurrent-
tenant writes," because that deployment stage was not yet distinguished from the eventual
production one when it was written.

## Decision

| Category | ADR-0001 (production, multi-tenant) | This amendment (v1, single-user) |
|---|---|---|
| Database | PostgreSQL | **SQLite** |
| ORM | SQLAlchemy 2.0 (async) | SQLAlchemy 2.0 (**sync**) |
| Migrations | Alembic | Alembic (unchanged) |
| Concurrency model | Multi-tenant, concurrent writers | Single-user, FastAPI's sync-threadpool concurrency only |

**SQLite**, not PostgreSQL, for the reasons ADR-0001 itself already implies once the deployment
stage is separated out: there is no concurrent-tenant write load to serve (no Auth, no
multi-user, per the operator's explicit scope above), no operational benefit to running a
separate database server process for a tool one researcher runs on their own machine, and a
real, concrete cost to doing so anyway — a Postgres dependency would mean every researcher
who wants to run this platform needs to additionally install, configure, and keep running a
database server, a real adoption/friction cost for a research tool with no compensating
benefit at this deployment stage.

**Sync SQLAlchemy, not async.** `bootstrap.py`'s orchestrators (`CreateProjectOrchestrator`,
`StartCollectionRunOrchestrator`, etc.) are all plain synchronous Python — none of the six
repository interfaces in `domain/repositories.py` are declared `async def`. Introducing an async
ORM underneath synchronous interfaces would need either a sync-over-async bridge (added
complexity for no benefit, since nothing upstream is actually async yet) or changing the
interfaces themselves — the second directly contradicts the operator's explicit instruction to
"preserve all existing repository interfaces so the change remains an implementation swap only."
Async SQLAlchemy remains the correct target if/when the orchestrator layer itself goes async
(e.g., alongside a real background-job runner, per ADR-0001's Redis/arq row, itself still
unbuilt) — not a reason to introduce async at this one layer in isolation now.

**Alembic, unchanged from ADR-0001.** SQLAlchemy's own standard migration tool works identically
against SQLite and PostgreSQL; no separate decision needed.

## Forward-compatibility guarantee (the concrete, checkable part of this ADR)

Every ORM model in `persistence/models.py` uses only dialect-portable SQLAlchemy column types
(`Uuid`, `String`, `Integer`, `DateTime`, `Text`) — no SQLite-specific type is used anywhere.
Every repository implementation depends only on the SQLAlchemy Core/ORM query API, not on any
SQLite-specific SQL. Migrating to PostgreSQL later is, by construction, a connection-string and
driver-package change (`sqlite:///...` → `postgresql+psycopg://...`, plus installing `psycopg`)
— **not** a change to `persistence/models.py`, the six repository classes, or anything in
`application/`, `api/`, or `domain/`. This is the literal mechanism behind the operator's
requirement that "a future PostgreSQL backend can be introduced without changes to the
application layer."

## Consequences

- `persistence/` is no longer empty; six concrete repository implementations exist behind the
  existing `IProjectRepository`/`ICollectionRunRepository`/`IAnalysisRunRepository`/
  `IReportRepository`/`IInterpretationRecordRepository`/`IExportRepository` Protocols.
- `bootstrap.py`'s `create_app()` gains a `db_url` parameter; default behavior (no `db_url`
  passed) creates a fresh, isolated temporary SQLite file per call — preserving every existing
  test's isolation assumption unchanged (see `t029_e2e_verification.py` check 10a, updated to
  describe this accurately rather than describe a "no Persistence Layer" state that is no longer
  true). Real, cross-restart durability requires explicitly passing a stable `db_url` — an
  opt-in, not a silent default change.
- `pyproject.toml` gains `sqlalchemy` and `alembic` as runtime dependencies (§ Runtime
  dependencies, "Persistence" group).
- A future decision to reintroduce multi-tenant/Auth scope (EPIC-07-original, T-030–T-032)
  should re-open the PostgreSQL question at that time — not before, and not implicitly.

## Rejected alternatives (brief)

- **PostgreSQL now, per ADR-0001's literal table** — rejected per this ADR's own reasoning above:
  ADR-0001's stated rationale for Postgres was multi-tenant concurrency, explicitly out of scope
  at this deployment stage per the operator's own instruction.
- **A JSON-file or pickle-based store (skip SQL entirely)** — rejected: would not deliver real
  queryability (`listProjects`, `listReportsForProject`, comparative analytics per
  `docs/implementation/BACKLOG_REPRIORITIZATION_2026-08.md` EPIC-09) and would need its own
  migration/versioning story invented from scratch rather than reusing Alembic, a mature,
  standard tool.
- **Async SQLAlchemy now, ahead of need** — rejected per this ADR's reasoning above: no upstream
  async interface exists yet to justify it, and it would force a repository-interface change the
  operator explicitly instructed against.
