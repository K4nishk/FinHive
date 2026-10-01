"""KCH-245: GetRecentlyApprovedReports backs the approvals tab's Recently
Approved / Undo panel. In-memory SQLite via `db_session`/`uow_factory`,
same as every other file in this directory (see tests/conftest.py)."""
from __future__ import annotations

from datetime import date, datetime

from loan_manager.application.use_cases.reports.get_recent_approved_reports import (
    GetRecentlyApprovedReports,
)
from loan_manager.domain.entities.report import Report, ReportRecord
from loan_manager.domain.value_objects.report_id import ReportId
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    ReportActor,
    ReportStatus,
)
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork


def _make_uow(session):
    return SqlAlchemyUnitOfWork(session)


def _record(report_id_str, ref_id="2026_03_001") -> ReportRecord:
    from decimal import Decimal
    return ReportRecord(
        id=None,
        report_id=report_id_str,
        reference_id=ref_id,
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
        post_extension_giving_date=date(2026, 4, 1),
        post_extension_due_date=date(2026, 7, 1),
        paidoff_date=None,
    )


def _seed(
    uow, report_id_str, status, updated_at, ref_id="2026_03_001",
    actor=ReportActor.FORM, user_request=None, turn_id=None,
):
    report = Report(
        id=None,
        report_id=ReportId(report_id_str),
        report_mode=CalculationMode.MONTHLY,
        status=status,
        records=[_record(report_id_str, ref_id)],
        created_at=updated_at,
        updated_at=updated_at,
        actor=actor,
        user_request=user_request,
        turn_id=turn_id,
    )
    return uow.reports.save(report)


class TestOnlyApprovedReturned:
    def test_only_approved_reports_are_returned(self, db_session):
        uow = _make_uow(db_session)
        _seed(uow, "RPT_20260301_001", ReportStatus.PENDING, datetime(2026, 3, 1))
        _seed(uow, "RPT_20260302_001", ReportStatus.APPROVED, datetime(2026, 3, 2))
        _seed(uow, "RPT_20260303_001", ReportStatus.DECLINED, datetime(2026, 3, 3))
        _seed(uow, "RPT_20260304_001", ReportStatus.REVERTED, datetime(2026, 3, 4))
        uow.commit()

        def uow_factory():
            return _make_uow(db_session)

        result = GetRecentlyApprovedReports(uow_factory).execute(limit=20)

        assert [r.report_id for r in result] == ["RPT_20260302_001"]
        assert result[0].status == ReportStatus.APPROVED


class TestOrderedNewestFirst:
    def test_ordered_newest_first_by_updated_at(self, db_session):
        uow = _make_uow(db_session)
        _seed(uow, "RPT_20260301_001", ReportStatus.APPROVED, datetime(2026, 3, 1, 9, 0))
        _seed(uow, "RPT_20260303_001", ReportStatus.APPROVED, datetime(2026, 3, 3, 9, 0))
        _seed(uow, "RPT_20260302_001", ReportStatus.APPROVED, datetime(2026, 3, 2, 9, 0))
        uow.commit()

        def uow_factory():
            return _make_uow(db_session)

        result = GetRecentlyApprovedReports(uow_factory).execute(limit=20)

        assert [r.report_id for r in result] == [
            "RPT_20260303_001", "RPT_20260302_001", "RPT_20260301_001",
        ]


class TestLimitCaps:
    def test_limit_caps_to_the_most_recent(self, db_session):
        uow = _make_uow(db_session)
        for day in range(1, 6):
            _seed(
                uow, f"RPT_202603{day:02d}_001", ReportStatus.APPROVED,
                datetime(2026, 3, day, 9, 0),
            )
        uow.commit()

        def uow_factory():
            return _make_uow(db_session)

        result = GetRecentlyApprovedReports(uow_factory).execute(limit=2)

        assert len(result) == 2
        assert [r.report_id for r in result] == ["RPT_20260305_001", "RPT_20260304_001"]


class TestMapsActorAndUserRequest:
    def test_maps_actor_and_user_request(self, db_session):
        uow = _make_uow(db_session)
        _seed(
            uow, "RPT_20260401_001", ReportStatus.APPROVED, datetime(2026, 4, 1),
            actor=ReportActor.AGENT, user_request="extend ravi's loan", turn_id="turn-9",
        )
        uow.commit()

        def uow_factory():
            return _make_uow(db_session)

        result = GetRecentlyApprovedReports(uow_factory).execute(limit=20)

        assert len(result) == 1
        assert result[0].actor == ReportActor.AGENT
        assert result[0].user_request == "extend ravi's loan"
        assert result[0].turn_id == "turn-9"
