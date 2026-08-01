"""Collection Engine Infrastructure adapter (BACKLOG.md T-010, T-015).

Implements `finfluencer.domain.collection_engine.ICollectionEngine` by wrapping the existing,
tested `finfluencer.collect.*` stage functions and `finfluencer.core.checkpoint.CheckpointManager`
-- unmodified -- behind one adapter class, per IMPLEMENTATION_ROADMAP.md section 3's "Wrapper
required" classification for the Collection Engine.

Two providers are wired in: `FixtureCollectionProvider` (T-010, canned dataset, no network) and,
as of T-015, a live path (`build_live_collection_engine`) that wires the real, already-tested
`YouTubePlatformProvider` (`providers/platform/youtube.py`) via `collect.main.
build_provider_and_quota` -- exactly the constructor-argument swap T-010's own Context Pack
anticipated; `CollectionEngineAdapter` itself required no changes for this.

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
from finfluencer.infrastructure.collection.live_provider import build_live_collection_engine

__all__ = [
    "CollectionEngineAdapter",
    "FixtureCollectionProvider",
    "build_live_collection_engine",
    "fixture_transcript_fetcher",
]
