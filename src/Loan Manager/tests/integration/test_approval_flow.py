"""Approval flow integration tests."""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.entities.report import Report, ReportRecord
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.domain.value_objects.report_id import ReportId
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    LoanStatus,
    ReportStatus,
)
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService
from loan_manager.infrastructure.recovery.backup_service import BackupService
from loan_manager.application.event_bus import EventBus
from loan_manager.application.dtos.report_dto import ApprovalResultDTO
from loan_manager.application.use_cases.reports.approve_report import ApproveReport
from loan_manager.application.use_cases.reports.decline_report import DeclineReport


def _make_uow(session):
    return SqlAlchemyUnitOfWork(session)


def _seed_loan(uow, ref_id="2026_03_001", giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1)):
    now = datetime.now()
    loan = Loan(
        id=None,
        reference_id=ReferenceId(ref_id),
        borrower_name="borrower",
        borrower_group="bg1",
        depositor_name="depositor",
        depositor_group="dg1",
        amount=Money(10000),
        giving_date=giving_date,
        due_period=None,
        due_date=due_date,
        status=LoanStatus.ACTIVE,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    uow.loans.save(loan)
    return loan


def _seed_report(uow, report_id_str="RPT_20260315_001", mode=CalculationMode.MONTHLY,
                 records_data=None):
    now = datetime.now()
    report_id = ReportId(report_id_str)

    if records_data is None:
        records_data = [{
            "reference_id": "2026_03_001",
            "post_extension_giving_date": date(2026, 4, 1),
            "post_extension_due_date": date(2026, 7, 1),
        }]

    records = []
    for rd in records_data:
        records.append(ReportRecord(
            id=None,
            report_id=report_id_str,
            reference_id=rd["reference_id"],
            borrower_name="borrower",
            depositor_name="depositor",
            depositor_group="dg1",
            amount=10000,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
            extension_period=3,
            extension_period_unit=ExtensionPeriodUnit.MONTHS,
            interest_rate=Decimal("12"),
            commission_rate=Decimal("6"),
            tds_flag=False,
            interest_amount=Decimal("300.00"),
            commission_amount=Decimal("150.00"),
            tds_amount=Decimal("0.00"),
            chq_amount=Decimal("300.00"),
            post_extension_giving_date=rd.get("post_extension_giving_date"),
            post_extension_due_date=rd.get("post_extension_due_date"),
            paidoff_date=rd.get("paidoff_date"),
        ))

    report = Report(
        id=None,
        report_id=report_id,
        report_mode=mode,
        status=ReportStatus.PENDING,
        records=records,
        created_at=now,
        updated_at=now,
    )
    return uow.reports.save(report)


class TestApproveNormalReport:
    def test_approve_updates_loan_dates(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(uow)
        _seed_report(uow)
        uow.commit()

        # Create a mock backup/recovery service
        recovery = RecoveryService()
        recovery.write = lambda op, data: None
        recovery.clear = lambda: None
        backup = BackupService()
        backup.create_backup = lambda: None
        event_bus = EventBus()

        def uow_factory():
            return _make_uow(db_session)

        approver = ApproveReport(uow_factory, recovery, backup, event_bus)
        result = approver.execute("RPT_20260315_001")

        assert result.success is True

        # Verify loan dates updated
        loan = uow.loans.get_by_reference_id("2026_03_001")
        assert loan.giving_date == date(2026, 4, 1)
        assert loan.due_date == date(2026, 7, 1)


class TestDeclineReport:
    def test_decline_leaves_loan_unchanged(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(uow)
        _seed_report(uow)
        uow.commit()

        event_bus = EventBus()

        def uow_factory():
            return _make_uow(db_session)

        decliner = DeclineReport(uow_factory, event_bus)
        decliner.execute("RPT_20260315_001")

        # Verify loan unchanged
        loan = uow.loans.get_by_reference_id("2026_03_001")
        assert loan.giving_date == date(2026, 1, 1)
        assert loan.due_date == date(2026, 4, 1)

        # Verify report is declined
        report = uow.reports.get_by_report_id("RPT_20260315_001")
        assert report.status == ReportStatus.DECLINED


class TestApprovePaidoffReport:
    def test_paidoff_approve_moves_loan_to_history(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(uow)

        paidoff_date = date(2026, 5, 1)
        _seed_report(
            uow,
            report_id_str="RPT_20260501_001",
            mode=CalculationMode.PAIDOFF,
            records_data=[{
                "reference_id": "2026_03_001",
                "post_extension_giving_date": None,
                "post_extension_due_date": None,
                "paidoff_date": paidoff_date,
            }],
        )
        uow.commit()

        recovery = RecoveryService()
        recovery.write = lambda op, data: None
        recovery.clear = lambda: None
        backup = BackupService()
        backup.create_backup = lambda: None
        event_bus = EventBus()

        def uow_factory():
            return _make_uow(db_session)

        approver = ApproveReport(uow_factory, recovery, backup, event_bus)
        result = approver.execute("RPT_20260501_001")

        assert result.success is True

        # Verify loan is inactive
        loan = uow.loans.get_by_reference_id("2026_03_001")
        assert loan.is_active is False
        assert loan.status == LoanStatus.PAIDOFF


class TestDuplicateRefIdWarning:
    def test_duplicate_warning_when_not_forced(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(uow, "2026_03_001")

        # Two reports referencing the same loan
        _seed_report(uow, "RPT_20260315_001", records_data=[{
            "reference_id": "2026_03_001",
            "post_extension_giving_date": date(2026, 4, 1),
            "post_extension_due_date": date(2026, 7, 1),
        }])
        _seed_report(uow, "RPT_20260315_002", records_data=[{
            "reference_id": "2026_03_001",
            "post_extension_giving_date": date(2026, 7, 1),
            "post_extension_due_date": date(2026, 10, 1),
        }])
        uow.commit()

        recovery = RecoveryService()
        recovery.write = lambda op, data: None
        recovery.clear = lambda: None
        backup = BackupService()
        backup.create_backup = lambda: None
        event_bus = EventBus()

        def uow_factory():
            return _make_uow(db_session)

        approver = ApproveReport(uow_factory, recovery, backup, event_bus)
        result = approver.execute("RPT_20260315_001", force=False)

        assert result.success is False
        assert result.requires_confirmation is True
        assert "2026_03_001" in result.duplicate_ref_ids


class TestDeletedLoanWarning:
    def test_deleted_loan_warning(self, db_session):
        uow = _make_uow(db_session)

        # Create report referencing a loan, but don't create the loan
        _seed_report(uow, "RPT_20260315_001", records_data=[{
            "reference_id": "2026_03_999",
            "post_extension_giving_date": date(2026, 4, 1),
            "post_extension_due_date": date(2026, 7, 1),
        }])
        uow.commit()

        recovery = RecoveryService()
        recovery.write = lambda op, data: None
        recovery.clear = lambda: None
        backup = BackupService()
        backup.create_backup = lambda: None
        event_bus = EventBus()

        def uow_factory():
            return _make_uow(db_session)

        approver = ApproveReport(uow_factory, recovery, backup, event_bus)
        result = approver.execute("RPT_20260315_001", force=False)

        assert result.success is False
        assert result.requires_confirmation is True
        assert "2026_03_999" in result.deleted_ref_ids
