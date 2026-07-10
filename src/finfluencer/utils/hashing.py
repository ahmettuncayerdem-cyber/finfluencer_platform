"""
finfluencer.utils.hashing
==========================

Salted SHA-256 hashing utilities.

Two primary use cases:

1. **Anonymise commenter identifiers at ingest** (Methods §3.11). Raw
   YouTube channel IDs never persist to disk; only their salted,
   truncated HMAC-SHA256 digest does.
2. **Hash files, config dicts, and byte strings for provenance**.
   Used by :mod:`finfluencer.core.reproducibility` and
   :mod:`finfluencer.core.checkpoint` to detect input changes.

Design decisions
----------------

*Algorithm.* SHA-256 is used throughout. It has hardware acceleration
on all modern CPUs, is standardised across languages (so replication
packages remain readable), and produces 256 bits of output — comfortably
above any collision-resistance requirement for our scale.

*HMAC over concatenation.* Anonymised identifiers use HMAC-SHA256 with
the project salt as the *key*, not `sha256(salt + id)`. HMAC is the
standard cryptographic construction for salted hashing and is immune to
length-extension attacks that affect naive concatenation.

*Truncation to 64 bits (16 hex characters).* Justified by the birthday
paradox: for a corpus of *n* commenters and a *k*-bit hash space, the
expected probability of at least one collision is approximately
*n² / 2^(k+1)*. For our expected scale of ~10⁴ commenters, this is
~10⁻¹². Even at 10⁶ commenters (a much larger future study),
collision probability remains below 10⁻⁷. Truncation also reduces
storage and makes hashes readable at a glance.

*Salt strength.* The salt's role is limited: YouTube channel-ID space
(~10⁴⁰) is too large for pre-computed rainbow tables regardless of
salting. The real defence against re-identification is *not persisting
raw IDs at all* — anonymisation happens in-memory at ingest, before
disk write. The salt guards against a specific attack (adversary tries
to hash known channel IDs to match observed hashes); a 32+ character
random salt makes this infeasible. Validation is performed at platform
startup, not per-hash, for performance and separation of concerns.

*Deterministic dict hashing.* :func:`hash_config_dict` serialises the
input via ``json.dumps(sort_keys=True)`` before hashing. This is
deterministic across Python runs and platforms (Python's ``json.dumps``
has a stable output format), unlike hashing the ``repr()`` of a dict.

*Streaming file hashing.* :func:`hash_file` reads in chunks so it works
on files larger than RAM (relevant for cached embedding tensors and
model weight archives in Phase 8).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from finfluencer.core.exceptions import ConfigError


# =============================================================================
# Constants
# =============================================================================


#: Length (hex chars) of anonymised identifier hashes. 16 hex = 64 bits.
IDENTIFIER_HASH_LENGTH: int = 16

#: Length (hex chars) of full SHA-256 output. 64 hex = 256 bits.
FULL_HASH_LENGTH: int = 64

#: Minimum recommended salt length in characters. Salts shorter than this
#: raise ConfigError in strict mode.
MIN_SALT_LENGTH: int = 16

#: Known placeholder salt values that must NOT be used in production.
#: Not exhaustive — the .env.example template guides users; this is a
#: fast-fail check for the most common cases.
_KNOWN_PLACEHOLDER_SALTS: frozenset[str] = frozenset(
    {
        "REPLACE_WITH_RANDOM_PROJECT_SALT",
        "REPLACE_ME",
        "your_salt_here",
        "changeme",
        "TODO",
        "test",
    },
)


# =============================================================================
# Primitive hashing
# =============================================================================


def hash_bytes(data: bytes) -> str:
    """Return the full SHA-256 hex digest of ``data``.

    Parameters
    ----------
    data
        Arbitrary byte string.

    Returns
    -------
    str
        64-character lowercase hex digest.
    """
    return hashlib.sha256(data).hexdigest()


def hash_string(text: str, *, encoding: str = "utf-8") -> str:
    """Return the full SHA-256 hex digest of ``text``.

    Parameters
    ----------
    text
        Arbitrary Unicode string.
    encoding
        Encoding used to convert ``text`` to bytes. Default ``"utf-8"``.

    Returns
    -------
    str
        64-character lowercase hex digest.
    """
    return hash_bytes(text.encode(encoding))


def hash_file(path: Path | str, *, chunk_size: int = 65536) -> str:
    """Return the full SHA-256 hex digest of the file at ``path``.

    Reads the file in chunks, so memory usage is bounded by ``chunk_size``
    even for files larger than RAM.

    Parameters
    ----------
    path
        Path to the file.
    chunk_size
        Bytes per read. Default 64 KiB.

    Returns
    -------
    str
        64-character lowercase hex digest.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    """
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


# =============================================================================
# Identifier hashing (anonymisation)
# =============================================================================


def hash_identifier(
    raw_id: str,
    salt: str,
    *,
    length: int = IDENTIFIER_HASH_LENGTH,
) -> str:
    """Anonymise a commenter identifier via HMAC-SHA256, truncated.

    Deterministic: the same ``(raw_id, salt)`` pair always produces the
    same output within a project. The salt should be pre-validated at
    startup via :func:`validate_salt` — this function performs only the
    minimum runtime check (non-empty salt) for performance, since it is
    called once per comment.

    Parameters
    ----------
    raw_id
        Raw identifier (e.g. YouTube channel ID). Empty string returns
        empty string — matches the behaviour of the YouTube API for
        comments whose authors have deleted their channels.
    salt
        Project-specific salt. Used as the HMAC key.
    length
        Truncation length in hex characters. Default 16 (64 bits).

    Returns
    -------
    str
        Truncated lowercase hex digest, or empty string if ``raw_id``
        is empty.

    Raises
    ------
    ValueError
        If ``salt`` is empty, or ``length`` is not in ``[1, 64]``.
    """
    if not salt:
        raise ValueError("hash_identifier: salt must not be empty")
    if not (1 <= length <= FULL_HASH_LENGTH):
        raise ValueError(
            f"hash_identifier: length must be in [1, {FULL_HASH_LENGTH}], "
            f"got {length}",
        )
    if not raw_id:
        return ""

    digest = hmac.new(
        key=salt.encode("utf-8"),
        msg=raw_id.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return digest[:length]


def validate_salt(salt: str, *, strict: bool = True) -> None:
    """Validate a salt at platform startup.

    Intended to be called once, at pipeline startup (from
    :mod:`finfluencer.core.config`), so subsequent :func:`hash_identifier`
    calls can trust the salt without per-call re-checking.

    Parameters
    ----------
    salt
        Candidate salt.
    strict
        If ``True`` (default), reject known placeholder patterns and
        short salts as :class:`ConfigError`. If ``False``, only enforce
        the non-empty rule (used in unit tests).

    Raises
    ------
    ValueError
        If ``salt`` is empty (a programmer error — configuration should
        have caught this earlier).
    ConfigError
        In strict mode: if ``salt`` matches a known placeholder or is
        below :data:`MIN_SALT_LENGTH` characters.
    """
    if not salt:
        raise ValueError("validate_salt: salt must not be empty")
    if not strict:
        return
    if salt in _KNOWN_PLACEHOLDER_SALTS:
        raise ConfigError(
            "Salt matches a known placeholder value. Generate a real salt "
            "with: python -c 'import secrets; print(secrets.token_hex(32))'",
            salt_length=len(salt),
        )
    if len(salt) < MIN_SALT_LENGTH:
        raise ConfigError(
            f"Salt is shorter than {MIN_SALT_LENGTH} characters. Generate a "
            f"stronger salt with: python -c 'import secrets; print(secrets.token_hex(32))'",
            salt_length=len(salt),
            min_length=MIN_SALT_LENGTH,
        )


# =============================================================================
# Deterministic config-dict hashing
# =============================================================================


def hash_config_dict(d: dict[str, Any]) -> str:
    """Deterministic SHA-256 hash of a configuration dictionary.

    Serialises ``d`` as JSON with sorted keys and compact stable
    formatting, then hashes the byte string. The result is deterministic
    across Python runs and platforms, provided all values are
    JSON-serialisable. Non-JSON-native types (dates, Decimals, Paths)
    are stringified via ``default=str``.

    Used by :mod:`finfluencer.core.checkpoint` to detect configuration
    changes that should invalidate downstream checkpoints.

    Parameters
    ----------
    d
        Dictionary to hash. Nested dicts are handled recursively via
        ``sort_keys=True``.

    Returns
    -------
    str
        64-character lowercase hex digest.

    Raises
    ------
    TypeError
        If ``d`` contains values that cannot be serialised even via
        ``default=str``.
    """
    payload = json.dumps(
        d,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,  # dates, Decimals, Paths → str; explicit and reproducible
    )
    return hash_string(payload)


# =============================================================================
# Validation helpers
# =============================================================================


def is_valid_sha256_hex(s: str, *, length: int = FULL_HASH_LENGTH) -> bool:
    """Return ``True`` iff ``s`` is a valid lowercase hex digest of the
    given length.

    Parameters
    ----------
    s
        Candidate string.
    length
        Expected length in hex characters. Default 64 (full SHA-256).
    """
    if not isinstance(s, str) or len(s) != length:
        return False
    try:
        int(s, 16)
    except ValueError:
        return False
    return s.lower() == s


def is_valid_identifier_hash(s: str) -> bool:
    """Return ``True`` iff ``s`` is a valid truncated identifier hash
    or the empty string (deleted-channel sentinel).
    """
    return s == "" or is_valid_sha256_hex(s, length=IDENTIFIER_HASH_LENGTH)


# =============================================================================
# Public API
# =============================================================================


__all__ = [
    # Constants
    "IDENTIFIER_HASH_LENGTH",
    "FULL_HASH_LENGTH",
    "MIN_SALT_LENGTH",
    # Primitive hashing
    "hash_bytes",
    "hash_string",
    "hash_file",
    # Identifier hashing
    "hash_identifier",
    "validate_salt",
    # Config-dict hashing
    "hash_config_dict",
    # Validation
    "is_valid_sha256_hex",
    "is_valid_identifier_hash",
]
