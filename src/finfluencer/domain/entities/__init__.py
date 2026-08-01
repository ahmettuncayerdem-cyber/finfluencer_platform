"""Domain entities (PRODUCT_ARCHITECTURE.md section 10.1).

BACKLOG.md T-007 (Sprint 0 Domain Model): four of section 10.1's fifteen entities --
`Tenant`, `Project`, `Dataset`, `CollectionRun`. BACKLOG.md T-018 (Sprint 2, EPIC-04) adds two
more: `AnalysisType`, `AnalysisRun`. The remaining nine (`User`, `TenantMembership`,
`ProjectMembership`, `VerticalTemplate`, `InterpretationRecord`, `Report`, `Export`,
`Subscription`, `AuditLogEntry`) are deliberately not implemented anywhere in this package --
see the TODO comments in `tenant.py`, `project.py`, `dataset.py`, `collection_run.py`, and
`analysis_run.py` for exactly where each one's ownership relationship will attach, cited by
PRODUCT_ARCHITECTURE.md section 10.1 line range.

No `domain.services.*` (`AuthorizationPolicy`, `ReproducibilityPolicy`,
`InterpretationProvenance`, section 12.1 line 838) exist yet either -- those operate across
entities not yet implemented (`ProjectMembership`, `InterpretationRecord`) or are out of this
task's scope.
"""

from __future__ import annotations

from finfluencer.domain.entities._common import DomainInvariantViolation, EntityId
from finfluencer.domain.entities.analysis_run import AnalysisRun, AnalysisRunStatus
from finfluencer.domain.entities.analysis_type import AnalysisType
from finfluencer.domain.entities.collection_run import CollectionRun, CollectionRunStatus
from finfluencer.domain.entities.dataset import Dataset
from finfluencer.domain.entities.project import Project, ProjectStatus
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
    "Project",
    "ProjectStatus",
    "Tenant",
    "TenantStatus",
]
