"""CollectionEngineAdapter (BACKLOG.md T-010): the Infrastructure implementation of
`finfluencer.domain.collection_engine.ICollectionEngine`.

Wraps, unmodified, the four existing Collection Engine stage functions in dependency order --
`collect_channels` -> `collect_videos` -> `collect_comments` -> `collect_transcripts`
(`finfluencer.collect.*`) -- plus the existing `CheckpointManager`
(`finfluencer.core.checkpoint`). Per IMPLEMENTATION_ROADMAP.md section 3's own reuse
classification, this whole group ("`collect/`... `providers/platform/youtube.py`") was assessed
together as one "Wrapper required" unit; the sequencing below is the *existing*, already-tested
`collect/main.py::run_pipeline` order, reused as-is -- not a new orchestration decision invented
at this layer. This is a deliberate, documented judgment call (see the Collection Engine's
CONTEXT_PACK.md, "Integration decisions"): if a fresh-context architecture review disagrees and
would rather this class expose four separately-callable single-stage methods for a future
orchestrator to sequence itself, that is a low-cost follow-up refactor, not evidence this class
violates BKG-001 -- no new business *rule* is added here, only reuse of an existing procedural
sequence.

Constraint: this module must never modify `finfluencer.collect.*` or
`finfluencer.providers.platform.*` (operator instruction, BACKLOG.md T-010) -- it only imports
and calls them.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from finfluencer.collect.channels import collect_channels
from finfluencer.collect.comments import collect_comments
from finfluencer.collect.transcripts import collect_transcripts
from finfluencer.collect.videos import collect_videos
from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import AnalystRoster, Settings
from finfluencer.domain.collection_engine import CollectionOutcome
from finfluencer.providers.platform.base import PlatformProvider


class CollectionEngineAdapter:
    """Implements `ICollectionEngine` (`finfluencer.domain.collection_engine`).

    Roadmap Risk R-1 ("Checkpoint concurrency assumption versus target Worker Tier"): the
    injected `CheckpointManager` assumes a single writer per `checkpoint_root`, undocumented
    for concurrent access. This class's own `run()` is what makes the "one root per run, never
    shared" partitioning discipline explicit rather than assumed -- `_paths_for()` derives a
    dedicated `checkpoint_root`/`cache_root`/`data_raw` triple per `run_id`, so two distinct
    `run_id`s can never collide even if a caller passed the same `base_root` for both. See
    `docs/adr/0002-collection-run-checkpoint-root-partitioning.md`.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        roster: AnalystRoster,
        provider: PlatformProvider,
        base_root: Path,
        transcript_fetcher: Callable[..., dict[str, Any]] | None = None,
        anon_salt: str | None = None,
    ) -> None:
        self._settings = settings
        self._roster = roster
        self._provider = provider
        self._base_root = Path(base_root)
        self._transcript_fetcher = transcript_fetcher
        # collect/comments.py requires a non-empty salt for commenter-hash anonymization
        # (Methods section 3.11). Legacy default-sourcing behavior preserved exactly:
        # collect/main.py::run_pipeline reads `os.environ.get("ANON_SALT", "")`; this
        # constructor does the same when `anon_salt` is not passed explicitly, so an
        # operator relying on the environment variable today sees no behavior change.
        self._anon_salt = anon_salt if anon_salt is not None else os.environ.get("ANON_SALT", "")

    def _paths_for(self, run_id: str) -> tuple[Path, Path, Path]:
        """Derive this run's isolated `(checkpoint_root, cache_root, data_raw)` triple.

        Roadmap Risk R-1's partitioning discipline, made concrete: every `run_id` gets its own
        subtree under `base_root`, never shared with any other `run_id`.
        """
        run_root = self._base_root / run_id
        return (run_root / "checkpoints", run_root / "cache", run_root / "data_raw")

    def run(self, run_id: str) -> CollectionOutcome:
        if not run_id or not run_id.strip():
            raise ValueError("run_id must be non-empty")

        checkpoint_root, cache_root, data_raw = self._paths_for(run_id)
        data_raw.mkdir(parents=True, exist_ok=True)
        checkpoint = CheckpointManager(checkpoint_root=checkpoint_root, cache_root=cache_root)

        # Stage 1: channels. Unmodified call into the existing, tested function.
        channels_df = collect_channels(
            self._settings,
            self._roster,
            self._provider,
            checkpoint,
            output_path=data_raw / "channels.parquet",
        )

        # Stage 2: videos (needs channels).
        videos_df = collect_videos(
            self._settings,
            channels_df,
            self._provider,
            checkpoint,
            output_path=data_raw / "videos.parquet",
        )

        # Stage 3: comments (needs videos). salt=None (collect_comments' own default) would
        # raise CollectionError for a non-empty-salt requirement (Methods section 3.11) if
        # self._anon_salt ends up empty -- surfaced here, not swallowed, same as legacy.
        comments_df = collect_comments(
            self._settings,
            videos_df,
            self._provider,
            checkpoint,
            output_path=data_raw / "comments.parquet",
            salt=self._anon_salt or None,
        )

        # Stage 4: transcripts (needs videos; does not need the provider -- matches
        # collect/main.py::run_pipeline's own comment on this exact point).
        transcript_kwargs: dict[str, Any] = {}
        if self._transcript_fetcher is not None:
            transcript_kwargs["fetcher"] = self._transcript_fetcher
        transcripts_df = collect_transcripts(
            self._settings,
            videos_df,
            checkpoint,
            output_path=data_raw / "transcripts.parquet",
            **transcript_kwargs,
        )

        return CollectionOutcome(
            run_id=run_id,
            stage_row_counts={
                "channels": len(channels_df),
                "videos": len(videos_df),
                "comments": len(comments_df),
                "transcripts": len(transcripts_df),
            },
        )


__all__ = ["CollectionEngineAdapter"]
