"""
finfluencer.collect.main
=========================

Unified CLI entry for the 4-stage data collection pipeline.

Stages (in dependency order):
    channels    → data/raw/channels.parquet
    videos      → data/raw/videos.parquet
    comments    → data/raw/comments.parquet
    transcripts → data/raw/transcripts.parquet

Usage
-----
    # Full pipeline, all analysts:
    python -m finfluencer.collect.main run

    # Individual stage:
    python -m finfluencer.collect.main run --stage videos

    # Custom config paths:
    python -m finfluencer.collect.main run \\
        --settings config/settings.yaml \\
        --analysts config/analysts.yaml

    # Dry run (validate config, don't hit the API):
    python -m finfluencer.collect.main run --dry-run
"""

from __future__ import annotations

# NOTE (2026-07-14): torch must be imported before pandas/pyarrow on this
# platform. pyarrow (imported transitively via pandas below, and directly
# by finfluencer.utils.io) registers its own bundled-DLL search path on
# Windows; if that happens first, torch's own DLL loader
# (torch/__init__.py::_load_dll_libraries) subsequently fails with
# "OSError: [WinError 1114] ... torch/lib/c10.dll" the first time any
# downstream stage (sentiment/embeddings/topics) tries to use it - even
# though `import torch` alone, in a fresh process, works fine. Importing
# torch first avoids the conflict entirely. Best-effort: environments
# without torch (e.g. a lightweight collection-only install) still work,
# since torch is only a hard dependency of the ML stages, not collection.
try:
    import torch  # noqa: F401
except ImportError:
    pass


import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import typer

from finfluencer.collect.channels import collect_channels
from finfluencer.collect.comments import collect_comments
from finfluencer.collect.quota import (
    create_youtube_tracker,
    load_persisted_tracker,
    persist_tracker,
)
from finfluencer.collect.transcripts import collect_transcripts
from finfluencer.collect.videos import collect_videos
from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.config import (
    UNPINNED_REVISION_FALLBACK,
    LoadedConfig,
    is_placeholder_revision,
    load_settings,
)
from finfluencer.core.exceptions import FinfluencerError
from finfluencer.core.logging import configure, get_logger
from finfluencer.core.registry import instantiate
from finfluencer.core.reproducibility import (
    RunStatus,
    build_provenance,
    generate_run_id,
    write_provenance,
)
from finfluencer.analysis.topic_sentiment import run_topic_sentiment
from finfluencer.embeddings.pipeline import run_embeddings
from finfluencer.preprocess.pipeline import build_default_preprocessor, run_preprocessing
from finfluencer.sentiment.pipeline import run_sentiment
from finfluencer.topics.pipeline import run_topic_evolution, run_topics

# Trigger provider registration
import finfluencer.providers.language  # noqa: F401
import finfluencer.providers.platform  # noqa: F401
import finfluencer.embeddings.sentence_transformer  # noqa: F401
import finfluencer.sentiment.transformer_classifier  # noqa: F401


_log = get_logger(__name__)

_VALID_STAGES = (
    "channels", "videos", "comments", "preprocess", "embeddings", "sentiment",
    "topics", "topic_sentiment", "topic_evolution", "transcripts", "all",
)

#: Stages that talk to the YouTube API and therefore need a platform
#: provider + quota tracker. preprocess/embeddings are offline
#: NLP stages and must not require YT_API_KEY.
_PROVIDER_STAGES = frozenset({"channels", "videos", "comments", "transcripts", "all"})


app = typer.Typer(add_completion=False, help="Finfluencer data-collection CLI.")


# -----------------------------------------------------------------------------
# Python API — the shape callers should prefer
# -----------------------------------------------------------------------------


def build_provider_and_quota(cfg: LoadedConfig) -> tuple[Any, Any]:
    """Instantiate the platform provider with a persistent QuotaTracker."""
    quota_state_path = (
        Path(str(cfg.settings.output.paths.checkpoints)) / "quota_state.json"
    )
    quota = load_persisted_tracker(
        cfg.settings.collection.quota,
        quota_state_path,
    )
    provider = instantiate(
        "platform",
        cfg.settings.providers.platform,
        quota_tracker=quota,
        shorts_max_duration_sec=cfg.settings.collection.shorts_max_duration_sec,
        promo_keywords=cfg.settings.collection.promo_keywords,
    )
    return provider, quota


