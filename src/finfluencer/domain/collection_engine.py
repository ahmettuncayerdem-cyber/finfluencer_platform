"""Collection Engine port (PRODUCT_ARCHITECTURE.md section 12.1, line 839: Domain "defines but
never implements ... `IAIProvider` -- the last one is Domain stating 'an AI provider must
accept a prompt and a manifest hash and return text plus a model-version tag,' without knowing
or caring which LLM actually answers." `ICollectionEngine` below follows the identical pattern
for the Collection Engine instead of an AI provider: Domain states the shape of "run a
collection," Infrastructure supplies the implementation, and nothing above Infrastructure knows
or needs to know that the implementation happens to be `collect/` + `providers/platform/*`
under the hood.

BACKLOG.md T-010 scope: this interface is what T-010's own acceptance criterion requires
("adapter implements the Infrastructure interface the orchestrator (T-011) will call") -- it did
not exist before this task, and creating it is this task's job, not a new abstraction invented
beyond what the architecture calls for. No concrete implementation lives here -- see
`finfluencer.infrastructure.collection`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CollectionOutcome:
    """Domain-safe summary of one collection run.

    Deliberately plain (str, dict[str, int]) -- no pandas DataFrame, no Pydantic Settings/
    AnalystRoster object crosses this boundary. Those are Infrastructure-internal
    implementation detail (section 12.1's "any external SDK... no exceptions" rule for Domain);
    this is the Domain-safe shape a future orchestrator (T-011) can depend on without importing
    pandas or `finfluencer.core.contracts` into Application/Domain.
    """

    run_id: str
    stage_row_counts: dict[str, int]


class ICollectionEngine(Protocol):
    """Domain- and Application-owned interface (section 12.1 line 831 pattern, applied here to
    the Collection Engine instead of a repository).
    """

    def run(self, run_id: str) -> CollectionOutcome:
        """Run (or resume) collection for the given ``run_id``.

        ``run_id`` is the caller's own identifier for one collection attempt -- a future
        orchestrator (T-011) is expected to pass a `CollectionRun.id` (section 10.1) once that
        entity exists in this data flow, but this interface does not require or assume that;
        it only requires a stable string a caller will not reuse across two logically distinct
        runs it wants isolated from each other. Calling this again with the same ``run_id`` is
        the resume path -- an already-completed run's cost is a fast no-op re-read, not a
        re-collection, per the legacy engine's own checkpoint discipline (unchanged by this
        interface).
        """
        ...
