"""API routes (PRODUCT_ARCHITECTURE.md section 12.1: "`api.routes.*` (one per section 11.2
service -- `api.routes.collection`, ..., `api.routes.identity`, ...)").

BACKLOG.md T-012 scope: `identity.py` (`CreateProject`) and `collection.py`
(`StartCollectionRun`) only -- the two operations the Walking Skeleton's frontend needs. Grows
one module per service as each vertical slice needs it, same discipline as
`application.orchestrators` and `presentation.dto`.

Every module here imports only `finfluencer.application.orchestrators.*` (to invoke, never to
reimplement) and `finfluencer.presentation.dto.*` (request/response shapes) -- never
`finfluencer.domain`, `finfluencer.infrastructure`, or `finfluencer.persistence` directly
(section 12.1: "Forbidden dependencies: Domain directly... Infrastructure, Persistence").
`scripts/check_layer_dependencies.py`'s IG-001 checker mechanically enforces the
Infrastructure/Persistence half of this for the `api` layer; the Domain half is not in its
`FORBIDDEN_IMPORTS` rule set (see the script's own docstring: IG-001 "verbatim" only forbids
`api` importing `infrastructure`/`persistence`, not `domain`) -- honored here via a dedicated
`ast`-based test, the same discipline used for every layer boundary this engagement has found
mechanically uncovered so far (Application, Infrastructure, and now this one).

Concrete orchestrator instances are never constructed here -- that is `bootstrap.py`'s job (the
one, deliberately-outside-the-six-layers composition root; see its own module docstring for why
that placement is necessary and not a new architectural layer). Routes reach their orchestrator
via `api.deps`, which reads it off `Request.app.state` -- itself only referencing Application
types, never a concrete Infrastructure class.
"""

from __future__ import annotations
