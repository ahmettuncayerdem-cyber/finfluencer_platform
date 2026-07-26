"""Tests for :mod:`finfluencer.topics.bertopic_runner`.

A fake internal BERTopic model is injected via ``model=`` so these
tests never touch the network or require ``bertopic``/``umap-learn``/
``hdbscan`` to be installed.
"""

from __future__ import annotations

import numpy as np
import pytest

from finfluencer.core.contracts import (
    HDBSCANConfig,
    ModelReference,
    TopicConfigurations,
    TopicsConfig,
    UMAPConfig,
)
from finfluencer.topics.bertopic_runner import (
    BERTopicRunner,
    _cosine_similarity,
    _merge_similar_topics,
    _normalize_probs,
    topics_over_time,
)


def _make_cfg(*, reduce_outliers: bool = False, merge_similarity_threshold: float = 1.0) -> TopicsConfig:
    return TopicsConfig(
        embedding_model=ModelReference(name="m", revision="r"),
        umap=UMAPConfig(n_neighbors=5, n_components=2, min_dist=0.0, metric="cosine"),
        hdbscan=HDBSCANConfig(
            min_cluster_size=2, min_samples=1, metric="euclidean",
            cluster_selection_method="eom",
        ),
        configurations=TopicConfigurations(within_analyst=True, pooled=True),
        merge_similarity_threshold=merge_similarity_threshold,
        reduce_outliers=reduce_outliers,
        quality_metrics=[],
    )


class _FakeBERTopicModel:
    def __init__(self, topics, probs=None, reduce_outliers_return=None, reduce_outliers_raises=False):
        self._topics = topics
        self._probs = probs
        self._reduce_outliers_return = reduce_outliers_return
        self._reduce_outliers_raises = reduce_outliers_raises
        self.save_calls: list[tuple] = []
        self.fit_transform_calls: list[tuple] = []
        self.transform_calls: list[tuple] = []
        self.reduce_outliers_calls: list[tuple] = []

    def fit_transform(self, texts, embeddings):
        self.fit_transform_calls.append((texts, embeddings))
        return self._topics, self._probs

    def transform(self, texts, embeddings):
        self.transform_calls.append((texts, embeddings))
        return self._topics, self._probs

    def reduce_outliers(self, texts, topics, strategy):
        self.reduce_outliers_calls.append((texts, topics, strategy))
        if self._reduce_outliers_raises:
            raise RuntimeError("boom")
        return self._reduce_outliers_return

    def save(self, path, serialization):
        self.save_calls.append((path, serialization))


class TestHelpers:
    def test_cosine_similarity_identical_vectors(self):
        v = np.array([1.0, 2.0, 3.0])
        assert _cosine_similarity(v, v) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal_vectors(self):
        assert _cosine_similarity(np.array([1.0, 0.0]), np.array([0.0, 1.0])) == pytest.approx(0.0)

    def test_cosine_similarity_zero_vector(self):
        assert _cosine_similarity(np.zeros(3), np.array([1.0, 2.0, 3.0])) == 0.0

    def test_normalize_probs_none(self):
        assert _normalize_probs(None, 3) == [0.0, 0.0, 0.0]

    def test_normalize_probs_1d(self):
        assert _normalize_probs(np.array([0.1, 0.9]), 2) == pytest.approx([0.1, 0.9])

    def test_normalize_probs_2d_takes_max(self):
        arr = np.array([[0.1, 0.7, 0.2], [0.9, 0.05, 0.05]])
        assert _normalize_probs(arr, 2) == pytest.approx([0.7, 0.9])

    def test_merge_identical_centroids_merges_into_smaller_id(self):
        topics = [0, 0, 1, 1]
        embeddings = np.ones((4, 3))  # identical vectors -> identical centroids
        merged = _merge_similar_topics(topics, embeddings, threshold=0.99)
        assert merged == [0, 0, 0, 0]

    def test_merge_threshold_ge_one_is_off_switch(self):
        """threshold >= 1.0 is the documented 'disabled' convention, even
        if actual cosine similarity is exactly 1.0."""
        topics = [0, 0, 1, 1]
        embeddings = np.ones((4, 3))
        merged = _merge_similar_topics(topics, embeddings, threshold=1.0)
        assert merged == [0, 0, 1, 1]

    def test_merge_dissimilar_topics_not_merged(self):
        topics = [0, 0, 1, 1]
        embeddings = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])
        merged = _merge_similar_topics(topics, embeddings, threshold=0.9)
        assert merged == [0, 0, 1, 1]

    def test_merge_preserves_outliers(self):
        topics = [-1, 0, 0, 1, 1]
        embeddings = np.ones((5, 3))
        merged = _merge_similar_topics(topics, embeddings, threshold=0.5)
        assert merged[0] == -1


