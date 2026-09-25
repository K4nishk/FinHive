"""Advisory-lock serialization for the migration runner (KCH-91).

Requires a real Postgres reachable via TEST_DATABASE_URL -- skipped otherwise,
per the ``integration`` marker's contract in pyproject.toml ("needs a database:
ephemeral Supabase branch or local Postgres"). This test drops and recreates
tables, so it must never fall back to DATABASE_URL: that variable can point at
a real application database, and running this against it would destroy its
migration history.

A third connection holds the advisory lock before the two runners start, so
both runners block on the lock. We poll ``pg_stat_activity`` to verify both
sessions are in the ``Lock`` wait state before releasing, making the test
deterministic: without the advisory lock in ``apply_pending``, both runners
would plan against the same empty history and one would fail on a
unique-violation.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from finhive.db.migrations import (
    _ADVISORY_LOCK_KEY,
    apply_pending,
)

asyncpg = pytest.importorskip("asyncpg")

pytestmark = pytest.mark.integration

_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
_LOCK_SCHEMA = "finhive_integration_lock"


from tests.integration._isolation import (  # noqa: E402
    drop_test_schema,
    reset_to_clean_schema,
    use_schema,
)


def _write(tmp_path: Path, filename: str, sql: str) -> Path:
    path = tmp_path / filename
    path.write_text(sql, encoding="utf-8")
    return path


async def _wait_for_lock_waiters(
    conn,
    lock_key: int,
    expected: int,
    timeout: float = 10.0,
) -> None:
    """Poll pg_locks + pg_stat_activity until *expected*
    sessions are waiting on *lock_key*."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        rows = await conn.fetch(
            """
            SELECT count(*) AS n
            FROM pg_stat_activity sa
            JOIN pg_locks pl
              ON pl.pid = sa.pid
            WHERE sa.wait_event_type = 'Lock'
              AND sa.wait_event = 'advisory'
              AND sa.state = 'active'
              AND sa.pid != pg_backend_pid()
              AND pl.objid = $1
              AND NOT pl.granted
            """,
            lock_key,
        )
        if rows[0]["n"] >= expected:
            return
        await asyncio.sleep(0.1)
    raise AssertionError(
        f"timed out waiting for {expected}"
        " advisory-lock waiters"
    )


@pytest.mark.skipif(not _DATABASE_URL, reason="needs TEST_DATABASE_URL")
def test_two_connections_racing_apply_pending_do_not_double_apply(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "0001_init.sql",
        "CREATE TABLE IF NOT EXISTS lock_test_t (a INT);",
    )

    async def _run() -> list[list]:
        conn_hold = await asyncpg.connect(_DATABASE_URL)
        conn_a = await asyncpg.connect(_DATABASE_URL)
        conn_b = await asyncpg.connect(_DATABASE_URL)
        try:
            # A schema of its own, joined by all three connections. The
            # unqualified drops this replaced resolved to `public`, and when
            # TEST_DATABASE_URL pointed at the dev database they deleted the
            # app's real migration ledger (public.schema_migrations). Advisory
            # locks are database-wide, so the race under test is unchanged.
            await reset_to_clean_schema(conn_hold, _LOCK_SCHEMA)
            await use_schema(conn_a, _LOCK_SCHEMA)
            await use_schema(conn_b, _LOCK_SCHEMA)

            await conn_hold.execute(
                "SELECT pg_advisory_lock($1)", _ADVISORY_LOCK_KEY
            )

            task_a = asyncio.create_task(apply_pending(conn_a, tmp_path))
            task_b = asyncio.create_task(apply_pending(conn_b, tmp_path))

            await _wait_for_lock_waiters(conn_hold, _ADVISORY_LOCK_KEY, 2)

            await conn_hold.execute(
                "SELECT pg_advisory_unlock($1)", _ADVISORY_LOCK_KEY
            )

            results = await asyncio.gather(task_a, task_b)

            rows = await conn_a.fetch(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
            assert [r["version"] for r in rows] == [1]
            return results
        finally:
            await drop_test_schema(conn_hold, _LOCK_SCHEMA)
            await conn_hold.close()
            await conn_a.close()
            await conn_b.close()

    first, second = asyncio.run(_run())

    assert sorted([len(first), len(second)]) == [0, 1]
