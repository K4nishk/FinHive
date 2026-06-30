from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.repositories.history_repository import ILoanHistoryRepository
from loan_manager.infrastructure.database.models import LoanHistoryModel


class SqlAlchemyLoanHistoryRepository(ILoanHistoryRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def archive(self, loan: Loan, paidoff_date: date) -> None:
        """Archive a loan to the history table."""
        history = LoanHistoryModel(
            reference_id=str(loan.reference_id),
            borrower_name=loan.borrower_name,
            borrower_group=loan.borrower_group,
            depositor_name=loan.depositor_name,
            depositor_group=loan.depositor_group,
            amount=int(loan.amount),
            giving_date=loan.giving_date,
            due_date=loan.due_date,
            paidoff_date=paidoff_date,
            archived_at=datetime.now(),
        )
        self._session.add(history)
        self._session.flush()
