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

Empty by design (BACKLOG.md T-006): the first four entities (Tenant, Project, Dataset,
CollectionRun) land in BACKLOG.md T-007, not here -- cross-vendor AI review is mandatory for that
change (IMPLEMENTATION_PLAYBOOK.md Part B.1), this scaffold is deliberately reviewed at lower
ceremony since it contains no business logic yet.
"""

from __future__ import annotations
