from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from loan_manager.application.dtos.loan_dto import LoanCreateDTO, LoanDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.events.loan_events import LoanCreated
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId


class CreateLoan:
    def __init__(self, uow_factory: Callable, ref_id_service: ReferenceIdService, event_bus: EventBus) -> None:
        self._uow_factory = uow_factory
        self._ref_id_service = ref_id_service
        self._event_bus = event_bus

    def execute(self, dto: LoanCreateDTO) -> LoanDTO:
        today = date.today()
        year, month = today.year, today.month
        year_month_key = self._ref_id_service.year_month_key(year, month)

        with self._uow_factory() as uow:
            last_order = uow.loan_meta.get_last_order(year_month_key)
            ref_id_str = self._ref_id_service.next_id(year, month, last_order)
            new_order = 1 if last_order is None else last_order + 1

            status = StatusEngine.compute(dto.giving_date, dto.due_date, today)
            now = datetime.now()

            loan = Loan(
                id=None,
                reference_id=ReferenceId(ref_id_str),
                borrower_name=dto.borrower_name,
                borrower_group=dto.borrower_group,
                depositor_name=dto.depositor_name,
                depositor_group=dto.depositor_group,
                amount=Money(dto.amount),
                giving_date=dto.giving_date,
                due_period=dto.due_period,
                due_date=dto.due_date,
                status=status,
                is_active=True,
                created_at=now,
                updated_at=now,
            )

            saved = uow.loans.save(loan)
            uow.loan_meta.set_last_order(year_month_key, new_order)
            uow.commit()

        self._event_bus.publish(LoanCreated(reference_id=ref_id_str))

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
