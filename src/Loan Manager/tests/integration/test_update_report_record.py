"""UpdateReportRecord use case tests."""
from datetime import date, datetime
from decimal import Decimal

import pytest
from loan_manager.application.dtos.loan_dto import LoanCreateDTO, PaidOffRequestDTO
from loan_manager.application.dtos.report_dto import ReportRecordUpdateDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.application.use_cases.loans.create_loan import CreateLoan
from loan_manager.application.use_cases.loans.delete_loan import DeleteLoan
from loan_manager.application.use_cases.loans.mark_paidoff import MarkPaidOff
from loan_manager.application.use_cases.reports.get_reports import (
    GetPendingReports,
    UpdateReportRecord,
)
from loan_manager.domain.entities.report import Report, ReportRecord
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.domain.value_objects.report_id import ReportId
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    ReportStatus,
)
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture
def uow_factory(db_session):
    def factory():
        return SqlAlchemyUnitOfWork(db_session)
    return factory


@pytest.fixture
def event_bus():
    return EventBus()


class TestUpdateReportRecord:
    def test_update_interest_rate_recalculates(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        paidoff_uc = MarkPaidOff(uow_factory, event_bus)
        update_uc = UpdateReportRecord(uow_factory)

        created = create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
        ))

        report = paidoff_uc.execute(created.reference_id, PaidOffRequestDTO(
            paidoff_date=date(2026, 5, 1),
            interest_rate=Decimal("12"),
            commission_rate=Decimal("6"),
        ))

        record = report.records[0]
        original_interest = record.interest_amount

        # Update with a higher interest rate
        updated = update_uc.execute(
            report.report_id,
            record.id,
            ReportRecordUpdateDTO(interest_rate=Decimal("24")),
        )

        assert updated.interest_rate == Decimal("24")
        # Interest should be recalculated and be higher
        assert updated.interest_amount > original_interest

    def test_update_nonexistent_record_raises(self, uow_factory):
        uc = UpdateReportRecord(uow_factory)
        with pytest.raises(ValueError, match="not found"):
            uc.execute("RPT_20260101_001", 9999, ReportRecordUpdateDTO(interest_rate=Decimal("12")))

    def test_update_preserves_borrower_group_and_due_period(self, uow_factory):
        """KCH-242 review cycle 2, MINOR-3: cycle-1 only proved
        GetPendingReports maps borrower_group/due_period. UpdateReportRecord
        builds its OWN `ReportRecordDTO` at the end of `execute()`
        (get_reports.py) -- dropping either kwarg there is the identical
        silent-default-to-None class of bug the cycle-1 `ReportDTO.actor`
        fix was about, and both fields default to None on
        `ReportRecordDTO` so a dropped kwarg fails silently, not loudly."""
        record = ReportRecord(
            id=None,
            report_id="RPT_20260601_001",
            reference_id="2026_06_001",
            borrower_name="agent borrower",
            depositor_name="depositor",
            depositor_group=None,
            amount=15000,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
            extension_period=3,
            extension_period_unit=ExtensionPeriodUnit.MONTHS,
            interest_rate=Decimal("12"),
            commission_rate=Decimal("6"),
            tds_flag=False,
            interest_amount=Decimal("450.00"),
            commission_amount=Decimal("225.00"),
            tds_amount=Decimal("0.00"),
            chq_amount=Decimal("450.00"),
            post_extension_giving_date=date(2026, 4, 1),
            post_extension_due_date=date(2026, 7, 1),
            paidoff_date=None,
            borrower_group="agent-group",
            due_period=6,
        )
        report = Report(
            id=None,
            report_id=ReportId("RPT_20260601_001"),
            report_mode=CalculationMode.MONTHLY,
            status=ReportStatus.PENDING,
            records=[record],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        with uow_factory() as uow:
            saved = uow.reports.save(report)
            uow.commit()
            record_id = saved.records[0].id

        updated = UpdateReportRecord(uow_factory).execute(
            "RPT_20260601_001",
            record_id,
            ReportRecordUpdateDTO(interest_rate=Decimal("24")),
        )

        assert updated.borrower_group == "agent-group", (
            "UpdateReportRecord must not silently drop borrower_group"
        )
        assert updated.due_period == 6, (
            "UpdateReportRecord must not silently drop due_period"
        )


class TestDeleteLoanInPendingReport:
    def test_delete_blocked_by_pending_report(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        paidoff_uc = MarkPaidOff(uow_factory, event_bus)
        delete_uc = DeleteLoan(uow_factory)

        created = create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
        ))

        paidoff_uc.execute(created.reference_id, PaidOffRequestDTO(
            paidoff_date=date(2026, 5, 1),
            interest_rate=Decimal("12"),
            commission_rate=Decimal("6"),
        ))

        with pytest.raises(ValueError, match="pending report"):
            delete_uc.execute(created.reference_id)
