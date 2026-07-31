"""
finfluencer.migration.backfill_topic_scope
=============================================

Migration Step 3.2.5. Adds the ``scope_id`` column to an *existing*
``topics.parquet`` produced by pre-Step-3.2 code, without re-fitting
any BERTopic model and without touching the checkpoint state that
records those fits.

Why this step exists
---------------------
Step 3.2 (``finfluencer.topics.pipeline``) made ``run_topics()`` populate
``scope_id`` on every row it writes going forward. It does not - and, by
the checkpoint architecture, structurally *cannot* - retroactively
populate ``scope_id`` on rows a *previous* run already wrote: re-running
``--stage topics`` against an unchanged corpus and config hits
``CheckpointManager.should_run() == False`` (the ``.done`` marker's
config-slice hash is unaffected by Step 3.2's change) and falls straight
to carrying prior rows through unchanged - see
``Entity_Centric_Migration_Plan_v2.md``'s Step 3.3 entry for the
attempted-and-rolled-back call-site swap this gap caused. This module is
the direct, additive fix: a one-time, idempotent backfill, in the same
spirit as :mod:`finfluencer.migration.backfill_entity_model` (Phase 0).

Design difference from ``backfill_entity_model``, documented explicitly
--------------------------------------------------------------------------
Phase 0's backfill writes *new*, additional parquet files alongside the
originals (``entities.parquet``, ``entity_video_link.parquet``, ...) -
nothing existing is modified in place. This backfill cannot follow that
shape unchanged: the goal is specifically for the *existing*
``topics.parquet`` to gain the column, in place, because that is the
exact file :func:`finfluencer.topics.pipeline.run_topic_evolution` reads
by default and the exact file the rolled-back Step 3.3 call site needs
to find ``scope_id`` on. The function below therefore returns a
*modified copy* of the input DataFrame rather than writing a sibling
file; the caller decides where to write it (typically: back to the same
path, after validating the returned frame - see the module-level
``__main__`` guard below for the actual production invocation used for
this migration step, which backs up the original file first).

Ground truth for group membership: topics.parquet's own rows, not a
fresh re-join - documented per the Step 3.2.5 approval gate's explicit
requirement
------------------------------------------------------------------------
:func:`finfluencer.topics.pipeline._resolve_and_persist_group_scope` (the
*live* mechanism, used by fresh ``run_topics()`` runs going forward)
derives a group's comment-ID set from a fresh join of
``comments.parquet`` against ``embeddings_index.parquet`` at fit time.
That join is **not** reproducible here: this is a *historical* backfill
over output already written by a past run, and re-deriving membership
from today's ``comments.parquet``/``embeddings_index.parquet`` could
silently include comments collected *after* that past run (if any exist
today) that were never actually part of the fitted corpus - a real
correctness risk, not a hypothetical one. This backfill therefore uses
each row already present in ``topics.parquet`` as ground truth for "was
this comment part of this scope's fitted corpus" (an existing-pipeline-
derived fact recorded at fit time, not a legacy label invented for this
migration), and additionally joins against ``comments.parquet`` for one
piece of information ``topics.parquet`` itself does not carry:
``analyst_key``, needed to group ``within_analyst`` rows per analyst.
``analyst_key`` is not a deprecated/legacy field being phased out early -
it remains the platform's live source of truth for entity membership
until Phase 1's membership resolvers (not yet implemented) cut over -
so this join is using current, authoritative data, not reaching back to
a legacy mechanism.

Safety
------
Every fixed field already on ``topics.parquet`` (``comment_id``,
``topic_id``, ``topic_prob``, ``topic_tier``, ``configuration``,
``topic_label``) is verified byte-for-byte unchanged, in original row
order, before this function returns. ``configuration`` values outside
``{"pooled", "within_analyst"}`` and ``within_analyst`` comment IDs with
no matching row in ``comments.parquet`` both raise ``ValueError`` rather
than being silently skipped - the same fail-loud discipline
``backfill_entity_model.py`` already established for this project.
Nothing here touches ``core/checkpoint.py`` or any ``.done`` marker;
this function never imports ``CheckpointManager``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from finfluencer.core.contracts import AnalysisScopeType, TopicRecord
from finfluencer.core.logging import get_logger
from finfluencer.scope import resolve_scope
from finfluencer.utils.io import read_parquet

_log = get_logger(__name__)

_INDEX_COLUMNS: list[str] = list(TopicRecord.model_fields.keys())
_VALID_CONFIGURATIONS = frozenset({"pooled", "within_analyst"})

#: Must match finfluencer.topics.pipeline._SCOPE_CRITERIA_VERSION exactly.
#: Not imported directly to avoid this migration-only module pulling in
#: topics/pipeline.py's full dependency chain (BERTopic-adjacent
#: imports) for what is otherwise a pure-pandas operation; the value is
#: duplicated here and asserted against the live constant in this
#: module's own test suite so the two cannot silently drift apart.
#: Using the identical value is required, not incidental: it is what
#: makes this backfill's scope_id values match what a future live
#: run_topics() call would independently (re-)compute for the same
#: groups, per resolve_scope()'s own idempotency guarantee.
SCOPE_CRITERIA_VERSION = "v1_topics_pipeline"


def _assert_columns_unchanged(
    original: pd.DataFrame, backfilled: pd.DataFrame, columns: list[str],
) -> None:
    """Raise if any pre-existing column's values or row order changed."""
    orig_subset = original[columns].reset_index(drop=True)
    new_subset = backfilled[columns].reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(orig_subset, new_subset, check_dtype=False)
    except AssertionError as exc:
        raise ValueError(
            f"backfill_topic_scope: pre-existing columns {columns} changed "
            f"value or order - refusing to proceed. Original error: {exc}",
        ) from exc


