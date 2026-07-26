"""Tests for :mod:`finfluencer.embeddings.pipeline`."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from finfluencer.core.checkpoint import CheckpointManager
from finfluencer.embeddings.pipeline import run_embeddings
from finfluencer.utils.hashing import hash_string
from finfluencer.utils.io import write_parquet


def _fake_settings(root_seed: int = 42):
    return SimpleNamespace(study=SimpleNamespace(root_seed=root_seed))


class _FakeProvider:
    """Minimal EmbeddingProvider — no model_name/revision/device attrs,
    so pipeline metadata fallback is exercised too."""

    key = "fake"
    dim = 4

    def __init__(self) -> None:
        self.encode_calls: list[list[str]] = []

    def encode(self, texts: list[str]) -> np.ndarray:
        self.encode_calls.append(list(texts))
        return np.array([[float(len(t))] * self.dim for t in texts], dtype=np.float32)


def _row(analyst_key: str, comment_id: str, text_clean: str) -> dict:
    return dict(analyst_key=analyst_key, comment_id=comment_id, text_clean=text_clean)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame([
        _row("satiroglu", "c1", "cashtag_thyao percent_10 arttı"),
        _row("satiroglu", "c2", "cashtag_thyao percent_10 arttı"),  # duplicate text of c1
        _row("gecer", "c3", "money_try kar ettim"),
    ])


@pytest.fixture
def provider() -> _FakeProvider:
    return _FakeProvider()


class TestRunEmbeddings:
    def test_cache_miss_then_hit(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out1 = tmp_path / "idx1.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_embeddings(
            _fake_settings(), comments_path, checkpoint,
            provider=provider, output_path=out1,
        )
        assert set(result["comment_id"]) == {"c1", "c2", "c3"}
        n_encode_calls_first = sum(len(c) for c in provider.encode_calls)

        # Re-running with a fresh checkpoint stage (new analyst target) but
        # same cache_root must hit the cache: no new encode() calls.
        checkpoint2 = CheckpointManager(tmp_checkpoint_root / "other", tmp_cache_root)
        out2 = tmp_path / "idx2.parquet"
        provider.encode_calls.clear()
        run_embeddings(
            _fake_settings(), comments_path, checkpoint2,
            provider=provider, output_path=out2,
        )
        assert sum(len(c) for c in provider.encode_calls) == 0
        assert n_encode_calls_first > 0

    def test_duplicate_text_encoded_once(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out_path = tmp_path / "idx.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_embeddings(
            _fake_settings(), comments_path, checkpoint,
            provider=provider, output_path=out_path,
        )
        # c1 and c2 share identical text_clean -> same hash -> encoded once.
        c1_hash = result.loc[result["comment_id"] == "c1", "embedding_hash"].iloc[0]
        c2_hash = result.loc[result["comment_id"] == "c2", "embedding_hash"].iloc[0]
        assert c1_hash == c2_hash
        all_encoded_texts = [t for call in provider.encode_calls for t in call]
        assert all_encoded_texts.count("cashtag_thyao percent_10 arttı") == 1

    def test_analyst_isolation(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out_path = tmp_path / "idx.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_embeddings(
            _fake_settings(), comments_path, checkpoint,
            provider=provider, output_path=out_path, analyst_key="satiroglu",
        )
        assert set(result["comment_id"]) == {"c1", "c2"}
        assert "c3" not in set(result["comment_id"])

    def test_checkpoint_skip_no_reencode(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out_path = tmp_path / "idx.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)
        settings = _fake_settings()

        first = run_embeddings(
            settings, comments_path, checkpoint,
            provider=provider, output_path=out_path,
        )
        provider.encode_calls.clear()
        second = run_embeddings(
            settings, comments_path, checkpoint,
            provider=provider, output_path=out_path,
        )
        assert provider.encode_calls == []
        assert set(first["comment_id"]) == set(second["comment_id"])

    def test_config_change_invalidates_checkpoint(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        run_embeddings(
            _fake_settings(root_seed=1), comments_path, checkpoint,
            provider=provider, output_path=tmp_path / "idx1.parquet",
        )
        provider.encode_calls.clear()
        run_embeddings(
            _fake_settings(root_seed=2), comments_path, checkpoint,
            provider=provider, output_path=tmp_path / "idx2.parquet",
        )
        # Different root_seed -> different stage_seed -> cache_root still
        # has the vectors (cache-first), so no new encode() calls even
        # though the Tier-2 checkpoint was invalidated and reprocessed.
        assert provider.encode_calls == []

    def test_empty_input_is_handled(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(pd.DataFrame(), comments_path)
        out_path = tmp_path / "idx.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_embeddings(
            _fake_settings(), comments_path, checkpoint,
            provider=provider, output_path=out_path,
        )
        assert result.empty

    def test_deterministic_hashing(
        self, tmp_checkpoint_root, tmp_cache_root, tmp_path, provider,
    ):
        comments_path = tmp_path / "comments.parquet"
        write_parquet(_sample_df(), comments_path)
        out_path = tmp_path / "idx.parquet"
        checkpoint = CheckpointManager(tmp_checkpoint_root, tmp_cache_root)

        result = run_embeddings(
            _fake_settings(), comments_path, checkpoint,
            provider=provider, output_path=out_path,
        )
        c1_hash = result.loc[result["comment_id"] == "c1", "embedding_hash"].iloc[0]
        expected = hash_string(
            "cashtag_thyao percent_10 arttı::fake::unknown::cpu",
        )
        assert c1_hash == expected
