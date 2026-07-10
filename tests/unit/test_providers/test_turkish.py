"""Tests for :mod:`finfluencer.providers.language.turkish`."""

from __future__ import annotations

import pytest

# Import package to trigger @register.
import finfluencer.providers.language  # noqa: F401
from finfluencer.core.registry import get
from finfluencer.providers.language.base import LanguageProvider
from finfluencer.providers.language.turkish import TurkishLanguageProvider


@pytest.fixture
def tr() -> TurkishLanguageProvider:
    return TurkishLanguageProvider()


class TestProtocolConformance:
    def test_isinstance_language_provider(self, tr):
        assert isinstance(tr, LanguageProvider)

    def test_registered_under_turkish_key(self):
        # Re-import to ensure @register has run in this test session.
        import importlib
        import finfluencer.providers.language.turkish as mod
        importlib.reload(mod)
        assert get("language", "turkish") is mod.TurkishLanguageProvider


class TestFoldCase:
    """The single most important Turkish-specific correctness test.

    Standard Python .lower() maps:
        "İ" → "i̇"  (i with combining dot, WRONG)
        "I" → "i"  (should be "ı" in Turkish)
    """

    @pytest.mark.parametrize("upper,lower", [
        ("İSTANBUL", "istanbul"),
        ("İZMİR", "izmir"),
        ("IĞDIR", "ığdır"),
        ("ANKARA", "ankara"),
        ("MERT", "mert"),
        ("ŞATIROĞLU", "şatıroğlu"),
    ])
    def test_correct_turkish_folding(self, tr, upper, lower):
        assert tr.fold_case(upper) == lower

    def test_default_python_lower_would_fail(self, tr):
        # Regression guard: prove we are NOT using default .lower().
        assert tr.fold_case("İSTANBUL") != "İSTANBUL".lower()


class TestStripNoise:
    def test_removes_urls(self, tr):
        assert "https" not in tr.strip_noise("visit https://x.com now")

    def test_removes_handles(self, tr):
        assert "@" not in tr.strip_noise("hi @user how are you")

    def test_removes_digits(self, tr):
        assert "123" not in tr.strip_noise("value is 123 units")

    def test_preserves_turkish_letters(self, tr):
        assert "ü" in tr.strip_noise("Türkçe metin")


class TestTokenize:
    def test_simple_split(self, tr):
        assert tr.tokenize("hocam çok teşekkürler") == ["hocam", "çok", "teşekkürler"]

    def test_empty_strings_excluded(self, tr):
        assert tr.tokenize("  a   b  ") == ["a", "b"]


class TestIsLanguage:
    def test_long_turkish_text(self, tr):
        assert tr.is_language(
            "Bugün borsa çok yükseldi ve dolar da düştü, teşekkürler hocam.",
        )

    def test_long_english_text(self, tr):
        assert not tr.is_language(
            "Today the market went up significantly and the currency fell.",
        )

    def test_short_turkish_uses_char_heuristic(self, tr):
        # langdetect is unreliable at this length; the char heuristic catches it.
        assert tr.is_language("teşekkürler")

    def test_empty(self, tr):
        assert not tr.is_language("")


class TestEmojiExtraction:
    def test_extract_common_emojis(self, tr):
        text, emojis = tr.extract_emojis("teşekkürler 🙏 hocam ❤️")
        assert len(emojis) >= 1  # at least the prayer hands
        assert "teşekkürler" in text
        assert "hocam" in text

    def test_no_emojis(self, tr):
        text, emojis = tr.extract_emojis("just plain text")
        assert emojis == []
        assert text == "just plain text"


class TestStopwords:
    def test_common_stopwords_present(self, tr):
        sw = tr.stopwords()
        for w in ("ve", "bir", "bu", "için", "ile"):
            assert w in sw

    def test_stopwords_is_a_set(self, tr):
        assert isinstance(tr.stopwords(), set)
