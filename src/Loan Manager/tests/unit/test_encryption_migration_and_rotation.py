"""The two failure modes a green KCH-227 suite did not cover (KCH-227 follow-up).

Every existing encryption test builds a FRESH schema and a single key version,
so neither of the defects this file pins could show up:

1. An existing, pre-encryption database. `create_all()` makes missing tables,
   never ALTERs one, so a database written before KCH-227 keeps plaintext and
   has no `_bidx`/`key_version` columns -- and the app dies at startup on it.
2. A key rotation. With one key version loaded, "decrypt with the current key"
   and "decrypt with the key this row was written under" are the same thing.
   They stop being the same the moment the ring advances.

Both were found by running the real thing against a copy of the real database
rather than by reading the code.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal
from importlib.util import find_spec

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import sessionmaker


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
    reason=f"encryption at rest needs `{_MISSING}` — "
    "pip install -r requirements.txt && pip install -e <repo root>",
)

pytestmark = needs_crypto

M1 = b"\x11" * 32
M2 = b"\x22" * 32


def _ring(current: int, **masters: bytes):
    from finhive.db.keys import KeyRing

    return KeyRing(current_version=current, masters={int(k[1:]): v for k, v in masters.items()})


def _legacy_db(path) -> None:
    """A database in the exact pre-KCH-227 shape: plaintext, no new columns."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE loans (
            id INTEGER NOT NULL PRIMARY KEY,
            reference_id VARCHAR(20) NOT NULL,
            borrower_name VARCHAR(255) NOT NULL,
            borrower_group VARCHAR(255) NOT NULL,
            depositor_name VARCHAR(255) NOT NULL,
            depositor_group VARCHAR(255),
            amount INTEGER NOT NULL,
            giving_date DATE NOT NULL,
            due_period INTEGER,
            due_date DATE,
            status VARCHAR(10) NOT NULL,
            is_active BOOLEAN NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        INSERT INTO loans VALUES
            (1,'2026_01_1','ravindra','bg1','anita','dg1',10000,'2026-01-01',
             NULL,'2026-06-01','Active',1,'2026-01-01','2026-01-01'),
            (2,'2026_01_2','sunita','bg13','vijay',NULL,25000,'2026-01-02',
             NULL,'2026-07-01','Active',1,'2026-01-02','2026-01-02');
        """
    )
    conn.commit()
    conn.close()


class TestExistingDatabaseMigration:
    def test_an_unmigrated_database_is_detected(self, tmp_path):
        from loan_manager.infrastructure.migrations.encrypt_existing_rows import (
            needs_migration,
        )

        db = tmp_path / "legacy.db"
        _legacy_db(db)
        assert needs_migration(db) is True

    def test_a_fresh_database_does_not_look_unmigrated(self, tmp_path):
        """The check must not fire on a database create_all() just made, or
        the app would refuse to start on a clean install."""
        from loan_manager.infrastructure.database.models import Base
        from loan_manager.infrastructure.migrations.encrypt_existing_rows import (
            needs_migration,
        )

        db = tmp_path / "fresh.db"
        Base.metadata.create_all(create_engine(f"sqlite:///{db}"))
        assert needs_migration(db) is False

    def test_migration_encrypts_rows_and_they_read_back_identically(self, tmp_path):
        from loan_manager.infrastructure.database.models import LoanModel
        from loan_manager.infrastructure.migrations.encrypt_existing_rows import (
            migrate,
        )
        from loan_manager.infrastructure.security.key_provider import (
            set_active_key_ring,
        )

        db = tmp_path / "legacy.db"
        _legacy_db(db)
        ring = _ring(1, v1=M1)

        assert migrate(db, ring)["loans"] == 2

        set_active_key_ring(ring)
        session = sessionmaker(bind=create_engine(f"sqlite:///{db}"))()
        rows = {r.reference_id: r for r in session.query(LoanModel).all()}
        assert rows["2026_01_1"].borrower_name == "ravindra"
        assert rows["2026_01_1"].amount == 10000
        assert rows["2026_01_2"].depositor_group is None  # NULL stays NULL

    def test_migration_leaves_no_plaintext_in_the_file(self, tmp_path):
        """Encrypting the live rows is not enough: SQLite frees the old pages
        without zeroing them, so the pre-migration values stay greppable until
        the file is VACUUMed. This asserts the VACUUM actually happened."""
        from loan_manager.infrastructure.migrations.encrypt_existing_rows import (
            migrate,
        )

        db = tmp_path / "legacy.db"
        _legacy_db(db)
        migrate(db, _ring(1, v1=M1))

        raw = db.read_bytes()
        for secret in (b"ravindra", b"sunita", b"anita", b"bg1", b"bg13"):
            assert secret not in raw, f"{secret!r} survived the migration in free pages"

    def test_migration_writes_a_backup_before_touching_anything(self, tmp_path):
        from loan_manager.infrastructure.migrations.encrypt_existing_rows import (
            migrate,
        )

        db = tmp_path / "legacy.db"
        _legacy_db(db)
        migrate(db, _ring(1, v1=M1))

        backup = tmp_path / "legacy.db.pre-encryption-backup"
        assert backup.exists()
        # the backup must still be the readable original, not a copy of the
        # encrypted result -- otherwise it is worthless as a recovery path
        assert b"ravindra" in backup.read_bytes()

    def test_migration_refuses_to_run_twice(self, tmp_path):
        """Encrypting ciphertext would destroy the data with no way back."""
        from loan_manager.infrastructure.migrations.encrypt_existing_rows import (
            migrate,
        )

        db = tmp_path / "legacy.db"
        _legacy_db(db)
        migrate(db, _ring(1, v1=M1))
        with pytest.raises(RuntimeError, match="already migrated"):
            migrate(db, _ring(1, v1=M1))


class TestKeyRotation:
    def _write_under_v1(self, db):
        from loan_manager.infrastructure.database.models import Base, LoanModel
        from loan_manager.infrastructure.security.key_provider import (
            set_active_key_ring,
        )

        set_active_key_ring(_ring(1, v1=M1))
        engine = create_engine(f"sqlite:///{db}")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        session.add(
            LoanModel(
                reference_id="2026_01_1", borrower_name="ravindra",
                borrower_group="bg1", depositor_name="anita", depositor_group="dg1",
                amount=10000, giving_date=date(2026, 1, 1),
                created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
                status="Active", is_active=True,
            )
        )
        session.commit()
        session.close()
        return engine

    def test_key_version_records_the_ring_not_a_literal(self, tmp_path):
        """It was a hardcoded `default=1`, so a row written under version 2 was
        stamped 1 -- an authoritative-looking value that was simply false."""
        from loan_manager.infrastructure.database.models import Base, LoanModel
        from loan_manager.infrastructure.security.key_provider import (
            set_active_key_ring,
        )

        db = tmp_path / "v2.db"
        set_active_key_ring(_ring(2, v1=M1, v2=M2))
        engine = create_engine(f"sqlite:///{db}")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        session.add(
            LoanModel(
                reference_id="2026_01_9", borrower_name="x", borrower_group="bg1",
                depositor_name="y", depositor_group=None, amount=1,
                giving_date=date(2026, 1, 1), created_at=datetime(2026, 1, 1),
                updated_at=datetime(2026, 1, 1), status="Active", is_active=True,
            )
        )
        session.commit()

        stored = sqlite3.connect(db).execute("SELECT key_version FROM loans").fetchone()
        assert stored[0] == 2

    def test_a_row_written_under_the_old_key_still_reads_after_rotation(self, tmp_path):
        from loan_manager.infrastructure.database.models import LoanModel
        from loan_manager.infrastructure.security.key_provider import (
            set_active_key_ring,
        )

        db = tmp_path / "rot.db"
        engine = self._write_under_v1(db)

        set_active_key_ring(_ring(2, v1=M1, v2=M2))
        session = sessionmaker(bind=engine)()
        assert session.query(LoanModel).one().borrower_name == "ravindra"

    def test_filters_still_match_after_rotation(self, tmp_path):
        """The nastiest half: decryption can survive a rotation while the blind
        index silently does not, so every filter returns zero rows against a
        loan book that is completely intact. Silent, not an error."""
        from loan_manager.infrastructure.repositories.sqlalchemy_loan_repo import (
            SqlAlchemyLoanRepository,
        )
        from loan_manager.infrastructure.security.key_provider import (
            set_active_key_ring,
        )

        db = tmp_path / "rot.db"
        engine = self._write_under_v1(db)

        set_active_key_ring(_ring(2, v1=M1, v2=M2))
        repo = SqlAlchemyLoanRepository(sessionmaker(bind=engine)())
        assert len(repo.get_all_active({"borrower_group": "bg1"})) == 1
        assert len(repo.get_all_active({"borrower_group": "bg99"})) == 0

    def test_dropping_the_old_master_fails_loudly(self, tmp_path):
        """Rotation tolerance must not become "decrypts with anything". Once
        v1's master is gone the row is genuinely unreadable, and that must
        raise rather than return None or empty."""
        from finhive.db.encryption import DecryptionError
        from loan_manager.infrastructure.database.models import LoanModel
        from loan_manager.infrastructure.security.key_provider import (
            set_active_key_ring,
        )

        db = tmp_path / "rot.db"
        engine = self._write_under_v1(db)

        set_active_key_ring(_ring(2, v2=M2))
        session = sessionmaker(bind=engine)()
        with pytest.raises(DecryptionError):
            _ = session.query(LoanModel).one().borrower_name


class TestWholeRupeeGuardOnTheWayIn:
    """The guard used to sit only on the read path, so a bad value committed
    and then made that row -- and any query loading it -- raise forever."""

    def test_a_non_integral_amount_is_refused_before_it_is_stored(self, tmp_path):
        from loan_manager.infrastructure.database.models import Base, LoanModel
        from loan_manager.infrastructure.security.key_provider import (
            set_active_key_ring,
        )

        set_active_key_ring(_ring(1, v1=M1))
        engine = create_engine(f"sqlite:///{tmp_path / 'r.db'}")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        session.add(
            LoanModel(
                reference_id="2026_01_3", borrower_name="x", borrower_group="bg1",
                depositor_name="y", depositor_group=None,
                amount=Decimal("100.50"),
                giving_date=date(2026, 1, 1), created_at=datetime(2026, 1, 1),
                updated_at=datetime(2026, 1, 1), status="Active", is_active=True,
            )
        )
        # SQLAlchemy wraps a TypeDecorator's ValueError in StatementError;
        # the original is the __cause__, so assert on both rather than on the
        # wrapper's text alone.
        with pytest.raises(StatementError) as exc:
            session.commit()
        assert isinstance(exc.value.orig, ValueError)
        assert "whole rupees" in str(exc.value.orig)
        session.rollback()

        # and nothing was persisted
        assert session.query(LoanModel).count() == 0

    def test_a_float_amount_is_refused(self, tmp_path):
        """`Decimal(0.1)` is 0.1000000000000000055... -- the exact trap the
        project's no-float-for-money rule exists to prevent."""
        from loan_manager.infrastructure.database.models import Base, LoanModel
        from loan_manager.infrastructure.security.key_provider import (
            set_active_key_ring,
        )

        set_active_key_ring(_ring(1, v1=M1))
        engine = create_engine(f"sqlite:///{tmp_path / 'f.db'}")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        session.add(
            LoanModel(
                reference_id="2026_01_4", borrower_name="x", borrower_group="bg1",
                depositor_name="y", depositor_group=None, amount=100.0,
                giving_date=date(2026, 1, 1), created_at=datetime(2026, 1, 1),
                updated_at=datetime(2026, 1, 1), status="Active", is_active=True,
            )
        )
        with pytest.raises(StatementError) as exc:
            session.commit()
        assert isinstance(exc.value.orig, ValueError)
        assert "never float" in str(exc.value.orig)
        session.rollback()