def build_checkpoint_manager(cfg: LoadedConfig) -> CheckpointManager:
    return CheckpointManager(
        checkpoint_root=cfg.settings.output.paths.checkpoints,
        cache_root=cfg.settings.output.paths.cache,
    )


def _run_manifest_path(cfg: LoadedConfig, run_id: str) -> Path:
    return (
        Path(str(cfg.settings.output.paths.checkpoints))
        / "run_manifests" / f"{run_id}.json"
    )


def _write_manifest_safe(
    cfg: LoadedConfig,
    checkpoint: CheckpointManager,
    run_id: str,
    *,
    stage: str,
    status: RunStatus,
    error: dict[str, str] | None = None,
    extras: dict[str, Any] | None = None,
) -> None:
    """Best-effort run-manifest write.

    Must never raise. A failure in the manifest system (Architecture
    v1.0 §10) must never turn an otherwise-successful pipeline run into
    a failure, and must never mask the *real* exception of an
    already-failing run — it only logs a warning and moves on.
    """
    try:
        provenance = build_provenance(
            cfg, stage=stage, run_id=run_id, status=status,
            checkpoint=checkpoint, error=error, extras=extras,
        )
        write_provenance(provenance, _run_manifest_path(cfg, run_id))
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "run_manifest_write_failed",
            run_id=run_id, status=status.value, reason=type(exc).__name__,
        )


