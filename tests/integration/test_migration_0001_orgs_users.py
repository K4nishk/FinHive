"""Migration 0001 -- a user can be created and resolved to an org and role
(KCH-92 acceptance).

Requires a real Supabase Postgres reachable via TEST_DATABASE_URL or
DATABASE_URL -- skipped otherwise, per the `integration` marker's contract in
pyproject.toml. `users.id` is a foreign key into Supabase's own `auth.users`,
so this needs a database that actually has the `auth` schema (a local
`supabase start` instance or a hosted Supabase branch, not a bare Postgres
container) -- see docs/LOCAL_SETUP_MACOS.md / LOCAL_SETUP_WINDOWS.md.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

asyncpg = pytest.importorskip("asyncpg")

from finhive.db.migrations import apply_pending  # noqa: E402

pytestmark = pytest.mark.integration

_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


@pytest.mark.skipif(not _DATABASE_URL, reason="needs TEST_DATABASE_URL or DATABASE_URL")
def test_a_user_can_be_created_and_resolved_to_an_org_and_role() -> None:
    import asyncio

    async def _run() -> tuple[str, str]:
        conn = await asyncpg.connect(_DATABASE_URL)
        try:
            # Forward-only: drop anything a prior run of this test left behind
            # rather than editing an "applied" migration in place.
            await conn.execute("DROP TABLE IF EXISTS users")
            await conn.execute("DROP TABLE IF EXISTS orgs")
            await conn.execute("DROP TABLE IF EXISTS schema_migrations")

            await apply_pending(conn, _MIGRATIONS_DIR)

            org_id = await conn.fetchval(
                "INSERT INTO orgs (name) VALUES ($1) RETURNING id", "Acme Lending"
            )

            auth_user_id = uuid.uuid4()
            await conn.execute("INSERT INTO auth.users (id) VALUES ($1)", auth_user_id)
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
            await conn.close()

    resolved_org_id, resolved_role = asyncio.run(_run())

    assert resolved_role == "bookkeeper"
    assert resolved_org_id
