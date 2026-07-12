"""
finfluencer.preprocess.base
=============================

Protocol for text preprocessing (language- and platform-agnostic).
"""

from __future__ import annotations

from typing import NamedTuple, Protocol, runtime_checkable


class PreprocessedText(NamedTuple):
    """Output of a single preprocessing call; maps 1:1 to CommentRecord fields."""

    text_clean: str
    tokens: list[str]
    n_tokens: int
    emojis: list[str]


@runtime_checkable
class TextPreprocessor(Protocol):
    """Structural interface for text preprocessing.

    Implementations compose a ``LanguageProvider`` (case-fold, strip,
    tokenize, emoji extraction) with platform/domain-specific
    normalisation (e.g. cashtags, hashtags, subreddit markup). Stateless;
    instances must be safe to share and reuse across documents.
    """

    #: Registry key (used by ``finfluencer.core.registry``).
    key: str

    def process(self, text_raw: str) -> PreprocessedText:
        """Return cleaned text, tokens, token count, and extracted emojis.

        Implementations decide internal ordering (case-fold, strip,
        tokenize, emoji extraction, domain normalisation); only the
        output shape is contractual.
        """
        ...


__all__ = ["PreprocessedText", "TextPreprocessor"]
