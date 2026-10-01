from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session, joinedload, selectinload

from loan_manager.domain.entities.report import Report, ReportRecord
from loan_manager.domain.repositories.report_repository import IReportRepository
from loan_manager.domain.value_objects.report_id import ReportId
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    ReportActor,
    ReportStatus,
)
from loan_manager.infrastructure.database.blind_index_sync import checked_update
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
            borrower_group=r.borrower_group,
            due_period=r.due_period,
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
        actor=ReportActor(model.actor),
        user_request=model.user_request,
        turn_id=model.turn_id,
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
        borrower_group=record.borrower_group,
        due_period=record.due_period,
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

    def get_recent_approved(self, limit: int) -> list[Report]:
        """KCH-245: the Recently Approved list for the approvals tab's undo
        panel. `selectinload`, not `joinedload` -- `joinedload` on a
        one-to-many alongside `LIMIT` multiplies/truncates rows at the SQL
        level (the classic collection+limit trap); `selectinload` issues a
        second, separate `WHERE report_id IN (...)` query for `records`
        after the limited `reports` query has already run, so `limit`
        applies to REPORTS, not to the join's row count."""
        models = (
            self._session.query(ReportModel)
            .options(selectinload(ReportModel.records))
            .filter(ReportModel.status == ReportStatus.APPROVED.value)
            .order_by(ReportModel.updated_at.desc(), ReportModel.id.desc())
            .limit(limit)
            .all()
        )
        return [report_model_to_entity(m) for m in models]

    def save(self, report: Report) -> Report:
        """Insert new report with its records."""
        model = ReportModel(
            report_id=str(report.report_id),
            report_mode=report.report_mode.value,
            status=report.status.value,
            created_at=report.created_at,
            updated_at=report.updated_at,
            actor=report.actor.value,
            user_request=report.user_request,
            turn_id=report.turn_id,
        )
        for record in report.records:
            model.records.append(report_record_to_model(record))

        self._session.add(model)
        self._session.flush()
        return report_model_to_entity(model)

    def mark_approved(self, report_id: str) -> None:
        # Through the guard like every other bulk update, though ReportModel
        # itself carries no encrypted column: the rule is "all Query.update()
        # passes the identity check", with no per-model exceptions to
        # remember. It is a set intersection, and it already covers this
        # table if it ever gains an identity column.
        checked_update(
            self._session.query(ReportModel).filter(
                ReportModel.report_id == report_id
            ),
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

    def mark_reverted(self, report_id: str) -> None:
        """KCH-244: undo an APPROVED report. Copy of mark_approved -- a
        `checked_update` set-intersection identity check, records left
        untouched (unlike mark_declined, which clears them: a reverted
        report keeps its records, since UndoApprovedReport reads them
        again from `report.records` on the way in and a re-approve is
        never offered after a revert)."""
        checked_update(
            self._session.query(ReportModel).filter(
                ReportModel.report_id == report_id
            ),
            {"status": ReportStatus.REVERTED.value, "updated_at": datetime.now()},
            synchronize_session="fetch",
        )
        self._session.flush()

    def get_pending_reference_ids(self) -> set[str]:
        """Get all reference_ids from pending report records.

        Filters out NULL: a CREATE-mode record (KCH-242) has no reference_id
        until its proposal is approved, and a `None` in this set would make
        DeleteLoan's `reference_id in pending_refs` membership check
        meaningless noise rather than a real "loan is in a pending report"
        signal.
        """
        models = (
            self._session.query(ReportRecordModel.reference_id)
            .join(ReportModel, ReportRecordModel.report_id == ReportModel.report_id)
            .filter(ReportModel.status == ReportStatus.PENDING.value)
            .filter(ReportRecordModel.reference_id.isnot(None))
            .all()
        )
        return {m[0] for m in models}

    def assign_reference_id(self, record_id: int, ref_id: str) -> None:
        """Attach a freshly minted reference_id to a CREATE-mode record
        (KCH-242), once ApproveReport has staged the loan it names.

        Goes through the ORM attribute, not a bulk `Query.update()`:
        `reference_id` is not an identity column (no `_bidx` companion), so
        there is no blind-index sync to worry about, but assigning the
        attribute is still the natural, auditable way to touch a single
        already-loaded row.
        """
        record = self._session.query(ReportRecordModel).get(record_id)
        if record is None:
            raise ValueError(f"report record not found: {record_id}")
        record.reference_id = ref_id
        self._session.flush()

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
