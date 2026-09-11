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

`key_index` is never `key_data` reused, and it is never derived *from*
`key_data`: `derive_key_index` takes the master key directly and derives
`key_index` with an info string that exists nowhere else, independently of
however `key_data` gets derived. Chaining `key_index` through `key_data`
(deriving one from the other) would mean any exposure of `key_data` -- which
happens on every encrypt/decrypt call, far more often than the master itself
is touched -- also hands over the blind-index key. Reusing or chaining key
material like that would let the blind index leak information about the
encryption key's use -- ADR-2.3 "Key management".

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


def derive_key_index(master_key: bytes) -> bytes:
    """HKDF-derive the HMAC key directly from the 32-byte master key.

    Independent of `key_data` (the AES-GCM key derived from the same
    master) -- both are derived straight from the master with distinct info
    strings, never one from the other, so exposure of `key_data` never
    reveals `key_index` -- ADR-2.3 "Key management": "Never the same key for
    both -- reusing it lets a blind index leak information about the
    encryption key's use."
    """
    if len(master_key) != KEY_LENGTH:
        raise ValueError(
            f"key must be {KEY_LENGTH} bytes for AES-256, got {len(master_key)}"
        )
    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=None,
        info=_KEY_INDEX_INFO,
    ).derive(master_key)


def compute_blind_index(plaintext: str, key_index: bytes, *, column: str) -> bytes:
    """HMAC-SHA256(key_index, normalize(plaintext))[:16] for an IDENTITY column.

    Takes the already-derived `key_index` (see `derive_key_index`) rather
    than a master or `key_data` and deriving internally -- the caller is the
    one who knows which key material it has, and deriving here would tempt a
    future caller into passing `key_data` and chaining the derivation again.

    `column` names the destination `_bidx` column's source field and is
    checked against `IDENTITY_BLIND_INDEX_COLUMNS` before anything is hashed:
    passing an amount column (or any column not on the allow-list) raises
    `ValueError` rather than silently producing a deterministic,
    frequency-analyzable index over NPI (ADR-2.4).
    """
    if column not in IDENTITY_BLIND_INDEX_COLUMNS:
        raise ValueError(
            f"refusing to compute a blind index for column {column!r}: only "
            f"{sorted(IDENTITY_BLIND_INDEX_COLUMNS)} may have one -- ADR-2.4 "
            "forbids a derived index of any kind on an amount column"
        )
    digest = hmac.new(
        key_index, normalize(plaintext).encode("utf-8"), hashlib.sha256
    ).digest()
    return digest[:BLIND_INDEX_LENGTH]
