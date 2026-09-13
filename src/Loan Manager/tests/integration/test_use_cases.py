"""Integration tests for use cases using in-memory DB."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from loan_manager.application.dtos.loan_dto import (
    ExtendLoanDTO,
    LoanCreateDTO,
    LoanFilterDTO,
    LoanUpdateDTO,
    PaidOffRequestDTO,
)
from loan_manager.application.dtos.calculation_dto import CalculationRequestDTO
from loan_manager.application.dtos.report_dto import (
    GenerateReportDTO,
    ReportRecordDTO,
    ReportRecordUpdateDTO,
)
from loan_manager.application.event_bus import EventBus
from loan_manager.application.use_cases.loans.create_loan import CreateLoan
from loan_manager.application.use_cases.loans.delete_loan import DeleteLoan
from loan_manager.application.use_cases.loans.extend_loan import ExtendLoan
from loan_manager.application.use_cases.loans.get_autocomplete import GetAutocompleteValues
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.application.use_cases.loans.mark_paidoff import MarkPaidOff
from loan_manager.application.use_cases.loans.recompute_statuses import RecomputeAllStatuses
from loan_manager.application.use_cases.loans.update_loan import UpdateLoan
from loan_manager.application.use_cases.reports.calculate_interest import CalculateInterest
from loan_manager.application.use_cases.reports.generate_report import GenerateReport
from loan_manager.application.use_cases.reports.get_reports import GetPendingReports, UpdateReportRecord
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    LoanStatus,
)
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture
def uow_factory(db_session):
    """Return a factory that creates UoW instances sharing the same session."""
    def factory():
        return SqlAlchemyUnitOfWork(db_session)
    return factory


@pytest.fixture
def event_bus():
    return EventBus()


class TestCreateLoan:
    def test_create_loan_returns_dto(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        uc = CreateLoan(uow_factory, ref_service, event_bus)

        dto = LoanCreateDTO(
            borrower_name="Test Borrower",
            borrower_group="Group A",
            depositor_name="Test Depositor",
            depositor_group="DG1",
            amount=50000,
            giving_date=date(2026, 1, 15),
            due_period=3,
        )

        result = uc.execute(dto)
        assert result.borrower_name == "test borrower"
        assert result.amount == 50000
        assert result.reference_id is not None
        assert result.is_active is True

    def test_create_loan_with_future_giving_date_is_pending(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        uc = CreateLoan(uow_factory, ref_service, event_bus)

        dto = LoanCreateDTO(
            borrower_name="Future",
            borrower_group="FG",
            depositor_name="Dep",
            amount=10000,
            giving_date=date(2027, 1, 1),
            due_date=date(2027, 4, 1),
        )

        result = uc.execute(dto)
        assert result.status == LoanStatus.PENDING


class TestUpdateLoan:
    def test_update_borrower_name(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        update_uc = UpdateLoan(uow_factory)

        create_dto = LoanCreateDTO(
            borrower_name="Original",
            borrower_group="G1",
            depositor_name="D1",
            amount=10000,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
        )
        created = create_uc.execute(create_dto)

        update_dto = LoanUpdateDTO(borrower_name="Updated")
        updated = update_uc.execute(created.reference_id, update_dto)
        assert updated.borrower_name == "updated"

    def test_update_nonexistent_raises(self, uow_factory):
        uc = UpdateLoan(uow_factory)
        with pytest.raises(ValueError, match="not found"):
            uc.execute("9999_99_999", LoanUpdateDTO(borrower_name="x"))


class TestDeleteLoan:
    def test_delete_existing_loan(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        delete_uc = DeleteLoan(uow_factory)

        dto = LoanCreateDTO(
            borrower_name="Delete Me",
            borrower_group="G1",
            depositor_name="D1",
            amount=10000,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
        )
        created = create_uc.execute(dto)
        delete_uc.execute(created.reference_id)

        get_uc = GetAllLoans(uow_factory)
        loans = get_uc.execute()
        assert len(loans) == 0

    def test_delete_nonexistent_raises(self, uow_factory):
        uc = DeleteLoan(uow_factory)
        with pytest.raises(ValueError, match="not found"):
            uc.execute("9999_99_999")


class TestExtendLoan:
    def test_extend_with_due_date_monthly(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        extend_uc = ExtendLoan(uow_factory, event_bus)

        created = create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
        ))

        extended = extend_uc.execute(created.reference_id, ExtendLoanDTO(
            extension_period=3, extension_period_unit="months"
        ))
        assert extended.giving_date == date(2026, 4, 1)
        assert extended.due_date == date(2026, 7, 1)

    def test_extend_with_due_date_daily(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        extend_uc = ExtendLoan(uow_factory, event_bus)

        created = create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
        ))

        extended = extend_uc.execute(created.reference_id, ExtendLoanDTO(
            extension_period=30, extension_period_unit="days"
        ))
        assert extended.giving_date == date(2026, 4, 1)
        assert extended.due_date == date(2026, 5, 1)

    def test_extend_no_due_date_requires_new_due_date(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        extend_uc = ExtendLoan(uow_factory, event_bus)

        created = create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1),
        ))

        with pytest.raises(ValueError, match="new_due_date must be provided"):
            extend_uc.execute(created.reference_id, ExtendLoanDTO(
                extension_period=3, extension_period_unit="months"
            ))

    def test_extend_no_due_date_with_new_due_date(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        extend_uc = ExtendLoan(uow_factory, event_bus)

        created = create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1),
        ))

        extended = extend_uc.execute(created.reference_id, ExtendLoanDTO(
            extension_period=3, extension_period_unit="months",
            new_due_date=date(2026, 9, 1),
        ))
        assert extended.due_date == date(2026, 9, 1)

    def test_extend_nonexistent_raises(self, uow_factory, event_bus):
        uc = ExtendLoan(uow_factory, event_bus)
        with pytest.raises(ValueError, match="not found"):
            uc.execute("9999_99_999", ExtendLoanDTO(extension_period=3))


class TestGetAllLoans:
    def test_get_all_returns_active(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        get_uc = GetAllLoans(uow_factory)

        create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
        ))

        loans = get_uc.execute()
        assert len(loans) == 1

    def test_get_with_filter(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        get_uc = GetAllLoans(uow_factory)

        create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="Alpha", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
        ))
        create_uc.execute(LoanCreateDTO(
            borrower_name="B2", borrower_group="Beta", depositor_name="D2",
            amount=20000, giving_date=date(2026, 2, 1), due_date=date(2026, 5, 1),
        ))

        loans = get_uc.execute(LoanFilterDTO(borrower_group="alpha"))
        assert len(loans) == 1
        assert loans[0].borrower_name == "b1"


class TestGetAutocomplete:
    def test_unique_values(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        autocomplete_uc = GetAutocompleteValues(uow_factory)

        create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="Alpha", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
        ))
        create_uc.execute(LoanCreateDTO(
            borrower_name="B2", borrower_group="Beta", depositor_name="D2",
            amount=20000, giving_date=date(2026, 2, 1), due_date=date(2026, 5, 1),
        ))

        values = autocomplete_uc.execute("borrower_group")
        assert "alpha" in values
        assert "beta" in values


class TestRecomputeStatuses:
    def test_recompute_updates_changed_statuses(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        recompute_uc = RecomputeAllStatuses(uow_factory)

        # Create a loan that was Active but due_date is now in the past
        create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2025, 1, 1), due_date=date(2025, 6, 1),
        ))

        count = recompute_uc.execute()
        # Status should have been recomputed (it was set during creation based on current date)
        # Since due_date 2025-06-01 < today 2026-06-30, it should be Overdue
        get_uc = GetAllLoans(uow_factory)
        loans = get_uc.execute()
        assert loans[0].status == LoanStatus.OVERDUE


class TestMarkPaidOff:
    def test_mark_paidoff_creates_pending_report(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        paidoff_uc = MarkPaidOff(uow_factory, event_bus)

        created = create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
        ))

        report = paidoff_uc.execute(created.reference_id, PaidOffRequestDTO(
            paidoff_date=date(2026, 5, 1),
            interest_rate=Decimal("12"),
            commission_rate=Decimal("6"),
            tds_flag=True,
        ))

        assert report.report_mode == CalculationMode.PAIDOFF
        assert len(report.records) == 1
        assert report.records[0].paidoff_date == date(2026, 5, 1)
        assert report.records[0].tds_amount > Decimal("0")

    def test_mark_paidoff_no_due_date_raises(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        paidoff_uc = MarkPaidOff(uow_factory, event_bus)

        created = create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1),
        ))

        with pytest.raises(ValueError, match="no due_date"):
            paidoff_uc.execute(created.reference_id, PaidOffRequestDTO(
                paidoff_date=date(2026, 5, 1),
                interest_rate=Decimal("12"),
                commission_rate=Decimal("6"),
            ))


class TestCalculateInterest:
    def test_calculate_monthly(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        calc_uc = CalculateInterest(uow_factory)

        create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
        ))

        result = calc_uc.execute(CalculationRequestDTO(
            mode=CalculationMode.MONTHLY,
            filters=LoanFilterDTO(),
            interest_rate=Decimal("12"),
            commission_rate=Decimal("6"),
            extension_period=3,
            extension_period_unit=ExtensionPeriodUnit.MONTHS,
            tds_flag=False,
        ))

        assert len(result.lines) == 1
        assert result.lines[0].interest_amount == Decimal("300.00")
        assert result.total_interest == Decimal("300.00")

    def test_calculate_daily(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        calc_uc = CalculateInterest(uow_factory)

        create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
        ))

        result = calc_uc.execute(CalculationRequestDTO(
            mode=CalculationMode.DAILY,
            filters=LoanFilterDTO(),
            interest_rate=Decimal("12"),
            commission_rate=Decimal("6"),
            extension_period=90,
            extension_period_unit=ExtensionPeriodUnit.DAYS,
            tds_flag=True,
        ))

        assert len(result.lines) == 1
        assert result.lines[0].interest_amount == Decimal("295.89")
        assert result.lines[0].tds_amount > Decimal("0")


class TestGenerateReport:
    def test_generate_report(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        calc_uc = CalculateInterest(uow_factory)
        gen_uc = GenerateReport(uow_factory, event_bus)

        created = create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
        ))

        calc_result = calc_uc.execute(CalculationRequestDTO(
            mode=CalculationMode.MONTHLY,
            filters=LoanFilterDTO(),
            interest_rate=Decimal("12"),
            commission_rate=Decimal("6"),
            extension_period=3,
            extension_period_unit=ExtensionPeriodUnit.MONTHS,
            tds_flag=False,
        ))

        line = calc_result.lines[0]
        record_dto = ReportRecordDTO(
            id=None,
            report_id="placeholder",
            reference_id=line.reference_id,
            borrower_name=line.borrower_name,
            depositor_name=line.depositor_name,
            depositor_group=None,
            amount=line.amount,
            giving_date=line.giving_date,
            due_date=line.due_date,
            extension_period=line.extension_period,
            extension_period_unit=line.extension_period_unit,
            interest_rate=line.interest_rate,
            commission_rate=line.commission_rate,
            tds_flag=line.tds_flag,
            interest_amount=line.interest_amount,
            commission_amount=line.commission_amount,
            tds_amount=line.tds_amount,
            chq_amount=line.chq_amount,
            post_extension_giving_date=line.post_extension_giving_date,
            post_extension_due_date=line.post_extension_due_date,
            paidoff_date=None,
        )

        report = gen_uc.execute(GenerateReportDTO(
            mode=CalculationMode.MONTHLY,
            records=[record_dto],
        ))

        assert report.report_id.startswith("RPT_")
        assert len(report.records) == 1


class TestGetPendingReports:
    def test_get_pending(self, uow_factory, event_bus):
        ref_service = ReferenceIdService()
        create_uc = CreateLoan(uow_factory, ref_service, event_bus)
        paidoff_uc = MarkPaidOff(uow_factory, event_bus)
        get_reports_uc = GetPendingReports(uow_factory)

        created = create_uc.execute(LoanCreateDTO(
            borrower_name="B1", borrower_group="G1", depositor_name="D1",
            amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
        ))

        paidoff_uc.execute(created.reference_id, PaidOffRequestDTO(
            paidoff_date=date(2026, 5, 1),
            interest_rate=Decimal("12"),
            commission_rate=Decimal("6"),
        ))

        pending = get_reports_uc.execute()
        assert len(pending) == 1
        assert pending[0].report_mode == CalculationMode.PAIDOFF
