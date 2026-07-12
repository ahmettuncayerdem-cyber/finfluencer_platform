"""Tests for :mod:`finfluencer.preprocess.financial_tr`."""

from __future__ import annotations

from finfluencer.preprocess.financial_tr import (
    normalize_cashtags,
    normalize_eur,
    normalize_financial_text,
    normalize_gold,
    normalize_percentages,
    normalize_try,
    normalize_usd,
)


class TestCashtags:
    def test_basic(self):
        assert normalize_cashtags("$THYAO yükseldi") == "CASHTAG_THYAO yükseldi"

    def test_lowercase_is_uppercased(self):
        assert normalize_cashtags("$thyao") == "CASHTAG_THYAO"

    def test_no_match_on_dollar_amount(self):
        assert normalize_cashtags("$100 aldım") == "$100 aldım"


class TestPercentages:
    def test_symbol_form(self):
        assert normalize_percentages("%10 arttı") == "PERCENT_10 arttı"

    def test_word_form(self):
        assert normalize_percentages("yüzde 10 arttı") == "PERCENT_10 arttı"

    def test_word_form_case_insensitive(self):
        assert normalize_percentages("Yüzde 25 düştü") == "PERCENT_25 düştü"

    def test_decimal_takes_integer_part(self):
        assert normalize_percentages("%10,5 arttı") == "PERCENT_10 arttı"


class TestGold:
    def test_basic(self):
        assert normalize_gold("gram altın aldım") == "MONEY_GOLD aldım"

    def test_amount_prefixed(self):
        assert normalize_gold("100 gram altın aldım") == "MONEY_GOLD aldım"

    def test_case_insensitive(self):
        assert normalize_gold("Gram Altın") == "MONEY_GOLD"


class TestTRY:
    def test_tl_suffix(self):
        assert normalize_try("100 TL kar") == "MONEY_TRY kar"

    def test_lira_symbol(self):
        assert normalize_try("100₺ kar") == "MONEY_TRY kar"

    def test_try_code(self):
        assert normalize_try("100 TRY kar") == "MONEY_TRY kar"


class TestUSD:
    def test_dollar_symbol(self):
        assert normalize_usd("$100 kazandım") == "MONEY_USD kazandım"

    def test_usd_code(self):
        assert normalize_usd("100 USD kazandım") == "MONEY_USD kazandım"


class TestEUR:
    def test_eur_code(self):
        assert normalize_eur("100 EUR kaybettim") == "MONEY_EUR kaybettim"


class TestFinancialTextComposed:
    def test_mixed_sentence(self):
        text = "$THYAO %10 arttı, 100 TL kar ettim, $100 de sattım"
        expected = "CASHTAG_THYAO PERCENT_10 arttı, MONEY_TRY kar ettim, MONEY_USD de sattım"
        assert normalize_financial_text(text) == expected

    def test_plain_text_untouched(self):
        text = "bugün hava çok güzeldi"
        assert normalize_financial_text(text) == text

    def test_gold_and_percent_combo(self):
        text = "yüzde 5 değer kazandı gram altın"
        assert normalize_financial_text(text) == "PERCENT_5 değer kazandı MONEY_GOLD"
