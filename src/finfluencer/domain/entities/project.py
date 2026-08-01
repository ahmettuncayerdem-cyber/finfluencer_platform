"""Project entity -- the root aggregate (PRODUCT_ARCHITECTURE.md section 10.1, lines 543-551).

    "Project — the root aggregate"
    "the unit a researcher thinks in ("my study"); owns everything beneath it, per this
    turn's explicit instruction." (line 544)

Sprint 0 scope note (BACKLOG.md T-007): of everything section 10.1 says Project owns, only
`Dataset` is implemented as an in-memory child collection here -- `AnalysisRun`,
`InterpretationRecord`, `Report`, `Export`, `ProjectMembership`, and `AuditLogEntry` are all out
of scope for this task and are marked with TODOs below at their exact ownership line.

Archival is modeled as the aggregate-root-level concern section 10.1 says it is:

    "the `active -> archived` transition is a one-way state change that then freezes
    everything inside the aggregate -- archival is enforced at the aggregate root, not
    per-child-entity, which is precisely why Project must be the root aggregate rather than a
    loose grouping." (line 548)

Concretely, this means: `Project.archive()` is the only archival mechanism that exists anywhere
in this Sprint 0 subset (no `Dataset.archive()` or `CollectionRun.archive()`), and `Project`
itself refuses further mutation once archived. What this deliberately does NOT do -- because
section 10.1 says enforcement happens "at the aggregate root, not per-child-entity" -- is add an
archived-check inside `Dataset`'s or `CollectionRun`'s own methods; calling
`dataset.rename(...)` directly on a `Dataset` object taken from an archived `Project` is not
guarded by this entity. Cross-aggregate enforcement of that kind is a Persistence/Application
Layer concern (the `ProjectRepository` loading the whole aggregate in one place, section 12.1
line 851), not something invented here without textual support.
"""

from __future__ import annotations

from enum import Enum

from finfluencer.domain.entities._common import (
    DomainInvariantViolation,
    EntityId,
    new_entity_id,
)
from finfluencer.domain.entities.dataset import Dataset


class ProjectStatus(str, Enum):
    """PRODUCT_ARCHITECTURE.md section 10.1, line 547:

    "created (SCR-PROJ-01) -> active -> archived (SCR-PROJ-03/04, section 7.2 stage 7) ->
    (no hard-delete state in v1...)."
    """

    ACTIVE = "active"
    ARCHIVED = "archived"


class Project:
    """The root aggregate (section 10.1, line 543)."""

    def __init__(
        self,
        tenant_id: EntityId,
        name: str,
        *,
        entity_id: EntityId | None = None,
    ) -> None:
        if tenant_id is None:
            raise ValueError(
                "Project.tenant_id is required: 'belongs to exactly one `Tenant`' "
                "(section 10.1, line 546)."
            )
        if not name or not name.strip():
            raise ValueError("Project.name must be non-empty.")
        self._id = entity_id if entity_id is not None else new_entity_id()
        self._tenant_id = tenant_id
        self._name = name
        self._status = ProjectStatus.ACTIVE
        # "owns many `Dataset`..." (line 546).
        self._datasets: list[Dataset] = []

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, VerticalTemplate, lines 523-531): Project
        # "references exactly one `VerticalTemplate` (pinned version, per above)" (line 546),
        # and "not versioned itself (it's the container), but its `VerticalTemplate` reference
        # is pinned... this is how a Project stays reproducible even as the platform's templates
        # evolve" (line 549). VerticalTemplate is out of Sprint 0 scope; no
        # `vertical_template_id` field is added here rather than pointing at an entity type
        # that does not exist yet.

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, AnalysisRun, lines 573-581; and
        # InterpretationRecord, Report, Export, lines 583-611): Project "owns many
        # `AnalysisRun`, many `InterpretationRecord` (transitively, via `AnalysisRun`), many
        # `Report`, many `Export` (transitively, via `Report`)" (line 546). None of these four
        # entities are implemented in Sprint 0 (BACKLOG.md T-007 scopes only Tenant, Project,
        # Dataset, CollectionRun).

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, ProjectMembership, lines 513-521): Project
        # "owns many `ProjectMembership`" (line 546). Not implemented -- arrives with future
        # Identity Service work (BACKLOG.md EPIC-01).

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, AuditLogEntry, lines 623-631): "the primary
        # audit boundary of the platform... Every state-changing action on anything inside the
        # aggregate... produces a `Project`-scoped `AuditLogEntry`" (line 550). Per section 12.2
        # line 864, audit writing is an Application-layer responsibility (`IAuditWriter`,
        # invoked by orchestrators after a Domain transition succeeds) -- deliberately not
        # implemented inside this entity.

    @property
    def id(self) -> EntityId:
        return self._id

    @property
    def tenant_id(self) -> EntityId:
        return self._tenant_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> ProjectStatus:
        return self._status

    @property
    def datasets(self) -> tuple[Dataset, ...]:
        """Read-only view -- mutation only via `add_dataset()`."""
        return tuple(self._datasets)

    def _reject_if_archived(self) -> None:
        if self._status is ProjectStatus.ARCHIVED:
            raise DomainInvariantViolation(
                "Project is archived; the active -> archived transition 'freezes everything "
                "inside the aggregate' (section 10.1, line 548) -- no further mutation is "
                "permitted through Project."
            )

    def rename(self, new_name: str) -> None:
        """"Mutable while active (roster, config)" (line 548)."""
        self._reject_if_archived()
        if not new_name or not new_name.strip():
            raise ValueError("Project.name must be non-empty.")
        self._name = new_name

    def add_dataset(self, dataset: Dataset) -> None:
        """The aggregate-root-controlled way `Project` acquires a `Dataset` it owns."""
        self._reject_if_archived()
        if dataset.project_id != self._id:
            raise ValueError(
                "Dataset.project_id does not match this Project's id -- "
                "a Dataset 'belongs to exactly one `Project`' (section 10.1, line 556)."
            )
        self._datasets.append(dataset)

    def archive(self) -> None:
        """"the `active -> archived` transition is a one-way state change" (line 548). Terminal
        -- there is deliberately no `unarchive()`/`reactivate()` method, since section 10.1
        never names one and "one-way" is stated explicitly, not merely implied.
        """
        self._reject_if_archived()
        self._status = ProjectStatus.ARCHIVED
