"""Infrastructure Layer (PRODUCT_ARCHITECTURE.md section 12.1).

Responsibility: implements every interface Domain/Application defined, and is the only layer
allowed to talk to the outside world (provider adapters, AI adapters, jobs, events, checkpoint,
logging, audit, configuration -- section 12.2).

Allowed dependencies: Domain Layer (implements its interfaces); any external SDK/library -- the
only layer permitted to.
Forbidden dependencies: PRODUCT_ARCHITECTURE.md section 12.1 line 845 names Presentation and API
("never calls upward -- a job worker doesn't know it was triggered by an HTTP request, only
that Application dispatched it") -- not mechanically enforced by
scripts/check_layer_dependencies.py's IG-001 checker, which restricts what may import *from*
infrastructure (presentation, api, domain), not what infrastructure itself may import. Honored
as a textual rule regardless, the same discipline applied to Application in BACKLOG.md T-009.

BACKLOG.md T-010 (Collection Engine adapter): ``finfluencer.infrastructure.collection`` wraps
`collect/` + `providers/platform/*` behind ``ICollectionEngine``
(``finfluencer.domain.collection_engine``), reusing tested existing code per
IMPLEMENTATION_ROADMAP.md section 3's reuse classification -- not rewritten here. Fixture-backed
only in this task (no live network dependency yet, per BACKLOG.md T-010's own scope) -- a real
YouTube-backed provider adapter is a later, not-yet-numbered task.
"""

from __future__ import annotations
