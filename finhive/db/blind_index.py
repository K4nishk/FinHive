"""HMAC blind index for encrypted IDENTITY columns only (ADR-2.3, ADR-2.4, KCH-96).

`finhive/db/encryption.py` makes `_ct` columns unusable for equality lookup by
design -- a fresh random IV means the same plaintext never encrypts to the same
ciphertext twice. This module is the other half of the ADR-2.3 pattern: a
`_bidx` column holding HMAC-SHA256(key_index, normalize(plaintext))[:16],
computed here and stored alongside the `_ct` column, so MVP1 parity checks
A1.1 (autocomplete), A1.2 (group auto-fill) and A5.8 (exact-match filtering)
keep working without ever decrypting the whole table.

`normalize()` is MVP1's own filter rule -- trim and lowercase -- so the index
is computed over exactly the value MVP1 filters, autocompletes and
group-auto-fills on.

`key_index` is never `key_data` reused, and it is never supplied by the
caller: it is derived here, via HKDF, from the same `key_data` callers pass to
`encrypt_field`, using an info string that exists nowhere else. Reusing one
key for both AES-GCM and the HMAC would let the blind index leak information
about the encryption key's use -- ADR-2.3 "Key management".

CRITICAL (ADR-2.4): a blind index must NEVER be computed for an amount
column. Loan amounts cluster on round numbers (INR 10,000, 15,000, 20,000), so
a deterministic index over them is reversible by frequency analysis without
the key -- worse than the equality leakage a blind index already accepts on
identity fields. `compute_blind_index` enforces this at runtime by rejecting
any `column` not on `IDENTITY_BLIND_INDEX_COLUMNS`;
`tests/unit/test_blind_index_lint.py` enforces it as a CI-blocking static
check over every migration file, so a future migration can't add one by
copy-pasting the identity-column pattern.
"""

from __future__ import annotations

import hashlib
import hmac

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from finhive.db.encryption import KEY_LENGTH

BLIND_INDEX_LENGTH = 16  # bytes, per ADR-2.3 (ARD v2.2.0 §1) -- truncated on purpose,
# to blunt (not eliminate) frequency analysis by introducing collisions.

# Distinct from any other info string this project derives a key with -- the
# whole point is that key_index cannot be recomputed as, or confused with, key_data.
_KEY_INDEX_INFO = b"finhive-blind-index-hmac-key-v1"

# The only columns ADR-2.3/ADR-2.4 permit a blind index on.
IDENTITY_BLIND_INDEX_COLUMNS = frozenset(
    {
        "borrower_name",
        "borrower_group",
        "depositor_name",
        "depositor_group",
    }
)

# ADR-2.4: these are NPI financial values. No derived index of any kind --
# not a blind index, not order-preserving, not format-preserving encryption.
FORBIDDEN_BLIND_INDEX_COLUMNS = frozenset(
    {
        "amount",
        "interest_amount",
        "commission_amount",
        "tds_amount",
        "chq_amount",
    }
)


def normalize(value: str) -> str:
    """MVP1's own filter rule: trim and lowercase.

    The blind index must be computed over exactly the value MVP1 filters on,
    or A5.8 (exact-match filtering) silently stops matching rows that MVP1
    itself would have matched.
    """
    return value.strip().lower()


def derive_key_index(key_data: bytes) -> bytes:
    """HKDF-derive the HMAC key from the AES key `key_data`.

    Uses an info string distinct from every other key this project derives,
    so `key_index` can never collide with, or be mistaken for, `key_data` --
    ADR-2.3 "Key management": "Never the same key for both -- reusing it lets
    a blind index leak information about the encryption key's use."
    """
    if len(key_data) != KEY_LENGTH:
        raise ValueError(f"key must be {KEY_LENGTH} bytes for AES-256, got {len(key_data)}")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=None,
        info=_KEY_INDEX_INFO,
    ).derive(key_data)


def compute_blind_index(plaintext: str, key_data: bytes, *, column: str) -> bytes:
    """HMAC-SHA256(key_index, normalize(plaintext))[:16] for an IDENTITY column.

    `column` names the destination `_bidx` column's source field and is
    checked against `IDENTITY_BLIND_INDEX_COLUMNS` before anything is hashed:
    passing an amount column (or any column not on the allow-list) raises
    `ValueError` rather than silently producing a deterministic,
    frequency-analyzable index over NPI (ADR-2.4).
    """
    if column not in IDENTITY_BLIND_INDEX_COLUMNS:
        raise ValueError(
            f"refusing to compute a blind index for column {column!r}: only "
            f"{sorted(IDENTITY_BLIND_INDEX_COLUMNS)} may have one -- ADR-2.4 forbids "
            "a derived index of any kind on an amount column"
        )
    key_index = derive_key_index(key_data)
    digest = hmac.new(key_index, normalize(plaintext).encode("utf-8"), hashlib.sha256).digest()
    return digest[:BLIND_INDEX_LENGTH]
