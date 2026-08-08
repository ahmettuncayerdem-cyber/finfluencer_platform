"""Composition root (BACKLOG.md T-012, extended by T-028) -- the one module allowed to import
across all six layers for wiring purposes only.

Why this needs to exist and why it cannot live inside any of the six layers: every layer's own
forbidden-dependency rules (`PRODUCT_ARCHITECTURE.md` section 12.1) are written from the
perspective of *using* another layer at request time, not *constructing* one at startup --
Application may depend on "Infrastructure-defined interfaces only (never a concrete
Infrastructure class)" (line 828), and the API Layer is forbidden from importing Infrastructure
or Persistence at all (line 821). Read literally and completely, no layer is allowed to
construct the concrete objects an orchestrator needs injected. Every strict-DI-inversion
architecture has exactly one such exception -- a startup/wiring script, not a business-logic
module -- and `PRODUCT_ARCHITECTURE.md` section 12.2 line 865 already names this pattern
explicitly: "Injected into Infrastructure adapters at startup... via dependency injection."
This module is that startup point, made concrete. It contains zero business logic (no `if`
branching on domain state, no sequencing decisions) -- only object construction and route
registration -- and it is not one of the six layers, so `scripts/check_layer_dependencies.py`'s
IG-001 checker (which only walks `presentation`/`api`/`domain`) never inspects it and is not
being silently evaded by its placement.

**In-memory repository stand-ins, not a Persistence Layer implementation.** `_InMemoryProject
Repository`/`_InMemoryCollectionRunRepository` below are the exact same shape as the
`FakeProjectRepository`/`FakeCollectionRunRepository` test doubles used throughout T-009/T-010/
T-011's own test suites, relocated from test code into a runnable composition root so the
Walking Skeleton has *something* satisfying `IProjectRepository`/`ICollectionRunRepository` to
inject. Non-durable (in-process Python dicts, lost on restart), single-process, no migrations,
no schema -- explicitly not `src/finfluencer/persistence/`'s eventual real implementation
(ADR-0001: PostgreSQL + SQLAlchemy 2.0). Operator constraint for T-012 ("No Persistence
implementation") is honored exactly: nothing durable is introduced here.

**Collection execution reuses T-010's adapter unmodified**, wired to `FixtureCollectionProvider`
(no live network -- same Sprint 0 scope T-010 itself carried) and a temp directory as
`base_root`, fresh each process start.

**T-028 extends this composition root with the Analysis and Reporting Services' first
Presentation/API wiring.** `StartAnalysisRunOrchestrator` (T-020), `GenerateReportOrchestrator`
(T-025), `ExportReportTableOrchestrator` (T-026), `FinalizeReportOrchestrator`/
`GenerateExportOrchestrator` (T-027), and `GetReportOrchestrator` (T-028) are all wired here
**completely unmodified** -- every one of them was already fully built and tested before this
task; this is the first time any of them is reachable over real HTTP.

**`_DemoTopicAssignmentEngine` is a deliberate, clearly-scoped exception to "reuse existing
Infrastructure unmodified."** It implements `IAnalysisEngine` (`domain/analysis_engine.py`) but
is **not** `TopicsAnalysisAdapter` (T-019) and does not wrap, import, or otherwise touch it.
Reasoning, recorded in full in `T-028_MIGRATION_RISK_CHECKLIST.md`: `StartAnalysisRun` (T-020)
had never been exposed via API before this task, and the real `TopicsAnalysisAdapter` requires
loading an actual BERTopic model -- heavy, network/model-availability-dependent, and T-019's own
test suite already establishes the precedent of injecting a fake `runner_factory`/`model_loader`
rather than load a real one even in its own tests. `_DemoTopicAssignmentEngine` reads a real,
already-collected `comments.parquet` and writes a real `topics.parquet` (deterministic topic
assignment, no ML), in the exact shape `MasterTableExportAdapter`'s own tests fixture -- so every
downstream Reporting adapter (`ResultSnapshotAdapter`, `MasterTableExportAdapter`,
`PdfRendererAdapter`) consumes it with zero special-casing, genuinely unmodified.

**Release Blocker #6 adds real dispatch, permissively, without retiring the demo path.** Per the
accepted resolution to a contradiction found while implementing the original Readiness Review's
plan (existing T-028 tests, and `StartAnalysisRunOrchestrator`'s/`ResultSnapshotAdapter`'s own
docstrings, establish that `analysis_type_id` is deliberately "trusted as given" everywhere else
in this codebase -- rejecting unrecognized ids here would have been a new, unevidenced rule, not
an extension of one): two fixed, well-known `AnalysisType` ids
(`TOPIC_MODELING_ANALYSIS_TYPE_ID`/`SENTIMENT_ANALYSIS_TYPE_ID`, below) are minted and mapped, in
`app.state.analysis_run_orchestrators_by_type`, to two new `StartAnalysisRunOrchestrator`
instances wired to `RealTopicsAnalysisEngine`/`RealSentimentAnalysisEngine`
(`infrastructure/analysis/`) instead of the demo engine. `api/routes/analysis.py` looks a
request's `analysis_type_id` up in that dict and falls back to the original, unchanged
`app.state.start_analysis_run_orchestrator` (still `_DemoTopicAssignmentEngine`-backed, still
exactly what it was before this change) for anything not an exact match -- including every
random UUID T-028's existing tests already send. **Still does not resolve TD-03/TD-04** (ARB-01's
flagged general `AnalysisType`-dispatch mechanism) -- this is two fixed dict entries, not a
catalog/repository; a real dispatch mechanism remains deferred, unchanged from ARB-01's review.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import FileResponse

from finfluencer.api.routes.analysis import router as analysis_router
from finfluencer.api.routes.collection import router as collection_router
from finfluencer.api.routes.identity import router as identity_router
from finfluencer.api.routes.reporting import router as reporting_router
from finfluencer.application.orchestrators import (
    CreateProjectOrchestrator,
    ExportReportTableOrchestrator,
    FinalizeReportOrchestrator,
    GenerateExportOrchestrator,
    GenerateReportOrchestrator,
    GetReportOrchestrator,
    StartAnalysisRunOrchestrator,
    StartCollectionRunOrchestrator,
)
from finfluencer.core.config import load_settings
from finfluencer.domain.analysis_engine import AnalysisOutcome
from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.analysis_run import AnalysisRun
from finfluencer.domain.entities.analysis_type import AnalysisType
from finfluencer.domain.entities.collection_run import CollectionRun
from finfluencer.domain.entities.export import Export, ExportFormat
from finfluencer.domain.entities.interpretation_record import InterpretationRecord
from finfluencer.domain.entities.project import Project
from finfluencer.domain.entities.report import Report
from finfluencer.infrastructure.analysis import (
    RealSentimentAnalysisEngine,
    RealTopicsAnalysisEngine,
)
from finfluencer.infrastructure.collection import (
    CollectionEngineAdapter,
    FixtureCollectionProvider,
    build_live_collection_engine,
    fixture_transcript_fetcher,
)
from finfluencer.infrastructure.reporting import (
    MasterTableExportAdapter,
    PdfRendererAdapter,
    ResultSnapshotAdapter,
)
from finfluencer.persistence.db import build_engine, build_session_factory, create_all_tables
from finfluencer.persistence.sqlalchemy_repositories import (
    SQLAlchemyAnalysisRunRepository,
    SQLAlchemyCollectionRunRepository,
    SQLAlchemyExportRepository,
    SQLAlchemyInterpretationRecordRepository,
    SQLAlchemyProjectRepository,
    SQLAlchemyReportRepository,
)
from finfluencer.utils.io import read_parquet, write_parquet

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SETTINGS = _REPO_ROOT / "config" / "settings.yaml"
_DEFAULT_ANALYSTS = _REPO_ROOT / "config" / "analysts.yaml"
_WEB_INDEX = _REPO_ROOT / "web" / "index.html"

#: Release Blocker #6 -- two fixed, well-known `AnalysisType` ids. Not a catalog/repository (see
#: module docstring): a caller that sets `analysis_type_id` to exactly one of these two values
#: reaches a real engine; every other value keeps reaching the demo engine, unchanged.
TOPIC_MODELING_ANALYSIS_TYPE_ID = EntityId(uuid.UUID("00000000-0000-0000-0000-0000000000a1"))
SENTIMENT_ANALYSIS_TYPE_ID = EntityId(uuid.UUID("00000000-0000-0000-0000-0000000000a2"))


class _InMemoryProjectRepository:
    """Sprint 0 stand-in for `IProjectRepository` (T-009) -- see module docstring."""

    def __init__(self) -> None:
        self._saved: list[Project] = []

    def add(self, project: Project) -> None:
        self._saved.append(project)


class _InMemoryCollectionRunRepository:
    """Sprint 0 stand-in for `ICollectionRunRepository` (T-011) -- see module docstring."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[EntityId, str], CollectionRun] = {}

    def add(self, collection_run: CollectionRun, *, idempotency_key: str) -> None:
        self._by_key[(collection_run.dataset_id, idempotency_key)] = collection_run

    def get_by_idempotency_key(
        self, dataset_id: EntityId, idempotency_key: str
    ) -> CollectionRun | None:
        return self._by_key.get((dataset_id, idempotency_key))

    def save(self, collection_run: CollectionRun) -> None:
        # No-op (EPIC-07', 2026-08-07): `_by_key` already stores the same object reference
        # `add()` received, so `.start()`/`.complete()`/`.fail()`/`.resume()` mutations are
        # already visible without a separate write. A real (SQL-backed) repository cannot rely
        # on this -- see `ICollectionRunRepository.save()`'s docstring for why the method exists.
        pass


