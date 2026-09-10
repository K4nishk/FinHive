"""The forward-only SQL migration runner (KCH-91).

Acceptance: running the migrator twice is idempotent, and editing an already
applied migration fails. `apply_pending` is exercised directly (not just the pure
`plan_migrations` helper it's built on) against a fake connection, so this covers
the actual code path the CLI runs -- not just the planning logic underneath it.
No Postgres or asyncpg required: the fake connection duck-types the
`execute`/`fetch`/`transaction` surface `apply_pending` depends on.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from finhive.db.migrations import (
    AppliedMigration,
    ChecksumMismatchError,
    DuplicateVersionError,
    _run_cli,
    apply_pending,
    checksum_of,
    discover_migrations,
    plan_migrations,
)


def _write(tmp_path: Path, filename: str, sql: str) -> Path:
    path = tmp_path / filename
    path.write_text(sql, encoding="utf-8")
    return path


# ── discover_migrations ──────────────────────────────────────────────────────


def test_discover_migrations_orders_by_version(tmp_path: Path) -> None:
    _write(tmp_path, "0002_add_index.sql", "CREATE INDEX idx ON t (a);")
    _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")

    migrations = discover_migrations(tmp_path)

    assert [m.version for m in migrations] == [1, 2]
    assert [m.name for m in migrations] == ["init", "add_index"]


def test_discover_migrations_ignores_non_matching_files(tmp_path: Path) -> None:
    _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    _write(tmp_path, "README.md", "# migrations")
    _write(tmp_path, "not_numbered.sql", "SELECT 1;")

    migrations = discover_migrations(tmp_path)

    assert [m.version for m in migrations] == [1]


def test_discover_migrations_rejects_duplicate_version(tmp_path: Path) -> None:
    _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    _write(tmp_path, "0001_also_init.sql", "CREATE TABLE u (a INT);")

    with pytest.raises(DuplicateVersionError):
        discover_migrations(tmp_path)


def test_checksum_changes_with_content() -> None:
    assert checksum_of("SELECT 1;") != checksum_of("SELECT 2;")
    assert checksum_of("SELECT 1;") == checksum_of("SELECT 1;")


# ── plan_migrations (pure) ───────────────────────────────────────────────────


def test_plan_is_up_to_date_when_nothing_pending_or_mismatched(tmp_path: Path) -> None:
    _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    migrations = discover_migrations(tmp_path)
    applied = [
        AppliedMigration(
            version=1, checksum=migrations[0].checksum, applied_at=datetime.now(timezone.utc)
        )
    ]

    plan = plan_migrations(migrations, applied)

    assert plan.pending == []
    assert plan.mismatched == []
    assert plan.is_up_to_date


def test_plan_flags_unapplied_migrations_as_pending(tmp_path: Path) -> None:
    _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    migrations = discover_migrations(tmp_path)

    plan = plan_migrations(migrations, applied=[])

    assert [m.version for m in plan.pending] == [1]
    assert plan.is_clean
    assert not plan.is_up_to_date


def test_plan_flags_edited_applied_migration_as_mismatched(tmp_path: Path) -> None:
    _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    migrations = discover_migrations(tmp_path)
    stale_checksum = checksum_of("CREATE TABLE t (a INT, b INT);")  # edited since applied
    applied = [
        AppliedMigration(version=1, checksum=stale_checksum, applied_at=datetime.now(timezone.utc))
    ]

    plan = plan_migrations(migrations, applied)

    assert not plan.is_clean
    assert plan.mismatched[0][0].version == 1


# ── apply_pending (async, against a fake connection) ────────────────────────


class _FakeTransaction:
    async def __aenter__(self) -> _FakeTransaction:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class _FakeConnection:
    """In-memory stand-in for an asyncpg.Connection's schema_migrations state."""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.executed_sql: list[str] = []

    async def execute(self, query: str, *args: object) -> None:
        self.executed_sql.append(query)
        if query.strip().startswith("INSERT INTO schema_migrations"):
            version, name, checksum = args
            self.rows.append(
                {
                    "version": version,
                    "name": name,
                    "checksum": checksum,
                    "applied_at": datetime.now(timezone.utc),
                }
            )

    async def fetch(self, query: str, *args: object) -> list[dict]:
        return list(self.rows)

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction()


def test_apply_pending_applies_new_migrations_in_order(tmp_path: Path) -> None:
    _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    _write(tmp_path, "0002_add_index.sql", "CREATE INDEX idx ON t (a);")
    conn = _FakeConnection()

    applied = asyncio.run(apply_pending(conn, tmp_path))

    assert [m.version for m in applied] == [1, 2]
    assert [row["version"] for row in conn.rows] == [1, 2]


def test_apply_pending_twice_is_idempotent(tmp_path: Path) -> None:
    _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    _write(tmp_path, "0002_add_index.sql", "CREATE INDEX idx ON t (a);")
    conn = _FakeConnection()

    first_run = asyncio.run(apply_pending(conn, tmp_path))
    second_run = asyncio.run(apply_pending(conn, tmp_path))

    assert [m.version for m in first_run] == [1, 2]
    assert second_run == []
    assert [row["version"] for row in conn.rows] == [1, 2]


def test_apply_pending_fails_when_an_applied_migration_was_edited(tmp_path: Path) -> None:
    path = _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    conn = _FakeConnection()
    asyncio.run(apply_pending(conn, tmp_path))

    # Edit the already-applied file in place -- forbidden.
    path.write_text("CREATE TABLE t (a INT, b INT);", encoding="utf-8")

    with pytest.raises(ChecksumMismatchError) as exc_info:
        asyncio.run(apply_pending(conn, tmp_path))

    assert exc_info.value.version == 1
    # Nothing new was recorded as a side effect of the failed attempt.
    assert [row["version"] for row in conn.rows] == [1]


def test_apply_pending_raises_before_applying_any_pending_migration_on_mismatch(
    tmp_path: Path,
) -> None:
    """A mismatch on an earlier version must block a later, genuinely-new
    migration from being applied -- the runner should fail closed, not apply
    everything it can and silently skip the bad one.
    """
    path1 = _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    conn = _FakeConnection()
    asyncio.run(apply_pending(conn, tmp_path))

    path1.write_text("CREATE TABLE t (a INT, b INT);", encoding="utf-8")
    _write(tmp_path, "0002_add_index.sql", "CREATE INDEX idx ON t (a);")

    with pytest.raises(ChecksumMismatchError):
        asyncio.run(apply_pending(conn, tmp_path))

    assert [row["version"] for row in conn.rows] == [1]


# ── CLI ───────────────────────────────────────────────────────────────────


def test_cli_fails_fast_when_database_url_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing DATABASE_URL must exit non-zero before ever importing asyncpg or
    attempting a connection.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["finhive-migrate"])

    exit_code = asyncio.run(_run_cli())

    assert exit_code == 2