class TestBERTopicRunner:
    def test_fit_transform_pass_through(self):
        model = _FakeBERTopicModel(topics=[0, 1, 0], probs=np.array([0.8, 0.7, 0.6]))
        runner = BERTopicRunner(_make_cfg(), seed=42, model=model)
        result = runner.fit_transform(["a", "b", "c"], np.zeros((3, 4)))
        assert result.topic_ids == [0, 1, 0]
        assert result.topic_probs == pytest.approx([0.8, 0.7, 0.6])
        assert len(model.fit_transform_calls) == 1

    def test_transform_pass_through(self):
        model = _FakeBERTopicModel(topics=[1, 1], probs=np.array([0.5, 0.5]))
        runner = BERTopicRunner(_make_cfg(), seed=42, model=model)
        result = runner.transform(["x", "y"], np.zeros((2, 4)))
        assert result.topic_ids == [1, 1]
        assert len(model.transform_calls) == 1

    def test_reduce_outliers_applied_when_outliers_present(self):
        model = _FakeBERTopicModel(
            topics=[-1, 0, 0], probs=np.array([0.0, 0.9, 0.8]),
            reduce_outliers_return=[0, 0, 0],
        )
        runner = BERTopicRunner(_make_cfg(reduce_outliers=True), seed=1, model=model)
        result = runner.fit_transform(["a", "b", "c"], np.ones((3, 2)))
        assert result.topic_ids == [0, 0, 0]
        assert len(model.reduce_outliers_calls) == 1

    def test_reduce_outliers_skipped_when_disabled(self):
        model = _FakeBERTopicModel(topics=[-1, 0], probs=np.array([0.0, 0.9]))
        runner = BERTopicRunner(_make_cfg(reduce_outliers=False), seed=1, model=model)
        result = runner.fit_transform(["a", "b"], np.ones((2, 2)))
        assert result.topic_ids == [-1, 0]
        assert model.reduce_outliers_calls == []

    def test_reduce_outliers_failure_is_handled_gracefully(self):
        model = _FakeBERTopicModel(
            topics=[-1, 0], probs=np.array([0.0, 0.9]), reduce_outliers_raises=True,
        )
        runner = BERTopicRunner(_make_cfg(reduce_outliers=True), seed=1, model=model)
        result = runner.fit_transform(["a", "b"], np.ones((2, 2)))
        # Falls back to original topics rather than raising.
        assert result.topic_ids == [-1, 0]

    def test_save_delegates_to_model(self, tmp_path):
        model = _FakeBERTopicModel(topics=[0], probs=np.array([1.0]))
        runner = BERTopicRunner(_make_cfg(), seed=1, model=model)
        target = tmp_path / "model.pkl"
        runner.save(target)
        assert model.save_calls == [(str(target), "pickle")]

    def test_load_model_requires_bertopic(self, tmp_path):
        pytest.importorskip("bertopic")
        with pytest.raises(Exception):  # noqa: B017 - path doesn't exist
            BERTopicRunner.load_model(tmp_path / "nonexistent.pkl")


class _FakeModelWithTopicsOverTime:
    def __init__(self, result):
        self._result = result
        self.calls: list[tuple] = []

    def topics_over_time(self, docs, timestamps, topics, nr_bins):
        self.calls.append((docs, timestamps, topics, nr_bins))
        return self._result


class TestTopicsOverTime:
    def test_passes_through_explicit_topics_and_returns_model_result(self):
        sentinel_result = object()
        model = _FakeModelWithTopicsOverTime(sentinel_result)
        result = topics_over_time(
            model, ["a", "b"], [0, 1], ["2024-01-01", "2024-01-02"], nr_bins=5,
        )
        assert result is sentinel_result
        assert model.calls == [(["a", "b"], ["2024-01-01", "2024-01-02"], [0, 1], 5)]
