from __future__ import annotations

from datetime import date
from typing import Callable, Optional

from loan_manager.application.dtos.loan_dto import LoanDTO, LoanFilterDTO


class GetAllLoans:
    def __init__(self, uow_factory: Callable) -> None:
        self._uow_factory = uow_factory

    def execute(self, filters: Optional[LoanFilterDTO] = None) -> list[LoanDTO]:
        db_filters = None
        by_month = None

        if filters:
            db_filters = {}
            if filters.borrower_group:
                db_filters["borrower_group"] = filters.borrower_group
            if filters.borrower_name:
                db_filters["borrower_name"] = filters.borrower_name
            if filters.depositor_name:
                db_filters["depositor_name"] = filters.depositor_name
            if filters.depositor_group:
                db_filters["depositor_group"] = filters.depositor_group
            by_month = filters.by_month
            if not db_filters:
                db_filters = None

        with self._uow_factory() as uow:
            loans = uow.loans.get_all_active(db_filters)

        # Apply by_month filter in Python
        # by_month filter: excludes loans with no due_date; shows loans where
        # due_date.month == selected_month AND due_date.year == current_year
        if by_month is not None:
            current_year = date.today().year
            loans = [
                loan for loan in loans
                if loan.due_date is not None
                and loan.due_date.month == by_month
                and loan.due_date.year == current_year
            ]

        return [
            LoanDTO(
                id=loan.id,
                reference_id=str(loan.reference_id),
                borrower_name=loan.borrower_name,
                borrower_group=loan.borrower_group,
                depositor_name=loan.depositor_name,
                depositor_group=loan.depositor_group,
                amount=int(loan.amount),
                giving_date=loan.giving_date,
                due_period=loan.due_period,
                due_date=loan.due_date,
                status=loan.status,
                is_active=loan.is_active,
                created_at=loan.created_at,
                updated_at=loan.updated_at,
            )
            for loan in loans
        ]
