"""Report entity (PRODUCT_ARCHITECTURE.md section 10.0, section 10.1 lines 593-601).

Section 10.0's core rule, structurally enforced here rather than merely documented: "Report only
ever references `InterpretationRecord` entities, never a live `AnalysisRun` pointer" (line 479).
Concretely, that means this module never imports `AnalysisRun` at all -- there is no
`analysis_run_id` field, no `AnalysisRun`-typed attribute, no path by which a `Report` could hold
a live reference to a mutable-until-completed run. Citations are stored as `InterpretationRecord`
ids only -- immutable-record references, exactly as section 10.0 requires. Verified structurally
by this package's own test suite (an ast-based no-import check, the same technique
`test_t023_plugin_generalization.py` established for the orchestrator), not left to convention
alone.
"""

from __future__ import annotations

from enum import Enum

from finfluencer.domain.entities._common import (
    DomainInvariantViolation,
    EntityId,
    new_entity_id,
)
from finfluencer.domain.entities.interpretation_record import InterpretationRecord


class ReportStatus(str, Enum):
    """PRODUCT_ARCHITECTURE.md section 10.1, line 597: "`draft -> finalized`; a finalized
    `Report` is what `Export` renders from; editable while in `draft`."
    """

    DRAFT = "draft"
    FINALIZED = "finalized"


class Report:
    """"an assembled, citable document referencing one or more `InterpretationRecord`s."
    (section 10.1, line 594)
    """

    def __init__(
        self,
        project_id: EntityId,
        *,
        entity_id: EntityId | None = None,
        version: int = 1,
    ) -> None:
        if project_id is None:
            raise ValueError(
                "Report.project_id is required: 'belongs to exactly one `Project`' (section "
                "10.1, line 596). The `SCR-XPRJ-01` v1.x cross-project exception (same line) "
                "is out of scope for this task -- not silently supported."
            )
        if version < 1:
            raise ValueError("Report.version must be >= 1.")
        self._id = entity_id if entity_id is not None else new_entity_id()
        self._project_id = project_id
        self._version = version
        self._status = ReportStatus.DRAFT
        self._citation_ids: list[EntityId] = []

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, line 599): "editing a finalized Report
        # creates a new version (`Report v2`) rather than mutating the finalized one." The
        # `version` field exists so a future command has something to increment; the actual
        # create-new-version-from-old orchestration is Application-layer work (BACKLOG.md,
        # not yet ticketed) -- mirrors how AnalysisRun's retry-creates-new-run logic lives in
        # T-020's orchestrator, never inside AnalysisRun itself. Not invented speculatively
        # here.

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, Export, lines 603-609): "belongs to
        # exactly one `Report` (specifically, one `Report` *version*)" (line 606). Report does
        # not hold a reverse collection to its Exports -- same one-directional-reference
        # convention as InterpretationRecord above.

    @property
    def id(self) -> EntityId:
        return self._id

    @property
    def project_id(self) -> EntityId:
        return self._project_id

    @property
    def version(self) -> int:
        return self._version

    @property
    def status(self) -> ReportStatus:
        return self._status

    @property
    def citation_ids(self) -> tuple[EntityId, ...]:
        """Read-only view of cited `InterpretationRecord` ids -- mutation only via
        `add_citation()`. A tuple, not the internal list, so a caller cannot silently mutate a
        "frozen snapshot" of citations out from under this Report (section 10.0's own
        reasoning for why raw citations became immutable too, line 479).
        """
        return tuple(self._citation_ids)

    def _reject_if_finalized(self) -> None:
        if self._status is ReportStatus.FINALIZED:
            raise DomainInvariantViolation(
                "Report is finalized (section 10.1, line 598: 'immutable once finalized') -- "
                "no further mutation is permitted. Create a new version instead of editing "
                "this one (line 599)."
            )

    def add_citation(self, record: InterpretationRecord) -> None:
        """"references many `InterpretationRecord`" (line 596). Stores only `record.id` --
        never the `InterpretationRecord` instance itself, and never touches
        `record.analysis_run_id` -- this method's whole signature exists to make "cites
        InterpretationRecord, never a live AnalysisRun pointer" (section 10.0, line 479)
        impossible to violate by construction, not just by convention.
        """
        self._reject_if_finalized()
        if record is None:
            raise ValueError("Report.add_citation() requires a non-None InterpretationRecord.")
        self._citation_ids.append(record.id)

    def finalize(self) -> None:
        """`draft -> finalized` (line 597). Terminal -- there is deliberately no
        `unfinalize()`, since section 10.1 names only a forward transition (a new version is
        how a "finalized" Report is ever changed again, not reverting this one).
        """
        self._reject_if_finalized()
        self._status = ReportStatus.FINALIZED


__all__ = ["Report", "ReportStatus"]
