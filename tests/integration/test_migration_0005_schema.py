"""Schema contract test for migration 0005 (KCH-98).

Runs the full migration chain (0001-0005) against a real Postgres via
``apply_pending`` and asserts the resulting catalog shape through
``information_schema`` and ``pg_indexes``.  Skipped when
``TEST_DATABASE_URL`` is not set or ``asyncpg`` is not installed.

Mirrors tests/integration/test_migration_0004_*.py.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

asyncpg = pytest.importorskip("asyncpg")

from finhive.db.migrations import (  # noqa: E402
    apply_pending,
)

pytestmark = pytest.mark.integration

_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
_MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[2] / "migrations"
)

_TABLES_TO_DROP = [
    "agent_turns",
    "proposed_mutations",
    "report_records",
    "reports",
    "report_meta",
    "loan_history",
    "loan_meta",
    "loans",
    "users",
    "orgs",
    "schema_migrations",
]


async def _reset(
    conn: asyncpg.Connection,  # type: ignore[name-defined]
) -> None:
    for table in _TABLES_TO_DROP:
        await conn.execute(
            f"DROP TABLE IF EXISTS {table} CASCADE"
        )


async def _columns(
    conn: asyncpg.Connection,  # type: ignore[name-defined]
    table: str,
) -> dict[str, dict[str, str]]:
    rows = await conn.fetch(
        "SELECT column_name, data_type,"
        " is_nullable, column_default"
        " FROM information_schema.columns"
        " WHERE table_name = $1"
        " ORDER BY ordinal_position",
        table,
    )
    return {
        r["column_name"]: {
            "type": r["data_type"],
            "nullable": r["is_nullable"],
            "default": r["column_default"] or "",
        }
        for r in rows
    }


async def _indexes(
    conn: asyncpg.Connection,  # type: ignore[name-defined]
    table: str,
) -> list[str]:
    rows = await conn.fetch(
        "SELECT indexname FROM pg_indexes"
        " WHERE tablename = $1"
        " ORDER BY indexname",
        table,
    )
    return [r["indexname"] for r in rows]


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


async def _setup_and_query():  # type: ignore[no-untyped-def]
    conn = await asyncpg.connect(_DATABASE_URL)
    try:
        await _reset(conn)
        await apply_pending(conn, _MIGRATIONS_DIR)

        pm_cols = await _columns(conn, "proposed_mutations")
        pm_idxs = await _indexes(conn, "proposed_mutations")
        at_cols = await _columns(conn, "agent_turns")
        at_idxs = await _indexes(conn, "agent_turns")

        return {
            "pm_cols": pm_cols,
            "pm_idxs": pm_idxs,
            "at_cols": at_cols,
            "at_idxs": at_idxs,
        }
    finally:
        await _reset(conn)
        await conn.close()


@pytest.fixture(scope="module")
def catalog() -> dict:  # type: ignore[type-arg]
    return _run(_setup_and_query())


@pytest.mark.skipif(
    not _DATABASE_URL, reason="needs TEST_DATABASE_URL",
)
class TestProposedMutationsSchema:

    def test_before_state_ct_is_bytea(
        self, catalog: dict,  # type: ignore[type-arg]
    ) -> None:
        col = catalog["pm_cols"]["before_state_ct"]
        assert col["type"] == "bytea"
        assert col["nullable"] == "NO"

    def test_after_state_ct_is_bytea(
        self, catalog: dict,  # type: ignore[type-arg]
    ) -> None:
        col = catalog["pm_cols"]["after_state_ct"]
        assert col["type"] == "bytea"
        assert col["nullable"] == "NO"

    def test_key_version_present(
        self, catalog: dict,  # type: ignore[type-arg]
    ) -> None:
        col = catalog["pm_cols"]["key_version"]
        assert col["nullable"] == "NO"

    def test_no_plaintext_jsonb(
        self, catalog: dict,  # type: ignore[type-arg]
    ) -> None:
        for name, info in catalog["pm_cols"].items():
            assert info["type"] != "jsonb", (
                f"{name} is JSONB"
            )

    def test_indexes(
        self, catalog: dict,  # type: ignore[type-arg]
    ) -> None:
        idxs = catalog["pm_idxs"]
        assert "proposed_mutations_org_id_idx" in idxs
        assert "proposed_mutations_loan_id_idx" in idxs
        assert "proposed_mutations_status_idx" in idxs


@pytest.mark.skipif(
    not _DATABASE_URL, reason="needs TEST_DATABASE_URL",
)
class TestAgentTurnsSchema:

    def test_react_trace_ct_is_bytea(
        self, catalog: dict,  # type: ignore[type-arg]
    ) -> None:
        col = catalog["at_cols"]["react_trace_ct"]
        assert col["type"] == "bytea"
        assert col["nullable"] == "NO"

    def test_key_version_present(
        self, catalog: dict,  # type: ignore[type-arg]
    ) -> None:
        col = catalog["at_cols"]["key_version"]
        assert col["nullable"] == "NO"

    def test_no_plaintext_jsonb(
        self, catalog: dict,  # type: ignore[type-arg]
    ) -> None:
        for name, info in catalog["at_cols"].items():
            assert info["type"] != "jsonb", (
                f"{name} is JSONB"
            )

    def test_indexes(
        self, catalog: dict,  # type: ignore[type-arg]
    ) -> None:
        idxs = catalog["at_idxs"]
        assert "agent_turns_org_id_idx" in idxs
        assert "agent_turns_user_id_idx" in idxs
