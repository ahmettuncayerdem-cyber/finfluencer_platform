"""
finfluencer.scope
==================

Migration Step 3.1: ``resolve_scope()`` is the single place
:class:`~finfluencer.core.contracts.AnalysisScope`'s
``resolved_comment_ids_hash`` is computed and persisted.

Design principle - "resolve once, persist, never re-derive"
-------------------------------------------------------------
Every stage that needs "which comments are in scope for this analysis"
should eventually call ``resolve_scope()`` exactly once and reference
the resulting ``scope_id``, rather than each independently re-deriving
comment membership through its own join/filter logic. This is the
direct structural fix for the bug where ``run_topics`` and
``run_topic_evolution`` (:mod:`finfluencer.topics.pipeline`) each
independently re-derive "pooled"/"within_analyst" comment membership
through a different join path and can disagree with each other. See
``entity_centric_platform_architecture.md`` and
``Entity_Centric_Migration_Plan_v2.md`` (Section 4) for the full design
rationale, and ``AnalysisScope_Impact_Analysis.md`` for the traced
blast radius of wiring this module into the existing pipeline.

Module placement
-----------------
The migration plan (``Entity_Centric_Migration_Plan_v2.md`` Section 9)
left this module's location as "a minor decision, not made here" -
either ``finfluencer.entities.scope`` or a top-level
``finfluencer.scope``. This implementation uses the top-level form
deliberately: ``finfluencer.entities`` (the membership-resolver
registry - Migration Phase 1/4) does not exist yet, and
``resolve_scope()`` has no dependency on it - it operates on an
already-resolved ``comment_ids`` list, not on entity membership
resolution itself. Making ``finfluencer.scope`` depend on a
not-yet-built package would be a false coupling.

What this module does NOT do
------------------------------
It does not decide *which* comments belong to a scope - that is a
membership resolver's job (Phase 1's ``creator`` resolver, Phase 4's
``topic``/``campaign``/``event`` resolvers), none of which exist yet.
``resolve_scope()`` takes an already-resolved ``comment_ids`` list and
performs the one thing Phase 3 exists to centralize: hashing that
membership exactly once and returning a persistable record.

Status as of Migration Step 3.1
----------------------------------
This module is new and entirely additive. Nothing in
:mod:`finfluencer.topics.pipeline` or
:mod:`finfluencer.analysis.topic_sentiment` calls ``resolve_scope()``
or ``persist_scope()`` yet - those stages still derive scope via the
pre-migration ``configuration``/``analyst_key`` path, unchanged.
Wiring ``run_topics()``/``run_topic_evolution()`` to call
``resolve_scope()`` and persist/read ``AnalysisScope`` rows is
Migration Step 3.2/3.3, not this step.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from finfluencer.core.contracts import AnalysisScope, AnalysisScopeType
from finfluencer.core.logging import get_logger
from finfluencer.utils.io import read_parquet, write_parquet

_log = get_logger(__name__)

_SCOPE_ID_HASH_LENGTH = 16


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_comment_ids(comment_ids: list[str]) -> str:
    """SHA-256 of the sorted, deduplicated ``comment_id`` list.

    The one place this hash is computed, per this module's docstring -
    every later reader of an ``AnalysisScope`` loads
    ``resolved_comment_ids_hash`` rather than recomputing this.
    """
    deduped_sorted = sorted(set(comment_ids))
    joined = "\n".join(deduped_sorted)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _hash_scope_identity(
    scope_type: AnalysisScopeType,
    entity_keys: list[str],
    filter_params: dict,
    criteria_version: str,
) -> str:
    """Content hash of the scope's *definition* (not its resolved
    membership) - this becomes ``scope_id``, the primary key.

    Two calls with the same ``(scope_type, entity_keys, filter_params,
    criteria_version)`` always produce the same ``scope_id``, regardless
    of what ``comment_ids`` happen to resolve to at call time - this is
    what makes ``resolve_scope()`` idempotent and safe to call more than
    once for "the same scope, re-resolved after new data arrived."
    """
    payload = json.dumps(
        {
            "scope_type": scope_type.value,
            "entity_keys": sorted(entity_keys),
            "filter_params": filter_params,
            "criteria_version": criteria_version,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:_SCOPE_ID_HASH_LENGTH]


def resolve_scope(
    comment_ids: list[str],
    *,
    scope_type: AnalysisScopeType,
    entity_keys: list[str] | None = None,
    filter_params: dict | None = None,
    criteria_version: str = "v1",
) -> AnalysisScope:
    """Resolve one :class:`AnalysisScope` record for an explicit set of
    comment IDs.

    Parameters
    ----------
    comment_ids
        The already-resolved list of comment IDs this scope covers.
        This function does not derive membership itself - see the
        module docstring.
    scope_type, entity_keys, filter_params, criteria_version
        The scope's definition. ``scope_id`` is a deterministic hash of
        these four values (see :func:`_hash_scope_identity`); calling
        this function twice with an identical definition always yields
        the same ``scope_id``, even if ``comment_ids`` differs between
        calls (e.g. new comments collected since the last resolution) -
        in that case ``resolved_comment_ids_hash`` differs, which is the
        signal that the scope's membership has drifted since it was
        last resolved.

    Returns
    -------
    AnalysisScope
        Not yet persisted - call :func:`persist_scope` to write it.

    Not yet called by any pipeline stage (Migration Step 3.1 status -
    see module docstring).
    """
    entity_keys = list(entity_keys) if entity_keys else []
    filter_params = dict(filter_params) if filter_params else {}
    scope_id = _hash_scope_identity(scope_type, entity_keys, filter_params, criteria_version)
    resolved_hash = _hash_comment_ids(comment_ids)
    scope = AnalysisScope(
        scope_id=scope_id,
        scope_type=scope_type,
        entity_keys=entity_keys,
        filter_params=filter_params,
        resolved_comment_ids_hash=resolved_hash,
        resolved_at=_now_iso(),
        criteria_version=criteria_version,
    )
    _log.info(
        "scope_resolved",
        scope_id=scope.scope_id,
        scope_type=scope.scope_type,
        n_comment_ids=len(comment_ids),
    )
    return scope


def persist_scope(scope: AnalysisScope, output_path: Path | str) -> None:
    """Upsert one :class:`AnalysisScope` row into ``analysis_scope.parquet``
    at ``output_path``, keyed by ``scope_id``.

    Idempotent: re-resolving the same scope definition against an
    unchanged comment set produces an identical row, so re-running is a
    no-op merge (``drop_duplicates(keep="last")``), not a duplicate row.
    If the same ``scope_id`` resolves to a *different*
    ``resolved_comment_ids_hash`` than before (membership drift - see
    :func:`resolve_scope`), the newest resolution wins and the prior one
    is superseded, not retained as a second row - callers that need to
    keep drift history should persist scopes to a different location
    per resolution rather than relying on this function's upsert
    behavior.

    Not yet called by any pipeline stage (Migration Step 3.1 status).

    Notes
    -----
    ``filter_params`` is stored as a JSON string, not a nested struct
    column: PyArrow cannot infer a schema for a struct-typed column
    whose value is an empty dict (``{}``, the common case for
    ``scope_type in (global_, entity)`` - "Cannot write struct type
    'filter_params' with no child field to Parquet"). A JSON string
    column sidesteps that entirely and round-trips losslessly via
    ``json.loads``/``json.dumps``. No pipeline code reads
    ``analysis_scope.parquet`` back yet (Migration Step 3.1 status), so
    this is forward-looking, not yet exercised by a real reader.
    """
    output_path = Path(output_path)
    row = scope.model_dump(mode="json")
    row["filter_params"] = json.dumps(row["filter_params"], sort_keys=True)
    new_row = pd.DataFrame([row])
    if output_path.exists():
        existing = read_parquet(output_path)
        combined = pd.concat([existing, new_row], ignore_index=True)
        combined = combined.drop_duplicates(subset=["scope_id"], keep="last")
    else:
        combined = new_row
    write_parquet(combined, output_path)
    _log.info(
        "analysis_scope_persisted",
        scope_id=scope.scope_id,
        scope_type=scope.scope_type,
        output_path=str(output_path),
    )


__all__ = ["resolve_scope", "persist_scope"]
