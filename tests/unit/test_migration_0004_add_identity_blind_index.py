"""Migration 0004 -- HMAC blind index for encrypted IDENTITY columns only
(KCH-96, ADR-2.3, ADR-2.4).

Mirrors test_migration_0003_encrypt_npi_columns.py: DDL shape checks without a
database. Pins down that every identity `_ct` column from 0003 gains a
matching indexed `_bidx` column, and that no amount column gains one --
ADR-2.4's hard rule, enforced here per-migration and, project-wide across
every migration file, in tests/unit/test_blind_index_lint.py.
"""

from __future__ import annotations

from pathlib import Path

from finhive.db.blind_index import FORBIDDEN_BLIND_INDEX_COLUMNS
from finhive.db.migrations import discover_migrations

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_LOANS_AND_LOAN_HISTORY_IDENTITY_COLUMNS = [
    "borrower_name",
    "borrower_group",
    "depositor_name",
    "depositor_group",
]

_REPORT_RECORDS_IDENTITY_COLUMNS = [
    "borrower_name",
    "depositor_name",
    "depositor_group",
]


def test_migration_0004_is_discovered_as_add_identity_blind_index() -> None:
    migrations = discover_migrations(_MIGRATIONS_DIR)
    migration_0004 = next(m for m in migrations if m.version == 4)

    assert migration_0004.name == "add_identity_blind_index"


def test_migration_0004_adds_a_bidx_column_for_every_identity_column() -> None:
    sql = _migration_0004_sql()
    loans_body = _statement_body(sql, "ALTER TABLE loans")
    loan_history_body = _statement_body(sql, "ALTER TABLE loan_history")

    for body in (loans_body, loan_history_body):
        for column in _LOANS_AND_LOAN_HISTORY_IDENTITY_COLUMNS:
            assert f"ADD COLUMN {column}_bidx BYTEA" in body, f"missing {column}_bidx"


def test_migration_0004_report_records_adds_a_bidx_column_for_every_identity_column() -> None:
    sql = _migration_0004_sql()
    body = _statement_body(sql, "ALTER TABLE report_records")

    for column in _REPORT_RECORDS_IDENTITY_COLUMNS:
        assert f"ADD COLUMN {column}_bidx BYTEA" in body, f"missing {column}_bidx"


def test_migration_0004_indexes_every_bidx_column_it_adds() -> None:
    sql = _migration_0004_sql()

    for table, columns in (
        ("loans", _LOANS_AND_LOAN_HISTORY_IDENTITY_COLUMNS),
        ("loan_history", _LOANS_AND_LOAN_HISTORY_IDENTITY_COLUMNS),
        ("report_records", _REPORT_RECORDS_IDENTITY_COLUMNS),
    ):
        for column in columns:
            assert f"CREATE INDEX {table}_{column}_bidx_idx ON {table} ({column}_bidx)" in sql, (
                f"{table}.{column}_bidx is not indexed"
            )


def test_migration_0004_never_adds_a_bidx_column_for_an_amount_column() -> None:
    """ADR-2.4, the acceptance criterion this migration exists to satisfy: no
    derived index of any kind on any amount column.
    """
    sql = _migration_0004_sql()

    for column in FORBIDDEN_BLIND_INDEX_COLUMNS:
        assert f"{column}_bidx" not in sql, f"{column} must never gain a blind index"


def test_migration_0004_does_not_touch_amount_bearing_ct_columns() -> None:
    sql = _migration_0004_sql()

    for column in FORBIDDEN_BLIND_INDEX_COLUMNS:
        assert f"{column}_ct" not in sql, f"{column}_ct must not be touched by this migration"


def _migration_0004_sql() -> str:
    migrations = discover_migrations(_MIGRATIONS_DIR)
    migration_0004 = next(m for m in migrations if m.version == 4)
    return migration_0004.sql


def _statement_body(sql: str, statement_start: str) -> str:
    start = sql.index(statement_start)
    end = sql.index(";", start)
    return sql[start:end]
