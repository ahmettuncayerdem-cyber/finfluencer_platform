"""Tests for :func:`finfluencer.topics.pipeline.run_topic_evolution`."""

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
from finfluencer.topics.pipeline import run_topic_evolution
from finfluencer.utils.io import write_parquet

_DIM = 4


def _topics_config() -> TopicsConfig:
    return TopicsConfig(
        embedding_model=ModelReference(name="emb-model", revision="main"),
        umap=UMAPConfig(n_neighbors=2, n_components=2, min_dist=0.0, metric="cosine"),
        hdbscan=HDBSCANConfig(
            min_cluster_size=2, min_samples=1, metric="euclidean",
            cluster_selection_method="eom",
        ),
        configurations=TopicConfigurations(within_analyst=True, pooled=True),
        merge_similarity_threshold=1.0,
        reduce_outliers=False,
        quality_metrics=[],
    )


def _fake_settings(cfg: TopicsConfig, root_seed: int = 1):
    return SimpleNamespace(topics=cfg, study=SimpleNamespace(root_seed=root_seed))


class _FakeModelWithTopicsOverTime:
    def __init__(self, result_df: pd.DataFrame):
        self._result_df = result_df
        self.calls: list[tuple] = []

    def topics_over_time(self, docs, timestamps, topics, nr_bins):
        self.calls.append((docs, timestamps, topics, nr_bins))
        return self._result_df


def _write_embedding(tmp_path: Path, comment_id: str) -> str:
    vec_path = tmp_path / "vectors" / f"{comment_id}.npy"
    vec_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(vec_path, np.random.default_rng(abs(hash(comment_id)) % (2**32)).random(_DIM))
    return str(vec_path)


def _write_corpus(tmp_path: Path) -> tuple[Path, Path, Path]:
    rows = [
        ("satiroglu", "c1", "yorum bir", "2024-01-01"),
        ("satiroglu", "c2", "yorum iki", "2024-02-01"),
        ("gecer", "c3", "yorum uc", "2024-01-15"),
    ]
    comments_df = pd.DataFrame([
        dict(analyst_key=a, comment_id=cid, text_clean=t, posted_date=d)
        for a, cid, t, d in rows
    ])
    embeddings_df = pd.DataFrame([
        dict(
            comment_id=cid,
            embedding_path=_write_embedding(tmp_path, cid),
            model_name="emb-model", revision="main", dimension=_DIM,
        )
        for _, cid, _, _ in rows
    ])

    # scope_id populated the same way _resolve_and_persist_group_scope
    # (Step 3.2) computes it for a live run_topics() call, and the same
    # way Step 3.2.5 backfilled it onto real topics.parquet - required
    # for _resolve_scoped_topics_via_scope() (Step 3.3) to have a
    # scope_id to match against. Mirrors test_step3_3_regression.py's
    # _write_corpus(), which already does this.
    from finfluencer.core.contracts import AnalysisScopeType
    from finfluencer.scope import resolve_scope

    pooled_scope = resolve_scope(
        ["c1", "c2", "c3"], scope_type=AnalysisScopeType.global_,
        criteria_version="v1_topics_pipeline",
    )
    satiroglu_scope = resolve_scope(
        ["c1", "c2"], scope_type=AnalysisScopeType.entity, entity_keys=["satiroglu"],
        criteria_version="v1_topics_pipeline",
    )
    gecer_scope = resolve_scope(
        ["c3"], scope_type=AnalysisScopeType.entity, entity_keys=["gecer"],
        criteria_version="v1_topics_pipeline",
    )

    topics_df = pd.DataFrame([
        dict(comment_id="c1", topic_id=0, topic_prob=0.9, topic_tier=None,
             configuration="pooled", scope_id=pooled_scope.scope_id, topic_label="0_altin"),
        dict(comment_id="c2", topic_id=0, topic_prob=0.8, topic_tier=None,
             configuration="pooled", scope_id=pooled_scope.scope_id, topic_label="0_altin"),
        dict(comment_id="c3", topic_id=1, topic_prob=0.7, topic_tier=None,
             configuration="pooled", scope_id=pooled_scope.scope_id, topic_label="1_borsa"),
        dict(comment_id="c1", topic_id=0, topic_prob=0.9, topic_tier=None,
             configuration="within_analyst", scope_id=satiroglu_scope.scope_id, topic_label="0_within"),
        dict(comment_id="c2", topic_id=0, topic_prob=0.8, topic_tier=None,
             configuration="within_analyst", scope_id=satiroglu_scope.scope_id, topic_label="0_within"),
        dict(comment_id="c3", topic_id=1, topic_prob=0.7, topic_tier=None,
             configuration="within_analyst", scope_id=gecer_scope.scope_id, topic_label="1_within"),
    ])

    comments_path = tmp_path / "comments.parquet"
    embeddings_path = tmp_path / "embeddings_index.parquet"
    topics_path = tmp_path / "topics.parquet"
    write_parquet(comments_df, comments_path)
    write_parquet(embeddings_df, embeddings_path)
    write_parquet(topics_df, topics_path)
    return comments_path, embeddings_path, topics_path


_BERTOPIC_RESULT = pd.DataFrame([
    {"Topic": 0, "Words": "altin, ons, gram", "Frequency": 2, "Timestamp": "2024-01-15"},
    {"Topic": 1, "Words": "borsa, faiz", "Frequency": 1, "Timestamp": "2024-01-15"},
])


