"""
finfluencer.core.checkpoint
============================

Three-tier checkpoint manager.

Tier 1 — Per-record (JSONL append)
    Streamed collection: each retrieved video/comment is appended as it
    arrives. A crash loses at most one in-flight record.

Tier 2 — Per-stage manifest (``.done`` marker)
    A stage writes a ``.done`` file when its config slice hash has been
    fully processed. Downstream stages check this marker; if the config
    slice has changed, the marker is invalidated and the stage re-runs.

Tier 3 — Content-addressed artefacts (cache)
    Heavy computations (embeddings, model outputs) live under
    ``cache/<content_hash>/…``. Reproducible re-runs load from cache
    instead of recomputing.

Concurrency
-----------
This manager assumes a single writer per ``checkpoint_root`` at a time.
Tier-1 JSONL appends and the Tier-2 ``.done``-marker read/write are not
file-locked; running two ``finfluencer run`` invocations concurrently
against the same checkpoint directory is unsupported and can race (both
may see a stale marker as "should run" before either writes it, or
appends may interleave). Use a separate ``checkpoint_root``/``cache_root``
per concurrent run if you need to parallelise.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from finfluencer.core.exceptions import (
    CheckpointCorruptedError,
    CheckpointInvalidatedError,
)
from finfluencer.utils.hashing import hash_config_dict
from finfluencer.utils.io import (
    append_jsonl,
    ensure_dir,
    load_completed_ids,
    read_json,
    read_jsonl,
    write_json,
)


# =============================================================================
# CheckpointManager
# =============================================================================


class CheckpointManager:
    """Coordinate three-tier checkpointing for a study.

    One instance per study run; passed to every stage. Stages call
    :meth:`should_run` to decide whether to skip, :meth:`append_record`
    to stream Tier-1 records, :meth:`mark_done` to write the Tier-2
    marker on successful completion, and :meth:`cache_path` to resolve
    Tier-3 artefact locations.
    """

    def __init__(self, checkpoint_root: Path | str, cache_root: Path | str) -> None:
        self.checkpoint_root: Path = ensure_dir(Path(checkpoint_root))
        self.cache_root: Path = ensure_dir(Path(cache_root))

    # -- Tier 2: stage-level done markers ---------------------------------

    def _marker_path(self, stage_name: str) -> Path:
        return self.checkpoint_root / f"{stage_name}.done"

    def has_valid_marker(self, stage_name: str, config_slice: dict[str, Any]) -> bool:
        """Return ``True`` iff a ``.done`` marker exists AND matches
        ``config_slice`` — read-only, never mutates checkpoint state.

        This is the query half of :meth:`should_run`'s logic, extracted
        so callers that must never touch disk (e.g.
        :mod:`finfluencer.reporting.orchestrator`'s dry-run plan, whose
        own docstring promises "never touches disk" — ADR-P2-004) have
        a way to ask "is this stage up to date?" without triggering
        :meth:`should_run`'s stale-marker deletion side effect.

        :meth:`should_run` remains the method real-run callers use —
        its mutation (deleting a stale marker so it is cleanly
        re-created on the next completion) is intentional and several
        collection/reporting stages depend on it (they detect the
        deletion via their own before/after marker-existence check to
        know whether to discard stale Tier-1 records too). This method
        changes none of that; it only adds a side-effect-free way to
        answer the same question.
        """
        marker = self._marker_path(stage_name)
        if not marker.exists():
            return False
        try:
            recorded = read_json(marker)
        except Exception as exc:  # noqa: BLE001
            raise CheckpointCorruptedError(
                f"Checkpoint marker unreadable: {marker}",
                marker=str(marker),
                reason=type(exc).__name__,
            ) from exc
        current_hash = hash_config_dict(config_slice)
        return recorded.get("config_slice_sha256") == current_hash

    def should_run(self, stage_name: str, config_slice: dict[str, Any]) -> bool:
        """Return ``True`` iff the stage should run.

        The stage should run when either:
            * no ``.done`` marker exists yet, or
            * the marker's recorded config-slice hash differs from the
              current one (upstream config changed).

        A stale marker is deleted so it is re-created on completion —
        this mutation is intentional and depended upon by real-run
        callers (see :meth:`has_valid_marker`'s docstring). Callers that
        must not mutate checkpoint state should call
        :meth:`has_valid_marker` instead.
        """
        marker = self._marker_path(stage_name)
        if self.has_valid_marker(stage_name, config_slice):
            return False
        if marker.exists():
            marker.unlink()
        return True

    def mark_done(
        self,
        stage_name: str,
        config_slice: dict[str, Any],
        *,
        extras: dict[str, Any] | None = None,
    ) -> None:
        """Write the ``.done`` marker for a completed stage."""
        marker = self._marker_path(stage_name)
        payload = {
            "stage": stage_name,
            "config_slice_sha256": hash_config_dict(config_slice),
            "extras": extras or {},
        }
        write_json(payload, marker)

    def invalidate(self, stage_name: str) -> None:
        """Force a stage to re-run on next invocation."""
        marker = self._marker_path(stage_name)
        if marker.exists():
            marker.unlink()
        # Also drop tier-1 record log if present
        tier1 = self._records_path(stage_name)
        if tier1.exists():
            tier1.unlink()

    # -- Tier 1: streamed records -----------------------------------------

    def _records_path(self, stage_name: str) -> Path:
        return self.checkpoint_root / f"{stage_name}.jsonl"

    def append_record(self, stage_name: str, record: dict[str, Any]) -> None:
        """Append a single Tier-1 record for a stage."""
        append_jsonl(record, self._records_path(stage_name))

    def read_records(self, stage_name: str) -> Iterator[dict[str, Any]]:
        """Iterate all Tier-1 records for a stage."""
        yield from read_jsonl(self._records_path(stage_name))

    def completed_ids(self, stage_name: str, *, key: str = "id") -> set[str]:
        """Return the set of ``key`` values already recorded for a stage.

        Used by collection to skip items already processed on resume.
        """
        return load_completed_ids(self._records_path(stage_name), key=key)

    # -- Tier 3: cache artefacts ------------------------------------------

    def cache_path(self, kind: str, content_hash: str, suffix: str = "") -> Path:
        """Resolve a content-addressed cache location.

        Parameters
        ----------
        kind
            Namespace, e.g. ``"embeddings"``, ``"models"``.
        content_hash
            SHA-256-derived identifier for the content.
        suffix
            Optional suffix (e.g. ``".npy"``, ``".tar.gz"``).

        Returns
        -------
        Path
            ``cache/<kind>/<hash>[<suffix>]``. The parent directory
            is created if missing; the file itself may or may not exist.
        """
        if not content_hash:
            raise ValueError("cache_path: content_hash must not be empty")
        # Shard by first two hex chars to avoid huge single directories.
        shard = content_hash[:2]
        parent = ensure_dir(self.cache_root / kind / shard)
        return parent / f"{content_hash}{suffix}"

    def cache_has(self, kind: str, content_hash: str, suffix: str = "") -> bool:
        """Check whether a cache artefact already exists."""
        return self.cache_path(kind, content_hash, suffix).exists()

    # -- Introspection: all markers (run-manifest support) -----------------

    def all_markers(self) -> dict[str, dict[str, Any]]:
        """Return every Tier-2 stage marker currently on disk.

        Reads every ``*.done`` file under ``checkpoint_root`` and returns
        ``{stage_name: marker_payload}``. Used by the run-manifest system
        (:mod:`finfluencer.core.reproducibility`) to fold per-stage
        ``config_slice_sha256`` values into one run-level record; never
        used by :meth:`should_run`/:meth:`mark_done` themselves, which
        stay purely per-stage. A corrupted marker is skipped rather than
        raised, so one bad marker file cannot prevent the manifest from
        describing everything else that completed successfully.
        """
        markers: dict[str, dict[str, Any]] = {}
        for marker_path in sorted(self.checkpoint_root.glob("*.done")):
            stage_name = marker_path.stem
            try:
                markers[stage_name] = read_json(marker_path)
            except Exception:  # noqa: BLE001
                continue
        return markers

    # -- Convenience: raise if invalidated --------------------------------

    def require_done(self, stage_name: str, config_slice: dict[str, Any]) -> None:
        """Raise :class:`CheckpointInvalidatedError` if the stage has not
        been completed (or was invalidated) for the given config slice.

        Used by downstream stages that cannot run without upstream output.
        """
        if self.should_run(stage_name, config_slice):
            raise CheckpointInvalidatedError(
                f"Upstream stage {stage_name!r} has not completed for the "
                f"current config; re-run it before proceeding.",
                stage=stage_name,
            )


__all__ = ["CheckpointManager"]
