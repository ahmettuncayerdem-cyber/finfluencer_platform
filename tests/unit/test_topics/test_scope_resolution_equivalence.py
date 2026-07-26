"""Deterministic comparison test: old (configuration-string) vs. new
(scope_id-based) comment-set resolution, required before Migration Step
3.3 switches ``run_topic_evolution()``'s production call site over.

Per the approval gate for this preparatory step: the old resolution
mechanism (:func:`finfluencer.topics.pipeline._resolve_scoped_topics_via_configuration`)
remains in production use and is not removed. The new mechanism
(:func:`finfluencer.topics.pipeline._resolve_scoped_topics_via_scope`) is
added but not yet wired into ``run_topic_evolution()``. This file proves
the two mechanisms select the identical comment set - not merely the
same row count - for every scope currently reachable
(``pooled``/``within_analyst`` x each analyst), using two genuinely
independent derivations (one reads ``topics_df["configuration"]``, the
other never does), plus one deliberately-constructed negative case
proving the comparison would actually catch a real divergence rather
than passing vacuously.
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
from finfluencer.topics.pipeline import (
    _resolve_scoped_topics_via_configuration,
    _resolve_scoped_topics_via_scope,
    run_topics,
)
from finfluencer.utils.io import write_parquet

_DIM = 4

# Four analysts, uneven group sizes, mirrors the real platform's shape
# more closely than a two-analyst fixture would.
_CORPUS_ROWS = [
    ("satiroglu", "c1", "harika bir gelisme"),
    ("satiroglu", "c2", "kotu bir haber"),
    ("satiroglu", "c3", "notr yorum"),
    ("gecer", "c4", "cok iyi gitti"),
    ("gecer", "c5", "faiz artisi bekleniyor"),
    ("basaran", "c6", "piyasa dustu"),
    ("basaran", "c7", "altin yukseliyor"),
    ("basaran", "c8", "dolar sabit kaldi"),
    ("yesilada", "c9", "hisse senedi arttii"),
]


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


class _FakeRunner:
    def __init__(self, model, fit_calls: list, transform_calls: list) -> None:
        self.model = model
        self._fit_calls = fit_calls
        self._transform_calls = transform_calls

    def fit_transform(self, texts, embeddings) -> TopicFitResult:
        self._fit_calls.append(len(texts))
        n = len(texts)
        return TopicFitResult(topic_ids=[i % 2 for i in range(n)], topic_probs=[0.9] * n, model="FITTED")

    def transform(self, texts, embeddings) -> TopicFitResult:
        self._transform_calls.append(len(texts))
        n = len(texts)
        return TopicFitResult(topic_ids=[i % 2 for i in range(n)], topic_probs=[0.9] * n, model=self.model)

    def save(self, path: Path) -> None:
        Path(path).write_bytes(b"fake-model")


def _make_runner_factory():
    fit_calls: list = []
    transform_calls: list = []
    def factory(model=None) -> _FakeRunner:
        return _FakeRunner(model=model, fit_calls=fit_calls, transform_calls=transform_calls)
    return factory


def _fake_model_loader(path: Path):
    return "LOADED"


def _write_embedding(tmp_path: Path, comment_id: str) -> str:
    vec_path = tmp_path / "vectors" / f"{comment_id}.npy"
    vec_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(vec_path, np.random.default_rng(abs(hash(comment_id)) % (2**32)).random(_DIM))
    return str(vec_path)


def _write_corpus(tmp_path: Path) -> tuple[Path, Path, pd.DataFrame, pd.DataFrame]:
    comments_df = pd.DataFrame([
        dict(analyst_key=a, comment_id=cid, text_clean=t) for a, cid, t in _CORPUS_ROWS
    ])
    embeddings_df = pd.DataFrame([
        dict(
            comment_id=cid, embedding_path=_write_embedding(tmp_path, cid),
            model_name="emb-model", revision="main", dimension=_DIM,
        )
        for _, cid, _ in _CORPUS_ROWS
    ])
    comments_path = tmp_path / "comments.parquet"
    embeddings_path = tmp_path / "embeddings_index.parquet"
    write_parquet(comments_df, comments_path)
    write_parquet(embeddings_df, embeddings_path)
    return comments_path, embeddings_path, comments_df, embeddings_df


@pytest.fixture
def resolved_topics(tmp_path: Path):
    """Runs the real (Step 3.2) run_topics() to get a topics_df with
    both `configuration` and `scope_id` genuinely populated the same
    way production does it - not a hand-built fixture."""
    comments_path, embeddings_path, comments_df, embeddings_df = _write_corpus(tmp_path)
    checkpoint = CheckpointManager(tmp_path / "checkpoints", tmp_path / "cache")
    cfg = _topics_config()
    settings = _fake_settings(cfg)
    topics_df = run_topics(
        settings, comments_path, embeddings_path, checkpoint,
        output_path=tmp_path / "topics.parquet",
        runner_factory=_make_runner_factory(),
        model_loader=_fake_model_loader,
    )
    return topics_df, comments_df, embeddings_df


class TestOldVsNewResolutionEquivalence:
    @pytest.mark.parametrize(
        "configuration,analyst_key",
        [
            ("pooled", None),
            ("within_analyst", "satiroglu"),
            ("within_analyst", "gecer"),
            ("within_analyst", "basaran"),
            ("within_analyst", "yesilada"),
        ],
    )
    def test_identical_comment_id_sets(self, resolved_topics, configuration, analyst_key):
        topics_df, comments_df, embeddings_df = resolved_topics

        old = _resolve_scoped_topics_via_configuration(
            topics_df, comments_df, configuration, analyst_key,
        )
        new = _resolve_scoped_topics_via_scope(
            topics_df, comments_df, embeddings_df, configuration, analyst_key,
        )

        old_ids = set(old["comment_id"])
        new_ids = set(new["comment_id"])

        assert old_ids, "fixture produced an empty old-path result - test would pass vacuously"
        assert old_ids == new_ids, (
            f"resolution mismatch for configuration={configuration!r} analyst_key={analyst_key!r}: "
            f"old-only={old_ids - new_ids}, new-only={new_ids - old_ids}"
        )
        # Not just the same IDs - the same number of rows (guards against
        # a hypothetical dup in one path masked by set() dedup).
        assert len(old) == len(new) == len(old_ids)

    def test_all_scopes_partition_full_corpus_identically(self, resolved_topics):
        """Union of all within_analyst scopes, resolved via each
        mechanism independently, must equal the same full comment set
        (and must equal the pooled scope's set) - a partition-level
        cross-check, not just per-scope."""
        topics_df, comments_df, embeddings_df = resolved_topics
        all_analysts = sorted(comments_df["analyst_key"].unique())

        old_union: set[str] = set()
        new_union: set[str] = set()
        for key in all_analysts:
            old_union |= set(
                _resolve_scoped_topics_via_configuration(
                    topics_df, comments_df, "within_analyst", key,
                )["comment_id"],
            )
            new_union |= set(
                _resolve_scoped_topics_via_scope(
                    topics_df, comments_df, embeddings_df, "within_analyst", key,
                )["comment_id"],
            )

        pooled_old = set(
            _resolve_scoped_topics_via_configuration(topics_df, comments_df, "pooled", None)["comment_id"],
        )
        pooled_new = set(
            _resolve_scoped_topics_via_scope(
                topics_df, comments_df, embeddings_df, "pooled", None,
            )["comment_id"],
        )

        assert old_union == new_union == pooled_old == pooled_new


class TestComparisonCatchesRealDivergence:
    """Negative control: prove the equivalence test above is actually
    sensitive to a real mismatch, not structurally guaranteed to pass.
    Without this, a bug that made the two mechanisms silently agree by
    construction (rather than by genuine equivalence) could hide behind
    a green test suite."""

    def test_corrupted_scope_id_column_is_detected(self, resolved_topics):
        topics_df, comments_df, embeddings_df = resolved_topics

        corrupted = topics_df.copy()
        # Poison every within_analyst row's scope_id so it can no longer
        # match any freshly-resolved AnalysisScope.
        mask = corrupted["configuration"] == "within_analyst"
        corrupted.loc[mask, "scope_id"] = "deliberately-wrong-scope-id"

        old = _resolve_scoped_topics_via_configuration(
            corrupted, comments_df, "within_analyst", "satiroglu",
        )
        new = _resolve_scoped_topics_via_scope(
            corrupted, comments_df, embeddings_df, "within_analyst", "satiroglu",
        )

        assert set(old["comment_id"])  # old path still finds rows via configuration
        assert set(new["comment_id"]) == set()  # new path finds nothing - divergence caught
        assert set(old["comment_id"]) != set(new["comment_id"])
