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

Empty by design (BACKLOG.md T-006): orchestrators are added per vertical slice, starting with
StartCollectionRun (BACKLOG.md T-011), not speculatively ahead of time.
"""

from __future__ import annotations
