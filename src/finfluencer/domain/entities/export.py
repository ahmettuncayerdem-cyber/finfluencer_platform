"""Export entity (PRODUCT_ARCHITECTURE.md section 10.1, lines 603-609).

Immutable from construction, same reasoning as `InterpretationRecord`: "an `Export` is a
rendering of a specific, already-immutable `Report` version; there's nothing to mutate." (line
608). Zero mutating methods, no terminal-state guard needed.
"""

from __future__ import annotations

from enum import Enum

from finfluencer.domain.entities._common import EntityId, new_entity_id


class ExportFormat(str, Enum):
    """PRODUCT_ARCHITECTURE.md section 8.4, line 299: "Rendered PDF (v1) / Word (v1.x)
    documents." Only `PDF` is implemented here -- `Word` is explicitly tagged v1.x (a later
    increment, not MVP-required per the Roadmap's own Phase 1 exit criteria, section 6).

    TODO(PRODUCT_ARCHITECTURE.md section 8.4, line 299; Roadmap section 5, Phase 1 vs 1.x):
    `WORD` arrives once its own task exists (not yet ticketed in EPIC-06's `T-024`-`T-028`
    range) -- adding the member now, with no adapter that could ever produce it, would be the
    same speculative-abstraction mistake `InterpretationRecordKind.AI_GENERATED` was flagged
    against.
    """

    PDF = "pdf"


class Export:
    """"one rendered artifact (PDF or Word) of a specific, finalized `Report` version."
    (section 10.1, line 604)
    """

    def __init__(
        self,
        report_id: EntityId,
        report_version: int,
        format: ExportFormat,
        *,
        entity_id: EntityId | None = None,
    ) -> None:
        if report_id is None:
            raise ValueError(
                "Export.report_id is required: 'belongs to exactly one `Report`' (section "
                "10.1, line 606)."
            )
        if report_version < 1:
            raise ValueError(
                "Export.report_version is required and must be >= 1: an Export belongs to "
                "'one `Report` *version*, per above' (section 10.1, line 606) -- pinning to a "
                "specific version, not a mutable Report-by-id reference, so a later Report "
                "edit (which creates a new version, line 599) can never silently change what "
                "an already-generated Export represents."
            )
        if format is None:
            raise ValueError("Export.format is required (section 10.1, line 604).")
        self._id = entity_id if entity_id is not None else new_entity_id()
        self._report_id = report_id
        self._report_version = report_version
        self._format = format

    @property
    def id(self) -> EntityId:
        return self._id

    @property
    def report_id(self) -> EntityId:
        return self._report_id

    @property
    def report_version(self) -> int:
        return self._report_version

    @property
    def format(self) -> ExportFormat:
        return self._format


__all__ = ["Export", "ExportFormat"]
