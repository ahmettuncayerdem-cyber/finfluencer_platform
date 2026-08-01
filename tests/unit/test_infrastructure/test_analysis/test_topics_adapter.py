"""Tests for `TopicsAnalysisAdapter` (BACKLOG.md T-019).

Same injection technique already established in `tests/unit/test_topics/test_pipeline.py`: a fake
`runner_factory`/`model_loader` stands in for `BERTopicRunner`/BERTopic itself, so these tests
never require `bertopic`/`umap-learn`/`hdbscan` to be installed -- confirmed consistent with the
pre-existing `test_topics` suite (49 passed, 1 skipped, no heavy ML deps installed in this
sandbox).
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
from finfluencer.infrastructure.analysis import TopicsAnalysisAdapter
from finfluencer.topics.bertopic_runner import TopicFitResult
from finfluencer.utils.io import read_parquet, write_parquet

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


def _fake_settings(cfg: TopicsConfig, root_seed: int = 1) -> Any:
    return SimpleNamespace(topics=cfg, study=SimpleNamespace(root_seed=root_seed))


class _FakeRunner:
    """Deterministic, known topic assignment: alternates topic 0/1 by row index -- the
    "fixture dataset with known expected topics" T-019's own Verification line requires."""

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


def _write_embedding(tmp_path: Path, comment_id: str) -> str:
    vec_path = tmp_path / "vectors" / f"{comment_id}.npy"
    vec_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(vec_path, np.random.default_rng(abs(hash(comment_id)) % (2**32)).random(_DIM))
    return str(vec_path)


def _write_fixture_dataset(
    tmp_path: Path, *, base_root: Path, collection_run_id: str,
) -> Path:
    """Writes comments.parquet at the T-010-convention path this adapter resolves
    (`base_root/collection_run_id/data_raw/comments.parquet`) and a standalone
    embeddings_index.parquet (caller-supplied, per this adapter's own Context Pack). Returns
    the embeddings_index_path.
    """
    rows = [
        ("satiroglu", "c1", "harika bir gelisme"),
        ("satiroglu", "c2", "kotu bir haber"),
        ("gecer", "c3", "notr bir yorum"),
        ("gecer", "c4", "cok iyi gitti"),
    ]
    comments_df = pd.DataFrame(
        [dict(analyst_key=a, comment_id=cid, text_clean=t) for a, cid, t in rows],
    )
    embeddings_df = pd.DataFrame(
        [
            dict(
                comment_id=cid,
                embedding_path=_write_embedding(tmp_path, cid),
                model_name="emb-model", revision="main", dimension=_DIM,
            )
            for _, cid, _ in rows
        ],
    )
    comments_path = base_root / collection_run_id / "data_raw" / "comments.parquet"
    comments_path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(comments_df, comments_path)

    embeddings_path = tmp_path / "embeddings_index.parquet"
    write_parquet(embeddings_df, embeddings_path)
    return embeddings_path


def test_adapter_produces_known_expected_topics(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    collection_run_id = "cr-fixture-1"
    embeddings_path = _write_fixture_dataset(
        tmp_path, base_root=base_root, collection_run_id=collection_run_id,
    )

    calls: list = []
    adapter = TopicsAnalysisAdapter(
        settings=_fake_settings(_topics_config()),
        base_root=base_root,
        embeddings_index_path=embeddings_path,
        runner_factory=_make_runner_factory(calls),
        model_loader=_fake_model_loader,
    )

    outcome = adapter.run(analysis_run_id="ar-1", collection_run_id=collection_run_id)

    assert isinstance(outcome, AnalysisOutcome)
    assert outcome.analysis_run_id == "ar-1"
    assert outcome.row_count == 4
    assert outcome.topic_count == 2  # _FakeRunner alternates topic 0/1 -- known, deterministic
    assert calls == [4]  # exactly one fit_transform call, over all 4 rows (pooled only)

    topics_path = base_root / "ar-1" / "data_processed" / "topics.parquet"
    topics_df = read_parquet(topics_path)
    assert sorted(topics_df["topic_id"].tolist()) == [0, 0, 1, 1]


def test_adapter_isolates_checkpoint_and_cache_per_analysis_run_id(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    collection_run_id = "cr-fixture-2"
    embeddings_path = _write_fixture_dataset(
        tmp_path, base_root=base_root, collection_run_id=collection_run_id,
    )
    adapter = TopicsAnalysisAdapter(
        settings=_fake_settings(_topics_config()),
        base_root=base_root,
        embeddings_index_path=embeddings_path,
        runner_factory=_make_runner_factory([]),
        model_loader=_fake_model_loader,
    )

    adapter.run(analysis_run_id="ar-a", collection_run_id=collection_run_id)
    adapter.run(analysis_run_id="ar-b", collection_run_id=collection_run_id)

    assert (base_root / "ar-a" / "checkpoints").exists()
    assert (base_root / "ar-b" / "checkpoints").exists()
    # Two distinct analysis_run_ids never share a checkpoint/cache root.
    assert (base_root / "ar-a" / "checkpoints") != (base_root / "ar-b" / "checkpoints")
    assert (base_root / "ar-a" / "data_processed" / "topics.parquet").exists()
    assert (base_root / "ar-b" / "data_processed" / "topics.parquet").exists()


def test_run_rejects_empty_analysis_run_id(tmp_path: Path) -> None:
    adapter = TopicsAnalysisAdapter(
        settings=_fake_settings(_topics_config()),
        base_root=tmp_path,
        embeddings_index_path=tmp_path / "embeddings_index.parquet",
    )
    with pytest.raises(ValueError):
        adapter.run(analysis_run_id="", collection_run_id="cr-1")


def test_run_rejects_empty_collection_run_id(tmp_path: Path) -> None:
    adapter = TopicsAnalysisAdapter(
        settings=_fake_settings(_topics_config()),
        base_root=tmp_path,
        embeddings_index_path=tmp_path / "embeddings_index.parquet",
    )
    with pytest.raises(ValueError):
        adapter.run(analysis_run_id="ar-1", collection_run_id="")


def test_adapter_module_does_not_import_presentation_or_api() -> None:
    # PRODUCT_ARCHITECTURE.md section 12.1: Infrastructure's forbidden dependencies include
    # Presentation and API -- same ast-based check T-010's own adapter test uses.
    import finfluencer.infrastructure.analysis.topics_adapter as module

    tree = ast.parse(inspect.getsource(module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(m.startswith("finfluencer.presentation") for m in imported_modules)
    assert not any(m.startswith("finfluencer.api") for m in imported_modules)


def test_adapter_never_modifies_wrapped_legacy_modules() -> None:
    import finfluencer.infrastructure.analysis.topics_adapter as module

    source = inspect.getsource(module)
    for forbidden in ("setattr(", "monkeypatch", "importlib.reload"):
        assert forbidden not in source
