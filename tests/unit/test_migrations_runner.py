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
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from finhive.db.migrations import (
    AppliedMigration,
    ChecksumMismatchError,
    DuplicateVersionError,
    MigrationError,
    MissingMigrationError,
    NameMismatchError,
    OutOfOrderMigrationError,
    _run_cli,
    _SELECT_APPLIED,
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


def test_discover_migrations_ignores_non_sql_files(tmp_path: Path) -> None:
    _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    _write(tmp_path, "README.md", "# migrations")

    migrations = discover_migrations(tmp_path)

    assert [m.version for m in migrations] == [1]


def test_discover_migrations_rejects_sql_file_with_invalid_name(
    tmp_path: Path,
) -> None:
    """A .sql file that doesn't match NNNN_name.sql must raise rather than be
    silently skipped -- a typo like `001_init.sql` (three digits) must not
    produce an apparently clean plan while the intended migration never runs.
    """
    _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    _write(tmp_path, "not_numbered.sql", "SELECT 1;")

    with pytest.raises(MigrationError):
        discover_migrations(tmp_path)


def test_discover_migrations_rejects_short_version_prefix(tmp_path: Path) -> None:
    """The exact typo named in the docstring above: a three-digit version
    prefix must be rejected rather than silently skipped.
    """
    _write(tmp_path, "001_init.sql", "CREATE TABLE t (a INT);")

    with pytest.raises(MigrationError):
        discover_migrations(tmp_path)


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
            version=1,
            name=migrations[0].name,
            checksum=migrations[0].checksum,
            applied_at=datetime.now(timezone.utc),
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
    # edited since applied
    stale_checksum = checksum_of("CREATE TABLE t (a INT, b INT);")
    applied = [
        AppliedMigration(
            version=1,
            name="init",
            checksum=stale_checksum,
            applied_at=datetime.now(timezone.utc),
        )
    ]

    plan = plan_migrations(migrations, applied)

    assert not plan.is_clean
    assert plan.mismatched[0][0].version == 1


def test_plan_flags_renamed_applied_migration_as_renamed(tmp_path: Path) -> None:
    """A migration whose file was renamed after being applied must not read as
    clean even when the SQL content -- and therefore the checksum -- is
    unchanged, otherwise renaming a file bypasses the immutable-file check
    entirely.
    """
    _write(tmp_path, "0001_renamed.sql", "CREATE TABLE t (a INT);")
    migrations = discover_migrations(tmp_path)
    applied = [
        AppliedMigration(
            version=1,
            name="init",
            checksum=migrations[0].checksum,
            applied_at=datetime.now(timezone.utc),
        )
    ]

    plan = plan_migrations(migrations, applied)

    assert not plan.is_clean
    assert plan.mismatched == []
    assert plan.renamed[0][0].version == 1


def test_plan_flags_applied_version_with_no_file_on_disk_as_missing(
    tmp_path: Path,
) -> None:
    """An applied migration whose file was deleted must not read as clean --
    otherwise deleting a file silently drops it from history enforcement.
    """
    applied = [
        AppliedMigration(
            version=1,
            name="init",
            checksum=checksum_of("CREATE TABLE t (a INT);"),
            applied_at=datetime.now(timezone.utc),
        )
    ]

    plan = plan_migrations(migrations=[], applied=applied)

    assert not plan.is_clean
    assert [a.version for a in plan.missing] == [1]


def test_plan_flags_pending_version_below_highest_applied_as_out_of_order(
    tmp_path: Path,
) -> None:
    """A new file numbered behind a version that's already applied must not
    read as a normal pending migration -- applying it now would run it after
    migrations that, in version order, were supposed to come after it.
    """
    _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    migrations = discover_migrations(tmp_path)
    applied = [
        AppliedMigration(
            version=2,
            name="add_index",
            checksum=checksum_of("CREATE INDEX idx ON t (a);"),
            applied_at=datetime.now(timezone.utc),
        )
    ]

    plan = plan_migrations(migrations, applied)

    assert not plan.is_clean
    assert [m.version for m in plan.out_of_order] == [1]


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
        # apply_pending only ever fetches applied history; asserting the query
        # here (rather than ignoring it and always returning self.rows) means a
        # future fetch call this fake doesn't expect fails loudly instead of
        # silently getting handed schema_migrations rows it never asked for.
        assert query == _SELECT_APPLIED, f"unexpected fetch query: {query!r}"
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


def test_apply_pending_fails_when_an_applied_migration_was_edited(
    tmp_path: Path,
) -> None:
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


def test_apply_pending_releases_the_advisory_lock_on_failure(tmp_path: Path) -> None:
    """A failed plan must still release the advisory lock -- otherwise a
    checksum mismatch on one run wedges every subsequent runner behind a lock
    that's never coming back.
    """
    path = _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    conn = _FakeConnection()
    asyncio.run(apply_pending(conn, tmp_path))
    path.write_text("CREATE TABLE t (a INT, b INT);", encoding="utf-8")

    with pytest.raises(ChecksumMismatchError):
        asyncio.run(apply_pending(conn, tmp_path))

    assert conn.executed_sql[-1] == "SELECT pg_advisory_unlock($1)"


def test_apply_pending_fails_when_an_applied_migration_was_renamed(
    tmp_path: Path,
) -> None:
    """Renaming an already-applied migration's file must fail even though its
    SQL content -- and therefore its checksum -- is unchanged. Otherwise a
    rename bypasses the checksum check that catches edits.
    """
    path = _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    conn = _FakeConnection()
    asyncio.run(apply_pending(conn, tmp_path))

    path.rename(tmp_path / "0001_renamed.sql")

    with pytest.raises(NameMismatchError) as exc_info:
        asyncio.run(apply_pending(conn, tmp_path))

    assert exc_info.value.version == 1
    assert exc_info.value.expected == "init"
    assert exc_info.value.actual == "renamed"
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


def test_apply_pending_fails_when_an_applied_migrations_file_is_deleted(
    tmp_path: Path,
) -> None:
    """Deleting an applied migration's file must not read as a clean, up to
    date database -- the runner must fail closed instead of silently forgetting
    that version happened.
    """
    path = _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")
    conn = _FakeConnection()
    asyncio.run(apply_pending(conn, tmp_path))

    path.unlink()

    with pytest.raises(MissingMigrationError) as exc_info:
        asyncio.run(apply_pending(conn, tmp_path))

    assert exc_info.value.version == 1


def test_apply_pending_fails_when_a_new_file_is_numbered_below_the_highest_applied(
    tmp_path: Path,
) -> None:
    """A new file numbered behind a version that's already applied must not be
    applied out of order -- the runner must fail closed instead of running it
    after migrations that were supposed to come first.
    """
    _write(tmp_path, "0002_add_index.sql", "CREATE INDEX idx ON t (a);")
    conn = _FakeConnection()
    asyncio.run(apply_pending(conn, tmp_path))

    _write(tmp_path, "0001_init.sql", "CREATE TABLE t (a INT);")

    with pytest.raises(OutOfOrderMigrationError) as exc_info:
        asyncio.run(apply_pending(conn, tmp_path))

    assert exc_info.value.version == 1
    assert exc_info.value.highest_applied == 2
    # Nothing new was recorded as a side effect of the failed attempt.
    assert [row["version"] for row in conn.rows] == [2]


# ── CLI ───────────────────────────────────────────────────────────────────


def test_cli_fails_fast_when_database_url_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing DATABASE_URL must exit non-zero before ever importing asyncpg or
    attempting a connection.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["finhive-migrate"])

    exit_code = asyncio.run(_run_cli())

    assert exit_code == 2


def test_cli_returns_one_on_migration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_local_windows.bat and run_local_mac.sh key their abort-on-failure
    behaviour off this exit code, distinct from the 2 returned above for a
    missing DATABASE_URL -- a MigrationError raised while applying migrations
    must map to exit code 1.

    asyncpg is stubbed via sys.modules rather than requiring the real package,
    so this test exercises the CLI's error handling regardless of whether
    asyncpg is installed in the environment running the suite.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
    monkeypatch.setattr("sys.argv", ["finhive-migrate"])

    class _FakeAsyncpgConnection:
        async def close(self) -> None:
            pass

    class _FakeAsyncpgModule:
        @staticmethod
        async def connect(url: str) -> _FakeAsyncpgConnection:
            return _FakeAsyncpgConnection()

    monkeypatch.setitem(sys.modules, "asyncpg", _FakeAsyncpgModule())

    async def _raise_checksum_mismatch(conn: object, migrations_dir: Path) -> list:
        raise ChecksumMismatchError(1, "init", "expected-checksum", "actual-checksum")

    monkeypatch.setattr("finhive.db.migrations.apply_pending", _raise_checksum_mismatch)

    exit_code = asyncio.run(_run_cli())

    assert exit_code == 1
