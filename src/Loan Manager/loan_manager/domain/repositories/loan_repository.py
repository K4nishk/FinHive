from abc import ABC, abstractmethod
from typing import Optional

from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.value_objects.status import LoanStatus


class ILoanRepository(ABC):
    @abstractmethod
    def get_by_reference_id(self, ref_id: str) -> Optional[Loan]: ...

    @abstractmethod
    def get_all_active(self, filters: Optional[dict] = None) -> list[Loan]: ...

    @abstractmethod
    def save(self, loan: Loan) -> Loan: ...

    @abstractmethod
    def delete(self, reference_id: str) -> None: ...

    @abstractmethod
    def bulk_update_status(self, updates: list[tuple[str, LoanStatus]]) -> None: ...

    @abstractmethod
    def get_unique_values(self, field: str, active_only: bool = True) -> list[str]: ...

    @abstractmethod
    def bulk_update_dates(self, updates: list[dict]) -> None:
        """updates: list of {reference_id, giving_date, due_date}"""
        ...

    @abstractmethod
    def set_inactive(self, reference_id: str) -> None: ...
