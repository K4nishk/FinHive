"""One-time migration unit tests for KCH-242
(`loan_manager.infrastructure.migrations.add_report_proposal_columns`).

Mirrors `tests/unit/test_encryption_migration_and_rotation.py`'s approach:
build a database in the EXACT pre-KCH-242 shape via raw DDL (never through
the app's own repositories -- those already write the NEW schema), with real
rows encrypted through a TEST key ring, then run the migration against it.

Every test uses `tmp_path`, never the real ledger (HARD RULE in the KCH-242
plan: never run this migration against `src/Loan Manager/data/loans.db`).
"""
from __future__ import annotations

import sqlite3
from decimal import Decimal
from importlib.util import find_spec
from pathlib import Path

import pytest
from sqlalchemy import create_engine


def _missing() -> str | None:
    for mod in ("cryptography", "finhive"):
        try:
            if find_spec(mod) is None:
                return mod
        except (ImportError, ValueError):
            return mod
    return None


_MISSING = _missing()
needs_crypto = pytest.mark.skipif(
    _MISSING is not None,
    reason=f"this migration needs `{_MISSING}` -- "
    "pip install -r requirements.txt && pip install -e <repo root>",
)
pytestmark = needs_crypto

M1 = b"\x11" * 32


def _ring(current: int = 1, **masters: bytes):
    from finhive.db.keys import KeyRing

    if not masters:
        masters = {"v1": M1}
    return KeyRing(current_version=current, masters={int(k[1:]): v for k, v in masters.items()})


# Every column `report_records` had BEFORE this migration, in
# `Base.metadata.create_all`'s own column order (see the pre-KCH-242
# `models.py`, or `test_migrated_schema_matches_create_all` below for the
# post-migration shape).
_OLD_REPORT_RECORDS_COLUMNS = (
    "id", "report_id", "reference_id", "borrower_name_ct", "depositor_name_ct",
    "depositor_group_ct", "borrower_name_bidx", "depositor_name_bidx",
    "depositor_group_bidx", "amount_ct", "giving_date", "due_date",
    "extension_period", "extension_period_unit", "interest_rate",
    "commission_rate", "tds_flag", "interest_amount_ct", "commission_amount_ct",
    "tds_amount_ct", "chq_amount_ct", "post_extension_giving_date",
    "post_extension_due_date", "paidoff_date", "key_version",
)


def _insert_report_record(conn, ring, i: int, report_id: str = "RPT_20260101_001") -> None:
    """Insert one pre-KCH-242 `report_records` row (25 positional columns),
    with EVERY nullable column given a real, distinguishing value -- shared
    by `_pre_kch242_db` and any test that needs to insert an extra row (e.g.
    one written through a second, still-open connection to exercise the
    live-WAL backup path)."""
    from finhive.db.blind_index import compute_blind_index
    from finhive.db.encryption import encrypt_amount, encrypt_field

    key_data = ring.key_data()
    key_index = ring.key_index()

    borrower = f"borrower {i}"
    depositor = f"depositor {i}"
    depositor_group = f"depgroup {i}"
    paidoff_month = ((i - 1) % 12) + 1
    paidoff_date = f"2026-{paidoff_month:02d}-15"
    conn.execute(
        f"INSERT INTO report_records VALUES ({', '.join(['?'] * 25)})",
        (
            i, report_id, f"2026_01_{i:03d}",
            encrypt_field(borrower, key_data),
            encrypt_field(depositor, key_data),
            encrypt_field(depositor_group, key_data),
            compute_blind_index(borrower, key_index, column="borrower_name"),
            compute_blind_index(depositor, key_index, column="depositor_name"),
            compute_blind_index(depositor_group, key_index, column="depositor_group"),
            encrypt_amount(Decimal(10000 * i), key_data),
            "2026-01-01", "2026-04-01",
            3, "months", "12.00", "6.00", 0,
            encrypt_amount(Decimal("300.00"), key_data),
            encrypt_amount(Decimal("150.00"), key_data),
            encrypt_amount(Decimal("30.00"), key_data),
            encrypt_amount(Decimal("270.00"), key_data),
            "2026-04-01", "2026-07-01", paidoff_date,
            1,
        ),
    )


