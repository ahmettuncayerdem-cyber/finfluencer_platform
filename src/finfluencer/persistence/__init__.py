"""Persistence Layer (PRODUCT_ARCHITECTURE.md section 12.1).

Responsibility: repository implementations, one per aggregate, per section 10's Project-as-
root-aggregate design. Storage technology is deliberately not named at the architecture level;
ADR-0001 (docs/adr/0001-technology-stack.md) names PostgreSQL + SQLAlchemy 2.0 as the accepted
implementation choice, with SQLAlchemy models kept strictly at this layer -- never leaking into
Domain (the specific failure mode ADR-0001 flags and guards against).

Allowed dependencies: Domain Layer (implements IRepository[T] per entity; translates domain
objects to/from a storage representation).
Forbidden dependencies: Presentation, API, Application (repositories are called *by* Application
through an interface Domain defined -- never initiate upward); Infrastructure (Persistence and
Infrastructure are peers, not dependent on each other). Not enforced by
scripts/check_layer_dependencies.py -- IG-001 does not name persistence's own forbidden-import
set; this discipline is a code-review concern for this layer.

Empty by design (BACKLOG.md T-006): the first repository lands with BACKLOG.md T-007's Domain
Model entities, not here.
"""

from __future__ import annotations
