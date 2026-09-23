"""One-time migration: encrypt the plaintext rows an existing database
already holds (KCH-227, ARB D-15).

WHY THIS EXISTS
`Base.metadata.create_all()` creates missing TABLES. It does not ALTER an
existing one. So when KCH-227 changed the mapped type of nine NPI columns and
added `_bidx` / `key_version` companions, every database created before that
commit kept its old shape -- plaintext values, and none of the new columns.
The app does not degrade on such a database, it dies: `RecomputeAllStatuses`
runs at startup and raises
`OperationalError: no such column: loans.borrower_name_bidx` before the UI
is constructed.

This module is the missing step. It is deliberately NOT run automatically at
startup: encrypting is a one-way transform, and a row encrypted under a key
that later goes missing is indistinguishable from data loss. The app detects
that the migration is needed and refuses to start with instructions; the
person runs it when they are ready, having read what it will do.

COLUMN NAMES CONVERGE ON `_ct`
Each encrypted column is renamed to `<name>_ct`, which is exactly what
migrations/0003 produces on Postgres. One set of ORM models then serves both
backends, so wiring Postgres later needs no second mapping and no rename
migration on either side. The ORM keeps the bare ATTRIBUTE names
(`borrower_name` maps to column `borrower_name_ct`), so repositories, the
domain and every use case are untouched.

SQLite is dynamically typed, so the ciphertext BLOB sits happily in a column
originally declared `VARCHAR(255)`/`INTEGER`/`NUMERIC` -- the rename is for
naming parity with Postgres, not because the type would otherwise object.

SAFETY
- Refuses to run twice (detects `key_version`).
- Copies the database file to `<name>.pre-encryption-backup` first and
  refuses to continue if that copy cannot be made or verified.
- Does all work in ONE transaction: either every row is encrypted or none is.
- Verifies before committing by decrypting every row back to its original
  value, and rolls the whole transaction back on any mismatch.
- VACUUMs afterwards, because encrypting the rows does not remove the old
  plaintext from the file's free pages -- it stays greppable without it.
"""

from __future__ import annotations

import shutil
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

from finhive.db.blind_index import compute_blind_index
from finhive.db.encryption import encrypt_amount, encrypt_field
from finhive.db.keys import KeyRing

# table -> (string identity columns, whole-rupee columns, decimal columns,
#           identity columns that carry a `_bidx`)
# The `_bidx` sets mirror migrations/0004_add_identity_blind_index.sql
# exactly, including that report_records has no borrower_group.
_PLAN: dict[str, dict[str, tuple[str, ...]]] = {
    "loans": {
        "strings": ("borrower_name", "borrower_group", "depositor_name", "depositor_group"),
        "rupees": ("amount",),
        "decimals": (),
        "bidx": ("borrower_name", "borrower_group", "depositor_name", "depositor_group"),
    },
    "loan_history": {
        "strings": ("borrower_name", "borrower_group", "depositor_name", "depositor_group"),
        "rupees": ("amount",),
        "decimals": (),
        "bidx": ("borrower_name", "borrower_group", "depositor_name", "depositor_group"),
    },
    "report_records": {
        "strings": ("borrower_name", "depositor_name", "depositor_group"),
        "rupees": ("amount",),
        "decimals": (
            "interest_amount",
            "commission_amount",
            "tds_amount",
            "chq_amount",
        ),
        "bidx": ("borrower_name", "depositor_name", "depositor_group"),
    },
}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def needs_migration(db_path: Path | str) -> bool:
    """True when this database predates KCH-227 and still holds plaintext.

    Detected by the absence of `key_version`, which every encrypted table
    gained in that commit. A brand-new database created by `create_all()`
    already has it, so this correctly returns False there.
    """
    path = Path(db_path)
    if not path.exists():
        return False
    conn = sqlite3.connect(path)
    try:
        present = _tables(conn)
        for table in _PLAN:
            if table in present and "key_version" not in _columns(conn, table):
                return True
        return False
    finally:
        conn.close()