class TestRunTopicEvolution:
    def test_invalid_configuration_raises(self, tmp_checkpoint_root, tmp_cache_root, tmp_path):
        comments_path, embeddings_path, topics_path = _write_corpus(tmp_path)
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        with pytest.raises(ValueError):
            run_topic_evolution(
                _fake_settings(_topics_config()), comments_path, embeddings_path, topics_path,
                checkpoint, configuration="bogus",
                output_path=tmp_path / "topic_evolution.parquet",
            )

    def test_within_analyst_without_analyst_key_raises(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path,
    ):
        comments_path, embeddings_path, topics_path = _write_corpus(tmp_path)
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        with pytest.raises(ValueError):
            run_topic_evolution(
                _fake_settings(_topics_config()), comments_path, embeddings_path, topics_path,
                checkpoint, configuration="within_analyst",
                output_path=tmp_path / "topic_evolution.parquet",
            )

    def test_missing_cached_model_raises_file_not_found(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path,
    ):
        comments_path, embeddings_path, topics_path = _write_corpus(tmp_path)
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        with pytest.raises(FileNotFoundError):
            run_topic_evolution(
                _fake_settings(_topics_config()), comments_path, embeddings_path, topics_path,
                checkpoint, configuration="pooled",
                output_path=tmp_path / "topic_evolution.parquet",
            )

    def test_pooled_evolution_with_cached_model(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path,
    ):
        comments_path, embeddings_path, topics_path = _write_corpus(tmp_path)
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        cfg = _topics_config()
        settings = _fake_settings(cfg)

        # Pre-seed the Tier-3 model cache exactly as run_topics would.
        from finfluencer.topics.pipeline import _model_fingerprint
        from finfluencer.core.reproducibility import derive_seed

        stage_seed = derive_seed(settings.study.root_seed, "topics")
        fingerprint = _model_fingerprint(
            ["c1", "c2", "c3"], "emb-model", "main", cfg, "pooled", stage_seed,
        )
        model_path = checkpoint.cache_path("topics_model", fingerprint, ".pkl")
        model_path.write_bytes(b"fake-cached-model")

        fake_model = _FakeModelWithTopicsOverTime(_BERTOPIC_RESULT)

        result = run_topic_evolution(
            settings, comments_path, embeddings_path, topics_path, checkpoint,
            configuration="pooled", nr_bins=3,
            model_loader=lambda path: fake_model,
            output_path=tmp_path / "topic_evolution.parquet",
        )

        assert len(result) == 2
        assert set(result["topic_id"]) == {0, 1}
        row0 = result.loc[result["topic_id"] == 0].iloc[0]
        assert row0["topic_label"] == "0_altin"
        assert row0["frequency"] == 2
        assert row0["bin_words"] == ["altin", "ons", "gram"]
        assert (result["analyst_key"].isna()).all()

        # nr_bins propagated through to the model call.
        assert fake_model.calls[0][3] == 3

    def test_within_analyst_evolution_scopes_to_analyst(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path,
    ):
        comments_path, embeddings_path, topics_path = _write_corpus(tmp_path)
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        cfg = _topics_config()
        settings = _fake_settings(cfg)

        from finfluencer.topics.pipeline import _model_fingerprint
        from finfluencer.core.reproducibility import derive_seed

        stage_seed = derive_seed(settings.study.root_seed, "topics")
        fingerprint = _model_fingerprint(
            ["c1", "c2"], "emb-model", "main", cfg, "within_analyst", stage_seed,
        )
        model_path = checkpoint.cache_path("topics_model", fingerprint, ".pkl")
        model_path.write_bytes(b"fake-cached-model")

        fake_model = _FakeModelWithTopicsOverTime(
            pd.DataFrame([
                {"Topic": 0, "Words": "altin, ons", "Frequency": 2, "Timestamp": "2024-01-15"},
            ]),
        )

        result = run_topic_evolution(
            settings, comments_path, embeddings_path, topics_path, checkpoint,
            configuration="within_analyst", analyst_key="satiroglu",
            model_loader=lambda path: fake_model,
            output_path=tmp_path / "topic_evolution.parquet",
        )

        assert len(result) == 1
        assert result.iloc[0]["analyst_key"] == "satiroglu"
        assert result.iloc[0]["topic_label"] == "0_within"
        # Only satiroglu's 2 comments should have been passed as docs.
        docs_passed = fake_model.calls[0][0]
        assert len(docs_passed) == 2

    def test_empty_topics_is_handled(self, tmp_checkpoint_root, tmp_cache_root, tmp_path):
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        comments_path = tmp_path / "comments.parquet"
        embeddings_path = tmp_path / "embeddings_index.parquet"
        topics_path = tmp_path / "topics.parquet"
        write_parquet(pd.DataFrame(), comments_path)
        write_parquet(pd.DataFrame(), embeddings_path)
        write_parquet(pd.DataFrame(), topics_path)

        result = run_topic_evolution(
            _fake_settings(_topics_config()), comments_path, embeddings_path, topics_path,
            checkpoint, configuration="pooled",
            output_path=tmp_path / "topic_evolution.parquet",
        )
        assert result.empty
