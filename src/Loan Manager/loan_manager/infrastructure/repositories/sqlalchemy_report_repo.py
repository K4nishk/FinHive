from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from loan_manager.domain.entities.report import Report, ReportRecord
from loan_manager.domain.repositories.report_repository import IReportRepository
from loan_manager.domain.value_objects.report_id import ReportId
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    ReportStatus,
)
from loan_manager.infrastructure.database.models import ReportModel, ReportRecordModel


def report_model_to_entity(model: ReportModel) -> Report:
    """Map ORM model to domain entity."""
    records = [
        ReportRecord(
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
            extension_period_unit=ExtensionPeriodUnit(r.extension_period_unit),
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
        for r in model.records
    ]

    return Report(
        id=model.id,
        report_id=ReportId(model.report_id),
        report_mode=CalculationMode(model.report_mode),
        status=ReportStatus(model.status),
        records=records,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def report_record_to_model(record: ReportRecord) -> ReportRecordModel:
    """Map domain ReportRecord to ORM model."""
    return ReportRecordModel(
        report_id=record.report_id,
        reference_id=record.reference_id,
        borrower_name=record.borrower_name,
        depositor_name=record.depositor_name,
        depositor_group=record.depositor_group,
        amount=record.amount,
        giving_date=record.giving_date,
        due_date=record.due_date,
        extension_period=record.extension_period,
        extension_period_unit=record.extension_period_unit.value,
        interest_rate=record.interest_rate,
        commission_rate=record.commission_rate,
        tds_flag=record.tds_flag,
        interest_amount=record.interest_amount,
        commission_amount=record.commission_amount,
        tds_amount=record.tds_amount,
        chq_amount=record.chq_amount,
        post_extension_giving_date=record.post_extension_giving_date,
        post_extension_due_date=record.post_extension_due_date,
        paidoff_date=record.paidoff_date,
    )


class SqlAlchemyReportRepository(IReportRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_report_id(self, report_id: str) -> Optional[Report]:
        model = (
            self._session.query(ReportModel)
            .options(joinedload(ReportModel.records))
            .filter(ReportModel.report_id == report_id)
            .first()
        )
        if model is None:
            return None
        return report_model_to_entity(model)

    def get_all_pending(self) -> list[Report]:
        models = (
            self._session.query(ReportModel)
            .options(joinedload(ReportModel.records))
            .filter(ReportModel.status == ReportStatus.PENDING.value)
            .all()
        )
        # Deduplicate due to joinedload producing duplicates
        seen = set()
        unique = []
        for m in models:
            if m.id not in seen:
                seen.add(m.id)
                unique.append(m)
        return [report_model_to_entity(m) for m in unique]

    def save(self, report: Report) -> Report:
        """Insert new report with its records."""
        model = ReportModel(
            report_id=str(report.report_id),
            report_mode=report.report_mode.value,
            status=report.status.value,
            created_at=report.created_at,
            updated_at=report.updated_at,
        )
        for record in report.records:
            model.records.append(report_record_to_model(record))

        self._session.add(model)
        self._session.flush()
        return report_model_to_entity(model)

    def mark_approved(self, report_id: str) -> None:
        self._session.query(ReportModel).filter(
            ReportModel.report_id == report_id
        ).update(
            {"status": ReportStatus.APPROVED.value, "updated_at": datetime.now()},
            synchronize_session="fetch",
        )
        self._session.flush()

    def mark_declined(self, report_id: str) -> None:
        model = (
            self._session.query(ReportModel)
            .options(joinedload(ReportModel.records))
            .filter(ReportModel.report_id == report_id)
            .first()
        )
        if model:
            model.status = ReportStatus.DECLINED.value
            model.updated_at = datetime.now()
            # Records cascade deleted via relationship config
            model.records.clear()
            self._session.flush()

    def get_pending_reference_ids(self) -> set[str]:
        """Get all reference_ids from pending report records."""
        models = (
            self._session.query(ReportRecordModel.reference_id)
            .join(ReportModel, ReportRecordModel.report_id == ReportModel.report_id)
            .filter(ReportModel.status == ReportStatus.PENDING.value)
            .all()
        )
        return {m[0] for m in models}

    def update_record(self, record_id: int, updates: dict) -> Optional[ReportRecordModel]:
        """Update a specific report record by its primary key."""
        record = self._session.query(ReportRecordModel).get(record_id)
        if record is None:
            return None
        for key, value in updates.items():
            setattr(record, key, value)
        self._session.flush()
        return record

    def get_record_by_id(self, record_id: int) -> Optional[ReportRecordModel]:
        return self._session.query(ReportRecordModel).get(record_id)
