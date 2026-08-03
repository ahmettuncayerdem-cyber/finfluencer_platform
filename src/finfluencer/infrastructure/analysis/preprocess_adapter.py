"""PreprocessEngineAdapter (Release Blocker #6,
`docs/implementation/RB6_ANALYSIS_DISPATCH_READINESS_REVIEW.md` section 5.1): Infrastructure
wrapper around the existing, tested `finfluencer.preprocess.pipeline.run_preprocessing` and
`build_default_preprocessor`, unmodified.

`preprocess/` is a Shared Core module (`BACKLOG.md`'s Engineering Workstreams policy) -- see this
change's Shared Core Impact Assessment in the Release Blocker #6 implementation report (not
repeated here; the underlying `preprocess/*` code is untouched by this file).

Does **not** implement `finfluencer.domain.analysis_engine.IAnalysisEngine` -- same reasoning
`EmbeddingsEngineAdapter` already established: no `AnalysisType` named "preprocess" exists,
nothing cites `comments.parquet`'s `text_clean` column from a `Report` directly, section 11.2
names no matching command. Exposes one plain method, `ensure_clean()`, mirroring
`EmbeddingsEngineAdapter.ensure_index()`'s shape exactly.

Constraint, same as every prior adapter in this package: this module must never modify
`finfluencer.preprocess.*` -- it only imports and calls it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import Settings
from finfluencer.core.registry import instantiate
from finfluencer.preprocess.pipeline import build_default_preprocessor, run_preprocessing


@dataclass(frozen=True)
class PreprocessOutcome:
    """Local return shape -- not a Domain type (see class docstring for why no
    `IPreprocessEngine` Domain port exists). `comments_path` is the same file
    `EmbeddingsEngineAdapter`/`TopicsAnalysisAdapter`/`SentimentAnalysisAdapter` already read --
    this adapter updates it in place, it does not produce a separate artifact.
    """

    comments_path: Path
    row_count: int


class PreprocessEngineAdapter:
    """Fills `text_clean`/`tokens`/`n_tokens`/`emojis` in a `CollectionRun`'s own
    `comments.parquet`, in place -- the same file `EmbeddingsEngineAdapter`,
    `TopicsAnalysisAdapter`, and `SentimentAnalysisAdapter` already read from
    `base_root / collection_run_id / "data_raw" / "comments.parquet"`. Every freshly-collected
    comment is written with `text_clean=""`
    (`providers/platform/youtube.py`, inline-commented `# populated in preprocessing`) -- this
    adapter is what actually populates it; both real analysis engines depend on this having run
    first (confirmed via code in the Release Blocker #6 Readiness Review, not assumed).

    **Why this does not implement `IAnalysisEngine`.** That Protocol's `run(analysis_run_id,
    collection_run_id) -> AnalysisOutcome` shape models a full, independently-dispatchable
    `AnalysisRun` -- topics and sentiment are each their own named `AnalysisType`, each producing
    their own citable result. Preprocessing is neither: no `AnalysisType` named "preprocess"
    exists or is proposed, `text_clean` is never itself cited by a `Report`, and section 11.2
    names no matching command. Reusing that Protocol here would be exactly the kind of speculative
    interface the operator's own instruction forbids -- same reasoning `EmbeddingsEngineAdapter`
    already applied to itself, not a new argument invented for this adapter.

    **Why isolation is per-`collection_run_id`, not per-`analysis_run_id`.** Preprocessed text is
    a property of the collected comments themselves, same reasoning `EmbeddingsEngineAdapter`
    already established -- shared/cached across however many analysis attempts (topics, sentiment,
    or both) run against the same `CollectionRun`, never recomputed per attempt.

    **Language selection reuses `collect/main.py`'s own established pattern**
    (`finfluencer.core.registry.instantiate("language", settings.providers.language)` then
    `build_default_preprocessor(language)`) verbatim -- not a new resolution mechanism invented
    here. `financial_tr.py`'s Turkish-financial-vocabulary normalization stays exactly as
    configured today, unmodified and unconditional -- flagged, not changed, in the Shared Core
    Impact Assessment (Roadmap Risk R-6).
    """

    def __init__(self, *, settings: Settings, base_root: Path) -> None:
        self._settings = settings
        self._base_root = Path(base_root)

    def _paths_for(self, collection_run_id: str) -> tuple[Path, Path, Path]:
        """Derive this `CollectionRun`'s isolated `(comments_path, checkpoint_root, cache_root)`.
        `comments_path` reuses T-010's existing directory convention verbatim, same as every
        sibling adapter in this package. Preprocessing writes back to `comments_path` itself (in
        place, matching `collect/main.py`'s own established default) -- not a separate output
        file -- so `EmbeddingsEngineAdapter`/`TopicsAnalysisAdapter`/`SentimentAnalysisAdapter`,
        all of which read `comments_path` directly and unmodified, see the populated
        `text_clean` without any change to their own code.
        """
        comments_path = self._base_root / collection_run_id / "data_raw" / "comments.parquet"
        preprocess_root = self._base_root / collection_run_id / "preprocess"
        return comments_path, preprocess_root / "checkpoints", preprocess_root / "cache"

    def ensure_clean(self, collection_run_id: str) -> PreprocessOutcome:
        """Idempotent: relies on `run_preprocessing()`'s own per-analyst checkpoint discipline,
        unmodified -- a second call for the same `collection_run_id` re-derives the same paths
        and skips already-processed analysts, never redoing work a prior call already did.
        """
        if not collection_run_id or not collection_run_id.strip():
            raise ValueError("collection_run_id must be non-empty")

        comments_path, checkpoint_root, cache_root = self._paths_for(collection_run_id)
        checkpoint = CheckpointManager(checkpoint_root=checkpoint_root, cache_root=cache_root)

        language = instantiate("language", self._settings.providers.language)
        preprocessor = build_default_preprocessor(language)

        df = run_preprocessing(
            self._settings,
            comments_path,
            checkpoint,
            preprocessor=preprocessor,
        )

        return PreprocessOutcome(comments_path=comments_path, row_count=len(df))


__all__ = ["PreprocessEngineAdapter", "PreprocessOutcome"]
