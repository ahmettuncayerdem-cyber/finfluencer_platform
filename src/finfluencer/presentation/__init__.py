"""Presentation Layer (PRODUCT_ARCHITECTURE.md section 12.1).

Responsibility: wire protocol and contract shape -- REST/JSON envelope format, API versioning
scheme, uniform error-response shape, one DTO pair per section 11 command/query.

Allowed dependencies: API Layer only.
Forbidden dependencies: Application, Domain, Infrastructure, Persistence (enforced by
scripts/check_layer_dependencies.py, IG-001, IMPLEMENTATION_PLAYBOOK.md section 0).

BACKLOG.md T-008 (API Contract schema for the skeleton slice): the first DTOs -- one pair per
PRODUCT_ARCHITECTURE.md section 11.2 command/query, for `CreateProject` (Identity Service) and
`StartCollectionRun`/`GetCollectionRun` (Collection Service) -- now live under
`finfluencer.presentation.dto`. Built with Pydantic (an external SDK, which is explicitly
permitted here: this layer's forbidden-dependency list, per section 12.1 line 813, names
Application/Domain/Infrastructure/Persistence, not third-party libraries -- unlike Domain,
which forbids every external SDK with no exceptions). DTOs never import a Domain entity
directly (section 12.1 line 813) -- status values are re-declared as independent `Literal`
types in this layer rather than importing `ProjectStatus`/`CollectionRunStatus` from
`finfluencer.domain.entities`.
"""

from __future__ import annotations
