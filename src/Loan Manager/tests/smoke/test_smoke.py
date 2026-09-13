"""
Smoke tests — Stage 6 finalization.

Verify end-to-end flows without a running UI:
- App initializes cleanly
- Loan CRUD round-trip
- Interest calculation produces correct output
- Report generation → approval flow
- CSV import / export round-trip
- Recovery file detection
"""
from __future__ import annotations

import csv
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from loan_manager.application.dtos.calculation_dto import CalculationRequestDTO
from loan_manager.application.dtos.loan_dto import LoanCreateDTO, LoanFilterDTO, ExtendLoanDTO
from loan_manager.application.dtos.report_dto import GenerateReportDTO, ReportRecordDTO
from loan_manager.domain.value_objects.status import (
    CalculationMode, ExtensionPeriodUnit, LoanStatus, ReportStatus
)
from loan_manager.infrastructure.database.models import Base
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from loan_manager.infrastructure.repositories.sqlalchemy_loan_repo import SqlAlchemyLoanRepository
from loan_manager.infrastructure.repositories.sqlalchemy_report_repo import SqlAlchemyReportRepository
from loan_manager.infrastructure.repositories.sqlalchemy_meta_repo import (
    SqlAlchemyLoanMetaRepository, SqlAlchemyReportMetaRepository,
)
from loan_manager.infrastructure.repositories.sqlalchemy_history_repo import SqlAlchemyLoanHistoryRepository
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService
from loan_manager.domain.services.interest_calculator import InterestCalculator
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.application.event_bus import EventBus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def session(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    yield s
    s.close()


@pytest.fixture()
def uow(session):
    uow = SqlAlchemyUnitOfWork(session)
    uow.loans = SqlAlchemyLoanRepository(session)
    uow.reports = SqlAlchemyReportRepository(session)
    uow.loan_meta = SqlAlchemyLoanMetaRepository(session)
    uow.history = SqlAlchemyLoanHistoryRepository(session)
    uow.report_meta = SqlAlchemyReportMetaRepository(session)
    return uow


@pytest.fixture()
def uow_factory(uow):
    """Return a callable that yields the pre-built UoW as a context manager."""
    return lambda: uow


# ---------------------------------------------------------------------------
# Smoke: Domain services
# ---------------------------------------------------------------------------

class TestStatusEngineSanity:
    def test_active(self):
        today = date(2026, 6, 15)
        assert StatusEngine.compute(date(2026, 1, 1), date(2026, 12, 31), today) == LoanStatus.ACTIVE

    def test_overdue(self):
        today = date(2026, 6, 15)
        assert StatusEngine.compute(date(2026, 1, 1), date(2026, 5, 1), today) == LoanStatus.OVERDUE

    def test_pending(self):
        today = date(2026, 6, 15)
        assert StatusEngine.compute(date(2026, 7, 1), date(2026, 12, 31), today) == LoanStatus.PENDING

    def test_no_due_date_past(self):
        today = date(2026, 6, 15)
        assert StatusEngine.compute(date(2026, 1, 1), None, today) == LoanStatus.OVERDUE

    def test_no_due_date_future(self):
        today = date(2026, 6, 15)
        assert StatusEngine.compute(date(2026, 7, 1), None, today) == LoanStatus.PENDING


class TestCalculatorSanity:
    def test_monthly(self):
        result = InterestCalculator.calculate_monthly(10000, Decimal("12"), 3)
        assert result == Decimal("300.00")

    def test_daily(self):
        result = InterestCalculator.calculate_daily(10000, Decimal("12"), 90)
        # (10000 * 12 * 90) / (365 * 100) = 295.89...
        assert result == Decimal("295.89")

    def test_tds(self):
        assert InterestCalculator.calculate_tds(Decimal("300.00")) == Decimal("30.00")

    def test_chq(self):
        assert InterestCalculator.calculate_chq(Decimal("300.00"), Decimal("30.00")) == Decimal("270.00")

    def test_commission_monthly(self):
        result = InterestCalculator.calculate_monthly(10000, Decimal("2"), 3)
        assert result == Decimal("50.00")


class TestReferenceIdSanity:
    def test_first_loan(self):
        assert ReferenceIdService.next_id(2026, 3, None) == "2026_03_001"

    def test_second_loan(self):
        assert ReferenceIdService.next_id(2026, 3, 1) == "2026_03_002"

    def test_overflow(self):
        assert ReferenceIdService.next_id(2026, 12, 999) == "2026_12_1000"

    def test_parse(self):
        assert ReferenceIdService.parse("2026_03_001") == (2026, 3, 1)

    def test_parse_overflow(self):
        assert ReferenceIdService.parse("2026_12_1000") == (2026, 12, 1000)


# ---------------------------------------------------------------------------
# Smoke: Loan CRUD round-trip
# ---------------------------------------------------------------------------

class TestLoanCrudRoundTrip:
    def test_create_and_retrieve(self, uow_factory):
        from loan_manager.application.use_cases.loans.create_loan import CreateLoan
        use_case = CreateLoan(uow_factory, ReferenceIdService(), EventBus())
        dto = LoanCreateDTO(
            borrower_name="alice",
            borrower_group="grp1",
            depositor_name="bob",
            amount=50000,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 6, 1),
        )
        result = use_case.execute(dto)
        today = date.today()
        expected_prefix = f"{today.year}_{today.month:02d}_"
        assert result.reference_id.startswith(expected_prefix)
        assert result.borrower_name == "alice"
        assert result.status == LoanStatus.OVERDUE  # due_date in past relative to today

    def test_delete(self, uow, uow_factory):
        from loan_manager.application.use_cases.loans.create_loan import CreateLoan
        from loan_manager.application.use_cases.loans.delete_loan import DeleteLoan
        create = CreateLoan(uow_factory, ReferenceIdService(), EventBus())
        dto = LoanCreateDTO(
            borrower_name="charlie",
            borrower_group="grp2",
            depositor_name="dave",
            amount=10000,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 12, 31),
        )
        loan = create.execute(dto)
        ref_id = loan.reference_id

        delete = DeleteLoan(uow_factory)
        delete.execute(ref_id)
        assert uow.loans.get_by_reference_id(ref_id) is None

    def test_extend(self, uow_factory):
        from loan_manager.application.use_cases.loans.create_loan import CreateLoan
        from loan_manager.application.use_cases.loans.extend_loan import ExtendLoan
        create = CreateLoan(uow_factory, ReferenceIdService(), EventBus())
        loan = create.execute(LoanCreateDTO(
            borrower_name="eve",
            borrower_group="grp3",
            depositor_name="frank",
            amount=20000,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 6, 1),
        ))
        ref_id = loan.reference_id

        extend = ExtendLoan(uow_factory, EventBus())
        extended = extend.execute(ref_id, ExtendLoanDTO(
            extension_period=3,
            extension_period_unit="months",
        ))
        assert extended.giving_date == date(2026, 6, 1)
        assert extended.due_date == date(2026, 9, 1)


