"""
finfluencer.providers.language.turkish
=======================================

Turkish-language provider.

Turkish-specific correctness considerations
--------------------------------------------
* **Dotted/dotless "I".** Python's default ``str.lower()`` maps ``İ``
  → ``i̇`` (i with a combining dot above) and ``I`` → ``i`` — both
  wrong. Correct Turkish folding requires an explicit character map:
  ``İ`` → ``i``, ``I`` → ``ı``. Failing to do this silently damages
  every downstream tokenisation and dictionary lookup involving these
  four letters.
* **langdetect determinism.** ``langdetect.DetectorFactory.seed = 0`` is
  set at import time so language detection is reproducible.
* **Short-comment heuristic.** langdetect performs poorly on comments
  below ~3 tokens; we fall back to a "contains Turkish-specific
  character" heuristic (``çğıöşü``) for these short cases.
"""

from __future__ import annotations

import re
import unicodedata

from langdetect import DetectorFactory, LangDetectException, detect

from finfluencer.core.registry import register
from finfluencer.providers.language.base import LanguageProvider


# Deterministic language detection.
DetectorFactory.seed = 0

# Turkish-aware case-folding map (correct İ/I handling).
_TR_LOWER_MAP: dict[int, int] = str.maketrans(
    {
        "İ": "i",
        "I": "ı",
        "Ğ": "ğ",
        "Ü": "ü",
        "Ş": "ş",
        "Ö": "ö",
        "Ç": "ç",
    },
)

# URL, mention/handle, and non-letter regexes.
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_HANDLE_RE = re.compile(r"@\w+")
# Retain Turkish-native letters and whitespace.
_NON_LETTER_RE = re.compile(r"[^a-zçğıöşü\s]", flags=re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")

# Turkish-specific character set for the short-comment heuristic.
_TR_SPECIAL_CHARS: frozenset[str] = frozenset("çğıöşü")

# Base stopword list. Not exhaustive; conservative to avoid over-pruning.
_BASE_STOPWORDS: frozenset[str] = frozenset({
    "acaba", "ama", "ancak", "aslında", "az", "bazı", "belki", "biri", "birkaç",
    "biz", "bu", "çok", "çünkü", "da", "daha", "de", "defa", "diye", "eğer",
    "en", "gibi", "hem", "hep", "hepsi", "her", "hiç", "için", "ile", "ise",
    "kez", "ki", "kim", "mı", "mi", "mu", "mü", "nasıl", "ne", "neden", "nerde",
    "nerede", "nereye", "niçin", "niye", "o", "sanki", "şey", "siz", "şu",
    "tüm", "ve", "veya", "ya", "yani", "artık", "olarak", "olur", "olan",
    "oldu", "olmak", "olması", "olsun", "olmuş", "ben", "sen",
    # Domain-augmented low-information tokens
    "bir", "aynen", "işte", "tabi", "tamam", "evet", "hayır", "bence",
    "sanırım", "galiba",
})


@register("language", "turkish")
class TurkishLanguageProvider:
    """Concrete Turkish implementation of :class:`LanguageProvider`."""

    key: str = "turkish"
    iso_code: str = "tr"

    # ---- Case folding ---------------------------------------------------

    def fold_case(self, text: str) -> str:
        """Turkish-aware lowercasing (correct İ/I handling)."""
        return text.translate(_TR_LOWER_MAP).lower()

    # ---- Noise stripping ------------------------------------------------

    def strip_noise(self, text: str) -> str:
        """Remove URLs, handles, digits, punctuation. Keep Turkish letters."""
        text = _URL_RE.sub(" ", text)
        text = _HANDLE_RE.sub(" ", text)
        text = _NON_LETTER_RE.sub(" ", text)
        text = _WHITESPACE_RE.sub(" ", text).strip()
        return text

    # ---- Tokenisation ---------------------------------------------------

    def tokenize(self, text: str) -> list[str]:
        """Whitespace tokenisation. Empty tokens are excluded."""
        return [t for t in text.split() if t]

    # ---- Stopwords ------------------------------------------------------

    def stopwords(self) -> set[str]:
        return set(_BASE_STOPWORDS)

    # ---- Language detection ---------------------------------------------

    def is_language(self, text: str) -> bool:
        """Return True if the text is Turkish.

        Short comments (< 3 whitespace tokens on the raw text) fall back
        to a Turkish-specific character heuristic, since langdetect is
        unreliable at that length.
        """
        stripped = text.strip()
        if not stripped:
            return False
        if len(stripped.split()) < 3:
            lowered = stripped.lower()
            return any(c in lowered for c in _TR_SPECIAL_CHARS)
        try:
            return detect(stripped) == "tr"
        except LangDetectException:
            return False

    # ---- Emoji extraction -----------------------------------------------

    def extract_emojis(self, text: str) -> tuple[str, list[str]]:
        """Separate emojis from text.

        Returns (text_without_emojis, list_of_extracted_emojis).
        Detection uses Unicode general-category ``So`` plus explicit
        emoji code-point blocks.
        """
        emojis: list[str] = []
        kept: list[str] = []
        for ch in text:
            code = ord(ch)
            cat = unicodedata.category(ch)
            is_emoji = (
                cat == "So"
                or 0x1F300 <= code <= 0x1FAFF
                or 0x2600 <= code <= 0x27BF
                or 0x1F000 <= code <= 0x1F2FF
            )
            if is_emoji:
                emojis.append(ch)
            else:
                kept.append(ch)
        return "".join(kept), emojis


__all__ = ["TurkishLanguageProvider"]
