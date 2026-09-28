"""Unit tests for propose_update.py (KCH-243): UpdateLoanTool."""
from __future__ import annotations

from datetime import date

from loan_manager.application.agent.tools import args as args_mod
from loan_manager.application.agent.tools.propose_common import ProposalContext
from loan_manager.application.agent.tools.propose_update import UpdateLoanTool
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.application.use_cases.reports.generate_report import GenerateReport
from loan_manager.application.use_cases.reports.get_reports import GetPendingReports
from loan_manager.domain.value_objects.status import CalculationMode, ReportActor

from .conftest import assert_no_npi_leak, make_loan, uow_factory_for

_TODAY = date(2026, 6, 1)
_CTX = ProposalContext(user_request="fix this loan please")


def _build_update(loans, reports_store=None):
    reports_store = reports_store if reports_store is not None else []
    uow_factory = uow_factory_for(loans, reports_store)
    clock = FixedClock(_TODAY)
    get_autocomplete = GetAutocompleteValues(uow_factory)
    tool = UpdateLoanTool(
        GetAllLoans(uow_factory, clock=clock),
        get_autocomplete,
        BuildEntityResolver(get_autocomplete),
        GetPendingReports(uow_factory),
        GenerateReport(uow_factory, EventBus()),
        _CTX,
    )
    return tool, reports_store


def test_update_row_merges_fields() -> None:
    """Only amount is given -- borrower_name/depositor_name in the proposed
    record must come from the loan's CURRENT values, not be lost."""
    loan = make_loan(
        borrower_name="original borrower", depositor_name="original depositor", amount=10000,
    )
    tool, reports_store = _build_update([loan])

    result = tool.execute(args_mod.UpdateLoan(ref_id=str(loan.reference_id), amount=200000))

    assert result["ok"] is True, result
    assert result["changed_fields"] == ["amount"]
    report = reports_store[0]
    assert report.report_mode == CalculationMode.UPDATE
    assert report.actor == ReportActor.AGENT
    rec = report.records[0]
    assert rec.reference_id == str(loan.reference_id)
    assert rec.borrower_name == "original borrower"
    assert rec.depositor_name == "original depositor"
    assert rec.amount == 200000
    assert rec.giving_date == loan.giving_date
    assert rec.due_date == loan.due_date
    assert_no_npi_leak(result, loan.borrower_name, loan.depositor_name, loan.borrower_group)


