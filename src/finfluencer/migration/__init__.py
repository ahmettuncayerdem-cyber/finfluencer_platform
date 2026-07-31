"""
finfluencer.migration
========================

One-time, additive backfill from the analyst-centric data model
(``VideoRecord``/``CommentRecord``, partitioned by ``analyst_key``) to
the entity-centric data model (``EntityRecord``/``CanonicalVideoRecord``/
``CanonicalCommentRecord``/``EntityVideoLinkRecord``) described in
``entity_centric_platform_architecture.md`` (Phase 0).

Nothing in this package touches, modifies, or deletes existing pipeline
inputs or outputs. It only reads ``videos.parquet``/``comments.parquet``/
``channels.parquet`` and writes new, additive canonical tables to a
separate output directory (default: ``data/interim/entity_model/``).
No existing collection/processing stage depends on this package's
output yet - that wiring is Phase 1+ of the migration and is out of
scope here.
"""

from __future__ import annotations