class TestBackendSchemaConvergence:
    """The SQLite models and the Postgres migrations must name columns the same.

    They diverged once already: the models mapped bare `borrower_name` while
    migrations/0003 creates `borrower_name_ct`, so the same ORM could not have
    read a Postgres database at all. Wiring Postgres later (ARB D-16) is only
    "smooth" if one set of models serves both, so this pins the contract
    rather than leaving it to be rediscovered at the pivot.

    Runs without Postgres: it compares the ORM's declared column names against
    the migration SQL as text.
    """

    # tests/unit/<file> -> unit -> tests -> "Loan Manager" -> src -> repo root
    _PG = Path(__file__).resolve().parents[4] / "migrations"

    def _postgres_columns(self) -> set[str]:
        import re

        if not self._PG.exists():
            pytest.skip(f"Postgres migrations not present at {self._PG}")

        sql = "".join(
            (self._PG / name).read_text()
            for name in (
                "0003_encrypt_npi_columns.sql",
                "0004_add_identity_blind_index.sql",
            )
        )
        return set(re.findall(r"ADD COLUMN (\w+)", sql)) | set(
            re.findall(r"TO (\w+)", sql)
        )

    @needs_crypto
    @pytest.mark.parametrize(
        "model_name", ["LoanModel", "LoanHistoryModel", "ReportRecordModel"]
    )
    def test_every_encrypted_column_exists_in_the_postgres_migrations(self, model_name):
        from loan_manager.infrastructure.database import models as m

        model = getattr(m, model_name)
        declared = {
            c.name
            for c in model.__table__.columns
            if c.name.endswith("_ct") or c.name.endswith("_bidx")
        }
        assert declared, f"{model_name} declares no encrypted columns"

        missing = sorted(declared - self._postgres_columns())
        assert not missing, (
            f"{model_name} maps {missing}, which migrations/0003+0004 do not "
            f"create. The ORM would not read a Postgres database."
        )

    @needs_crypto
    def test_attribute_names_stay_bare_so_repositories_are_untouched(self):
        """The `_ct` suffix belongs to the DATABASE column, not the Python
        attribute. If these ever diverge, every repository and mapper function
        has to change with them."""
        from loan_manager.infrastructure.database.models import LoanModel

        for attr in ("borrower_name", "borrower_group", "depositor_name", "amount"):
            assert hasattr(LoanModel, attr)
            assert LoanModel.__table__.columns[
                LoanModel.__mapper__.columns[attr].name
            ].name == f"{attr}_ct"


