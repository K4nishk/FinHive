"""AES-256-GCM field encryption (ADR-2.3, ADR-2.4, KCH-95).

Covers the crypto primitive in isolation: round trip, the random-IV property
that motivates the separate blind index (KCH-96), and that a tampered blob
or wrong key fails the auth tag rather than decrypting to garbage.
"""

from __future__ import annotations

import os

import pytest

from finhive.db.encryption import (
    IV_LENGTH,
    KEY_LENGTH,
    DecryptionError,
    decrypt_field,
    encrypt_field,
)

_KEY = b"\x01" * KEY_LENGTH
_OTHER_KEY = b"\x02" * KEY_LENGTH


def test_round_trip_returns_the_original_plaintext() -> None:
    blob = encrypt_field("Sharma Traders", _KEY)

    assert decrypt_field(blob, _KEY) == "Sharma Traders"


def test_round_trip_preserves_a_financial_value_encoded_as_a_string() -> None:
    blob = encrypt_field("150000", _KEY)

    assert decrypt_field(blob, _KEY) == "150000"


def test_ciphertext_never_contains_the_plaintext() -> None:
    plaintext = "Sharma Traders"
    blob = encrypt_field(plaintext, _KEY)

    assert plaintext.encode("utf-8") not in blob


def test_same_plaintext_encrypts_differently_each_call() -> None:
    """A random IV per call -- equality on `_ct` values must never work
    directly, which is why exact-match filtering needs the separate HMAC
    blind index (KCH-96) rather than comparing ciphertext.
    """
    first = encrypt_field("Sharma Traders", _KEY)
    second = encrypt_field("Sharma Traders", _KEY)

    assert first != second
    assert decrypt_field(first, _KEY) == decrypt_field(second, _KEY)


def test_blob_starts_with_a_96_bit_iv() -> None:
    blob = encrypt_field("Sharma Traders", _KEY)

    assert len(blob) >= IV_LENGTH


def test_tampered_ciphertext_fails_the_auth_tag_instead_of_decrypting() -> None:
    blob = bytearray(encrypt_field("Sharma Traders", _KEY))
    blob[-1] ^= 0xFF  # flip a bit inside the auth tag

    with pytest.raises(DecryptionError):
        decrypt_field(bytes(blob), _KEY)


def test_wrong_key_fails_the_auth_tag() -> None:
    blob = encrypt_field("Sharma Traders", _KEY)

    with pytest.raises(DecryptionError):
        decrypt_field(blob, _OTHER_KEY)


def test_truncated_blob_fails_the_auth_tag() -> None:
    blob = encrypt_field("Sharma Traders", _KEY)

    with pytest.raises(DecryptionError):
        decrypt_field(blob[:-1], _KEY)


@pytest.mark.parametrize("bad_key", [os.urandom(16), os.urandom(31), os.urandom(33)])
def test_encrypt_rejects_a_key_that_is_not_32_bytes(bad_key: bytes) -> None:
    with pytest.raises(ValueError):
        encrypt_field("Sharma Traders", bad_key)


@pytest.mark.parametrize("bad_key", [os.urandom(16), os.urandom(31), os.urandom(33)])
def test_decrypt_rejects_a_key_that_is_not_32_bytes(bad_key: bytes) -> None:
    blob = encrypt_field("Sharma Traders", _KEY)

    with pytest.raises(ValueError):
        decrypt_field(blob, bad_key)
