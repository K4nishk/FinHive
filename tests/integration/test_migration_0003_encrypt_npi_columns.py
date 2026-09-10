"""Migration 0003 -- NPI columns hold AES-256-GCM ciphertext, not plaintext,
and a tampered ciphertext fails the auth tag on read (KCH-95 acceptance).

Requires a real, disposable Postgres reachable via TEST_DATABASE_URL --
skipped otherwise, per the `integration` marker's contract in pyproject.toml.

TEST_DATABASE_URL only, never DATABASE_URL: `_reset` drops all business
tables, so pointing this at an application database would be destructive.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

asyncpg = pytest.importorskip("asyncpg")

from finhive.db.encryption import KEY_LENGTH, DecryptionError, decrypt_field, encrypt_field
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
def test_stored_loan_row_carries_no_plaintext_name_or_amount() -> None:
    import asyncio

    borrower_name = "Sharma Traders"
    amount = "150000"

    async def _run() -> tuple[bytes, bytes]:
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
                encrypt_field(borrower_name, _KEY),
                encrypt_field("group", _KEY),
                encrypt_field("depositor", _KEY),
                encrypt_field(amount, _KEY),
                "2026-01-01",
                "Active",
            )

            row = await conn.fetchrow(
                "SELECT borrower_name_ct, amount_ct FROM loans WHERE reference_id = $1",
                "2026_01_001",
            )
            return row["borrower_name_ct"], row["amount_ct"]
        finally:
            await conn.close()

    borrower_ct, amount_ct = asyncio.run(_run())

    assert borrower_name.encode("utf-8") not in borrower_ct
    assert amount.encode("utf-8") not in amount_ct
    assert decrypt_field(borrower_ct, _KEY) == borrower_name
    assert decrypt_field(amount_ct, _KEY) == amount


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
