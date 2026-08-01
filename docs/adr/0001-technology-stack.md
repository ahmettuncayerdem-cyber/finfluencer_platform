# ADR 0001 — Technology Stack for the Six-Layer Platform

**Date:** 2026-08-01
**Status:** Accepted — 2026-08-01 (BACKLOG.md T-004; Playbook Part E, ADR Policy: Claude drafted, human decided). This ADR is not reopened by acceptance — the open question noted below (React vs. Svelte/Vue) is accepted as-is, not resolved further, per the operator's explicit instruction not to redesign it.
**Drafted by:** Claude, grounded in direct inspection of `pyproject.toml` and the existing `src/finfluencer/` codebase, not a from-scratch survey.

## Context

`PRODUCT_ARCHITECTURE.md` §16 deliberately left implementation technology unspecified — cloud-neutral, no mandated container/orchestration platform, no named language beyond what the existing CLI already commits to. That neutrality was correct at the architecture layer. It cannot stay open past T-004: `T-005` (wire IG-001 into CI) and `T-006` (scaffold the six-layer package skeleton) both need to know what they're scaffolding. This ADR closes that gap for the categories the architecture left open, using what the current repository already proves rather than a greenfield survey.

## Decision

| Category | Choice | Status |
|---|---|---|
| Core language | Python (existing) | Not a new choice — carried forward |
| API/web framework | FastAPI | New |
| Database | PostgreSQL | New |
| ORM / DB access | SQLAlchemy 2.0 (async) | New |
| Cache / job-queue backend | Redis | New |
| Background job runner | arq (Redis-backed, asyncio-native) | New |
| Frontend | React + TypeScript | New |
| Auth (MVP) | First-party JWT session tokens, issued by the API itself | New |
| Packaging | Docker (portability only — no orchestrator mandated) | New |
| CI | GitHub Actions | New |

## Reasoning

**Python stays the core language.** Not really a decision — 812 lines of `core/contracts.py`, the entire Collection/Analysis/Reporting pipeline, and every reuse classification in `IMPLEMENTATION_ROADMAP.md` §3 assume it. Rewriting any of that in another language would contradict the roadmap's own reuse-first premise for no offsetting benefit.

**FastAPI, not Flask or Django.** The deciding fact is already in the repo, not a framework popularity comparison: `core/contracts.py` is Pydantic v2, `extra="forbid"`, load-bearing for the whole reproducibility story. FastAPI's request/response validation *is* Pydantic — adopting it costs zero new validation paradigm, versus translating an established, tested contract style into Django's forms/serializers or hand-rolling it in Flask. Async-native, which the existing `httpx` dependency (already declared for "concurrent market-data retrieval… in later phases") anticipates.

**PostgreSQL, not a NoSQL store or SQLite.** The Domain Model (§10.1) is relational by construction — `AnalysisRun` pins to exactly one `CollectionRun`, `Report` cites immutable `InterpretationRecord` entities, tenant isolation (§14.7, T-032) needs real foreign-key and row-level enforcement, not application-level convention. SQLite is disqualified by BKG-001/multi-tenant concurrency needs past Sprint 0; a document store would mean reimplementing referential integrity that Postgres provides for free. JSON columns cover the genuinely flexible fields (§10.1's per-entity metadata) without abandoning relational integrity for the entities that need it.

**SQLAlchemy 2.0, kept strictly at the Persistence layer.** This is the one place this ADR has to actively guard against a known failure mode this project already named: SQLAlchemy models must not leak into Domain (§12.1, IG-001) the way an ORM-first design tends to invite. Domain entities stay plain Pydantic/dataclass objects; SQLAlchemy models are Persistence-layer-only, mapped at the boundary. This is a discipline this ADR flags for T-006/T-007, not something SQLAlchemy enforces on its own.

**Redis + arq over Celery.** Celery is the more famous choice but pulls in a heavier broker abstraction (typically RabbitMQ) this project has no other reason to run. Redis is the smaller footprint, doubles as the cache layer (§16.9's Worker Tier and any future AI Interpretation Tier caching share one dependency instead of two), and arq's asyncio-native design matches FastAPI's async model without a sync/async bridge.

**React + TypeScript.** The weakest-evidence choice in this ADR — there is no existing frontend code to extend, unlike every backend choice above. Justified narrowly: §13.9 describes a data-dense, desktop-first application (tables, charts, status views), which is React's best-supported use case by ecosystem depth, not a claim that it's uniquely correct. This is the one row in this table where a genuinely different, reasonable choice (Svelte, Vue) wouldn't be wrong — flagged for explicit human sign-off rather than treated as settled.

**First-party JWT auth, not an external identity provider.** §14.13 (SSO/SCIM) is explicitly out of scope for MVP-era commercial-grade, not enterprise-grade (§1.5). Standing up Auth0/Cognito-equivalent infrastructure before there's a single real tenant would be premature commitment against a cloud-neutrality requirement (§16) most such providers quietly violate. Revisit at the point §14.13 actually activates.

**Docker for packaging, no mandated orchestrator.** Satisfies §16.25's portability requirement (self-hosted and SaaS from the same artifact) without importing Kubernetes complexity this project doesn't need at MVP scale — consistent with §16.1's explicit "no mandated container/orchestration technology unless architecturally required."

**GitHub Actions for CI.** Not a strong technical argument either way against competitors — chosen because `.github/PULL_REQUEST_TEMPLATE.md` already exists in this repository, implying GitHub is already the git host; using its native CI avoids a second platform integration for no benefit.

## Consequences

- `T-005` (IG-001 in CI) can now be written concretely against GitHub Actions.
- `T-006` (six-layer skeleton) can now be scaffolded as an actual FastAPI project structure.
- `T-007`'s Domain Model reconciliation with `core/contracts.py` has a target ORM boundary to design against.
- New dependencies to add to `pyproject.toml` once T-004 is approved: `fastapi`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `redis`, `arq`, `python-jose` (or equivalent JWT library) — none conflict with or duplicate anything currently declared.
- The frontend stack (React/TypeScript) has no corresponding entry in `pyproject.toml` at all; it will need its own `package.json` at a location T-006 also needs to settle (monorepo layout is an implicit sub-decision of T-006, not resolved by this ADR).

## Rejected alternatives (brief)

- **Django** — rejected over FastAPI: its ORM and forms layer duplicate what Pydantic already does in this codebase, and its batteries-included admin/templating features have no use case here.
- **MongoDB / DynamoDB-style store** — rejected: the Domain Model's relational invariants (pinning, immutability, tenant isolation) are exactly what a document store makes harder, not easier, to enforce.
- **Celery** — rejected: heavier broker requirement for no capability this project needs yet; revisit only if arq's feature set proves insufficient.
- **Kubernetes at MVP** — rejected as premature: §16.1 already forbids mandating an orchestrator without architectural necessity, and there's no multi-service scaling need yet to create one.

## Open question for the human decision

React vs. Svelte/Vue is the one row above where the evidence is genuinely thin (no existing frontend code either way). Recommend accepting React for ecosystem-depth reasons stated above, but this is the one line item in this ADR that's a preference call, not a reuse-driven near-certainty like the backend rows.
