from __future__ import annotations
from types import TracebackType
from typing import Optional, Type

from sqlalchemy.orm import Session

from loan_manager.application.interfaces.unit_of_work import IUnitOfWork
from loan_manager.infrastructure.repositories.sqlalchemy_loan_repo import SqlAlchemyLoanRepository
from loan_manager.infrastructure.repositories.sqlalchemy_report_repo import SqlAlchemyReportRepository
from loan_manager.infrastructure.repositories.sqlalchemy_meta_repo import SqlAlchemyLoanMetaRepository, SqlAlchemyReportMetaRepository
from loan_manager.infrastructure.repositories.sqlalchemy_history_repo import SqlAlchemyLoanHistoryRepository


class SqlAlchemyUnitOfWork(IUnitOfWork):
    def __init__(self, session: Session) -> None:
        self._session = session
        self.loans = SqlAlchemyLoanRepository(session)
        self.reports = SqlAlchemyReportRepository(session)
        self.loan_meta = SqlAlchemyLoanMetaRepository(session)
        self.history = SqlAlchemyLoanHistoryRepository(session)
        self.report_meta = SqlAlchemyReportMetaRepository(session)

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if exc_type:
            self.rollback()
        self._session.close()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    @property
    def session(self) -> Session:
        return self._session
