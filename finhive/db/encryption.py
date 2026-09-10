"""AES-256-GCM encryption at rest for NPI fields (ADR-2.3, ADR-2.4, KCH-95).

Every identity field (borrower_name, borrower_group, depositor_name,
depositor_group) and every financial value (amount, interest_amount,
commission_amount, tds_amount, chq_amount) is encrypted with AES-256-GCM
before it reaches a `_ct` column, and decrypted here on the way back out.
Rates and periods are intentionally out of scope -- ADR-2.4's derivation
check is what makes leaving them plaintext safe.

The stored blob is `iv || ciphertext || tag`: a fresh random 96-bit IV per
call (never reused -- reuse is what breaks GCM), followed by the ciphertext
with its 16-byte authentication tag appended, exactly as
`cryptography.hazmat.primitives.ciphers.aead.AESGCM` produces it. A random
IV means the same plaintext encrypts differently every time, which is why
equality lookups on these columns need the separate HMAC blind index
(KCH-96) rather than comparing `_ct` values directly.

No key derivation or storage lives here -- callers supply a raw 32-byte
`key_data` (see KCH-97 for HKDF derivation and rotation via `key_version`).
"""

from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

IV_LENGTH = 12  # 96 bits, per ADR-2.3/2.4
KEY_LENGTH = 32  # AES-256


class DecryptionError(Exception):
    """Ciphertext failed the GCM authentication tag check.

    Raised on a tampered blob or the wrong key -- never on malformed input
    silently decrypting to garbage, which is the property AES-GCM buys over
    an unauthenticated cipher.
    """


def _require_key_length(key: bytes) -> None:
    if len(key) != KEY_LENGTH:
        raise ValueError(f"key must be {KEY_LENGTH} bytes for AES-256, got {len(key)}")


def encrypt_field(plaintext: str, key: bytes) -> bytes:
    """Encrypt `plaintext` for storage in a `_ct` column.

    Returns `iv || ciphertext || tag`. Two calls with the same plaintext and
    key produce different output, by design -- the IV is drawn fresh from
    `os.urandom` every time.
    """
    _require_key_length(key)
    iv = os.urandom(IV_LENGTH)
    ciphertext = AESGCM(key).encrypt(iv, plaintext.encode("utf-8"), None)
    return iv + ciphertext


def decrypt_field(blob: bytes, key: bytes) -> str:
    """Decrypt a blob produced by `encrypt_field`.

    Raises `DecryptionError` if the auth tag doesn't verify -- a tampered
    ciphertext or the wrong key -- rather than returning corrupted plaintext.
    """
    _require_key_length(key)
    iv, ciphertext = blob[:IV_LENGTH], blob[IV_LENGTH:]
    try:
        plaintext = AESGCM(key).decrypt(iv, ciphertext, None)
    except InvalidTag as exc:
        raise DecryptionError("ciphertext failed GCM authentication tag check") from exc
    return plaintext.decode("utf-8")
