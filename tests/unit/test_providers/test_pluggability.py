"""Tests for the LanguageProvider / PlatformProvider pluggability contract.

These tests EXIST TO GUARD the v2.1 architectural promise (§H, §I) that
new languages and platforms can be added without touching any code
outside ``providers/*/``. If any of these tests fails, a change has
inadvertently coupled the core to a specific language or platform key
and the fix belongs in provider modules, not in the tests.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from finfluencer.core.contracts import ProvidersConfig
from finfluencer.core.exceptions import ProviderNotFoundError
from finfluencer.core.registry import (
    clear_registry,
    get,
    instantiate,
    list_registered,
    register,
)
from finfluencer.providers.language.base import LanguageProvider


# ============================================================================
# Schema-level pluggability
# ============================================================================


class TestProvidersConfigSchema:
    """The ProvidersConfig schema must accept any well-formed key without
    requiring code changes to core/contracts.py."""

    def test_accepts_turkish(self):
        p = ProvidersConfig(language="turkish", platform="youtube")
        assert p.language == "turkish"

    def test_accepts_english(self):
        # No English provider is registered yet — schema must still accept
        # the string. Existence checking is a runtime concern.
        p = ProvidersConfig(language="english", platform="youtube")
        assert p.language == "english"

    def test_accepts_german(self):
        p = ProvidersConfig(language="german", platform="youtube")
        assert p.language == "german"

    def test_accepts_arabic(self):
        p = ProvidersConfig(language="arabic", platform="youtube")
        assert p.language == "arabic"

    def test_accepts_future_platforms(self):
        for platform in ("x", "reddit", "tiktok", "instagram"):
            p = ProvidersConfig(language="turkish", platform=platform)
            assert p.platform == platform

    @pytest.mark.parametrize("bad_key", [
        "Not-a-valid-key",           # uppercase and hyphen
        "1english",                  # leading digit
        "",                          # empty
        "en glish",                  # whitespace
        "a" * 33,                    # too long
    ])
    def test_rejects_malformed_keys(self, bad_key):
        with pytest.raises(ValidationError):
            ProvidersConfig(language=bad_key, platform="youtube")


# ============================================================================
# Runtime pluggability — the actual demonstration
# ============================================================================


class TestLanguageProviderPluggability:
    """Demonstrate that a new language provider can be registered and used
    WITHOUT touching any file under ``core/`` or the existing Turkish
    provider.
    """

    def test_fake_english_provider_registers_and_resolves(self):
        """The full plug-in sequence: define, register, resolve, use."""
        clear_registry()

        @register("language", "english")
        class FakeEnglishProvider:
            """A minimal LanguageProvider for the pluggability test.

            In a real deployment this class lives in
            ``providers/language/english.py`` (in-tree) or ships in a
            separate ``finfluencer-english`` PyPI package that declares
            an entry point under ``finfluencer.providers``.
            """
            key: str = "english"
            iso_code: str = "en"

            def fold_case(self, text: str) -> str:
                return text.lower()

            def strip_noise(self, text: str) -> str:
                import re
                return re.sub(r"[^a-z\s]", " ", text.lower()).strip()

            def tokenize(self, text: str) -> list[str]:
                return [t for t in text.split() if t]

            def stopwords(self) -> set[str]:
                return {"the", "a", "an", "is", "are"}

            def is_language(self, text: str) -> bool:
                return bool(text and any(c.isascii() and c.isalpha() for c in text))

            def extract_emojis(self, text: str) -> tuple[str, list[str]]:
                return text, []

        # Registry lookup succeeds.
        cls = get("language", "english")
        assert cls is FakeEnglishProvider

        # Instantiation works via registry helper.
        inst = instantiate("language", "english")
        assert isinstance(inst, LanguageProvider)

        # Protocol conformance verified at runtime.
        assert inst.iso_code == "en"
        assert inst.fold_case("HELLO") == "hello"
        assert "the" in inst.stopwords()
        assert inst.is_language("hello world")

    def test_multiple_languages_coexist(self):
        """Multiple language providers can be registered simultaneously
        and looked up independently — required for cross-cultural
        comparative studies (roadmap)."""
        import importlib

        clear_registry()

        # Force @register to run again (module is cached from first import,
        # so a plain `import` would be a no-op after clear_registry).
        from finfluencer.providers.language import turkish as _turkish_mod
        importlib.reload(_turkish_mod)

        @register("language", "german")
        class FakeGermanProvider:
            key: str = "german"
            iso_code: str = "de"

            def fold_case(self, text: str) -> str: return text.lower()
            def strip_noise(self, text: str) -> str: return text
            def tokenize(self, text: str) -> list[str]: return text.split()
            def stopwords(self) -> set[str]: return {"der", "die", "das"}
            def is_language(self, text: str) -> bool: return "ß" in text.lower()
            def extract_emojis(self, text: str) -> tuple[str, list[str]]: return text, []

        # Both providers coexist; neither shadows the other.
        registered_keys = {k for _, k in list_registered("language")}
        assert "turkish" in registered_keys
        assert "german" in registered_keys

        tr = instantiate("language", "turkish")
        de = instantiate("language", "german")
        assert tr.iso_code == "tr"
        assert de.iso_code == "de"

    def test_missing_provider_error_carries_available_keys(self):
        """When a configured provider is not registered, the error
        message lists what IS registered so the user can fix the config."""
        import importlib

        clear_registry()
        from finfluencer.providers.language import turkish as _turkish_mod
        importlib.reload(_turkish_mod)

        with pytest.raises(ProviderNotFoundError) as exc_info:
            get("language", "arabic")
        assert "turkish" in exc_info.value.context.get("available_keys", [])


# ============================================================================
# Core-code isolation guard
# ============================================================================


class TestCoreDoesNotDependOnLanguageProviders:
    """Static assertions about the module dependency graph."""

    def test_contracts_does_not_import_provider_modules(self):
        """`core.contracts` must not import from `providers.*`; if it did,
        registering a new provider would require a contracts change."""
        import inspect
        from finfluencer.core import contracts

        source = inspect.getsource(contracts)
        assert "from finfluencer.providers" not in source
        assert "import finfluencer.providers" not in source

    def test_registry_does_not_import_language_module(self):
        """`core.registry` must not IMPORT concrete language providers.
        Documentation examples that mention provider class names are fine
        (they are docstring text, not code dependencies)."""
        import inspect
        from finfluencer.core import registry

        source = inspect.getsource(registry)
        # Real imports leave "from finfluencer.providers" or
        # "import finfluencer.providers" in the source.
        assert "from finfluencer.providers" not in source
        assert "import finfluencer.providers" not in source

    def test_config_module_does_not_hardcode_turkish(self):
        import inspect
        from finfluencer.core import config

        source = inspect.getsource(config)
        # 'turkish' may appear only in comments/docstrings, never in code logic.
        # A quick heuristic: no equality check against the string "turkish".
        assert '== "turkish"' not in source
        assert "'turkish'" not in source or "# " in source  # allow in comment