@needs_crypto
def test_legacy_migration_leaves_no_plaintext_names_in_file(tmp_path):
    """What this actually proves, honestly scoped: migrating a pre-KCH-227
    `loans` table (`_legacy_db` above -- one table, borrower/depositor names
    and groups only, no `loan_history`, no `report_records`, no derived
    amounts) leaves none of the fixture's plaintext names/groups readable in
    the migrated file.

    `_legacy_db` also seeds an `amount` column (10000, 25000) -- present in
    the fixture, but NOT one of the secrets this test's needle list checks,
    so this test asserts nothing about whether `amount` leaked.

    It does NOT prove the cross-table or derived-amount claims -- those, plus
    the WAL/journal and freshly-written (non-legacy) rows, are covered by
    `tests/integration/test_encryption_at_rest.py`.
    """
    from loan_manager.infrastructure.migrations.encrypt_existing_rows import migrate

    db = tmp_path / "legacy.db"
    _legacy_db(db)
    migrate(db, _ring(1, v1=M1))

    raw = db.read_bytes()
    for secret in (b"ravindra", b"sunita", b"anita", b"vijay", b"bg1", b"bg13", b"dg1"):
        assert secret not in raw, f"{secret!r} is readable without the key"


@needs_crypto
def test_negative_derived_amounts_are_refused(tmp_path):
    """Operator decision 2026-09-23: negative amounts are not expected, so a
    negative is a calculation defect and must surface rather than persist."""
    from finhive.db.encryption import encrypt_amount

    with pytest.raises(ValueError, match="non-negative"):
        encrypt_amount(Decimal("-1.00"), M1)