def _pre_kch242_db(path, ring, *, n_records: int = 2) -> None:
    """A database in the exact pre-KCH-242 (but POST-KCH-227, i.e. already
    encrypted) shape: `reports` has no actor/user_request_ct/turn_id,
    `report_records` has no borrower_group_ct/due_period and its
    reference_id/giving_date are still NOT NULL."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE reports (
            id INTEGER NOT NULL PRIMARY KEY,
            report_id VARCHAR(20) NOT NULL,
            report_mode VARCHAR(10) NOT NULL,
            status VARCHAR(10) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        CREATE UNIQUE INDEX ix_reports_report_id ON reports (report_id);

        CREATE TABLE report_records (
            id INTEGER NOT NULL PRIMARY KEY,
            report_id VARCHAR(20) NOT NULL,
            reference_id VARCHAR(20) NOT NULL,
            borrower_name_ct BLOB NOT NULL,
            depositor_name_ct BLOB NOT NULL,
            depositor_group_ct BLOB,
            borrower_name_bidx BLOB NOT NULL,
            depositor_name_bidx BLOB NOT NULL,
            depositor_group_bidx BLOB,
            amount_ct BLOB NOT NULL,
            giving_date DATE NOT NULL,
            due_date DATE,
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
            FOREIGN KEY(report_id) REFERENCES reports (report_id) ON DELETE CASCADE
        );
        CREATE INDEX ix_report_records_borrower_name_bidx ON report_records (borrower_name_bidx);
        CREATE INDEX ix_report_records_depositor_group_bidx
            ON report_records (depositor_group_bidx);
        CREATE INDEX ix_report_records_depositor_name_bidx ON report_records (depositor_name_bidx);
        CREATE INDEX ix_report_records_reference_id ON report_records (reference_id);
        CREATE INDEX ix_report_records_report_id ON report_records (report_id);
        """
    )
    conn.execute(
        "INSERT INTO reports VALUES (1, 'RPT_20260101_001', 'Monthly', 'Pending', "
        "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
    )
    for i in range(1, n_records + 1):
        _insert_report_record(conn, ring, i)
    conn.commit()
    conn.close()


def _plaintext_db(path) -> None:
    """A pre-KCH-227 database: fully plaintext, no `_ct`/`key_version`
    columns at all -- `encrypt_existing_rows.needs_migration` must fire on
    this, and this migration must refuse to run before that one has."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE reports (
            id INTEGER NOT NULL PRIMARY KEY,
            report_id VARCHAR(20) NOT NULL,
            report_mode VARCHAR(10) NOT NULL,
            status VARCHAR(10) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        CREATE TABLE report_records (
            id INTEGER NOT NULL PRIMARY KEY,
            report_id VARCHAR(20) NOT NULL,
            reference_id VARCHAR(20) NOT NULL,
            borrower_name VARCHAR(255) NOT NULL,
            depositor_name VARCHAR(255) NOT NULL,
            depositor_group VARCHAR(255),
            amount INTEGER NOT NULL,
            giving_date DATE NOT NULL,
            due_date DATE,
            extension_period INTEGER NOT NULL,
            extension_period_unit VARCHAR(10) NOT NULL,
            interest_rate NUMERIC(5,2) NOT NULL,
            commission_rate NUMERIC(5,2) NOT NULL,
            tds_flag BOOLEAN NOT NULL,
            interest_amount NUMERIC(12,2),
            commission_amount NUMERIC(12,2),
            tds_amount NUMERIC(12,2),
            chq_amount NUMERIC(12,2),
            post_extension_giving_date DATE,
            post_extension_due_date DATE,
            paidoff_date DATE
        );
        """
    )
    conn.commit()
    conn.close()


