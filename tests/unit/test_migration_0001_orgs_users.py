"""Migration 0001 -- orgs and users tables (KCH-92).

`finhive/db/migrations.py` (KCH-91) only knows how to discover and checksum
`NNNN_name.sql` files; it has no idea what any particular migration's SQL
should contain. These tests cover that gap for migration 0001 without a
database: they assert the file is discoverable under the runner's naming
convention and that its DDL actually creates the tenant-root and
Supabase-auth-mapping shape the ARD specifies (ARD v2.0.0 §9) -- a tenant
root with no dependency on the user it will end up owning, and a `users` row
that resolves to exactly one org and one of the three defined roles.
"""

from __future__ import annotations

from pathlib import Path

from finhive.db.migrations import discover_migrations

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def test_migration_0001_is_discovered_as_init_orgs_users() -> None:
    migrations = discover_migrations(_MIGRATIONS_DIR)

    assert migrations[0].version == 1
    assert migrations[0].name == "init_orgs_users"


def test_migration_0001_creates_orgs_before_users() -> None:
    sql = _migration_0001_sql()

    assert sql.index("CREATE TABLE orgs") < sql.index("CREATE TABLE users")


def test_migration_0001_users_references_auth_users() -> None:
    sql = _migration_0001_sql()

    assert "REFERENCES auth.users" in sql


def test_migration_0001_users_references_orgs() -> None:
    sql = _migration_0001_sql()

    assert "REFERENCES orgs" in sql


def test_migration_0001_role_is_constrained_to_owner_bookkeeper_viewer() -> None:
    sql = _migration_0001_sql()

    assert "CHECK (role IN ('owner', 'bookkeeper', 'viewer'))" in sql


def _migration_0001_sql() -> str:
    migrations = discover_migrations(_MIGRATIONS_DIR)
    migration_0001 = next(m for m in migrations if m.version == 1)
    return migration_0001.sql
