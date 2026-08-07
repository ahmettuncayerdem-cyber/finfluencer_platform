# Backlog Reprioritization — 2026-08-07

**Status:** Proposal for operator review — not yet applied to `BACKLOG.md`. Once confirmed,
the accepted ordering gets written into `BACKLOG.md` as the new Engineering Workstreams section.

**Trigger:** Operator instruction (2026-08-07, post-Gaza-pilot-smoke-test): deprioritize
Authentication (single-user, research-oriented platform, nothing yet worth protecting behind
real accounts), reprioritize toward multi-analyst orchestration, comparative analytics,
visualization, AI-assisted interpretation, and advanced reporting — "challenge the current
backlog if necessary and justify every reprioritization with technical and product reasoning."

**Method:** Read `BACKLOG.md` in full (not just headers), `PRODUCT_ARCHITECTURE.md` §3.1 (MVP
scoping table), §8.1–8.10 (module specs), and the actual source tree (`src/finfluencer/`) to
separate three categories that are easy to blur together: *already built*, *designed but not
built*, and *not even designed yet*. The proposal below is grounded in that read, not in a
fresh guess at what a research platform "should" have next.

---

## 1. The central finding this proposal is built on

**Deprioritizing Authentication does not mean the platform has no durability problem — it has
a different one, and several of the requested features silently depend on it.**

`persistence/` (the actual six-layer Persistence Layer) is empty except for a docstring.
Every repository in `bootstrap.py` — `_InMemoryProjectRepository`,
`_InMemoryCollectionRunRepository`, `_InMemoryAnalysisRunRepository`, `_InMemoryReportRepository`,
`_InMemoryInterpretationRecordRepository`, `_InMemoryExportRepository` — is an in-process
Python dict, explicitly documented as "non-durable... lost on restart, single-process." This
was the correct, deliberate choice for Sprint 0–4 (BACKLOG.md T-012's own operator constraint:
"No Persistence implementation"). It is **not** a correct permanent state for a platform being
asked to do comparative analytics across runs.

Concretely, right now: the real Gaza-pilot data this session just collected (19/19 smoke test,
real BBC News comments, real BERTopic/sentiment output) lives under a `tempfile.mkdtemp()`
directory tied to one Python process that has already exited. There is no `listProjects`, no
`listReportsForProject`, no way to open the platform tomorrow and see yesterday's work. This
isn't a hypothetical scaling concern — it is the actual, current state of the actual data this
engagement produced today.

Checked directly against what the operator asked for:

| Requested capability | Blocked by missing Persistence? | Evidence |
|---|---|---|
| Multi-analyst orchestration | **Partially** — already real at the *within one run* level (§2 below); blocked at the *across runs/projects over time* level | `CollectionEngineAdapter` already iterates the full analyst roster per run; but there is no way to list or compare past `CollectionRun`s once the process restarts |
| Comparative analytics | **Yes, fully** | `PRODUCT_ARCHITECTURE.md` §3.1 lists "Cross-project comparison" as v1.x, "No" backend asset, explicitly "depends on multi-project use" |
| Visualization | **No** | Existing figure-generation code (`market/figures.py`, `output.figures` config) operates on data already in hand within one run/request — a rendering layer can be built without solving durability first |
| AI-assisted interpretation | **No, for the v1.x scope** | §8.5's v1.x scope is explicitly single-shot ("explain this result"); AIG-003 ("AI Operations Are Stateless") is *already formalized* in the architecture — the v1.x version is designed to not need persistent state |
| Advanced/comparative reporting | **Yes, fully** | §8.4's own `listReportsForProject` and §8.3's deferred "Research History API" are both explicitly, in the architecture document itself, gated on durable storage that doesn't exist |

This is the reprioritization's load-bearing claim: **a minimum, deliberately scoped persistence
slice is not a detour from the requested feature list — it is the prerequisite for roughly half
of it**, and pretending otherwise would mean building comparative-analytics and
advanced-reporting features on top of state that evaporates on every restart, which is not a
real capability, it's a demo.

This is *not* a proposal to build ADR-0001's full production system (PostgreSQL + SQLAlchemy 2.0,
migrations, multi-tenant scale) right now — that remains correctly out of scope for a
single-user research tool. §3 scopes something much smaller.

---

