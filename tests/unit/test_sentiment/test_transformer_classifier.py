"""Tests for :mod:`finfluencer.sentiment.transformer_classifier`.

Fake internal model/tokenizer are injected via ``model=``/``tokenizer=``
so these tests never touch the network or require
``transformers``/``torch`` to be installed.
"""

from __future__ import annotations

import numpy as np
import pytest

from finfluencer.sentiment.base import SentimentProvider
from finfluencer.sentiment.transformer_classifier import (
    DEFAULT_MAX_LENGTH,
    DEFAULT_MODEL_NAME,
    DEFAULT_REVISION,
    TransformerSentimentClassifier,
    _positive_index,
    _softmax,
)


class _FakeConfig:
    def __init__(self, id2label: dict[int, str]) -> None:
        self.id2label = id2label


class _FakeOutput:
    def __init__(self, logits: np.ndarray) -> None:
        self.logits = logits


class _FakeModel:
    """Stand-in for AutoModelForSequenceClassification.

    Returns fixed logits ``[0.0, 1.0]`` per row regardless of input
    content — deterministic and sufficient to exercise batching and
    label-order handling without needing real inference.
    """

    def __init__(self, id2label: dict[int, str] | None = None) -> None:
        self.config = _FakeConfig(id2label or {0: "negative", 1: "positive"})
        self.calls: list[dict] = []

    def eval(self) -> "_FakeModel":
        return self

    def to(self, device: str) -> "_FakeModel":
        return self

    def __call__(self, **encoded) -> _FakeOutput:
        self.calls.append(encoded)
        n = encoded["n"]
        logits = np.tile(np.array([0.0, 1.0]), (n, 1)).astype(np.float32)
        return _FakeOutput(logits)


class _FakeTokenizer:
    def __call__(self, texts, *, padding, truncation, max_length, return_tensors):
        return {"n": len(texts)}


@pytest.fixture
def provider() -> TransformerSentimentClassifier:
    return TransformerSentimentClassifier(model=_FakeModel(), tokenizer=_FakeTokenizer())


class TestHelpers:
    def test_softmax_sums_to_one(self):
        out = _softmax(np.array([[1.0, 2.0], [0.0, 0.0]]))
        assert np.allclose(out.sum(axis=-1), 1.0)

    def test_positive_index_by_label_name(self):
        assert _positive_index({0: "NEGATIVE", 1: "POSITIVE"}) == 1
        assert _positive_index({0: "positive", 1: "negative"}) == 0

    def test_positive_index_fallback_when_unlabelled(self):
        assert _positive_index({0: "LABEL_0", 1: "LABEL_1"}) == 1


class TestTransformerSentimentClassifier:
    def test_structural_type(self, provider):
        assert isinstance(provider, SentimentProvider)

    def test_default_metadata(self, provider):
        assert provider.model_name == DEFAULT_MODEL_NAME
        assert provider.revision == DEFAULT_REVISION
        assert provider.device == "cpu"  # no torch/CUDA in the test environment
        assert provider.max_length == DEFAULT_MAX_LENGTH

    def test_explicit_metadata_overrides(self):
        provider = TransformerSentimentClassifier(
            "custom/model", revision="v2", device="cuda",
            model=_FakeModel(), tokenizer=_FakeTokenizer(),
        )
        assert provider.model_name == "custom/model"
        assert provider.revision == "v2"
        assert provider.device == "cuda"

    def test_predict_shape_and_range(self, provider):
        out = provider.predict(["metin bir", "metin iki", "metin uc"])
        assert out.shape == (3,)
        assert np.all((out >= 0.0) & (out <= 1.0))

    def test_predict_empty_list(self, provider):
        out = provider.predict([])
        assert out.shape == (0,)

    def test_predict_is_deterministic(self, provider):
        out1 = provider.predict(["ayni metin"])
        out2 = provider.predict(["ayni metin"])
        assert np.array_equal(out1, out2)

    def test_positive_label_order_respected(self):
        # id2label reversed: index 0 is "positive" this time.
        model = _FakeModel(id2label={0: "positive", 1: "negative"})
        provider = TransformerSentimentClassifier(model=model, tokenizer=_FakeTokenizer())
        out = provider.predict(["x"])
        # Fixed fake logits [0.0, 1.0] favour index 1 ("negative" here), so
        # P(positive) (index 0) must be the smaller softmax value.
        assert out[0] < 0.5

    def test_batching_respects_batch_size(self):
        model = _FakeModel()
        provider = TransformerSentimentClassifier(
            model=model, tokenizer=_FakeTokenizer(), batch_size=2,
        )
        provider.predict(["a", "b", "c", "d", "e"])
        assert len(model.calls) == 3  # 5 texts, batch_size=2 -> 2,2,1
