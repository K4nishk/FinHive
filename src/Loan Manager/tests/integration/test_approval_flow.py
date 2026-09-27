"""Approval flow integration tests."""
from datetime import date, datetime
from decimal import Decimal

import pytest
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.create_loan import CreateLoan
from loan_manager.application.use_cases.reports.approve_report import ApproveReport
from loan_manager.application.use_cases.reports.decline_report import DeclineReport
from loan_manager.application.use_cases.reports.get_reports import GetPendingReports
from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.entities.report import Report, ReportRecord
from loan_manager.domain.events.loan_events import LoanCreated
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.domain.value_objects.report_id import ReportId
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    LoanStatus,
    ReportActor,
    ReportStatus,
)
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from loan_manager.infrastructure.recovery.backup_service import BackupService
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService


def _make_uow(session):
    return SqlAlchemyUnitOfWork(session)


def _seed_loan(
    uow,
    ref_id="2026_03_001",
    giving_date=date(2026, 1, 1),
    due_date=date(2026, 4, 1),
    status=LoanStatus.ACTIVE,
):
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
        status=status,
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
            giving_date=rd.get("giving_date", date(2026, 1, 1)),
            due_date=rd.get("due_date", date(2026, 4, 1)),
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


def _seed_create_report(
    uow,
    report_id_str="RPT_20260410_001",
    records_data=None,
    actor=ReportActor.FORM,
    user_request=None,
    turn_id=None,
):
    """A CREATE-mode (KCH-242) report: every record proposes a brand-new
    borrower, so (per the CREATE row convention) reference_id/giving_date
    are None and the proposed values live in post_extension_giving_date/
    post_extension_due_date, with extension_period=0/rates=0/derived
    amounts=None as placeholders."""
    now = datetime.now()
    report_id = ReportId(report_id_str)

    if records_data is None:
        records_data = [{
            "borrower_name": "new borrower",
            "borrower_group": "new-group",
            "amount": 15000,
            "post_extension_giving_date": date(2026, 4, 10),
            "post_extension_due_date": date(2026, 7, 10),
            "due_period": 3,
        }]

    records = []
    for rd in records_data:
        records.append(ReportRecord(
            id=None,
            report_id=report_id_str,
            reference_id=None,
            borrower_name=rd["borrower_name"],
            depositor_name=rd.get("depositor_name", "depositor"),
            depositor_group=rd.get("depositor_group"),
            amount=rd["amount"],
            giving_date=None,
            due_date=None,
            extension_period=0,
            extension_period_unit=ExtensionPeriodUnit.MONTHS,
            interest_rate=Decimal("0"),
            commission_rate=Decimal("0"),
            tds_flag=False,
            interest_amount=None,
            commission_amount=None,
            tds_amount=None,
            chq_amount=None,
            post_extension_giving_date=rd["post_extension_giving_date"],
            post_extension_due_date=rd.get("post_extension_due_date"),
            paidoff_date=None,
            borrower_group=rd["borrower_group"],
            due_period=rd.get("due_period"),
        ))

    report = Report(
        id=None,
        report_id=report_id,
        report_mode=CalculationMode.CREATE,
        status=ReportStatus.PENDING,
        records=records,
        created_at=now,
        updated_at=now,
        actor=actor,
        user_request=user_request,
        turn_id=turn_id,
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


class TestApproveRecomputesStatus:
    """KCH-233 regression: an approved extension must recompute the loan's
    status immediately (against the injected Clock), not leave the
    pre-approval status stale until the next app-launch RecomputeAllStatuses
    sweep.
    """

    def test_approve_extend_report_on_overdue_loan_sets_active_immediately(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(
            uow,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
            status=LoanStatus.OVERDUE,
        )
        _seed_report(uow, records_data=[{
            "reference_id": "2026_03_001",
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

        approver = ApproveReport(
            uow_factory, recovery, backup, event_bus,
            clock=FixedClock(date(2026, 5, 15)),
        )
        result = approver.execute("RPT_20260315_001")
        assert result.success is True

        # Fresh UoW read -- no RecomputeAllStatuses ran between approval and
        # this read, so ACTIVE can only come from ApproveReport itself.
        fresh_uow = _make_uow(db_session)
        loan = fresh_uow.loans.get_by_reference_id("2026_03_001")
        assert loan.status == LoanStatus.ACTIVE

    def test_approve_extend_report_still_overdue_keeps_overdue(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(
            uow,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
            status=LoanStatus.OVERDUE,
        )
        _seed_report(uow, records_data=[{
            "reference_id": "2026_03_001",
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

        # Clock is past the new due_date (2026-07-01) -> still OVERDUE.
        approver = ApproveReport(
            uow_factory, recovery, backup, event_bus,
            clock=FixedClock(date(2026, 8, 1)),
        )
        result = approver.execute("RPT_20260315_001")
        assert result.success is True

        fresh_uow = _make_uow(db_session)
        loan = fresh_uow.loans.get_by_reference_id("2026_03_001")
        assert loan.status == LoanStatus.OVERDUE

    def test_approve_extend_report_on_archived_loan_leaves_status_alone(self, db_session):
        """Review finding (cycle 1, MAJOR): a loan paid off (and archived via
        set_inactive) after a normal report was generated must not have its
        status overwritten by that report's approval -- is_active=False rows
        keep whatever MarkPaidOff/history archival set (PAIDOFF), never a
        status recomputed from the extension dates.
        """
        uow = _make_uow(db_session)
        _seed_loan(
            uow,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
            status=LoanStatus.OVERDUE,
        )
        _seed_report(uow, records_data=[{
            "reference_id": "2026_03_001",
            "post_extension_giving_date": date(2026, 4, 1),
            "post_extension_due_date": date(2026, 7, 1),
        }])
        uow.commit()

        # Simulate the loan being paid off and archived after report
        # generation but before this report's approval -- the same
        # is_active=False/status=PAIDOFF write ApproveReport's own PAIDOFF
        # branch (and MarkPaidOff) performs via set_inactive.
        uow.loans.set_inactive("2026_03_001")
        uow.commit()

        recovery = RecoveryService()
        recovery.write = lambda op, data: None
        recovery.clear = lambda: None
        backup = BackupService()
        backup.create_backup = lambda: None
        event_bus = EventBus()

        def uow_factory():
            return _make_uow(db_session)

        # Clock 2026-05-15 is before the post-extension due_date
        # (2026-07-01), so an unguarded recompute would set ACTIVE.
        approver = ApproveReport(
            uow_factory, recovery, backup, event_bus,
            clock=FixedClock(date(2026, 5, 15)),
        )
        result = approver.execute("RPT_20260315_001")
        assert result.success is True

        fresh_uow = _make_uow(db_session)
        loan = fresh_uow.loans.get_by_reference_id("2026_03_001")
        assert loan.status == LoanStatus.PAIDOFF
        assert loan.is_active is False

    def test_approve_extend_report_before_new_giving_date_sets_pending(self, db_session):
        """Pending branch: the clock can also land before the *new*
        (post-extension) giving_date, in which case the loan must show
        PENDING immediately, not ACTIVE/OVERDUE computed off the old dates.
        """
        uow = _make_uow(db_session)
        _seed_loan(
            uow,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
            status=LoanStatus.ACTIVE,
        )
        _seed_report(uow, records_data=[{
            "reference_id": "2026_03_001",
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

        # Clock 2026-03-01 is before the new giving_date (2026-04-01).
        approver = ApproveReport(
            uow_factory, recovery, backup, event_bus,
            clock=FixedClock(date(2026, 3, 1)),
        )
        result = approver.execute("RPT_20260315_001")
        assert result.success is True

        fresh_uow = _make_uow(db_session)
        loan = fresh_uow.loans.get_by_reference_id("2026_03_001")
        assert loan.giving_date == date(2026, 4, 1)
        assert loan.status == LoanStatus.PENDING


class TestApproveCreateReport:
    """KCH-242: approving a CREATE-mode (agent-proposed) report mints a
    brand-new loan per record on ApproveReport's own uow/transaction, then
    attaches the fresh reference_id back onto the record it came from --
    all in the SAME commit as mark_approved.
    """

    def test_approve_create_report_creates_exactly_one_loan_with_fresh_ref(self, db_session):
        uow = _make_uow(db_session)
        _seed_create_report(uow)
        uow.commit()

        recovery = RecoveryService()
        recovery.write = lambda op, data: None
        recovery.clear = lambda: None
        backup = BackupService()
        backup.create_backup = lambda: None
        event_bus = EventBus()
        created_events: list[LoanCreated] = []
        event_bus.subscribe(LoanCreated, created_events.append)

        def uow_factory():
            return _make_uow(db_session)

        approver = ApproveReport(
            uow_factory, recovery, backup, event_bus,
            clock=FixedClock(date(2026, 4, 10)),
        )
        result = approver.execute("RPT_20260410_001")

        assert result.success is True

        fresh_uow = _make_uow(db_session)
        all_loans = fresh_uow.loans.get_all_active()
        assert len(all_loans) == 1, "exactly one loan must exist after approving one CREATE record"

        loan = all_loans[0]
        assert str(loan.reference_id).startswith("2026_04_")
        assert loan.borrower_name == "new borrower"
        assert loan.borrower_group == "new-group"
        assert loan.giving_date == date(2026, 4, 10)
        assert loan.due_date == date(2026, 7, 10)

        # LoanCreated published (after the commit), then the record's own
        # reference_id assigned, then the report itself moved to Approved.
        assert [e.reference_id for e in created_events] == [str(loan.reference_id)]

        report = fresh_uow.reports.get_by_report_id("RPT_20260410_001")
        assert report.status == ReportStatus.APPROVED
        assert report.records[0].reference_id == str(loan.reference_id)

    def test_approve_create_report_is_atomic_on_failure(self, db_session, monkeypatch):
        """The SECOND of two CREATE records fails to stage -- simulated via
        a patched `CreateLoan.stage` that raises on its second call, standing
        in for any real mid-loop staging failure (a DB constraint violation,
        a disk-full error, ...). NOTHING from either record may survive
        that: not the first record's own loan (already staged/flushed, but
        never committed), not the loan_meta counter either stage() call
        would have advanced, and the report must still read back exactly
        Pending.

        Two more direct "corrupt one record" ideas were tried and rejected
        as unusable here: a negative amount is refused by
        `report_records.amount`'s `EncryptedRupees` at `uow.reports.save()`
        time in fixture setup itself (one layer too early -- it never
        reaches ApproveReport at all), and a reference_id collision with an
        existing loan is silently absorbed by `SqlAlchemyLoanRepository.save`
        being an upsert-by-reference_id (it UPDATEs instead of raising --
        itself worth a DEBT note, since a real such collision would silently
        overwrite a stranger's loan rather than fail loudly). Patching
        `stage()` isolates the property actually under test -- ApproveReport
        commits once, atomically -- from both of those unrelated layers.
        """
        uow = _make_uow(db_session)
        _seed_create_report(
            uow,
            records_data=[
                {
                    "borrower_name": "good borrower",
                    "borrower_group": "good-group",
                    "amount": 15000,
                    "post_extension_giving_date": date(2026, 4, 10),
                    "post_extension_due_date": date(2026, 7, 10),
                    "due_period": 3,
                },
                {
                    "borrower_name": "second borrower",
                    "borrower_group": "second-group",
                    "amount": 22000,
                    "post_extension_giving_date": date(2026, 4, 11),
                    "post_extension_due_date": date(2026, 7, 11),
                    "due_period": 3,
                },
            ],
        )
        uow.commit()

        recovery = RecoveryService()
        recovery.write = lambda op, data: None
        recovery.clear = lambda: None
        backup = BackupService()
        backup.create_backup = lambda: None
        event_bus = EventBus()
        created_events: list[LoanCreated] = []
        event_bus.subscribe(LoanCreated, created_events.append)

        def uow_factory():
            return _make_uow(db_session)

        approver = ApproveReport(
            uow_factory, recovery, backup, event_bus,
            clock=FixedClock(date(2026, 4, 10)),
        )

        original_stage = CreateLoan.stage
        calls = {"n": 0}

        def _fail_on_second_call(self, uow_arg, dto):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("simulated staging failure on the second record")
            return original_stage(self, uow_arg, dto)

        monkeypatch.setattr(CreateLoan, "stage", _fail_on_second_call)

        with pytest.raises(RuntimeError, match="simulated staging failure"):
            approver.execute("RPT_20260410_001")

        fresh_uow = _make_uow(db_session)
        assert fresh_uow.loans.get_all_active() == [], (
            "a failure on the SECOND record must roll back the FIRST "
            "record's loan too -- one transaction, one commit"
        )
        assert fresh_uow.loan_meta.get_last_order("2026_04") is None, (
            "loan_meta must not have advanced for a transaction that never committed"
        )
        report = fresh_uow.reports.get_by_report_id("RPT_20260410_001")
        assert report.status == ReportStatus.PENDING
        assert report.records[0].reference_id is None
        assert report.records[1].reference_id is None
        # KCH-242 review cycle 2, MINOR-2: a rolled-back approve must never
        # publish LoanCreated for the loan staged (but never committed)
        # before the failure -- publish happens strictly after `uow.commit()`
        # succeeds, so a failed transaction must leave this list empty.
        assert created_events == [], (
            "no LoanCreated may be published for a CREATE approval that "
            "failed before commit"
        )

    def test_create_records_do_not_trigger_deleted_warning(self, db_session):
        """A CREATE record's reference_id is None -- report_ref_ids must
        filter that out, or None gets treated as a 'reference_id in the
        report that no longer exists' and the approval is wrongly held for
        confirmation (KCH-242 plan: report_ref_ids ignores None refs).
        """
        uow = _make_uow(db_session)
        _seed_create_report(uow)
        uow.commit()

        recovery = RecoveryService()
        recovery.write = lambda op, data: None
        recovery.clear = lambda: None
        backup = BackupService()
        backup.create_backup = lambda: None
        event_bus = EventBus()

        def uow_factory():
            return _make_uow(db_session)

        approver = ApproveReport(
            uow_factory, recovery, backup, event_bus,
            clock=FixedClock(date(2026, 4, 10)),
        )
        result = approver.execute("RPT_20260410_001", force=False)

        assert result.success is True
        assert result.requires_confirmation is False
        assert result.deleted_ref_ids == []
        assert result.duplicate_ref_ids == []

    def test_approve_create_report_with_multiple_records_mints_distinct_consecutive_refs(
        self, db_session
    ):
        uow = _make_uow(db_session)
        _seed_create_report(
            uow,
            records_data=[
                {
                    "borrower_name": "borrower one",
                    "borrower_group": "group-1",
                    "amount": 10000,
                    "post_extension_giving_date": date(2026, 4, 10),
                    "post_extension_due_date": date(2026, 7, 10),
                    "due_period": 3,
                },
                {
                    "borrower_name": "borrower two",
                    "borrower_group": "group-2",
                    "amount": 20000,
                    "post_extension_giving_date": date(2026, 4, 11),
                    "post_extension_due_date": date(2026, 7, 11),
                    "due_period": 3,
                },
                {
                    "borrower_name": "borrower three",
                    "borrower_group": "group-3",
                    "amount": 30000,
                    "post_extension_giving_date": date(2026, 4, 12),
                    "post_extension_due_date": date(2026, 7, 12),
                    "due_period": 3,
                },
            ],
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

        approver = ApproveReport(
            uow_factory, recovery, backup, event_bus,
            clock=FixedClock(date(2026, 4, 10)),
        )
        result = approver.execute("RPT_20260410_001")
        assert result.success is True

        fresh_uow = _make_uow(db_session)
        report = fresh_uow.reports.get_by_report_id("RPT_20260410_001")
        refs = [r.reference_id for r in report.records]

        assert refs == ["2026_04_001", "2026_04_002", "2026_04_003"], (
            "each record in a multi-record CREATE report must get its OWN, "
            "consecutive reference_id -- not the same one three times"
        )
        assert len(set(refs)) == 3

        all_loans = {str(loan.reference_id): loan for loan in fresh_uow.loans.get_all_active()}
        assert len(all_loans) == 3
        assert all_loans["2026_04_001"].borrower_name == "borrower one"
        assert all_loans["2026_04_002"].borrower_name == "borrower two"
        assert all_loans["2026_04_003"].borrower_name == "borrower three"


class TestApproveCreateReportNeverOverwritesAnExistingLoan:
    """KCH-242 review cycle 1 (BLOCKER): `CreateLoan.stage` mints a
    reference_id from the `loan_meta` counter, but `SqlAlchemyLoanRepository
    .save()` upserts BY reference_id. `ImportLoans.commit()` never bumps
    `loan_meta` for a CSV row that already carries its own reference_id, so
    the counter can lag behind a loan that already exists under the very id
    `stage()` would otherwise mint next -- an approval then silently
    OVERWRITES that loan instead of creating a new one (success=True, no
    error, the original's data is just gone).
    """

    def test_create_approval_skips_an_existing_ref_and_leaves_it_untouched(self, db_session):
        uow = _make_uow(db_session)
        # Simulates ImportLoans writing 2026_03_001 with its own explicit
        # ref and never bumping loan_meta -- get_last_order("2026_03") stays
        # None, exactly as if nothing had ever been minted this month.
        original = _seed_loan(
            uow,
            ref_id="2026_03_001",
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
            status=LoanStatus.ACTIVE,
        )
        _seed_create_report(uow, report_id_str="RPT_20260310_001")
        uow.commit()
        assert uow.loan_meta.get_last_order("2026_03") is None

        recovery = RecoveryService()
        recovery.write = lambda op, data: None
        recovery.clear = lambda: None
        backup = BackupService()
        backup.create_backup = lambda: None
        event_bus = EventBus()

        def uow_factory():
            return _make_uow(db_session)

        # Clock lands in the SAME year-month as the existing "2026_03_001"
        # -- an unguarded stage() would mint that exact id again.
        approver = ApproveReport(
            uow_factory, recovery, backup, event_bus,
            clock=FixedClock(date(2026, 3, 15)),
        )
        result = approver.execute("RPT_20260310_001")
        assert result.success is True

        fresh_uow = _make_uow(db_session)
        report = fresh_uow.reports.get_by_report_id("RPT_20260310_001")
        new_ref = report.records[0].reference_id

        assert new_ref != "2026_03_001", (
            "the CREATE approval must never mint the already-taken "
            "2026_03_001"
        )
        assert new_ref.startswith("2026_03_")

        original_reloaded = fresh_uow.loans.get_by_reference_id("2026_03_001")
        assert original_reloaded is not None, "the original loan must still exist"
        assert original_reloaded.borrower_name == original.borrower_name
        assert original_reloaded.borrower_group == original.borrower_group
        assert original_reloaded.amount == original.amount
        assert original_reloaded.giving_date == date(2026, 1, 1)
        assert original_reloaded.due_date == date(2026, 4, 1)
        assert original_reloaded.is_active is True
        assert original_reloaded.status == LoanStatus.ACTIVE

        new_loan = fresh_uow.loans.get_by_reference_id(new_ref)
        assert new_loan is not None
        assert new_loan.borrower_name == "new borrower"

    def test_create_approval_does_not_resurrect_a_paidoff_loan_at_that_ref(self, db_session):
        """A paid-off loan stays in `loans` with is_active=False (never
        deleted) until archival -- its reference_id must be just as
        off-limits to a fresh CREATE mint as an active loan's."""
        uow = _make_uow(db_session)
        original = _seed_loan(
            uow,
            ref_id="2026_03_001",
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
            status=LoanStatus.PAIDOFF,
        )
        uow.loans.set_inactive("2026_03_001")
        _seed_create_report(uow, report_id_str="RPT_20260310_001")
        uow.commit()

        recovery = RecoveryService()
        recovery.write = lambda op, data: None
        recovery.clear = lambda: None
        backup = BackupService()
        backup.create_backup = lambda: None
        event_bus = EventBus()

        def uow_factory():
            return _make_uow(db_session)

        approver = ApproveReport(
            uow_factory, recovery, backup, event_bus,
            clock=FixedClock(date(2026, 3, 15)),
        )
        result = approver.execute("RPT_20260310_001")
        assert result.success is True

        fresh_uow = _make_uow(db_session)
        report = fresh_uow.reports.get_by_report_id("RPT_20260310_001")
        new_ref = report.records[0].reference_id
        assert new_ref != "2026_03_001"

        paidoff_reloaded = fresh_uow.loans.get_by_reference_id("2026_03_001")
        assert paidoff_reloaded is not None, "the paid-off loan must not be deleted or replaced"
        assert paidoff_reloaded.is_active is False
        assert paidoff_reloaded.borrower_name == original.borrower_name


class TestApproveIsIdempotent:
    """KCH-242 review cycle 1 (MAJOR): re-approving an already-Approved
    report must be a no-op failure, never a second mint/update pass."""

    def test_second_approval_of_an_already_approved_create_report_mints_no_extra_loan(
        self, db_session
    ):
        uow = _make_uow(db_session)
        _seed_create_report(uow)
        uow.commit()

        recovery = RecoveryService()
        recovery.write = lambda op, data: None
        recovery.clear = lambda: None
        backup = BackupService()
        backup.create_backup = lambda: None
        event_bus = EventBus()

        def uow_factory():
            return _make_uow(db_session)

        approver = ApproveReport(
            uow_factory, recovery, backup, event_bus,
            clock=FixedClock(date(2026, 4, 10)),
        )
        first = approver.execute("RPT_20260410_001")
        assert first.success is True

        second = approver.execute("RPT_20260410_001")

        assert second.success is False, (
            "a report that is already Approved must refuse a second "
            "approval, not mint a duplicate loan"
        )

        fresh_uow = _make_uow(db_session)
        assert len(fresh_uow.loans.get_all_active()) == 1, (
            "only ONE loan may exist no matter how many times execute() is "
            "called on an already-approved report"
        )

    def test_second_approval_of_an_already_approved_normal_report_reapplies_nothing(
        self, db_session
    ):
        uow = _make_uow(db_session)
        _seed_loan(uow)
        _seed_report(uow)
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
        first = approver.execute("RPT_20260315_001")
        assert first.success is True

        second = approver.execute("RPT_20260315_001")
        assert second.success is False

    def test_approving_a_declined_create_report_mints_no_loan(self, db_session):
        """KCH-242 review cycle 2, MINOR-1: the PENDING-only guard
        (`approve_report.py`, `if report.status != ReportStatus.PENDING`)
        is right, but every existing idempotency test above only exercises
        an already-APPROVED report. A DECLINED AGENT proposal is the case
        that actually matters for agent proposals: decline it, then try to
        approve it anyway -- must refuse, mint nothing."""
        uow = _make_uow(db_session)
        _seed_create_report(uow)
        uow.commit()

        event_bus = EventBus()

        def uow_factory():
            return _make_uow(db_session)

        DeclineReport(uow_factory, event_bus).execute("RPT_20260410_001")

        fresh_uow = _make_uow(db_session)
        assert fresh_uow.reports.get_by_report_id(
            "RPT_20260410_001"
        ).status == ReportStatus.DECLINED

        recovery = RecoveryService()
        recovery.write = lambda op, data: None
        recovery.clear = lambda: None
        backup = BackupService()
        backup.create_backup = lambda: None

        approver = ApproveReport(
            uow_factory, recovery, backup, event_bus,
            clock=FixedClock(date(2026, 4, 10)),
        )
        result = approver.execute("RPT_20260410_001")

        assert result.success is False, (
            "a DECLINED report must never be approvable"
        )

        final_uow = _make_uow(db_session)
        assert final_uow.loans.get_all_active() == [], (
            "no loan may be minted from a DECLINED CREATE report"
        )
        assert final_uow.reports.get_by_report_id(
            "RPT_20260410_001"
        ).status == ReportStatus.DECLINED


class TestGetPendingReportsMapsEveryField:
    """KCH-242 review cycle 1 (MAJOR, ORCH RULING): GetPendingReports must
    map actor/user_request/turn_id/borrower_group/due_period through --
    dropping them silently mislabelled every AGENT report as FORM
    (ReportDTO.actor used to default to FORM)."""

    def test_an_agent_create_report_keeps_its_actor_and_agent_fields_on_read(self, db_session):
        uow = _make_uow(db_session)
        _seed_create_report(
            uow,
            report_id_str="RPT_20260410_002",
            records_data=[{
                "borrower_name": "agent borrower",
                "borrower_group": "agent-group",
                "amount": 12000,
                "post_extension_giving_date": date(2026, 4, 10),
                "post_extension_due_date": date(2026, 7, 10),
                "due_period": 3,
            }],
            actor=ReportActor.AGENT,
            user_request="lend 12000 to a new borrower for 3 months",
            turn_id="turn-abc-123",
        )
        uow.commit()

        def uow_factory():
            return _make_uow(db_session)

        reports = GetPendingReports(uow_factory).execute()
        report = next(r for r in reports if r.report_id == "RPT_20260410_002")

        assert report.actor == ReportActor.AGENT, (
            "an AGENT report must read back as AGENT, not silently default "
            "to FORM"
        )
        assert report.user_request == "lend 12000 to a new borrower for 3 months"
        assert report.turn_id == "turn-abc-123"
        assert report.records[0].borrower_group == "agent-group"
        assert report.records[0].due_period == 3
