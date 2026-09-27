"""SqlAlchemyReportRepository unit tests for the KCH-242 additions:
actor/user_request/turn_id round-trip through the ORM mapping, a CREATE-mode
record's nullable reference_id/giving_date, `assign_reference_id`, and
`get_pending_reference_ids` filtering out CREATE-mode NULLs.

Uses the `db_session` fixture (in-memory SQLite, `Base.metadata.create_all`)
and the autouse test key ring from `tests/conftest.py` -- real
encrypt/decrypt round-trips through the ORM, no mocking of the encrypted
columns.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from loan_manager.domain.entities.report import Report, ReportRecord
from loan_manager.domain.value_objects.report_id import ReportId
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    ReportActor,
    ReportStatus,
)
from loan_manager.infrastructure.repositories.sqlalchemy_report_repo import (
    SqlAlchemyReportRepository,
)

_NOW = datetime(2026, 3, 15, 12, 0, 0)


def _create_record(**overrides) -> ReportRecord:
    fields = dict(
        id=None,
        report_id="RPT_20260315_001",
        reference_id=None,
        borrower_name="new borrower",
        depositor_name="depositor",
        depositor_group=None,
        amount=10000,
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
        post_extension_giving_date=date(2026, 4, 1),
        post_extension_due_date=date(2026, 7, 1),
        paidoff_date=None,
        borrower_group="new-group",
        due_period=3,
    )
    fields.update(overrides)
    return ReportRecord(**fields)


class TestActorUserRequestTurnIdRoundTrip:
    def test_form_report_round_trips_default_actor_with_no_prompt(self, db_session):
        repo = SqlAlchemyReportRepository(db_session)
        report = Report(
            id=None,
            report_id=ReportId("RPT_20260315_001"),
            report_mode=CalculationMode.CREATE,
            status=ReportStatus.PENDING,
            records=[_create_record()],
            created_at=_NOW,
            updated_at=_NOW,
        )
        repo.save(report)
        db_session.commit()

        fresh = SqlAlchemyReportRepository(db_session).get_by_report_id("RPT_20260315_001")
        assert fresh.actor == ReportActor.FORM
        assert fresh.user_request is None
        assert fresh.turn_id is None

    def test_agent_report_round_trips_actor_user_request_and_turn_id(self, db_session):
        repo = SqlAlchemyReportRepository(db_session)
        report = Report(
            id=None,
            report_id=ReportId("RPT_20260315_002"),
            report_mode=CalculationMode.CREATE,
            status=ReportStatus.PENDING,
            records=[_create_record(report_id="RPT_20260315_002")],
            created_at=_NOW,
            updated_at=_NOW,
            actor=ReportActor.AGENT,
            user_request="add a new loan for ravindra of 10000",
            turn_id="turn-abc-123",
        )
        repo.save(report)
        db_session.commit()

        fresh = SqlAlchemyReportRepository(db_session).get_by_report_id("RPT_20260315_002")
        assert fresh.actor == ReportActor.AGENT
        assert fresh.user_request == "add a new loan for ravindra of 10000"
        assert fresh.turn_id == "turn-abc-123"


class TestCreateModeRecordRoundTrip:
    def test_create_record_round_trips_null_reference_id_and_giving_date(self, db_session):
        repo = SqlAlchemyReportRepository(db_session)
        report = Report(
            id=None,
            report_id=ReportId("RPT_20260315_003"),
            report_mode=CalculationMode.CREATE,
            status=ReportStatus.PENDING,
            records=[_create_record(report_id="RPT_20260315_003")],
            created_at=_NOW,
            updated_at=_NOW,
        )
        repo.save(report)
        db_session.commit()

        fresh = SqlAlchemyReportRepository(db_session).get_by_report_id("RPT_20260315_003")
        record = fresh.records[0]
        assert record.reference_id is None
        assert record.giving_date is None
        assert record.borrower_group == "new-group"
        assert record.due_period == 3


class TestAssignReferenceId:
    def test_assign_reference_id_sets_it_on_the_named_record(self, db_session):
        """Mirrors ApproveReport's own sequencing (KCH-242): assign_reference_id
        runs per record, THEN mark_approved once, before any read-back --
        Report.__post_init__ forbids a Pending CREATE record from already
        carrying a reference_id, so reading back in between (as opposed to
        after mark_approved, like here) would be asserting an intermediate
        state production code never actually re-reads through the entity
        mapper.
        """
        repo = SqlAlchemyReportRepository(db_session)
        report = Report(
            id=None,
            report_id=ReportId("RPT_20260315_004"),
            report_mode=CalculationMode.CREATE,
            status=ReportStatus.PENDING,
            records=[_create_record(report_id="RPT_20260315_004")],
            created_at=_NOW,
            updated_at=_NOW,
        )
        saved = repo.save(report)
        db_session.commit()
        record_id = saved.records[0].id

        repo.assign_reference_id(record_id, "2026_03_007")
        repo.mark_approved("RPT_20260315_004")
        db_session.commit()

        fresh = SqlAlchemyReportRepository(db_session).get_by_report_id("RPT_20260315_004")
        assert fresh.records[0].reference_id == "2026_03_007"
        assert fresh.status == ReportStatus.APPROVED


class TestGetPendingReferenceIdsFiltersNull:
    def test_create_records_reference_id_none_is_excluded(self, db_session):
        repo = SqlAlchemyReportRepository(db_session)
        # A CREATE report (reference_id=None) and a normal report (a real
        # reference_id) both Pending -- only the real one may appear.
        repo.save(
            Report(
                id=None,
                report_id=ReportId("RPT_20260315_005"),
                report_mode=CalculationMode.CREATE,
                status=ReportStatus.PENDING,
                records=[_create_record(report_id="RPT_20260315_005")],
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        repo.save(
            Report(
                id=None,
                report_id=ReportId("RPT_20260315_006"),
                report_mode=CalculationMode.MONTHLY,
                status=ReportStatus.PENDING,
                records=[
                    ReportRecord(
                        id=None,
                        report_id="RPT_20260315_006",
                        reference_id="2026_03_099",
                        borrower_name="borrower",
                        depositor_name="depositor",
                        depositor_group=None,
                        amount=10000,
                        giving_date=date(2026, 1, 1),
                        due_date=date(2026, 4, 1),
                        extension_period=3,
                        extension_period_unit=ExtensionPeriodUnit.MONTHS,
                        interest_rate=Decimal("12"),
                        commission_rate=Decimal("6"),
                        tds_flag=False,
                        interest_amount=None,
                        commission_amount=None,
                        tds_amount=None,
                        chq_amount=None,
                        post_extension_giving_date=date(2026, 4, 1),
                        post_extension_due_date=date(2026, 7, 1),
                        paidoff_date=None,
                    )
                ],
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        db_session.commit()

        pending = repo.get_pending_reference_ids()

        assert None not in pending
        assert pending == {"2026_03_099"}
