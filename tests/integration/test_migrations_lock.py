"""Advisory-lock serialization for the migration runner (KCH-91).

Requires a real Postgres reachable via TEST_DATABASE_URL -- skipped otherwise,
per the `integration` marker's contract in pyproject.toml ("needs a database:
ephemeral Supabase branch or local Postgres"). This test drops and recreates
tables, so it must never fall back to DATABASE_URL: that variable can point at
a real application database, and running this against it would destroy its
migration history.

Two real asyncpg connections race `apply_pending` against the same pending
migration concurrently. Without the advisory lock serializing planning and
application, both connections can fetch the same empty applied history and
then both try to INSERT the same primary key into schema_migrations, so one
of the two fails on a unique-violation instead of the runner staying
idempotent. This exercises the actual `apply_pending` code path against a
real database, not a fake connection.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

asyncpg = pytest.importorskip("asyncpg")

from finhive.db.migrations import apply_pending  # noqa: E402

pytestmark = pytest.mark.integration

_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def _write(tmp_path: Path, filename: str, sql: str) -> Path:
    path = tmp_path / filename
    path.write_text(sql, encoding="utf-8")
    return path


@pytest.mark.skipif(not _DATABASE_URL, reason="needs TEST_DATABASE_URL")
def test_two_connections_racing_apply_pending_do_not_double_apply(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "0001_init.sql", "CREATE TABLE IF NOT EXISTS lock_test_t (a INT);")

    async def _run() -> list[list]:
        conn_a = await asyncpg.connect(_DATABASE_URL)
        conn_b = await asyncpg.connect(_DATABASE_URL)
        try:
            await conn_a.execute("DROP TABLE IF EXISTS schema_migrations")
            await conn_a.execute("DROP TABLE IF EXISTS lock_test_t")

            results = await asyncio.gather(
                apply_pending(conn_a, tmp_path),
                apply_pending(conn_b, tmp_path),
            )
            rows = await conn_a.fetch(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
            assert [r["version"] for r in rows] == [1]
            return results
        finally:
            await conn_a.close()
            await conn_b.close()

    first, second = asyncio.run(_run())

    # Exactly one connection applies the migration; the other, having waited
    # on the advisory lock, finds it already applied and applies nothing --
    # neither connection raises a unique-violation on schema_migrations.
    assert sorted([len(first), len(second)]) == [0, 1]
