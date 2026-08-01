"""Presentation Layer (PRODUCT_ARCHITECTURE.md section 12.1).

Responsibility: wire protocol and contract shape -- REST/JSON envelope format, API versioning
scheme, uniform error-response shape, one DTO pair per section 11 command/query.

Allowed dependencies: API Layer only.
Forbidden dependencies: Application, Domain, Infrastructure, Persistence (enforced by
scripts/check_layer_dependencies.py, IG-001, IMPLEMENTATION_PLAYBOOK.md section 0).

Empty by design (BACKLOG.md T-006): DTOs are added per API Contract slice as each vertical slice
needs them, not speculatively ahead of time.
"""

from __future__ import annotations
