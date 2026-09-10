"""Migration 0003 -- encrypt NPI columns at rest before any real data lands
(KCH-95, ADR-2.3, ADR-2.4).

Mirrors test_migration_0002_mvp1_tables.py: DDL shape checks without a
database. Pins down that every identity and financial NPI column is
replaced by a `_ct` column plus `key_version`, and that rates, periods and
dates -- which the derivation check in ADR-2.4 clears as safe -- are left
untouched.
"""

from __future__ import annotations

from pathlib import Path

from finhive.db.migrations import discover_migrations

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_LOANS_AND_LOAN_HISTORY_NPI_COLUMNS = [
    "borrower_name",
    "borrower_group",
    "depositor_name",
    "depositor_group",
    "amount",
]

_REPORT_RECORDS_NPI_COLUMNS = [
    "borrower_name",
    "depositor_name",
    "depositor_group",
    "amount",
    "interest_amount",
    "commission_amount",
    "tds_amount",
    "chq_amount",
]

_REPORT_RECORDS_PLAINTEXT_COLUMNS = [
    "extension_period",
    "extension_period_unit",
    "interest_rate",
    "commission_rate",
    "tds_flag",
    "giving_date",
    "due_date",
    "post_extension_giving_date",
    "post_extension_due_date",
    "paidoff_date",
]


def test_migration_0003_is_discovered_as_encrypt_npi_columns() -> None:
    migrations = discover_migrations(_MIGRATIONS_DIR)

    assert migrations[2].version == 3
    assert migrations[2].name == "encrypt_npi_columns"


def test_migration_0003_replaces_plaintext_npi_columns_with_ciphertext_columns() -> None:
    sql = _migration_0003_sql()
    loans_body = _statement_body(sql, "ALTER TABLE loans")
    loan_history_body = _statement_body(sql, "ALTER TABLE loan_history")

    for body in (loans_body, loan_history_body):
        for column in _LOANS_AND_LOAN_HISTORY_NPI_COLUMNS:
            assert f"DROP COLUMN {column}," in body or f"DROP COLUMN {column}\n" in body, (
                f"plaintext column {column} was not dropped"
            )
            assert f"ADD COLUMN {column}_ct BYTEA" in body, (
                f"missing ciphertext column {column}_ct"
            )


def test_migration_0003_report_records_encrypts_identity_and_financial_columns() -> None:
    sql = _migration_0003_sql()
    body = _statement_body(sql, "ALTER TABLE report_records")

    for column in _REPORT_RECORDS_NPI_COLUMNS:
        assert f"DROP COLUMN {column}," in body or f"DROP COLUMN {column}\n" in body, (
            f"plaintext column {column} was not dropped"
        )
        assert f"ADD COLUMN {column}_ct BYTEA" in body, f"missing ciphertext column {column}_ct"


def test_migration_0003_leaves_rates_periods_and_dates_plaintext() -> None:
    """Decisions 13 and 14: a percentage is not a balance, and dates are
    needed for arithmetic and range filters -- neither is touched here.
    """
    sql = _migration_0003_sql()
    body = _statement_body(sql, "ALTER TABLE report_records")

    for column in _REPORT_RECORDS_PLAINTEXT_COLUMNS:
        assert f"DROP COLUMN {column}" not in body, f"{column} must stay plaintext"
        assert f"{column}_ct" not in sql, f"{column} must not gain a ciphertext column"


def test_migration_0003_adds_key_version_to_every_encrypted_table() -> None:
    sql = _migration_0003_sql()

    for table in ("loans", "loan_history", "report_records"):
        body = _statement_body(sql, f"ALTER TABLE {table}")
        assert "ADD COLUMN key_version SMALLINT NOT NULL DEFAULT 1" in body, (
            f"{table} is missing key_version"
        )


def test_migration_0003_does_not_add_any_derived_index() -> None:
    """ADR-2.4: a blind index (or any derived index) on an amount column is
    a hard rule violation -- and the blind index for identity columns is a
    separate migration (KCH-96), not this one.
    """
    sql = _migration_0003_sql()

    assert "CREATE INDEX" not in sql
    assert "_bidx" not in sql


def test_migration_0003_leaves_loan_meta_and_report_meta_untouched() -> None:
    """No NPI columns live on the per-org counter tables."""
    sql = _migration_0003_sql()

    assert "ALTER TABLE loan_meta" not in sql
    assert "ALTER TABLE reports " not in sql
    assert "ALTER TABLE report_meta" not in sql


def _migration_0003_sql() -> str:
    migrations = discover_migrations(_MIGRATIONS_DIR)
    migration_0003 = next(m for m in migrations if m.version == 3)
    return migration_0003.sql


def _statement_body(sql: str, statement_start: str) -> str:
    start = sql.index(statement_start)
    end = sql.index(";", start)
    return sql[start:end]
