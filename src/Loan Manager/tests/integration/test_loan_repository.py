"""Loan repository integration tests."""
from datetime import date, datetime

import pytest

from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.domain.value_objects.status import LoanStatus
from loan_manager.infrastructure.repositories.sqlalchemy_loan_repo import SqlAlchemyLoanRepository


def _make_loan(
    ref_id: str = "2026_03_001",
    borrower_name: str = "test_borrower",
    borrower_group: str = "bg1",
    depositor_name: str = "test_depositor",
    depositor_group: str = "dg1",
    amount: int = 10000,
    giving_date: date = date(2026, 1, 1),
    due_date: date | None = date(2026, 4, 1),
    status: LoanStatus = LoanStatus.ACTIVE,
    is_active: bool = True,
) -> Loan:
    now = datetime.now()
    return Loan(
        id=None,
        reference_id=ReferenceId(ref_id),
        borrower_name=borrower_name,
        borrower_group=borrower_group,
        depositor_name=depositor_name,
        depositor_group=depositor_group,
        amount=Money(amount),
        giving_date=giving_date,
        due_period=None,
        due_date=due_date,
        status=status,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


class TestSqlAlchemyLoanRepository:
    def test_save_and_get_by_reference_id(self, db_session):
        repo = SqlAlchemyLoanRepository(db_session)
        loan = _make_loan()
        saved = repo.save(loan)
        db_session.commit()

        retrieved = repo.get_by_reference_id("2026_03_001")
        assert retrieved is not None
        assert str(retrieved.reference_id) == "2026_03_001"
        assert retrieved.borrower_name == "test_borrower"
        assert int(retrieved.amount) == 10000

    def test_save_upsert_updates_existing(self, db_session):
        repo = SqlAlchemyLoanRepository(db_session)
        loan = _make_loan()
        repo.save(loan)
        db_session.commit()

        # Update the loan
        loan.borrower_name = "updated_borrower"
        loan.updated_at = datetime.now()
        repo.save(loan)
        db_session.commit()

        retrieved = repo.get_by_reference_id("2026_03_001")
        assert retrieved.borrower_name == "updated_borrower"

    def test_get_all_active_returns_only_active(self, db_session):
        repo = SqlAlchemyLoanRepository(db_session)
        repo.save(_make_loan("2026_03_001", is_active=True))
        repo.save(_make_loan("2026_03_002", is_active=False))
        db_session.commit()

        active = repo.get_all_active()
        assert len(active) == 1
        assert str(active[0].reference_id) == "2026_03_001"

    def test_delete_removes_loan(self, db_session):
        repo = SqlAlchemyLoanRepository(db_session)
        repo.save(_make_loan())
        db_session.commit()

        repo.delete("2026_03_001")
        db_session.commit()

        assert repo.get_by_reference_id("2026_03_001") is None

    def test_bulk_update_status(self, db_session):
        repo = SqlAlchemyLoanRepository(db_session)
        repo.save(_make_loan("2026_03_001", status=LoanStatus.ACTIVE))
        repo.save(_make_loan("2026_03_002", status=LoanStatus.ACTIVE))
        db_session.commit()

        repo.bulk_update_status([
            ("2026_03_001", LoanStatus.OVERDUE),
            ("2026_03_002", LoanStatus.PENDING),
        ])
        db_session.commit()

        l1 = repo.get_by_reference_id("2026_03_001")
        l2 = repo.get_by_reference_id("2026_03_002")
        assert l1.status == LoanStatus.OVERDUE
        assert l2.status == LoanStatus.PENDING

    def test_get_unique_values(self, db_session):
        repo = SqlAlchemyLoanRepository(db_session)
        repo.save(_make_loan("2026_03_001", borrower_group="bg1"))
        repo.save(_make_loan("2026_03_002", borrower_group="bg2"))
        repo.save(_make_loan("2026_03_003", borrower_group="bg1"))
        db_session.commit()

        values = repo.get_unique_values("borrower_group")
        assert sorted(values) == ["bg1", "bg2"]

    def test_filter_by_borrower_group(self, db_session):
        repo = SqlAlchemyLoanRepository(db_session)
        repo.save(_make_loan("2026_03_001", borrower_group="bg1"))
        repo.save(_make_loan("2026_03_002", borrower_group="bg2"))
        repo.save(_make_loan("2026_03_003", borrower_group="bg1"))
        db_session.commit()

        results = repo.get_all_active({"borrower_group": "bg1"})
        assert len(results) == 2

    def test_no_due_date_included_in_name_filters(self, db_session):
        """Loans with no due_date are included when filtering by name/group (not by_months)."""
        repo = SqlAlchemyLoanRepository(db_session)
        repo.save(_make_loan("2026_03_001", borrower_group="bg1", due_date=None))
        repo.save(_make_loan("2026_03_002", borrower_group="bg1", due_date=date(2026, 5, 1)))
        db_session.commit()

        results = repo.get_all_active({"borrower_group": "bg1"})
        assert len(results) == 2

    def test_bulk_update_dates(self, db_session):
        repo = SqlAlchemyLoanRepository(db_session)
        repo.save(_make_loan("2026_03_001", giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1)))
        db_session.commit()

        repo.bulk_update_dates([{
            "reference_id": "2026_03_001",
            "giving_date": date(2026, 4, 1),
            "due_date": date(2026, 7, 1),
        }])
        db_session.commit()

        loan = repo.get_by_reference_id("2026_03_001")
        assert loan.giving_date == date(2026, 4, 1)
        assert loan.due_date == date(2026, 7, 1)

    def test_set_inactive(self, db_session):
        repo = SqlAlchemyLoanRepository(db_session)
        repo.save(_make_loan("2026_03_001"))
        db_session.commit()

        repo.set_inactive("2026_03_001")
        db_session.commit()

        loan = repo.get_by_reference_id("2026_03_001")
        assert loan.is_active is False
        assert loan.status == LoanStatus.PAIDOFF

    def test_get_by_reference_id_not_found(self, db_session):
        repo = SqlAlchemyLoanRepository(db_session)
        assert repo.get_by_reference_id("nonexistent") is None
