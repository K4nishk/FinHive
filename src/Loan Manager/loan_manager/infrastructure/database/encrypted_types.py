"""SQLAlchemy `TypeDecorator`s that encrypt NPI at the ORM<->DB boundary
(KCH-227, ARB D-15).

Every decorator here stores `LargeBinary` and hands the ORM plain Python
values (`str`, `int`, `Decimal`) on the way in and out. The domain and
application layers never see bytes and never import this module -- they keep
working in plaintext exactly as before. Only the mapped column's *type*
changes in `models.py`; attribute names are untouched, which is what keeps
every repository and mapping function working without modification.

Crypto is `finhive.db.encryption` (AES-256-GCM, random 96-bit IV per call --
see that module for the on-disk blob format). This file does no key
management of its own: it reads the single process-wide active key via
`infrastructure.security.key_provider.active_key_data()`, which
`Container.get_key_ring()` wires up at startup (main.py step 3a already
calls it). A decorator invoked before that has happened raises
`KeyConfigurationError` -- it never falls back to writing plaintext.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import LargeBinary
from sqlalchemy.types import TypeDecorator

from finhive.db.encryption import (
    DecryptionError,
    decrypt_amount,
    decrypt_field,
    encrypt_amount,
    encrypt_field,
)
from loan_manager.infrastructure.security.key_provider import (
    active_key_data,
    candidate_key_data,
)


def _decrypt_with_any(decryptor: Any, value: bytes) -> Any:
    """Decrypt under whichever loaded key version actually produced `value`.

    Writes always use the CURRENT key (`active_key_data`), but reads must
    tolerate rows still encrypted under an older one, or rotation is a
    one-way trip that bricks the existing loan book -- see
    `candidate_key_data` for why trying each master is sound and why the
    decorator cannot simply read the row's `key_version` column.

    Re-raises the LAST failure if no key works, so the error the user sees
    is a real GCM failure rather than a swallowed one.
    """
    last: Exception | None = None
    for key in candidate_key_data():
        try:
            return decryptor(value, key)
        except DecryptionError as exc:
            last = exc
    raise last if last is not None else DecryptionError(
        "no key versions are loaded to decrypt with"
    )


class EncryptedString(TypeDecorator):
    """Transparent AES-256-GCM encryption for a plaintext identity column.

    Used for `borrower_name`, `borrower_group`, `depositor_name` and
    `depositor_group`. `None` passes through untouched in both directions --
    several of these columns stay nullable.
    """

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        return encrypt_field(value, active_key_data())

    def process_result_value(self, value: bytes | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return _decrypt_with_any(decrypt_field, value)


class EncryptedRupees(TypeDecorator):
    """Transparent encryption for `amount`, held in the domain as `int`
    whole rupees.

    Binds by converting the `int` to `Decimal` and encrypting through
    `encrypt_amount` (which canonicalizes to two decimal places); reads
    decrypt back to `Decimal` and convert to `int`.

    Only whole-rupee values are accepted on the way out. The operator
    confirmed the current single user never produces a fractional amount
    here, so a non-integral *stored* value means data corruption, not a
    legitimate case -- this raises `ValueError` naming the value rather than
    silently truncating it. If FinHive ever onboards more users and
    fractional rupee amounts become legitimate, this column should move to
    `EncryptedDecimal` instead of loosening this check.
    """

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: int | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        # Guard on the way IN, not only on the way out. Encrypting first and
        # validating on read makes this class CREATE the corruption it later
        # refuses to read: the bad write commits, and from then on every load
        # of that row -- including queries that merely touch the model --
        # raises, with no way back without the key and a manual repair.
        if isinstance(value, float):
            raise ValueError(
                f"EncryptedRupees received a float ({value!r}). Money is never "
                "float -- pass int rupees or a Decimal."
            )
        amount = Decimal(value)
        if amount != amount.to_integral_value():
            raise ValueError(
                f"EncryptedRupees accepts whole rupees only, got {value!r} -- "
                "refusing to store a value that could not be read back."
            )
        return encrypt_amount(amount, active_key_data())

    def process_result_value(self, value: bytes | None, dialect: Any) -> int | None:
        if value is None:
            return None
        decrypted = _decrypt_with_any(decrypt_amount, value)
        if decrypted != decrypted.to_integral_value():
            raise ValueError(
                f"EncryptedRupees column holds a non-integral stored value: "
                f"{decrypted!r} -- whole-rupee amounts only, this indicates "
                f"data corruption"
            )
        return int(decrypted)


class EncryptedDecimal(TypeDecorator):
    """Transparent encryption for a nullable two-decimal-place derived
    amount.

    Used for `interest_amount`, `commission_amount`, `tds_amount` and
    `chq_amount`. Unlike `amount` (see `EncryptedRupees`), these may
    legitimately carry paise, so this round-trips `Decimal` values as-is
    (quantized to two places by `encrypt_amount`/`decrypt_amount`). `None`
    passes through untouched -- these columns are all nullable.
    """

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        return encrypt_amount(value, active_key_data())

    def process_result_value(self, value: bytes | None, dialect: Any) -> Decimal | None:
        if value is None:
            return None
        return _decrypt_with_any(decrypt_amount, value)
