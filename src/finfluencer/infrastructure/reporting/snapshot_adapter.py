"""ResultSnapshotAdapter (BACKLOG.md T-025): Infrastructure implementation of
`finfluencer.domain.reporting_engine.IResultSnapshotReader`.

Reads one `AnalysisRun`'s own result parquet -- `topics.parquet` or `sentiment.parquet`, at the
conventional `base_root/analysis_run_id/data_processed/<name>.parquet` path `TopicsAnalysisAdapter`
(T-019) / `SentimentAnalysisAdapter` (T-022) already write to -- and serializes it to a JSON
string (`DataFrame.to_json(orient="records")`), the content a new `InterpretationRecord`
(kind=`raw_result_snapshot`) is built from.

Deliberately does not use `reporting.master_table.build_master_table()`: that function requires
`comments.parquet`, `topics.parquet`, AND `sentiment.parquet` simultaneously and produces a
cross-AnalysisType joined table -- a different granularity than "one snapshot of one AnalysisRun's
own output" (section 10.1 line 586: an InterpretationRecord "belongs to exactly one
`AnalysisRun`, always"). See `CONTEXT_PACK_REPORTING.md`'s Integration decisions section.

Which of the two known output filenames applies is resolved by presence, not by an
`AnalysisType` lookup -- there is no `AnalysisType` catalog/repository wired up anywhere in this
codebase yet that Application could consult to resolve `analysis_type_id` to a concrete adapter
or filename. This is a deliberate, flagged assumption (see CONTEXT_PACK_REPORTING.md's Known
technical debt): a third `AnalysisType` needs its own filename added to `_KNOWN_OUTPUT_FILENAMES`,
or a more general mechanism, whichever a future task actually needs.
"""

from __future__ import annotations

from pathlib import Path

from finfluencer.utils.io import read_parquet

#: Result filenames this adapter knows how to read, by presence (see module docstring).
_KNOWN_OUTPUT_FILENAMES: tuple[str, ...] = ("topics.parquet", "sentiment.parquet")


class ResultSnapshotAdapter:
    """Implements `IResultSnapshotReader` (`finfluencer.domain.reporting_engine`)."""

    def __init__(self, *, base_root: Path) -> None:
        self._base_root = Path(base_root)

    def _resolve_output_path(self, analysis_run_id: str) -> Path:
        analysis_root = self._base_root / analysis_run_id / "data_processed"
        found = [
            analysis_root / name
            for name in _KNOWN_OUTPUT_FILENAMES
            if (analysis_root / name).exists()
        ]
        if not found:
            raise FileNotFoundError(
                f"No known result file found for analysis_run_id={analysis_run_id!r} under "
                f"{analysis_root} (looked for: {', '.join(_KNOWN_OUTPUT_FILENAMES)}). The "
                "AnalysisRun may not be completed yet, or its output was written somewhere "
                "other than this adapter's conventional path."
            )
        if len(found) > 1:
            raise ValueError(
                f"Ambiguous result for analysis_run_id={analysis_run_id!r}: found more than "
                f"one known output file under {analysis_root} ({[str(p) for p in found]}). "
                "Each AnalysisRun is expected to produce exactly one result file."
            )
        return found[0]

    def read(self, analysis_run_id: str) -> str:
        if not analysis_run_id or not analysis_run_id.strip():
            raise ValueError("analysis_run_id must be non-empty")
        output_path = self._resolve_output_path(analysis_run_id)
        df = read_parquet(output_path)
        return df.to_json(orient="records")


__all__ = ["ResultSnapshotAdapter"]
