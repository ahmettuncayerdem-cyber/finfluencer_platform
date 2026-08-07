"""
finfluencer.sentiment.transformer_classifier
===============================================

Transformers-backed :class:`~finfluencer.sentiment.base.SentimentProvider`
(binary polarity only).

Heavy ML dependencies (``transformers``, ``torch``) are imported lazily
— only when a real (non-injected) model is constructed — so importing
this module (and registering the provider) never requires them. Tests
inject ``model=``/``tokenizer=`` fakes.

Positive-class column lookup is done via the model's ``config.id2label``
mapping (searching for a label containing "pos", case-insensitively)
rather than assuming a fixed index — robust to different label-order
conventions across HuggingFace checkpoints. Falls back to index 1
(the common binary-classifier convention) if no label matches.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from finfluencer.core.registry import register

#: Default model per Phase 2.2 spec (config/settings.yaml sentiment.primary_model).
DEFAULT_MODEL_NAME: str = "savasy/bert-base-turkish-sentiment-cased"
DEFAULT_REVISION: str = "main"
DEFAULT_MAX_LENGTH: int = 512


def _auto_device() -> str:
    """CPU/GPU auto-detection. Falls back to "cpu" if torch is absent."""
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _softmax(logits: np.ndarray) -> np.ndarray:
    """Numerically-stable softmax over the last axis (pure NumPy — no torch
    dependency needed for the math, so fake logits in tests work too)."""
    shifted = logits - logits.max(axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=-1, keepdims=True)


def _positive_index(id2label: dict[int, str]) -> int:
    """Locate the positive-class column; robust to label-order conventions."""
    for idx, label in id2label.items():
        if "pos" in str(label).lower():
            return int(idx)
    return 1  # conventional binary-classifier fallback (0=negative, 1=positive)


@register("sentiment", "transformer")
class TransformerSentimentClassifier:
    """Concrete :class:`SentimentProvider` wrapping a HF sequence-classification model.

    Stores ``model_name``, ``revision``, ``device`` — the metadata
    :mod:`finfluencer.sentiment.pipeline` needs for cache-key composition.
    """

    key: str = "transformer"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        *,
        revision: str = DEFAULT_REVISION,
        device: str | None = None,
        batch_size: int = 32,
        max_length: int = DEFAULT_MAX_LENGTH,
        use_safetensors: bool = True,
        model: Any | None = None,
        tokenizer: Any | None = None,
    ) -> None:
        self.model_name: str = model_name
        self.revision: str = revision
        self.device: str = device or _auto_device()
        self.batch_size: int = batch_size
        self.max_length: int = max_length
        self.use_safetensors: bool = use_safetensors

        if model is not None and tokenizer is not None:
            self._model = model
            self._tokenizer = tokenizer
        else:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(model_name, revision=revision)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                model_name, revision=revision,
                # NOTE (2026-07-14): use_safetensors=False was previously set
                # here as a defensive measure against a hypothesized Windows
                # mmap crash (huggingface/safetensors#693). That hypothesis
                # was empirically ruled out at the time (the real crash was
                # a missing torch.inference_mode(), fixed in predict() below).
                # On the current environment (torch 2.13.0+cpu), the legacy
                # pickle (.bin) loading path causes a native DLL
                # initialization failure (WinError 1114 loading
                # torch/lib/c10.dll). Omitting the flag entirely still hit
                # the same failure (transformers did not auto-prefer
                # safetensors here) - only an EXPLICIT use_safetensors=True
                # avoids it, confirmed via isolated reproduction.
                #
                # UPDATED (2026-08-07, Gaza pilot smoke test): hardcoding
                # True silently assumed every future pinned model ships a
                # safetensors file. cardiffnlp/twitter-roberta-base-
                # sentiment-latest does not (real OSError observed, no
                # auto-conversion branch exists on the Hub either) -- now a
                # constructor parameter (core.contracts.ModelReference.
                # use_safetensors), defaulting to True so every existing
                # config (including the Turkish study's own pinned models)
                # keeps exactly its current, already-proven-safe behavior.
                # Setting it False for a specific model is a deliberate,
                # per-model, reversible experiment that REINTRODUCES the
                # legacy pickle-loading path responsible for the original
                # Windows DLL crash above -- it must be exercised and
                # observed on real Windows hardware before being trusted,
                # not assumed safe by symmetry with this comment.
                use_safetensors=self.use_safetensors,
            ).to(self.device)
            self._model.eval()

        id2label = getattr(getattr(self._model, "config", None), "id2label", None) or {
            0: "negative", 1: "positive",
        }
        self._positive_index: int = _positive_index(id2label)

    def predict(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0,), dtype=np.float32)

        # Root cause (confirmed via batch-level RSS instrumentation on a real
        # run: memory grew from ~931MB to ~20.9GB within 3 batches, crashing
        # with 0xC0000005): without disabling autograd, every forward pass
        # retains its full backward graph. eval() alone only disables
        # dropout/batchnorm, not graph tracking. torch.inference_mode()
        # disables it; falls back to a no-op context when torch isn't
        # importable (fake models injected in tests).
        try:
            import torch
            _no_grad_ctx = torch.inference_mode
        except ImportError:
            from contextlib import nullcontext
            _no_grad_ctx = nullcontext

        probs: list[float] = []
        with _no_grad_ctx():
            for start in range(0, len(texts), self.batch_size):
                batch = texts[start:start + self.batch_size]
                encoded = self._tokenizer(
                    batch, padding=True, truncation=True,
                    max_length=self.max_length, return_tensors="pt",
                )
                outputs = self._model(**encoded)
                logits = outputs.logits
                logits = (
                    logits.detach().cpu().numpy() if hasattr(logits, "detach")
                    else np.asarray(logits)
                )
                batch_probs = _softmax(np.asarray(logits, dtype=np.float64))[:, self._positive_index]
                probs.extend(float(p) for p in batch_probs)
        return np.asarray(probs, dtype=np.float32)


__all__ = [
    "TransformerSentimentClassifier",
    "DEFAULT_MODEL_NAME", "DEFAULT_REVISION", "DEFAULT_MAX_LENGTH",
]
