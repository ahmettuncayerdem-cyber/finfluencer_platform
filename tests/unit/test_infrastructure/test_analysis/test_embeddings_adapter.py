"""Tests for `EmbeddingsEngineAdapter` (Release Blocker #4, RELEASE_BLOCKING_ASSESSMENT.md item
#4). Same injection technique already established for `TopicsAnalysisAdapter`/
`SentimentAnalysisAdapter`: a fake `EmbeddingProvider` stands in for
`SentenceTransformerProvider`, so these tests never require `sentence_transformers`/`torch` to be
installed.
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

from finfluencer.core.contracts import ModelReference, TopicsConfig
from finfluencer.infrastructure.analysis import EmbeddingsEngineAdapter, EmbeddingsOutcome
from finfluencer.utils.io import read_parquet, write_parquet


class _FakeProvider:
    key = "fake"
    dim = 3

    def __init__(self) -> None:
        self.encode_calls: list[list[str]] = []

    def encode(self, texts: list[str]) -> np.ndarray:
        self.encode_calls.append(list(texts))
        return np.array([[float(len(t))] * self.dim for t in texts], dtype=np.float32)


def _minimal_topics_config() -> TopicsConfig:
    from finfluencer.core.contracts import HDBSCANConfig, TopicConfigurations, UMAPConfig

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


def _fake_settings(root_seed: int = 1) -> Any:
    return SimpleNamespace(topics=_minimal_topics_config(), study=SimpleNamespace(root_seed=root_seed))


def _write_comments(base_root: Path, collection_run_id: str, rows: list[tuple[str, str, str]]) -> None:
    comments_path = base_root / collection_run_id / "data_raw" / "comments.parquet"
    comments_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        [dict(analyst_key=a, comment_id=cid, text_clean=t) for a, cid, t in rows],
    )
    write_parquet(df, comments_path)


_ROWS = [
    ("satiroglu", "c1", "harika bir gelisme"),
    ("satiroglu", "c2", "kotu bir haber"),
    ("gecer", "c3", "notr bir yorum"),
]


def test_ensure_index_produces_a_real_embeddings_index_with_one_row_per_comment(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    _write_comments(base_root, "cr-1", _ROWS)

    adapter = EmbeddingsEngineAdapter(
        settings=_fake_settings(), base_root=base_root, provider=_FakeProvider(),
    )
    outcome = adapter.ensure_index("cr-1")

    assert isinstance(outcome, EmbeddingsOutcome)
    assert outcome.row_count == 3
    assert outcome.index_path == base_root / "cr-1" / "embeddings" / "embeddings_index.parquet"
    index_df = read_parquet(outcome.index_path)
    assert sorted(index_df["comment_id"].tolist()) == ["c1", "c2", "c3"]
    assert set(index_df["comment_id"]) == {"c1", "c2", "c3"}


def test_ensure_index_is_idempotent_and_reuses_the_cache(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    _write_comments(base_root, "cr-2", _ROWS)
    provider = _FakeProvider()
    adapter = EmbeddingsEngineAdapter(settings=_fake_settings(), base_root=base_root, provider=provider)

    adapter.ensure_index("cr-2")
    first_call_count = len(provider.encode_calls)
    adapter.ensure_index("cr-2")
    second_call_count = len(provider.encode_calls)

    # Every text already cached on the second call -- no new encode() calls issued.
    assert second_call_count == first_call_count


def test_two_collection_run_ids_never_share_an_output_path(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    _write_comments(base_root, "cr-a", _ROWS)
    _write_comments(base_root, "cr-b", _ROWS)
    adapter = EmbeddingsEngineAdapter(
        settings=_fake_settings(), base_root=base_root, provider=_FakeProvider(),
    )

    outcome_a = adapter.ensure_index("cr-a")
    outcome_b = adapter.ensure_index("cr-b")

    assert outcome_a.index_path != outcome_b.index_path
    assert outcome_a.index_path.exists()
    assert outcome_b.index_path.exists()


def test_ensure_index_rejects_empty_collection_run_id(tmp_path: Path) -> None:
    adapter = EmbeddingsEngineAdapter(
        settings=_fake_settings(), base_root=tmp_path, provider=_FakeProvider(),
    )
    with pytest.raises(ValueError):
        adapter.ensure_index("")


def test_default_provider_factory_is_never_invoked_when_a_provider_is_supplied(tmp_path: Path) -> None:
    """Proves the lazy-provider seam is real: supplying `provider=` directly must never touch
    `_default_provider_factory` (which would import `sentence_transformers`/`torch`)."""
    base_root = tmp_path / "runs"
    _write_comments(base_root, "cr-3", _ROWS)
    adapter = EmbeddingsEngineAdapter(
        settings=_fake_settings(), base_root=base_root, provider=_FakeProvider(),
    )

    def _boom() -> Any:
        raise AssertionError("default_provider_factory must not be called when provider= is set")

    adapter._provider_factory = _boom  # type: ignore[method-assign]
    adapter.ensure_index("cr-3")  # must not raise


def test_provider_factory_seam_is_used_when_no_provider_is_supplied(tmp_path: Path) -> None:
    base_root = tmp_path / "runs"
    _write_comments(base_root, "cr-4", _ROWS)
    fake = _FakeProvider()
    adapter = EmbeddingsEngineAdapter(
        settings=_fake_settings(), base_root=base_root, provider_factory=lambda: fake,
    )

    outcome = adapter.ensure_index("cr-4")

    assert outcome.row_count == 3
    assert fake.encode_calls  # the factory-produced provider was actually used


def test_adapter_module_does_not_import_presentation_or_api() -> None:
    import finfluencer.infrastructure.analysis.embeddings_adapter as module

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
    import finfluencer.infrastructure.analysis.embeddings_adapter as module

    source = inspect.getsource(module)
    for forbidden in ("setattr(", "monkeypatch", "importlib.reload"):
        assert forbidden not in source
