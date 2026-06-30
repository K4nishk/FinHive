"""Filter logic integration tests using sample data."""
from datetime import date, datetime

import pytest

from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.domain.value_objects.status import LoanStatus
from loan_manager.infrastructure.repositories.sqlalchemy_loan_repo import SqlAlchemyLoanRepository
from tests.fixtures.sample_data import SAMPLE_LOANS


def _create_sample_loans(db_session):
    """Insert all 15 sample loans into the DB."""
    repo = SqlAlchemyLoanRepository(db_session)
    now = datetime.now()
    for i, data in enumerate(SAMPLE_LOANS, start=1):
        loan = Loan(
            id=None,
            reference_id=ReferenceId(f"2026_{data['giving_date'].month:02d}_{i:03d}"),
            borrower_name=data["borrower_name"],
            borrower_group=data["borrower_group"],
            depositor_name=data["depositor_name"],
            depositor_group=data.get("depositor_group"),
            amount=Money(data["amount"]),
            giving_date=data["giving_date"],
            due_period=None,
            due_date=data.get("due_date"),
            status=LoanStatus.ACTIVE,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        repo.save(loan)
    db_session.commit()
    return repo


class TestFilterByBorrowerGroup:
    def test_borrower_group_bg3_returns_2(self, db_session):
        """bg3 contains b3 and b4."""
        repo = _create_sample_loans(db_session)
        results = repo.get_all_active({"borrower_group": "bg3"})
        names = [r.borrower_name for r in results]
        assert sorted(names) == ["b3", "b4"]

    def test_borrower_group_bg1_returns_2(self, db_session):
        """bg1 contains b1 and b9."""
        repo = _create_sample_loans(db_session)
        results = repo.get_all_active({"borrower_group": "bg1"})
        names = [r.borrower_name for r in results]
        assert sorted(names) == ["b1", "b9"]


class TestFilterByDepositorGroup:
    def test_depositor_group_dg3_returns_4(self, db_session):
        """dg3 contains b6, b7, b8, b9."""
        repo = _create_sample_loans(db_session)
        results = repo.get_all_active({"depositor_group": "dg3"})
        names = [r.borrower_name for r in results]
        assert sorted(names) == ["b6", "b7", "b8", "b9"]


class TestByMonthFilter:
    def test_by_month_april_2026(self, db_session):
        """ByMonth April: b1 has due_date 2026-04-02."""
        repo = _create_sample_loans(db_session)
        all_loans = repo.get_all_active()

        # Apply by_month filter in Python (same logic as GetAllLoans use case)
        current_year = 2026
        by_month = 4
        filtered = [
            loan for loan in all_loans
            if loan.due_date is not None
            and loan.due_date.month == by_month
            and loan.due_date.year == current_year
        ]
        names = [loan.borrower_name for loan in filtered]
        assert names == ["b1"]

    def test_by_month_excludes_no_due_date(self, db_session):
        """Loans with no due_date should be excluded by by_month filter."""
        repo = SqlAlchemyLoanRepository(db_session)
        now = datetime.now()

        # One loan with due_date in April
        repo.save(Loan(
            id=None,
            reference_id=ReferenceId("2026_04_001"),
            borrower_name="with_due",
            borrower_group="bg1",
            depositor_name="d1",
            depositor_group="dg1",
            amount=Money(10000),
            giving_date=date(2026, 1, 1),
            due_period=None,
            due_date=date(2026, 4, 15),
            status=LoanStatus.ACTIVE,
            is_active=True,
            created_at=now,
            updated_at=now,
        ))

        # One loan with no due_date
        repo.save(Loan(
            id=None,
            reference_id=ReferenceId("2026_04_002"),
            borrower_name="no_due",
            borrower_group="bg1",
            depositor_name="d2",
            depositor_group="dg1",
            amount=Money(10000),
            giving_date=date(2026, 1, 1),
            due_period=None,
            due_date=None,
            status=LoanStatus.OVERDUE,
            is_active=True,
            created_at=now,
            updated_at=now,
        ))
        db_session.commit()

        all_loans = repo.get_all_active()
        filtered = [
            loan for loan in all_loans
            if loan.due_date is not None
            and loan.due_date.month == 4
            and loan.due_date.year == 2026
        ]
        assert len(filtered) == 1
        assert filtered[0].borrower_name == "with_due"

    def test_no_filter_includes_no_due_date(self, db_session):
        """Without by_month filter, loans with no due_date ARE included."""
        repo = SqlAlchemyLoanRepository(db_session)
        now = datetime.now()

        repo.save(Loan(
            id=None,
            reference_id=ReferenceId("2026_04_001"),
            borrower_name="with_due",
            borrower_group="bg1",
            depositor_name="d1",
            depositor_group="dg1",
            amount=Money(10000),
            giving_date=date(2026, 1, 1),
            due_period=None,
            due_date=date(2026, 4, 15),
            status=LoanStatus.ACTIVE,
            is_active=True,
            created_at=now,
            updated_at=now,
        ))
        repo.save(Loan(
            id=None,
            reference_id=ReferenceId("2026_04_002"),
            borrower_name="no_due",
            borrower_group="bg1",
            depositor_name="d2",
            depositor_group="dg1",
            amount=Money(10000),
            giving_date=date(2026, 1, 1),
            due_period=None,
            due_date=None,
            status=LoanStatus.OVERDUE,
            is_active=True,
            created_at=now,
            updated_at=now,
        ))
        db_session.commit()

        all_loans = repo.get_all_active()
        assert len(all_loans) == 2


class TestFilterExcludesPaidoff:
    def test_inactive_excluded(self, db_session):
        """Paidoff/inactive records should NOT appear in active queries."""
        repo = SqlAlchemyLoanRepository(db_session)
        now = datetime.now()

        repo.save(Loan(
            id=None,
            reference_id=ReferenceId("2026_04_001"),
            borrower_name="active",
            borrower_group="bg1",
            depositor_name="d1",
            depositor_group="dg1",
            amount=Money(10000),
            giving_date=date(2026, 1, 1),
            due_period=None,
            due_date=date(2026, 4, 15),
            status=LoanStatus.ACTIVE,
            is_active=True,
            created_at=now,
            updated_at=now,
        ))
        repo.save(Loan(
            id=None,
            reference_id=ReferenceId("2026_04_002"),
            borrower_name="paidoff",
            borrower_group="bg1",
            depositor_name="d2",
            depositor_group="dg1",
            amount=Money(10000),
            giving_date=date(2026, 1, 1),
            due_period=None,
            due_date=date(2026, 4, 15),
            status=LoanStatus.PAIDOFF,
            is_active=False,
            created_at=now,
            updated_at=now,
        ))
        db_session.commit()

        results = repo.get_all_active({"borrower_group": "bg1"})
        assert len(results) == 1
        assert results[0].borrower_name == "active"
