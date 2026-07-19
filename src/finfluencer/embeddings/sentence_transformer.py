"""
finfluencer.embeddings.sentence_transformer
=============================================

Sentence-Transformers-backed :class:`~finfluencer.embeddings.base.EmbeddingProvider`.

Heavy ML dependencies (``sentence_transformers``, ``torch``) are
imported lazily — only when a real (non-injected) model is constructed
— so importing this module (and registering the provider) never
requires them to be installed. Tests inject a fake ``model`` object
exposing ``.encode()`` and ``.get_sentence_embedding_dimension()``.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from finfluencer.core.registry import register

#: Default model per Phase 2.1 spec — multilingual, covers Turkish.
DEFAULT_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
DEFAULT_REVISION: str = "main"


def _auto_device() -> str:
    """CPU/GPU auto-detection. Falls back to "cpu" if torch is absent."""
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


@register("embedding", "sentence_transformer")
class SentenceTransformerProvider:
    """Concrete :class:`EmbeddingProvider` wrapping a sentence-transformers model.

    Stores ``model_name``, ``revision``, ``device``, and ``dim`` — the
    metadata :mod:`finfluencer.embeddings.pipeline` needs for cache-key
    composition and ``embeddings_index.parquet`` provenance.
    """

    key: str = "sentence_transformer"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        *,
        revision: str = DEFAULT_REVISION,
        device: str | None = None,
        batch_size: int = 32,
        model: Any | None = None,
    ) -> None:
        self.model_name: str = model_name
        self.revision: str = revision
        self.device: str = device or _auto_device()
        self.batch_size: int = batch_size

        if model is not None:
            self._model = model
        else:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                model_name, revision=revision, device=self.device,
            )

        self.dim: int = int(self._model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype=np.float32)
        embeddings = self._model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(embeddings, dtype=np.float32)


__all__ = ["SentenceTransformerProvider", "DEFAULT_MODEL_NAME", "DEFAULT_REVISION"]
