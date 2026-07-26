"""Tests for :mod:`finfluencer.providers.language.english`."""

from __future__ import annotations

import pytest

# Import package to trigger @register.
import finfluencer.providers.language  # noqa: F401
from finfluencer.core.registry import get
from finfluencer.providers.language.base import LanguageProvider
from finfluencer.providers.language.english import EnglishLanguageProvider


@pytest.fixture
def en() -> EnglishLanguageProvider:
    return EnglishLanguageProvider()


class TestProtocolConformance:
    def test_isinstance_language_provider(self, en):
        assert isinstance(en, LanguageProvider)

    def test_registered_under_english_key(self):
        import importlib
        import finfluencer.providers.language.english as mod
        importlib.reload(mod)
        assert get("language", "english") is mod.EnglishLanguageProvider


class TestFoldCase:
    def test_lowercases_ascii(self, en):
        assert en.fold_case("HELLO World") == "hello world"

    def test_no_dotted_i_special_casing(self, en):
        # English has no dotted/dotless I problem - plain .lower() is correct.
        assert en.fold_case("ISTANBUL") == "istanbul"


class TestStripNoise:
    def test_removes_urls(self, en):
        assert "https" not in en.strip_noise("visit https://example.com now")

    def test_removes_www_urls(self, en):
        assert "www" not in en.strip_noise("check www.example.com today")

    def test_removes_handles(self, en):
        assert "@" not in en.strip_noise("hi @someone how are you")

    def test_removes_non_letters(self, en):
        cleaned = en.strip_noise("value is 123 units, cost: $45.67!")
        assert "123" not in cleaned
        assert "45" not in cleaned
        assert "$" not in cleaned
        assert "!" not in cleaned

    def test_collapses_whitespace_and_strips(self, en):
        assert en.strip_noise("  hello    world  ") == "hello world"


class TestTokenize:
    def test_simple_split(self, en):
        assert en.tokenize("the quick brown fox") == ["the", "quick", "brown", "fox"]

    def test_empty_strings_excluded(self, en):
        assert en.tokenize("  a   b  ") == ["a", "b"]

    def test_empty_input(self, en):
        assert en.tokenize("") == []


class TestStopwords:
    def test_common_stopwords_present(self, en):
        sw = en.stopwords()
        for w in ("the", "a", "and", "is", "not"):
            assert w in sw

    def test_stopwords_is_a_set(self, en):
        assert isinstance(en.stopwords(), set)

    def test_returned_set_is_a_copy(self, en):
        # Mutating the returned set must not affect the module's base set.
        sw = en.stopwords()
        sw.add("not_actually_a_stopword")
        assert "not_actually_a_stopword" not in en.stopwords()


class TestIsLanguage:
    def test_empty_string(self, en):
        assert not en.is_language("")

    def test_whitespace_only(self, en):
        assert not en.is_language("   ")

    def test_short_text_with_letters_uses_char_heuristic(self, en):
        # Fewer than 3 words - langdetect is unreliable here, so the char
        # heuristic (any a-z letter present) is used instead.
        assert en.is_language("hi there")

    def test_short_text_without_letters_fails_char_heuristic(self, en):
        assert not en.is_language("123 456")

    def test_long_english_text_detected(self, en):
        assert en.is_language(
            "The quick brown fox jumps over the lazy dog and runs away quickly.",
        )

    def test_long_non_english_text_not_detected(self, en):
        assert not en.is_language(
            "Le renard brun rapide saute par dessus le chien paresseux.",
        )

    def test_undetectable_text_raises_internally_and_returns_false(self, en):
        # >=3 "words" with no linguistic features at all - langdetect raises
        # LangDetectException internally; is_language() must catch it and
        # return False rather than propagate.
        assert not en.is_language("!!! ??? ### $$$")


class TestExtractEmojis:
    def test_no_emojis(self, en):
        text, emojis = en.extract_emojis("just plain text")
        assert emojis == []
        assert text == "just plain text"

    def test_extracts_common_emoji(self, en):
        text, emojis = en.extract_emojis("hello \U0001F600 world")
        assert emojis == ["\U0001F600"]
        assert "hello" in text
        assert "world" in text
        assert "\U0001F600" not in text

    def test_emoji_only_text(self, en):
        text, emojis = en.extract_emojis("\U0001F600\U00002600")
        assert text == ""
        assert emojis == ["\U0001F600", "\U00002600"]

    def test_codepoint_range_boundary_outside_so_category(self, en):
        # U+1FAFF falls inside the 0x1F300-0x1FAFF range but is category
        # "Cn" (unassigned), not "So" - this proves the range check, not
        # just the category check, is exercised.
        text, emojis = en.extract_emojis("x\U0001FAFFy")
        assert emojis == ["\U0001FAFF"]
        assert text == "xy"
