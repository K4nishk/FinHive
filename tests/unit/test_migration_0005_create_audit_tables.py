"""Migration 0005 -- create proposed_mutations and agent_turns with encrypted
JSONB columns from the start (KCH-98, ADR-2.4).

DDL shape checks without a database, mirroring the earlier migration tests.
Pins down that the `_ct` columns exist (no plaintext JSONB), that
`key_version` is present on both tables, and that no blind index exists on
any column here (the variable-shape blobs never back a lookup).
"""

from __future__ import annotations

from pathlib import Path

from finhive.db.migrations import discover_migrations

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def _migration_0005_sql() -> str:
    migrations = discover_migrations(_MIGRATIONS_DIR)
    migration_0005 = next(m for m in migrations if m.version == 5)
    return migration_0005.sql


def test_migration_0005_is_discovered() -> None:
    migrations = discover_migrations(_MIGRATIONS_DIR)
    migration_0005 = next(m for m in migrations if m.version == 5)

    assert migration_0005.name == "create_audit_tables"


def test_proposed_mutations_has_encrypted_state_columns() -> None:
    sql = _migration_0005_sql()

    assert "before_state_ct BYTEA NOT NULL" in sql
    assert "after_state_ct  BYTEA NOT NULL" in sql


def test_proposed_mutations_has_no_plaintext_state_columns() -> None:
    sql = _migration_0005_sql()

    assert "before_state JSONB" not in sql
    assert "after_state JSONB" not in sql


def test_agent_turns_has_encrypted_trace_column() -> None:
    sql = _migration_0005_sql()

    assert "react_trace_ct    BYTEA NOT NULL" in sql


def test_agent_turns_has_no_plaintext_trace_column() -> None:
    sql = _migration_0005_sql()

    assert "react_trace JSONB" not in sql


def test_both_tables_have_key_version() -> None:
    sql = _migration_0005_sql()
    lower = sql.lower()

    pm_start = lower.index("create table proposed_mutations")
    pm_end = lower.index(";", pm_start)
    pm_body = sql[pm_start:pm_end]
    assert "key_version" in pm_body

    at_start = lower.index("create table agent_turns")
    at_end = lower.index(";", at_start)
    at_body = sql[at_start:at_end]
    assert "key_version" in at_body


def test_no_blind_index_columns() -> None:
    sql = _migration_0005_sql()

    assert "_bidx" not in sql


def test_proposed_mutations_indexes_org_loan_status() -> None:
    sql = _migration_0005_sql()

    assert "proposed_mutations_org_id_idx" in sql
    assert "proposed_mutations_loan_id_idx" in sql
    assert "proposed_mutations_status_idx" in sql


def test_agent_turns_indexes_org_user() -> None:
    sql = _migration_0005_sql()

    assert "agent_turns_org_id_idx" in sql
    assert "agent_turns_user_id_idx" in sql
