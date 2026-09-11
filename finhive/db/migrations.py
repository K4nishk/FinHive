"""Forward-only SQL migration runner (KCH-91).

Reads numbered `migrations/NNNN_name.sql` files and applies the ones a target
Postgres database hasn't seen yet, recording each in a `schema_migrations` table
keyed by version, checksum and applied-at timestamp. There are no down-migrations:
rolling a live schema back is riskier than rolling forward, so the only way to
undo a change is a new migration that does so.

The planning logic (`discover_migrations`, `plan_migrations`) is pure and has no
database dependency, so it's fully unit-testable without Postgres or asyncpg
installed. `apply_pending` is the only function that talks to a connection, and it
duck-types against one (`execute` / `fetch` / `transaction`) rather than importing
asyncpg, so callers can pass a real `asyncpg.Connection` or a test double.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

_FILENAME_RE = re.compile(r"^(?P<version>\d{4})_(?P<name>[a-z0-9_]+)\.sql$")

_CREATE_SCHEMA_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

_SELECT_APPLIED = "SELECT version, name, checksum, applied_at FROM schema_migrations"

_INSERT_APPLIED = (
    "INSERT INTO schema_migrations (version, name, checksum) VALUES ($1, $2, $3)"
)


class MigrationError(Exception):
    """Base error for the migration runner."""


class DuplicateVersionError(MigrationError):
    def __init__(self, version: int, paths: list[Path]) -> None:
        self.version = version
        self.paths = paths
        names = ", ".join(p.name for p in paths)
        super().__init__(f"duplicate migration version {version:04d}: {names}")


class ChecksumMismatchError(MigrationError):
    """A previously-applied migration file's contents changed on disk."""

    def __init__(self, version: int, name: str, expected: str, actual: str) -> None:
        self.version = version
        self.name = name
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"migration {version:04d}_{name}.sql was already applied with checksum "
            f"{expected}, but the file on disk now checksums to {actual}. Migrations "
            "are forward-only and immutable once applied -- add a new migration "
            "instead of editing this one."
        )


class NameMismatchError(MigrationError):
    """A previously-applied migration's file was renamed on disk."""

    def __init__(self, version: int, expected: str, actual: str) -> None:
        self.version = version
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"migration {version:04d} was recorded as applied under the name "
            f"'{expected}', but the file on disk for that version is now named "
            f"'{actual}'. Migrations are forward-only and immutable once applied "
            "-- renaming an applied migration's file is not allowed."
        )


class MissingMigrationError(MigrationError):
    """A previously-applied migration's file is no longer on disk."""

    def __init__(self, version: int) -> None:
        self.version = version
        super().__init__(
            f"migration {version:04d} is recorded as applied in schema_migrations, "
            "but no matching file exists in the migrations directory. Migrations "
            "are forward-only and immutable once applied -- restore the file "
            "instead of deleting it."
        )


class OutOfOrderMigrationError(MigrationError):
    """A pending migration's version sits below the highest applied version."""

    def __init__(self, version: int, highest_applied: int) -> None:
        self.version = version
        self.highest_applied = highest_applied
        super().__init__(
            f"migration {version:04d} is pending, but migration "
            f"{highest_applied:04d} has already been applied. Migrations are "
            "forward-only -- a new file cannot be numbered below the highest "
            "applied version."
        )


@dataclass(frozen=True)
class MigrationFile:
    version: int
    name: str
    path: Path
    checksum: str
    sql: str


@dataclass(frozen=True)
class AppliedMigration:
    version: int
    name: str
    checksum: str
    applied_at: datetime


@dataclass(frozen=True)
class MigrationPlan:
    pending: list[MigrationFile]
    mismatched: list[tuple[MigrationFile, AppliedMigration]]
    renamed: list[tuple[MigrationFile, AppliedMigration]]
    missing: list[AppliedMigration]
    out_of_order: list[MigrationFile]

    @property
    def is_clean(self) -> bool:
        return (
            not self.mismatched
            and not self.renamed
            and not self.missing
            and not self.out_of_order
        )

    @property
    def is_up_to_date(self) -> bool:
        return not self.pending and self.is_clean


