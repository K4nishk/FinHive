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
from loan_manager.application.use_cases.reports.get_reports import GetPendingReports, UpdateReportRecord
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.domain.value_objects.status import ExtensionPeriodUnit
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
