from abc import ABC, abstractmethod
from datetime import date

from loan_manager.domain.entities.loan import Loan


class ILoanHistoryRepository(ABC):
    @abstractmethod
    def archive(self, loan: Loan, paidoff_date: date) -> None: ...
