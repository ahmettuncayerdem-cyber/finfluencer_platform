"""Tests for `RealTopicsAnalysisEngine` (Release Blocker #6,
`docs/implementation/RB6_ANALYSIS_DISPATCH_READINESS_REVIEW.md` sections 5.2/5.3).

Tests the *composition/sequencing* this class adds -- preprocess -> embeddings -> a fresh
`TopicsAnalysisAdapter` per call -- not the internals of any of the three pieces it composes,
each of which already has its own dedicated test suite. `preprocess_engine`/`embeddings_engine`
are faked here (duck-typed, recording call order) so these tests isolate the composition logic;
`runner_factory`/`model_loader` reuse `test_topics_adapter.py`'s own established fake pattern for
the same reason that file fakes them (no `bertopic`/`torch` required to run these tests).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.contracts import (
    HDBSCANConfig,
    ModelReference,
    TopicConfigurations,
    TopicsConfig,
    UMAPConfig,
)
from finfluencer.domain.analysis_engine import AnalysisOutcome
from finfluencer.infrastructure.analysis import EmbeddingsOutcome, RealTopicsAnalysisEngine
from finfluencer.topics.bertopic_runner import TopicFitResult
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
        configurations=TopicConfigurations(within_analyst=False, pooled=True),
        merge_similarity_threshold=1.0,
        reduce_outliers=False,
        quality_metrics=[],
    )


def _fake_settings() -> Any:
    return SimpleNamespace(topics=_topics_config(), study=SimpleNamespace(root_seed=1))


class _FakeRunner:
    """Same deterministic behaviour `test_topics_adapter.py` already establishes."""

    def __init__(self, model: Any, calls: list) -> None:
        self.model = model
        self._calls = calls

    def fit_transform(self, texts: list[str], embeddings: np.ndarray) -> TopicFitResult:
        self._calls.append(len(texts))
        n = len(texts)
        return TopicFitResult(
            topic_ids=[i % 2 for i in range(n)], topic_probs=[0.9] * n, model="FITTED_SENTINEL",
        )

    def transform(self, texts: list[str], embeddings: np.ndarray) -> TopicFitResult:
        n = len(texts)
        return TopicFitResult(
            topic_ids=[i % 2 for i in range(n)], topic_probs=[0.9] * n, model=self.model,
        )

    def save(self, path: Path) -> None:
        Path(path).write_bytes(b"fake-model")


def _make_runner_factory(calls: list):
    def factory(model: Any = None) -> _FakeRunner:
        return _FakeRunner(model=model, calls=calls)
    return factory


def _fake_model_loader(path: Path) -> str:
    return "LOADED_SENTINEL"


class _FakePreprocessEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def ensure_clean(self, collection_run_id: str) -> SimpleNamespace:
        self.calls.append(collection_run_id)
        return SimpleNamespace(comments_path=None, row_count=0)


class _FakeEmbeddingsEngine:
    """Records call order and returns a caller-supplied `EmbeddingsOutcome` per
    `collection_run_id` -- lets tests prove `RealTopicsAnalysisEngine` uses the *right* path for
    the *right* run, not a stale one from a previous call (the exact bug this class exists to
    avoid, per `TopicsAnalysisAdapter`'s own fixed-`embeddings_index_path` finding).
    """

    def __init__(self, index_paths: dict[str, Path]) -> None:
        self.calls: list[str] = []
        self._index_paths = index_paths

    def ensure_index(self, collection_run_id: str) -> EmbeddingsOutcome:
        self.calls.append(collection_run_id)
        return EmbeddingsOutcome(index_path=self._index_paths[collection_run_id], row_count=0)


def _write_embedding(tmp_path: Path, tag: str, comment_id: str) -> str:
    vec_path = tmp_path / "vectors" / tag / f"{comment_id}.npy"
    vec_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(vec_path, np.random.default_rng(abs(hash((tag, comment_id))) % (2**32)).random(_DIM))
    return str(vec_path)


def _write_fixture(tmp_path: Path, base_root: Path, collection_run_id: str, tag: str) -> Path:
    rows = [
        ("satiroglu", "c1", "harika bir gelisme"),
        ("satiroglu", "c2", "kotu bir haber"),
        ("gecer", "c3", "notr bir yorum"),
        ("gecer", "c4", "cok iyi gitti"),
    ]
    comments_df = pd.DataFrame(
        [dict(analyst_key=a, comment_id=cid, text_clean=t) for a, cid, t in rows],
    )
    comments_path = base_root / collection_run_id / "data_raw" / "comments.parquet"
    comments_path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(comments_df, comments_path)

    embeddings_df = pd.DataFrame(
        [
            dict(
                comment_id=cid,
                embedding_path=_write_embedding(tmp_path, tag, cid),
                model_name="emb-model", revision="main", dimension=_DIM,
            )
            for _, cid, _ in rows
        ],
    )
    embeddings_path = tmp_path / f"embeddings_index_{tag}.parquet"
    write_parquet(embeddings_df, embeddings_path)
    return embeddings_path


def test_run_sequences_preprocess_then_embeddings_then_topics(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    embeddings_path = _write_fixture(tmp_path, base_root, "cr-1", "a")

    preprocess = _FakePreprocessEngine()
    embeddings = _FakeEmbeddingsEngine({"cr-1": embeddings_path})
    calls: list = []
    engine = RealTopicsAnalysisEngine(
        settings=_fake_settings(),
        base_root=base_root,
        preprocess_engine=preprocess,
        embeddings_engine=embeddings,
        runner_factory=_make_runner_factory(calls),
        model_loader=_fake_model_loader,
    )

    outcome = engine.run(analysis_run_id="ar-1", collection_run_id="cr-1")

    assert isinstance(outcome, AnalysisOutcome)
    assert outcome.row_count == 4
    assert outcome.topic_count == 2
    assert preprocess.calls == ["cr-1"]
    assert embeddings.calls == ["cr-1"]
    assert calls == [4]  # topics runner actually invoked, over all 4 rows


def test_two_collection_runs_each_use_their_own_embeddings_index(tmp_path: Path) -> None:
    """Proves the fixed-`embeddings_index_path` finding is actually closed: two different
    `collection_run_id`s, same engine instance, each must resolve its own embeddings index --
    not the first one's, stale, reused for the second.
    """
    base_root = tmp_path / "runs"
    path_a = _write_fixture(tmp_path, base_root, "cr-a", "a")
    path_b = _write_fixture(tmp_path, base_root, "cr-b", "b")
    assert path_a != path_b

    preprocess = _FakePreprocessEngine()
    embeddings = _FakeEmbeddingsEngine({"cr-a": path_a, "cr-b": path_b})
    engine = RealTopicsAnalysisEngine(
        settings=_fake_settings(),
        base_root=base_root,
        preprocess_engine=preprocess,
        embeddings_engine=embeddings,
        runner_factory=_make_runner_factory([]),
        model_loader=_fake_model_loader,
    )

    outcome_a = engine.run(analysis_run_id="ar-a", collection_run_id="cr-a")
    outcome_b = engine.run(analysis_run_id="ar-b", collection_run_id="cr-b")

    assert outcome_a.row_count == 4
    assert outcome_b.row_count == 4
    assert preprocess.calls == ["cr-a", "cr-b"]
    assert embeddings.calls == ["cr-a", "cr-b"]


def test_run_rejects_empty_analysis_run_id(tmp_path: Path) -> None:
    engine = RealTopicsAnalysisEngine(
        settings=_fake_settings(), base_root=tmp_path,
        preprocess_engine=_FakePreprocessEngine(),
        embeddings_engine=_FakeEmbeddingsEngine({}),
    )
    with pytest.raises(ValueError):
        engine.run(analysis_run_id="", collection_run_id="cr-1")


def test_run_rejects_empty_collection_run_id(tmp_path: Path) -> None:
    engine = RealTopicsAnalysisEngine(
        settings=_fake_settings(), base_root=tmp_path,
        preprocess_engine=_FakePreprocessEngine(),
        embeddings_engine=_FakeEmbeddingsEngine({}),
    )
    with pytest.raises(ValueError):
        engine.run(analysis_run_id="ar-1", collection_run_id="")


def test_default_constituent_engines_are_real_when_not_injected(tmp_path: Path) -> None:
    """Proves the default-construction seam is real: omitting `preprocess_engine`/
    `embeddings_engine` must build the real `PreprocessEngineAdapter`/`EmbeddingsEngineAdapter`,
    not silently do nothing."""
    from finfluencer.infrastructure.analysis import EmbeddingsEngineAdapter, PreprocessEngineAdapter

    engine = RealTopicsAnalysisEngine(settings=_fake_settings(), base_root=tmp_path)
    assert isinstance(engine._preprocess_engine, PreprocessEngineAdapter)
    assert isinstance(engine._embeddings_engine, EmbeddingsEngineAdapter)


def test_module_does_not_import_presentation_or_api() -> None:
    import finfluencer.infrastructure.analysis.real_topics_engine as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)