class TestNeedsMigration:
    def test_fresh_create_all_db_is_not_flagged(self, tmp_path):
        from loan_manager.infrastructure.database.models import Base
        from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
            needs_migration,
        )

        db = tmp_path / "fresh.db"
        Base.metadata.create_all(create_engine(f"sqlite:///{db}"))
        assert needs_migration(db) is False

    def test_nonexistent_db_is_not_flagged(self, tmp_path):
        from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
            needs_migration,
        )

        assert needs_migration(tmp_path / "does-not-exist.db") is False

    def test_pre_kch242_db_is_flagged(self, tmp_path):
        from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
            needs_migration,
        )

        db = tmp_path / "legacy.db"
        _pre_kch242_db(db, _ring())
        assert needs_migration(db) is True


class TestMigrationPreservesRowsByteForByte:
    def test_every_pre_existing_column_round_trips_exactly(self, tmp_path):
        from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
            migrate,
        )

        db = tmp_path / "legacy.db"
        ring = _ring()
        _pre_kch242_db(db, ring, n_records=3)

        before = sqlite3.connect(db)
        before_rows = {
            row[0]: row
            for row in before.execute(
                f"SELECT {', '.join(_OLD_REPORT_RECORDS_COLUMNS)} FROM report_records"
            ).fetchall()
        }
        before.close()
        assert len(before_rows) == 3  # sanity: the fixture actually wrote rows

        migrate(db, ring)

        after = sqlite3.connect(db)
        after_rows = {
            row[0]: row
            for row in after.execute(
                f"SELECT {', '.join(_OLD_REPORT_RECORDS_COLUMNS)} FROM report_records"
            ).fetchall()
        }
        after.close()

        assert after_rows == before_rows, (
            "every column report_records had BEFORE the rebuild -- including "
            "every _ct ciphertext blob -- must survive byte-for-byte"
        )


class TestMigratedSchemaMatchesCreateAll:
    def test_reports_and_report_records_match_a_fresh_create_all_db(self, tmp_path):
        from loan_manager.infrastructure.database.models import Base
        from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
            migrate,
        )

        legacy = tmp_path / "legacy.db"
        ring = _ring()
        _pre_kch242_db(legacy, ring)
        migrate(legacy, ring)

        fresh = tmp_path / "fresh.db"
        Base.metadata.create_all(create_engine(f"sqlite:///{fresh}"))

        legacy_conn = sqlite3.connect(legacy)
        fresh_conn = sqlite3.connect(fresh)
        try:
            for table in ("reports", "report_records"):
                # Keyed by column NAME, not compared as an ordered list:
                # `reports` gains its three new columns via plain
                # `ALTER TABLE ... ADD COLUMN`, which SQLite always appends
                # at the end regardless of where models.py declares them, so
                # physical column order legitimately differs from a fresh
                # `create_all` there. `report_records` is fully rebuilt with
                # the create_all column order, so its dict comparison is
                # exact either way. Each PRAGMA table_info row is
                # (cid, name, type, notnull, dflt_value, pk) -- cid (position)
                # is dropped before comparing so a NOT NULL/default/type/pk
                # mismatch is still caught, just not a reordering.
                def _by_name(info):
                    return {row[1]: row[2:] for row in info}

                legacy_info = _by_name(legacy_conn.execute(f"PRAGMA table_info({table})"))
                fresh_info = _by_name(fresh_conn.execute(f"PRAGMA table_info({table})"))
                assert legacy_info == fresh_info, f"{table}: table_info mismatch"

                legacy_idx = sorted(
                    r[1] for r in legacy_conn.execute(f"PRAGMA index_list({table})")
                )
                fresh_idx = sorted(
                    r[1] for r in fresh_conn.execute(f"PRAGMA index_list({table})")
                )
                assert legacy_idx == fresh_idx, f"{table}: index name set mismatch"

                for index_name in legacy_idx:
                    legacy_cols = legacy_conn.execute(
                        f"PRAGMA index_info({index_name})"
                    ).fetchall()
                    fresh_cols = fresh_conn.execute(
                        f"PRAGMA index_info({index_name})"
                    ).fetchall()
                    assert legacy_cols == fresh_cols, f"{index_name}: index_info mismatch"
        finally:
            legacy_conn.close()
            fresh_conn.close()


