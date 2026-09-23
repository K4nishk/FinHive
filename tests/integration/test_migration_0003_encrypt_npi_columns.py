"""Migration 0003 -- NPI columns hold AES-256-GCM ciphertext,
not plaintext, and a tampered ciphertext fails the auth tag on
read (KCH-95 acceptance).

Requires a real, disposable Postgres reachable via
TEST_DATABASE_URL -- skipped otherwise, per the `integration`
marker's contract in pyproject.toml.

TEST_DATABASE_URL only, never DATABASE_URL: `_reset` drops all
business tables, so pointing this at an application database
would be destructive.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

asyncpg = pytest.importorskip("asyncpg")

from finhive.db.blind_index import (  # noqa: E402
    compute_blind_index,
    derive_key_index,
)
from finhive.db.encryption import (  # noqa: E402
    KEY_LENGTH,
    DecryptionError,
    decrypt_amount,
    decrypt_field,
    encrypt_amount,
    encrypt_field,
)
from finhive.db.migrations import apply_pending  # noqa: E402

pytestmark = pytest.mark.integration

_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
_MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[2] / "migrations"
)
_KEY = b"\x03" * KEY_LENGTH
_KEY_INDEX = derive_key_index(b"\x03" * KEY_LENGTH)


def _bidx(value: str, column: str) -> bytes:
    """Blind index for a `_bidx` column, NOT NULL as of migration 0004.

    This module is about 0003, but `apply_pending` applies the whole chain,
    so every insert must satisfy the FINAL schema's constraints, not 0003's.
    """
    return compute_blind_index(value, _KEY_INDEX, column=column)

_TABLES = [
    "report_records",
    "reports",
    "report_meta",
    "loan_history",
    "loan_meta",
    "loans",
]


from tests.integration._isolation import reset_to_clean_schema  # noqa: E402


async def _reset(conn: asyncpg.Connection) -> None:
    """Isolated schema, not a table list -- see tests/integration/_isolation.py.

    The previous list predated migration 0005, so it left `proposed_mutations`
    and `agent_turns` behind and the next module's `apply_pending` failed with
    DuplicateTableError.
    """
    await reset_to_clean_schema(conn)


@pytest.mark.skipif(
    not _DATABASE_URL, reason="needs TEST_DATABASE_URL"
)
def test_stored_rows_carry_no_plaintext_npi() -> None:
    """Every identity and financial NPI column, on every
    table migration 0003 touches (loans, loan_history,
    report_records) must read back as ciphertext.
    """
    plaintexts = {
        "borrower_name": "Sharma Traders",
        "borrower_group": "Sharma Group",
        "depositor_name": "Gupta Finance",
        "depositor_group": "Gupta Group",
    }
    amounts = {
        "amount": Decimal("150000.00"),
        "interest_amount": Decimal("4500.00"),
        "commission_amount": Decimal("900.00"),
        "tds_amount": Decimal("450.00"),
        "chq_amount": Decimal("4050.00"),
    }

    async def _run() -> dict[str, bytes]:
        conn = await asyncpg.connect(_DATABASE_URL)
        try:
            await _reset(conn)
            await apply_pending(conn, _MIGRATIONS_DIR)

            org_id = await conn.fetchval(
                "INSERT INTO orgs (name)"
                " VALUES ($1) RETURNING id",
                "Org A",
            )

            await conn.execute(
                """
                INSERT INTO loans (
                    org_id, reference_id,
                    borrower_name_ct, borrower_name_bidx,
                    borrower_group_ct, borrower_group_bidx,
                    depositor_name_ct, depositor_name_bidx,
                    depositor_group_ct,
                    amount_ct, giving_date, status
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12
                )
                """,
                org_id,
                "2026_01_001",
                encrypt_field(
                    plaintexts["borrower_name"], _KEY
                ),
                _bidx(plaintexts["borrower_name"], "borrower_name"),
                encrypt_field(
                    plaintexts["borrower_group"], _KEY
                ),
                _bidx(plaintexts["borrower_group"], "borrower_group"),
                encrypt_field(
                    plaintexts["depositor_name"], _KEY
                ),
                _bidx(plaintexts["depositor_name"], "depositor_name"),
                encrypt_field(
                    plaintexts["depositor_group"], _KEY
                ),
                encrypt_amount(amounts["amount"], _KEY),
                date(2026, 1, 1),
                "Active",
            )

            await conn.execute(
                """
                INSERT INTO loan_history (
                    org_id, reference_id,
                    borrower_name_ct, borrower_name_bidx,
                    borrower_group_ct, borrower_group_bidx,
                    depositor_name_ct, depositor_name_bidx,
                    depositor_group_ct,
                    amount_ct, giving_date
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11
                )
                """,
                org_id,
                "2026_01_001",
                encrypt_field(
                    plaintexts["borrower_name"], _KEY
                ),
                _bidx(plaintexts["borrower_name"], "borrower_name"),
                encrypt_field(
                    plaintexts["borrower_group"], _KEY
                ),
                _bidx(plaintexts["borrower_group"], "borrower_group"),
                encrypt_field(
                    plaintexts["depositor_name"], _KEY
                ),
                _bidx(plaintexts["depositor_name"], "depositor_name"),
                encrypt_field(
                    plaintexts["depositor_group"], _KEY
                ),
                encrypt_amount(amounts["amount"], _KEY),
                date(2026, 1, 1),
            )

            await conn.execute(
                "INSERT INTO reports"
                " (org_id, report_id, report_mode)"
                " VALUES ($1, $2, $3)",
                org_id,
                "2026_01_001",
                "Daily",
            )
            await conn.execute(
                """
                INSERT INTO report_records (
                    org_id, report_id,
                    reference_id,
                    borrower_name_ct, borrower_name_bidx,
                    depositor_name_ct, depositor_name_bidx,
                    depositor_group_ct,
                    amount_ct, giving_date,
                    extension_period,
                    extension_period_unit,
                    interest_rate,
                    commission_rate,
                    interest_amount_ct,
                    commission_amount_ct,
                    tds_amount_ct,
                    chq_amount_ct
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,
                    $9,$10,$11,$12,$13,$14,
                    $15,$16,$17,$18
                )
                """,
                org_id,
                "2026_01_001",
                "2026_01_001",
                encrypt_field(
                    plaintexts["borrower_name"], _KEY
                ),
                _bidx(plaintexts["borrower_name"], "borrower_name"),
                encrypt_field(
                    plaintexts["depositor_name"], _KEY
                ),
                _bidx(plaintexts["depositor_name"], "depositor_name"),
                encrypt_field(
                    plaintexts["depositor_group"], _KEY
                ),
                encrypt_amount(amounts["amount"], _KEY),
                date(2026, 1, 1),
                30,
                "days",
                Decimal("12.00"),
                Decimal("2.00"),
                encrypt_amount(
                    amounts["interest_amount"], _KEY
                ),
                encrypt_amount(
                    amounts["commission_amount"], _KEY
                ),
                encrypt_amount(
                    amounts["tds_amount"], _KEY
                ),
                encrypt_amount(
                    amounts["chq_amount"], _KEY
                ),
            )

            loan = await conn.fetchrow(
                "SELECT borrower_name_ct,"
                " borrower_group_ct,"
                " depositor_name_ct,"
                " depositor_group_ct,"
                " amount_ct, key_version"
                " FROM loans"
                " WHERE reference_id = $1",
                "2026_01_001",
            )
            hist = await conn.fetchrow(
                "SELECT borrower_name_ct,"
                " borrower_group_ct,"
                " depositor_name_ct,"
                " depositor_group_ct,"
                " amount_ct, key_version"
                " FROM loan_history"
                " WHERE reference_id = $1",
                "2026_01_001",
            )
            rr = await conn.fetchrow(
                "SELECT borrower_name_ct,"
                " depositor_name_ct,"
                " depositor_group_ct,"
                " amount_ct,"
                " interest_amount_ct,"
                " commission_amount_ct,"
                " tds_amount_ct,"
                " chq_amount_ct,"
                " key_version"
                " FROM report_records"
                " WHERE reference_id = $1",
                "2026_01_001",
            )
            return {
                "l.bn": loan["borrower_name_ct"],
                "l.bg": loan["borrower_group_ct"],
                "l.dn": loan["depositor_name_ct"],
                "l.dg": loan["depositor_group_ct"],
                "l.amt": loan["amount_ct"],
                "l.kv": loan["key_version"],
                "h.bn": hist["borrower_name_ct"],
                "h.bg": hist["borrower_group_ct"],
                "h.dn": hist["depositor_name_ct"],
                "h.dg": hist["depositor_group_ct"],
                "h.amt": hist["amount_ct"],
                "h.kv": hist["key_version"],
                "rr.bn": rr["borrower_name_ct"],
                "rr.dn": rr["depositor_name_ct"],
                "rr.dg": rr["depositor_group_ct"],
                "rr.amt": rr["amount_ct"],
                "rr.int": rr["interest_amount_ct"],
                "rr.com": rr["commission_amount_ct"],
                "rr.tds": rr["tds_amount_ct"],
                "rr.chq": rr["chq_amount_ct"],
                "rr.kv": rr["key_version"],
            }
        finally:
            await _reset(conn)
            await conn.close()

    stored = asyncio.run(_run())

    id_cols = [
        c for c in stored
        if c.endswith(".bn")
        or c.endswith(".bg")
        or c.endswith(".dn")
        or c.endswith(".dg")
    ]
    amt_cols = [
        c for c in stored
        if c.endswith(".amt")
        or c.endswith(".int")
        or c.endswith(".com")
        or c.endswith(".tds")
        or c.endswith(".chq")
    ]
    assert id_cols and amt_cols, (
        "test setup must exercise both NPI kinds"
    )

    for plaintext in plaintexts.values():
        encoded = plaintext.encode("utf-8")
        for col in id_cols:
            assert encoded not in stored[col], (
                f"{col} stored"
                f" {plaintext!r} in the clear"
            )

    for amount in amounts.values():
        for rep in (str(amount), str(int(amount))):
            encoded = rep.encode("utf-8")
            for col in amt_cols:
                assert encoded not in stored[col], (
                    f"{col} stored"
                    f" {rep!r} in the clear"
                )

    assert (
        decrypt_field(stored["l.bn"], _KEY)
        == plaintexts["borrower_name"]
    )
    assert (
        decrypt_field(stored["l.bg"], _KEY)
        == plaintexts["borrower_group"]
    )
    assert (
        decrypt_field(stored["l.dn"], _KEY)
        == plaintexts["depositor_name"]
    )
    assert (
        decrypt_field(stored["l.dg"], _KEY)
        == plaintexts["depositor_group"]
    )
    assert (
        decrypt_amount(stored["l.amt"], _KEY)
        == amounts["amount"]
    )

    assert (
        decrypt_field(stored["h.bn"], _KEY)
        == plaintexts["borrower_name"]
    )
    assert (
        decrypt_amount(stored["h.amt"], _KEY)
        == amounts["amount"]
    )

    assert (
        decrypt_field(stored["rr.bn"], _KEY)
        == plaintexts["borrower_name"]
    )
    assert (
        decrypt_amount(stored["rr.amt"], _KEY)
        == amounts["amount"]
    )
    assert (
        decrypt_amount(stored["rr.int"], _KEY)
        == amounts["interest_amount"]
    )
    assert (
        decrypt_amount(stored["rr.com"], _KEY)
        == amounts["commission_amount"]
    )
    assert (
        decrypt_amount(stored["rr.tds"], _KEY)
        == amounts["tds_amount"]
    )
    assert (
        decrypt_amount(stored["rr.chq"], _KEY)
        == amounts["chq_amount"]
    )

    assert stored["l.kv"] == 1
    assert stored["h.kv"] == 1
    assert stored["rr.kv"] == 1


@pytest.mark.skipif(
    not _DATABASE_URL, reason="needs TEST_DATABASE_URL"
)
def test_tampered_ct_from_postgres_fails_auth_tag() -> None:
    async def _run() -> bytes:
        conn = await asyncpg.connect(_DATABASE_URL)
        try:
            await _reset(conn)
            await apply_pending(conn, _MIGRATIONS_DIR)

            org_id = await conn.fetchval(
                "INSERT INTO orgs (name)"
                " VALUES ($1) RETURNING id",
                "Org A",
            )
            await conn.execute(
                """
                INSERT INTO loans (
                    org_id, reference_id,
                    borrower_name_ct, borrower_name_bidx,
                    borrower_group_ct, borrower_group_bidx,
                    depositor_name_ct, depositor_name_bidx,
                    amount_ct, giving_date, status
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11
                )
                """,
                org_id,
                "2026_01_001",
                encrypt_field("Sharma Traders", _KEY),
                _bidx("Sharma Traders", "borrower_name"),
                encrypt_field("group", _KEY),
                _bidx("group", "borrower_group"),
                encrypt_field("depositor", _KEY),
                _bidx("depositor", "depositor_name"),
                encrypt_field("150000", _KEY),
                date(2026, 1, 1),
                "Active",
            )

            tampered = bytearray(
                await conn.fetchval(
                    "SELECT amount_ct"
                    " FROM loans"
                    " WHERE reference_id = $1",
                    "2026_01_001",
                )
            )
            tampered[-1] ^= 0xFF
            await conn.execute(
                "UPDATE loans"
                " SET amount_ct = $1"
                " WHERE reference_id = $2",
                bytes(tampered),
                "2026_01_001",
            )

            return await conn.fetchval(
                "SELECT amount_ct"
                " FROM loans"
                " WHERE reference_id = $1",
                "2026_01_001",
            )
        finally:
            await _reset(conn)
            await conn.close()

    tampered_amount_ct = asyncio.run(_run())

    with pytest.raises(DecryptionError):
        decrypt_field(tampered_amount_ct, _KEY)