def _to_decimal(value: Any) -> Decimal:
    """Convert a stored NUMERIC to Decimal without ever passing through float.

    sqlite3 hands back a Python float for a REAL-affinity column, and
    `Decimal(0.1)` is 0.1000000000000000055511151231257827 -- the exact trap
    the project's no-float-for-money rule exists to prevent. Going via `str`
    keeps the decimal value the user actually entered.
    """
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def migrate(
    db_path: Path | str,
    key_ring: KeyRing,
    *,
    make_backup: bool = True,
) -> dict[str, int]:
    """Encrypt every plaintext row in place. Returns {table: rows_encrypted}.

    Raises before modifying anything if the backup cannot be made, and rolls
    the whole transaction back if the post-migration read-back fails.
    """
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"no database at {path}")
    if not needs_migration(path):
        raise RuntimeError(
            f"{path} is already migrated (a `key_version` column is present). "
            "Refusing to encrypt twice -- doing so would encrypt the "
            "ciphertext and lose the data irrecoverably."
        )

    if make_backup:
        backup = path.with_suffix(path.suffix + ".pre-encryption-backup")
        shutil.copy2(path, backup)
        if not backup.exists() or backup.stat().st_size != path.stat().st_size:
            raise RuntimeError(
                f"backup at {backup} was not written correctly -- refusing to "
                "start a one-way encryption without a good copy"
            )

    key_data = key_ring.key_data()
    key_index = key_ring.key_index()
    version = key_ring.current_version

    conn = sqlite3.connect(path)
    conn.isolation_level = None  # explicit transaction below
    counts: dict[str, int] = {}
    originals: dict[str, list[tuple]] = {}

    try:
        conn.execute("BEGIN")
        present = _tables(conn)

        for table, plan in _PLAN.items():
            if table not in present:
                continue
            existing = _columns(conn, table)
            if "key_version" in existing:
                continue  # already done (partial re-run)

            # Rename each plaintext column to its `_ct` name, so SQLite ends
            # up with exactly the column names migrations/0003 gives Postgres
            # and one set of ORM models serves both backends. The ORM keeps
            # the bare ATTRIBUTE names, so no repository changes.
            encrypted = (
                list(plan["strings"]) + list(plan["rupees"]) + list(plan["decimals"])
            )
            for column in encrypted:
                if column in existing and f"{column}_ct" not in existing:
                    conn.execute(
                        f"ALTER TABLE {table} RENAME COLUMN {column} TO {column}_ct"
                    )

            for column in plan["bidx"]:
                if f"{column}_bidx" not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column}_bidx BLOB")
            conn.execute(f"ALTER TABLE {table} ADD COLUMN key_version SMALLINT")

            payload = (
                list(plan["strings"]) + list(plan["rupees"]) + list(plan["decimals"])
            )
            rows = conn.execute(
                f"SELECT id, {', '.join(f'{c}_ct' for c in payload)} FROM {table}"
            ).fetchall()
            originals[table] = rows

            for row in rows:
                row_id, values = row[0], row[1:]
                cells = dict(zip(payload, values))
                sets: dict[str, Any] = {"key_version": version}

                for column in plan["strings"]:
                    raw = cells[column]
                    sets[f"{column}_ct"] = (
                        encrypt_field(str(raw), key_data) if raw is not None else None
                    )
                for column in plan["rupees"]:
                    raw = cells[column]
                    sets[f"{column}_ct"] = (
                        encrypt_amount(Decimal(int(raw)), key_data)
                        if raw is not None
                        else None
                    )
                for column in plan["decimals"]:
                    raw = cells[column]
                    sets[f"{column}_ct"] = (
                        encrypt_amount(_to_decimal(raw), key_data)
                        if raw is not None
                        else None
                    )
                for column in plan["bidx"]:
                    raw = cells[column]
                    sets[f"{column}_bidx"] = (
                        compute_blind_index(str(raw), key_index, column=column)
                        if raw is not None
                        else None
                    )

                assignments = ", ".join(f"{c} = ?" for c in sets)
                conn.execute(
                    f"UPDATE {table} SET {assignments} WHERE id = ?",
                    (*sets.values(), row_id),
                )

            counts[table] = len(rows)

        _verify(conn, originals, key_data)
        conn.execute("COMMIT")

        # Encrypting the live rows is NOT enough. SQLite marks the old pages
        # free, it does not zero them, so every pre-migration plaintext name
        # and amount stays readable in the file's free space -- verified by
        # grepping the raw bytes after a migration: 'abcd', 'b1' and 'bg1'
        # were all still present. VACUUM rewrites the database into a fresh
        # file and drops the free pages, which is what actually removes them.
        # It cannot run inside a transaction, hence its position here.
        conn.execute("VACUUM")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    return counts