def run_pipeline(
    cfg: LoadedConfig,
    *,
    stage: str = "all",
    dry_run: bool = False,
) -> dict[str, pd.DataFrame]:
    """Run one or all data-collection stages.

    Parameters
    ----------
    cfg
        Result of :func:`finfluencer.core.config.load_settings`.
    stage
        One of ``"channels"``, ``"videos"``, ``"comments"``,
        ``"preprocess"``, ``"embeddings"``, ``"sentiment"``, ``"topics"``,
        ``"topic_sentiment"``, ``"topic_evolution"``, ``"transcripts"``,
        or ``"all"`` (default).
    dry_run
        If True, validate config + construct provider but do not
        execute any stage.

    Returns
    -------
    dict[str, pd.DataFrame]
        Mapping stage_name → resulting frame. Empty on dry-run.

    Run manifest
    ------------
    Every non-dry-run invocation writes a run manifest (Architecture
    v1.0 §10) to ``<checkpoints>/run_manifests/<run_id>.json``: written
    as ``RUNNING`` before any stage executes, then updated in place to
    ``SUCCESS`` or ``FAILED`` when the run ends — a failed run still
    leaves behind a valid manifest describing what happened. Manifest
    writing is best-effort and can never itself cause this function to
    raise or to raise a different exception than the one the pipeline
    itself produced.
    """
    if stage not in _VALID_STAGES:
        raise ValueError(f"stage must be one of {_VALID_STAGES}, got {stage!r}")

    checkpoint = build_checkpoint_manager(cfg)

    provider: Any = None
    quota: Any = None
    if stage in _PROVIDER_STAGES:
        provider, quota = build_provider_and_quota(cfg)

    if dry_run:
        _log.info("dry_run_ok",
                  stage=stage,
                  quota_remaining=quota.remaining if quota is not None else None,
                  analysts=[a.key for a in cfg.roster.analysts])
        return {}

    run_id = generate_run_id()
    _write_manifest_safe(cfg, checkpoint, run_id, stage=stage, status=RunStatus.running)

    results: dict[str, pd.DataFrame] = {}
    try:
        data_raw = Path(str(cfg.settings.output.paths.data_raw))
        data_raw.mkdir(parents=True, exist_ok=True)

        salt = os.environ.get("ANON_SALT", "")

        # Stage 1: channels
        channels_path = data_raw / "channels.parquet"
        if stage in ("channels", "all"):
            _log.info("stage_start", stage="channels")
            df = collect_channels(
                cfg.settings, cfg.roster, provider, checkpoint,
                output_path=channels_path,
            )
            results["channels"] = df
            _log.info("stage_done", stage="channels", n_rows=len(df))

        # Stage 2: videos (needs channels)
        videos_path = data_raw / "videos.parquet"
        if stage in ("videos", "all"):
            if not channels_path.exists():
                raise FileNotFoundError(
                    f"channels.parquet not found at {channels_path}; "
                    f"run --stage channels first",
                )
            channels_df = pd.read_parquet(channels_path)
            _log.info("stage_start", stage="videos")
            df = collect_videos(
                cfg.settings, channels_df, provider, checkpoint,
                output_path=videos_path,
            )
            results["videos"] = df
            _log.info("stage_done", stage="videos", n_rows=len(df))

        # Stage 3: comments (needs videos)
        comments_path = data_raw / "comments.parquet"
        if stage in ("comments", "all"):
            if not videos_path.exists():
                raise FileNotFoundError(
                    f"videos.parquet not found at {videos_path}; "
                    f"run --stage videos first",
                )
            videos_df = pd.read_parquet(videos_path)
            _log.info("stage_start", stage="comments")
            df = collect_comments(
                cfg.settings, videos_df, provider, checkpoint,
                output_path=comments_path,
                salt=salt or None,
            )
            results["comments"] = df
            _log.info("stage_done", stage="comments", n_rows=len(df))

        # Stage 3b: preprocess (needs comments)
        if stage in ("preprocess", "all"):
            if not comments_path.exists():
                raise FileNotFoundError(
                    f"comments.parquet not found at {comments_path}; "
                    f"run --stage comments first",
                )
            _log.info("stage_start", stage="preprocess")
            language = instantiate("language", cfg.settings.providers.language)
            preprocessor = build_default_preprocessor(language)
            df = run_preprocessing(
                cfg.settings, comments_path, checkpoint,
                preprocessor=preprocessor,
            )
            results["preprocess"] = df
            _log.info("stage_done", stage="preprocess", n_rows=len(df))

        # Stage 3c: embeddings (needs comments with text_clean populated)
        if stage in ("embeddings", "all"):
            if not comments_path.exists():
                raise FileNotFoundError(
                    f"comments.parquet not found at {comments_path}; "
                    f"run --stage comments first",
                )
            _log.info("stage_start", stage="embeddings")
            data_processed = Path(str(cfg.settings.output.paths.data_processed))
            data_processed.mkdir(parents=True, exist_ok=True)
            embedding_model = cfg.settings.topics.embedding_model
            # Publication-stage pin enforcement already ran inside load_settings()
            # against the raw config value; here we resolve a still-placeholder
            # revision to an actually loadable ref so pre-publication runs work.
            effective_revision = (
                UNPINNED_REVISION_FALLBACK
                if is_placeholder_revision(embedding_model.revision)
                else embedding_model.revision
            )
            embedding_provider = instantiate(
                "embedding", "sentence_transformer",
                model_name=embedding_model.name,
                revision=effective_revision,
            )
            df = run_embeddings(
                cfg.settings, comments_path, checkpoint,
                provider=embedding_provider,
                output_path=data_processed / "embeddings_index.parquet",
            )
            results["embeddings"] = df
            _log.info("stage_done", stage="embeddings", n_rows=len(df))

        # Stage 3d: sentiment (needs comments with text_clean populated)
        if stage in ("sentiment", "all"):
            if not comments_path.exists():
                raise FileNotFoundError(
                    f"comments.parquet not found at {comments_path}; "
                    f"run --stage comments first",
                )
            _log.info("stage_start", stage="sentiment")
            data_processed = Path(str(cfg.settings.output.paths.data_processed))
            data_processed.mkdir(parents=True, exist_ok=True)
            primary_model = cfg.settings.sentiment.primary_model
            effective_revision = (
                UNPINNED_REVISION_FALLBACK
                if is_placeholder_revision(primary_model.revision)
                else primary_model.revision
            )
            sentiment_provider = instantiate(
                "sentiment", "transformer",
                model_name=primary_model.name,
                revision=effective_revision,
                batch_size=cfg.settings.sentiment.batch_size,
                max_length=primary_model.max_length or 512,
            )
            df = run_sentiment(
                cfg.settings, comments_path, checkpoint,
                provider=sentiment_provider,
                output_path=data_processed / "sentiment.parquet",
            )
            results["sentiment"] = df
            _log.info("stage_done", stage="sentiment", n_rows=len(df))

        # Stage 3e: topics (needs comments text_clean + embeddings_index.parquet)
        if stage in ("topics", "all"):
            if not comments_path.exists():
                raise FileNotFoundError(
                    f"comments.parquet not found at {comments_path}; "
                    f"run --stage comments first",
                )
            data_processed = Path(str(cfg.settings.output.paths.data_processed))
            embeddings_index_path = data_processed / "embeddings_index.parquet"
            if not embeddings_index_path.exists():
                raise FileNotFoundError(
                    f"embeddings_index.parquet not found at {embeddings_index_path}; "
                    f"run --stage embeddings first",
                )
            _log.info("stage_start", stage="topics")
            data_processed.mkdir(parents=True, exist_ok=True)
            df = run_topics(
                cfg.settings, comments_path, embeddings_index_path, checkpoint,
                output_path=data_processed / "topics.parquet",
            )
            results["topics"] = df
            _log.info("stage_done", stage="topics", n_rows=len(df))

        # Stage 3f: topic_sentiment (needs topics.parquet + sentiment.parquet;
        # cheap descriptive aggregation, no checkpointing)
        if stage in ("topic_sentiment", "all"):
            data_processed = Path(str(cfg.settings.output.paths.data_processed))
            topics_out_path = data_processed / "topics.parquet"
            sentiment_out_path = data_processed / "sentiment.parquet"
            if not topics_out_path.exists():
                raise FileNotFoundError(
                    f"topics.parquet not found at {topics_out_path}; "
                    f"run --stage topics first",
                )
            if not sentiment_out_path.exists():
                raise FileNotFoundError(
                    f"sentiment.parquet not found at {sentiment_out_path}; "
                    f"run --stage sentiment first",
                )
            _log.info("stage_start", stage="topic_sentiment")
            data_processed.mkdir(parents=True, exist_ok=True)
            df = run_topic_sentiment(
                comments_path, topics_out_path, sentiment_out_path,
                output_path=data_processed / "topic_sentiment.parquet",
            )
            results["topic_sentiment"] = df
            _log.info("stage_done", stage="topic_sentiment", n_rows=len(df))

        # Stage 3g: topic_evolution (needs comments + embeddings_index.parquet +
        # topics.parquet; read-only view over the cached BERTopic model, never
        # refits. CLI defaults to "pooled" - the primary cross-analyst view;
        # within_analyst evolution is reachable via the Python API directly.)
        if stage in ("topic_evolution", "all"):
            if not comments_path.exists():
                raise FileNotFoundError(
                    f"comments.parquet not found at {comments_path}; "
                    f"run --stage comments first",
                )
            data_processed = Path(str(cfg.settings.output.paths.data_processed))
            embeddings_index_path = data_processed / "embeddings_index.parquet"
            topics_out_path = data_processed / "topics.parquet"
            if not embeddings_index_path.exists():
                raise FileNotFoundError(
                    f"embeddings_index.parquet not found at {embeddings_index_path}; "
                    f"run --stage embeddings first",
                )
            if not topics_out_path.exists():
                raise FileNotFoundError(
                    f"topics.parquet not found at {topics_out_path}; "
                    f"run --stage topics first",
                )
            _log.info("stage_start", stage="topic_evolution")
            data_processed.mkdir(parents=True, exist_ok=True)
            df = run_topic_evolution(
                cfg.settings, comments_path, embeddings_index_path, topics_out_path,
                checkpoint, configuration="pooled",
                output_path=data_processed / "topic_evolution.parquet",
            )
            results["topic_evolution"] = df
            _log.info("stage_done", stage="topic_evolution", n_rows=len(df))

        # Stage 4: transcripts (needs videos, does NOT need the provider)
        transcripts_path = data_raw / "transcripts.parquet"
        if stage in ("transcripts", "all"):
            if not videos_path.exists():
                raise FileNotFoundError(
                    f"videos.parquet not found at {videos_path}; "
                    f"run --stage videos first",
                )
            videos_df = pd.read_parquet(videos_path)
            _log.info("stage_start", stage="transcripts")
            df = collect_transcripts(
                cfg.settings, videos_df, checkpoint,
                output_path=transcripts_path,
            )
            results["transcripts"] = df
            _log.info("stage_done", stage="transcripts", n_rows=len(df))

        # Persist quota state so tomorrow's run starts from the current usage.
        # Only relevant when a provider/quota was actually constructed
        # (offline-only runs such as --stage preprocess/embeddings/sentiment skip this).
        # Best-effort: every actual collection/processing stage above has
        # already completed and written its output by this point, so a
        # failure purely in saving quota bookkeeping must not turn an
        # otherwise-successful run into a FAILED manifest (same rationale
        # as _write_manifest_safe).
        if quota is not None:
            quota_state_path = (
                Path(str(cfg.settings.output.paths.checkpoints)) / "quota_state.json"
            )
            try:
                persist_tracker(quota, quota_state_path)
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "quota_state_persist_failed",
                    reason=type(exc).__name__,
                )
        _log.info("pipeline_complete", stages_run=list(results.keys()),
                  quota_snapshot=quota.snapshot() if quota is not None else None)
    except Exception as exc:
        _write_manifest_safe(
            cfg, checkpoint, run_id, stage=stage, status=RunStatus.failed,
            error={"type": type(exc).__name__, "message": str(exc)},
            extras={"stages_run": list(results.keys())},
        )
        raise

    _write_manifest_safe(
        cfg, checkpoint, run_id, stage=stage, status=RunStatus.success,
        extras={"stages_run": list(results.keys())},
    )
    return results


