"""The `before_insert`/`before_update` mapper events that keep each identity
column's `_bidx` companion in sync (KCH-229).

`sqlalchemy_loan_repo.py` filters by comparing a freshly computed blind index
against the stored `_bidx` column -- these tests are what makes that
trustworthy: they assert the stored value really is
`compute_blind_index(current plaintext, key_index, column=...)`, recomputed
on every insert AND every update, not just set once and left stale.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from loan_manager.infrastructure.database.models import Base, LoanModel
from loan_manager.infrastructure.security.key_provider import set_active_key_ring


def _missing() -> str | None:
    """Which dependency of the encryption path is absent, if any.

    Copied verbatim from tests/unit/test_key_provider.py -- see that
    module's docstring for why both `cryptography` and `finhive` must be
    checked, not just `cryptography`.
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

if _MISSING is None:
    from finhive.db.blind_index import compute_blind_index, derive_key_index
    from finhive.db.keys import KeyRing

_MASTER = b"\x77" * 32
_TEST_KEY_RING = KeyRing(current_version=1, masters={1: _MASTER}) if _MISSING is None else None


@pytest.fixture(autouse=True)
def _active_key_ring():
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


def _expected(plaintext: str, *, column: str) -> bytes:
    return compute_blind_index(plaintext, derive_key_index(_MASTER), column=column)


def _make_loan(**over) -> LoanModel:
    now = datetime(2026, 1, 1, 12, 0, 0)
    fields = dict(
        reference_id="2026_01_001",
        borrower_name="carol danvers",
        borrower_group="bg-avengers",
        depositor_name="nick fury",
        depositor_group="dg-shield",
        amount=50000,
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


class TestInsertComputesBlindIndex:
    def test_all_four_identity_columns_get_the_expected_bidx(self, session):
        loan = _make_loan()
        session.add(loan)
        session.commit()

        loan_id = loan.id
        session.expunge_all()
        fetched = session.get(LoanModel, loan_id)

        assert fetched.borrower_name_bidx == _expected("carol danvers", column="borrower_name")
        assert fetched.borrower_group_bidx == _expected("bg-avengers", column="borrower_group")
        assert fetched.depositor_name_bidx == _expected("nick fury", column="depositor_name")
        assert fetched.depositor_group_bidx == _expected("dg-shield", column="depositor_group")

    def test_null_depositor_group_yields_null_bidx(self, session):
        loan = _make_loan(depositor_group=None)
        session.add(loan)
        session.commit()

        loan_id = loan.id
        session.expunge_all()
        fetched = session.get(LoanModel, loan_id)

        assert fetched.depositor_group_bidx is None

    def test_bidx_uses_key_index_not_key_data(self, session):
        """Using key_data (or any key derived through it) here would defeat
        the entire point of a separate key_index -- see
        tests/unit/test_key_provider.py::test_key_index_derives_from_the_master_not_from_key_data.
        """
        from finhive.db.keys import derive_key_data

        loan = _make_loan(borrower_name="carol danvers")
        session.add(loan)
        session.commit()

        loan_id = loan.id
        session.expunge_all()
        fetched = session.get(LoanModel, loan_id)

        wrong_key_index = derive_key_data(_MASTER)  # deliberately the wrong derivation
        wrong = compute_blind_index("carol danvers", wrong_key_index, column="borrower_name")
        assert fetched.borrower_name_bidx != wrong
        assert fetched.borrower_name_bidx == _expected("carol danvers", column="borrower_name")


class TestUpdateRecomputesBlindIndex:
    def test_changing_borrower_group_updates_its_bidx(self, session):
        loan = _make_loan(borrower_group="bg-old")
        session.add(loan)
        session.commit()

        loan.borrower_group = "bg-new"
        session.commit()

        loan_id = loan.id
        session.expunge_all()
        fetched = session.get(LoanModel, loan_id)

        assert fetched.borrower_group == "bg-new"
        assert fetched.borrower_group_bidx == _expected("bg-new", column="borrower_group")
        assert fetched.borrower_group_bidx != _expected("bg-old", column="borrower_group")

    def test_setting_depositor_group_to_none_clears_its_bidx(self, session):
        loan = _make_loan(depositor_group="dg-old")
        session.add(loan)
        session.commit()

        loan.depositor_group = None
        session.commit()

        loan_id = loan.id
        session.expunge_all()
        fetched = session.get(LoanModel, loan_id)

        assert fetched.depositor_group is None
        assert fetched.depositor_group_bidx is None
