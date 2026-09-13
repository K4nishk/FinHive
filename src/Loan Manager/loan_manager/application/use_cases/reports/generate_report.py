from __future__ import annotations

from datetime import datetime
from typing import Callable

from loan_manager.application.dtos.report_dto import GenerateReportDTO, ReportDTO, ReportRecordDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.domain.entities.report import Report, ReportRecord
from loan_manager.domain.events.report_events import ReportGenerated
from loan_manager.domain.value_objects.report_id import ReportId
from loan_manager.domain.value_objects.status import ReportStatus


class GenerateReport:
    def __init__(self, uow_factory: Callable, event_bus: EventBus) -> None:
        self._uow_factory = uow_factory
        self._event_bus = event_bus

    def execute(self, dto: GenerateReportDTO) -> ReportDTO:
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")

        with self._uow_factory() as uow:
            last_order = uow.report_meta.get_last_order(date_str)
            new_order = 1 if last_order is None else last_order + 1
            report_id = ReportId.build(date_str, new_order)

            records = [
                ReportRecord(
                    id=None,
                    report_id=str(report_id),
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
                for rec in dto.records
            ]

            report = Report(
                id=None,
                report_id=report_id,
                report_mode=dto.mode,
                status=ReportStatus.PENDING,
                records=records,
                created_at=now,
                updated_at=now,
            )

            saved = uow.reports.save(report)
            uow.report_meta.set_last_order(date_str, new_order)
            uow.commit()

        self._event_bus.publish(ReportGenerated(report_id=str(report_id)))

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