def checksum_of(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def discover_migrations(migrations_dir: Path) -> list[MigrationFile]:
    """Discover `NNNN_name.sql` files, sorted by version.

    Non-`.sql` files (this README, stray docs) are ignored, so the directory
    can carry documentation alongside the migrations themselves. A `.sql` file
    that doesn't match the `NNNN_name.sql` naming convention raises instead of
    being silently skipped -- a typo in a migration's filename must not
    produce a clean plan that quietly never runs the intended migration.
    """
    by_version: dict[int, list[Path]] = {}
    for path in migrations_dir.glob("*.sql"):
        match = _FILENAME_RE.match(path.name)
        if not match:
            raise MigrationError(
                f"{path.name} does not match the required migration filename "
                "convention NNNN_name.sql (a zero-padded 4-digit version, an "
                "underscore, then a lowercase snake_case name)"
            )
        by_version.setdefault(int(match.group("version")), []).append(path)

    for version, paths in by_version.items():
        if len(paths) > 1:
            raise DuplicateVersionError(version, sorted(paths))

    migrations = []
    for version, paths in by_version.items():
        path = paths[0]
        match = _FILENAME_RE.match(path.name)
        assert match is not None
        sql = path.read_text(encoding="utf-8")
        migrations.append(
            MigrationFile(
                version=version,
                name=match.group("name"),
                path=path,
                checksum=checksum_of(sql),
                sql=sql,
            )
        )
    return sorted(migrations, key=lambda m: m.version)


def plan_migrations(
    migrations: list[MigrationFile], applied: list[AppliedMigration]
) -> MigrationPlan:
    """Pure planning step: compare on-disk migrations against applied history.

    A migration with no applied record is pending. A migration whose recorded
    name no longer matches the file on disk for that version is renamed --
    renaming the file after it was applied would otherwise bypass the
    checksum check entirely. A migration whose applied checksum no longer
    matches the file on disk is mismatched -- it was edited after being
    applied, which is exactly what must not happen. An applied version with no
    matching file on disk is missing -- its migration file was deleted. A
    pending version below the highest applied version is out-of-order -- a new
    file was added numbered behind history that has already been applied.
    Applied history must be an exact prefix of what's on disk; any of these
    states means it isn't, and the caller must fail closed rather than apply
    anything.
    """
    migrations_by_version = {m.version: m for m in migrations}
    applied_by_version = {a.version: a for a in applied}

    pending: list[MigrationFile] = []
    mismatched: list[tuple[MigrationFile, AppliedMigration]] = []
    renamed: list[tuple[MigrationFile, AppliedMigration]] = []

    for migration in migrations:
        record = applied_by_version.get(migration.version)
        if record is None:
            pending.append(migration)
        elif record.name != migration.name:
            renamed.append((migration, record))
        elif record.checksum != migration.checksum:
            mismatched.append((migration, record))

    missing = sorted(
        (
            record
            for version, record in applied_by_version.items()
            if version not in migrations_by_version
        ),
        key=lambda a: a.version,
    )

    highest_applied = max(applied_by_version, default=None)
    out_of_order = []
    if highest_applied is not None:
        out_of_order = sorted(
            (m for m in pending if m.version < highest_applied), key=lambda m: m.version
        )

    return MigrationPlan(
        pending=pending,
        mismatched=mismatched,
        renamed=renamed,
        missing=missing,
        out_of_order=out_of_order,
    )


class _Transaction(Protocol):
    async def __aenter__(self) -> Any: ...
    async def __aexit__(self, *exc_info: object) -> Any: ...


class Connection(Protocol):
    """The subset of `asyncpg.Connection` the runner needs."""

    async def execute(self, query: str, *args: Any) -> Any: ...
    async def fetch(self, query: str, *args: Any) -> Any: ...
    def transaction(self) -> _Transaction: ...


# Arbitrary but stable bigint key for the session-level advisory lock that
# serializes planning and application below -- "fhmg" (FinHive MiGrate) packed
# into 32 bits. Any fixed constant works; it only needs to not collide with a
# lock key some other subsystem takes on the same database.
_ADVISORY_LOCK_KEY = 0x66686D67

# Bounds how long a runner waits for another runner's advisory lock before
# giving up. Without this, a hung runner holding the lock wedges every other
# runner -- including local dev launchers -- indefinitely.
_LOCK_TIMEOUT_SECONDS = 30


async def apply_pending(
    conn: Connection, migrations_dir: Path
) -> list[MigrationFile]:
    """Apply pending migrations, forward-only, against `conn`.

    Raises `ChecksumMismatchError` before applying anything if a previously
    applied file has been edited on disk, `NameMismatchError` if a previously
    applied file was renamed, `MissingMigrationError` if a previously applied
    file was deleted, or `OutOfOrderMigrationError` if a new file was added
    numbered behind a version that's already been applied.
    Returns the migrations newly applied this call -- an empty list when the
    database is already up to date, which is what makes running this twice in
    a row idempotent.

    Planning (fetching applied history) and application happen while holding a
    Postgres advisory lock, so two runners racing against the same database
    serialize instead of both planning against the same snapshot and then both
    trying to apply the same pending migration.
    """
    await conn.execute(f"SET lock_timeout = '{_LOCK_TIMEOUT_SECONDS}s'")
    await conn.execute("SELECT pg_advisory_lock($1)", _ADVISORY_LOCK_KEY)
    try:
        await conn.execute(_CREATE_SCHEMA_MIGRATIONS_TABLE)
        rows = await conn.fetch(_SELECT_APPLIED)
        applied = [
            AppliedMigration(
                version=row["version"],
                name=row["name"],
                checksum=row["checksum"],
                applied_at=row["applied_at"],
            )
            for row in rows
        ]

        migrations = discover_migrations(migrations_dir)
        result = plan_migrations(migrations, applied)

        if not result.is_clean:
            if result.missing:
                raise MissingMigrationError(result.missing[0].version)
            if result.out_of_order:
                highest_applied = max(a.version for a in applied)
                raise OutOfOrderMigrationError(
                    result.out_of_order[0].version, highest_applied
                )
            if result.renamed:
                migration, record = result.renamed[0]
                raise NameMismatchError(migration.version, record.name, migration.name)
            migration, record = result.mismatched[0]
            raise ChecksumMismatchError(
                migration.version, migration.name, record.checksum, migration.checksum
            )

        for migration in result.pending:
            async with conn.transaction():
                await conn.execute(migration.sql)
                await conn.execute(
                    _INSERT_APPLIED,
                    migration.version,
                    migration.name,
                    migration.checksum,
                )

        return result.pending
    finally:
        await conn.execute("SELECT pg_advisory_unlock($1)", _ADVISORY_LOCK_KEY)


async def _run_cli() -> int:
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Forward-only SQL migration runner")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "migrations",
    )
    args = parser.parse_args()

    if not args.database_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2

    import asyncpg

    conn = await asyncpg.connect(args.database_url)
    try:
        applied = await apply_pending(conn, args.migrations_dir)
    except MigrationError as exc:
        print(f"migration failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await conn.close()

    if not applied:
        print("up to date -- nothing to apply")
    for migration in applied:
        print(f"applied {migration.version:04d}_{migration.name}.sql")
    return 0


def main() -> int:
    import asyncio

    return asyncio.run(_run_cli())


if __name__ == "__main__":
    raise SystemExit(main())