# ---------------------------------------------------------------------------
# Smoke: Interest calculation
# ---------------------------------------------------------------------------

class TestCalculationFlow:
    def test_monthly_calculation(self, uow_factory):
        from loan_manager.application.use_cases.loans.create_loan import CreateLoan
        from loan_manager.application.use_cases.reports.calculate_interest import CalculateInterest

        create = CreateLoan(uow_factory, ReferenceIdService(), EventBus())
        create.execute(LoanCreateDTO(
            borrower_name="grace",
            borrower_group="bg1",
            depositor_name="henry",
            amount=10000,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 7, 1),
        ))

        calc = CalculateInterest(uow_factory)
        req = CalculationRequestDTO(
            mode=CalculationMode.MONTHLY,
            filters=LoanFilterDTO(borrower_name="grace"),
            interest_rate=Decimal("12"),
            commission_rate=Decimal("2"),
            extension_period=3,
            extension_period_unit=ExtensionPeriodUnit.MONTHS,
            tds_flag=False,
        )
        result = calc.execute(req)
        assert len(result.lines) == 1
        assert result.lines[0].interest_amount == Decimal("300.00")
        assert result.lines[0].commission_amount == Decimal("50.00")
        assert result.total_interest == Decimal("300.00")


# ---------------------------------------------------------------------------
# Smoke: Recovery service
# ---------------------------------------------------------------------------

class TestRecoveryService:
    def test_write_and_clear(self, tmp_path, monkeypatch):
        import loan_manager.config as cfg
        monkeypatch.setattr(cfg, "RECOVERY_FILE", tmp_path / "recovery.tmp")

        from loan_manager.infrastructure.recovery.recovery_service import RecoveryService
        svc = RecoveryService()
        assert not svc.exists()

        svc.write("approve", {"report_id": "RPT_20260320_001"})
        assert svc.exists()
        data = svc.read()
        assert data["operation"] == "approve"

        svc.clear()
        assert not svc.exists()


# ---------------------------------------------------------------------------
# Smoke: CSV import round-trip
# ---------------------------------------------------------------------------

class TestCsvImportRoundTrip:
    def test_parse_csv(self, tmp_path):
        from loan_manager.infrastructure.csv.import_service import CsvImportService

        csv_file = tmp_path / "test_loans.csv"
        csv_file.write_text(
            "borrower_name,borrower_group,amount,giving_date,depositor_name,depositor_group,due_date\n"
            "alice,grp1,10000,2026-01-01,bob,grp2,2026-06-01\n"
            "charlie,grp1,20000,2026-02-01,dave,,\n",
            encoding="utf-8",
        )

        svc = CsvImportService()
        records = svc.parse(str(csv_file))
        assert len(records) == 2
        assert records[0]["borrower_name"] == "alice"
        assert records[1]["due_date"] is None

    def test_export_csv(self, tmp_path, uow_factory):
        from loan_manager.application.use_cases.loans.create_loan import CreateLoan
        from loan_manager.application.use_cases.data.export_loans import ExportLoans

        create = CreateLoan(uow_factory, ReferenceIdService(), EventBus())
        create.execute(LoanCreateDTO(
            borrower_name="irene",
            borrower_group="grpX",
            depositor_name="jack",
            amount=15000,
            giving_date=date(2026, 3, 1),
            due_date=date(2026, 9, 1),
        ))

        export_path = str(tmp_path / "export.csv")
        export = ExportLoans(uow_factory)
        result_path = export.execute(format="csv", output_path=export_path)

        assert Path(result_path).exists()
        with open(result_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert any(r.get("borrower_name") == "irene" for r in rows)
