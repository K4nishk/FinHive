from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable

from loan_manager.application.dtos.loan_dto import PaidOffRequestDTO
from loan_manager.application.dtos.report_dto import ReportDTO, ReportRecordDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.domain.entities.report import Report, ReportRecord
from loan_manager.domain.events.loan_events import LoanPaidOffRequested
from loan_manager.domain.services.interest_calculator import InterestCalculator
from loan_manager.domain.value_objects.report_id import ReportId
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    ReportStatus,
)


class MarkPaidOff:
    def __init__(self, uow_factory: Callable, event_bus: EventBus) -> None:
        self._uow_factory = uow_factory
        self._event_bus = event_bus

    def execute(self, reference_id: str, dto: PaidOffRequestDTO) -> ReportDTO:
        with self._uow_factory() as uow:
            loan = uow.loans.get_by_reference_id(reference_id)
            if loan is None:
                raise ValueError(f"Loan not found: {reference_id}")

            if loan.due_date is None:
                raise ValueError(f"Cannot mark paidoff: loan {reference_id} has no due_date")

            # Check no existing pending Paidoff report for this loan
            pending_reports = uow.reports.get_all_pending()
            for report in pending_reports:
                if report.report_mode == CalculationMode.PAIDOFF:
                    for rec in report.records:
                        if rec.reference_id == reference_id:
                            raise ValueError(
                                f"A pending Paidoff report already exists for loan {reference_id}"
                            )

            # Calculate extension_period as days between paidoff_date and due_date
            extension_period = (dto.paidoff_date - loan.due_date).days

            # Calculate amounts using Daily formula
            interest_amount = InterestCalculator.calculate_daily(
                int(loan.amount), dto.interest_rate, abs(extension_period)
            )
            commission_amount = InterestCalculator.calculate_daily(
                int(loan.amount), dto.commission_rate, abs(extension_period)
            )
            tds_amount = InterestCalculator.calculate_tds(interest_amount) if dto.tds_flag else Decimal("0.00")
            chq_amount = InterestCalculator.calculate_chq(interest_amount, tds_amount)

            # Generate report_id
            now = datetime.now()
            date_str = now.strftime("%Y%m%d")
            last_order = uow.report_meta.get_last_order(date_str)
            new_order = 1 if last_order is None else last_order + 1
            report_id = ReportId.build(date_str, new_order)

            record = ReportRecord(
                id=None,
                report_id=str(report_id),
                reference_id=reference_id,
                borrower_name=loan.borrower_name,
                depositor_name=loan.depositor_name,
                depositor_group=loan.depositor_group,
                amount=int(loan.amount),
                giving_date=loan.giving_date,
                due_date=loan.due_date,
                extension_period=extension_period,
                extension_period_unit=ExtensionPeriodUnit.DAYS,
                interest_rate=dto.interest_rate,
                commission_rate=dto.commission_rate,
                tds_flag=dto.tds_flag,
                interest_amount=interest_amount,
                commission_amount=commission_amount,
                tds_amount=tds_amount,
                chq_amount=chq_amount,
                post_extension_giving_date=None,
                post_extension_due_date=None,
                paidoff_date=dto.paidoff_date,
            )

            report = Report(
                id=None,
                report_id=report_id,
                report_mode=CalculationMode.PAIDOFF,
                status=ReportStatus.PENDING,
                records=[record],
                created_at=now,
                updated_at=now,
            )

            saved = uow.reports.save(report)
            uow.report_meta.set_last_order(date_str, new_order)
            uow.commit()

        self._event_bus.publish(
            LoanPaidOffRequested(reference_id=reference_id, report_id=str(report_id))
        )

        return ReportDTO(
            id=saved.id,
            report_id=str(saved.report_id),
            report_mode=saved.report_mode,
            status=saved.status,
            records=[
                ReportRecordDTO(
                    id=r.id,
                    report_id=r.report_id,
                    reference_id=r.reference_id,
                    borrower_name=r.borrower_name,
                    depositor_name=r.depositor_name,
                    depositor_group=r.depositor_group,
                    amount=r.amount,
                    giving_date=r.giving_date,
                    due_date=r.due_date,
                    extension_period=r.extension_period,
                    extension_period_unit=r.extension_period_unit,
                    interest_rate=r.interest_rate,
                    commission_rate=r.commission_rate,
                    tds_flag=r.tds_flag,
                    interest_amount=r.interest_amount,
                    commission_amount=r.commission_amount,
                    tds_amount=r.tds_amount,
                    chq_amount=r.chq_amount,
                    post_extension_giving_date=r.post_extension_giving_date,
                    post_extension_due_date=r.post_extension_due_date,
                    paidoff_date=r.paidoff_date,
                )
                for r in saved.records
            ],
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )
