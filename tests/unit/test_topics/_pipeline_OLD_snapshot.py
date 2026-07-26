"""
finfluencer.topics.pipeline
==============================

BERTopic stage (Phase 2.3): ``comments.parquet.text_clean`` +
``embeddings_index.parquet`` -> ``topics.parquet`` (TopicRecord schema).

Two-level cache-first design
-----------------------------
Unlike embeddings/sentiment (per-row, embarrassingly parallel), topic
modeling is a *joint/batch* operation — one comment's topic depends on
every other comment in its fitting corpus. So the cache unit here is
the **fitted BERTopic model**, not a per-row result:

* **Tier-3 model cache** (``kind="topics_model"``): keyed by a
  fingerprint of ``(sorted comment_ids, embedding model/revision, UMAP
  config, HDBSCAN config, configuration name, stage_seed)``. Same
  corpus + same config -> load the saved model and ``.transform()``
  (cheap, deterministic) instead of refitting.
* **Tier-2 stage checkpoint**: its config-slice additionally includes
  ``reduce_outliers``/``merge_similarity_threshold``. Changing either
  reprocesses the stage (so the parquet output reflects it) but still
  *hits* the model cache — outlier-reduction and topic-merging are
  cheap, deterministic post-processing steps reapplied on every run,
  never part of the expensive UMAP/HDBSCAN refit decision.

Checkpoint granularity
-----------------------
* ``within_analyst``: one Tier-2 stage per analyst
  (``topics_within__<analyst_key>``) — a separate model per analyst,
  so ``analyst_key`` filtering works exactly like
  :mod:`finfluencer.embeddings.pipeline`.
* ``pooled``: a single stage (``topics_pooled``) over the full corpus.
  Pooled is inherently cross-analyst; when ``analyst_key`` narrows a
  call, pooled is skipped for that call and its existing rows (if any)
  are carried through unchanged — splitting "pooled" per analyst would
  silently change what the configuration means.

Deferred to later phases (not implemented here)
-------------------------------------------------
``topic_tier`` is always written as ``None`` — it is a dictionary-based
downstream classification task, separate from BERTopic itself.

``topic_label`` is populated from the fitted/loaded BERTopic model's own
``get_topic_info()`` (its default c-TF-IDF-derived topic name, e.g.
``"3_borsa_faiz_piyasa"``) when available — see ``_topic_label_map``.
This is BERTopic's own descriptive name, not manual/LLM-assisted
semantic labeling; that remains future work. Injected test doubles that
don't expose ``get_topic_info()`` fall back to ``None`` (unchanged
behaviour).

Temporal topic evolution (Phase 2.5)
--------------------------------------
:func:`run_topic_evolution` is a read-only downstream view — it never
fits a model. It recomputes the same fingerprint used above to locate
the already-cached model, then asks BERTopic's own
``topics_over_time()`` for a time-binned representation, passing this
stage's own final ``topic_id`` assignments explicitly (so
outlier-reduction/merge post-processing is respected rather than the
model's raw fit-time ``self.topics_``). Raises ``FileNotFoundError`` if
the ``topics`` stage hasn't produced a cached model for the requested
``(configuration[, analyst_key])`` yet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import (
    Settings,
    TopicEvolutionRecord,
    TopicRecord,
    TopicsConfig,
)
from finfluencer.core.logging import bind_context, clear_context, get_logger
from finfluencer.core.reproducibility import derive_seed
from finfluencer.topics.bertopic_runner import BERTopicRunner, TopicFitResult
from finfluencer.topics.bertopic_runner import topics_over_time as _bertopic_topics_over_time
from finfluencer.utils.hashing import hash_config_dict
from finfluencer.utils.io import read_parquet, write_parquet

_log = get_logger(__name__)
_STAGE_PREFIX_WITHIN = "topics_within"
_STAGE_NAME_POOLED = "topics_pooled"
_MODEL_CACHE_KIND = "topics_model"
_INDEX_COLUMNS: list[str] = list(TopicRecord.model_fields.keys())
_DEFAULT_OUTPUT = Path("data/processed/topics.parquet")
_EVOLUTION_INDEX_COLUMNS: list[str] = list(TopicEvolutionRecord.model_fields.keys())
_DEFAULT_EVOLUTION_OUTPUT = Path("data/processed/topic_evolution.parquet")

RunnerFactory = Callable[..., BERTopicRunner]


def _within_stage_name(analyst_key: str) -> str:
    return f"{_STAGE_PREFIX_WITHIN}__{analyst_key}"


def _empty_index() -> pd.DataFrame:
    return pd.DataFrame(columns=_INDEX_COLUMNS)


def _load_embedding_matrix(paths: list[str]) -> np.ndarray:
    return np.stack([np.load(p) for p in paths])


def _model_fingerprint(
    comment_ids: list[str],
    embedding_model_name: str,
    embedding_revision: str,
    cfg: TopicsConfig,
    configuration: str,
    stage_seed: int,
) -> str:
    """Cache key for the fitted model. Excludes reduce_outliers/merge
    threshold on purpose — those are cheap post-steps reapplied fresh,
    never a reason to refit UMAP/HDBSCAN."""
    material = {
        "comment_ids": sorted(comment_ids),
        "embedding_model_name": embedding_model_name,
        "embedding_revision": embedding_revision,
        "umap": cfg.umap.model_dump(mode="json"),
        "hdbscan": cfg.hdbscan.model_dump(mode="json"),
        "configuration": configuration,
        "stage_seed": stage_seed,
    }
    return hash_config_dict(material)


def _stage_cfg_slice(
    fingerprint: str, reduce_outliers: bool, merge_similarity_threshold: float,
) -> dict[str, Any]:
    return {
        "fingerprint": fingerprint,
        "reduce_outliers": reduce_outliers,
        "merge_similarity_threshold": merge_similarity_threshold,
    }


def _fit_or_load(
    runner_factory: RunnerFactory,
    model_loader: Callable[[Path], Any],
    checkpoint: CheckpointManager,
    fingerprint: str,
    texts: list[str],
    embeddings: np.ndarray,
) -> TopicFitResult:
    model_path = checkpoint.cache_path(_MODEL_CACHE_KIND, fingerprint, ".pkl")
    cache_hit = checkpoint.cache_has(_MODEL_CACHE_KIND, fingerprint, ".pkl")
    if cache_hit:
        loaded_model = model_loader(model_path)
        runner = runner_factory(model=loaded_model)
        result = runner.transform(texts, embeddings)
    else:
        runner = runner_factory(model=None)
        result = runner.fit_transform(texts, embeddings)
        runner.save(model_path)
    # TEMPORARY DIAGNOSTIC INSTRUMENTATION — remove once topic_label
    # root cause is confirmed on a real run.
    _log.info(
        "topic_label_debug_fit_or_load",
        fingerprint=fingerprint,
        cache_hit=cache_hit,
        model_is_none=result.model is None,
        model_type=type(result.model).__name__,
        n_topic_ids=len(result.topic_ids),
        unique_topic_ids=sorted(set(result.topic_ids)),
    )
    return result


def _topic_label_map(model: Any) -> dict[int, str]:
    """Best-effort ``topic_id -> Name`` lookup from a fitted/loaded
    BERTopic model's own ``get_topic_info()``.

    Returns ``{}`` (all labels fall back to ``None``) if the model has
    no such method — this is what keeps injected test doubles (which
    expose only ``fit_transform``/``transform``/``save``) working
    unchanged. Any lookup failure is logged and swallowed rather than
    failing the stage, since the label is descriptive metadata, not
    required for downstream correctness.
    """
    get_topic_info = getattr(model, "get_topic_info", None)
    # TEMPORARY DIAGNOSTIC INSTRUMENTATION — remove once topic_label
    # root cause is confirmed on a real run.
    _log.info(
        "topic_label_debug_map_lookup",
        model_type=type(model).__name__,
        has_get_topic_info=get_topic_info is not None,
    )
    if get_topic_info is None:
        return {}
    try:
        info = get_topic_info()
        label_map = dict(zip(info["Topic"], info["Name"]))
        _log.info(
            "topic_label_debug_map_built",
            n_entries=len(label_map),
            sample=dict(list(label_map.items())[:5]),
            key_types=sorted({type(k).__name__ for k in label_map.keys()}),
        )
        return label_map
    except Exception as exc:  # noqa: BLE001
        _log.warning("topic_label_lookup_failed", reason=str(exc))
        return {}


def _rows_from_result(
    comment_ids: list[str], result: TopicFitResult, configuration: str,
) -> pd.DataFrame:
    label_map = _topic_label_map(result.model)
    # TEMPORARY DIAGNOSTIC INSTRUMENTATION — remove once topic_label
    # root cause is confirmed on a real run.
    unique_result_ids = sorted(set(result.topic_ids))
    _log.info(
        "topic_label_debug_rows",
        configuration=configuration,
        unique_topic_ids_in_result=unique_result_ids,
        topic_ids_missing_from_label_map=[
            t for t in unique_result_ids if t not in label_map
        ],
        result_id_types=sorted({type(t).__name__ for t in result.topic_ids}),
    )
    records = [
        {
            "comment_id": cid,
            "topic_id": tid,
            "topic_prob": prob,
            "topic_tier": None,
            "configuration": configuration,
            "topic_label": label_map.get(tid),
        }
        for cid, tid, prob in zip(comment_ids, result.topic_ids, result.topic_probs)
    ]
    return pd.DataFrame.from_records(records, columns=_INDEX_COLUMNS)


def _process_within_analyst(
    joined: pd.DataFrame,
    *,
    cfg: TopicsConfig,
    checkpoint: CheckpointManager,
    stage_seed: int,
    analyst_key_filter: str | None,
    runner_factory: RunnerFactory,
    model_loader: Callable[[Path], Any],
    existing_df: pd.DataFrame | None,
) -> pd.DataFrame:
    all_keys = sorted(joined["analyst_key"].unique().tolist())
    target_keys = [analyst_key_filter] if analyst_key_filter is not None else all_keys
    out_of_scope_keys = [k for k in all_keys if k not in target_keys]

    def _prior(key: str) -> pd.DataFrame:
        if existing_df is not None and "comment_id" in existing_df.columns:
            ids = set(joined.loc[joined["analyst_key"] == key, "comment_id"].tolist())
            rows = existing_df.loc[
                existing_df["comment_id"].isin(ids)
                & (existing_df["configuration"] == "within_analyst")
            ]
            if not rows.empty:
                return rows
        return _empty_index()

    parts: list[pd.DataFrame] = [_prior(k) for k in out_of_scope_keys]

    for key in target_keys:
        group = joined.loc[joined["analyst_key"] == key]
        if group.empty:
            continue

        comment_ids = group["comment_id"].tolist()
        fingerprint = _model_fingerprint(
            comment_ids,
            group["embedding_model_name"].iloc[0],
            group["embedding_revision"].iloc[0],
            cfg, "within_analyst", stage_seed,
        )
        cfg_slice = _stage_cfg_slice(fingerprint, cfg.reduce_outliers, cfg.merge_similarity_threshold)
        stage_name = _within_stage_name(key)
        marker = checkpoint.checkpoint_root / f"{stage_name}.done"
        had_marker = marker.exists()

        if not checkpoint.should_run(stage_name, cfg_slice):
            # TEMPORARY DIAGNOSTIC INSTRUMENTATION — remove once
            # topic_label root cause is confirmed on a real run.
            _log.info(
                "topic_label_debug_stage_skipped",
                stage=stage_name,
                reason="should_run_false_prior_rows_carried_through_unchanged",
            )
            parts.append(_prior(key))
            continue
        if had_marker and not marker.exists():
            checkpoint.invalidate(stage_name)

        bind_context(analyst_key=key, stage=stage_name)
        try:
            texts = group["text_clean"].tolist()
            embeddings = _load_embedding_matrix(group["embedding_path"].tolist())
            result = _fit_or_load(
                runner_factory, model_loader, checkpoint, fingerprint, texts, embeddings,
            )
            rows = _rows_from_result(comment_ids, result, "within_analyst")
            parts.append(rows)
            checkpoint.mark_done(
                stage_name, cfg_slice, extras={"n_topics": len(set(result.topic_ids))},
            )
            _log.info("topics_within_analyst_done", analyst_key=key, n_rows=len(rows))
        finally:
            clear_context()

    non_empty = [p for p in parts if not p.empty]
    return pd.concat(non_empty, ignore_index=True) if non_empty else _empty_index()


def _process_pooled(
    joined: pd.DataFrame,
    *,
    cfg: TopicsConfig,
    checkpoint: CheckpointManager,
    stage_seed: int,
    runner_factory: RunnerFactory,
    model_loader: Callable[[Path], Any],
    existing_df: pd.DataFrame | None,
) -> pd.DataFrame:
    if joined.empty:
        return _empty_index()

    def _prior() -> pd.DataFrame:
        if existing_df is not None and "configuration" in existing_df.columns:
            rows = existing_df.loc[existing_df["configuration"] == "pooled"]
            if not rows.empty:
                return rows
        return _empty_index()

    comment_ids = joined["comment_id"].tolist()
    fingerprint = _model_fingerprint(
        comment_ids,
        joined["embedding_model_name"].iloc[0],
        joined["embedding_revision"].iloc[0],
        cfg, "pooled", stage_seed,
    )
    cfg_slice = _stage_cfg_slice(fingerprint, cfg.reduce_outliers, cfg.merge_similarity_threshold)
    stage_name = _STAGE_NAME_POOLED
    marker = checkpoint.checkpoint_root / f"{stage_name}.done"
    had_marker = marker.exists()

    if not checkpoint.should_run(stage_name, cfg_slice):
        # TEMPORARY DIAGNOSTIC INSTRUMENTATION — remove once topic_label
        # root cause is confirmed on a real run. If this fires, the
        # Tier-2 checkpoint considers the stage already complete for the
        # current config_slice and _fit_or_load/_rows_from_result are
        # NEVER called this run — rows are carried through unchanged
        # from the existing (possibly pre-patch) topics.parquet.
        _log.info(
            "topic_label_debug_stage_skipped",
            stage=stage_name,
            reason="should_run_false_prior_rows_carried_through_unchanged",
        )
        return _prior()
    if had_marker and not marker.exists():
        checkpoint.invalidate(stage_name)

    bind_context(stage=stage_name)
    try:
        texts = joined["text_clean"].tolist()
        embeddings = _load_embedding_matrix(joined["embedding_path"].tolist())
        result = _fit_or_load(
            runner_factory, model_loader, checkpoint, fingerprint, texts, embeddings,
        )
        rows = _rows_from_result(comment_ids, result, "pooled")
        checkpoint.mark_done(
            stage_name, cfg_slice, extras={"n_topics": len(set(result.topic_ids))},
        )
        _log.info("topics_pooled_done", n_rows=len(rows))
        return rows
    finally:
        clear_context()


def run_topics(
    settings: Settings,
    comments_path: Path | str,
    embeddings_index_path: Path | str,
    checkpoint: CheckpointManager,
    *,
    output_path: Path | str | None = None,
    analyst_key: str | None = None,
    runner_factory: RunnerFactory | None = None,
    model_loader: Callable[[Path], Any] | None = None,
) -> pd.DataFrame:
    """Fill ``topics.parquet`` from comments + their cached embeddings.

    Parameters
    ----------
    settings
        Validated settings; uses ``settings.topics`` and ``settings.study.root_seed``.
    comments_path
        Source ``comments.parquet`` (must have ``text_clean`` populated).
    embeddings_index_path
        ``embeddings_index.parquet`` from :mod:`finfluencer.embeddings.pipeline`.
    checkpoint
        Shared :class:`CheckpointManager`.
    output_path
        Destination. Defaults to ``data/processed/topics.parquet``.
    analyst_key
        If given, only that analyst's ``within_analyst`` model is
        (re)processed; ``pooled`` is skipped for this call (its existing
        rows, if any, are carried through unchanged) since pooled is not
        analyst-scoped by definition.
    runner_factory
        Override for constructing :class:`BERTopicRunner` (tests inject
        a fake). Defaults to ``BERTopicRunner(settings.topics, stage_seed, model=model)``.
    model_loader
        Override for loading a cached model from a path (tests inject a
        fake). Defaults to :meth:`BERTopicRunner.load_model`.
    """
    comments_path = Path(comments_path)
    embeddings_index_path = Path(embeddings_index_path)
    output_path = Path(output_path) if output_path is not None else _DEFAULT_OUTPUT

    comments_df = read_parquet(comments_path)
    embeddings_df = read_parquet(embeddings_index_path)

    if (
        comments_df.empty or embeddings_df.empty
        or "text_clean" not in comments_df.columns
        or "comment_id" not in embeddings_df.columns
    ):
        _log.warning("topics_no_input_available")
        empty = _empty_index()
        write_parquet(empty, output_path)
        return empty

    joined = comments_df[["comment_id", "analyst_key", "text_clean"]].merge(
        embeddings_df.rename(
            columns={"model_name": "embedding_model_name", "revision": "embedding_revision"},
        )[["comment_id", "embedding_path", "embedding_model_name", "embedding_revision"]],
        on="comment_id", how="inner",
    )
    if joined.empty:
        _log.warning("topics_no_matching_embeddings")
        empty = _empty_index()
        write_parquet(empty, output_path)
        return empty

    cfg = settings.topics
    stage_seed = derive_seed(settings.study.root_seed, "topics")

    if runner_factory is None:
        def runner_factory(model: Any | None = None) -> BERTopicRunner:
            return BERTopicRunner(cfg, stage_seed, model=model)

    if model_loader is None:
        model_loader = BERTopicRunner.load_model

    existing_df: pd.DataFrame | None = None
    if output_path.exists():
        try:
            existing_df = read_parquet(output_path)
        except Exception:  # noqa: BLE001
            existing_df = None

    parts: list[pd.DataFrame] = []

    if cfg.configurations.within_analyst:
        parts.append(_process_within_analyst(
            joined, cfg=cfg, checkpoint=checkpoint, stage_seed=stage_seed,
            analyst_key_filter=analyst_key, runner_factory=runner_factory,
            model_loader=model_loader, existing_df=existing_df,
        ))

    if cfg.configurations.pooled and analyst_key is None:
        parts.append(_process_pooled(
            joined, cfg=cfg, checkpoint=checkpoint, stage_seed=stage_seed,
            runner_factory=runner_factory, model_loader=model_loader,
            existing_df=existing_df,
        ))
    elif cfg.configurations.pooled and existing_df is not None and "configuration" in existing_df.columns:
        prior_pooled = existing_df.loc[existing_df["configuration"] == "pooled"]
        if not prior_pooled.empty:
            parts.append(prior_pooled)

    non_empty = [p for p in parts if not p.empty]
    result_df = pd.concat(non_empty, ignore_index=True) if non_empty else _empty_index()
    write_parquet(result_df, output_path)
    _log.info("topics_stage_summary", n_rows_out=len(result_df))
    return result_df


# =============================================================================
# Phase 2.5: temporal topic evolution (read-only view over the cached model)
# =============================================================================


def _empty_evolution_index() -> pd.DataFrame:
    return pd.DataFrame(columns=_EVOLUTION_INDEX_COLUMNS)


def _parse_bin_words(words: Any) -> list[str]:
    """BERTopic's ``Words`` column is a comma-joined string; normalize
    to a list. Already-list values (e.g. from injected test doubles)
    pass through unchanged."""
    if isinstance(words, list):
        return words
    if not words:
        return []
    return [w.strip() for w in str(words).split(",") if w.strip()]


def run_topic_evolution(
    settings: Settings,
    comments_path: Path | str,
    embeddings_index_path: Path | str,
    topics_path: Path | str,
    checkpoint: CheckpointManager,
    *,
    configuration: str = "pooled",
    analyst_key: str | None = None,
    nr_bins: int = 10,
    output_path: Path | str | None = None,
    model_loader: Callable[[Path], Any] | None = None,
) -> pd.DataFrame:
    """Fill ``topic_evolution.parquet`` from an already-cached BERTopic model.

    Requires the ``topics`` stage to have already run for the requested
    ``(configuration[, analyst_key])`` — this function never fits a
    model, only loads the cached one (Tier-3, ``kind="topics_model"``)
    and asks it for a time-binned view via
    :func:`finfluencer.topics.bertopic_runner.topics_over_time`.

    Parameters
    ----------
    settings
        Validated settings; uses ``settings.topics`` and
        ``settings.study.root_seed`` — must match the topics stage's
        own fingerprint inputs exactly, or the cache lookup misses.
    comments_path
        Source ``comments.parquet`` (``text_clean`` + ``posted_date``).
    embeddings_index_path
        ``embeddings_index.parquet`` — needed to reproduce the same
        model fingerprint the topics stage used.
    topics_path
        ``topics.parquet`` — source of this run's ``topic_id``
        assignments (post outlier-reduction/merge) and ``topic_label``.
    checkpoint
        Shared :class:`CheckpointManager` (read-only here — used only
        to resolve the Tier-3 model cache path).
    configuration
        ``"pooled"`` or ``"within_analyst"``.
    analyst_key
        Required when ``configuration="within_analyst"``.
    nr_bins
        Number of time bins (BERTopic's own binning). Not a
        reproducibility-critical seed — deterministic given fixed
        data, so it is a plain function argument, not a settings.yaml
        field.
    output_path
        Destination. Defaults to ``data/processed/topic_evolution.parquet``.
    model_loader
        Override for loading a cached model from a path (tests inject
        a fake). Defaults to :meth:`BERTopicRunner.load_model`.

    Raises
    ------
    ValueError
        Invalid ``configuration``, or ``within_analyst`` without ``analyst_key``.
    FileNotFoundError
        If no cached model exists for the computed fingerprint (i.e.
        the ``topics`` stage hasn't run for this exact configuration).
    """
    if configuration not in ("pooled", "within_analyst"):
        raise ValueError(
            f'configuration must be "pooled" or "within_analyst", got {configuration!r}',
        )
    if configuration == "within_analyst" and analyst_key is None:
        raise ValueError('analyst_key is required when configuration="within_analyst"')

    comments_path = Path(comments_path)
    embeddings_index_path = Path(embeddings_index_path)
    topics_path = Path(topics_path)
    output_path = Path(output_path) if output_path is not None else _DEFAULT_EVOLUTION_OUTPUT

    comments_df = read_parquet(comments_path)
    embeddings_df = read_parquet(embeddings_index_path)
    topics_df = read_parquet(topics_path)

    if (
        comments_df.empty or topics_df.empty
        or "topic_id" not in topics_df.columns
        or "posted_date" not in comments_df.columns
    ):
        _log.warning("topic_evolution_no_input_available")
        empty = _empty_evolution_index()
        write_parquet(empty, output_path)
        return empty

    scoped_topics = topics_df.loc[topics_df["configuration"] == configuration]
    if configuration == "within_analyst":
        analyst_ids = set(
            comments_df.loc[comments_df["analyst_key"] == analyst_key, "comment_id"].tolist(),
        )
        scoped_topics = scoped_topics.loc[scoped_topics["comment_id"].isin(analyst_ids)]

    if scoped_topics.empty:
        _log.warning(
            "topic_evolution_no_matching_topics",
            configuration=configuration, analyst_key=analyst_key,
        )
        empty = _empty_evolution_index()
        write_parquet(empty, output_path)
        return empty

    joined = scoped_topics.merge(
        comments_df[["comment_id", "text_clean", "posted_date"]],
        on="comment_id", how="inner",
    ).merge(
        embeddings_df.rename(
            columns={"model_name": "embedding_model_name", "revision": "embedding_revision"},
        )[["comment_id", "embedding_model_name", "embedding_revision"]],
        on="comment_id", how="inner",
    )
    if joined.empty:
        _log.warning("topic_evolution_no_matching_rows")
        empty = _empty_evolution_index()
        write_parquet(empty, output_path)
        return empty

    cfg = settings.topics
    stage_seed = derive_seed(settings.study.root_seed, "topics")
    comment_ids = joined["comment_id"].tolist()
    fingerprint = _model_fingerprint(
        comment_ids,
        joined["embedding_model_name"].iloc[0],
        joined["embedding_revision"].iloc[0],
        cfg, configuration, stage_seed,
    )

    if not checkpoint.cache_has(_MODEL_CACHE_KIND, fingerprint, ".pkl"):
        raise FileNotFoundError(
            f"No cached BERTopic model found for configuration={configuration!r} "
            f"analyst_key={analyst_key!r} (fingerprint={fingerprint}); "
            f"run --stage topics first.",
        )

    if model_loader is None:
        model_loader = BERTopicRunner.load_model
    model_path = checkpoint.cache_path(_MODEL_CACHE_KIND, fingerprint, ".pkl")
    model = model_loader(model_path)

    docs = joined["text_clean"].tolist()
    topic_ids = joined["topic_id"].tolist()
    timestamps = joined["posted_date"].tolist()
    topic_label_by_id = dict(zip(joined["topic_id"], joined["topic_label"]))

    raw = _bertopic_topics_over_time(model, docs, topic_ids, timestamps, nr_bins)

    records = [
        {
            "configuration": configuration,
            "analyst_key": analyst_key if configuration == "within_analyst" else None,
            "topic_id": int(row["Topic"]),
            "topic_label": topic_label_by_id.get(int(row["Topic"])),
            "time_bin": str(row["Timestamp"]),
            "frequency": int(row["Frequency"]),
            "bin_words": _parse_bin_words(row["Words"]),
        }
        for _, row in raw.iterrows()
    ]
    result_df = (
        pd.DataFrame.from_records(records, columns=_EVOLUTION_INDEX_COLUMNS)
        if records else _empty_evolution_index()
    )
    write_parquet(result_df, output_path)
    _log.info("topic_evolution_stage_summary", n_rows_out=len(result_df))
    return result_df


__all__ = ["run_topics", "run_topic_evolution"]
