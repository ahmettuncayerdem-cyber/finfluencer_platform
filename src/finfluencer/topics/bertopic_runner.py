"""
finfluencer.topics.bertopic_runner
=====================================

Thin, dependency-injectable wrapper around UMAP + HDBSCAN + BERTopic.

Heavy ML dependencies (``bertopic``, ``umap-learn``, ``hdbscan``) are
imported lazily — only when a real (non-injected) model is constructed
— so importing this module never requires them. Tests inject a fake
``model=`` exposing ``fit_transform``/``transform``/``save``.

Determinism
------------
UMAP is stochastic (spectral initialisation + SGD); its ``random_state``
is fixed to a caller-supplied seed (derived from ``root_seed`` by the
pipeline). HDBSCAN itself has no random component — it is deterministic
given a fixed input — so reproducibility follows from UMAP's fixed
output being fed to HDBSCAN unchanged. No HDBSCAN "seed" exists or is
invented here.

Topic merging
-------------
``merge_similarity_threshold`` is applied via a version-independent,
self-contained union-find over *centroid embeddings computed from the
input embedding matrix* (mean of a topic's member vectors) — not
BERTopic's internal ``topic_embeddings_``, which varies across library
versions. Merging always folds a topic into the *smaller* topic_id, so
the result is deterministic and independent of processing order.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from finfluencer.core.contracts import TopicsConfig
from finfluencer.core.logging import get_logger

_log = get_logger(__name__)


@dataclass
class TopicFitResult:
    """Output of a fit/transform pass, before or after post-processing."""

    topic_ids: list[int]
    topic_probs: list[float]
    model: Any


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _topic_centroids(topics: list[int], embeddings: np.ndarray) -> dict[int, np.ndarray]:
    unique_ids = sorted({t for t in topics if t != -1})
    topics_arr = np.asarray(topics)
    return {
        tid: embeddings[topics_arr == tid].mean(axis=0)
        for tid in unique_ids
    }


def _merge_similar_topics(
    topics: list[int], embeddings: np.ndarray, threshold: float,
) -> list[int]:
    """Union-find merge of topics whose centroid cosine similarity >= threshold.

    Deterministic: always merges into the smaller topic_id, regardless
    of iteration order. A ``threshold >= 1.0`` is a no-op (exact-only
    match, effectively disabled — the common "off" convention).
    """
    if threshold >= 1.0:
        return topics
    centroids = _topic_centroids(topics, embeddings)
    ids_list = sorted(centroids.keys())
    if len(ids_list) < 2:
        return topics

    parent: dict[int, int] = {tid: tid for tid in ids_list}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for i in range(len(ids_list)):
        for j in range(i + 1, len(ids_list)):
            a, b = ids_list[i], ids_list[j]
            if _cosine_similarity(centroids[a], centroids[b]) >= threshold:
                union(a, b)

    return [find(t) if t != -1 else -1 for t in topics]


def _normalize_probs(probs: Any, n: int) -> list[float]:
    """Coerce BERTopic's ``probs`` output (None, 1D, or 2D) to a flat
    per-document scalar list — the assigned topic's confidence, matching
    the existing ``TopicRecord.topic_prob: float`` schema (not the full
    per-topic distribution)."""
    if probs is None:
        return [0.0] * n
    arr = np.asarray(probs)
    if arr.ndim == 1:
        return [float(p) for p in arr]
    return [float(row.max()) if row.size else 0.0 for row in arr]


class BERTopicRunner:
    """Fits (or applies) BERTopic with injected/deterministic UMAP+HDBSCAN.

    Two entry points mirror the cache-first pipeline's two paths:
    :meth:`fit_transform` (cache miss — full fit) and :meth:`transform`
    (cache hit — apply an already-fitted, loaded model). Both apply the
    same ``reduce_outliers``/topic-merge post-processing, so changing
    those two config knobs never requires a UMAP/HDBSCAN refit.
    """

    def __init__(
        self,
        cfg: TopicsConfig,
        seed: int,
        *,
        model: Any | None = None,
    ) -> None:
        self.cfg = cfg
        self.seed = seed

        if model is not None:
            self._model = model
        else:
            from bertopic import BERTopic
            from hdbscan import HDBSCAN
            from umap import UMAP

            umap_model = UMAP(
                n_neighbors=cfg.umap.n_neighbors,
                n_components=cfg.umap.n_components,
                min_dist=cfg.umap.min_dist,
                metric=cfg.umap.metric,
                low_memory=cfg.umap.low_memory,
                random_state=seed,
            )
            hdbscan_model = HDBSCAN(
                min_cluster_size=cfg.hdbscan.min_cluster_size,
                min_samples=cfg.hdbscan.min_samples,
                metric=cfg.hdbscan.metric,
                cluster_selection_method=cfg.hdbscan.cluster_selection_method,
                prediction_data=True,
            )
            self._model = BERTopic(
                umap_model=umap_model,
                hdbscan_model=hdbscan_model,
                calculate_probabilities=False,
            )

    def _postprocess(
        self, texts: list[str], embeddings: np.ndarray, topics: list[int], probs: list[float],
    ) -> TopicFitResult:
        if self.cfg.reduce_outliers and -1 in topics:
            try:
                topics = list(self._model.reduce_outliers(texts, topics, strategy="c-tf-idf"))
            except Exception as exc:  # noqa: BLE001
                _log.warning("reduce_outliers_failed", reason=str(exc))

        topics = _merge_similar_topics(topics, embeddings, self.cfg.merge_similarity_threshold)
        return TopicFitResult(topic_ids=topics, topic_probs=probs, model=self._model)

    def fit_transform(self, texts: list[str], embeddings: np.ndarray) -> TopicFitResult:
        """Full fit (cache miss). Expensive — UMAP + HDBSCAN over the corpus."""
        topics, probs = self._model.fit_transform(texts, embeddings=embeddings)
        topics = list(topics)
        probs = _normalize_probs(probs, len(topics))
        return self._postprocess(texts, embeddings, topics, probs)

    def transform(self, texts: list[str], embeddings: np.ndarray) -> TopicFitResult:
        """Apply an already-fitted (e.g. cache-loaded) model. Cheap, deterministic."""
        topics, probs = self._model.transform(texts, embeddings=embeddings)
        topics = list(topics)
        probs = _normalize_probs(probs, len(topics))
        return self._postprocess(texts, embeddings, topics, probs)

    def save(self, path: Path | str) -> None:
        self._model.save(str(path), serialization="pickle")

    @staticmethod
    def load_model(path: Path | str) -> Any:
        from bertopic import BERTopic

        return BERTopic.load(str(path))


def topics_over_time(
    model: Any,
    docs: list[str],
    topics: list[int],
    timestamps: list[str],
    nr_bins: int,
) -> Any:
    """Thin wrapper around BERTopic's own ``topics_over_time()`` (Phase 2.5).

    ``topics`` is passed explicitly so that post-fit reassignments
    already applied by this runner (outlier-reduction, similarity
    merging — see :meth:`BERTopicRunner._postprocess`) are respected,
    rather than the model's raw ``self.topics_`` from the original fit.

    Returns BERTopic's own result frame unchanged (columns ``Topic``,
    ``Words``, ``Frequency``, ``Timestamp``); shaping into
    :class:`~finfluencer.core.contracts.TopicEvolutionRecord` rows
    happens in :mod:`finfluencer.topics.pipeline`.
    """
    return model.topics_over_time(docs, timestamps, topics=topics, nr_bins=nr_bins)


__all__ = ["BERTopicRunner", "TopicFitResult", "topics_over_time"]
