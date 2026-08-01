"""API Layer (PRODUCT_ARCHITECTURE.md section 12.1).

Responsibility: HTTP routing per section 11.3's endpoint derivation, authentication token
validation (delegated to Identity Service), authorization enforcement via CheckAuthorization,
idempotency-key deduplication, rate limiting.

Allowed dependencies: Application Layer (invokes orchestrators/use cases); Presentation Layer
(DTO translation).
Forbidden dependencies: Domain directly, Infrastructure, Persistence (enforced by
scripts/check_layer_dependencies.py, IG-001, IMPLEMENTATION_PLAYBOOK.md section 0).

Empty by design (BACKLOG.md T-006): routes are added per API Contract slice as each vertical
slice needs them, not speculatively ahead of time.
"""

from __future__ import annotations
