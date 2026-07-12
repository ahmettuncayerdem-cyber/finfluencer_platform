"""
examples/language_demo.py
==========================

First runnable feature of the Finfluencer Research Platform:
the TurkishLanguageProvider preprocessing pipeline.

Why this is the first working feature
-------------------------------------
* No external services (no YouTube API, no HuggingFace, no network).
* No credentials required (no API key, no anonymisation salt).
* No configuration files needed.
* Runs to completion in under 1 second.
* Exercises the entire language-provider abstraction end-to-end.

What it demonstrates
--------------------
1. Turkish-aware case folding (İ→i, I→ı) — the single most important
   Turkish-NLP correctness invariant. Standard Python str.lower() gets
   this WRONG for four out of the eight Turkish uppercase letters.
2. Noise stripping (URLs, mentions, digits, punctuation).
3. Whitespace tokenisation.
4. Stopword filtering.
5. Emoji extraction (kept separate from tokens for downstream analysis).
6. Language detection (short-comment character heuristic + langdetect
   fallback for longer text).
7. Runtime pluggability: the same pipeline runs against the
   EnglishLanguageProvider by changing one string.

Run
---
    python examples/language_demo.py
or (equivalently)
    python -m finfluencer

Prerequisites
-------------
    export PYTHONPATH=src         # Linux / macOS
    $env:PYTHONPATH = "$PWD\\src" # Windows PowerShell
"""

from __future__ import annotations

import sys

# Trigger @register decorators so the registry knows about the providers
import finfluencer.providers.language  # noqa: F401
from finfluencer.core.registry import instantiate, list_registered


# =============================================================================
# Sample data — realistic Turkish YouTube comments (pilot-corpus style)
# =============================================================================


TURKISH_SAMPLES: list[str] = [
    "Hocam bugün İSTANBUL borsası çok yükseldi, teşekkürler analiz için!",
    "Bence dolar/TL 30 seviyesini kırar 🚀 Görüşleriniz nedir?",
    "https://youtube.com/@hoca gerçekten harika bir kanal 👍",
    "Reklam olduğunu belirtmiyor musunuz? Bu kabul edilebilir değil.",
    "Iğdır'dan selam, teşekkürler hocam ❤️",
    "sağolun",  # very short — tests the character heuristic
]

ENGLISH_SAMPLES: list[str] = [
    "Thanks for the analysis, the market moved exactly as you predicted!",
    "This is a normal English sentence for pluggability demonstration.",
]


# =============================================================================
# Presentation helpers
# =============================================================================


def _hr(char: str = "─", width: int = 78) -> str:
    return char * width


def _section(title: str) -> None:
    print()
    print(_hr("═"))
    print(f" {title}")
    print(_hr("═"))


def _step(label: str, value: object) -> None:
    """Print one preprocessing step's output with aligned label."""
    print(f"  {label:<22} {value!r}")


# =============================================================================
# The demonstration
# =============================================================================


def demonstrate_turkish_correctness() -> None:
    """The single most important invariant: Turkish-aware case folding."""
    _section("1. TURKISH-AWARE CASE FOLDING — the critical correctness invariant")

    tr = instantiate("language", "turkish")

    print("""
Standard Python str.lower() gets Turkish wrong for four letters:
    'İ'.lower()  →  'i̇'    (i with combining dot above — a two-code-point
                              string that breaks equality checks!)
    'I'.lower()  →  'i'    (correct in English, WRONG in Turkish;
                              Turkish's dotless I lowercases to 'ı')

The TurkishLanguageProvider maps these correctly:
    fold_case('İ')  →  'i'
    fold_case('I')  →  'ı'
""")

    edge_cases = [
        ("İSTANBUL", "istanbul", "correct dotted-I lowercasing"),
        ("IĞDIR",    "ığdır",    "correct dotless-I lowercasing"),
        ("ŞATIROĞLU", "şatıroğlu", "all four combining diacritics"),
    ]
    print(f"  {'Input':<12} {'Turkish provider':<18} {'Python .lower()':<20} Note")
    print(f"  {_hr('-', 74)}")
    for src, expected, note in edge_cases:
        tr_out = tr.fold_case(src)
        py_out = src.lower()
        match_ok = "✓" if tr_out == expected else "✗"
        py_ok = "✓" if py_out == expected else "✗"
        print(f"  {src:<12} {tr_out:<16} {match_ok}  {py_out!r:<18} {py_ok}  {note}")


