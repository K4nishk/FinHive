from __future__ import annotations

from datetime import datetime
from typing import Callable

from loan_manager.application.dtos.loan_dto import LoanCreateDTO, LoanDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import Clock, SystemClock
from loan_manager.application.interfaces.unit_of_work import IUnitOfWork
from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.events.loan_events import LoanCreated
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId


class CreateLoan:
    def __init__(
        self,
        uow_factory: Callable,
        ref_id_service: ReferenceIdService,
        event_bus: EventBus,
        clock: Clock | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._ref_id_service = ref_id_service
        self._event_bus = event_bus
        self._clock = clock or SystemClock()

    def stage(self, uow: IUnitOfWork, dto: LoanCreateDTO) -> Loan:
        """Build, mint a reference_id for, and save one loan within an
        ALREADY-OPEN unit of work. Does not commit and does not publish
        `LoanCreated` -- extracted (KCH-242) so `ApproveReport`'s CREATE
        branch can stage several new loans on its own single `uow` and
        commit them all atomically in one transaction, publishing per loan
        only after that commit succeeds. `execute()` below is the original,
        unchanged single-loan behaviour built on top of this.
        """
        today = self._clock.today()
        year, month = today.year, today.month
        year_month_key = self._ref_id_service.year_month_key(year, month)

        last_order = uow.loan_meta.get_last_order(year_month_key)
        order = 1 if last_order is None else last_order + 1
        # Insert-only skip-ahead (KCH-242 review, blocker): `uow.loans.save`
        # is an upsert by reference_id, so a `loan_meta` counter that lagged
        # behind an import carrying its own explicit reference_ids
        # (ImportLoans never bumps the counter for those rows -- DEBT) would
        # otherwise mint a ref that already names a real loan and silently
        # OVERWRITE it. Walk forward past every ref that already exists --
        # active OR inactive/paid-off, since a paid-off loan stays in
        # `loans` with is_active=False until archival and its ref must never
        # be reused either -- so this always lands on the first genuinely
        # free reference_id, and the counter persisted below never regresses.
        reference_id = ReferenceId.build(year, month, order)
        while uow.loans.get_by_reference_id(str(reference_id)) is not None:
            order += 1
            reference_id = ReferenceId.build(year, month, order)

        status = StatusEngine.compute(dto.giving_date, dto.due_date, today)
        now = datetime.now()

        loan = Loan(
            id=None,
            reference_id=reference_id,
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
        uow.loan_meta.set_last_order(year_month_key, order)
        return saved

    def execute(self, dto: LoanCreateDTO) -> LoanDTO:
        with self._uow_factory() as uow:
            saved = self.stage(uow, dto)
            uow.commit()

        self._event_bus.publish(LoanCreated(reference_id=str(saved.reference_id)))

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
