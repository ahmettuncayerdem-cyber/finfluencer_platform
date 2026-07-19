"""
finfluencer.sentiment.pipeline
=================================

Sentiment-polarity stage (Phase 2.2): ``comments.parquet.text_clean``
-> cached P(positive) scores -> ``sentiment.parquet`` (SentimentRecord schema).

Scope
-----
Binary polarity only. ``sentiment_target`` / ``sentiment_market_directed``
(analyst vs market vs both vs neither) are populated as ``None`` here by
design - target-of-affect classification is a distinct NLP task
(target-dependent sentiment) with its own model and evaluation
requirements and ships as Phase 2.3, wired against the same
``comment_id`` join key already present in this frame.

Cache-first
-----------
SHA-256 of ``(text_clean, model_name, revision, device)`` is the cache
key (Tier-3, ``kind="sentiment"`` - a separate namespace from the
``"embeddings"`` cache, so entries never collide even though the
hashing scheme is identical). Identical text is scored once.

Checkpointing
-------------
One Tier-2 stage per analyst (``sentiment_comments__<analyst_key>``),
mirroring :mod:`finfluencer.embeddings.pipeline`; ``root_seed`` and the
``pseudo_neutral_band`` are folded into the stage's config-slice hash.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import SentimentClass, SentimentRecord, Settings
from finfluencer.core.logging import bind_context, clear_context, get_logger
from finfluencer.core.reproducibility import derive_seed
from finfluencer.sentiment.base import SentimentProvider
from finfluencer.utils.hashing import hash_string
from finfluencer.utils.io import read_parquet, write_parquet

_log = get_logger(__name__)
_STAGE_PREFIX = "sentiment_comments"
_CACHE_KIND = "sentiment"
_INDEX_COLUMNS: list[str] = list(SentimentRecord.model_fields.keys())
_DEFAULT_OUTPUT = Path("data/processed/sentiment.parquet")


def _stage_name(analyst_key: str) -> str:
    return f"{_STAGE_PREFIX}__{analyst_key}"


def _provider_metadata(provider: SentimentProvider) -> tuple[str, str, str]:
    """Read model_name/revision/device off the provider when available.

    The Protocol itself only guarantees key/predict; richer providers
    (e.g. TransformerSentimentClassifier) expose these for accurate
    cache-key composition. Minimal/fake providers fall back to defaults.
    """
    model_name = getattr(provider, "model_name", provider.key)
    revision = getattr(provider, "revision", "unknown")
    device = getattr(provider, "device", "cpu")
    return model_name, revision, device


def _score_hash(text_clean: str, model_name: str, revision: str, device: str) -> str:
    return hash_string(f"{text_clean}::{model_name}::{revision}::{device}")


def _empty_index() -> pd.DataFrame:
    return pd.DataFrame(columns=_INDEX_COLUMNS)


def _config_slice(
    provider_key: str,
    model_name: str,
    revision: str,
    device: str,
    pseudo_neutral_band: tuple[float, float],
    stage_seed: int,
) -> dict[str, Any]:
    return {
        "provider_key": provider_key,
        "model_name": model_name,
        "revision": revision,
        "device": device,
        "pseudo_neutral_band": list(pseudo_neutral_band),
        "stage_seed": stage_seed,
    }


def _classify(prob: float, band: tuple[float, float]) -> tuple[str, bool]:
    """Threshold + pseudo-neutral banding (Methods 3.4.1).

    Returns ``(sentiment_class.value, sentiment_pseudo_neutral)``.
    """
    lo, hi = band
    sentiment_class = SentimentClass.positive if prob >= 0.5 else SentimentClass.negative
    pseudo_neutral = lo <= prob <= hi
    return sentiment_class.value, pseudo_neutral


def _process_group(
    group: pd.DataFrame,
    *,
    provider: SentimentProvider,
    checkpoint: CheckpointManager,
    model_name: str,
    revision: str,
    device: str,
    pseudo_neutral_band: tuple[float, float],
) -> pd.DataFrame:
    """Cache-first polarity scoring for one analyst's comment subset.

    Per-row work (hashing, classification) is plain Python; only
    cache-miss texts are sent to ``provider.predict`` (batched), and
    each unique hash is scored at most once even across duplicate
    ``text_clean`` values.
    """
    comment_ids = group["comment_id"].tolist()
    texts = group["text_clean"].tolist()
    hashes = [_score_hash(t, model_name, revision, device) for t in texts]

    misses: dict[str, str] = {}
    for h, t in zip(hashes, texts):
        if h not in misses and not checkpoint.cache_has(_CACHE_KIND, h, ".npy"):
            misses[h] = t

    if misses:
        miss_hashes = list(misses.keys())
        probs = provider.predict([misses[h] for h in miss_hashes])
        for h, p in zip(miss_hashes, probs):
            path = checkpoint.cache_path(_CACHE_KIND, h, ".npy")
            np.save(path, np.asarray(p, dtype=np.float32))

    records = []
    for cid, h in zip(comment_ids, hashes):
        path = checkpoint.cache_path(_CACHE_KIND, h, ".npy")
        prob = float(np.load(path))
        sentiment_class, pseudo_neutral = _classify(prob, pseudo_neutral_band)
        records.append({
            "comment_id": cid,
            "sentiment_prob": prob,
            "sentiment_class": sentiment_class,
            "sentiment_pseudo_neutral": pseudo_neutral,
            "sentiment_target": None,           # Phase 2.3
            "sentiment_market_directed": None,  # Phase 2.3
        })
    return pd.DataFrame.from_records(records, columns=_INDEX_COLUMNS)


def run_sentiment(
    settings: Settings,
    comments_path: Path | str,
    checkpoint: CheckpointManager,
    *,
    provider: SentimentProvider,
    output_path: Path | str | None = None,
    analyst_key: str | None = None,
) -> pd.DataFrame:
    """Fill ``sentiment.parquet`` from ``comments.parquet.text_clean``.

    Parameters
    ----------
    settings
        Validated settings; uses ``settings.sentiment.pseudo_neutral_band``
        and ``settings.study.root_seed``.
    comments_path
        Source ``comments.parquet`` (read-only; must have ``text_clean``
        populated by :mod:`finfluencer.preprocess.pipeline` first).
    checkpoint
        Shared :class:`CheckpointManager`; one Tier-2 stage per analyst,
        Tier-3 cache for the scores themselves.
    provider
        Any :class:`SentimentProvider`-compatible object.
    output_path
        Destination. Defaults to ``data/processed/sentiment.parquet``.
    analyst_key
        If given, only that analyst's rows are (re)scored; others are
        carried through unchanged from any existing output.
    """
    comments_path = Path(comments_path)
    output_path = Path(output_path) if output_path is not None else _DEFAULT_OUTPUT

    df = read_parquet(comments_path)
    if df.empty or "analyst_key" not in df.columns or "text_clean" not in df.columns:
        _log.warning("sentiment_no_comments_available")
        empty = _empty_index()
        write_parquet(empty, output_path)
        return empty

    model_name, revision, device = _provider_metadata(provider)
    band = tuple(settings.sentiment.pseudo_neutral_band)
    stage_seed = derive_seed(settings.study.root_seed, _STAGE_PREFIX)
    cfg_slice = _config_slice(provider.key, model_name, revision, device, band, stage_seed)

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
                pseudo_neutral_band=band,
            )
            parts.append(result)
            checkpoint.mark_done(
                stage_name, cfg_slice, extras={"n_scored": len(result)},
            )
            _log.info(
                "sentiment_analyst_done", analyst_key=key, n_scored=len(result),
            )
        finally:
            clear_context()

    non_empty_parts = [p for p in parts if not p.empty]
    result_df = (
        pd.concat(non_empty_parts, ignore_index=True) if non_empty_parts else _empty_index()
    )
    write_parquet(result_df, output_path)
    _log.info("sentiment_stage_summary", n_rows_out=len(result_df))
    return result_df


__all__ = ["run_sentiment"]