def _verify(
    conn: sqlite3.Connection,
    originals: dict[str, list[tuple]],
    key_data: bytes,
) -> None:
    """Prove every row still decrypts to exactly what it held before.

    Runs INSIDE the transaction, so a mismatch rolls the whole thing back and
    the database is left untouched. Checking that the ciphertext is merely
    non-null would pass even if every row had been encrypted under the wrong
    key -- only a round-trip comparison against the original values shows the
    data actually survived.

    Decrypts with the key that was just passed in, NOT through the app's
    process-wide active ring: a migration is run as a standalone command with
    no Container, and reaching for global state here made verification fail
    with a key-configuration error rather than a data error.
    """
    from finhive.db.encryption import decrypt_amount, decrypt_field

    for table, rows in originals.items():
        plan = _PLAN[table]
        payload = list(plan["strings"]) + list(plan["rupees"]) + list(plan["decimals"])
        for row in rows:
            row_id, before = row[0], row[1:]
            after = conn.execute(
                f"SELECT {', '.join(f'{c}_ct' for c in payload)} FROM {table} "
                f"WHERE id = ?", (row_id,)
            ).fetchone()
            for column, was, now in zip(payload, before, after):
                if was is None:
                    if now is not None:
                        raise RuntimeError(
                            f"{table}.{column} row {row_id}: NULL became non-NULL"
                        )
                    continue
                if column in plan["strings"]:
                    got: Any = decrypt_field(now, key_data)
                    expected: Any = str(was)
                elif column in plan["rupees"]:
                    got = int(decrypt_amount(now, key_data))
                    expected = int(was)
                else:
                    got = decrypt_amount(now, key_data)
                    expected = _to_decimal(was)
                if got != expected:
                    raise RuntimeError(
                        f"{table}.{column} row {row_id} did not survive the "
                        f"round trip: {expected!r} -> {got!r}"
                    )


def main() -> int:
    """CLI entry point: `python -m loan_manager.infrastructure.migrations.encrypt_existing_rows`."""
    import sys

    from loan_manager.config import DB_PATH
    from loan_manager.infrastructure.security.key_provider import (
        KeyConfigurationError,
        load_keys,
    )

    if not needs_migration(DB_PATH):
        print(f"{DB_PATH} is already encrypted -- nothing to do.")
        return 0

    try:
        ring = load_keys()
    except KeyConfigurationError as exc:
        print(f"Cannot migrate: the master key is not usable.\n\n{exc}", file=sys.stderr)
        return 1

    print(f"About to encrypt existing rows in {DB_PATH}.")
    print("A backup will be written alongside it first.")
    print("This is ONE-WAY: without the master key the data cannot be read again.\n")

    counts = migrate(DB_PATH, ring)
    for table, n in sorted(counts.items()):
        print(f"  {table}: {n} row(s) encrypted")
    print("\nDone. Verified by decrypting every row back to its original value.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
