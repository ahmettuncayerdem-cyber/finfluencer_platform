"""
finfluencer.sentiment.base
=============================

Protocol for sentiment-polarity providers.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class SentimentProvider(Protocol):
    """Structural interface for binary sentiment-polarity backends.

    Implementations must be safe to reuse across calls; batching is the
    implementation's responsibility. Target-of-affect classification
    (analyst/market/both/neither) is a separate concern (Phase 2.3) and
    is intentionally NOT part of this Protocol.
    """

    #: Registry key (used by finfluencer.core.registry).
    key: str

    def predict(self, texts: list[str]) -> np.ndarray:
        """Return an ``(len(texts),)`` float array of P(positive) in [0, 1]."""
        ...


__all__ = ["SentimentProvider"]
