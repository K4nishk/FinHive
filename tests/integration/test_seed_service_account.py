"""finhive/db/seed_service_account.py -- MVP1 owner service account seed
(KCH-94 acceptance): seeding twice is idempotent and resolves to a real
org_id with role=owner.

Requires a real Supabase instance -- a local `supabase start` or a hosted
branch -- reachable via TEST_DATABASE_URL/DATABASE_URL, SUPABASE_URL and
SUPABASE_SERVICE_ROLE_KEY. Skipped otherwise, per the `integration` marker's
contract in pyproject.toml. Needs the `auth` schema (users.id references
auth.users), so a bare Postgres container is not enough -- see
docs/LOCAL_SETUP_MACOS.md / LOCAL_SETUP_WINDOWS.md.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

asyncpg = pytest.importorskip("asyncpg")

from finhive.db.admin import AdminClient  # noqa: E402
from finhive.db.migrations import apply_pending  # noqa: E402
from finhive.db.seed_service_account import SeedConfig, seed_service_account  # noqa: E402

pytestmark = pytest.mark.integration

_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
_SUPABASE_URL = os.environ.get("SUPABASE_URL")
_SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_REQUIRES = not (_DATABASE_URL and _SUPABASE_URL and _SUPABASE_SERVICE_ROLE_KEY)


@pytest.mark.skipif(
    _REQUIRES,
    reason="needs TEST_DATABASE_URL/DATABASE_URL, SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY",
)
def test_seeding_twice_resolves_to_one_real_org_and_role_owner() -> None:
    import asyncio

    async def _run() -> tuple[str, str, str, str]:
        conn = await asyncpg.connect(_DATABASE_URL)
        try:
            # Forward-only: drop anything a prior run of this test left behind
            # rather than editing an "applied" migration in place.
            await conn.execute("DROP TABLE IF EXISTS users")
            await conn.execute("DROP TABLE IF EXISTS orgs")
            await conn.execute("DROP TABLE IF EXISTS schema_migrations")

            await apply_pending(conn, _MIGRATIONS_DIR)

            email = f"kch-94-{uuid.uuid4().hex[:12]}@example.invalid"
            config = SeedConfig(
                database_url=_DATABASE_URL,
                supabase_url=_SUPABASE_URL,
                supabase_service_role_key=_SUPABASE_SERVICE_ROLE_KEY,
                owner_email=email,
                owner_password="kch-94-integration-test-password",
                org_name=f"KCH-94 test org {uuid.uuid4().hex[:8]}",
            )
            admin = AdminClient(_SUPABASE_URL, _SUPABASE_SERVICE_ROLE_KEY)

            first_org, first_user = await seed_service_account(conn, admin, config)
            second_org, second_user = await seed_service_account(conn, admin, config)
            assert (first_org, first_user) == (second_org, second_user)

            row = await conn.fetchrow(
                "SELECT org_id, role FROM users WHERE id = $1", uuid.UUID(first_user)
            )
            return first_org, first_user, str(row["org_id"]), row["role"]
        finally:
            await conn.close()

    first_org, first_user, resolved_org_id, resolved_role = asyncio.run(_run())

    assert resolved_role == "owner"
    assert resolved_org_id == first_org
    assert first_user
