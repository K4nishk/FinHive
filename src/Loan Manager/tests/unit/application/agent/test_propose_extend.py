"""Unit tests for propose_extend.py (KCH-243): ExtendLoanTool and
ExtendOverdueBatchTool -- PROPOSE only, never a loan write (see
test_propose_no_loan_write.py for the dedicated guard)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from loan_manager.application.agent.tools import args as args_mod
from loan_manager.application.agent.tools.propose_common import ProposalContext
from loan_manager.application.agent.tools.propose_extend import (
    ExtendLoanTool,
    ExtendOverdueBatchTool,
)
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.application.use_cases.reports.calculate_interest import (
    CalculateInterest,
)
from loan_manager.application.use_cases.reports.generate_report import GenerateReport
from loan_manager.application.use_cases.reports.get_reports import GetPendingReports
from loan_manager.domain.value_objects.status import CalculationMode, ReportActor

from .conftest import assert_no_npi_leak, make_loan, uow_factory_for

# Matches demo_fixture.FIXTURE_TODAY so the sharma-group fixtures below
# (copied verbatim from demo_fixture.py's own dates) reproduce the demo's
# own documented overdue set (rakesh, vikram) without redoing that maths.
_TODAY = date(2026, 9, 25)
_CTX = ProposalContext(user_request="extend it please")


def _build_extend(loans, reports_store=None):
    reports_store = reports_store if reports_store is not None else []
    uow_factory = uow_factory_for(loans, reports_store)
    clock = FixedClock(_TODAY)
    tool = ExtendLoanTool(
        GetAllLoans(uow_factory, clock=clock),
        GetPendingReports(uow_factory),
        GenerateReport(uow_factory, EventBus()),
        clock,
        _CTX,
    )
    return tool, reports_store


def _build_batch(loans, reports_store=None):
    reports_store = reports_store if reports_store is not None else []
    uow_factory = uow_factory_for(loans, reports_store)
    clock = FixedClock(_TODAY)
    get_autocomplete = GetAutocompleteValues(uow_factory)
    tool = ExtendOverdueBatchTool(
        GetAllLoans(uow_factory, clock=clock),
        get_autocomplete,
        BuildEntityResolver(get_autocomplete),
        GetPendingReports(uow_factory),
        CalculateInterest(uow_factory),
        GenerateReport(uow_factory, EventBus()),
        clock,
        _CTX,
    )
    return tool, reports_store


def test_extend_loan_writes_one_agent_report() -> None:
    loan = make_loan(giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1))
    tool, reports_store = _build_extend([loan])

    result = tool.execute(
        args_mod.ExtendLoan(ref_id=str(loan.reference_id), months=3, rate=12)
    )

    assert result["ok"] is True
    assert len(reports_store) == 1
    report = reports_store[0]
    assert report.report_mode == CalculationMode.MONTHLY
    assert report.actor == ReportActor.AGENT
    assert report.user_request == "extend it please"
    assert len(report.records) == 1
    rec = report.records[0]
    assert rec.post_extension_giving_date == date(2026, 4, 1)
    assert rec.post_extension_due_date == date(2026, 7, 1)
    assert_no_npi_leak(result, loan.borrower_name, loan.depositor_name, loan.borrower_group)


def test_extend_undated_rejected_without_new_due_date() -> None:
    loan = make_loan(giving_date=date(2026, 1, 1), due_date=None)
    tool, reports_store = _build_extend([loan])

    result = tool.execute(
        args_mod.ExtendLoan(ref_id=str(loan.reference_id), months=3, rate=12)
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "UNDATED_LOAN"
    assert reports_store == []
    assert_no_npi_leak(result, loan.borrower_name, loan.depositor_name, loan.borrower_group)


def test_extend_undated_with_new_due_date_sets_both_post_dates() -> None:
    loan = make_loan(giving_date=date(2026, 1, 1), due_date=None)
    tool, reports_store = _build_extend([loan])

    result = tool.execute(
        args_mod.ExtendLoan(
            ref_id=str(loan.reference_id), months=3, rate=12, new_due_date="2026-12-01"
        )
    )

    assert result["ok"] is True
    rec = reports_store[0].records[0]
    assert rec.post_extension_giving_date == _TODAY
    assert rec.post_extension_due_date == date(2026, 12, 1)


@pytest.mark.parametrize(
    "new_due_date",
    ["2026-06-01", "2026-09-25"],  # strictly before today, and == today (boundary)
    ids=["before-today", "equal-to-today"],
)
def test_new_due_date_not_after_today_rejected(new_due_date: str) -> None:
    """Review cycle 1, MINOR-4 (M4, ORCHESTRATOR RULING): `new_due_date` is
    required to be STRICTLY after today (`<=` rejects), so `new_due_date ==
    today` must be rejected exactly like a date in the past -- a `<=` -> `<`
    typo would let a same-day "extension" through."""
    loan = make_loan(giving_date=date(2026, 1, 1), due_date=None)
    tool, reports_store = _build_extend([loan])

    result = tool.execute(
        args_mod.ExtendLoan(
            ref_id=str(loan.reference_id), months=3, rate=12, new_due_date=new_due_date
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "NEW_DUE_DATE_INVALID"
    assert reports_store == []


def test_new_due_date_on_dated_loan_rejected() -> None:
    loan = make_loan(giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1))
    tool, reports_store = _build_extend([loan])

    result = tool.execute(
        args_mod.ExtendLoan(
            ref_id=str(loan.reference_id), months=3, rate=12, new_due_date="2026-09-01"
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "NEW_DUE_DATE_INVALID"
    assert reports_store == []


def test_extend_unknown_ref() -> None:
    tool, reports_store = _build_extend([])

    result = tool.execute(args_mod.ExtendLoan(ref_id="2026_03_999", months=3, rate=12))

    assert result["ok"] is False
    assert result["error"]["code"] == "REF_ID_NOT_FOUND"
    assert reports_store == []


def test_extend_already_pending_rejected() -> None:
    loan = make_loan(giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1))
    tool, reports_store = _build_extend([loan])
    # A pending report already names this ref_id.
    first = tool.execute(
        args_mod.ExtendLoan(ref_id=str(loan.reference_id), months=3, rate=12)
    )
    assert first["ok"] is True
    assert len(reports_store) == 1

    second = tool.execute(
        args_mod.ExtendLoan(ref_id=str(loan.reference_id), months=2, rate=10)
    )

    assert second["ok"] is False
    assert second["error"]["code"] == "ALREADY_PENDING"
    assert len(reports_store) == 1  # no second report written


def test_extend_tds_flag_computes_tds_and_chq() -> None:
    """Review cycle 1, MINOR-4 (M12, ORCHESTRATOR RULING): tds_flag=True
    must actually compute TDS (10% of interest, CLAUDE.md) and CHQ
    (interest - TDS) on the proposed record -- a stubbed `if False` in
    their place would silently always price TDS at zero."""
    loan = make_loan(amount=100000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1))
    tool, reports_store = _build_extend([loan])

    result = tool.execute(
        args_mod.ExtendLoan(
            ref_id=str(loan.reference_id), months=3, rate=12, tds_flag=True
        )
    )

    assert result["ok"] is True, result
    rec = reports_store[0].records[0]
    # interest = 100000 * 12 * 3 / 1200 = 3000.00
    assert rec.interest_amount == Decimal("3000.00")
    assert rec.tds_flag is True
    assert rec.tds_amount == Decimal("300.00")  # 10% of interest
    assert rec.chq_amount == Decimal("2700.00")  # interest - tds


# ── ExtendOverdueBatchTool ──────────────────────────────────────────────────


def _sharma_loans():
    return [
        make_loan(  # overdue
            borrower_name="rakesh sharma", borrower_group="sharma group",
            depositor_name="meera iyer", depositor_group="chennai circle",
            giving_date=date(2026, 4, 10), due_date=date(2026, 7, 10),
        ),
        make_loan(  # active
            borrower_name="sunita sharma", borrower_group="sharma group",
            depositor_name="arjun rao", depositor_group="chennai circle",
            giving_date=date(2026, 6, 1), due_date=date(2026, 12, 1),
        ),
        make_loan(  # overdue
            borrower_name="vikram sharma", borrower_group="sharma group",
            depositor_name="meera iyer", depositor_group="chennai circle",
            giving_date=date(2026, 2, 15), due_date=date(2026, 8, 15),
        ),
        make_loan(  # active
            borrower_name="anil sharma", borrower_group="sharma group",
            depositor_name="kavita nair", depositor_group=None,
            giving_date=date(2026, 8, 20), due_date=date(2027, 2, 20),
        ),
    ]


def _all_npi(loans):
    out = []
    for loan in loans:
        out += [loan.borrower_name, loan.depositor_name, loan.borrower_group]
        if loan.depositor_group:
            out.append(loan.depositor_group)
    return out


def test_batch_one_report_n_overdue_items() -> None:
    """ACCEPTANCE-shape (matches the demo fixture): sharma group has 4
    active loans; StatusEngine says exactly rakesh and vikram are OVERDUE at
    the fixed today -- ONE report, N=2 items."""
    loans = _sharma_loans()
    tool, reports_store = _build_batch(loans)

    result = tool.execute(
        args_mod.ExtendOverdueBatch(borrower_group="sharma group", months=1, rate=12)
    )

    assert result["ok"] is True, result
    assert result["item_count"] == 2
    assert len(reports_store) == 1
    assert len(reports_store[0].records) == 2
    assert reports_store[0].report_mode == CalculationMode.MONTHLY
    assert reports_store[0].actor == ReportActor.AGENT
    assert_no_npi_leak(result, *_all_npi(loans))


def test_batch_skips_pending() -> None:
    """Review cycle 1, MINOR-4 (M7, ORCHESTRATOR RULING): a loan already
    named by another PENDING report must be excluded from the batch and
    listed in `skipped_pending` -- an empty already_pending set would
    silently propose a SECOND, conflicting change over the first."""
    loans = _sharma_loans()
    reports_store: list = []
    rakesh_ref = str(loans[0].reference_id)

    single_tool, _ = _build_extend(loans, reports_store)
    pre_pending = single_tool.execute(
        args_mod.ExtendLoan(ref_id=rakesh_ref, months=1, rate=12)
    )
    assert pre_pending["ok"] is True
    assert len(reports_store) == 1

    batch_tool, _ = _build_batch(loans, reports_store)
    result = batch_tool.execute(
        args_mod.ExtendOverdueBatch(borrower_group="sharma group", months=1, rate=12)
    )

    assert result["ok"] is True, result
    assert result["item_count"] == 1  # vikram only -- rakesh already pending
    assert result["skipped_pending"] == [rakesh_ref]
    assert rakesh_ref not in {item["ref_id"] for item in result["items"]}
    assert len(reports_store) == 2  # rakesh's single report, plus vikram's batch report


def test_batch_uses_months_for_interest_and_dates() -> None:
    """Review cycle 1, MINOR-4 (M21, ORCHESTRATOR RULING): the batch must
    use `args.months` for BOTH the proposed new due dates AND the interest
    calculation -- a hardcoded `1` in either place would silently mis-price
    or mis-date every item whenever the caller asks for a different span."""
    loans = _sharma_loans()
    tool, reports_store = _build_batch(loans)

    result = tool.execute(
        args_mod.ExtendOverdueBatch(borrower_group="sharma group", months=3, rate=12)
    )

    assert result["ok"] is True, result
    assert result["item_count"] == 2
    by_ref = {item["ref_id"]: item for item in result["items"]}
    rakesh_ref, vikram_ref = str(loans[0].reference_id), str(loans[2].reference_id)
    # amount=10000 (make_loan default) x rate=12 x months=3 / 1200 = 300.00
    assert by_ref[rakesh_ref]["new_due_date"] == "2026-10-10"  # 2026-07-10 + 3m
    assert Decimal(by_ref[rakesh_ref]["interest"]) == Decimal("300.00")
    assert by_ref[vikram_ref]["new_due_date"] == "2026-11-15"  # 2026-08-15 + 3m
    assert Decimal(by_ref[vikram_ref]["interest"]) == Decimal("300.00")
    # months=1 (the default elsewhere in this file) would give 100.00 instead
    # -- pin the non-trivial 300.00 so a hardcoded `1` cannot pass by accident.
    assert Decimal(by_ref[rakesh_ref]["interest"]) != Decimal("100.00")
    for rec in reports_store[0].records:
        assert rec.extension_period == 3


def test_batch_status_from_engine_not_column() -> None:
    """A loan whose STORED status column disagrees with what StatusEngine
    derives from its dates must still be filtered by the derived status --
    CLAUDE.md: never read loans.status in agent tools."""
    from loan_manager.domain.value_objects.status import LoanStatus

    loans = [
        make_loan(
            borrower_group="sharma group",
            giving_date=date(2026, 1, 1), due_date=date(2026, 3, 1),  # overdue by date
            status=LoanStatus.ACTIVE,  # stale/lying persisted column
        ),
    ]
    tool, reports_store = _build_batch(loans)

    result = tool.execute(
        args_mod.ExtendOverdueBatch(borrower_group="sharma group", months=1, rate=12)
    )

    assert result["ok"] is True
    assert result["item_count"] == 1


def test_batch_group_separator_variant_resolves_via_resolver() -> None:
    """"sharma-group" (hyphen) is not literally in the known-value set
    (which holds the stored "sharma group", space), but EntityResolver's
    own normalisation folds separators to space and matches it exactly --
    `resolve_group`'s resolver path (not its known-set fast path) must
    accept it."""
    loans = [
        make_loan(
            borrower_group="sharma group",
            giving_date=date(2026, 1, 1), due_date=date(2026, 3, 1),
        ),
    ]
    tool, reports_store = _build_batch(loans)

    result = tool.execute(
        args_mod.ExtendOverdueBatch(borrower_group="sharma-group", months=1, rate=12)
    )

    assert result["ok"] is True, result
    assert result["item_count"] == 1


def test_batch_undated_excluded_and_listed() -> None:
    loans = [
        make_loan(  # overdue, dated
            borrower_group="sharma group",
            giving_date=date(2026, 1, 1), due_date=date(2026, 3, 1),
        ),
        make_loan(  # overdue, undated -- deepak-menon-style trap
            borrower_group="sharma group",
            giving_date=date(2026, 1, 1), due_date=None,
        ),
    ]
    undated_ref = str(loans[1].reference_id)
    tool, reports_store = _build_batch(loans)

    result = tool.execute(
        args_mod.ExtendOverdueBatch(borrower_group="sharma group", months=1, rate=12)
    )

    assert result["ok"] is True
    assert result["item_count"] == 1
    assert result["skipped_undated"] == [undated_ref]
    assert len(reports_store) == 1
    assert len(reports_store[0].records) == 1


def test_batch_all_undated_nothing_to_propose_no_report() -> None:
    loans = [
        make_loan(borrower_group="sharma group", giving_date=date(2026, 1, 1), due_date=None),
    ]
    tool, reports_store = _build_batch(loans)

    result = tool.execute(
        args_mod.ExtendOverdueBatch(borrower_group="sharma group", months=1, rate=12)
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "NOTHING_TO_PROPOSE"
    assert reports_store == []


def test_batch_non_exact_group_asks_confirm_no_report() -> None:
    loans = _sharma_loans()
    tool, reports_store = _build_batch(loans)

    # "sharma" alone is a fuzzy, non-exact match for the group "sharma
    # group" (a real borrower_name token also matches "sharma"), so the
    # resolver must not silently pick one -- CONFIRM_REQUIRED, no report.
    result = tool.execute(
        args_mod.ExtendOverdueBatch(borrower_group="sharma", months=1, rate=12)
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "CONFIRM_REQUIRED"
    assert reports_store == []
    assert_no_npi_leak(result, *_all_npi(loans))


def test_batch_unknown_group_unresolved_no_report() -> None:
    loans = _sharma_loans()
    tool, reports_store = _build_batch(loans)

    result = tool.execute(
        args_mod.ExtendOverdueBatch(borrower_group="totally unknown group", months=1, rate=12)
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "UNRESOLVED_ENTITY"
    assert reports_store == []
    assert_no_npi_leak(result, *_all_npi(loans))