class TestRefusals:
    def test_refuses_to_migrate_twice(self, tmp_path):
        from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
            migrate,
        )

        db = tmp_path / "legacy.db"
        ring = _ring()
        _pre_kch242_db(db, ring)
        migrate(db, ring)

        with pytest.raises(RuntimeError, match="already migrated"):
            migrate(db, ring)

    def test_refuses_before_encrypt_existing_rows_has_run(self, tmp_path):
        from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
            migrate,
        )

        db = tmp_path / "plaintext.db"
        _plaintext_db(db)

        with pytest.raises(RuntimeError, match="encrypt_existing_rows|encryption at rest"):
            migrate(db, _ring())

    def test_refuses_without_a_key_ring(self, tmp_path):
        from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
            migrate,
        )

        db = tmp_path / "legacy.db"
        _pre_kch242_db(db, _ring())

        with pytest.raises(RuntimeError, match="key_ring"):
            migrate(db, None)

    def test_migrate_with_the_wrong_key_refuses_and_leaves_the_db_unchanged(
        self, tmp_path
    ):
        """KCH-242 review cycle 2, MINOR-4: `_verify`'s own decrypt check
        (`borrower_name_ct no longer decrypts with the given key`) is real
        code, but nothing in the suite feeds it a WRONG key ring to prove
        it actually fires (mutant M7 -- `_verify`'s decrypt check turned
        into `pass` -- survived cycle 1's mutation run for exactly this
        reason). Rows are encrypted with one key_version-1 master; migrate
        is called with a KeyRing whose OWN key_version-1 master differs --
        same stored `key_version`, wrong key material, exactly what a
        misconfigured `FINHIVE_MASTER_KEY_V1` on the wrong machine would
        produce."""
        from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
            migrate,
            needs_migration,
        )

        db = tmp_path / "legacy.db"
        correct_ring = _ring(v1=M1)
        _pre_kch242_db(db, correct_ring, n_records=2)

        wrong_ring = _ring(v1=b"\x22" * 32)

        with pytest.raises(RuntimeError, match="no longer|decrypt"):
            migrate(db, wrong_ring)

        assert needs_migration(db) is True, (
            "a migration refused over a wrong key must leave the db exactly "
            "as unmigrated as it started"
        )
        conn = sqlite3.connect(db)
        try:
            columns = {r[1] for r in conn.execute("PRAGMA table_info(reports)")}
            assert "actor" not in columns, (
                "the reports ALTER must have been rolled back, not just the "
                "report_records rebuild"
            )
            (count,) = conn.execute("SELECT COUNT(*) FROM report_records").fetchone()
            assert count == 2, "row count must be exactly what it was before the attempt"
        finally:
            conn.close()


