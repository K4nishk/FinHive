"""End-to-end PROPOSE tool tests against the real demo seed (KCH-243).

Reuses `demo_seed.seed` (Ponytail rung 2) over the DEMO_LOANS fixture
(KCH-231) instead of hand-building loans -- the sharma-group overdue set and
the deepak-menon undated trap are exactly the scenarios that fixture already
documents. Expected ref_ids are derived from DEMO_LOANS + StatusEngine here,
never hardcoded, so a future fixture edit cannot silently desync this test
from the data it actually seeds.

Uses the in-memory SQLite `db_session`/`in_memory_engine` fixtures
(`tests/conftest.py`), same as `test_approval_flow.py` and
`test_undo_approved_report.py` -- no Postgres/TEST_DATABASE_URL needed.
"""
from __future__ import annotations

from dateutil.relativedelta import relativedelta
from loan_manager.application.agent.tools import args as args_mod
from loan_manager.application.agent.tools.propose_tools import build_propose_registry
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.reports.approve_report import ApproveReport
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.status import LoanStatus
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from loan_manager.infrastructure.recovery.backup_service import BackupService
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService
from loan_manager.infrastructure.seed import demo_seed
from loan_manager.infrastructure.seed.demo_fixture import DEMO_LOANS, FIXTURE_TODAY
from sqlalchemy.orm import sessionmaker


def _seed(engine, today=FIXTURE_TODAY) -> None:
    # A dedicated sessionmaker/session for `seed()` itself -- it owns and
    # closes this session internally; the test's own `db_session` (bound to
    # the SAME in-memory engine, which SQLAlchemy keeps as one persistent
    # connection for a `:memory:` URL) is untouched by that close.
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    demo_seed.seed(lambda: Session(), today=today)


def _make_uow(session):
    return SqlAlchemyUnitOfWork(session)


def _uow_factory_for(session):
    def factory():
        return _make_uow(session)

    return factory


def _approver(uow_factory, clock):
    recovery = RecoveryService()
    recovery.write = lambda op, data: None
    recovery.clear = lambda: None
    backup = BackupService()
    backup.create_backup = lambda: None
    return ApproveReport(uow_factory, recovery, backup, EventBus(), clock=clock)


def _sharma_overdue_refs(today=FIXTURE_TODAY) -> list[str]:
    return sorted(
        fixture.ref
        for fixture in DEMO_LOANS
        if fixture.borrower_group == "sharma group"
        and StatusEngine.compute(fixture.giving_date, fixture.due_date, today)
        == LoanStatus.OVERDUE
    )


def test_extend_all_overdue_sharma_one_report_n_items(db_session, in_memory_engine) -> None:
    """ACCEPTANCE: sharma group has 4 active demo loans; StatusEngine says
    exactly N are OVERDUE at FIXTURE_TODAY -- extend_overdue_batch proposes
    ONE report covering exactly those N, the loans are untouched until
    approval, and approval moves each one's dates by exactly `months`."""
    _seed(in_memory_engine)
    expected_refs = _sharma_overdue_refs()
    assert expected_refs  # sanity: the fixture still has an overdue sharma set

    uow_factory = _uow_factory_for(db_session)
    clock = FixedClock(FIXTURE_TODAY)

    before = {
        ref: (
            (loan := _make_uow(db_session).loans.get_by_reference_id(ref)).giving_date,
            loan.due_date,
        )
        for ref in expected_refs
    }

    registry = build_propose_registry(
        uow_factory, clock, EventBus(), user_request="extend all overdue sharma group loans"
    )
    result = registry.handler("extend_overdue_batch")(
        args_mod.ExtendOverdueBatch(borrower_group="sharma group", months=1, rate=12)
    )

    assert result["ok"] is True, result
    assert result["item_count"] == len(expected_refs)
    assert sorted(item["ref_id"] for item in result["items"]) == expected_refs

    # Untouched until approval.
    for ref in expected_refs:
        loan = _make_uow(db_session).loans.get_by_reference_id(ref)
        assert (loan.giving_date, loan.due_date) == before[ref]

    approval = _approver(uow_factory, clock).execute(result["report_id"])
    assert approval.success is True

    for ref in expected_refs:
        loan = _make_uow(db_session).loans.get_by_reference_id(ref)
        old_giving, old_due = before[ref]
        assert loan.giving_date == old_due
        assert loan.due_date == old_due + relativedelta(months=1)


def test_sharma_non_exact_confirms_no_report(db_session, in_memory_engine) -> None:
    _seed(in_memory_engine)
    uow_factory = _uow_factory_for(db_session)
    registry = build_propose_registry(
        uow_factory, FixedClock(FIXTURE_TODAY), EventBus(), user_request="extend sharma"
    )

    result = registry.handler("extend_overdue_batch")(
        args_mod.ExtendOverdueBatch(borrower_group="sharma", months=1, rate=12)
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "CONFIRM_REQUIRED"
    assert _make_uow(db_session).reports.get_all_pending() == []


def test_undated_menon_trap_end_to_end(db_session, in_memory_engine) -> None:
    """deepak menon / "menon traders": overdue, no due_date. A batch over
    his (single-member) group must EXCLUDE and report him via
    skipped_undated rather than silently doing nothing useful; extend_loan
    on him directly must refuse without new_due_date, then succeed once one
    is given."""
    _seed(in_memory_engine)
    uow_factory = _uow_factory_for(db_session)
    clock = FixedClock(FIXTURE_TODAY)
    menon = next(f for f in DEMO_LOANS if f.borrower_name == "deepak menon")
    assert menon.due_date is None
    assert StatusEngine.compute(menon.giving_date, menon.due_date, FIXTURE_TODAY) == (
        LoanStatus.OVERDUE
    )

    registry = build_propose_registry(
        uow_factory, clock, EventBus(), user_request="extend menon traders"
    )
    batch_result = registry.handler("extend_overdue_batch")(
        args_mod.ExtendOverdueBatch(borrower_group="menon traders", months=1, rate=12)
    )
    assert batch_result["ok"] is False
    assert batch_result["error"]["code"] == "NOTHING_TO_PROPOSE"
    assert batch_result["error"]["skipped_undated"] == [menon.ref]
    assert _make_uow(db_session).reports.get_all_pending() == []

    rejected = registry.handler("extend_loan")(
        args_mod.ExtendLoan(ref_id=menon.ref, months=1, rate=12)
    )
    assert rejected["ok"] is False
    assert rejected["error"]["code"] == "UNDATED_LOAN"

    accepted = registry.handler("extend_loan")(
        args_mod.ExtendLoan(ref_id=menon.ref, months=1, rate=12, new_due_date="2026-10-15")
    )
    assert accepted["ok"] is True, accepted
    assert accepted["items"][0]["ref_id"] == menon.ref
    assert accepted["items"][0]["new_due_date"] == "2026-10-15"