def test_update_group_mismatch_rejected() -> None:
    # Explicit, non-generic names/groups here (never the "borrower"/
    # "depositor" placeholder defaults) so assert_no_npi_leak's substring
    # scan can't collide with the field-name text ("borrower_group") the
    # observation legitimately carries.
    loan = make_loan(
        borrower_name="ramesh gupta", borrower_group="sharma group", amount=10000,
    )
    other = make_loan(borrower_name="suresh iyer", borrower_group="iyer chem", amount=10000)
    tool, reports_store = _build_update([loan, other])

    result = tool.execute(
        args_mod.UpdateLoan(
            ref_id=str(loan.reference_id), borrower_group="iyer chem", amount=200000
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "GROUP_MISMATCH"
    assert reports_store == []
    assert_no_npi_leak(result, loan.borrower_name, loan.borrower_group, other.borrower_group)


def test_update_group_match_ok() -> None:
    loan = make_loan(borrower_group="sharma group", amount=10000)
    tool, reports_store = _build_update([loan])

    result = tool.execute(
        args_mod.UpdateLoan(
            ref_id=str(loan.reference_id), borrower_group="sharma group", amount=200000
        )
    )

    assert result["ok"] is True, result
    assert len(reports_store) == 1


def test_update_noop_nothing_to_propose() -> None:
    loan = make_loan(
        borrower_name="same borrower", depositor_name="same depositor", amount=10000,
    )
    tool, reports_store = _build_update([loan])

    result = tool.execute(
        args_mod.UpdateLoan(
            ref_id=str(loan.reference_id),
            borrower_name="same borrower",
            amount=10000,
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "NOTHING_TO_PROPOSE"
    assert reports_store == []


def test_update_case_only_name_is_noop() -> None:
    """Review cycle 1, MAJOR-1: every other write path lowercases/strips
    names (LoanCreateDTO/LoanUpdateDTO.to_lowercase) before they ever reach
    the book; update_loan must apply the same normalisation BEFORE the
    no-op comparison, or a pure case change ("Ramesh Gupta" for stored
    "ramesh gupta") is proposed as a real change and, on approval, stores
    mixed case."""
    loan = make_loan(borrower_name="ramesh gupta", amount=10000)
    tool, reports_store = _build_update([loan])

    result = tool.execute(
        args_mod.UpdateLoan(ref_id=str(loan.reference_id), borrower_name="Ramesh Gupta")
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "NOTHING_TO_PROPOSE"
    assert reports_store == []


def test_update_mixed_case_name_change_is_stored_lowercase() -> None:
    """A GENUINE rename must still be proposed, but the proposed record
    already carries the normalised (lowercase/stripped) value -- never the
    raw mixed-case text -- so the eventual approval writes exactly what
    every other write path would. Covers BOTH names (review cycle 2,
    MINOR-2, ORCHESTRATOR RULING): depositor_name shares the exact same
    `_normalize_name` call as borrower_name, but had no test of its own
    (N7/N8 in the reviewer's mutation table)."""
    loan = make_loan(borrower_name="ramesh gupta", depositor_name="arjun rao", amount=10000)
    tool, reports_store = _build_update([loan])

    result = tool.execute(
        args_mod.UpdateLoan(
            ref_id=str(loan.reference_id),
            borrower_name="Lakshmi Iyer-Rao",
            depositor_name="MEERA IYER",
        )
    )

    assert result["ok"] is True, result
    assert sorted(result["changed_fields"]) == ["borrower_name", "depositor_name"]
    rec = reports_store[0].records[0]
    assert rec.borrower_name == "lakshmi iyer-rao"
    assert rec.depositor_name == "meera iyer"


def test_update_case_only_depositor_name_is_noop() -> None:
    """Review cycle 2, MINOR-2 (ORCHESTRATOR RULING, N7/N8): the depositor
    no-op comparison must use the NORMALISED value, exactly like borrower --
    a case-only depositor "rename" must be NOTHING_TO_PROPOSE, not a
    changed_fields=['depositor_name'] false positive."""
    loan = make_loan(depositor_name="arjun rao", amount=10000)
    tool, reports_store = _build_update([loan])

    result = tool.execute(
        args_mod.UpdateLoan(ref_id=str(loan.reference_id), depositor_name="Arjun Rao")
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "NOTHING_TO_PROPOSE"
    assert reports_store == []


def test_update_unresolved_group_rejected() -> None:
    loan = make_loan(borrower_name="ramesh gupta", borrower_group="sharma group", amount=10000)
    tool, reports_store = _build_update([loan])

    result = tool.execute(
        args_mod.UpdateLoan(
            ref_id=str(loan.reference_id), borrower_group="totally unknown group", amount=200000
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "UNRESOLVED_ENTITY"
    assert reports_store == []


def test_update_borrower_and_depositor_name_changes_both_listed() -> None:
    loan = make_loan(
        borrower_name="original borrower", depositor_name="original depositor", amount=10000,
    )
    tool, reports_store = _build_update([loan])

    result = tool.execute(
        args_mod.UpdateLoan(
            ref_id=str(loan.reference_id),
            borrower_name="new borrower name",
            depositor_name="new depositor name",
        )
    )

    assert result["ok"] is True, result
    assert sorted(result["changed_fields"]) == ["borrower_name", "depositor_name"]
    rec = reports_store[0].records[0]
    assert rec.borrower_name == "new borrower name"
    assert rec.depositor_name == "new depositor name"
    assert rec.amount == 10000  # unchanged, merged from the loan's current value


def test_update_unknown_ref() -> None:
    tool, reports_store = _build_update([])

    result = tool.execute(args_mod.UpdateLoan(ref_id="2026_03_999", amount=200000))

    assert result["ok"] is False
    assert result["error"]["code"] == "REF_ID_NOT_FOUND"
    assert reports_store == []


def test_update_already_pending_rejected() -> None:
    loan = make_loan(amount=10000)
    tool, reports_store = _build_update([loan])
    first = tool.execute(args_mod.UpdateLoan(ref_id=str(loan.reference_id), amount=200000))
    assert first["ok"] is True

    second = tool.execute(args_mod.UpdateLoan(ref_id=str(loan.reference_id), amount=300000))

    assert second["ok"] is False
    assert second["error"]["code"] == "ALREADY_PENDING"
    assert len(reports_store) == 1
