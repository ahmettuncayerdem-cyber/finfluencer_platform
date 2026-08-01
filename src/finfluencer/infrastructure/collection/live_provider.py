"""Live-provider wiring (BACKLOG.md T-015): construct a `CollectionEngineAdapter` (T-010,
unmodified) against the real YouTube Data API instead of `FixtureCollectionProvider`.

Reuses, rather than reimplements, the existing `finfluencer.collect.main.build_provider_and_quota`
factory -- the same function `collect/main.py::run_pipeline` already uses to construct a real,
quota-tracked `PlatformProvider` from validated config. `CollectionEngineAdapter` needed zero
changes for this task: it already depends on `PlatformProvider` as a Protocol (T-010's own
Context Pack: "a real, network-backed provider adapter is a pure constructor-argument swap...
no change to this class") -- confirmed true here, not merely asserted.

This module does not touch `bootstrap.py` (T-012, a Sprint 0 artifact) -- the dev page's default
wiring remains fixture-backed, on purpose. Standing up a live-backed API/UI path is not part of
T-015's scope (its own `Depends on` line names only T-013), and switching the dev page to live
mode by default would spend real YouTube API quota on every page load, which nothing in T-015's
acceptance criteria asks for.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from finfluencer.collect.main import build_provider_and_quota
from finfluencer.core.config import LoadedConfig
from finfluencer.infrastructure.collection.collection_engine_adapter import CollectionEngineAdapter


def build_live_collection_engine(
    cfg: LoadedConfig,
    base_root: Path,
    *,
    transcript_fetcher: Callable[..., dict[str, Any]] | None = None,
) -> tuple[CollectionEngineAdapter, Any]:
    """Construct a `CollectionEngineAdapter` wired to the real, configured platform provider.

    Returns `(adapter, quota_tracker)` -- the quota tracker is returned alongside the adapter
    (rather than hidden inside it) so a caller can inspect remaining quota after a run without
    `CollectionEngineAdapter` needing a new public accessor it doesn't otherwise need. This
    mirrors `collect.main.build_provider_and_quota`'s own return shape exactly.

    `anon_salt` is deliberately not passed here -- `CollectionEngineAdapter`'s own constructor
    already defaults to `os.environ.get("ANON_SALT", "")` when not given explicitly, identical
    to `collect/main.py::run_pipeline`'s existing behavior. No new secret-handling decision.
    """
    provider, quota = build_provider_and_quota(cfg)
    adapter = CollectionEngineAdapter(
        settings=cfg.settings,
        roster=cfg.roster,
        provider=provider,
        base_root=base_root,
        transcript_fetcher=transcript_fetcher,
    )
    return adapter, quota


__all__ = ["build_live_collection_engine"]
