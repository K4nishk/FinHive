"""Migration 0001 -- orgs and users tables (KCH-92).

Requires a Postgres reachable via TEST_DATABASE_URL -- skipped otherwise,
per the ``integration`` marker's contract in pyproject.toml. A plain
container is enough: ARB D-16 replaced Supabase with local Postgres, so
``users.id`` is a locally issued UUID rather than a foreign key into
Supabase's ``auth`` schema, and this test no longer needs that schema to
exist (KCH-225, KCH-228).

It works inside a schema the integration lane owns and recreates, so it
never touches anything else in the database and must never fall back to
DATABASE_URL.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

asyncpg = pytest.importorskip("asyncpg")

from finhive.db.migrations import apply_pending  # noqa: E402

pytestmark = pytest.mark.integration

_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


from tests.integration._isolation import drop_test_schema, reset_to_clean_schema  # noqa: E402


@pytest.mark.skipif(
    not _DATABASE_URL,
    reason="needs TEST_DATABASE_URL",
)
def test_user_created_and_resolved_to_org_and_role() -> None:
    import asyncio

    async def _run() -> tuple[str, str]:
        conn = await asyncpg.connect(_DATABASE_URL)
        try:
            # Isolated schema rather than three table names: this list
            # predated migrations 0002-0005, so it left every later table
            # behind -- see tests/integration/_isolation.py.
            await reset_to_clean_schema(conn)

            await apply_pending(conn, _MIGRATIONS_DIR)

            org_id = await conn.fetchval(
                "INSERT INTO orgs (name)"
                " VALUES ($1) RETURNING id",
                "Acme Lending",
            )

            # Identity is issued locally, not by Supabase (ARB D-16,
            # KCH-228). Migration 0001 used to declare
            # `REFERENCES auth.users (id)` and this test populated that
            # Supabase-owned table to satisfy it; neither exists on local
            # Postgres, so both had to go.
            auth_user_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO users (id, org_id, role) VALUES ($1, $2, $3)",
                auth_user_id,
                org_id,
                "bookkeeper",
            )

            row = await conn.fetchrow(
                "SELECT org_id, role FROM users WHERE id = $1", auth_user_id
            )
            return str(row["org_id"]), row["role"]
        finally:
            # Schema-level teardown: dropping `users` by name fails once
            # migration 0005's foreign keys reference it.
            await drop_test_schema(conn)
            await conn.close()

    resolved_org_id, resolved_role = asyncio.run(_run())

    assert resolved_role == "bookkeeper"
    assert resolved_org_id