def demonstrate_full_pipeline(comment: str, provider_key: str = "turkish") -> None:
    """Run every step of the preprocessing pipeline on one comment."""
    provider = instantiate("language", provider_key)

    _section(f"Full pipeline ({provider_key} provider)")
    _step("Input", comment)

    # Step 1: separate emojis from text
    text_no_emoji, emojis = provider.extract_emojis(comment)
    _step("Emojis extracted", emojis)
    _step("Text w/o emojis", text_no_emoji)

    # Step 2: Turkish-aware case folding
    folded = provider.fold_case(text_no_emoji)
    _step("Folded case", folded)

    # Step 3: strip noise (URLs, handles, digits, punctuation)
    clean = provider.strip_noise(folded)
    _step("Noise stripped", clean)

    # Step 4: tokenise
    tokens = provider.tokenize(clean)
    _step("Tokens", tokens)

    # Step 5: filter stopwords
    stopwords = provider.stopwords()
    content_tokens = [t for t in tokens if t not in stopwords]
    _step("Content tokens", content_tokens)
    _step("Dropped stopwords", [t for t in tokens if t in stopwords])

    # Step 6: language detection
    is_lang = provider.is_language(comment)
    _step(f"is_language={provider_key}?", is_lang)


def demonstrate_language_detection() -> None:
    """Show that is_language() correctly distinguishes Turkish from English."""
    _section("2. LANGUAGE DETECTION — Turkish vs. English")

    tr = instantiate("language", "turkish")

    all_samples: list[tuple[str, str]] = [
        (t, "expected: Turkish")   for t in TURKISH_SAMPLES
    ] + [
        (t, "expected: English")   for t in ENGLISH_SAMPLES
    ]

    print(f"  {'Turkish?':<10} Comment (truncated)")
    print(f"  {_hr('-', 74)}")
    for text, expectation in all_samples:
        is_tr = tr.is_language(text)
        mark = "yes " if is_tr else "no  "
        preview = text if len(text) <= 60 else text[:57] + "..."
        print(f"  {mark:<10} {preview}   [{expectation}]")


def demonstrate_pluggability() -> None:
    """Run the SAME pipeline against the EnglishLanguageProvider — one string change."""
    _section("3. PLUGGABILITY — same pipeline, different language")

    registered = sorted(k for _, k in list_registered("language"))
    print(f"\n  Registered language providers: {registered}")
    print(f"  (Adding a new language requires ZERO changes to core/*)")
    print()

    demonstrate_full_pipeline(ENGLISH_SAMPLES[0], provider_key="english")


# =============================================================================
# Entry point
# =============================================================================


def main() -> int:
    print(_hr("═"))
    print(" FINFLUENCER RESEARCH PLATFORM — First Runnable Feature Demo")
    print(" TurkishLanguageProvider preprocessing pipeline")
    print(_hr("═"))
    print()
    print(" This demo runs offline and requires no credentials.")
    print(" It exercises the language-provider abstraction end-to-end.")

    demonstrate_turkish_correctness()

    for i, comment in enumerate(TURKISH_SAMPLES[:3], start=1):
        _section(f"Pipeline example {i} of 3 (Turkish)")
        demonstrate_full_pipeline(comment, provider_key="turkish")

    demonstrate_language_detection()
    demonstrate_pluggability()

    print()
    print(_hr("═"))
    print(" Demo complete. All operations local; no network calls made.")
    print(" Next runnable feature (requires YouTube API key + verified handles):")
    print("     python -m finfluencer.collect.main run --dry-run")
    print(_hr("═"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
