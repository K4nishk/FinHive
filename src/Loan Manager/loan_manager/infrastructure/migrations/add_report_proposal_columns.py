"""One-time migration: add the report-proposal columns KCH-242 needs
(`reports.actor`/`user_request_ct`/`turn_id`, `report_records.borrower_group_ct`/
`due_period`, and `report_records.reference_id`/`giving_date` becoming
nullable) to a database created before this issue.

WHY THIS EXISTS
`Base.metadata.create_all()` creates missing TABLES, never ALTERs an
existing one -- the same gap `encrypt_existing_rows.py` documents for
KCH-227. A database written before KCH-242 lacks `reports.actor`, so the
app would die the first time it tried to read or write a report:
`OperationalError: no such column: reports.actor`.

This module is the missing step, deliberately NOT run automatically at
startup (`main.py` Step 3c refuses and prints the command below instead):
`report_records` is rebuilt in place (see WHY THE REBUILD below), which is a
one-way schema change on the operator's only copy of the loan book.

MUST RUN AFTER encrypt_existing_rows
`report_records.borrower_name_ct` etc. only exist once KCH-227's migration
has run; this migration refuses outright on a still-plaintext database
(`encrypt_existing_rows.needs_migration` is checked first) rather than
building a `borrower_group_ct` column next to plaintext siblings.

WHY THE REBUILD, NOT A PLAIN ALTER
`reports` only gains three new, nullable-or-defaulted columns, so a plain
`ALTER TABLE ... ADD COLUMN` suffices for it (SQLite allows a NOT NULL
column here only because `actor` also carries a `DEFAULT 'FORM'`).
`report_records` is different: `reference_id` and `giving_date` go from
NOT NULL to nullable (a CREATE-mode proposal has neither until approval
mints a loan -- see `domain/entities/report.py`), and SQLite's `ALTER TABLE`
cannot drop a `NOT NULL` constraint. The documented workaround is SQLite's
own 12-step procedure ("Making Other Kinds Of Table Schema Changes" in the
ALTER TABLE docs): build a new table with the target schema, copy every row
across, drop the old table, rename the new one into place, and recreate its
indexes under their original names -- steps 1-8 below; the migration itself
also verifies rather than just trusting them (steps 9-11 do not correspond
to any check this schema needs, since it defines no views or triggers).

SAFETY
- Refuses if `encrypt_existing_rows` still needs to run first, if this
  migration has already run (idempotent), or if no key ring is supplied.
- Backs up via `sqlite3.Connection.backup()` (not a raw file copy -- a
  concurrently-open WAL file cannot be safely copied byte-for-byte) to
  `<db>.pre-kch242-backup`, then verifies that copy with
  `PRAGMA integrity_check` and matching row counts before touching the
  live database at all.
- Does all work in ONE transaction: either every change lands or none does.
- Verifies, INSIDE that transaction, that `PRAGMA foreign_key_check` is
  empty, that `report_records`' row count is unchanged, that every column
  the old table had survived the rebuild byte-for-byte (including every
  `_ct` ciphertext blob, compared raw -- not decrypted-and-recompared, which
  would only prove the plaintext round-trips, not that the exact stored
  bytes were preserved), and that `borrower_name_ct` still decrypts with the
  key ring passed in. Any failure rolls the whole transaction back.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loan_manager.infrastructure.migrations import encrypt_existing_rows

if TYPE_CHECKING:  # pragma: no cover - typing only
    from finhive.db.keys import KeyRing

# Column order matches `Base.metadata.create_all` on the pre-KCH-242 schema
# exactly -- this is every column `report_records` had BEFORE this
# migration, in the order the rebuild copies them.
_REPORT_RECORDS_OLD_COLUMNS: tuple[str, ...] = (
    "id", "report_id", "reference_id", "borrower_name_ct", "depositor_name_ct",
    "depositor_group_ct", "borrower_name_bidx", "depositor_name_bidx",
    "depositor_group_bidx", "amount_ct", "giving_date", "due_date",
    "extension_period", "extension_period_unit", "interest_rate",
    "commission_rate", "tds_flag", "interest_amount_ct", "commission_amount_ct",
    "tds_amount_ct", "chq_amount_ct", "post_extension_giving_date",
    "post_extension_due_date", "paidoff_date", "key_version",
)

# Matches `Base.metadata.create_all` on the CURRENT (post-KCH-242) models.py
# exactly, column-for-column -- verified by
# `test_migrated_schema_matches_create_all` against a fresh `create_all` db,
# so index-name or column-order drift between this literal and models.py is
# caught rather than silently shipped.
_REPORT_RECORDS_CREATE_NEW = """
CREATE TABLE report_records_new (
    id INTEGER NOT NULL,
    report_id VARCHAR(20) NOT NULL,
    reference_id VARCHAR(20),
    borrower_group_ct BLOB,
    borrower_name_ct BLOB NOT NULL,
    depositor_name_ct BLOB NOT NULL,
    depositor_group_ct BLOB,
    borrower_name_bidx BLOB NOT NULL,
    depositor_name_bidx BLOB NOT NULL,
    depositor_group_bidx BLOB,
    amount_ct BLOB NOT NULL,
    giving_date DATE,
    due_date DATE,
    due_period INTEGER,
    extension_period INTEGER NOT NULL,
    extension_period_unit VARCHAR(10) NOT NULL,
    interest_rate NUMERIC(5, 2) NOT NULL,
    commission_rate NUMERIC(5, 2) NOT NULL,
    tds_flag BOOLEAN NOT NULL,
    interest_amount_ct BLOB,
    commission_amount_ct BLOB,
    tds_amount_ct BLOB,
    chq_amount_ct BLOB,
    post_extension_giving_date DATE,
    post_extension_due_date DATE,
    paidoff_date DATE,
    key_version SMALLINT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(report_id) REFERENCES reports (report_id) ON DELETE CASCADE
)
"""

_REPORT_RECORDS_INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_report_records_borrower_name_bidx ON report_records (borrower_name_bidx)",
    "CREATE INDEX ix_report_records_depositor_group_bidx ON report_records (depositor_group_bidx)",
    "CREATE INDEX ix_report_records_depositor_name_bidx ON report_records (depositor_name_bidx)",
    "CREATE INDEX ix_report_records_reference_id ON report_records (reference_id)",
    "CREATE INDEX ix_report_records_report_id ON report_records (report_id)",
)


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def needs_migration(db_path: Path | str) -> bool:
    """True when this database predates KCH-242 and is missing either
    `reports.actor` or `report_records.borrower_group_ct`.

    A missing table is not itself a reason to migrate -- `create_all()`
    will create it fresh, with every KCH-242 column already in place, so a
    brand-new database (or one that never created these tables at all)
    correctly returns False here, same as `encrypt_existing_rows.needs_migration`.
    """
    path = Path(db_path)
    if not path.exists():
        return False
    conn = sqlite3.connect(path)
    try:
        present = _tables(conn)
        return ("reports" in present and "actor" not in _columns(conn, "reports")) or (
            "report_records" in present
            and "borrower_group_ct" not in _columns(conn, "report_records")
        )
    finally:
        conn.close()


def _make_backup(path: Path) -> Path:
    """`sqlite3.Connection.backup()`, not a raw file copy: `shutil.copy2`
    would race a live WAL file and can copy a torn, unusable snapshot.
    Verified immediately with `PRAGMA integrity_check` and matching row
    counts, so a bad backup is caught before anything live is touched.
    """
    backup_path = path.with_name(path.name + ".pre-kch242-backup")
    src = sqlite3.connect(path)
    try:
        dst = sqlite3.connect(backup_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    check_conn = sqlite3.connect(backup_path)
    try:
        (integrity,) = check_conn.execute("PRAGMA integrity_check").fetchone()
        if integrity != "ok":
            raise RuntimeError(
                f"backup at {backup_path} failed PRAGMA integrity_check: {integrity!r}"
            )
        src_conn = sqlite3.connect(path)
        try:
            for table in ("reports", "report_records"):
                if table not in _tables(src_conn):
                    continue
                (src_count,) = src_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                (dst_count,) = check_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                if src_count != dst_count:
                    raise RuntimeError(
                        f"backup at {backup_path} holds {dst_count} {table} "
                        f"rows, source holds {src_count} -- refusing to "
                        "proceed without a good backup"
                    )
        finally:
            src_conn.close()
    finally:
        check_conn.close()
    return backup_path


def _rebuild_report_records(conn: sqlite3.Connection) -> dict[Any, tuple]:
    """SQLite's 12-step ALTER TABLE procedure, steps 3-8 (1-2 -- disabling
    foreign keys and opening the transaction -- and 9-11 -- view/trigger
    reconstruction and the foreign-key re-check -- are the caller's job,
    since they span both tables this migration touches, not just this one).

    Returns the pre-rebuild rows (every OLD column, keyed by id) so the
    caller's `_verify` can prove the copy was byte-for-byte, not merely that
    row counts matched.
    """
    before_rows = {
        row[0]: row
        for row in conn.execute(
            f"SELECT {', '.join(_REPORT_RECORDS_OLD_COLUMNS)} "
            "FROM report_records ORDER BY id"
        ).fetchall()
    }

    conn.execute("DROP TABLE IF EXISTS report_records_new")
    conn.execute(_REPORT_RECORDS_CREATE_NEW)
    conn.execute(
        f"INSERT INTO report_records_new ({', '.join(_REPORT_RECORDS_OLD_COLUMNS)}) "
        f"SELECT {', '.join(_REPORT_RECORDS_OLD_COLUMNS)} FROM report_records"
    )
    conn.execute("DROP TABLE report_records")
    conn.execute("ALTER TABLE report_records_new RENAME TO report_records")
    for statement in _REPORT_RECORDS_INDEXES:
        conn.execute(statement)

    return before_rows


def _verify(
    conn: sqlite3.Connection,
    before_rows: dict[Any, tuple] | None,
    key_data: bytes,
) -> None:
    """Runs INSIDE the transaction; any failure here must propagate so the
    caller rolls the whole thing back rather than committing a partial or
    corrupted rebuild."""
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        raise RuntimeError(
            f"PRAGMA foreign_key_check found violations after the rebuild: "
            f"{fk_violations}"
        )

    if before_rows is None:
        return  # report_records was not rebuilt this run -- nothing to compare

    (after_count,) = conn.execute("SELECT COUNT(*) FROM report_records").fetchone()
    if after_count != len(before_rows):
        raise RuntimeError(
            f"report_records row count changed across the rebuild: "
            f"{len(before_rows)} -> {after_count}"
        )

    after_rows = {
        row[0]: row
        for row in conn.execute(
            f"SELECT {', '.join(_REPORT_RECORDS_OLD_COLUMNS)} "
            "FROM report_records ORDER BY id"
        ).fetchall()
    }
    if after_rows != before_rows:
        raise RuntimeError(
            "report_records rebuild did not copy every pre-existing column "
            "byte-for-byte -- refusing to commit"
        )

    from finhive.db.encryption import decrypt_field

    name_col = _REPORT_RECORDS_OLD_COLUMNS.index("borrower_name_ct")
    for row_id, row in after_rows.items():
        blob = row[name_col]
        try:
            decrypt_field(blob, key_data)
        except Exception as exc:
            raise RuntimeError(
                f"report_records row {row_id}: borrower_name_ct no longer "
                f"decrypts with the given key after the rebuild: {exc}"
            ) from exc


def migrate(
    db_path: Path | str,
    key_ring: KeyRing | None,
    *,
    make_backup: bool = True,
) -> dict[str, str | None]:
    """Add the KCH-242 report-proposal columns in place. Returns
    `{"backup": <path or None>}`.

    Raises before modifying anything if: the database still needs
    `encrypt_existing_rows` first, this migration has already run, no
    `key_ring` was supplied, or the backup cannot be made and verified.
    Rolls the whole transaction back if the in-transaction verification
    (`_verify`) fails.
    """
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"no database at {path}")
    if key_ring is None:
        raise RuntimeError(
            "no key_ring supplied -- this migration verifies "
            "borrower_name_ct still decrypts after the report_records "
            "rebuild, and cannot do that without one"
        )
    if encrypt_existing_rows.needs_migration(path):
        raise RuntimeError(
            f"{path} predates encryption at rest (KCH-227, ARB D-15) -- run "
            "encrypt_existing_rows first. This migration adds "
            "borrower_group_ct alongside the other _ct columns on "
            "report_records, and must never build an encrypted column next "
            "to plaintext siblings."
        )
    if not needs_migration(path):
        raise RuntimeError(
            f"{path} is already migrated (reports.actor and "
            "report_records.borrower_group_ct are both present already). "
            "Refusing to migrate twice."
        )

    backup_path = _make_backup(path) if make_backup else None
    key_data = key_ring.key_data()

    conn = sqlite3.connect(path)
    try:
        # Step 1 of SQLite's 12-step procedure: foreign key enforcement can
        # only be toggled OUTSIDE a transaction, so this runs before BEGIN.
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.isolation_level = None  # explicit transaction control below
        conn.execute("BEGIN IMMEDIATE")

        present = _tables(conn)

        if "reports" in present and "actor" not in _columns(conn, "reports"):
            # `reports` only gains new, nullable-or-defaulted columns, so a
            # plain ALTER suffices -- no rebuild needed for this table.
            conn.execute(
                "ALTER TABLE reports ADD COLUMN actor VARCHAR(5) NOT NULL DEFAULT 'FORM'"
            )
            conn.execute("ALTER TABLE reports ADD COLUMN user_request_ct BLOB")
            conn.execute("ALTER TABLE reports ADD COLUMN turn_id VARCHAR(36)")

        before_rows = None
        if "report_records" in present and "borrower_group_ct" not in _columns(
            conn, "report_records"
        ):
            before_rows = _rebuild_report_records(conn)

        _verify(conn, before_rows, key_data)

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()

    return {"backup": str(backup_path) if backup_path else None}


def main() -> int:
    """CLI entry point:
    `python -m loan_manager.infrastructure.migrations.add_report_proposal_columns --db <path>`."""
    import argparse

    from loan_manager.container import Container
    from loan_manager.infrastructure.security.key_provider import KeyConfigurationError

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="path to the SQLite database to migrate")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Cannot migrate: database not found at {db_path}", file=sys.stderr)
        return 1
    if not needs_migration(db_path):
        print(f"{db_path} is already migrated -- nothing to do.")
        return 0

    try:
        key_ring = Container().get_key_ring(also_protect=(db_path,))
    except KeyConfigurationError as exc:
        print(f"Cannot migrate: the master key is not usable.\n\n{exc}", file=sys.stderr)
        return 1

    print(f"About to add report-proposal columns (KCH-242) to {db_path}.")
    print("A backup will be written alongside it first.\n")

    result = migrate(db_path, key_ring)
    print(f"Backup written to {result['backup']}.")
    print(
        "\nDone. Verified in-transaction: no foreign_key_check violations, "
        "row counts unchanged, every pre-existing column byte-identical "
        "(including ciphertext), and borrower_name_ct still decrypts with "
        "your key."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
