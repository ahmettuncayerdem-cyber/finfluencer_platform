"""InterpretationRecord entity (PRODUCT_ARCHITECTURE.md section 10.0, section 10.1 lines
583-591).

Section 10.0's design resolution: "InterpretationRecord is generalized from 'AI-generated
commentary' to the general concept of an immutable, versioned, citable unit" -- discriminated by
`kind`. This task (BACKLOG.md T-024) implements only `kind: raw_result_snapshot` ("a frozen
snapshot of a specific table/figure/statistic taken from one AnalysisRun at cite-time. No AI
involved.", line 476) -- `kind: ai_generated` (line 477) is deliberately not implemented, per
T-024's own BACKLOG line ("deliberately without the ai_generated kind, which is out of scope
until Phase 2"). No `InterpretationRecordKind.AI_GENERATED` member exists; adding one before the
AI Interpretation Layer (BACKLOG.md, not yet numbered) actually exists would be a speculative
abstraction this task was not asked to build.

The strongest immutability guarantee of any entity in this package: unlike `CollectionRun`/
`AnalysisRun` ("immutable once completed" -- a state reached after construction), an
`InterpretationRecord` is immutable from the moment `__init__` returns. Section 10.1 line 588 is
explicit and leaves no lifecycle to model: "No API path may update an existing
`InterpretationRecord`; 'regenerate' ... always creates a new one." Consequently this class has
zero mutating methods -- there is no terminal-state guard because there is no non-terminal state.
"""

from __future__ import annotations

from enum import Enum

from finfluencer.domain.entities._common import EntityId, new_entity_id


class InterpretationRecordKind(str, Enum):
    """PRODUCT_ARCHITECTURE.md section 10.0, lines 476-477. Only the non-AI half is
    implemented here -- see this module's own docstring.

    TODO(PRODUCT_ARCHITECTURE.md section 10.0, line 477; section 9.4, AIG-001): `kind:
    ai_generated` ("bound by the full AIG-001 rule set... produced by SCR-ANLY-04") arrives
    with the AI Interpretation Layer (Roadmap Phase 2, section 8.5) -- not implemented until
    that epic exists. Adding the member now, with no code path that could ever construct it,
    would be exactly the kind of speculative abstraction this task's own discipline forbids.
    """

    RAW_RESULT_SNAPSHOT = "raw_result_snapshot"


class InterpretationRecord:
    """"the immutable, versioned, citable unit every `Report` references." (section 10.1, line
    584)
    """

    def __init__(
        self,
        analysis_run_id: EntityId,
        kind: InterpretationRecordKind,
        selector: str,
        content: str,
        *,
        entity_id: EntityId | None = None,
    ) -> None:
        if analysis_run_id is None:
            raise ValueError(
                "InterpretationRecord.analysis_run_id is required: 'belongs to exactly one "
                "`AnalysisRun`, always (both `kind`s -- this is AIG-001 Rule 2 made "
                "structural)' (section 10.1, line 586)."
            )
        if kind is None:
            raise ValueError("InterpretationRecord.kind is required (section 10.0, line 474).")
        if not selector or not selector.strip():
            raise ValueError(
                "InterpretationRecord.selector is required: identifies which table/figure/"
                "statistic this snapshot is of ('CreateRawSnapshot(analysisRunId, selector)', "
                "section 11.2, line 722)."
            )
        if not content or not content.strip():
            raise ValueError(
                "InterpretationRecord.content is required: the frozen snapshot itself ('a "
                "frozen snapshot of a specific table/figure/statistic', section 10.0, line "
                "476). Serialization format is deliberately unspecified here -- the caller "
                "constructing a real citation from AnalysisRun output (BACKLOG.md T-025) "
                "decides the concrete encoding; this entity only guarantees the container is "
                "immutable once set."
            )
        self._id = entity_id if entity_id is not None else new_entity_id()
        self._analysis_run_id = analysis_run_id
        self._kind = kind
        self._selector = selector
        self._content = content

        # TODO(PRODUCT_ARCHITECTURE.md section 10.1, Report, lines 593-601): "referenced by
        # many `Report` (a `Report` can cite several)" (line 586). Report does not hold a
        # reverse collection back to InterpretationRecord -- it stores this entity's `id` in
        # its own citations list (see report.py), the same one-directional-reference
        # convention CollectionRun/AnalysisRun already established (a CollectionRun does not
        # enumerate the AnalysisRuns that pin to it either).

    @property
    def id(self) -> EntityId:
        return self._id

    @property
    def analysis_run_id(self) -> EntityId:
        return self._analysis_run_id

    @property
    def kind(self) -> InterpretationRecordKind:
        return self._kind

    @property
    def selector(self) -> str:
        return self._selector

    @property
    def content(self) -> str:
        return self._content


__all__ = ["InterpretationRecord", "InterpretationRecordKind"]
