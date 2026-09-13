from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from loan_manager.domain.repositories.loan_meta_repository import ILoanMetaRepository
from loan_manager.infrastructure.database.models import LoanMetaModel, ReportMetaModel


class SqlAlchemyLoanMetaRepository(ILoanMetaRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_last_order(self, year_month: str) -> Optional[int]:
        model = (
            self._session.query(LoanMetaModel)
            .filter(LoanMetaModel.year_month == year_month)
            .first()
        )
        if model is None:
            return None
        return model.last_order

    def set_last_order(self, year_month: str, order: int) -> None:
        model = (
            self._session.query(LoanMetaModel)
            .filter(LoanMetaModel.year_month == year_month)
            .first()
        )
        if model:
            model.last_order = order
        else:
            model = LoanMetaModel(year_month=year_month, last_order=order)
            self._session.add(model)
        self._session.flush()


class SqlAlchemyReportMetaRepository:
    """Report meta repository for tracking report order counters."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_last_order(self, report_date: str) -> Optional[int]:
        model = (
            self._session.query(ReportMetaModel)
            .filter(ReportMetaModel.report_date == report_date)
            .first()
        )
        if model is None:
            return None
        return model.last_order

    def set_last_order(self, report_date: str, order: int) -> None:
        model = (
            self._session.query(ReportMetaModel)
            .filter(ReportMetaModel.report_date == report_date)
            .first()
        )
        if model:
            model.last_order = order
        else:
            model = ReportMetaModel(report_date=report_date, last_order=order)
            self._session.add(model)
        self._session.flush()
