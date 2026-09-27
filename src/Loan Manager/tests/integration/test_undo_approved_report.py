"""Integration tests for UndoApprovedReport (KCH-244).

Reuses `_make_uow`/`_seed_loan`/`_seed_report`/`_seed_create_report` from
test_approval_flow.py (Ponytail rung 2 -- this is the same seeding shape
ApproveReport's own tests already use, and undo's fixtures are approval's
fixtures plus one extra step).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from loan_manager.application.dtos.loan_dto import LoanUpdateDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.update_loan import UpdateLoan
from loan_manager.application.use_cases.reports.approve_report import ApproveReport
from loan_manager.application.use_cases.reports.decline_report import DeclineReport
from loan_manager.application.use_cases.reports.undo_approved_report import (
    UndoApprovedReport,
)
from loan_manager.domain.entities.report import Report, ReportRecord
from loan_manager.domain.events.report_events import ReportReverted
from loan_manager.domain.value_objects.report_id import ReportId
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    LoanStatus,
    ReportStatus,
)
from loan_manager.infrastructure.database.models import LoanHistoryModel
from loan_manager.infrastructure.recovery.backup_service import BackupService
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService

from tests.integration.test_approval_flow import (
    _make_uow,
    _seed_create_report,
    _seed_loan,
    _seed_report,
)

_CLOCK = FixedClock(date(2026, 5, 15))


def _approver(db_session, clock=_CLOCK):
    recovery = RecoveryService()
    recovery.write = lambda op, data: None
    recovery.clear = lambda: None
    backup = BackupService()
    backup.create_backup = lambda: None
    event_bus = EventBus()

    def uow_factory():
        return _make_uow(db_session)

    approver = ApproveReport(uow_factory, recovery, backup, event_bus, clock=clock)
    return approver, event_bus, uow_factory


def _undoer(uow_factory, event_bus=None, clock=_CLOCK) -> UndoApprovedReport:
    return UndoApprovedReport(uow_factory, event_bus or EventBus(), clock=clock)


class TestUndoThreeItemExtendBatch:
    """ACCEPTANCE (KCH-244 plan §3.1): a three-record MONTHLY report,
    approved, then undone -- every loan's dates AND recomputed status must
    both come back to their pre-approval values."""

    def test_undo_three_item_extend_batch_restores_prior_dates_and_statuses(
        self, db_session
    ):
        uow = _make_uow(db_session)
        _seed_loan(
            uow, ref_id="2026_01_001",
            giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
            status=LoanStatus.OVERDUE,
        )
        _seed_loan(
            uow, ref_id="2026_02_001",
            giving_date=date(2026, 2, 1), due_date=date(2026, 6, 1),
            status=LoanStatus.ACTIVE,
        )
        _seed_loan(
            uow, ref_id="2026_01_002",
            giving_date=date(2026, 1, 15), due_date=None,
            status=LoanStatus.OVERDUE,
        )
        _seed_report(
            uow,
            "RPT_20260315_900",
            mode=CalculationMode.MONTHLY,
            records_data=[
                {
                    "reference_id": "2026_01_001",
                    "giving_date": date(2026, 1, 1),
                    "due_date": date(2026, 4, 1),
                    "post_extension_giving_date": date(2026, 4, 1),
                    "post_extension_due_date": date(2026, 7, 1),
                },
                {
                    "reference_id": "2026_02_001",
                    "giving_date": date(2026, 2, 1),
                    "due_date": date(2026, 6, 1),
                    "post_extension_giving_date": date(2026, 6, 1),
                    "post_extension_due_date": date(2026, 9, 1),
                },
                {
                    "reference_id": "2026_01_002",
                    "giving_date": date(2026, 1, 15),
                    "due_date": None,
                    "post_extension_giving_date": date(2026, 5, 1),
                    "post_extension_due_date": date(2026, 8, 1),
                },
            ],
        )
        uow.commit()

        approver, _, uow_factory = _approver(db_session)
        result = approver.execute("RPT_20260315_900")
        assert result.success is True

        fresh = _make_uow(db_session)
        a = fresh.loans.get_by_reference_id("2026_01_001")
        b = fresh.loans.get_by_reference_id("2026_02_001")
        c = fresh.loans.get_by_reference_id("2026_01_002")
        assert (a.giving_date, a.due_date, a.status) == (
            date(2026, 4, 1), date(2026, 7, 1), LoanStatus.ACTIVE,
        )
        assert (b.giving_date, b.due_date, b.status) == (
            date(2026, 6, 1), date(2026, 9, 1), LoanStatus.PENDING,
        )
        assert (c.giving_date, c.due_date, c.status) == (
            date(2026, 5, 1), date(2026, 8, 1), LoanStatus.ACTIVE,
        )

        undoer = _undoer(uow_factory)
        undo_result = undoer.execute("RPT_20260315_900")
        assert undo_result.success is True

        fresh2 = _make_uow(db_session)
        a2 = fresh2.loans.get_by_reference_id("2026_01_001")
        b2 = fresh2.loans.get_by_reference_id("2026_02_001")
        c2 = fresh2.loans.get_by_reference_id("2026_01_002")
        assert (a2.giving_date, a2.due_date, a2.status) == (
            date(2026, 1, 1), date(2026, 4, 1), LoanStatus.OVERDUE,
        )
        assert (b2.giving_date, b2.due_date, b2.status) == (
            date(2026, 2, 1), date(2026, 6, 1), LoanStatus.ACTIVE,
        )
        assert (c2.giving_date, c2.due_date, c2.status) == (
            date(2026, 1, 15), None, LoanStatus.OVERDUE,
        )

        report = fresh2.reports.get_by_report_id("RPT_20260315_900")
        assert report.status == ReportStatus.REVERTED


class TestSecondUndoIsRefused:
    def test_second_undo_is_refused_and_changes_nothing(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(uow)
        _seed_report(uow)
        uow.commit()

        approver, _, uow_factory = _approver(db_session)
        approver.execute("RPT_20260315_001")

        undoer = _undoer(uow_factory)
        first = undoer.execute("RPT_20260315_001")
        assert first.success is True

        second = undoer.execute("RPT_20260315_001")
        assert second.success is False
        assert second.reason == "not_approved"

        fresh = _make_uow(db_session)
        loan = fresh.loans.get_by_reference_id("2026_03_001")
        # Still reverted -- the second (refused) call touched nothing further.
        assert loan.giving_date == date(2026, 1, 1)
        assert loan.due_date == date(2026, 4, 1)
        report = fresh.reports.get_by_report_id("RPT_20260315_001")
        assert report.status == ReportStatus.REVERTED


class TestUndoOfPendingOrDeclinedReportIsRefused:
    @pytest.mark.parametrize("decline", [False, True])
    def test_undo_of_pending_or_declined_report_is_refused(self, db_session, decline):
        uow = _make_uow(db_session)
        _seed_loan(uow)
        _seed_report(uow)
        uow.commit()

        def uow_factory():
            return _make_uow(db_session)

        if decline:
            DeclineReport(uow_factory, EventBus()).execute("RPT_20260315_001")

        undoer = _undoer(uow_factory)
        result = undoer.execute("RPT_20260315_001")

        assert result.success is False
        assert result.reason == "not_approved"


class TestUndoRefusesWholeBatchOnConflict:
    def test_undo_refuses_whole_batch_when_one_loan_changed_since_approval(
        self, db_session
    ):
        uow = _make_uow(db_session)
        _seed_loan(uow, ref_id="2026_03_001")
        _seed_loan(uow, ref_id="2026_03_002")
        _seed_loan(uow, ref_id="2026_03_003")
        _seed_report(
            uow,
            "RPT_20260315_910",
            records_data=[
                {
                    "reference_id": "2026_03_001",
                    "post_extension_giving_date": date(2026, 4, 1),
                    "post_extension_due_date": date(2026, 7, 1),
                },
                {
                    "reference_id": "2026_03_002",
                    "post_extension_giving_date": date(2026, 4, 1),
                    "post_extension_due_date": date(2026, 7, 1),
                },
                {
                    "reference_id": "2026_03_003",
                    "post_extension_giving_date": date(2026, 4, 1),
                    "post_extension_due_date": date(2026, 7, 1),
                },
            ],
        )
        uow.commit()

        approver, _, uow_factory = _approver(db_session)
        result = approver.execute("RPT_20260315_910")
        assert result.success is True

        # Simulate an UpdateLoan edit on B after approval, moving its due_date.
        mid_uow = _make_uow(db_session)
        b_loan = mid_uow.loans.get_by_reference_id("2026_03_002")
        b_loan.due_date = date(2026, 12, 1)
        mid_uow.loans.save(b_loan)
        mid_uow.commit()

        undoer = _undoer(uow_factory)
        undo_result = undoer.execute("RPT_20260315_910")

        assert undo_result.success is False
        assert undo_result.reason == "changed_since_approval"
        assert undo_result.conflict_ref_ids == ["2026_03_002"]

        fresh = _make_uow(db_session)
        a = fresh.loans.get_by_reference_id("2026_03_001")
        c = fresh.loans.get_by_reference_id("2026_03_003")
        assert a.giving_date == date(2026, 4, 1) and a.due_date == date(2026, 7, 1)
        assert c.giving_date == date(2026, 4, 1) and c.due_date == date(2026, 7, 1)
        report = fresh.reports.get_by_report_id("RPT_20260315_910")
        assert report.status == ReportStatus.APPROVED


class TestUndoRefusesWhenLoanPaidOffSinceApproval:
    def test_undo_refuses_when_loan_paid_off_since_approval(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(uow)
        _seed_report(uow)
        uow.commit()

        approver, _, uow_factory = _approver(db_session)
        approver.execute("RPT_20260315_001")

        mid_uow = _make_uow(db_session)
        mid_uow.loans.set_inactive("2026_03_001")
        mid_uow.commit()

        undoer = _undoer(uow_factory)
        result = undoer.execute("RPT_20260315_001")

        assert result.success is False
        assert result.reason == "changed_since_approval"
        assert result.conflict_ref_ids == ["2026_03_001"]

        report = _make_uow(db_session).reports.get_by_report_id("RPT_20260315_001")
        assert report.status == ReportStatus.APPROVED


class TestUndoRefusesWhenLoanDeletedSinceApproval:
    def test_undo_refuses_when_loan_deleted_since_approval(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(uow)
        _seed_report(uow)
        uow.commit()

        approver, _, uow_factory = _approver(db_session)
        approver.execute("RPT_20260315_001")

        mid_uow = _make_uow(db_session)
        mid_uow.loans.delete("2026_03_001")
        mid_uow.commit()

        undoer = _undoer(uow_factory)
        result = undoer.execute("RPT_20260315_001")

        assert result.success is False
        assert result.reason == "changed_since_approval"
        assert result.conflict_ref_ids == ["2026_03_001"]

        report = _make_uow(db_session).reports.get_by_report_id("RPT_20260315_001")
        assert report.status == ReportStatus.APPROVED


class TestUndoRefusesWhenLoanIsInANewerPendingReport:
    def test_undo_refuses_when_loan_is_in_a_newer_pending_report(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(uow)
        _seed_report(uow)
        uow.commit()

        approver, _, uow_factory = _approver(db_session)
        approver.execute("RPT_20260315_001")

        mid_uow = _make_uow(db_session)
        _seed_report(
            mid_uow,
            "RPT_20260401_001",
            records_data=[
                {
                    "reference_id": "2026_03_001",
                    "post_extension_giving_date": date(2026, 7, 1),
                    "post_extension_due_date": date(2026, 10, 1),
                }
            ],
        )
        mid_uow.commit()

        undoer = _undoer(uow_factory)
        result = undoer.execute("RPT_20260315_001")

        assert result.success is False
        assert result.reason == "changed_since_approval"
        assert result.conflict_ref_ids == ["2026_03_001"]


class TestUndoCreateReportDeactivatesMintedLoans:
    def test_undo_create_report_deactivates_the_minted_loans(self, db_session):
        uow = _make_uow(db_session)
        _seed_create_report(uow)
        uow.commit()

        create_clock = FixedClock(date(2026, 4, 10))
        approver, _, uow_factory = _approver(db_session, clock=create_clock)
        result = approver.execute("RPT_20260410_001")
        assert result.success is True

        fresh = _make_uow(db_session)
        report = fresh.reports.get_by_report_id("RPT_20260410_001")
        minted_ref = report.records[0].reference_id
        loan = fresh.loans.get_by_reference_id(minted_ref)
        assert loan.is_active is True

        undoer = _undoer(uow_factory, clock=create_clock)
        undo_result = undoer.execute("RPT_20260410_001")
        assert undo_result.success is True

        fresh2 = _make_uow(db_session)
        loan2 = fresh2.loans.get_by_reference_id(minted_ref)
        assert loan2.is_active is False
        report2 = fresh2.reports.get_by_report_id("RPT_20260410_001")
        assert report2.status == ReportStatus.REVERTED


class TestUndoCreateReportRefusedWhenMintedLoanEditedSince:
    def test_undo_create_report_refused_when_minted_loan_edited_since(self, db_session):
        uow = _make_uow(db_session)
        _seed_create_report(uow)
        uow.commit()

        create_clock = FixedClock(date(2026, 4, 10))
        approver, _, uow_factory = _approver(db_session, clock=create_clock)
        approver.execute("RPT_20260410_001")

        fresh = _make_uow(db_session)
        report = fresh.reports.get_by_report_id("RPT_20260410_001")
        minted_ref = report.records[0].reference_id

        mid_uow = _make_uow(db_session)
        loan = mid_uow.loans.get_by_reference_id(minted_ref)
        loan.giving_date = date(2026, 4, 20)
        mid_uow.loans.save(loan)
        mid_uow.commit()

        undoer = _undoer(uow_factory, clock=create_clock)
        result = undoer.execute("RPT_20260410_001")

        assert result.success is False
        assert result.reason == "changed_since_approval"
        assert result.conflict_ref_ids == [minted_ref]

        final = _make_uow(db_session)
        loan_final = final.loans.get_by_reference_id(minted_ref)
        assert loan_final.is_active is True
        assert loan_final.giving_date == date(2026, 4, 20)


class TestUndoCreateDuePeriodDerivedDueDateIsNotAFalseConflict:
    def test_undo_create_with_due_period_derived_due_date_is_not_a_false_conflict(
        self, db_session
    ):
        uow = _make_uow(db_session)
        _seed_create_report(
            uow,
            records_data=[
                {
                    "borrower_name": "derived due borrower",
                    "borrower_group": "derived-group",
                    "amount": 18000,
                    "post_extension_giving_date": date(2026, 4, 10),
                    "post_extension_due_date": None,
                    "due_period": 3,
                }
            ],
        )
        uow.commit()

        create_clock = FixedClock(date(2026, 4, 10))
        approver, _, uow_factory = _approver(db_session, clock=create_clock)
        result = approver.execute("RPT_20260410_001")
        assert result.success is True

        fresh = _make_uow(db_session)
        report = fresh.reports.get_by_report_id("RPT_20260410_001")
        minted_ref = report.records[0].reference_id
        loan = fresh.loans.get_by_reference_id(minted_ref)
        # Derived by LoanCreateDTO.derive_due_date: giving_date + 3 months.
        assert loan.due_date == date(2026, 7, 10)

        undoer = _undoer(uow_factory, clock=create_clock)
        undo_result = undoer.execute("RPT_20260410_001")

        assert undo_result.success is True
        final = _make_uow(db_session)
        assert final.loans.get_by_reference_id(minted_ref).is_active is False


class TestUndoPaidoffReportIsRefused:
    def test_undo_paidoff_report_is_refused_and_touches_nothing(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(uow)
        paidoff_date = date(2026, 5, 1)
        _seed_report(
            uow,
            "RPT_20260501_001",
            mode=CalculationMode.PAIDOFF,
            records_data=[
                {
                    "reference_id": "2026_03_001",
                    "post_extension_giving_date": None,
                    "post_extension_due_date": None,
                    "paidoff_date": paidoff_date,
                }
            ],
        )
        uow.commit()

        approver, _, uow_factory = _approver(db_session)
        result = approver.execute("RPT_20260501_001")
        assert result.success is True

        history_before = db_session.query(LoanHistoryModel).count()

        undoer = _undoer(uow_factory)
        undo_result = undoer.execute("RPT_20260501_001")

        assert undo_result.success is False
        assert undo_result.reason == "paidoff_not_undoable"

        history_after = db_session.query(LoanHistoryModel).count()
        assert history_after == history_before

        fresh = _make_uow(db_session)
        loan = fresh.loans.get_by_reference_id("2026_03_001")
        assert loan.is_active is False
        assert loan.status == LoanStatus.PAIDOFF
        report = fresh.reports.get_by_report_id("RPT_20260501_001")
        assert report.status == ReportStatus.APPROVED


class TestUndoPublishesReportRevertedOnlyOnSuccess:
    def test_undo_publishes_report_reverted_only_on_success(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(uow, ref_id="2026_03_001")
        _seed_report(uow, "RPT_20260315_920")  # left PENDING -- never approved
        uow.commit()

        event_bus = EventBus()
        reverted_events: list[ReportReverted] = []
        event_bus.subscribe(ReportReverted, reverted_events.append)

        def uow_factory():
            return _make_uow(db_session)

        undoer = UndoApprovedReport(uow_factory, event_bus, clock=_CLOCK)

        refused = undoer.execute("RPT_20260315_920")
        assert refused.success is False
        assert reverted_events == []

        uow2 = _make_uow(db_session)
        _seed_loan(uow2, ref_id="2026_03_778")
        _seed_report(
            uow2,
            "RPT_20260315_921",
            records_data=[
                {
                    "reference_id": "2026_03_778",
                    "post_extension_giving_date": date(2026, 4, 1),
                    "post_extension_due_date": date(2026, 7, 1),
                }
            ],
        )
        uow2.commit()

        recovery = RecoveryService()
        recovery.write = lambda op, data: None
        recovery.clear = lambda: None
        backup = BackupService()
        backup.create_backup = lambda: None
        approver = ApproveReport(uow_factory, recovery, backup, EventBus(), clock=_CLOCK)
        approve_result = approver.execute("RPT_20260315_921")
        assert approve_result.success is True

        success = undoer.execute("RPT_20260315_921")
        assert success.success is True
        assert [e.report_id for e in reverted_events] == ["RPT_20260315_921"]


class TestUndoUnknownReportRaises:
    def test_undo_unknown_report_raises(self, db_session):
        def uow_factory():
            return _make_uow(db_session)

        undoer = UndoApprovedReport(uow_factory, EventBus(), clock=_CLOCK)
        with pytest.raises(ValueError, match="Report not found"):
            undoer.execute("RPT_DOES_NOT_EXIST")


class TestUndoCreateReportRefusedWhenMintedLoanDeletedSince:
    """CREATE's own version of TestUndoRefusesWhenLoanDeletedSinceApproval --
    covers `_create_conflicts`' `loan is None or not loan.is_active` branch,
    which the "edited since" test above never reaches (that one always finds
    the loan, just with different dates)."""

    def test_undo_create_report_refused_when_minted_loan_deleted_since(self, db_session):
        uow = _make_uow(db_session)
        _seed_create_report(uow)
        uow.commit()

        create_clock = FixedClock(date(2026, 4, 10))
        approver, _, uow_factory = _approver(db_session, clock=create_clock)
        approver.execute("RPT_20260410_001")

        fresh = _make_uow(db_session)
        report = fresh.reports.get_by_report_id("RPT_20260410_001")
        minted_ref = report.records[0].reference_id

        mid_uow = _make_uow(db_session)
        mid_uow.loans.delete(minted_ref)
        mid_uow.commit()

        undoer = _undoer(uow_factory, clock=create_clock)
        result = undoer.execute("RPT_20260410_001")

        assert result.success is False
        assert result.reason == "changed_since_approval"
        assert result.conflict_ref_ids == [minted_ref]


class TestUndoCreateReportRefusedWhenMintedLoanInNewerPendingReport:
    """CREATE's own version of TestUndoRefusesWhenLoanIsInANewerPendingReport
    -- covers `_create_conflicts`' `ref in pending_refs` branch."""

    def test_undo_create_report_refused_when_minted_loan_is_in_a_newer_pending_report(
        self, db_session
    ):
        uow = _make_uow(db_session)
        _seed_create_report(uow)
        uow.commit()

        create_clock = FixedClock(date(2026, 4, 10))
        approver, _, uow_factory = _approver(db_session, clock=create_clock)
        approver.execute("RPT_20260410_001")

        fresh = _make_uow(db_session)
        report = fresh.reports.get_by_report_id("RPT_20260410_001")
        minted_ref = report.records[0].reference_id

        mid_uow = _make_uow(db_session)
        _seed_report(
            mid_uow,
            "RPT_20260501_001",
            records_data=[
                {
                    "reference_id": minted_ref,
                    "post_extension_giving_date": date(2026, 8, 1),
                    "post_extension_due_date": date(2026, 11, 1),
                }
            ],
        )
        mid_uow.commit()

        undoer = _undoer(uow_factory, clock=create_clock)
        result = undoer.execute("RPT_20260410_001")

        assert result.success is False
        assert result.reason == "changed_since_approval"
        assert result.conflict_ref_ids == [minted_ref]


