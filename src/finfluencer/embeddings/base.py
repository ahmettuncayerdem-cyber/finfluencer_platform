"""
finfluencer.embeddings.base
=============================

Protocol for text-embedding providers.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Structural interface for embedding backends.

    Implementations must be safe to reuse across calls; batching is the
    implementation's responsibility. Stateless from the caller's point
    of view (same input texts -> same output vectors).
    """

    #: Registry key (used by finfluencer.core.registry).
    key: str

    #: Output embedding dimensionality.
    dim: int

    def encode(self, texts: list[str]) -> np.ndarray:
        """Return an ``(len(texts), dim)`` float array of embeddings."""
        ...


__all__ = ["EmbeddingProvider"]
