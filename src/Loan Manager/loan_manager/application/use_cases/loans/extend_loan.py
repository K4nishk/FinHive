from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable

from dateutil.relativedelta import relativedelta

from loan_manager.application.dtos.loan_dto import ExtendLoanDTO, LoanDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.domain.events.loan_events import LoanExtended
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.status import ExtensionPeriodUnit


class ExtendLoan:
    def __init__(self, uow_factory: Callable, event_bus: EventBus) -> None:
        self._uow_factory = uow_factory
        self._event_bus = event_bus

    def execute(self, reference_id: str, dto: ExtendLoanDTO) -> LoanDTO:
        with self._uow_factory() as uow:
            loan = uow.loans.get_by_reference_id(reference_id)
            if loan is None:
                raise ValueError(f"Loan not found: {reference_id}")

            unit = ExtensionPeriodUnit(dto.extension_period_unit)

            if loan.due_date is not None:
                new_giving_date = loan.due_date
                if unit == ExtensionPeriodUnit.MONTHS:
                    new_due_date = loan.due_date + relativedelta(months=dto.extension_period)
                else:
                    new_due_date = loan.due_date + timedelta(days=dto.extension_period)
            else:
                # No-due-date case
                new_giving_date = date.today()
                if dto.new_due_date is None:
                    raise ValueError("new_due_date must be provided for loans with no due_date")
                new_due_date = dto.new_due_date

            loan.giving_date = new_giving_date
            loan.due_date = new_due_date
            loan.status = StatusEngine.compute(new_giving_date, new_due_date, date.today())
            loan.updated_at = datetime.now()

            saved = uow.loans.save(loan)
            uow.commit()

        self._event_bus.publish(
            LoanExtended(
                reference_id=reference_id,
                new_giving_date=new_giving_date,
                new_due_date=new_due_date,
            )
        )

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