class TestUndoRefusesUnrecognizedReportMode:
    """ORCHESTRATOR RULING: a CalculationMode neither the CREATE, PAIDOFF nor
    EXTEND branch recognises must be refused loudly, never silently treated
    as an EXTEND report. CalculationMode's *own* enum has only 5 members
    today, and `report_model_to_entity` enforces membership on every real
    read, so this can only be exercised with a hand-built domain `Report`
    behind a minimal fake UoW -- there is no way to get an unrecognised mode
    through the real repository at all, which is exactly the safety net this
    test is pinning down."""

    def test_undo_refuses_unrecognized_report_mode(self):
        record = ReportRecord(
            id=1,
            report_id="RPT_20260901_001",
            reference_id="2026_03_999",
            borrower_name="borrower",
            depositor_name="depositor",
            depositor_group=None,
            amount=1000,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
            extension_period=1,
            extension_period_unit=ExtensionPeriodUnit.MONTHS,
            interest_rate=Decimal("1"),
            commission_rate=Decimal("1"),
            tds_flag=False,
            interest_amount=None,
            commission_amount=None,
            tds_amount=None,
            chq_amount=None,
            post_extension_giving_date=None,
            post_extension_due_date=None,
            paidoff_date=None,
        )
        # A plain str works: CalculationMode is a `str, Enum`, so every
        # `==`/`in` check below compares by string value, exactly as it
        # would against a real (but as-yet-unknown-to-this-code) enum member.
        report = Report(
            id=1,
            report_id=ReportId("RPT_20260901_001"),
            report_mode="FutureMode",
            status=ReportStatus.APPROVED,
            records=[record],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        class _FakeReportsRepo:
            def get_by_report_id(self, report_id):
                return report if report_id == "RPT_20260901_001" else None

        class _FakeUow:
            def __init__(self):
                self.reports = _FakeReportsRepo()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def commit(self):
                raise AssertionError("must never commit on a refusal")

        undoer = UndoApprovedReport(lambda: _FakeUow(), EventBus(), clock=_CLOCK)
        result = undoer.execute("RPT_20260901_001")

        assert result.success is False
        assert result.reason == "unrecognized_report_mode"


# ---------------------------------------------------------------------------
# Review cycle 1, MAJOR-1: CREATE undo must detect an edit to ANY field
# approval wrote -- not just giving_date/due_date. `_create_conflicts`
# previously compared dates only, so `set_inactive` silently threw away a
# name/group/amount/due_period edit make since approval, along with the
# loan's dates. Each of these 3 tests edits exactly ONE non-date field and
# leaves the dates untouched, isolating the fixed comparison from the
# pre-existing date compare.
# ---------------------------------------------------------------------------


class TestUndoCreateReportRefusedWhenMintedLoanFieldEditedSince:
    """Review cycle 2, MINOR-1: parametrised over every CREATE-compared
    field that isn't already covered by its own dedicated test (amount:
    TestUndoCreateReportRefusedWhenMintedLoanAmountEditedSince; due_date:
    TestUndoCreateReportRefusedWhenMintedLoanDueDateOnlyEditedSince;
    giving_date: TestUndoCreateReportRefusedWhenMintedLoanEditedSince) --
    borrower_name (kept from cycle 1), borrower_group, depositor_name,
    depositor_group, due_period. Each kills the mutant that drops that one
    field's compare in `_create_conflicts`
    (undo_approved_report.py:139/140/141/144 -- borrower_name/borrower_group/
    depositor_name/depositor_group, and :144 due_period per the reviewer's
    C1/C2/C3/C4/C6)."""

    @pytest.mark.parametrize(
        "update_kwargs, changed_attr, changed_value",
        [
            pytest.param(
                {"borrower_name": "corrected name"}, "borrower_name", "corrected name",
                id="borrower_name",
            ),
            pytest.param(
                {"borrower_group": "other-group"}, "borrower_group", "other-group",
                id="borrower_group",
            ),
            pytest.param(
                {"depositor_name": "other depositor"}, "depositor_name", "other depositor",
                id="depositor_name",
            ),
            pytest.param(
                {"depositor_group": "other-dep-group"}, "depositor_group", "other-dep-group",
                id="depositor_group",
            ),
            pytest.param({"due_period": 6}, "due_period", 6, id="due_period"),
        ],
    )
    def test_undo_create_report_refused_when_minted_loan_field_edited_since(
        self, db_session, update_kwargs, changed_attr, changed_value
    ):
        uow = _make_uow(db_session)
        _seed_create_report(uow)
        uow.commit()

        create_clock = FixedClock(date(2026, 4, 10))
        approver, _, uow_factory = _approver(db_session, clock=create_clock)
        approver.execute("RPT_20260410_001")

        fresh = _make_uow(db_session)
        report = fresh.reports.get_by_report_id("RPT_20260410_001")
        minted_ref = report.records[0].reference_id

        UpdateLoan(uow_factory).execute(minted_ref, LoanUpdateDTO(**update_kwargs))

        undoer = _undoer(uow_factory, clock=create_clock)
        result = undoer.execute("RPT_20260410_001")

        assert result.success is False
        assert result.reason == "changed_since_approval"
        assert result.conflict_ref_ids == [minted_ref]

        final = _make_uow(db_session)
        loan = final.loans.get_by_reference_id(minted_ref)
        assert loan.is_active is True
        assert getattr(loan, changed_attr) == changed_value


class TestUndoCreateWithMixedCaseRecordNamesIsNotAFalseConflict:
    """Review cycle 2, MINOR-2: `_create_conflicts` must compare the loan
    against `record_to_loan_create_dto(rec)` -- the SAME normalised
    (lowercase/stripped) DTO `stage()` built the loan from -- never against
    the report record's raw fields. A record carrying un-normalised casing
    or padding (e.g. a future agent/form producer that doesn't pre-lowercase)
    is not a real difference once both sides go through the same DTO, and
    must not block a legitimate undo. Kills the mutant that swaps the DTO
    comparison for a raw `rec.*` one."""

    def test_undo_create_with_mixed_case_record_names_is_not_a_false_conflict(self, db_session):
        uow = _make_uow(db_session)
        _seed_create_report(
            uow,
            records_data=[
                {
                    "borrower_name": "  Alice SMITH ",
                    "borrower_group": " BG One",
                    "depositor_name": "  Bob JONES ",
                    "depositor_group": " DG ",
                    "amount": 15000,
                    "post_extension_giving_date": date(2026, 4, 10),
                    "post_extension_due_date": date(2026, 7, 10),
                    "due_period": 3,
                }
            ],
        )
        uow.commit()

        create_clock = FixedClock(date(2026, 4, 10))
        approver, _, uow_factory = _approver(db_session, clock=create_clock)
        result = approver.execute("RPT_20260410_001")
        assert result.success is True

        fresh = _make_uow(db_session)
        report = fresh.reports.get_by_report_id("RPT_20260410_001")
        minted_ref = report.records[0].reference_id
        loan = fresh.loans.get_by_reference_id(minted_ref)
        # CreateLoan.stage() normalised the record through the same
        # LoanCreateDTO validators -- already lowercase/stripped.
        assert loan.borrower_name == "alice smith"
        assert loan.borrower_group == "bg one"
        assert loan.depositor_name == "bob jones"
        assert loan.depositor_group == "dg"

        undoer = _undoer(uow_factory, clock=create_clock)
        undo_result = undoer.execute("RPT_20260410_001")

        assert undo_result.success is True
        final = _make_uow(db_session)
        assert final.loans.get_by_reference_id(minted_ref).is_active is False


class TestUndoCreateReportRefusedWhenMintedLoanAmountEditedSince:
    def test_undo_create_report_refused_when_minted_loan_amount_edited_since(self, db_session):
        uow = _make_uow(db_session)
        _seed_create_report(uow)
        uow.commit()

        create_clock = FixedClock(date(2026, 4, 10))
        approver, _, uow_factory = _approver(db_session, clock=create_clock)
        approver.execute("RPT_20260410_001")

        fresh = _make_uow(db_session)
        report = fresh.reports.get_by_report_id("RPT_20260410_001")
        minted_ref = report.records[0].reference_id

        UpdateLoan(uow_factory).execute(minted_ref, LoanUpdateDTO(amount=99999))

        undoer = _undoer(uow_factory, clock=create_clock)
        result = undoer.execute("RPT_20260410_001")

        assert result.success is False
        assert result.reason == "changed_since_approval"
        assert result.conflict_ref_ids == [minted_ref]

        final = _make_uow(db_session)
        loan = final.loans.get_by_reference_id(minted_ref)
        assert loan.is_active is True
        assert int(loan.amount) == 99999


class TestUndoCreateReportRefusedWhenMintedLoanDueDateOnlyEditedSince:
    """Also the dedicated kill-test for mutant M8 (`_create_conflicts`
    reduced to comparing `giving_date` only): giving_date is left untouched
    here, so only a due_date-aware compare can catch this edit."""

    def test_undo_create_report_refused_when_minted_loan_due_date_edited_since(self, db_session):
        uow = _make_uow(db_session)
        _seed_create_report(uow)
        uow.commit()

        create_clock = FixedClock(date(2026, 4, 10))
        approver, _, uow_factory = _approver(db_session, clock=create_clock)
        approver.execute("RPT_20260410_001")

        fresh = _make_uow(db_session)
        report = fresh.reports.get_by_report_id("RPT_20260410_001")
        minted_ref = report.records[0].reference_id
        original = fresh.loans.get_by_reference_id(minted_ref)
        assert original.giving_date == date(2026, 4, 10)

        UpdateLoan(uow_factory).execute(
            minted_ref, LoanUpdateDTO(due_date=date(2026, 12, 1))
        )

        undoer = _undoer(uow_factory, clock=create_clock)
        result = undoer.execute("RPT_20260410_001")

        assert result.success is False
        assert result.reason == "changed_since_approval"
        assert result.conflict_ref_ids == [minted_ref]

        final = _make_uow(db_session)
        loan = final.loans.get_by_reference_id(minted_ref)
        assert loan.is_active is True
        assert loan.giving_date == date(2026, 4, 10)
        assert loan.due_date == date(2026, 12, 1)


# ---------------------------------------------------------------------------
# Review cycle 1, MAJOR-2: one named test per surviving mutant (M4, M6, M7,
# M9, M14 below; M8 is killed by the due_date-only test right above it).
# ---------------------------------------------------------------------------


class TestUndoLeavesLoanOfRecordSkippedAtApprovalUntouched:
    """MAJOR-2 primary test -- kills M4 (restore loop iterates
    `report.records` instead of `_applied_extend_records`). A 2-record
    MONTHLY report where the second record's `post_extension_due_date` is
    None is skipped by approval (never gets its dates written); undo must
    apply the SAME skip, or it clobbers the loan's true CURRENT dates
    (edited after approval, unrelated to this report) with the stale
    generation snapshot."""

    def test_undo_leaves_loan_of_record_skipped_at_approval_untouched(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(
            uow, ref_id="2026_03_101",
            giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
            status=LoanStatus.OVERDUE,
        )
        _seed_loan(
            uow, ref_id="2026_03_102",
            giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
            status=LoanStatus.OVERDUE,
        )
        _seed_report(
            uow,
            "RPT_20260315_930",
            records_data=[
                {
                    "reference_id": "2026_03_101",
                    "giving_date": date(2026, 1, 1),
                    "due_date": date(2026, 4, 1),
                    "post_extension_giving_date": date(2026, 4, 1),
                    "post_extension_due_date": date(2026, 7, 1),
                },
                {
                    # Skipped at approval: post_extension_due_date is None.
                    "reference_id": "2026_03_102",
                    "giving_date": date(2026, 1, 1),
                    "due_date": date(2026, 4, 1),
                    "post_extension_giving_date": date(2026, 4, 1),
                    "post_extension_due_date": None,
                },
            ],
        )
        uow.commit()

        approver, _, uow_factory = _approver(db_session)
        result = approver.execute("RPT_20260315_930")
        assert result.success is True

        fresh = _make_uow(db_session)
        applied = fresh.loans.get_by_reference_id("2026_03_101")
        skipped = fresh.loans.get_by_reference_id("2026_03_102")
        assert (applied.giving_date, applied.due_date) == (date(2026, 4, 1), date(2026, 7, 1))
        # Untouched by approval (skipped) -- still its original dates.
        assert (skipped.giving_date, skipped.due_date) == (date(2026, 1, 1), date(2026, 4, 1))

        # An UNRELATED edit to the skipped loan, made any time after
        # approval -- undo must never see or overwrite this.
        UpdateLoan(uow_factory).execute(
            "2026_03_102", LoanUpdateDTO(giving_date=date(2026, 2, 1))
        )

        undoer = _undoer(uow_factory)
        undo_result = undoer.execute("RPT_20260315_930")
        assert undo_result.success is True

        final = _make_uow(db_session)
        applied2 = final.loans.get_by_reference_id("2026_03_101")
        skipped2 = final.loans.get_by_reference_id("2026_03_102")
        assert (applied2.giving_date, applied2.due_date) == (date(2026, 1, 1), date(2026, 4, 1))
        # The skipped loan keeps the edit -- undo must never have touched it.
        assert skipped2.giving_date == date(2026, 2, 1)
        assert skipped2.due_date == date(2026, 4, 1)


class TestUndoRefusesWholeBatchWithTwoConflictingLoans:
    """Kills M6 (extend conflict loop `break`s at the first conflict instead
    of checking every record) -- also doubles as the dedicated M14 test
    (`sorted(conflicts, reverse=True)`): the expected list is asserted in
    ascending order, so a reversed result fails the same assertion."""

    def test_undo_refuses_whole_batch_with_two_conflicting_loans_lists_both(self, db_session):
        uow = _make_uow(db_session)
        _seed_loan(uow, ref_id="2026_03_201")
        _seed_loan(uow, ref_id="2026_03_202")
        _seed_report(
            uow,
            "RPT_20260315_940",
            records_data=[
                {
                    "reference_id": "2026_03_201",
                    "post_extension_giving_date": date(2026, 4, 1),
                    "post_extension_due_date": date(2026, 7, 1),
                },
                {
                    "reference_id": "2026_03_202",
                    "post_extension_giving_date": date(2026, 4, 1),
                    "post_extension_due_date": date(2026, 7, 1),
                },
            ],
        )
        uow.commit()

        approver, _, uow_factory = _approver(db_session)
        result = approver.execute("RPT_20260315_940")
        assert result.success is True

        # Both loans edited after approval -- both must conflict.
        UpdateLoan(uow_factory).execute(
            "2026_03_201", LoanUpdateDTO(due_date=date(2026, 12, 1))
        )
        UpdateLoan(uow_factory).execute(
            "2026_03_202", LoanUpdateDTO(due_date=date(2026, 12, 2))
        )

        undoer = _undoer(uow_factory)
        undo_result = undoer.execute("RPT_20260315_940")

        assert undo_result.success is False
        assert undo_result.reason == "changed_since_approval"
        assert undo_result.conflict_ref_ids == ["2026_03_201", "2026_03_202"]


class TestUndoCreateReportRefusedWhenMintedLoanPaidOffSince:
    """Kills M7 (`_create_conflicts` drops the `not loan.is_active` check) --
    the CREATE-mode sibling of TestUndoRefusesWhenLoanPaidOffSinceApproval,
    which only exercises the EXTEND branch."""

    def test_undo_create_report_refused_when_minted_loan_paid_off_since(self, db_session):
        uow = _make_uow(db_session)
        _seed_create_report(uow)
        uow.commit()

        create_clock = FixedClock(date(2026, 4, 10))
        approver, _, uow_factory = _approver(db_session, clock=create_clock)
        approver.execute("RPT_20260410_001")

        fresh = _make_uow(db_session)
        report = fresh.reports.get_by_report_id("RPT_20260410_001")
        minted_ref = report.records[0].reference_id

        mid_uow = _make_uow(db_session)
        mid_uow.loans.set_inactive(minted_ref)
        mid_uow.commit()

        undoer = _undoer(uow_factory, clock=create_clock)
        result = undoer.execute("RPT_20260410_001")

        assert result.success is False
        assert result.reason == "changed_since_approval"
        assert result.conflict_ref_ids == [minted_ref]


class TestUndoCreateReportWithMultipleRecordsDeactivatesAll:
    """Kills M9 (`_undo_create` deactivates only `report.records[:1]`)."""

    def test_undo_create_report_with_multiple_records_deactivates_all(self, db_session):
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

        create_clock = FixedClock(date(2026, 4, 10))
        approver, _, uow_factory = _approver(db_session, clock=create_clock)
        result = approver.execute("RPT_20260410_001")
        assert result.success is True

        fresh = _make_uow(db_session)
        report = fresh.reports.get_by_report_id("RPT_20260410_001")
        minted_refs = [r.reference_id for r in report.records]
        assert len(minted_refs) == 3

        undoer = _undoer(uow_factory, clock=create_clock)
        undo_result = undoer.execute("RPT_20260410_001")
        assert undo_result.success is True

        final = _make_uow(db_session)
        for ref in minted_refs:
            loan = final.loans.get_by_reference_id(ref)
            assert loan.is_active is False, f"{ref} must be deactivated by undo"
