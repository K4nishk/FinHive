"""Seed the MVP1 owner's service account (KCH-94).

Milestone one skips public multi-user signup: a single service account is
seeded for the existing MVP1 user, authenticating against Supabase Auth, with
`role=owner` in the `users` table (migration 0001) and a real `org_id` --
never a single-tenant shortcut that bypasses per-org scoping, since that
would invalidate the isolation guarantees RLS adds later (ARD v2.0.0 section 8).

Credentials and connection details come from environment variables normally
sourced from `ops/.env.local` (gitignored, never committed):

    DATABASE_URL               Postgres connection string, as used by the migration runner.
    SUPABASE_URL                Base URL of the Supabase project. Defaults to the local
                                 `supabase start` API gateway, http://127.0.0.1:54321.
    SUPABASE_SERVICE_ROLE_KEY   Service-role key -- confined to this module and
                                 finhive/db/admin.py, never used elsewhere.
    MVP1_OWNER_EMAIL            Login email for the seeded owner account.
    MVP1_OWNER_PASSWORD         Login password for the seeded owner account.
    MVP1_OWNER_ORG_NAME         Optional; defaults to "MVP1 Owner".

Re-running this module is idempotent: the org is looked up by name before
being created, the Supabase user is looked up by email before being created,
and the `users` row is upserted so role and org_id always end up matching
this seed even if a prior run only partially completed.
"""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from finhive.db.admin import AdminClient, SupabaseAdminError

_DEFAULT_ORG_NAME = "MVP1 Owner"
_DEFAULT_SUPABASE_URL = "http://127.0.0.1:54321"

_SELECT_ORG_BY_NAME = "SELECT id FROM orgs WHERE name = $1"
_INSERT_ORG = "INSERT INTO orgs (name) VALUES ($1) RETURNING id"
_UPSERT_OWNER = """
    INSERT INTO users (id, org_id, role)
    VALUES ($1, $2, 'owner')
    ON CONFLICT (id) DO UPDATE SET org_id = EXCLUDED.org_id, role = EXCLUDED.role
"""

# Arbitrary but stable bigint key for the session-level advisory lock guarding
# the ensure-org-then-upsert-owner sequence below, so two concurrent seed runs
# (e.g. two terminals both launching run_local_mac.sh) serialize instead of
# both inserting an "MVP1 Owner" org. "fhsa" (FinHive Seed Account) packed
# into 32 bits -- see finhive/db/migrations.py for the same pattern.
_ADVISORY_LOCK_KEY = 0x66687361


class ConfigError(Exception):
    """A required environment variable is missing."""


class Connection(Protocol):
    """The subset of `asyncpg.Connection` this seed needs."""

    async def fetchval(self, query: str, *args: Any) -> Any: ...
    async def execute(self, query: str, *args: Any) -> Any: ...


class AdminAuth(Protocol):
    """The subset of `AdminClient` this seed needs."""

    def create_or_get_user(self, email: str, password: str) -> str: ...


@dataclass(frozen=True)
class SeedConfig:
    database_url: str
    supabase_url: str
    supabase_service_role_key: str
    owner_email: str
    owner_password: str
    org_name: str = _DEFAULT_ORG_NAME


def load_config(env: dict[str, str] | None = None) -> SeedConfig:
    """Read the seed configuration from `env` (defaults to `os.environ`).

    Raises `ConfigError` naming every missing required variable at once,
    rather than failing on the first one, so a developer fixes their
    `ops/.env.local` in one pass.
    """
    env = os.environ if env is None else env
    required = (
        "DATABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "MVP1_OWNER_EMAIL",
        "MVP1_OWNER_PASSWORD",
    )
    missing = [name for name in required if not env.get(name)]
    if missing:
        raise ConfigError(
            "missing required environment variable(s): "
            + ", ".join(missing)
            + " -- set them in ops/.env.local"
        )
    return SeedConfig(
        database_url=env["DATABASE_URL"],
        supabase_url=env.get("SUPABASE_URL") or _DEFAULT_SUPABASE_URL,
        supabase_service_role_key=env["SUPABASE_SERVICE_ROLE_KEY"],
        owner_email=env["MVP1_OWNER_EMAIL"],
        owner_password=env["MVP1_OWNER_PASSWORD"],
        org_name=env.get("MVP1_OWNER_ORG_NAME") or _DEFAULT_ORG_NAME,
    )


async def _ensure_org(conn: Connection, name: str) -> Any:
    org_id = await conn.fetchval(_SELECT_ORG_BY_NAME, name)
    if org_id is not None:
        return org_id
    return await conn.fetchval(_INSERT_ORG, name)


async def seed_service_account(
    conn: Connection, admin: AdminAuth, config: SeedConfig
) -> tuple[str, str]:
    """Idempotently seed the org + owner row. Returns `(org_id, user_id)`."""
    await conn.execute("SELECT pg_advisory_lock($1)", _ADVISORY_LOCK_KEY)
    try:
        org_id = await _ensure_org(conn, config.org_name)
        user_id = uuid.UUID(admin.create_or_get_user(config.owner_email, config.owner_password))
        await conn.execute(_UPSERT_OWNER, user_id, org_id)
    finally:
        await conn.execute("SELECT pg_advisory_unlock($1)", _ADVISORY_LOCK_KEY)
    return str(org_id), str(user_id)


async def _run_cli() -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    import asyncpg

    admin = AdminClient(config.supabase_url, config.supabase_service_role_key)
    conn = await asyncpg.connect(config.database_url)
    try:
        org_id, user_id = await seed_service_account(conn, admin, config)
    except SupabaseAdminError as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await conn.close()

    print(f"seeded owner {config.owner_email} -> org {org_id}, user {user_id}")
    return 0


def main() -> int:
    import asyncio

    return asyncio.run(_run_cli())


if __name__ == "__main__":
    raise SystemExit(main())
