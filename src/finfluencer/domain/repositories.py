"""Repository interfaces (PRODUCT_ARCHITECTURE.md section 12.1, line 839: Domain "defines but
never implements `IRepository<T>`..."; line 831: "Application and Domain jointly own these
interfaces; Infrastructure/Persistence only ever implement them.").

BACKLOG.md T-009 scope: `IProjectRepository` only, and only the one method `CreateProject`
needs (`add`). Grows per-epic exactly like the Domain Model (T-007) and the API Contract
(T-008) before it -- not designed speculatively ahead of what the current task needs.

No concrete implementation exists anywhere in this repository yet. BACKLOG.md T-009 explicitly
excludes Persistence Layer work ("No persistence implementation yet," operator instruction,
2026-08-01). A test double implementing this `Protocol` (as used in
`tests/unit/test_application/test_create_project_orchestrator.py`) is an ordinary test fixture,
not a Persistence-layer implementation -- it never touches `src/finfluencer/persistence/`.
"""

from __future__ import annotations

from typing import Protocol

from finfluencer.domain.entities.project import Project


class IProjectRepository(Protocol):
    """Domain- and Application-owned interface, per section 12.1 lines 831/839 above."""

    def add(self, project: Project) -> None:
        """Persist a newly created Project.

        No `get`/`update`/`delete` method exists on this interface yet -- `CreateProject`
        (T-009) only ever adds a new Project. A fuller repository surface arrives with
        whichever future task first needs to read a Project back (e.g. `GetProject`,
        section 11.2 line 658).
        """
        ...