# -----------------------------------------------------------------------------
# CLI wrapper (Typer)
# -----------------------------------------------------------------------------


@app.command()
def run(
    settings: Path = typer.Option(
        Path("config/settings.yaml"), "--settings", "-s",
        help="Path to settings.yaml",
    ),
    analysts: Path = typer.Option(
        Path("config/analysts.yaml"), "--analysts", "-a",
        help="Path to analysts.yaml",
    ),
    stage: str = typer.Option(
        "all", "--stage",
        help=f"Stage to run: one of {_VALID_STAGES}",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Validate config + provider without executing any stage",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Human-readable console logging (default: JSON to stderr)",
    ),
) -> None:
    """Run the data-collection pipeline."""
    if stage not in _VALID_STAGES:
        typer.echo(
            f"Error: --stage must be one of {_VALID_STAGES}, got {stage!r}",
            err=True,
        )
        raise typer.Exit(code=2)

    try:
        cfg = load_settings(settings, analysts)
        log_dir = Path(str(cfg.settings.output.paths.logs))
        log_dir.mkdir(parents=True, exist_ok=True)
        configure(log_dir=log_dir, verbose=verbose)

        run_pipeline(cfg, stage=stage, dry_run=dry_run)
    except (FileNotFoundError, FinfluencerError) as e:
        # Known, typed failure modes (bad config, missing upstream stage
        # output, quota/auth/collection errors, ...) get a clean one-line
        # message. Anything else is an unexpected error and is left to
        # propagate as a full traceback so it isn't accidentally hidden.
        typer.echo(f"Pipeline aborted: {e}", err=True)
        raise typer.Exit(code=1)


def main() -> None:
    """Module entry point (``python -m finfluencer.collect.main``)."""
    app()


if __name__ == "__main__":
    main()
