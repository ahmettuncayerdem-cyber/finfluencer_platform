"""Tests for :mod:`finfluencer.embeddings.sentence_transformer`.

A fake internal model is injected via ``model=`` so these tests never
touch the network or require ``sentence_transformers``/``torch`` to be
installed.
"""

from __future__ import annotations

import numpy as np
import pytest

from finfluencer.embeddings.base import EmbeddingProvider
from finfluencer.embeddings.sentence_transformer import (
    DEFAULT_MODEL_NAME,
    DEFAULT_REVISION,
    SentenceTransformerProvider,
)


class _FakeModel:
    """Stand-in for sentence_transformers.SentenceTransformer."""

    def __init__(self, dim: int = 8) -> None:
        self._dim = dim
        self.encode_calls: list[list[str]] = []

    def get_sentence_embedding_dimension(self) -> int:
        return self._dim

    def encode(self, texts, *, batch_size, convert_to_numpy, show_progress_bar):
        self.encode_calls.append(list(texts))
        return np.ones((len(texts), self._dim), dtype=np.float32)


@pytest.fixture
def fake_model() -> _FakeModel:
    return _FakeModel(dim=8)


class TestSentenceTransformerProvider:
    def test_structural_type(self, fake_model):
        provider = SentenceTransformerProvider(model=fake_model)
        assert isinstance(provider, EmbeddingProvider)

    def test_default_metadata(self, fake_model):
        provider = SentenceTransformerProvider(model=fake_model)
        assert provider.model_name == DEFAULT_MODEL_NAME
        assert provider.revision == DEFAULT_REVISION
        assert provider.device == "cpu"  # no torch/CUDA in the test environment
        assert provider.dim == 8

    def test_explicit_metadata_overrides(self, fake_model):
        provider = SentenceTransformerProvider(
            "custom/model", revision="v2", device="cuda", model=fake_model,
        )
        assert provider.model_name == "custom/model"
        assert provider.revision == "v2"
        assert provider.device == "cuda"

    def test_encode_shape_and_dtype(self, fake_model):
        provider = SentenceTransformerProvider(model=fake_model)
        out = provider.encode(["a", "b", "c"])
        assert out.shape == (3, 8)
        assert out.dtype == np.float32

    def test_encode_empty_list(self, fake_model):
        provider = SentenceTransformerProvider(model=fake_model)
        out = provider.encode([])
        assert out.shape == (0, 8)

    def test_encode_delegates_to_model(self, fake_model):
        provider = SentenceTransformerProvider(model=fake_model)
        provider.encode(["merhaba"])
        assert fake_model.encode_calls == [["merhaba"]]