## 2. What's already real (challenging the premise that multi-analyst orchestration is missing)

Worth stating plainly because it changes what "multi-analyst orchestration" as a backlog item
should even mean: **within a single `CollectionRun`, multi-analyst orchestration already
works and is already exercised.** `config/analysts.yaml` / `config/analysts.gaza_pilot.yaml`
both configure multiple roster entries; `CollectionEngineAdapter` collects all of them in one
run; BERTopic already runs in both `pooled` (cross-analyst) and `within_analyst` configurations;
the master table already carries `analyst_key` as a first-class column. `PRODUCT_ARCHITECTURE.md`
§3.1 itself lists "Cross-channel comparison" as an MVP capability with backend asset ✅, calling
it "already the study's core design."

So: if "multi-analyst orchestration" meant *analyzing several channels together in one study*,
it is done, not a backlog item. What is actually missing — and what I believe the operator
means in practice — is orchestrating and comparing **across separate `CollectionRun`s /
`Project`s over time** (e.g., re-running the same roster monthly and tracking drift; or
comparing the Turkish finfluencer study against the Gaza pilot side by side). That capability
is real, not yet built, and — per §1's table — gated on persistence.

---

## 3. Proposed new epic ordering

### EPIC-07' (was EPIC-07) — Minimum Viable Persistence — **NEW, proposed P0**
**Purpose:** durable storage for exactly the six repositories already interface-defined in
`bootstrap.py`'s in-memory stand-ins — no more, no less. Not a rewrite: `IProjectRepository`,
`ICollectionRunRepository`, etc. are already the Domain-defined interfaces every orchestrator
already codes against (T-009 through T-028 all built to interfaces, not to the in-memory
classes directly) — per `PRODUCT_ARCHITECTURE.md` §12.1's own dependency rule ("Application may
depend on Infrastructure-defined interfaces only, never a concrete class"), this is a
**swap-the-implementation** task, not a rearchitecture.
**Scope decision, stated explicitly:** SQLite via SQLAlchemy 2.0 for v1, not PostgreSQL. ADR-0001
already named SQLAlchemy 2.0 as the ORM; it did not mandate Postgres specifically as the *only*
acceptable backend for every deployment stage, and a single-user research tool has no concurrent-
write, multi-tenant, or horizontal-scale requirement that would justify running a Postgres server
alongside it. SQLite gets 90% of the durability benefit (survives restarts, supports real
queries, is trivially inspectable/backupable by a researcher with no DB admin skills) at near-zero
operational cost. **This should be logged as a formal ADR amendment, not a silent deviation** —
proposed as ADR-0001-A (SQLite for v1 single-user deployment; Postgres remains the multi-tenant
answer if/when EPIC-07-original's Auth/multi-tenant scope is revisited).
**Priority:** P0 — everything in §4/§5 below either depends on it directly or is meaningfully
weaker without it.
**Effort:** M. Six repository implementations, each a thin SQLAlchemy-backed adapter behind an
already-stable interface; a schema migration tool (Alembic, standard with SQLAlchemy) for the
inevitable schema evolution as new entities are added.
**Explicit non-goals:** no multi-tenant row-level isolation (that's T-032's job, still correctly
deferred with Auth), no connection pooling/scale concerns, no Postgres.

### EPIC-09 — Comparative Analytics & Research History — depends on EPIC-07'
**Purpose:** the concrete, currently-missing capability §1/§2 identified: `listProjects`,
`listReportsForProject`, cross-`CollectionRun` and cross-`Project` comparison views, exactly as
already specified in `PRODUCT_ARCHITECTURE.md` §8.3's deferred "Research History API" and §8.9's
"Cross-project comparison" screen. Not new design — implementing what's already specified.
**Priority:** P1.
**Effort:** M.

### EPIC-10 — Visualization Rendering Layer — independent of EPIC-07', can run in parallel
**Purpose:** close the gap §3.1's own table names precisely: "Topic/Sentiment Visualization...
Partial — data exists, no web rendering layer." Build on `market/figures.py`'s existing
figure-generation patterns and `output.figures` config (`dpi`, `formats`, `colourblind_safe`
already specified) rather than inventing a new visualization stack; the real gap is exposing
this through the API/web layer, not generating the figures in the first place.
**Priority:** P1 (co-equal with EPIC-09 — genuinely independent of persistence, no reason to
sequence it behind).
**Effort:** M.

### EPIC-11 — AI-Assisted Interpretation (v1.x scope only) — independent of EPIC-07'
**Purpose:** implement `PRODUCT_ARCHITECTURE.md` §8.5's already-specified v1.x scope: single-shot
`requestInterpretation(analysisRunId, scope)` producing a natural-language explanation of one
Analysis Run's output, bound by the already-formalized guardrails **AIG-001** (AI Interpretation
Guardrail) and **AIG-003** (AI Operations Are Stateless). The stateless framing is exactly why
this doesn't need to wait on EPIC-07' — it's designed not to.
**Priority:** P1.
**Effort:** M — the `llm` config section already exists in `settings.yaml`
(`enabled`/`provider`/`require_human_validation`/`prompt_version`), currently pointed at
`offline_stub`; this epic is building the real provider path behind that already-present
feature flag, not inventing new configuration surface.
**Explicit non-goal:** the v2 conversational Research Assistant (`getInterpretationHistory`) —
correctly deferred, since *that* variant does need persistent conversation state.

