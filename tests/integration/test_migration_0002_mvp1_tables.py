"""Migration 0002 -- MVP1's six tables exist per-tenant in Postgres, and the
reference_id uniqueness guarantee is scoped to an org rather than global
(KCH-93 acceptance).

Requires a real Postgres reachable via TEST_DATABASE_URL or DATABASE_URL --
skipped otherwise, per the `integration` marker's contract in pyproject.toml.
Unlike 0001's test, this one doesn't need the `auth` schema, so a bare
Postgres container works, not just a Supabase instance.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

asyncpg = pytest.importorskip("asyncpg")

from finhive.db.migrations import apply_pending  # noqa: E402

pytestmark = pytest.mark.integration

_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_MVP1_TABLES = [
    "report_records",
    "reports",
    "report_meta",
    "loan_history",
    "loan_meta",
    "loans",
]


async def _reset(conn: asyncpg.Connection) -> None:
    # Forward-only: drop anything a prior run left behind rather than editing
    # an "applied" migration in place.
    for table in [*_MVP1_TABLES, "users", "orgs", "schema_migrations"]:
        await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


@pytest.mark.skipif(not _DATABASE_URL, reason="needs TEST_DATABASE_URL or DATABASE_URL")
def test_two_orgs_can_independently_reuse_the_same_reference_id() -> None:
    import asyncio

    async def _run() -> tuple[int, int]:
        conn = await asyncpg.connect(_DATABASE_URL)
        try:
            await _reset(conn)
            await apply_pending(conn, _MIGRATIONS_DIR)

            org_a = await conn.fetchval(
                "INSERT INTO orgs (name) VALUES ($1) RETURNING id", "Org A"
            )
            org_b = await conn.fetchval(
                "INSERT INTO orgs (name) VALUES ($1) RETURNING id", "Org B"
            )

            insert_loan = """
                INSERT INTO loans (
                    org_id, reference_id, borrower_name, borrower_group,
                    depositor_name, amount, giving_date, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
            for org_id in (org_a, org_b):
                await conn.execute(
                    insert_loan,
                    org_id,
                    "2026_01_001",
                    "borrower",
                    "group",
                    "depositor",
                    1000,
                    "2026-01-01",
                    "Active",
                )

            count = await conn.fetchval(
                "SELECT count(*) FROM loans WHERE reference_id = $1", "2026_01_001"
            )
            return count, 2
        finally:
            await conn.close()

    count, expected = asyncio.run(_run())

    assert count == expected


@pytest.mark.skipif(not _DATABASE_URL, reason="needs TEST_DATABASE_URL or DATABASE_URL")
def test_reference_id_must_stay_unique_within_the_same_org() -> None:
    import asyncio

    async def _run() -> bool:
        conn = await asyncpg.connect(_DATABASE_URL)
        try:
            await _reset(conn)
            await apply_pending(conn, _MIGRATIONS_DIR)

            org_id = await conn.fetchval(
                "INSERT INTO orgs (name) VALUES ($1) RETURNING id", "Org A"
            )

            insert_loan = """
                INSERT INTO loans (
                    org_id, reference_id, borrower_name, borrower_group,
                    depositor_name, amount, giving_date, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
            await conn.execute(
                insert_loan,
                org_id,
                "2026_01_001",
                "borrower",
                "group",
                "depositor",
                1000,
                "2026-01-01",
                "Active",
            )

            try:
                await conn.execute(
                    insert_loan,
                    org_id,
                    "2026_01_001",
                    "another borrower",
                    "group",
                    "depositor",
                    2000,
                    "2026-01-02",
                    "Active",
                )
            except asyncpg.UniqueViolationError:
                return True
            return False
        finally:
            await conn.close()

    raised = asyncio.run(_run())

    assert raised


@pytest.mark.skipif(not _DATABASE_URL, reason="needs TEST_DATABASE_URL or DATABASE_URL")
def test_report_record_cannot_attach_to_another_orgs_report() -> None:
    """The FK on report_records is composite on (org_id, report_id); a report
    row belonging to org A must not accept a report_record claiming org B,
    even with a matching report_id.
    """
    import asyncio

    async def _run() -> bool:
        conn = await asyncpg.connect(_DATABASE_URL)
        try:
            await _reset(conn)
            await apply_pending(conn, _MIGRATIONS_DIR)

            org_a = await conn.fetchval(
                "INSERT INTO orgs (name) VALUES ($1) RETURNING id", "Org A"
            )
            org_b = await conn.fetchval(
                "INSERT INTO orgs (name) VALUES ($1) RETURNING id", "Org B"
            )

            await conn.execute(
                "INSERT INTO reports (org_id, report_id, report_mode) "
                "VALUES ($1, $2, $3)",
                org_a,
                "20260101",
                "Daily",
            )

            insert_record = """
                INSERT INTO report_records (
                    org_id, report_id, reference_id, borrower_name,
                    depositor_name, amount, giving_date, extension_period,
                    extension_period_unit, interest_rate, commission_rate
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """
            try:
                await conn.execute(
                    insert_record,
                    org_b,
                    "20260101",
                    "2026_01_001",
                    "borrower",
                    "depositor",
                    1000,
                    "2026-01-01",
                    30,
                    "days",
                    2.5,
                    1.0,
                )
            except asyncpg.ForeignKeyViolationError:
                return True
            return False
        finally:
            await conn.close()

    raised = asyncio.run(_run())

    assert raised
