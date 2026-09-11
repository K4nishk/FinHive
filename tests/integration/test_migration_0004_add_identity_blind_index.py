"""Migration 0004 -- HMAC blind index makes MVP1 parity checks A1.1
(autocomplete), A1.2 (group auto-fill) and A5.8 (exact-match filtering) work
against ciphertext identity columns (KCH-96 acceptance).

Requires a real, disposable Postgres reachable via TEST_DATABASE_URL --
skipped otherwise, per the `integration` marker's contract in pyproject.toml.
Mirrors tests/integration/test_migration_0003_encrypt_npi_columns.py.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

asyncpg = pytest.importorskip("asyncpg")

from finhive.db.blind_index import compute_blind_index
from finhive.db.encryption import KEY_LENGTH, decrypt_field, encrypt_field
from finhive.db.migrations import apply_pending

pytestmark = pytest.mark.integration

_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
_KEY = b"\x04" * KEY_LENGTH

_TABLES = ["report_records", "reports", "report_meta", "loan_history", "loan_meta", "loans"]


async def _reset(conn: "asyncpg.Connection") -> None:
    for table in [*_TABLES, "users", "orgs", "schema_migrations"]:
        await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


async def _insert_loan(
    conn: "asyncpg.Connection",
    org_id: str,
    reference_id: str,
    borrower_name: str,
    borrower_group: str,
    depositor_name: str,
) -> None:
    await conn.execute(
        """
        INSERT INTO loans (
            org_id, reference_id,
            borrower_name_ct, borrower_name_bidx,
            borrower_group_ct, borrower_group_bidx,
            depositor_name_ct, depositor_name_bidx,
            amount_ct, giving_date, status
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """,
        org_id,
        reference_id,
        encrypt_field(borrower_name, _KEY),
        compute_blind_index(borrower_name, _KEY, column="borrower_name"),
        encrypt_field(borrower_group, _KEY),
        compute_blind_index(borrower_group, _KEY, column="borrower_group"),
        encrypt_field(depositor_name, _KEY),
        compute_blind_index(depositor_name, _KEY, column="depositor_name"),
        encrypt_field("150000.00", _KEY),
        "2026-01-01",
        "Active",
    )


@pytest.mark.skipif(not _DATABASE_URL, reason="needs TEST_DATABASE_URL")
def test_exact_match_autocomplete_and_group_auto_fill_survive_encryption() -> None:
    async def _run() -> dict[str, object]:
        conn = await asyncpg.connect(_DATABASE_URL)
        try:
            await _reset(conn)
            await apply_pending(conn, _MIGRATIONS_DIR)

            org_id = await conn.fetchval(
                "INSERT INTO orgs (name) VALUES ($1) RETURNING id", "Org A"
            )
            await _insert_loan(
                conn, org_id, "2026_01_001", "Sharma Traders", "Sharma Group", "Gupta Finance"
            )
            await _insert_loan(
                conn, org_id, "2026_01_002", "sharma traders", "Sharma Group", "Patel Finance"
            )
            await _insert_loan(
                conn, org_id, "2026_01_003", "Verma Traders", "Verma Group", "Gupta Finance"
            )

            # A5.8 -- exact-match filtering: a differently-cased/padded query
            # still finds every row MVP1's own normalize-then-filter rule would.
            query_index = compute_blind_index(
                "  SHARMA TRADERS  ", _KEY, column="borrower_name"
            )
            exact_match_rows = await conn.fetch(
                "SELECT reference_id FROM loans WHERE borrower_name_bidx = $1 ORDER BY reference_id",
                query_index,
            )

            # A1.1 -- autocomplete: distinct blind indexes group identical
            # normalized names without decrypting the whole table.
            distinct_rows = await conn.fetch(
                "SELECT DISTINCT borrower_name_bidx, borrower_name_ct FROM loans"
            )

            # A1.2 -- group auto-fill: looking a borrower up by name resolves
            # their group deterministically.
            group_row = await conn.fetchrow(
                "SELECT borrower_group_ct FROM loans WHERE borrower_name_bidx = $1 LIMIT 1",
                compute_blind_index("Sharma Traders", _KEY, column="borrower_name"),
            )

            return {
                "exact_match_reference_ids": [r["reference_id"] for r in exact_match_rows],
                "distinct_names": sorted(
                    decrypt_field(r["borrower_name_ct"], _KEY) for r in distinct_rows
                ),
                "auto_filled_group": decrypt_field(group_row["borrower_group_ct"], _KEY),
            }
        finally:
            await conn.close()

    result = asyncio.run(_run())

    assert result["exact_match_reference_ids"] == ["2026_01_001", "2026_01_002"]
    assert result["distinct_names"] == ["Sharma Traders", "Verma Traders", "sharma traders"]
    assert result["auto_filled_group"] == "Sharma Group"
