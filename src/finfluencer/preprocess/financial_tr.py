"""
finfluencer.preprocess.financial_tr
=====================================

Turkish financial-domain text normalisation. Complements
``LanguageProvider`` (case-fold, tokenize, stopwords, emoji extraction)
— this module handles only domain-specific entities: cashtags,
percentages, and currency/commodity mentions. Pure functions, no I/O.
"""

from __future__ import annotations

import re

_CASHTAG_RE = re.compile(r"\$([A-Za-z]{2,10})\b")

_PERCENT_SYMBOL_RE = re.compile(r"%\s?(\d+(?:[.,]\d+)?)")
_PERCENT_WORD_RE = re.compile(r"\byüzde\s+(\d+(?:[.,]\d+)?)", re.IGNORECASE)

_GOLD_RE = re.compile(r"(?:\d+(?:[.,]\d+)?\s*)?gram\s+altın\b", re.IGNORECASE)

_TRY_RE = re.compile(r"\d+(?:[.,]\d+)?\s?(?:TL\b|TRY\b|₺)", re.IGNORECASE)
_USD_SYMBOL_RE = re.compile(r"\$\s?\d+(?:[.,]\d+)?")
_USD_UNIT_RE = re.compile(r"\d+(?:[.,]\d+)?\s?USD\b", re.IGNORECASE)
_EUR_RE = re.compile(r"\d+(?:[.,]\d+)?\s?EUR\b", re.IGNORECASE)


def _leading_int(raw: str) -> str:
    """Return the integer portion of a comma/dot-formatted number string."""
    return raw.split(",")[0].split(".")[0]


def normalize_cashtags(text: str) -> str:
    """``$THYAO`` -> ``CASHTAG_THYAO``. Digits after ``$`` are left alone."""
    return _CASHTAG_RE.sub(lambda m: f"CASHTAG_{m.group(1).upper()}", text)


def normalize_percentages(text: str) -> str:
    """``%10`` / ``yüzde 10`` -> ``PERCENT_10`` (fractional part dropped)."""
    text = _PERCENT_SYMBOL_RE.sub(lambda m: f"PERCENT_{_leading_int(m.group(1))}", text)
    text = _PERCENT_WORD_RE.sub(lambda m: f"PERCENT_{_leading_int(m.group(1))}", text)
    return text


def normalize_gold(text: str) -> str:
    """``gram altın`` (optionally amount-prefixed) -> ``MONEY_GOLD``."""
    return _GOLD_RE.sub("MONEY_GOLD", text)


def normalize_try(text: str) -> str:
    """``100 TL`` / ``100₺`` / ``100 TRY`` -> ``MONEY_TRY``."""
    return _TRY_RE.sub("MONEY_TRY", text)


def normalize_usd(text: str) -> str:
    """``$100`` / ``100 USD`` -> ``MONEY_USD``."""
    text = _USD_SYMBOL_RE.sub("MONEY_USD", text)
    text = _USD_UNIT_RE.sub("MONEY_USD", text)
    return text


def normalize_eur(text: str) -> str:
    """``100 EUR`` -> ``MONEY_EUR``."""
    return _EUR_RE.sub("MONEY_EUR", text)


def normalize_financial_text(text: str) -> str:
    """Apply all Turkish financial-domain normalisations, in order.

    Cashtags before USD (both use ``$``, disambiguated by trailing
    letters vs digits, so order is not strictly required but kept for
    readability). Generic NLP (case-fold, tokenize, stopwords, emoji)
    is NOT performed here — see ``providers.language`` for that.
    """
    text = normalize_cashtags(text)
    text = normalize_percentages(text)
    text = normalize_gold(text)
    text = normalize_try(text)
    text = normalize_usd(text)
    text = normalize_eur(text)
    return text


__all__ = [
    "normalize_cashtags",
    "normalize_percentages",
    "normalize_gold",
    "normalize_try",
    "normalize_usd",
    "normalize_eur",
    "normalize_financial_text",
]
