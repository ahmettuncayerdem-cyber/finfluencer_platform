"""SQLAlchemy ORM models (BACKLOG.md EPIC-07', ADR-0001-A) -- Persistence-layer-only, per this
package's own `__init__.py` docstring and ADR-0001's explicit guard: "SQLAlchemy models must not
leak into Domain... Domain entities stay plain... objects; SQLAlchemy models are
Persistence-layer-only, mapped at the boundary." No file outside `persistence/` imports this
module. `sqlalchemy_repositories.py` is the only translation boundary between these rows and the
real `domain/entities/*.py` objects the rest of the platform actually works with.

One model per BACKLOG.md-scoped entity -- `Project`, `CollectionRun`, `AnalysisRun`, `Report`
(plus its `ReportCitation` join rows), `InterpretationRecord`, `Export` -- matching exactly the
six repository interfaces `domain/repositories.py` already defines. No `Dataset` table:
`Dataset` has no repository interface anywhere in this codebase yet (bootstrap.py's own
docstring: "there is no real `CreateDataset` command yet... no real way to obtain a `dataset_id`
other than generating one client-side") -- `CollectionRun.dataset_id` is stored as a plain UUID
column with no foreign key, honestly reflecting that there is nothing to reference yet, not
inventing a `datasets` table this task was not asked to build. Same reasoning for
`AnalysisRun.analysis_type_id` (no `AnalysisType` table exists; `bootstrap.py` mints exactly two
fixed, well-known ids at process-start, per Release Blocker #6).

Every column type below is deliberately dialect-portable (`Uuid`, `String`, `Integer`,
`DateTime`, `Text`) -- see ADR-0001-A's forward-compatibility guarantee: none of this needs to
change to run against PostgreSQL instead of SQLite later.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid


class Base(DeclarativeBase):
    """Shared declarative base for every model in this module -- `db.create_all_tables()`
    and every `alembic/env.py` autogeneration pass both key off this one `Base.metadata`.
    """


def _utcnow() -> datetime:
    """Single shared "row created at" default -- Python-side (not a DB `server_default`) so
    it behaves identically across SQLite and a future PostgreSQL backend without relying on
    either dialect's own `CURRENT_TIMESTAMP` semantics (ADR-0001-A's forward-compatibility
    guarantee, applied to timestamps specifically).
    """
    return datetime.now(timezone.utc)


class ProjectRow(Base):
    """Backs `IProjectRepository` / `domain.entities.project.Project`."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class CollectionRunRow(Base):
    """Backs `ICollectionRunRepository` / `domain.entities.collection_run.CollectionRun`.

    `idempotency_key` + `dataset_id` carry a real `UniqueConstraint`: the interface's own
    docstring guarantees `add()` is "called exactly once per key" for this repository
    (unlike `AnalysisRunRow` below) -- the constraint makes a violation of that documented
    contract a loud database error instead of a silent duplicate row.
    """

    __tablename__ = "collection_runs"
    __table_args__ = (
        UniqueConstraint("dataset_id", "idempotency_key", name="uq_collection_run_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class AnalysisRunRow(Base):
    """Backs `IAnalysisRunRepository` / `domain.entities.analysis_run.AnalysisRun`.

    Deliberately NO unique constraint on `(project_id, idempotency_key)` -- unlike
    `CollectionRunRow` above, the interface's own docstring requires the opposite guarantee
    here: "this method may legitimately be called more than once for the same
    `idempotency_key`... each retry after a `FAILED` attempt persists a *new* `AnalysisRun`."
    `get_by_idempotency_key()` resolves the ambiguity by ordering on `created_at` and
    returning the newest row -- see `sqlalchemy_repositories.py`.
    """

    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    collection_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("collection_runs.id"), nullable=False,
    )
    analysis_type_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    analysis_type_version: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class ReportRow(Base):
    """Backs `IReportRepository` / `domain.entities.report.Report`.

    `citations` is the ordered association to `ReportCitationRow` below -- `Report.citation_ids`
    (domain) is an ordered tuple, and `Report.add_citation()` appends, so `position` (not
    insertion order alone, which SQL does not guarantee on read-back) is what
    `sqlalchemy_repositories.py` sorts by when reconstructing a domain `Report`.
    """

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    citations: Mapped[list["ReportCitationRow"]] = relationship(
        back_populates="report", order_by="ReportCitationRow.position", cascade="all, delete-orphan",
    )


class ReportCitationRow(Base):
    """Join row: one cited `InterpretationRecord` id, at one ordered `position`, for one
    `ReportRow`. Not itself a Domain entity -- `Report.citation_ids` (domain) is a plain tuple of
    ids; this table only exists because a relational store needs a real row per list element,
    the storage-layer translation `persistence/__init__.py`'s own docstring says this layer is
    responsible for.
    """

    __tablename__ = "report_citations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reports.id"), index=True, nullable=False,
    )
    interpretation_record_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    report: Mapped["ReportRow"] = relationship(back_populates="citations")


class InterpretationRecordRow(Base):
    """Backs `IInterpretationRecordRepository` /
    `domain.entities.interpretation_record.InterpretationRecord`. `content` is `Text`, not
    `String` -- a "frozen snapshot of a specific table/figure/statistic" (the entity's own
    docstring) can be arbitrarily large serialized content, not a short label.
    """

    __tablename__ = "interpretation_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    selector: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class ExportRow(Base):
    """Backs `IExportRepository` / `domain.entities.export.Export`. Real `UniqueConstraint` on
    the natural key the interface's own docstring names: "`(report_id, report_version, format)`
    already uniquely determines an Export."
    """

    __tablename__ = "exports"
    __table_args__ = (
        UniqueConstraint(
            "report_id", "report_version", "format", name="uq_export_natural_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    report_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    report_version: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


__all__ = [
    "AnalysisRunRow",
    "Base",
    "CollectionRunRow",
    "ExportRow",
    "InterpretationRecordRow",
    "ProjectRow",
    "ReportCitationRow",
    "ReportRow",
]
