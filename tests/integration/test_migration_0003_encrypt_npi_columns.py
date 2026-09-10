"""Migration 0003 -- NPI columns hold AES-256-GCM ciphertext, not plaintext,
and a tampered ciphertext fails the auth tag on read (KCH-95 acceptance).

Requires a real, disposable Postgres reachable via TEST_DATABASE_URL --
skipped otherwise, per the `integration` marker's contract in pyproject.toml.

TEST_DATABASE_URL only, never DATABASE_URL: `_reset` drops all business
tables, so pointing this at an application database would be destructive.

The plaintext-storage check below reads back every identity and financial
NPI column across all three tables this migration touches (loans,
loan_history, report_records) through ordinary SQL. It does not inspect
WAL segments or on-disk page files -- that needs filesystem or superuser
access this suite does not assume the target Postgres grants (TEST_DATABASE_URL
may point at a disposable Supabase branch, not a local instance) -- so a
row surviving in the WAL after a crash, outside any column this migration
defines, is out of scope here.
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pytest

asyncpg = pytest.importorskip("asyncpg")

from finhive.db.encryption import (
    KEY_LENGTH,
    DecryptionError,
    decrypt_amount,
    decrypt_field,
    encrypt_amount,
    encrypt_field,
)
from finhive.db.migrations import apply_pending

pytestmark = pytest.mark.integration

_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
_KEY = b"\x03" * KEY_LENGTH

_TABLES = [
    "report_records",
    "reports",
    "report_meta",
    "loan_history",
    "loan_meta",
    "loans",
]


async def _reset(conn: asyncpg.Connection) -> None:
    for table in [*_TABLES, "users", "orgs", "schema_migrations"]:
        await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


@pytest.mark.skipif(not _DATABASE_URL, reason="needs TEST_DATABASE_URL")
def test_stored_rows_carry_no_plaintext_identity_or_financial_value() -> None:
    """Every identity and financial NPI column, on every table migration
    0003 touches (loans, loan_history, report_records) -- not just one
    table's borrower_name and amount -- must read back as ciphertext.
    """
    import asyncio

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
                "INSERT INTO orgs (name) VALUES ($1) RETURNING id", "Org A"
            )

            await conn.execute(
                """
                INSERT INTO loans (
                    org_id, reference_id, borrower_name_ct, borrower_group_ct,
                    depositor_name_ct, depositor_group_ct, amount_ct, giving_date, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                org_id,
                "2026_01_001",
                encrypt_field(plaintexts["borrower_name"], _KEY),
                encrypt_field(plaintexts["borrower_group"], _KEY),
                encrypt_field(plaintexts["depositor_name"], _KEY),
                encrypt_field(plaintexts["depositor_group"], _KEY),
                encrypt_amount(amounts["amount"], _KEY),
                "2026-01-01",
                "Active",
            )

            await conn.execute(
                """
                INSERT INTO loan_history (
                    org_id, reference_id, borrower_name_ct, borrower_group_ct,
                    depositor_name_ct, depositor_group_ct, amount_ct, giving_date
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                org_id,
                "2026_01_001",
                encrypt_field(plaintexts["borrower_name"], _KEY),
                encrypt_field(plaintexts["borrower_group"], _KEY),
                encrypt_field(plaintexts["depositor_name"], _KEY),
                encrypt_field(plaintexts["depositor_group"], _KEY),
                encrypt_amount(amounts["amount"], _KEY),
                "2026-01-01",
            )

            await conn.execute(
                "INSERT INTO reports (org_id, report_id, report_mode) VALUES ($1, $2, $3)",
                org_id,
                "2026_01_001",
                "Daily",
            )
            await conn.execute(
                """
                INSERT INTO report_records (
                    org_id, report_id, reference_id, borrower_name_ct, depositor_name_ct,
                    depositor_group_ct, amount_ct, giving_date, extension_period,
                    extension_period_unit, interest_rate, commission_rate,
                    interest_amount_ct, commission_amount_ct, tds_amount_ct, chq_amount_ct
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                """,
                org_id,
                "2026_01_001",
                "2026_01_001",
                encrypt_field(plaintexts["borrower_name"], _KEY),
                encrypt_field(plaintexts["depositor_name"], _KEY),
                encrypt_field(plaintexts["depositor_group"], _KEY),
                encrypt_amount(amounts["amount"], _KEY),
                "2026-01-01",
                30,
                "days",
                Decimal("12.00"),
                Decimal("2.00"),
                encrypt_amount(amounts["interest_amount"], _KEY),
                encrypt_amount(amounts["commission_amount"], _KEY),
                encrypt_amount(amounts["tds_amount"], _KEY),
                encrypt_amount(amounts["chq_amount"], _KEY),
            )

            loan_row = await conn.fetchrow(
                """
                SELECT borrower_name_ct, borrower_group_ct, depositor_name_ct,
                       depositor_group_ct, amount_ct
                FROM loans WHERE reference_id = $1
                """,
                "2026_01_001",
            )
            history_row = await conn.fetchrow(
                """
                SELECT borrower_name_ct, borrower_group_ct, depositor_name_ct,
                       depositor_group_ct, amount_ct
                FROM loan_history WHERE reference_id = $1
                """,
                "2026_01_001",
            )
            report_row = await conn.fetchrow(
                """
                SELECT borrower_name_ct, depositor_name_ct, depositor_group_ct, amount_ct,
                       interest_amount_ct, commission_amount_ct, tds_amount_ct, chq_amount_ct
                FROM report_records WHERE reference_id = $1
                """,
                "2026_01_001",
            )
            return {
                "loans.borrower_name_ct": loan_row["borrower_name_ct"],
                "loans.borrower_group_ct": loan_row["borrower_group_ct"],
                "loans.depositor_name_ct": loan_row["depositor_name_ct"],
                "loans.depositor_group_ct": loan_row["depositor_group_ct"],
                "loans.amount_ct": loan_row["amount_ct"],
                "loan_history.borrower_name_ct": history_row["borrower_name_ct"],
                "loan_history.borrower_group_ct": history_row["borrower_group_ct"],
                "loan_history.depositor_name_ct": history_row["depositor_name_ct"],
                "loan_history.depositor_group_ct": history_row["depositor_group_ct"],
                "loan_history.amount_ct": history_row["amount_ct"],
                "report_records.borrower_name_ct": report_row["borrower_name_ct"],
                "report_records.depositor_name_ct": report_row["depositor_name_ct"],
                "report_records.depositor_group_ct": report_row["depositor_group_ct"],
                "report_records.amount_ct": report_row["amount_ct"],
                "report_records.interest_amount_ct": report_row["interest_amount_ct"],
                "report_records.commission_amount_ct": report_row["commission_amount_ct"],
                "report_records.tds_amount_ct": report_row["tds_amount_ct"],
                "report_records.chq_amount_ct": report_row["chq_amount_ct"],
            }
        finally:
            await conn.close()

    stored = asyncio.run(_run())

    identity_columns = [col for col in stored if "name_ct" in col or "group_ct" in col]
    amount_columns = [col for col in stored if "amount_ct" in col]
    assert identity_columns and amount_columns, "test setup must exercise both NPI kinds"

    for plaintext in plaintexts.values():
        encoded = plaintext.encode("utf-8")
        for column in identity_columns:
            assert encoded not in stored[column], f"{column} stored {plaintext!r} in the clear"

    for amount in amounts.values():
        for representation in (str(amount), str(int(amount))):
            encoded = representation.encode("utf-8")
            for column in amount_columns:
                assert encoded not in stored[column], (
                    f"{column} stored {representation!r} in the clear"
                )

    assert decrypt_field(stored["loans.borrower_name_ct"], _KEY) == plaintexts["borrower_name"]
    assert decrypt_field(stored["loans.borrower_group_ct"], _KEY) == plaintexts["borrower_group"]
    assert decrypt_field(stored["loans.depositor_name_ct"], _KEY) == plaintexts["depositor_name"]
    assert (
        decrypt_field(stored["loans.depositor_group_ct"], _KEY) == plaintexts["depositor_group"]
    )
    assert decrypt_amount(stored["loans.amount_ct"], _KEY) == amounts["amount"]

    assert (
        decrypt_field(stored["loan_history.borrower_name_ct"], _KEY)
        == plaintexts["borrower_name"]
    )
    assert decrypt_amount(stored["loan_history.amount_ct"], _KEY) == amounts["amount"]

    assert (
        decrypt_field(stored["report_records.borrower_name_ct"], _KEY)
        == plaintexts["borrower_name"]
    )
    assert decrypt_amount(stored["report_records.amount_ct"], _KEY) == amounts["amount"]
    assert (
        decrypt_amount(stored["report_records.interest_amount_ct"], _KEY)
        == amounts["interest_amount"]
    )
    assert (
        decrypt_amount(stored["report_records.commission_amount_ct"], _KEY)
        == amounts["commission_amount"]
    )
    assert decrypt_amount(stored["report_records.tds_amount_ct"], _KEY) == amounts["tds_amount"]
    assert decrypt_amount(stored["report_records.chq_amount_ct"], _KEY) == amounts["chq_amount"]


@pytest.mark.skipif(not _DATABASE_URL, reason="needs TEST_DATABASE_URL")
def test_tampered_ciphertext_read_back_from_postgres_fails_the_auth_tag() -> None:
    import asyncio

    async def _run() -> bytes:
        conn = await asyncpg.connect(_DATABASE_URL)
        try:
            await _reset(conn)
            await apply_pending(conn, _MIGRATIONS_DIR)

            org_id = await conn.fetchval(
                "INSERT INTO orgs (name) VALUES ($1) RETURNING id", "Org A"
            )
            await conn.execute(
                """
                INSERT INTO loans (
                    org_id, reference_id, borrower_name_ct, borrower_group_ct,
                    depositor_name_ct, amount_ct, giving_date, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                org_id,
                "2026_01_001",
                encrypt_field("Sharma Traders", _KEY),
                encrypt_field("group", _KEY),
                encrypt_field("depositor", _KEY),
                encrypt_field("150000", _KEY),
                "2026-01-01",
                "Active",
            )

            tampered = bytearray(
                await conn.fetchval(
                    "SELECT amount_ct FROM loans WHERE reference_id = $1", "2026_01_001"
                )
            )
            tampered[-1] ^= 0xFF
            await conn.execute(
                "UPDATE loans SET amount_ct = $1 WHERE reference_id = $2",
                bytes(tampered),
                "2026_01_001",
            )

            return await conn.fetchval(
                "SELECT amount_ct FROM loans WHERE reference_id = $1", "2026_01_001"
            )
        finally:
            await conn.close()

    tampered_amount_ct = asyncio.run(_run())

    with pytest.raises(DecryptionError):
        decrypt_field(tampered_amount_ct, _KEY)
