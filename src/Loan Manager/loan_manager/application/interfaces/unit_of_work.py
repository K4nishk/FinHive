from abc import ABC, abstractmethod
from types import TracebackType
from typing import Optional, Type

from loan_manager.domain.repositories.loan_repository import ILoanRepository
from loan_manager.domain.repositories.report_repository import IReportRepository
from loan_manager.domain.repositories.loan_meta_repository import ILoanMetaRepository
from loan_manager.domain.repositories.history_repository import ILoanHistoryRepository


class IUnitOfWork(ABC):
    loans: ILoanRepository
    reports: IReportRepository
    loan_meta: ILoanMetaRepository
    history: ILoanHistoryRepository

    @abstractmethod
    def __enter__(self) -> "IUnitOfWork": ...

    @abstractmethod
    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None: ...

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...
