"""Reporting Infrastructure adapter (BACKLOG.md T-025).

Implements `finfluencer.domain.reporting_engine.IResultSnapshotReader` by reading one
AnalysisRun's own result parquet (`topics.parquet` or `sentiment.parquet`, whichever exists at
its conventional path) and serializing it to a JSON string -- new code, not a wrap of
`reporting/master_table.py` (that module joins across AnalysisTypes at a different granularity;
see `CONTEXT_PACK_REPORTING.md`'s own Integration decisions section for why it was not reused
here).

See `CONTEXT_PACK_REPORTING.md` in this directory (IMPLEMENTATION_PLAYBOOK.md Part B.2).
"""

from __future__ import annotations

from finfluencer.infrastructure.reporting.snapshot_adapter import ResultSnapshotAdapter

__all__ = ["ResultSnapshotAdapter"]
