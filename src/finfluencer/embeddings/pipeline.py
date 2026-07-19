"""
finfluencer.embeddings.pipeline
=================================

Embedding-generation stage: ``comments.parquet.text_clean`` -> cached
``.npy`` vectors + ``embeddings_index.parquet`` (Phase 2.1).

Cache-first
-----------
The SHA-256 of ``(text_clean, model_name, revision, device)`` is the
cache key (Tier-3, ``CheckpointManager.cache_path``/``cache_has``,
kind="embeddings"). Identical text is encoded once - duplicates across
or within an analyst's comments reuse the same cache entry - and the
same text on CPU vs GPU (or a different model/revision) is a deliberate
cache miss, since the vectors are not guaranteed identical.

Checkpointing
-------------
One Tier-2 stage per analyst (``embed_comments__<analyst_key>``),
mirroring :mod:`finfluencer.preprocess.pipeline`; ``root_seed`` is
folded into the stage's config-slice hash so a reproducibility-seed
change forces reprocessing. When a stage is skipped, previously-indexed
rows are sourced from ``output_path`` (falling back to an empty frame
for analysts never processed).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import EmbeddingIndexRecord, Settings
from finfluencer.core.logging import bind_context, clear_context, get_logger
from finfluencer.core.reproducibility import derive_seed
from finfluencer.embeddings.base import EmbeddingProvider
from finfluencer.utils.hashing import hash_string
from finfluencer.utils.io import read_parquet, write_parquet

_log = get_logger(__name__)
_STAGE_PREFIX = "embed_comments"
_CACHE_KIND = "embeddings"
_INDEX_COLUMNS: list[str] = list(EmbeddingIndexRecord.model_fields.keys())
_DEFAULT_OUTPUT = Path("data/processed/embeddings_index.parquet")


def _stage_name(analyst_key: str) -> str:
    return f"{_STAGE_PREFIX}__{analyst_key}"


def _provider_metadata(provider: EmbeddingProvider) -> tuple[str, str, str]:
    """Read model_name/revision/device off the provider when available.

    The Protocol itself only guarantees key/dim/encode; richer providers
    (e.g. SentenceTransformerProvider) expose these for accurate
    embeddings_index.parquet provenance. Minimal/fake providers fall
    back to sensible defaults.
    """
    model_name = getattr(provider, "model_name", provider.key)
    revision = getattr(provider, "revision", "unknown")
    device = getattr(provider, "device", "cpu")
    return model_name, revision, device


def _embedding_hash(text_clean: str, model_name: str, revision: str, device: str) -> str:
    return hash_string(f"{text_clean}::{model_name}::{revision}::{device}")


def _empty_index() -> pd.DataFrame:
    return pd.DataFrame(columns=_INDEX_COLUMNS)


def _config_slice(
    provider_key: str, model_name: str, revision: str, device: str, stage_seed: int,
) -> dict[str, Any]:
    return {
        "provider_key": provider_key,
        "model_name": model_name,
        "revision": revision,
        "device": device,
        "stage_seed": stage_seed,
    }


def _process_group(
    group: pd.DataFrame,
    *,
    provider: EmbeddingProvider,
    checkpoint: CheckpointManager,
    model_name: str,
    revision: str,
    device: str,
) -> pd.DataFrame:
    """Cache-first embedding for one analyst's comment subset.

    Only cache-miss texts are encoded, and each unique hash is encoded
    at most once even if several rows share identical ``text_clean``
    (duplicate-text de-duplication). Pandas is used only to read the
    input columns and assemble the output frame; the miss-detection and
    encode-dispatch logic is plain Python.
    """
    comment_ids = group["comment_id"].tolist()
    texts = group["text_clean"].tolist()
    hashes = [_embedding_hash(t, model_name, revision, device) for t in texts]

    misses: dict[str, str] = {}
    for h, t in zip(hashes, texts):
        if h not in misses and not checkpoint.cache_has(_CACHE_KIND, h, ".npy"):
            misses[h] = t

    if misses:
        miss_hashes = list(misses.keys())
        vectors = provider.encode([misses[h] for h in miss_hashes])
        for h, vec in zip(miss_hashes, vectors):
            path = checkpoint.cache_path(_CACHE_KIND, h, ".npy")
            np.save(path, np.asarray(vec))

    records = [
        {
            "comment_id": cid,
            "embedding_hash": h,
            "embedding_path": str(checkpoint.cache_path(_CACHE_KIND, h, ".npy")),
            "model_name": model_name,
            "revision": revision,
            "dimension": provider.dim,
        }
        for cid, h in zip(comment_ids, hashes)
    ]
    return pd.DataFrame.from_records(records, columns=_INDEX_COLUMNS)


def run_embeddings(
    settings: Settings,
    comments_path: Path | str,
    checkpoint: CheckpointManager,
    *,
    provider: EmbeddingProvider,
    output_path: Path | str | None = None,
    analyst_key: str | None = None,
) -> pd.DataFrame:
    """Fill ``embeddings_index.parquet`` from ``comments.parquet.text_clean``.

    Parameters
    ----------
    settings
        Validated settings; uses ``settings.study.root_seed``.
    comments_path
        Source ``comments.parquet`` (read-only; must have ``text_clean``
        populated by :mod:`finfluencer.preprocess.pipeline` first).
    checkpoint
        Shared :class:`CheckpointManager`; one Tier-2 stage per analyst,
        Tier-3 cache for the vectors themselves.
    provider
        Any :class:`EmbeddingProvider`-compatible object.
    output_path
        Destination index. Defaults to ``data/processed/embeddings_index.parquet``.
    analyst_key
        If given, only that analyst's rows are (re)embedded; others are
        carried through unchanged from any existing index.
    """
    comments_path = Path(comments_path)
    output_path = Path(output_path) if output_path is not None else _DEFAULT_OUTPUT

    df = read_parquet(comments_path)
    if df.empty or "analyst_key" not in df.columns or "text_clean" not in df.columns:
        _log.warning("embeddings_no_comments_available")
        empty = _empty_index()
        write_parquet(empty, output_path)
        return empty

    model_name, revision, device = _provider_metadata(provider)
    stage_seed = derive_seed(settings.study.root_seed, _STAGE_PREFIX)
    cfg_slice = _config_slice(provider.key, model_name, revision, device, stage_seed)

    existing_df: pd.DataFrame | None = None
    if output_path.exists():
        try:
            existing_df = read_parquet(output_path)
        except Exception:  # noqa: BLE001
            existing_df = None

    all_keys = sorted(df["analyst_key"].unique().tolist())
    target_keys = [analyst_key] if analyst_key is not None else all_keys
    out_of_scope_keys = [k for k in all_keys if k not in target_keys]

    def _prior_rows(key: str) -> pd.DataFrame:
        if existing_df is not None and "comment_id" in existing_df.columns:
            ids = set(df.loc[df["analyst_key"] == key, "comment_id"].tolist())
            rows = existing_df.loc[existing_df["comment_id"].isin(ids)]
            if not rows.empty:
                return rows
        return _empty_index()

    parts: list[pd.DataFrame] = [_prior_rows(k) for k in out_of_scope_keys]

    for key in target_keys:
        group = df.loc[df["analyst_key"] == key]
        if group.empty:
            continue

        stage_name = _stage_name(key)
        marker = checkpoint.checkpoint_root / f"{stage_name}.done"
        had_marker = marker.exists()

        if not checkpoint.should_run(stage_name, cfg_slice):
            parts.append(_prior_rows(key))
            continue
        if had_marker and not marker.exists():
            checkpoint.invalidate(stage_name)

        bind_context(analyst_key=key, stage=stage_name)
        try:
            result = _process_group(
                group, provider=provider, checkpoint=checkpoint,
                model_name=model_name, revision=revision, device=device,
            )
            parts.append(result)
            checkpoint.mark_done(
                stage_name, cfg_slice, extras={"n_embedded": len(result)},
            )
            _log.info(
                "embeddings_analyst_done", analyst_key=key, n_embedded=len(result),
            )
        finally:
            clear_context()

    non_empty_parts = [p for p in parts if not p.empty]
    result_df = (
        pd.concat(non_empty_parts, ignore_index=True) if non_empty_parts else _empty_index()
    )
    write_parquet(result_df, output_path)
    _log.info("embeddings_stage_summary", n_rows_out=len(result_df))
    return result_df


__all__ = ["run_embeddings"]