def backfill_topic_scope(
    topics_path: Path | str,
    comments_path: Path | str,
    *,
    criteria_version: str = SCOPE_CRITERIA_VERSION,
) -> dict[str, Any]:
    """Return a copy of ``topics.parquet`` with ``scope_id`` populated,
    plus a validation report. Does not write anything to disk - the
    caller is responsible for persisting the returned frame (see module
    docstring for why this differs from ``backfill_entity_model``'s
    write-a-new-file shape).

    Parameters
    ----------
    topics_path
        Existing ``topics.parquet`` (read-only - never modified by this
        function).
    comments_path
        Existing ``comments.parquet`` (read-only), used solely to look
        up ``analyst_key`` per ``comment_id`` for ``within_analyst``
        grouping - see module docstring's "Ground truth" section.
    criteria_version
        Stamped into every resolved ``AnalysisScope`` - must match the
        live pipeline's value for future runs to reproduce the same
        ``scope_id`` values (see ``SCOPE_CRITERIA_VERSION``'s docstring).

    Returns
    -------
    dict
        ``{"topics": DataFrame, "report": {...}}`` - ``topics`` is the
        input frame with ``scope_id`` populated and column order
        normalized to ``TopicRecord``'s field order; row order and every
        other value are verified identical to the input before return.

    Raises
    ------
    ValueError
        If any ``configuration`` value is outside
        ``{"pooled", "within_analyst"}``; if any ``within_analyst`` row's
        ``comment_id`` has no matching row in ``comments.parquet``; or if
        the internal unchanged-columns check fails (should be
        unreachable given the logic below, kept as a hard safety net
        rather than trusted-by-construction).
    """
    topics_df = read_parquet(Path(topics_path))
    comments_df = read_parquet(Path(comments_path))

    if topics_df.empty:
        _log.warning("backfill_topic_scope_empty_input")
        report = {
            "n_rows_in": 0, "n_rows_out": 0, "n_pooled_rows": 0,
            "n_within_analyst_rows": 0, "n_distinct_scope_ids": 0,
            "analysts": [],
        }
        return {"topics": topics_df.copy(), "report": report}

    bad_configurations = set(topics_df["configuration"].unique()) - _VALID_CONFIGURATIONS
    if bad_configurations:
        raise ValueError(
            f"backfill_topic_scope: unexpected configuration value(s) "
            f"{sorted(bad_configurations)} - expected only "
            f"{sorted(_VALID_CONFIGURATIONS)}. Refusing to guess a scope "
            f"type for an unrecognized configuration.",
        )

    original_columns = [c for c in topics_df.columns if c != "scope_id"]
    out = topics_df.copy()
    if "scope_id" not in out.columns:
        out["scope_id"] = None

    pooled_mask = out["configuration"] == "pooled"
    pooled_comment_ids = out.loc[pooled_mask, "comment_id"].tolist()
    n_distinct_scope_ids = 0
    if pooled_comment_ids:
        pooled_scope = resolve_scope(
            pooled_comment_ids,
            scope_type=AnalysisScopeType.global_,
            criteria_version=criteria_version,
        )
        out.loc[pooled_mask, "scope_id"] = pooled_scope.scope_id
        n_distinct_scope_ids += 1
        _log.info(
            "backfill_topic_scope_pooled_resolved",
            scope_id=pooled_scope.scope_id, n_comment_ids=len(pooled_comment_ids),
        )

    within_mask = out["configuration"] == "within_analyst"
    within_rows = out.loc[within_mask].copy()
    if not within_rows.empty:
        analyst_by_comment = comments_df.set_index("comment_id")["analyst_key"]
        within_rows["_analyst_key"] = within_rows["comment_id"].map(analyst_by_comment)
        missing = within_rows.loc[within_rows["_analyst_key"].isna(), "comment_id"].tolist()
        if missing:
            raise ValueError(
                f"backfill_topic_scope: {len(missing)} within_analyst comment_id(s) "
                f"in topics.parquet have no matching row in comments.parquet - "
                f"cannot determine analyst_key. First offenders: {missing[:10]}",
            )
        analysts_seen: list[str] = []
        for analyst_key, group in within_rows.groupby("_analyst_key"):
            comment_ids = group["comment_id"].tolist()
            scope = resolve_scope(
                comment_ids,
                scope_type=AnalysisScopeType.entity,
                entity_keys=[analyst_key],
                criteria_version=criteria_version,
            )
            out.loc[group.index, "scope_id"] = scope.scope_id
            n_distinct_scope_ids += 1
            analysts_seen.append(analyst_key)
            _log.info(
                "backfill_topic_scope_within_analyst_resolved",
                analyst_key=analyst_key, scope_id=scope.scope_id, n_comment_ids=len(comment_ids),
            )
    else:
        analysts_seen = []

    still_unresolved = out["scope_id"].isna().sum()
    if still_unresolved:
        raise ValueError(
            f"backfill_topic_scope: {still_unresolved} row(s) left with no "
            f"scope_id after processing all configuration groups - this "
            f"should be unreachable given the configuration-value check "
            f"above; refusing to return a partially-backfilled frame.",
        )

    _assert_columns_unchanged(topics_df, out, original_columns)

    out = out[[c for c in _INDEX_COLUMNS if c in out.columns]]

    report = {
        "n_rows_in": len(topics_df),
        "n_rows_out": len(out),
        "n_pooled_rows": int(pooled_mask.sum()),
        "n_within_analyst_rows": int(within_mask.sum()),
        "n_distinct_scope_ids": n_distinct_scope_ids,
        "analysts": sorted(analysts_seen),
    }
    _log.info("backfill_topic_scope_done", **report)
    return {"topics": out, "report": report}


__all__ = ["backfill_topic_scope", "SCOPE_CRITERIA_VERSION"]
