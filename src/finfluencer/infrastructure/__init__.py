"""Infrastructure Layer (PRODUCT_ARCHITECTURE.md section 12.1).

Responsibility: implements every interface Domain/Application defined, and is the only layer
allowed to talk to the outside world (provider adapters, AI adapters, jobs, events, checkpoint,
logging, audit, configuration -- section 12.2).

Allowed dependencies: Domain Layer (implements its interfaces); any external SDK/library -- the
only layer permitted to.
Forbidden dependencies: none named by IG-001 for this layer specifically -- IG-001
(IMPLEMENTATION_PLAYBOOK.md section 0) restricts what may import *from* infrastructure
(presentation, api, domain), not what infrastructure itself may import.

Empty by design (BACKLOG.md T-006): the first adapter wraps collect/ and providers/platform/
youtube.py (BACKLOG.md T-010), reusing tested existing code per IMPLEMENTATION_ROADMAP.md
section 3's reuse classification -- not rewritten here, not speculated on ahead of time.
"""

from __future__ import annotations
