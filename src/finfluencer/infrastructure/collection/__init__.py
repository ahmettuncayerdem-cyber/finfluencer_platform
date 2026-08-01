"""Collection Engine Infrastructure adapter (BACKLOG.md T-010).

Implements `finfluencer.domain.collection_engine.ICollectionEngine` by wrapping the existing,
tested `finfluencer.collect.*` stage functions and `finfluencer.core.checkpoint.CheckpointManager`
-- unmodified -- behind one adapter class, per IMPLEMENTATION_ROADMAP.md section 3's "Wrapper
required" classification for the Collection Engine.

Fixture-only in this task: `FixtureCollectionProvider` (a `PlatformProvider` implementation
backed by `fixture_data.py`'s canned dataset) is the only provider wired in here -- no live
network dependency exists anywhere in this package. A real, YouTube-network-backed provider
adapter (e.g. wrapping `providers/platform/youtube.py` directly) is a separate, not-yet-numbered
future task; swapping one in requires no change to `CollectionEngineAdapter`, only a different
constructor argument.

See `CONTEXT_PACK.md` in this directory (IMPLEMENTATION_PLAYBOOK.md Part B.2) and
`docs/adr/0002-collection-run-checkpoint-root-partitioning.md` for the Roadmap Risk R-1
partitioning decision.
"""

from __future__ import annotations

from finfluencer.infrastructure.collection.collection_engine_adapter import (
    CollectionEngineAdapter,
)
from finfluencer.infrastructure.collection.fixture_provider import (
    FixtureCollectionProvider,
    fixture_transcript_fetcher,
)

__all__ = [
    "CollectionEngineAdapter",
    "FixtureCollectionProvider",
    "fixture_transcript_fetcher",
]
