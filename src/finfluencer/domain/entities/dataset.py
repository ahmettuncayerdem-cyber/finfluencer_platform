"""Dataset entity (PRODUCT_ARCHITECTURE.md section 10.1, lines 553-561)."""

from __future__ import annotations

from finfluencer.domain.entities._common import EntityId, new_entity_id
from finfluencer.domain.entities.collection_run import CollectionRun


class Dataset:
    """"a named collection container within a Project (e.g., "YouTube comments, Analyst
    Roster A, Jan-Jun 2026")." (section 10.1, line 554)
    """

    def __init__(
        self,
        project_id: EntityId,
        name: str,
        *,
        description: str | None = None,
        entity_id: EntityId | None = None,
    ) -> None:
        if project_id is None:
            raise ValueError(
                "Dataset.project_id is required: 'belongs to exactly one `Project`' "
                "(section 10.1, line 556)."
            )
        if not name or not name.strip():
            raise ValueError("Dataset.name must be non-empty.")
        self._id = entity_id if entity_id is not None else new_entity_id()
        self._project_id = project_id
        self._name = name
        self._description = description
        # "owns many `CollectionRun` (its version/state history...)" (line 556).
        self._collection_runs: list[CollectionRun] = []

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, AnalysisRun, lines 573-581): "never
        # deleted while any `AnalysisRun` references it (referential integrity constraint for
        # Backend Architecture to enforce)" (line 557). Note the text's own wording: this is a
        # constraint for "Backend Architecture" (i.e. Application/Persistence, section 12) to
        # enforce, not the Domain entity itself -- there is deliberately no delete/remove
        # method on this class to guard against in the first place. AnalysisRun does not exist
        # yet in Sprint 0, so this constraint has no referent yet either.

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, AuditLogEntry, lines 623-631, and section
        # 12.2, line 864): "`Project`-scoped `AuditLogEntry` on creation and on each new
        # `CollectionRun`" (line 560). Not written by this entity -- Application-layer
        # responsibility, per the same reasoning as Tenant/CollectionRun.

    @property
    def id(self) -> EntityId:
        return self._id

    @property
    def project_id(self) -> EntityId:
        return self._project_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str | None:
        return self._description

    @property
    def collection_runs(self) -> tuple[CollectionRun, ...]:
        """Read-only view. "content only changes by adding a new `CollectionRun`, never by
        editing existing collected data in place" (line 558) -- there is deliberately no way
        to remove or replace an entry once added, only to append via `add_collection_run()`.
        """
        return tuple(self._collection_runs)

    def rename(self, new_name: str) -> None:
        """"the `Dataset` record itself (name, description) is mutable" (line 558)."""
        if not new_name or not new_name.strip():
            raise ValueError("Dataset.name must be non-empty.")
        self._name = new_name

    def update_description(self, new_description: str | None) -> None:
        """"the `Dataset` record itself (name, description) is mutable" (line 558)."""
        self._description = new_description

    def add_collection_run(self, collection_run: CollectionRun) -> None:
        """"its *content* is not directly mutable -- content only changes by adding a new
        `CollectionRun`" (line 558). The one way this entity's data ever grows.
        """
        if collection_run.dataset_id != self._id:
            raise ValueError(
                "CollectionRun.dataset_id does not match this Dataset's id -- "
                "a CollectionRun 'belongs to exactly one `Dataset`' (section 10.1, line 566)."
            )
        self._collection_runs.append(collection_run)
