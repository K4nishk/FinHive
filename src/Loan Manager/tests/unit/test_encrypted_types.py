"""Encrypted-column TypeDecorators at the ORM<->DB boundary (KCH-227, ARB D-15).

This is the test D-15 rests on: not that `encrypt_field`/`encrypt_amount`
work in isolation (`finhive/db/encryption.py` already has its own suite for
that), but that a value written through the ORM to a real SQLite file is
unrecoverable without the key and comes back byte-for-byte through the
mapped attribute. A mock session cannot prove the bytes on disk are
ciphertext -- only a raw `sqlite3` read of a real file can.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from loan_manager.infrastructure.database.encrypted_types import (
    EncryptedDecimal,
    EncryptedRupees,
    EncryptedString,
)
from loan_manager.infrastructure.database.models import (
    Base,
    LoanModel,
    ReportModel,
    ReportRecordModel,
)
from loan_manager.infrastructure.security.key_provider import (
    KeyConfigurationError,
    active_key_data,
    set_active_key_ring,
)


def _missing() -> str | None:
    """Which dependency of the encryption path is absent, if any.

    Copied verbatim from tests/unit/test_key_provider.py rather than
    imported -- see that module's docstring for why both `cryptography` and
    `finhive` must be checked, not just `cryptography`.
    """
    from importlib.util import find_spec

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

# finhive.db.encryption / finhive.db.keys are only importable once the guard
# above has already decided the suite will run -- importing them at module
# scope unconditionally would turn a missing dependency into a collection
# error instead of a clean skip.
if _MISSING is None:
    from finhive.db.encryption import DecryptionError
    from finhive.db.keys import KeyRing


# A key distinct from the one tests/conftest.py's autouse fixture installs,
# so a bug that accidentally fell back to some other ambient key would show
# up as a decryption failure instead of silently passing.
_TEST_KEY_RING = KeyRing(current_version=1, masters={1: b"\x99" * 32}) if _MISSING is None else None


@pytest.fixture(autouse=True)
def _this_modules_key_ring():
    """Override conftest's ambient key with one local to this file.

    Every test in this module gets it for free; the no-active-key test below
    clears it explicitly for the duration of one assertion.
    """
    set_active_key_ring(_TEST_KEY_RING)
    yield
    set_active_key_ring(_TEST_KEY_RING)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=True)
    s = Session()
    yield s
    s.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _make_loan(**over) -> LoanModel:
    now = datetime(2026, 1, 1, 12, 0, 0)
    fields = dict(
        reference_id="2026_01_001",
        borrower_name="alice cooper",
        borrower_group="bg-north",
        depositor_name="bob marley",
        depositor_group="dg-east",
        amount=125000,
        giving_date=date(2026, 1, 1),
        due_period=None,
        due_date=date(2026, 4, 1),
        status="Active",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    fields.update(over)
    return LoanModel(**fields)


class TestRoundTrip:
    def test_loan_model_round_trips_all_encrypted_fields(self, session):
        loan = _make_loan()
        session.add(loan)
        session.commit()

        loan_id = loan.id
        session.expunge_all()

        fetched = session.get(LoanModel, loan_id)
        assert fetched.borrower_name == "alice cooper"
        assert fetched.borrower_group == "bg-north"
        assert fetched.depositor_name == "bob marley"
        assert fetched.depositor_group == "dg-east"
        assert fetched.amount == 125000

    def test_null_depositor_group_round_trips_as_none(self, session):
        loan = _make_loan(depositor_group=None)
        session.add(loan)
        session.commit()

        loan_id = loan.id
        session.expunge_all()

        fetched = session.get(LoanModel, loan_id)
        assert fetched.depositor_group is None

    def test_amount_round_trips_as_int_not_decimal_or_str(self, session):
        loan = _make_loan(amount=999999)
        session.add(loan)
        session.commit()

        loan_id = loan.id
        session.expunge_all()

        fetched = session.get(LoanModel, loan_id)
        assert fetched.amount == 999999
        assert type(fetched.amount) is int

    def test_report_record_derived_amounts_round_trip_as_decimal(self, session):
        report = ReportModel(
            report_id="R2026_01_001",
            report_mode="Daily",
            status="Pending",
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )
        record = ReportRecordModel(
            report_id="R2026_01_001",
            reference_id="2026_01_001",
            borrower_name="alice cooper",
            depositor_name="bob marley",
            depositor_group="dg-east",
            amount=125000,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
            extension_period=3,
            extension_period_unit="Months",
            interest_rate=Decimal("12.00"),
            commission_rate=Decimal("2.00"),
            tds_flag=False,
            interest_amount=Decimal("3750.50"),
            commission_amount=Decimal("625.25"),
            tds_amount=None,
            chq_amount=Decimal("4375.75"),
        )
        report.records.append(record)
        session.add(report)
        session.commit()

        record_id = record.id
        session.expunge_all()

        fetched = session.get(ReportRecordModel, record_id)
        assert fetched.interest_amount == Decimal("3750.50")
        assert type(fetched.interest_amount) is Decimal
        assert fetched.commission_amount == Decimal("625.25")
        assert fetched.chq_amount == Decimal("4375.75")
        assert fetched.tds_amount is None


class TestEncryptedRupeesCorruption:
    def test_raises_value_error_on_a_non_integral_stored_value(self):
        """A fractional stored amount means data corruption for the current
        single whole-rupee user, not a legitimate value -- EncryptedRupees
        must raise rather than truncate it away silently.
        """
        from finhive.db.encryption import encrypt_amount

        corrupt_blob = encrypt_amount(Decimal("100.50"), active_key_data())

        with pytest.raises(ValueError, match="100.50"):
            EncryptedRupees().process_result_value(corrupt_blob, None)


class TestNoPlaintextOnDisk:
    def test_no_fixture_value_appears_anywhere_in_the_file(self, tmp_path):
        """The assertion D-15 actually rests on: a mock session cannot prove
        the bytes on disk are ciphertext, only a raw read of a real file can.
        """
        db_path = tmp_path / "no_plaintext.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, expire_on_commit=True)
        s = Session()

        loan = _make_loan(
            borrower_name="zolgratharin quinceberry",
            borrower_group="unmistakably-distinct-group",
            depositor_name="fennimore vashcott",
            depositor_group="another-unique-group",
            amount=7654321,
        )
        s.add(loan)
        s.commit()
        s.close()
        engine.dispose()

        plaintext_needles = [
            "zolgratharin quinceberry",
            "unmistakably-distinct-group",
            "fennimore vashcott",
            "another-unique-group",
            "7654321",
        ]

        raw = sqlite3.connect(str(db_path))
        try:
            cursor = raw.execute("SELECT * FROM loans")
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
        finally:
            raw.close()

        assert rows, "expected at least one row written to the file"

        # KCH-229: the blind-index columns are the one place a plaintext
        # equality relationship is deliberately still visible (two loans
        # with the same borrower_group have equal borrower_group_bidx) --
        # but the VALUE itself must not be eyeball-reversible to the
        # plaintext. Check them explicitly, not just as part of the
        # generic "no column leaks" sweep below.
        bidx_columns = [
            "borrower_name_bidx",
            "borrower_group_bidx",
            "depositor_name_bidx",
            "depositor_group_bidx",
        ]
        assert set(bidx_columns).issubset(columns), (
            "expected blind-index columns on the loans table"
        )
        row = dict(zip(columns, rows[0]))
        for bidx_column in bidx_columns:
            value = row[bidx_column]
            assert isinstance(value, (bytes, bytearray)) and len(value) > 0, (
                f"{bidx_column} should hold a non-empty HMAC digest"
            )

        for row in rows:
            for column, value in zip(columns, row):
                rendered = value if isinstance(value, (bytes, bytearray)) else str(value)
                rendered_text = (
                    rendered.decode("utf-8", errors="replace")
                    if isinstance(rendered, (bytes, bytearray))
                    else rendered
                )
                for needle in plaintext_needles:
                    assert needle not in rendered_text, (
                        f"plaintext {needle!r} leaked into column {column!r}"
                    )
                    if isinstance(rendered, (bytes, bytearray)):
                        assert needle.encode("utf-8") not in rendered, (
                            f"plaintext {needle!r} leaked into column {column!r} (raw bytes)"
                        )


class TestTamperDetection:
    def test_corrupting_one_byte_raises_decryption_error(self):
        blob = EncryptedString().process_bind_param("do not tamper with me", None)
        tampered = bytearray(blob)
        tampered[-1] ^= 0xFF  # flip a bit inside the GCM auth tag

        with pytest.raises(DecryptionError):
            EncryptedString().process_result_value(bytes(tampered), None)


class TestRandomIV:
    def test_same_value_encrypted_twice_yields_different_ciphertext(self):
        first = EncryptedString().process_bind_param("repeat me", None)
        second = EncryptedString().process_bind_param("repeat me", None)

        assert first != second
        # ... yet both still decrypt back to the same plaintext.
        assert EncryptedString().process_result_value(first, None) == "repeat me"
        assert EncryptedString().process_result_value(second, None) == "repeat me"

    def test_same_amount_encrypted_twice_yields_different_ciphertext(self):
        first = EncryptedDecimal().process_bind_param(Decimal("42.00"), None)
        second = EncryptedDecimal().process_bind_param(Decimal("42.00"), None)

        assert first != second


class TestNoActiveKey:
    def test_encrypted_string_bind_raises_without_an_active_key(self):
        set_active_key_ring(None)
        with pytest.raises(KeyConfigurationError):
            EncryptedString().process_bind_param("anything", None)

    def test_encrypted_rupees_result_raises_without_an_active_key(self):
        blob = EncryptedRupees().process_bind_param(100, None)
        set_active_key_ring(None)
        with pytest.raises(KeyConfigurationError):
            EncryptedRupees().process_result_value(blob, None)

    def test_encrypted_decimal_bind_raises_without_an_active_key(self):
        set_active_key_ring(None)
        with pytest.raises(KeyConfigurationError):
            EncryptedDecimal().process_bind_param(Decimal("1.00"), None)