class _InMemoryAnalysisRunRepository:
    """Sprint 0 stand-in for `IAnalysisRunRepository` (T-020/T-025) -- see module docstring."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[EntityId, str], AnalysisRun] = {}
        self._by_id: dict[EntityId, AnalysisRun] = {}

    def add(self, analysis_run: AnalysisRun, *, idempotency_key: str) -> None:
        self._by_key[(analysis_run.project_id, idempotency_key)] = analysis_run
        self._by_id[analysis_run.id] = analysis_run

    def get_by_idempotency_key(
        self, project_id: EntityId, idempotency_key: str
    ) -> AnalysisRun | None:
        return self._by_key.get((project_id, idempotency_key))

    def get_by_id(self, project_id: EntityId, analysis_run_id: EntityId) -> AnalysisRun | None:
        run = self._by_id.get(analysis_run_id)
        if run is None or run.project_id != project_id:
            return None
        return run

    def save(self, analysis_run: AnalysisRun) -> None:
        # No-op (EPIC-07', 2026-08-07) -- see `_InMemoryCollectionRunRepository.save()`.
        pass


class _InMemoryReportRepository:
    """Sprint 0 stand-in for `IReportRepository` (T-025) -- see module docstring."""

    def __init__(self) -> None:
        self._by_id: dict[EntityId, Report] = {}

    def add(self, report: Report) -> None:
        self._by_id[report.id] = report

    def get_by_id(self, project_id: EntityId, report_id: EntityId) -> Report | None:
        report = self._by_id.get(report_id)
        if report is None or report.project_id != project_id:
            return None
        return report

    def save(self, report: Report) -> None:
        # No-op (EPIC-07', 2026-08-07) -- see `_InMemoryCollectionRunRepository.save()`.
        pass


class _InMemoryInterpretationRecordRepository:
    """Sprint 0 stand-in for `IInterpretationRecordRepository` (T-025/T-026) -- see module
    docstring.
    """

    def __init__(self) -> None:
        self._by_id: dict[EntityId, InterpretationRecord] = {}

    def add(self, record: InterpretationRecord) -> None:
        self._by_id[record.id] = record

    def get_by_id(self, record_id: EntityId) -> InterpretationRecord | None:
        return self._by_id.get(record_id)


class _InMemoryExportRepository:
    """Sprint 0 stand-in for `IExportRepository` (T-027) -- see module docstring."""

    def __init__(self) -> None:
        self._exports: list[Export] = []

    def add(self, export: Export) -> None:
        self._exports.append(export)

    def get_by_report_version_and_format(
        self, report_id: EntityId, report_version: int, format: ExportFormat,
    ) -> Export | None:
        for export in self._exports:
            if (
                export.report_id == report_id
                and export.report_version == report_version
                and export.format == format
            ):
                return export
        return None


class _DemoTopicAssignmentEngine:
    """Deliberate, clearly-scoped demo stand-in for `IAnalysisEngine` (BACKLOG.md T-028) --
    NOT `TopicsAnalysisAdapter` (T-019), does not wrap or import it. See this module's own
    docstring (top) and `T-028_MIGRATION_RISK_CHECKLIST.md` for the full reasoning.

    Deterministic and dependency-free (`pandas`/`finfluencer.utils.io` only): reads the real
    `comments.parquet` a real `CollectionRun` already produced, assigns each comment a topic by
    a fixed rule (`hash(comment_id) % 3`, not randomized -- reproducible across calls), and
    writes a real `topics.parquet` in the exact shape `reporting.master_table.build_master_table`
    (via `MasterTableExportAdapter`, T-026) and `ResultSnapshotAdapter` (T-025) both already
    expect: `comment_id, configuration, topic_id, topic_label, topic_prob` for the `pooled`
    configuration; `comment_id, configuration, topic_id, topic_label` (no `topic_prob`) for
    `within_analyst` -- matching `MasterTableExportAdapter`'s own test fixtures exactly, so every
    downstream Reporting adapter consumes this output with zero special-casing.

    Produces topics-shaped output only -- a `Report` citing only this demo engine's output
    cannot be table-exported via `MasterTableExportAdapter` (which needs both a topics- and a
    sentiment-shaped `AnalysisRun`); `MasterTableExportAdapter` already raises a clear
    `FileNotFoundError` in that case (T-026's own documented, not-a-bug behavior) -- not
    silently wrong output.
    """

    def __init__(self, *, base_root: Path) -> None:
        self._base_root = base_root

    def run(self, analysis_run_id: str, collection_run_id: str) -> AnalysisOutcome:
        comments_path = self._base_root / collection_run_id / "data_raw" / "comments.parquet"
        comments = read_parquet(comments_path)

        pooled_rows: list[dict[str, Any]] = []
        within_rows: list[dict[str, Any]] = []
        for comment_id in comments["comment_id"]:
            topic_id = abs(hash(str(comment_id))) % 3
            topic_label = f"demo_topic_{topic_id}"
            pooled_rows.append({
                "comment_id": comment_id, "configuration": "pooled",
                "topic_id": topic_id, "topic_label": topic_label, "topic_prob": 0.75,
            })
            within_rows.append({
                "comment_id": comment_id, "configuration": "within_analyst",
                "topic_id": topic_id, "topic_label": topic_label,
            })
        topics_df = pd.DataFrame(pooled_rows + within_rows)

        output_path = self._base_root / analysis_run_id / "data_processed" / "topics.parquet"
        write_parquet(topics_df, output_path)

        return AnalysisOutcome(
            analysis_run_id=analysis_run_id,
            row_count=len(comments),
            topic_count=int(topics_df["topic_id"].nunique()) if not topics_df.empty else 0,
        )


def create_app(
    *,
    settings_path: Path = _DEFAULT_SETTINGS,
    analysts_path: Path = _DEFAULT_ANALYSTS,
    collection_base_root: Path | None = None,
    anon_salt: str = "sprint0-dev-salt",
    use_live_collection: bool = False,
    db_url: str | None = None,
) -> FastAPI:
    """Build the Walking Skeleton's FastAPI app: wire repositories, construct all
    orchestrators, register routes.

    `collection_base_root` defaults to a fresh temp directory per call -- there is no
    persistence-layer decision here about where collected *data* (parquet files) should
    permanently live; that is still explicitly out of scope (this is EPIC-07's
    `data_raw`/`data_processed` file tree, not `db_url` below).

    `use_live_collection` (T-029 MVP sign-off support, added after Release Blocker #3): opt-in
    only, default `False` -- the dev page's default wiring stays fixture-backed for exactly the
    reason this module's docstring already gives (spending real YouTube API quota on every page
    load would be silently expensive). When `True`, swaps `FixtureCollectionProvider` for
    `build_live_collection_engine` (T-015, already fully tested) -- reuses the existing,
    already-tested live wiring unmodified; no new collection logic. Requires a real `YT_API_KEY`
    in the environment, the same as `scripts/t015_live_smoke_test.py`; raises the same
    `AuthenticationError` from `YouTubePlatformProvider.__init__` if it's missing.

    `db_url` (BACKLOG.md EPIC-07', ADR-0001-A, 2026-08-07): `None` (the default) preserves every
    prior caller's exact behavior unchanged -- the original in-memory `_InMemory*Repository`
    stand-ins (non-durable, lost on process exit, one fresh instance per `create_app()` call).
    This default matters for test isolation specifically: `t029_e2e_verification.py` check 10a
    asserts two separate `create_app()` calls against the same `collection_base_root` do NOT
    share Report state -- that assertion is about the *default* case and remains true, since no
    `db_url` means no shared backing store either. Passing an explicit `db_url` (e.g.
    `"sqlite:///./data/finfluencer.db"`) switches every repository that has a
    `persistence/sqlalchemy_repositories.py` implementation to a real, durable SQLite-backed one
    instead -- multiple `create_app()` calls with the *same* `db_url` now genuinely share state
    (that is the point: real cross-process/cross-restart durability requires the caller to pass
    a stable path, not the default fresh-temp-file-per-call behavior). Schema is ensured via
    `create_all_tables()` (checkfirst, so safe against an already-Alembic-migrated database too)
    rather than requiring the caller to have run `alembic upgrade head` first -- convenient for
    ad-hoc/dev/test `db_url`s; a real deployment should still run Alembic migrations directly
    (see `alembic/README.md`) so schema changes go through reviewable migration files.
    """
    cfg = load_settings(settings_path, analysts_path, validate_secrets=False)
    base_root = (
        Path(collection_base_root)
        if collection_base_root is not None
        else Path(tempfile.mkdtemp(prefix="finfluencer-walking-skeleton-"))
    )

    if use_live_collection:
        collection_engine, _live_quota = build_live_collection_engine(
            cfg, base_root, transcript_fetcher=None,
        )
    else:
        collection_engine = CollectionEngineAdapter(
            settings=cfg.settings,
            roster=cfg.roster,
            provider=FixtureCollectionProvider(),
            base_root=base_root,
            transcript_fetcher=fixture_transcript_fetcher,
            anon_salt=anon_salt,
        )

    if db_url is not None:
        engine = build_engine(db_url)
        create_all_tables(engine)
        session_factory = build_session_factory(engine)
        project_repository = SQLAlchemyProjectRepository(session_factory)
        collection_run_repository = SQLAlchemyCollectionRunRepository(session_factory)
        analysis_run_repository = SQLAlchemyAnalysisRunRepository(session_factory)
        report_repository = SQLAlchemyReportRepository(session_factory)
        interpretation_record_repository = SQLAlchemyInterpretationRecordRepository(
            session_factory,
        )
        export_repository = SQLAlchemyExportRepository(session_factory)
    else:
        project_repository = _InMemoryProjectRepository()
        collection_run_repository = _InMemoryCollectionRunRepository()
        analysis_run_repository = _InMemoryAnalysisRunRepository()
        report_repository = _InMemoryReportRepository()
        interpretation_record_repository = _InMemoryInterpretationRecordRepository()
        export_repository = _InMemoryExportRepository()

    demo_analysis_engine = _DemoTopicAssignmentEngine(base_root=base_root)
    # Release Blocker #6: real engines, reachable only via the two fixed ids above -- the demo
    # engine above remains the orchestrator wired to `app.state.start_analysis_run_orchestrator`
    # (unchanged) and the fallback for every `analysis_type_id` that isn't one of these two.
    real_topics_engine = RealTopicsAnalysisEngine(settings=cfg.settings, base_root=base_root)
    real_sentiment_engine = RealSentimentAnalysisEngine(settings=cfg.settings, base_root=base_root)
    topic_modeling_analysis_type = AnalysisType(
        "topic_modeling", "1.0.0", entity_id=TOPIC_MODELING_ANALYSIS_TYPE_ID,
    )
    sentiment_analysis_type = AnalysisType(
        "sentiment", "1.0.0", entity_id=SENTIMENT_ANALYSIS_TYPE_ID,
    )
    result_snapshot_reader = ResultSnapshotAdapter(base_root=base_root)
    table_exporter = MasterTableExportAdapter(base_root=base_root, settings=cfg.settings)
    pdf_renderer = PdfRendererAdapter()

    exports_root = base_root / "exports"
    exports_root.mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="Finfluencer Research Platform -- Walking Skeleton (Sprint 0)",
        version="0.1.0-sprint0",
    )
    app.state.create_project_orchestrator = CreateProjectOrchestrator(
        project_repository=project_repository
    )
    app.state.start_collection_run_orchestrator = StartCollectionRunOrchestrator(
        collection_run_repository=collection_run_repository,
        collection_engine=collection_engine,
    )
    app.state.start_analysis_run_orchestrator = StartAnalysisRunOrchestrator(
        analysis_run_repository=analysis_run_repository,
        analysis_engine=demo_analysis_engine,
    )
    # Release Blocker #6: real dispatch, permissive by construction (see module docstring). Only
    # these two exact ids are looked up by `api/routes/analysis.py`; any other `analysis_type_id`
    # -- including every random UUID T-028's own tests already send -- keeps reaching
    # `app.state.start_analysis_run_orchestrator` above, unchanged.
    app.state.analysis_run_orchestrators_by_type = {
        topic_modeling_analysis_type.id: StartAnalysisRunOrchestrator(
            analysis_run_repository=analysis_run_repository,
            analysis_engine=real_topics_engine,
        ),
        sentiment_analysis_type.id: StartAnalysisRunOrchestrator(
            analysis_run_repository=analysis_run_repository,
            analysis_engine=real_sentiment_engine,
        ),
    }
    app.state.generate_report_orchestrator = GenerateReportOrchestrator(
        analysis_run_repository=analysis_run_repository,
        report_repository=report_repository,
        interpretation_record_repository=interpretation_record_repository,
        snapshot_reader=result_snapshot_reader,
    )
    app.state.get_report_orchestrator = GetReportOrchestrator(
        report_repository=report_repository,
    )
    app.state.finalize_report_orchestrator = FinalizeReportOrchestrator(
        report_repository=report_repository,
    )
    app.state.generate_export_orchestrator = GenerateExportOrchestrator(
        report_repository=report_repository,
        interpretation_record_repository=interpretation_record_repository,
        export_repository=export_repository,
        pdf_renderer=pdf_renderer,
    )
    app.state.export_report_table_orchestrator = ExportReportTableOrchestrator(
        report_repository=report_repository,
        interpretation_record_repository=interpretation_record_repository,
        analysis_run_repository=analysis_run_repository,
        table_exporter=table_exporter,
    )
    app.state.exports_root = exports_root

    app.include_router(identity_router)
    app.include_router(collection_router)
    app.include_router(analysis_router)
    app.include_router(reporting_router)

    @app.get("/", include_in_schema=False)
    def _serve_dev_ui() -> Any:
        # A single static HTML+vanilla-JS page (web/index.html) -- deliberately NOT the
        # ADR-0001-decided React+TypeScript frontend, which needs its own package.json and a
        # monorepo-layout decision ADR-0001 itself left open. This is a Sprint 0-only,
        # same-origin developer page proving the Walking Skeleton end to end; full React
        # adoption is deferred to a dedicated future frontend task.
        return FileResponse(_WEB_INDEX)

    return app


def _new_dataset_id() -> str:
    """Convenience for manual/local testing -- the Walking Skeleton has no `CreateDataset`
    command yet (out of T-012's scope, per BACKLOG.md), so there is no real way to obtain a
    `dataset_id` other than generating one client-side. Not imported by any route -- exists only
    so a developer running this app locally has an obvious, documented way to get a valid UUID
    to type into the frontend's "Dataset ID" field.
    """
    return str(uuid.uuid4())


__all__ = [
    "SENTIMENT_ANALYSIS_TYPE_ID",
    "TOPIC_MODELING_ANALYSIS_TYPE_ID",
    "create_app",
]
