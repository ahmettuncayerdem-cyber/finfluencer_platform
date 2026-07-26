"""Tests for :mod:`finfluencer.topics.pipeline`.

A fake runner factory + fake model loader stand in for BERTopicRunner /
BERTopic itself, so these tests never require ``bertopic``/``umap-learn``/
``hdbscan`` to be installed.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.core.contracts import (
    HDBSCANConfig,
    ModelReference,
    TopicConfigurations,
    TopicsConfig,
    UMAPConfig,
)
from finfluencer.topics.bertopic_runner import TopicFitResult
from finfluencer.topics.pipeline import _rows_from_result, run_topics
from finfluencer.utils.io import write_parquet

_DIM = 4


def _topics_config(
    *, within_analyst: bool = True, pooled: bool = True,
    reduce_outliers: bool = False, merge_similarity_threshold: float = 1.0,
) -> TopicsConfig:
    return TopicsConfig(
        embedding_model=ModelReference(name="emb-model", revision="main"),
        umap=UMAPConfig(n_neighbors=2, n_components=2, min_dist=0.0, metric="cosine"),
        hdbscan=HDBSCANConfig(
            min_cluster_size=2, min_samples=1, metric="euclidean",
            cluster_selection_method="eom",
        ),
        configurations=TopicConfigurations(within_analyst=within_analyst, pooled=pooled),
        merge_similarity_threshold=merge_similarity_threshold,
        reduce_outliers=reduce_outliers,
        quality_metrics=[],
    )


def _fake_settings(cfg: TopicsConfig, root_seed: int = 1):
    return SimpleNamespace(topics=cfg, study=SimpleNamespace(root_seed=root_seed))


class _FakeRunner:
    """Duck-typed stand-in for BERTopicRunner. Deterministic alternating
    topic assignment; records fit/transform call counts on shared lists
    so tests can assert cache-hit vs cache-miss behaviour."""

    def __init__(self, model, fit_calls: list, transform_calls: list) -> None:
        self.model = model
        self._fit_calls = fit_calls
        self._transform_calls = transform_calls

    def fit_transform(self, texts: list[str], embeddings: np.ndarray) -> TopicFitResult:
        self._fit_calls.append(len(texts))
        n = len(texts)
        return TopicFitResult(
            topic_ids=[i % 2 for i in range(n)],
            topic_probs=[0.9] * n,
            model="FITTED_SENTINEL",
        )

    def transform(self, texts: list[str], embeddings: np.ndarray) -> TopicFitResult:
        self._transform_calls.append(len(texts))
        n = len(texts)
        return TopicFitResult(
            topic_ids=[i % 2 for i in range(n)],
            topic_probs=[0.9] * n,
            model=self.model,
        )

    def save(self, path: Path) -> None:
        Path(path).write_bytes(b"fake-model")


def _make_runner_factory(fit_calls: list, transform_calls: list):
    def factory(model=None) -> _FakeRunner:
        return _FakeRunner(model=model, fit_calls=fit_calls, transform_calls=transform_calls)
    return factory


def _fake_model_loader(path: Path):
    return "LOADED_SENTINEL"


def _write_embedding(tmp_path: Path, comment_id: str) -> str:
    vec_path = tmp_path / "vectors" / f"{comment_id}.npy"
    vec_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(vec_path, np.random.default_rng(abs(hash(comment_id)) % (2**32)).random(_DIM))
    return str(vec_path)


def _write_corpus(tmp_path: Path) -> tuple[Path, Path]:
    rows = [
        ("satiroglu", "c1", "harika bir gelisme"),
        ("satiroglu", "c2", "kotu bir haber"),
        ("gecer", "c3", "notr bir yorum"),
        ("gecer", "c4", "cok iyi gitti"),
    ]
    comments_df = pd.DataFrame([
        dict(analyst_key=a, comment_id=cid, text_clean=t) for a, cid, t in rows
    ])
    embeddings_df = pd.DataFrame([
        dict(
            comment_id=cid,
            embedding_path=_write_embedding(tmp_path, cid),
            model_name="emb-model", revision="main", dimension=_DIM,
        )
        for _, cid, _ in rows
    ])
    comments_path = tmp_path / "comments.parquet"
    embeddings_path = tmp_path / "embeddings_index.parquet"
    write_parquet(comments_df, comments_path)
    write_parquet(embeddings_df, embeddings_path)
    return comments_path, embeddings_path


class _FakeModelWithTopicInfo:
    """Minimal fake exposing BERTopic's ``get_topic_info()`` shape
    (columns ``Topic``/``Name``), for testing ``_rows_from_result``'s
    topic_label lookup without a real BERTopic model."""

    def __init__(self, info: dict) -> None:
        self._info = info

    def get_topic_info(self) -> pd.DataFrame:
        return pd.DataFrame({
            "Topic": list(self._info.keys()),
            "Name": list(self._info.values()),
        })


class TestRowsFromResultTopicLabel:
    def test_topic_label_propagated_from_model_get_topic_info(self):
        model = _FakeModelWithTopicInfo({
            -1: "-1_outlier_misc",
            0: "0_altin_gm_ons_mi",
            1: "1_video_videosu_videolar_youtube",
        })
        result = TopicFitResult(
            topic_ids=[0, 1, -1, 0], topic_probs=[0.9, 0.8, 0.0, 0.7], model=model,
        )
        rows = _rows_from_result(["a", "b", "c", "d"], result, "pooled", "scope-test-1")
        labels = dict(zip(rows["comment_id"], rows["topic_label"]))
        assert labels == {
            "a": "0_altin_gm_ons_mi",
            "b": "1_video_videosu_videolar_youtube",
            "c": "-1_outlier_misc",
            "d": "0_altin_gm_ons_mi",
        }
        # Migration Step 3.2: scope_id is now populated on every row from
        # the caller-supplied value - see finfluencer.scope.resolve_scope.
        assert (rows["scope_id"] == "scope-test-1").all()

    def test_topic_label_falls_back_to_none_when_model_lacks_get_topic_info(self):
        result = TopicFitResult(topic_ids=[0, 1], topic_probs=[0.5, 0.5], model="SENTINEL")
        rows = _rows_from_result(["a", "b"], result, "pooled", "scope-test-2")
        assert rows["topic_label"].isna().all()

    def test_topic_label_none_for_topic_id_missing_from_model_info(self):
        model = _FakeModelWithTopicInfo({0: "0_foo_bar"})
        result = TopicFitResult(topic_ids=[0, 5], topic_probs=[0.5, 0.5], model=model)
        rows = _rows_from_result(["a", "b"], result, "pooled", "scope-test-3")
        labels = dict(zip(rows["comment_id"], rows["topic_label"]))
        assert labels["a"] == "0_foo_bar"
        assert pd.isna(labels["b"])


class TestRunTopics:
    def test_pooled_and_within_analyst_both_produce_rows(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path,
    ):
        comments_path, embeddings_path = _write_corpus(tmp_path)
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        fit_calls, transform_calls = [], []

        result = run_topics(
            _fake_settings(_topics_config()), comments_path, embeddings_path, checkpoint,
            output_path=tmp_path / "topics.parquet",
            runner_factory=_make_runner_factory(fit_calls, transform_calls),
            model_loader=_fake_model_loader,
        )

        configs = set(result["configuration"])
        assert configs == {"within_analyst", "pooled"}
        assert set(result.loc[result["configuration"] == "pooled", "comment_id"]) == {
            "c1", "c2", "c3", "c4",
        }
        assert result["topic_tier"].isna().all()
        assert result["topic_label"].isna().all()

    def test_cache_hit_uses_transform_not_fit(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path,
    ):
        comments_path, embeddings_path = _write_corpus(tmp_path)
        cfg = _topics_config()
        fit_calls, transform_calls = [], []

        checkpoint1 = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        run_topics(
            _fake_settings(cfg), comments_path, embeddings_path, checkpoint1,
            output_path=tmp_path / "t1.parquet",
            runner_factory=_make_runner_factory(fit_calls, transform_calls),
            model_loader=_fake_model_loader,
        )
        assert len(fit_calls) > 0
        assert len(transform_calls) == 0

        # Fresh Tier-2 checkpoint (new stage markers) but SAME cache_root:
        # model cache should hit -> transform, not fit.
        fit_calls2, transform_calls2 = [], []
        checkpoint2 = CheckpointManager(tmp_checkpoint_root / "other", tmp_cache_root)
        run_topics(
            _fake_settings(cfg), comments_path, embeddings_path, checkpoint2,
            output_path=tmp_path / "t2.parquet",
            runner_factory=_make_runner_factory(fit_calls2, transform_calls2),
            model_loader=_fake_model_loader,
        )
        assert fit_calls2 == []
        assert len(transform_calls2) > 0

    def test_checkpoint_skip_avoids_any_refit_or_transform(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path,
    ):
        comments_path, embeddings_path = _write_corpus(tmp_path)
        cfg = _topics_config()
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        settings = _fake_settings(cfg)
        out_path = tmp_path / "topics.parquet"

        fit_calls, transform_calls = [], []
        first = run_topics(
            settings, comments_path, embeddings_path, checkpoint,
            output_path=out_path,
            runner_factory=_make_runner_factory(fit_calls, transform_calls),
            model_loader=_fake_model_loader,
        )

        fit_calls2, transform_calls2 = [], []
        second = run_topics(
            settings, comments_path, embeddings_path, checkpoint,
            output_path=out_path,
            runner_factory=_make_runner_factory(fit_calls2, transform_calls2),
            model_loader=_fake_model_loader,
        )
        assert fit_calls2 == []
        assert transform_calls2 == []  # same checkpoint -> should_run False -> _prior_rows
        assert set(zip(first["comment_id"], first["configuration"])) == \
            set(zip(second["comment_id"], second["configuration"]))

    def test_config_change_reprocesses_stage_but_still_hits_model_cache(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path,
    ):
        comments_path, embeddings_path = _write_corpus(tmp_path)
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        out_path = tmp_path / "topics.parquet"

        fit_calls, transform_calls = [], []
        run_topics(
            _fake_settings(_topics_config(reduce_outliers=False)),
            comments_path, embeddings_path, checkpoint,
            output_path=out_path,
            runner_factory=_make_runner_factory(fit_calls, transform_calls),
            model_loader=_fake_model_loader,
        )
        assert len(fit_calls) > 0

        # reduce_outliers flips -> Tier-2 stage config-slice changes ->
        # stage reprocesses, but fingerprint (model cache key) is
        # unaffected -> model cache still hits -> transform, not fit.
        fit_calls2, transform_calls2 = [], []
        run_topics(
            _fake_settings(_topics_config(reduce_outliers=True)),
            comments_path, embeddings_path, checkpoint,
            output_path=out_path,
            runner_factory=_make_runner_factory(fit_calls2, transform_calls2),
            model_loader=_fake_model_loader,
        )
        assert fit_calls2 == []
        assert len(transform_calls2) > 0

    def test_analyst_key_filter_skips_pooled_and_scopes_within_analyst(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path,
    ):
        comments_path, embeddings_path = _write_corpus(tmp_path)
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        fit_calls, transform_calls = [], []

        result = run_topics(
            _fake_settings(_topics_config()), comments_path, embeddings_path, checkpoint,
            output_path=tmp_path / "topics.parquet",
            analyst_key="satiroglu",
            runner_factory=_make_runner_factory(fit_calls, transform_calls),
            model_loader=_fake_model_loader,
        )
        assert set(result["configuration"]) == {"within_analyst"}
        assert set(result["comment_id"]) == {"c1", "c2"}

    def test_only_within_analyst_enabled(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path,
    ):
        comments_path, embeddings_path = _write_corpus(tmp_path)
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        fit_calls, transform_calls = [], []

        result = run_topics(
            _fake_settings(_topics_config(within_analyst=True, pooled=False)),
            comments_path, embeddings_path, checkpoint,
            output_path=tmp_path / "topics.parquet",
            runner_factory=_make_runner_factory(fit_calls, transform_calls),
            model_loader=_fake_model_loader,
        )
        assert set(result["configuration"]) == {"within_analyst"}

    def test_empty_comments_is_handled(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path,
    ):
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        comments_path = tmp_path / "comments.parquet"
        embeddings_path = tmp_path / "embeddings_index.parquet"
        write_parquet(pd.DataFrame(), comments_path)
        write_parquet(pd.DataFrame(), embeddings_path)

        result = run_topics(
            _fake_settings(_topics_config()), comments_path, embeddings_path, checkpoint,
            output_path=tmp_path / "topics.parquet",
            runner_factory=_make_runner_factory([], []),
            model_loader=_fake_model_loader,
        )
        assert result.empty

    def test_no_matching_embeddings_is_handled(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path,
    ):
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        comments_path = tmp_path / "comments.parquet"
        embeddings_path = tmp_path / "embeddings_index.parquet"
        write_parquet(
            pd.DataFrame([dict(analyst_key="a", comment_id="zzz", text_clean="x")]),
            comments_path,
        )
        write_parquet(
            pd.DataFrame(columns=["comment_id", "embedding_path", "model_name", "revision", "dimension"]),
            embeddings_path,
        )

        result = run_topics(
            _fake_settings(_topics_config()), comments_path, embeddings_path, checkpoint,
            output_path=tmp_path / "topics.parquet",
            runner_factory=_make_runner_factory([], []),
            model_loader=_fake_model_loader,
        )
        assert result.empty
