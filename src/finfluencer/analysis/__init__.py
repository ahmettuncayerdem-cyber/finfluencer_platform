"""finfluencer.analysis — cross-output analysis modules (Phase 2.4+).

Consumes already-computed stage outputs (``topics.parquet``,
``sentiment.parquet``, ...) and produces descriptive aggregations.
Unlike preprocess/embeddings/sentiment/topics, these are cheap,
deterministic joins over existing parquet frames — no
:class:`~finfluencer.core.checkpoint.CheckpointManager` involvement.
"""

from __future__ import annotations
