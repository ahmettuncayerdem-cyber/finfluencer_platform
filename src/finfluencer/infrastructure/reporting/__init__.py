"""Reporting Infrastructure adapters (BACKLOG.md T-025, T-026).

- `ResultSnapshotAdapter` (T-025) implements `IResultSnapshotReader` by reading one AnalysisRun's
  own result parquet and serializing it to a JSON string -- new code, not a wrap of
  `reporting/master_table.py` (that module joins across AnalysisTypes at a different
  granularity).
- `MasterTableExportAdapter` (T-026) implements `ITableExporter` by wrapping
  `reporting.master_table.build_master_table`/`save_master_table` unmodified -- the correct reuse
  target `ResultSnapshotAdapter` deliberately was not.

See `CONTEXT_PACK_REPORTING.md` in this directory (IMPLEMENTATION_PLAYBOOK.md Part B.2).
"""

from __future__ import annotations

from finfluencer.infrastructure.reporting.snapshot_adapter import ResultSnapshotAdapter
from finfluencer.infrastructure.reporting.table_export_adapter import MasterTableExportAdapter

__all__ = ["MasterTableExportAdapter", "ResultSnapshotAdapter"]
