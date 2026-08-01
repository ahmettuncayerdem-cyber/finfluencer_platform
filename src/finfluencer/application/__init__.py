"""Application Layer (PRODUCT_ARCHITECTURE.md section 12.1).

Responsibility: orchestrates each section 11 command/query into a coordinated sequence of
Domain and Infrastructure-interface calls. One orchestrator per command. Sequencing only --
no business rules here (BKG-001).

Allowed dependencies: Domain Layer; Infrastructure-defined interfaces only (IJobDispatcher,
IEventPublisher, ICheckpointRecorder, ILogger, IAuditWriter) -- never a concrete Infrastructure
class.
Forbidden dependencies: Presentation, API (never calls upward); concrete Infrastructure/
Persistence implementations. Not enforced by scripts/check_layer_dependencies.py -- IG-001
names presentation, api, and domain only; the "never a concrete class, only an interface"
discipline for this layer is a code-review concern, not a mechanically checkable import rule.

BACKLOG.md T-009 (CreateProject command): the first orchestrator,
`orchestrators.create_project.CreateProjectOrchestrator`, now lives here. Scoped by explicit
operator instruction to exactly what T-009 requires: no persistence implementation (depends on
`IProjectRepository`, an interface, only), no authentication, no authorization. Everything else
in section 11's command/query catalog (starting with `StartCollectionRun`, BACKLOG.md T-011)
grows this package per vertical slice, not speculatively ahead of time.
"""

from __future__ import annotations
