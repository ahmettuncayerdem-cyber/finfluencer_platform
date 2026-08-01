"""AnalysisType entity (PRODUCT_ARCHITECTURE.md section 10.1, lines 533-541).

Catalog definition of one pluggable analysis kind (topic modeling, sentiment, market
correlation, future types) -- "the concrete mechanism behind section 5's 'pluggable analysis
types, not pipeline stages' claim" (line 537).
"""

from __future__ import annotations

from finfluencer.domain.entities._common import EntityId, new_entity_id


class AnalysisType:
    """"catalog definition of one pluggable analysis kind" (section 10.1, line 534).

    Deliberately minimal for BACKLOG.md T-018: only the identity and pinned-version fields an
    `AnalysisRun` needs to reference (line 539: "an `AnalysisRun` records which `AnalysisType`
    version produced it, so re-deriving old results means running the same version, not
    whatever the type has since become"). The catalog itself (parameter schemas, which types
    exist, how they're added) is "platform-managed" (line 537) -- an Application/Infrastructure
    concern for a future task, not modeled here to avoid speculative work T-018 does not ask for.
    """

    def __init__(
        self, key: str, version: str, *, entity_id: EntityId | None = None
    ) -> None:
        if not key or not key.strip():
            raise ValueError(
                "AnalysisType.key is required: 'catalog definition of one pluggable analysis "
                "kind' (section 10.1, line 534)."
            )
        if not version or not version.strip():
            raise ValueError(
                "AnalysisType.version is required: 'versioned ... an AnalysisRun records which "
                "AnalysisType version produced it' (section 10.1, line 539)."
            )
        self._id = entity_id if entity_id is not None else new_entity_id()
        self._key = key
        self._version = version

    @property
    def id(self) -> EntityId:
        return self._id

    @property
    def key(self) -> str:
        """Catalog key, e.g. ``"topic_modeling"``."""
        return self._key

    @property
    def version(self) -> str:
        """The specific version an `AnalysisRun` pins to (line 539) -- distinct from the
        catalog's current version, which may have since moved on.
        """
        return self._version


__all__ = ["AnalysisType"]