### EPIC-12 — Advanced Reporting (Word export, richer citation types) — partially depends on EPIC-07'
**Purpose:** `PRODUCT_ARCHITECTURE.md` §3.1's v1.x row: Word export. The CSV/PDF export path is
already real and live-verified (T-026/T-027, 2026-08-07 smoke test); Word export is additive to
that, not a rebuild.
**Priority:** P2 — real but lower-leverage than EPIC-09/10/11 for "research capability" per the
operator's own stated optimization target.
**Effort:** S–M.

### EPIC-07-original (Identity Widening: T-030/T-031/T-032) — **explicitly deprioritized, not deleted**
Per operator instruction. Retained in `BACKLOG.md` with its existing task IDs unchanged (renumbering
would break every cross-reference to T-030–T-032 already in the architecture/roadmap docs) but
moved out of the near-term critical path. **One caveat worth flagging, not silently absorbing:**
EPIC-07' (persistence) makes real, durable, potentially multi-day-spanning research data exist
for the first time — which is a small, real argument for *not* deferring Auth indefinitely
forever, since durable data is exactly the kind of thing worth access-controlling eventually.
Not a reason to build it now (still correctly gated on "something worth protecting" actually
existing at meaningful scale), but worth re-raising once EPIC-09 ships, not forgotten for good.

### EPIC-08 (Repository Hygiene, T-033) — unchanged, still P2, still non-blocking

---

## 4. Proposed execution order (single sequence, for a single engineering thread)

1. **EPIC-07' (Minimum Viable Persistence)** — first, because §1's table shows it's the real
   dependency root for half the requested list.
2. **EPIC-10 (Visualization)** and **EPIC-11 (AI-Assisted Interpretation, v1.x)** — run these two
   in parallel with each other (genuinely independent of one another and, per §1, independent of
   EPIC-07' too) once EPIC-07' is far enough along that its interfaces are stable, even before
   it's fully shipped.
3. **EPIC-09 (Comparative Analytics & Research History)** — right after EPIC-07' ships, since it's
   the most direct consumer of it.
4. **EPIC-12 (Advanced Reporting)** — lowest-leverage of the four requested feature areas per the
   operator's own stated goals (research capability, scalability, long-term product value); ships
   last.

---

## 5. What I am explicitly *not* proposing

- Not proposing to build ADR-0001's full production persistence stack (Postgres, migrations at
  scale, connection pooling) — that remains correctly deferred until multi-tenant/Auth scope is
  real (§3, EPIC-07').
- Not proposing to touch Authentication, Persistence's *tenant-isolation* concerns (T-032), or
  any of the software architecture frozen in the earlier V1.0 Research Readiness pass, beyond
  the scoped repository-implementation swap in EPIC-07'.
- Not silently reinterpreting "multi-analyst orchestration" as already-solved and dropping it —
  §2 states directly what part of it is done and what part isn't, rather than either claiming
  full credit or ignoring the real gap.

---

## 6. Requested decision

Confirm or amend this ordering before `BACKLOG.md` is updated to reflect it. The one item most
worth a deliberate yes/no rather than assumed default is EPIC-07's SQLite-not-Postgres scope
call (§3) — it's a real technical decision with a documented rationale, not a formality.
