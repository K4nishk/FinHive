from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Callable

from dateutil.relativedelta import relativedelta

from loan_manager.application.dtos.report_dto import (
    ReportDTO,
    ReportRecordDTO,
    ReportRecordUpdateDTO,
)
from loan_manager.domain.services.interest_calculator import InterestCalculator
from loan_manager.domain.value_objects.status import ExtensionPeriodUnit


class GetPendingReports:
    def __init__(self, uow_factory: Callable) -> None:
        self._uow_factory = uow_factory

    def execute(self) -> list[ReportDTO]:
        with self._uow_factory() as uow:
            reports = uow.reports.get_all_pending()

        return [
            ReportDTO(
                id=r.id,
                report_id=str(r.report_id),
                report_mode=r.report_mode,
                status=r.status,
                records=[
                    ReportRecordDTO(
                        id=rec.id,
                        report_id=rec.report_id,
                        reference_id=rec.reference_id,
                        borrower_name=rec.borrower_name,
                        depositor_name=rec.depositor_name,
                        depositor_group=rec.depositor_group,
                        amount=rec.amount,
                        giving_date=rec.giving_date,
                        due_date=rec.due_date,
                        extension_period=rec.extension_period,
                        extension_period_unit=rec.extension_period_unit,
                        interest_rate=rec.interest_rate,
                        commission_rate=rec.commission_rate,
                        tds_flag=rec.tds_flag,
                        interest_amount=rec.interest_amount,
                        commission_amount=rec.commission_amount,
                        tds_amount=rec.tds_amount,
                        chq_amount=rec.chq_amount,
                        post_extension_giving_date=rec.post_extension_giving_date,
                        post_extension_due_date=rec.post_extension_due_date,
                        paidoff_date=rec.paidoff_date,
                    )
                    for rec in r.records
                ],
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in reports
        ]


class UpdateReportRecord:
    def __init__(self, uow_factory: Callable) -> None:
        self._uow_factory = uow_factory

    def execute(self, report_id: str, record_id: int, dto: ReportRecordUpdateDTO) -> ReportRecordDTO:
        with self._uow_factory() as uow:
            record_model = uow.reports.get_record_by_id(record_id)
            if record_model is None:
                raise ValueError(f"Report record not found: {record_id}")

            if record_model.report_id != report_id:
                raise ValueError(f"Record {record_id} does not belong to report {report_id}")

            # Apply updates
            if dto.extension_period is not None:
                record_model.extension_period = dto.extension_period
            if dto.extension_period_unit is not None:
                record_model.extension_period_unit = dto.extension_period_unit.value
            if dto.interest_rate is not None:
                record_model.interest_rate = dto.interest_rate
            if dto.commission_rate is not None:
                record_model.commission_rate = dto.commission_rate
            if dto.tds_flag is not None:
                record_model.tds_flag = dto.tds_flag

            # Recalculate
            unit = ExtensionPeriodUnit(record_model.extension_period_unit)
            interest_amount = InterestCalculator.calculate(
                record_model.amount,
                record_model.interest_rate,
                record_model.extension_period,
                unit,
            )
            commission_amount = InterestCalculator.calculate(
                record_model.amount,
                record_model.commission_rate,
                record_model.extension_period,
                unit,
            )
            tds_amount = (
                InterestCalculator.calculate_tds(interest_amount) if record_model.tds_flag else Decimal("0.00")
            )
            chq_amount = InterestCalculator.calculate_chq(interest_amount, tds_amount)

            record_model.interest_amount = interest_amount
            record_model.commission_amount = commission_amount
            record_model.tds_amount = tds_amount
            record_model.chq_amount = chq_amount

            # Recalculate post-extension dates when period or unit changes
            if record_model.due_date is not None:
                record_model.post_extension_giving_date = record_model.due_date
                if unit == ExtensionPeriodUnit.MONTHS:
                    record_model.post_extension_due_date = (
                        record_model.due_date
                        + relativedelta(months=record_model.extension_period)
                    )
                else:
                    record_model.post_extension_due_date = (
                        record_model.due_date
                        + timedelta(days=record_model.extension_period)
                    )

            uow.session.flush()

            # Update report.updated_at
            from datetime import datetime
            from loan_manager.infrastructure.database.models import ReportModel
            uow.session.query(ReportModel).filter(
                ReportModel.report_id == report_id
            ).update({"updated_at": datetime.now()}, synchronize_session="fetch")

            uow.commit()

            return ReportRecordDTO(
                id=record_model.id,
                report_id=record_model.report_id,
                reference_id=record_model.reference_id,
                borrower_name=record_model.borrower_name,
                depositor_name=record_model.depositor_name,
                depositor_group=record_model.depositor_group,
                amount=record_model.amount,
                giving_date=record_model.giving_date,
                due_date=record_model.due_date,
                extension_period=record_model.extension_period,
                extension_period_unit=ExtensionPeriodUnit(record_model.extension_period_unit),
                interest_rate=record_model.interest_rate,
                commission_rate=record_model.commission_rate,
                tds_flag=record_model.tds_flag,
                interest_amount=record_model.interest_amount,
                commission_amount=record_model.commission_amount,
                tds_amount=record_model.tds_amount,
                chq_amount=record_model.chq_amount,
                post_extension_giving_date=record_model.post_extension_giving_date,
                post_extension_due_date=record_model.post_extension_due_date,
                paidoff_date=record_model.paidoff_date,
            )
