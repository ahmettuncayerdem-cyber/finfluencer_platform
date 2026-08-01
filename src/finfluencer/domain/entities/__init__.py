"""Domain entities (PRODUCT_ARCHITECTURE.md section 10.1).

BACKLOG.md T-007 (Sprint 0 Domain Model): four of section 10.1's fifteen entities --
`Tenant`, `Project`, `Dataset`, `CollectionRun`. BACKLOG.md T-018 (Sprint 2, EPIC-04) adds two
more: `AnalysisType`, `AnalysisRun`. BACKLOG.md T-024 (Sprint 4, EPIC-06) adds three more:
`InterpretationRecord` (kind=`raw_result_snapshot` only), `Report`, `Export`. The remaining six
(`User`, `TenantMembership`, `ProjectMembership`, `VerticalTemplate`, `Subscription`,
`AuditLogEntry`) are deliberately not implemented anywhere in this package -- see the TODO
comments in `tenant.py`, `project.py`, `dataset.py`, `collection_run.py`, `analysis_run.py`,
`interpretation_record.py`, and `report.py` for exactly where each one's ownership relationship
will attach, cited by PRODUCT_ARCHITECTURE.md section 10.1 line range.

No `domain.services.*` (`AuthorizationPolicy`, `ReproducibilityPolicy`,
`InterpretationProvenance`, section 12.1 line 838) exist yet either -- those operate across
entities not yet implemented (`ProjectMembership`) or are out of scope until the AI
Interpretation Layer (Roadmap Phase 2).
"""

from __future__ import annotations

from finfluencer.domain.entities._common import DomainInvariantViolation, EntityId
from finfluencer.domain.entities.analysis_run import AnalysisRun, AnalysisRunStatus
from finfluencer.domain.entities.analysis_type import AnalysisType
from finfluencer.domain.entities.collection_run import CollectionRun, CollectionRunStatus
from finfluencer.domain.entities.dataset import Dataset
from finfluencer.domain.entities.export import Export, ExportFormat
from finfluencer.domain.entities.interpretation_record import (
    InterpretationRecord,
    InterpretationRecordKind,
)
from finfluencer.domain.entities.project import Project, ProjectStatus
from finfluencer.domain.entities.report import Report, ReportStatus
from finfluencer.domain.entities.tenant import Tenant, TenantStatus

__all__ = [
    "AnalysisRun",
    "AnalysisRunStatus",
    "AnalysisType",
    "CollectionRun",
    "CollectionRunStatus",
    "Dataset",
    "DomainInvariantViolation",
    "EntityId",
    "Export",
    "ExportFormat",
    "InterpretationRecord",
    "InterpretationRecordKind",
    "Project",
    "ProjectStatus",
    "Report",
    "ReportStatus",
    "Tenant",
    "TenantStatus",
]
