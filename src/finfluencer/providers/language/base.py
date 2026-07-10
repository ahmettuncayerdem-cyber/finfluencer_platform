"""
finfluencer.providers.language.base
====================================

Protocol for language-specific text operations.

A ``LanguageProvider`` bundles the operations that depend on the target
language: correct case-folding, tokenisation, stopword list, and
language detection. The Turkish implementation is in :mod:`.turkish`.
Third parties register additional providers via the plugin registry.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LanguageProvider(Protocol):
    """Structural interface for language-specific operations.

    Providers should be *stateless* (constructor may accept configuration,
    but instances should be safe to share across threads and reuse across
    documents).
    """

    #: Registry key (used by :mod:`finfluencer.core.registry`).
    key: str

    #: ISO 639-1 language code (e.g. "tr", "en").
    iso_code: str

    def fold_case(self, text: str) -> str:
        """Return language-correct lowercased text.

        Implementations must handle language-specific case rules
        (e.g. Turkish dotted/dotless I).
        """
        ...

    def strip_noise(self, text: str) -> str:
        """Remove URLs, handles, punctuation, and digits.

        Preserve language-native letters and whitespace only.
        """
        ...

    def tokenize(self, text: str) -> list[str]:
        """Split cleaned text into tokens.

        Whitespace tokenisation is the default; morphologically rich
        languages may override with lemmatisation.
        """
        ...

    def stopwords(self) -> set[str]:
        """Return the language's stopword list.

        Callers may augment via config; see
        :attr:`finfluencer.core.contracts.PreprocessingConfig.stopwords_augment_path`.
        """
        ...

    def is_language(self, text: str) -> bool:
        """Detect whether ``text`` is written in this language.

        Should be robust to short comments — providers may fall back
        to character-based heuristics for texts below a few tokens.
        """
        ...

    def extract_emojis(self, text: str) -> tuple[str, list[str]]:
        """Return ``(text_without_emojis, extracted_emojis)``."""
        ...


__all__ = ["LanguageProvider"]
