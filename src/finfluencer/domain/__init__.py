"""Domain Layer (PRODUCT_ARCHITECTURE.md section 12.1).

Responsibility: the business rules themselves -- the actual subject of BKG-001. Rich entities
(every entity from section 10.1) enforcing their own lifecycle rules in code, not by convention.
Domain services hold cross-entity policy: AuthorizationPolicy, ReproducibilityPolicy,
InterpretationProvenance.

Allowed dependencies: none, outward. The one non-negotiable rule of the architecture: if Domain
cannot import Infrastructure, Persistence, API, or Presentation, business logic cannot leak into
those layers by construction.
Forbidden dependencies: everything outside itself -- Application, Presentation, API,
Infrastructure, Persistence, and any external SDK, no exceptions (enforced by
scripts/check_layer_dependencies.py, IG-001, IMPLEMENTATION_PLAYBOOK.md section 0).

BACKLOG.md T-007 (Sprint 0 Domain Model): the first four entities -- Tenant, Project, Dataset,
CollectionRun, per PRODUCT_ARCHITECTURE.md section 10.1 -- now live under
``finfluencer.domain.entities``. This is a deliberate subset, not all fifteen section 10.1
entities: User, TenantMembership, ProjectMembership, VerticalTemplate, AnalysisType,
InterpretationRecord, Report, Export, Subscription, and AuditLogEntry are intentionally deferred
to later tasks and are not implemented anywhere in this package yet. Each deferred entity's
extension point is marked with a TODO comment in the owning module, citing the exact
PRODUCT_ARCHITECTURE.md section 10.1 line range it will implement. No authorization logic exists
here either -- ``AuthorizationPolicy`` (section 12.1) is not yet implemented.

BACKLOG.md T-009 (CreateProject command): ``finfluencer.domain.repositories`` adds
``IProjectRepository``, the one repository interface Application's new
``CreateProjectOrchestrator`` depends on. No concrete implementation exists anywhere yet --
Persistence Layer work is explicitly out of scope until a later task.

This top-level package intentionally re-exports nothing: import from
``finfluencer.domain.entities`` or ``finfluencer.domain.repositories`` directly. No mandatory
cross-vendor AI architecture review (IMPLEMENTATION_PLAYBOOK.md Part B.1) has yet been
performed against either change from a genuinely different vendor/session -- BACKLOG.md records
this as an open item, not a satisfied gate.
"""

from __future__ import annotations