class TestBackup:
    def test_backup_is_written_and_intact(self, tmp_path):
        from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
            migrate,
        )

        db = tmp_path / "legacy.db"
        ring = _ring()
        _pre_kch242_db(db, ring, n_records=2)

        result = migrate(db, ring)

        backup_path = db.with_name(db.name + ".pre-kch242-backup")
        assert result["backup"] == str(backup_path)
        assert backup_path.exists()

        conn = sqlite3.connect(backup_path)
        try:
            (integrity,) = conn.execute("PRAGMA integrity_check").fetchone()
            assert integrity == "ok"
            (count,) = conn.execute("SELECT COUNT(*) FROM report_records").fetchone()
            assert count == 2
            # The backup is the PRE-migration shape -- it must NOT have the
            # new columns, or it would not be a faithful backup of what was
            # about to be changed.
            columns = {r[1] for r in conn.execute("PRAGMA table_info(reports)")}
            assert "actor" not in columns
        finally:
            conn.close()

    def test_backup_survives_a_live_wal_connection_with_uncheckpointed_rows(self, tmp_path):
        """KCH-242 review, test gap M8: a naive `shutil.copy2` of the main
        db file races a live WAL -- a row committed through another
        connection but not yet checkpointed back into the main file lives
        ONLY in `-wal` and would be silently missing from such a copy. This
        proves `_make_backup`'s `sqlite3.Connection.backup()` (the SQLite
        Online Backup API, which reads through the WAL) does not have that
        gap."""
        from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
            migrate,
        )

        db = tmp_path / "legacy.db"
        ring = _ring()
        _pre_kch242_db(db, ring, n_records=2)

        held = sqlite3.connect(db)
        try:
            held.execute("PRAGMA journal_mode=WAL")
            _insert_report_record(held, ring, 3)
            held.commit()  # a real, committed row -- just not checkpointed

            result = migrate(db, ring)

            backup_path = Path(result["backup"])
            conn = sqlite3.connect(backup_path)
            try:
                (count,) = conn.execute("SELECT COUNT(*) FROM report_records").fetchone()
                assert count == 3, (
                    "the backup must include the row committed through the "
                    "still-open WAL connection -- a raw file copy would "
                    "have missed it"
                )
            finally:
                conn.close()
        finally:
            held.close()


class TestVerifyFailureRollsBack:
    def test_a_verify_failure_rolls_back_the_whole_transaction(self, tmp_path, monkeypatch):
        """KCH-242 review, test gap M9: forces `_verify` (run INSIDE the
        transaction) to fail and proves the caller's `except Exception:
        ROLLBACK; raise` actually undoes BOTH the `reports` ALTER and the
        `report_records` rebuild -- SQLite DDL is transactional, but only if
        the rollback path is actually exercised somewhere, which no other
        test here does."""
        import loan_manager.infrastructure.migrations.add_report_proposal_columns as mod

        db = tmp_path / "legacy.db"
        ring = _ring()
        _pre_kch242_db(db, ring, n_records=2)

        def _boom(conn, before_rows, key_data):
            raise RuntimeError("simulated verification failure")

        monkeypatch.setattr(mod, "_verify", _boom)

        with pytest.raises(RuntimeError, match="simulated verification failure"):
            mod.migrate(db, ring)

        assert mod.needs_migration(db) is True, (
            "a rolled-back migration must leave the database exactly as "
            "unmigrated as it started"
        )
        conn = sqlite3.connect(db)
        try:
            columns = {r[1] for r in conn.execute("PRAGMA table_info(reports)")}
            assert "actor" not in columns, (
                "the reports ALTER must have been rolled back too, not "
                "just the report_records rebuild"
            )
            (count,) = conn.execute("SELECT COUNT(*) FROM report_records").fetchone()
            assert count == 2, "row count must be exactly what it was before the attempt"
        finally:
            conn.close()


class TestMainCli:
    def test_nonexistent_db_path_errors_instead_of_reporting_already_migrated(
        self, tmp_path, monkeypatch, capsys
    ):
        """KCH-242 review, MINOR: a typo'd or missing --db path must not be
        confused with an up-to-date database -- `needs_migration` returns
        False for BOTH (a fresh/nonexistent db legitimately needs nothing),
        so `main()` must check existence itself before asking that
        question."""
        from loan_manager.infrastructure.migrations.add_report_proposal_columns import (
            main,
        )

        missing = tmp_path / "does-not-exist.db"
        monkeypatch.setattr(
            "sys.argv", ["add_report_proposal_columns", "--db", str(missing)]
        )

        rc = main()

        assert rc != 0, (
            "a nonexistent database path must be an error (non-zero exit), "
            "not silently treated as 'already migrated'"
        )
        stderr = capsys.readouterr().err
        assert "not found" in stderr.lower()
