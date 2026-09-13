"""Migration 0002 -- port MVP1's six tables to Postgres with org_id (KCH-93).

Mirrors test_migration_0001_orgs_users.py: these tests cover the DDL shape
without a database. MVP1's reference_id/report_id counters (loan_meta /
report_meta) were global, so reference_id and report_id were globally unique.
Multi-tenancy gives each org its own counter, so uniqueness must now be
scoped to (org_id, reference_id) / (org_id, report_id) rather than bare --
these tests pin that down alongside the plain "org_id was added" checks.
"""

from __future__ import annotations

from pathlib import Path

from finhive.db.migrations import discover_migrations

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_MVP1_TABLES = [
    "loans",
    "loan_meta",
    "loan_history",
    "reports",
    "report_records",
    "report_meta",
]


def test_migration_0002_is_discovered_as_port_mvp1_tables() -> None:
    migrations = discover_migrations(_MIGRATIONS_DIR)

    assert migrations[1].version == 2
    assert migrations[1].name == "port_mvp1_tables"


def test_migration_0002_creates_all_six_mvp1_tables() -> None:
    sql = _migration_0002_sql()

    for table in _MVP1_TABLES:
        assert f"CREATE TABLE {table} (" in sql, (
            f"missing CREATE TABLE {table}"
        )


def test_migration_0002_every_table_has_org_id_fk() -> None:
    sql = _migration_0002_sql()

    for table in _MVP1_TABLES:
        body = _table_body(sql, table)
        assert "org_id UUID NOT NULL REFERENCES orgs (id)" in body, (
            f"{table} is missing an org_id FK into orgs"
        )


def test_migration_0002_loans_reference_id_unique_per_org() -> None:
    sql = _migration_0002_sql()
    body = _table_body(sql, "loans")

    assert "UNIQUE (org_id, reference_id)" in body
    assert "reference_id TEXT NOT NULL UNIQUE" not in body


def test_migration_0002_reports_report_id_unique_per_org() -> None:
    sql = _migration_0002_sql()
    body = _table_body(sql, "reports")

    assert "UNIQUE (org_id, report_id)" in body
    assert "report_id TEXT NOT NULL UNIQUE" not in body


def test_migration_0002_loan_meta_counter_is_keyed_per_org() -> None:
    sql = _migration_0002_sql()
    body = _table_body(sql, "loan_meta")

    assert "PRIMARY KEY (org_id, year_month)" in body


def test_migration_0002_report_meta_counter_is_keyed_per_org() -> None:
    sql = _migration_0002_sql()
    body = _table_body(sql, "report_meta")

    assert "PRIMARY KEY (org_id, report_date)" in body


def test_migration_0002_report_records_fk_tenant_scoped() -> None:
    """A bare `report_id` FK would let a row reference another org's report
    row (same report_id, different org_id) since report_id alone is no
    longer unique -- the FK must be composite on (org_id, report_id).
    """
    sql = _migration_0002_sql()
    body = _table_body(sql, "report_records")

    expected = (
        "FOREIGN KEY (org_id, report_id)"
        " REFERENCES reports (org_id, report_id)"
    )
    assert expected in body


def test_migration_0002_preserves_mvp1_indexes() -> None:
    sql = _migration_0002_sql()

    expected_indexes = [
        "CREATE INDEX loans_borrower_name_idx"
        " ON loans (borrower_name)",
        "CREATE INDEX loans_depositor_name_idx"
        " ON loans (depositor_name)",
        "CREATE INDEX loans_status_idx"
        " ON loans (status)",
        "CREATE INDEX loan_history_reference_id_idx"
        " ON loan_history (reference_id)",
        "CREATE INDEX report_records_reference_id_idx"
        " ON report_records (reference_id)",
    ]
    for idx in expected_indexes:
        assert idx in sql, f"missing index: {idx}"


def test_migration_0002_creates_orgs_before_referencing_tables() -> None:
    """0001 creates orgs; 0002 must not re-declare it."""
    sql = _migration_0002_sql()

    assert "CREATE TABLE orgs" not in sql


def _migration_0002_sql() -> str:
    migrations = discover_migrations(_MIGRATIONS_DIR)
    migration_0002 = next(m for m in migrations if m.version == 2)
    return migration_0002.sql


def _table_body(sql: str, table: str) -> str:
    start = sql.index(f"CREATE TABLE {table} (")
    end = sql.index(");", start)
    return sql[start:end]
