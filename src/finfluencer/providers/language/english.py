"""
finfluencer.providers.language.english
=======================================

English-language provider (roadmap demonstration).

Demonstrates that adding a new language requires ONLY:
    1. A new file under ``providers/language/`` (this file)
    2. An import line in ``providers/language/__init__.py`` to run @register

NO changes to any ``core/*`` module are required.
"""

from __future__ import annotations

import re

from langdetect import DetectorFactory, LangDetectException, detect

from finfluencer.core.registry import register
from finfluencer.providers.language.base import LanguageProvider

DetectorFactory.seed = 0

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_HANDLE_RE = re.compile(r"@\w+")
_NON_LETTER_RE = re.compile(r"[^a-z\s]", flags=re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")

_BASE_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "as", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "this", "that",
    "these", "those", "i", "you", "he", "she", "it", "we", "they", "what",
    "which", "who", "when", "where", "why", "how", "not", "no",
})


@register("language", "english")
class EnglishLanguageProvider:
    """Concrete English implementation of :class:`LanguageProvider`."""

    key: str = "english"
    iso_code: str = "en"

    def fold_case(self, text: str) -> str:
        return text.lower()  # English has no dotted/dotless I problem

    def strip_noise(self, text: str) -> str:
        text = _URL_RE.sub(" ", text)
        text = _HANDLE_RE.sub(" ", text)
        text = _NON_LETTER_RE.sub(" ", text)
        text = _WHITESPACE_RE.sub(" ", text).strip()
        return text

    def tokenize(self, text: str) -> list[str]:
        return [t for t in text.split() if t]

    def stopwords(self) -> set[str]:
        return set(_BASE_STOPWORDS)

    def is_language(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        if len(stripped.split()) < 3:
            return bool(re.search(r"[a-z]", stripped.lower()))
        try:
            return detect(stripped) == "en"
        except LangDetectException:
            return False

    def extract_emojis(self, text: str) -> tuple[str, list[str]]:
        import unicodedata
        emojis: list[str] = []
        kept: list[str] = []
        for ch in text:
            code = ord(ch)
            cat = unicodedata.category(ch)
            if cat == "So" or 0x1F300 <= code <= 0x1FAFF or 0x2600 <= code <= 0x27BF:
                emojis.append(ch)
            else:
                kept.append(ch)
        return "".join(kept), emojis


__all__ = ["EnglishLanguageProvider"]
