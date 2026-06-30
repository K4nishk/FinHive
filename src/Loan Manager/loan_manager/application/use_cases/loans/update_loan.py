from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from loan_manager.application.dtos.loan_dto import LoanUpdateDTO, LoanDTO
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.money import Money


class UpdateLoan:
    def __init__(self, uow_factory: Callable) -> None:
        self._uow_factory = uow_factory

    def execute(self, reference_id: str, dto: LoanUpdateDTO) -> LoanDTO:
        with self._uow_factory() as uow:
            loan = uow.loans.get_by_reference_id(reference_id)
            if loan is None:
                raise ValueError(f"Loan not found: {reference_id}")

            recompute_status = False

            if dto.borrower_name is not None:
                loan.borrower_name = dto.borrower_name
            if dto.borrower_group is not None:
                loan.borrower_group = dto.borrower_group
            if dto.depositor_name is not None:
                loan.depositor_name = dto.depositor_name
            if dto.depositor_group is not None:
                loan.depositor_group = dto.depositor_group
            if dto.amount is not None:
                loan.amount = Money(dto.amount)
            if dto.giving_date is not None:
                loan.giving_date = dto.giving_date
                recompute_status = True
            if dto.due_period is not None:
                loan.due_period = dto.due_period
            if dto.due_date is not None:
                loan.due_date = dto.due_date
                recompute_status = True
            if dto.status is not None:
                loan.status = dto.status

            if recompute_status and dto.status is None:
                loan.status = StatusEngine.compute(loan.giving_date, loan.due_date, date.today())

            loan.updated_at = datetime.now()
            saved = uow.loans.save(loan)
            uow.commit()

        return LoanDTO(
            id=saved.id,
            reference_id=str(saved.reference_id),
            borrower_name=saved.borrower_name,
            borrower_group=saved.borrower_group,
            depositor_name=saved.depositor_name,
            depositor_group=saved.depositor_group,
            amount=int(saved.amount),
            giving_date=saved.giving_date,
            due_period=saved.due_period,
            due_date=saved.due_date,
            status=saved.status,
            is_active=saved.is_active,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )
