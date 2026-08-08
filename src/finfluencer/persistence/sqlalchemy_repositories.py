"""SQLAlchemy-backed repository implementations (BACKLOG.md EPIC-07', ADR-0001-A).

The only translation boundary between `persistence/models.py`'s ORM rows and the real
`domain/entities/*.py` objects the rest of the platform works with -- per this package's own
`__init__.py` docstring and PRODUCT_ARCHITECTURE.md section 12.1: "SQLAlchemy models must not
leak into Domain." Every method here accepts/returns plain Domain entities; no caller outside
`persistence/` ever sees a `*Row` object.

Each repository takes a `sessionmaker` (not a live `Session`) and opens/commits/closes one short
session per method call -- the standard sync-SQLAlchemy-under-a-thread-pool pattern `db.py`'s own
`build_session_factory()` docstring anticipates (FastAPI runs sync path operations in a worker
thread; a `Session` is not safe to share across threads, a fresh one per call is).

Reconstructing a Domain entity from a row never reaches into the entity's private attributes.
Every entity's public constructor accepts `entity_id=` to pin a specific id, and every state
transition (`start()`, `complete()`, `fail()`, `resume()`, `add_citation()`, `finalize()`) is a
public method -- so a row at, say, `status="completed"` is reconstructed by literally replaying
the same transitions the original object went through (`queued --start()--> running
--complete()--> completed`), not by writing to `_status` directly. This keeps every one of the
entities' own invariant checks (e.g. "cannot complete from queued") load-bearing even for rows
that were never touched by this process, rather than bypassing them via a Persistence-only back
door.

`save()` (EPIC-07', added to `ICollectionRunRepository`/`IAnalysisRunRepository`/
`IReportRepository` in `domain/repositories.py` -- see that module's own docstring for why) is
implemented here as a real `UPDATE`, closing the "add-once-then-mutate-by-reference" gap that
only ever worked for the in-memory stand-ins.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from finfluencer.domain.entities._common import EntityId
from finfluencer.domain.entities.analysis_run import AnalysisRun, AnalysisRunStatus
from finfluencer.domain.entities.collection_run import CollectionRun, CollectionRunStatus
from finfluencer.domain.entities.export import Export, ExportFormat
from finfluencer.domain.entities.interpretation_record import (
    InterpretationRecord,
    InterpretationRecordKind,
)
from finfluencer.domain.entities.project import Project
from finfluencer.domain.entities.report import Report, ReportStatus
from finfluencer.persistence.models import (
    AnalysisRunRow,
    CollectionRunRow,
    ExportRow,
    InterpretationRecordRow,
    ProjectRow,
    ReportCitationRow,
    ReportRow,
)


def _replay_collection_run_status(run: CollectionRun, target: CollectionRunStatus) -> None:
    """Drive a freshly-constructed (`queued`) CollectionRun to `target` via its own public
    state-transition methods -- see this module's docstring for why this is done via replay
    rather than private-attribute assignment.
    """
    if target is CollectionRunStatus.QUEUED:
        return
    run.start()
    if target is CollectionRunStatus.RUNNING:
        return
    if target is CollectionRunStatus.COMPLETED:
        run.complete()
        return
    if target is CollectionRunStatus.FAILED:
        run.fail()
        return
    raise AssertionError(f"Unreachable CollectionRunStatus: {target!r}")


def _replay_analysis_run_status(run: AnalysisRun, target: AnalysisRunStatus) -> None:
    """Same replay reasoning as `_replay_collection_run_status`, for `AnalysisRun` (no
    `resume()` on this entity -- see `analysis_run.py`'s own module docstring)."""
    if target is AnalysisRunStatus.QUEUED:
        return
    run.start()
    if target is AnalysisRunStatus.RUNNING:
        return
    if target is AnalysisRunStatus.COMPLETED:
        run.complete()
        return
    if target is AnalysisRunStatus.FAILED:
        run.fail()
        return
    raise AssertionError(f"Unreachable AnalysisRunStatus: {target!r}")


class SQLAlchemyProjectRepository:
    """Backs `IProjectRepository` (BACKLOG.md T-009). `add()` only -- see that Protocol's own
    docstring: no `get`/`update`/`delete` method exists on the interface yet, so none is added
    speculatively here either.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, project: Project) -> None:
        with self._session_factory() as session:
            session.add(
                ProjectRow(
                    id=project.id,
                    tenant_id=project.tenant_id,
                    name=project.name,
                    status=project.status.value,
                )
            )
            session.commit()


class SQLAlchemyCollectionRunRepository:
    """Backs `ICollectionRunRepository` (BACKLOG.md T-011, `save()` added EPIC-07')."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, collection_run: CollectionRun, *, idempotency_key: str) -> None:
        with self._session_factory() as session:
            session.add(
                CollectionRunRow(
                    id=collection_run.id,
                    dataset_id=collection_run.dataset_id,
                    status=collection_run.status.value,
                    idempotency_key=idempotency_key,
                )
            )
            session.commit()

    def get_by_idempotency_key(
        self, dataset_id: EntityId, idempotency_key: str
    ) -> CollectionRun | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(CollectionRunRow).where(
                    CollectionRunRow.dataset_id == uuid.UUID(str(dataset_id)),
                    CollectionRunRow.idempotency_key == idempotency_key,
                )
            )
            if row is None:
                return None
            return self._to_domain(row)

    def save(self, collection_run: CollectionRun) -> None:
        with self._session_factory() as session:
            row = session.get(CollectionRunRow, collection_run.id)
            if row is None:
                raise ValueError(
                    f"SQLAlchemyCollectionRunRepository.save(): no existing row for "
                    f"CollectionRun id={collection_run.id!r} -- save() re-persists an "
                    f"already-add()-ed run, it does not insert a new one."
                )
            row.status = collection_run.status.value
            session.commit()

    @staticmethod
    def _to_domain(row: CollectionRunRow) -> CollectionRun:
        run = CollectionRun(
            dataset_id=EntityId(row.dataset_id), entity_id=EntityId(row.id),
        )
        _replay_collection_run_status(run, CollectionRunStatus(row.status))
        return run


class SQLAlchemyAnalysisRunRepository:
    """Backs `IAnalysisRunRepository` (BACKLOG.md T-020/T-025, `save()` added EPIC-07')."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, analysis_run: AnalysisRun, *, idempotency_key: str) -> None:
        with self._session_factory() as session:
            session.add(
                AnalysisRunRow(
                    id=analysis_run.id,
                    project_id=analysis_run.project_id,
                    collection_run_id=analysis_run.collection_run_id,
                    analysis_type_id=analysis_run.analysis_type_id,
                    analysis_type_version=analysis_run.analysis_type_version,
                    status=analysis_run.status.value,
                    idempotency_key=idempotency_key,
                )
            )
            session.commit()

    def get_by_idempotency_key(
        self, project_id: EntityId, idempotency_key: str
    ) -> AnalysisRun | None:
        with self._session_factory() as session:
            # "the most recently persisted AnalysisRun" (interface docstring) -- deliberately
            # NOT unique per (project_id, idempotency_key), unlike CollectionRunRow; order by
            # created_at descending and take the newest, per that same docstring's own
            # ambiguity-resolution rule.
            row = session.scalar(
                select(AnalysisRunRow)
                .where(
                    AnalysisRunRow.project_id == uuid.UUID(str(project_id)),
                    AnalysisRunRow.idempotency_key == idempotency_key,
                )
                .order_by(AnalysisRunRow.created_at.desc())
                .limit(1)
            )
            if row is None:
                return None
            return self._to_domain(row)

    def get_by_id(self, project_id: EntityId, analysis_run_id: EntityId) -> AnalysisRun | None:
        with self._session_factory() as session:
            row = session.get(AnalysisRunRow, analysis_run_id)
            if row is None or row.project_id != uuid.UUID(str(project_id)):
                return None
            return self._to_domain(row)

    def save(self, analysis_run: AnalysisRun) -> None:
        with self._session_factory() as session:
            row = session.get(AnalysisRunRow, analysis_run.id)
            if row is None:
                raise ValueError(
                    f"SQLAlchemyAnalysisRunRepository.save(): no existing row for AnalysisRun "
                    f"id={analysis_run.id!r} -- save() re-persists an already-add()-ed run, it "
                    f"does not insert a new one."
                )
            row.status = analysis_run.status.value
            session.commit()

    @staticmethod
    def _to_domain(row: AnalysisRunRow) -> AnalysisRun:
        run = AnalysisRun(
            project_id=EntityId(row.project_id),
            collection_run_id=EntityId(row.collection_run_id),
            analysis_type_id=EntityId(row.analysis_type_id),
            analysis_type_version=row.analysis_type_version,
            entity_id=EntityId(row.id),
        )
        _replay_analysis_run_status(run, AnalysisRunStatus(row.status))
        return run


class SQLAlchemyReportRepository:
    """Backs `IReportRepository` (BACKLOG.md T-025, `save()` added EPIC-07').

    `get_by_id()`/`save()` also read/write `report_citations` rows and the referenced
    `interpretation_records` rows directly (no separate `IInterpretationRecordRepository`
    dependency is injected here -- this repository owns the `report_citations` join table
    outright, same "one repository per aggregate-ish cluster" shape the in-memory stand-ins
    already had). Reconstructing citations requires the *real* cited `InterpretationRecord`
    rows (not just their ids): `Report.add_citation()` takes an `InterpretationRecord` instance
    and reads `record.id` off it -- see `report.py`'s own docstring for why (structural
    guarantee against ever holding a live `AnalysisRun` pointer instead).
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, report: Report) -> None:
        with self._session_factory() as session:
            session.add(
                ReportRow(
                    id=report.id,
                    project_id=report.project_id,
                    version=report.version,
                    status=report.status.value,
                )
            )
            session.commit()

    def get_by_id(self, project_id: EntityId, report_id: EntityId) -> Report | None:
        with self._session_factory() as session:
            row = session.get(ReportRow, report_id)
            if row is None or row.project_id != uuid.UUID(str(project_id)):
                return None
            return self._to_domain(session, row)

    def save(self, report: Report) -> None:
        with self._session_factory() as session:
            row = session.get(ReportRow, report.id)
            if row is None:
                raise ValueError(
                    f"SQLAlchemyReportRepository.save(): no existing row for Report "
                    f"id={report.id!r} -- save() re-persists an already-add()-ed report, it "
                    f"does not insert a new one."
                )
            row.status = report.status.value

            # Citations are append-only from Report's own public API (no remove_citation()
            # exists), so the simplest correct sync is: delete any join rows not already
            # persisted, re-insert the full current ordered list. Cheap at this entity's real
            # scale (a handful of citations per Report, section 10.1).
            existing_ids = {c.interpretation_record_id for c in row.citations}
            for position, record_id in enumerate(report.citation_ids):
                if uuid.UUID(str(record_id)) not in existing_ids:
                    row.citations.append(
                        ReportCitationRow(
                            interpretation_record_id=record_id, position=position,
                        )
                    )
            session.commit()

    @staticmethod
    def _to_domain(session: Session, row: ReportRow) -> Report:
        report = Report(
            project_id=EntityId(row.project_id), entity_id=EntityId(row.id), version=row.version,
        )
        for citation in sorted(row.citations, key=lambda c: c.position):
            record_row = session.get(InterpretationRecordRow, citation.interpretation_record_id)
            if record_row is None:
                raise AssertionError(
                    f"Data integrity violation: report_citations row references "
                    f"interpretation_record_id={citation.interpretation_record_id!r}, which "
                    f"has no matching interpretation_records row."
                )
            record = InterpretationRecord(
                analysis_run_id=EntityId(record_row.analysis_run_id),
                kind=InterpretationRecordKind(record_row.kind),
                selector=record_row.selector,
                content=record_row.content,
                entity_id=EntityId(record_row.id),
            )
            report.add_citation(record)
        if row.status == ReportStatus.FINALIZED.value:
            report.finalize()
        return report


