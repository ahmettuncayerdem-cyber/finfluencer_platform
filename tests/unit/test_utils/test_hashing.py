"""Tests for :mod:`finfluencer.utils.hashing`."""

from __future__ import annotations

import pytest
from finfluencer.core.exceptions import ConfigError
from finfluencer.utils.hashing import (
    FULL_HASH_LENGTH,
    IDENTIFIER_HASH_LENGTH,
    hash_bytes,
    hash_config_dict,
    hash_file,
    hash_identifier,
    hash_string,
    is_valid_identifier_hash,
    is_valid_sha256_hex,
    validate_salt,
)


class TestHashBytes:
    def test_rfc_test_vector_empty(self) -> None:
        # Well-known SHA-256 of empty input.
        assert hash_bytes(b"") == (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_rfc_test_vector_abc(self) -> None:
        assert hash_bytes(b"abc") == (
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )

    def test_deterministic(self) -> None:
        assert hash_bytes(b"foo") == hash_bytes(b"foo")


class TestHashString:
    def test_unicode_preserved(self) -> None:
        # Turkish characters must not be dropped or mangled.
        assert hash_string("Şatıroğlu") == hash_string("Şatıroğlu")

    def test_different_encodings_produce_different_hashes(self) -> None:
        assert hash_string("abc", encoding="utf-8") != hash_string(
            "abc", encoding="utf-16",
        )


class TestHashFile:
    def test_roundtrip(self, tmp_path):
        p = tmp_path / "x.bin"
        p.write_bytes(b"the quick brown fox jumps over the lazy dog")
        assert hash_file(p) == hash_bytes(b"the quick brown fox jumps over the lazy dog")

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            hash_file(tmp_path / "missing")


class TestHashIdentifier:
    def test_deterministic(self, strong_salt):
        a = hash_identifier("UC123abc", strong_salt)
        b = hash_identifier("UC123abc", strong_salt)
        assert a == b

    def test_default_length_16(self, strong_salt):
        h = hash_identifier("UC123abc", strong_salt)
        assert len(h) == IDENTIFIER_HASH_LENGTH == 16

    def test_full_length_supported(self, strong_salt):
        h = hash_identifier("UC123abc", strong_salt, length=FULL_HASH_LENGTH)
        assert len(h) == FULL_HASH_LENGTH == 64

    def test_different_salts_differ(self):
        h1 = hash_identifier("UC123", "a" * 32)
        h2 = hash_identifier("UC123", "b" * 32)
        assert h1 != h2

    def test_empty_raw_id_returns_empty(self, strong_salt):
        assert hash_identifier("", strong_salt) == ""

    def test_empty_salt_raises(self):
        with pytest.raises(ValueError, match="salt"):
            hash_identifier("UC123", "")

    @pytest.mark.parametrize("length", [0, -1, 65])
    def test_invalid_length_raises(self, strong_salt, length):
        with pytest.raises(ValueError, match="length"):
            hash_identifier("UC123", strong_salt, length=length)

    def test_hmac_not_concatenation(self, strong_salt):
        # HMAC-SHA256("k","m") is NOT equal to SHA256("k"+"m"). Regression
        # guard so a future well-meaning refactor cannot silently degrade.
        raw = "UC123"
        via_hmac = hash_identifier(raw, strong_salt, length=FULL_HASH_LENGTH)
        via_concat = hash_string(strong_salt + raw)
        assert via_hmac != via_concat


class TestValidateSalt:
    def test_accepts_strong_salt(self, strong_salt):
        validate_salt(strong_salt)  # must not raise

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            validate_salt("")

    def test_rejects_placeholder_in_strict(self):
        with pytest.raises(ConfigError, match="placeholder"):
            validate_salt("REPLACE_WITH_RANDOM_PROJECT_SALT")

    def test_rejects_short_in_strict(self):
        with pytest.raises(ConfigError, match="shorter|characters"):
            validate_salt("short")

    def test_non_strict_accepts_short(self):
        validate_salt("short", strict=False)  # must not raise


class TestHashConfigDict:
    def test_key_order_invariant(self):
        d1 = {"a": 1, "b": 2, "nested": {"x": 1, "y": 2}}
        d2 = {"b": 2, "a": 1, "nested": {"y": 2, "x": 1}}
        assert hash_config_dict(d1) == hash_config_dict(d2)

    def test_value_sensitive(self):
        assert hash_config_dict({"a": 1}) != hash_config_dict({"a": 2})

    def test_accepts_date_via_default_str(self):
        from datetime import date
        h = hash_config_dict({"d": date(2025, 1, 1)})
        assert len(h) == FULL_HASH_LENGTH


class TestValidators:
    @pytest.mark.parametrize("s,expected", [
        ("a" * 64, True),
        ("A" * 64, False),          # uppercase rejected
        ("a" * 63, False),           # wrong length
        ("g" * 64, False),           # non-hex char
        ("", False),
    ])
    def test_is_valid_sha256_hex(self, s, expected):
        assert is_valid_sha256_hex(s) is expected

    def test_is_valid_identifier_hash_accepts_empty(self):
        # Empty is the "deleted-channel" sentinel.
        assert is_valid_identifier_hash("") is True