class SQLAlchemyInterpretationRecordRepository:
    """Backs `IInterpretationRecordRepository` (BACKLOG.md T-024/T-026). No `save()`:
    `InterpretationRecord` is immutable from construction (its own module docstring), so no
    "add-then-mutate" gap exists here -- `add()` alone is genuinely sufficient, unlike
    `CollectionRun`/`AnalysisRun`/`Report`.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, record: InterpretationRecord) -> None:
        with self._session_factory() as session:
            session.add(
                InterpretationRecordRow(
                    id=record.id,
                    analysis_run_id=record.analysis_run_id,
                    kind=record.kind.value,
                    selector=record.selector,
                    content=record.content,
                )
            )
            session.commit()

    def get_by_id(self, record_id: EntityId) -> InterpretationRecord | None:
        with self._session_factory() as session:
            row = session.get(InterpretationRecordRow, record_id)
            if row is None:
                return None
            return InterpretationRecord(
                analysis_run_id=EntityId(row.analysis_run_id),
                kind=InterpretationRecordKind(row.kind),
                selector=row.selector,
                content=row.content,
                entity_id=EntityId(row.id),
            )


class SQLAlchemyExportRepository:
    """Backs `IExportRepository` (BACKLOG.md T-027). No `save()`: `Export` is immutable from
    construction (same reasoning as `InterpretationRecord` above) -- `add()` alone is
    sufficient.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, export: Export) -> None:
        with self._session_factory() as session:
            session.add(
                ExportRow(
                    id=export.id,
                    report_id=export.report_id,
                    report_version=export.report_version,
                    format=export.format.value,
                )
            )
            session.commit()

    def get_by_report_version_and_format(
        self, report_id: EntityId, report_version: int, format: ExportFormat,
    ) -> Export | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ExportRow).where(
                    ExportRow.report_id == uuid.UUID(str(report_id)),
                    ExportRow.report_version == report_version,
                    ExportRow.format == format.value,
                )
            )
            if row is None:
                return None
            return Export(
                report_id=EntityId(row.report_id),
                report_version=row.report_version,
                format=ExportFormat(row.format),
                entity_id=EntityId(row.id),
            )


__all__ = [
    "SQLAlchemyAnalysisRunRepository",
    "SQLAlchemyCollectionRunRepository",
    "SQLAlchemyExportRepository",
    "SQLAlchemyInterpretationRecordRepository",
    "SQLAlchemyProjectRepository",
    "SQLAlchemyReportRepository",
]
