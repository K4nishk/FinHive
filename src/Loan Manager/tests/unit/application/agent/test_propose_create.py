"""Unit tests for propose_create.py (KCH-243): CreateLoanTool."""
from __future__ import annotations

from datetime import date

from loan_manager.application.agent.tools import args as args_mod
from loan_manager.application.agent.tools.propose_common import ProposalContext
from loan_manager.application.agent.tools.propose_create import CreateLoanTool
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.reports.generate_report import GenerateReport
from loan_manager.domain.value_objects.status import CalculationMode, ReportActor

from .conftest import assert_no_npi_leak, make_loan, uow_factory_for

_TODAY = date(2026, 6, 1)
_CTX = ProposalContext(user_request="new loan please")


def _build_create(loans, reports_store=None):
    reports_store = reports_store if reports_store is not None else []
    uow_factory = uow_factory_for(loans, reports_store)
    clock = FixedClock(_TODAY)
    get_autocomplete = GetAutocompleteValues(uow_factory)
    tool = CreateLoanTool(
        get_autocomplete,
        BuildEntityResolver(get_autocomplete),
        GenerateReport(uow_factory, EventBus()),
        clock,
        _CTX,
    )
    return tool, reports_store


def _known_group_loan():
    # Seeds "sharma group"/"chennai circle" as real, resolvable groups
    # without this record itself being the one under test.
    return make_loan(
        borrower_name="existing borrower", borrower_group="sharma group",
        depositor_name="existing depositor", depositor_group="chennai circle",
    )


def test_create_row_shape() -> None:
    """The CREATE row this tool proposes must match the CREATE convention
    `Report.__post_init__` and `approve_report.record_to_loan_create_dto`
    both rely on -- reference_id/giving_date/due_date all None, proposed
    values in post_extension_*, extension_period=0, rates=0, derived
    amounts=None (test_approval_flow.py's `_seed_create_report` fixture
    shape, KCH-242)."""
    seed = _known_group_loan()
    tool, reports_store = _build_create([seed])

    result = tool.execute(
        args_mod.CreateLoan(
            borrower_name="Ravi Kumar",
            borrower_group="sharma group",
            depositor_name="Meena Shah",
            depositor_group="chennai circle",
            amount=150000,
            due_period=3,
        )
    )

    assert result["ok"] is True, result
    assert len(reports_store) == 1
    report = reports_store[0]
    assert report.report_mode == CalculationMode.CREATE
    assert report.actor == ReportActor.AGENT
    assert len(report.records) == 1
    rec = report.records[0]
    assert rec.reference_id is None
    assert rec.giving_date is None
    assert rec.due_date is None
    assert rec.extension_period == 0
    assert rec.interest_rate == 0
    assert rec.commission_rate == 0
    assert rec.interest_amount is None
    assert rec.commission_amount is None
    assert rec.tds_amount is None
    assert rec.chq_amount is None
    assert rec.borrower_group == "sharma group"
    assert rec.depositor_group == "chennai circle"
    assert rec.due_period == 3
    assert rec.post_extension_giving_date == _TODAY
    assert rec.post_extension_due_date == date(2026, 9, 1)
    assert rec.borrower_name == "Ravi Kumar"
    assert rec.depositor_name == "Meena Shah"
    assert rec.amount == 150000


def test_create_stores_canonical_group_case() -> None:
    """Review cycle 1, MINOR (ORCHESTRATOR RULING): resolve_group's
    known-set fast path must return the STORED (canonical) group value, not
    whatever case the caller typed -- the proposal record, and later
    KCH-245's display of it, must never carry "Sharma Group" for a book
    that stores everything as "sharma group"."""
    seed = _known_group_loan()
    tool, reports_store = _build_create([seed])

    result = tool.execute(
        args_mod.CreateLoan(
            borrower_name="Ravi Kumar",
            borrower_group="Sharma Group",
            depositor_name="Meena Shah",
            depositor_group="Chennai Circle",
            amount=150000,
        )
    )

    assert result["ok"] is True, result
    rec = reports_store[0].records[0]
    assert rec.borrower_group == "sharma group"
    assert rec.depositor_group == "chennai circle"


def test_create_no_due_period_no_post_due_date() -> None:
    seed = _known_group_loan()
    tool, reports_store = _build_create([seed])

    result = tool.execute(
        args_mod.CreateLoan(
            borrower_name="Ravi Kumar",
            borrower_group="sharma group",
            depositor_name="Meena Shah",
            amount=150000,
        )
    )

    assert result["ok"] is True
    rec = reports_store[0].records[0]
    assert rec.due_period is None
    assert rec.post_extension_due_date is None
    assert rec.post_extension_giving_date == _TODAY


def test_create_unknown_group_unresolved() -> None:
    seed = _known_group_loan()
    tool, reports_store = _build_create([seed])

    result = tool.execute(
        args_mod.CreateLoan(
            borrower_name="Ravi Kumar",
            borrower_group="totally new group",
            depositor_name="Meena Shah",
            amount=150000,
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "UNRESOLVED_ENTITY"
    assert reports_store == []
    assert_no_npi_leak(
        result, "Ravi Kumar", "Meena Shah", seed.borrower_name, seed.depositor_name,
        seed.borrower_group,
    )


def test_create_unknown_depositor_group_unresolved() -> None:
    """borrower_group resolves fine; a bad depositor_group must still be
    rejected -- the check is per-field, not short-circuited by the first
    success."""
    seed = _known_group_loan()
    tool, reports_store = _build_create([seed])

    result = tool.execute(
        args_mod.CreateLoan(
            borrower_name="Ravi Kumar",
            borrower_group="sharma group",
            depositor_name="Meena Shah",
            depositor_group="totally new depositor group",
            amount=150000,
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "UNRESOLVED_ENTITY"
    assert result["error"]["field"] == "depositor_group"
    assert reports_store == []


def test_create_non_exact_group_confirm() -> None:
    seed = _known_group_loan()
    tool, reports_store = _build_create([seed])

    # "sharma" alone is not the exact stored group "sharma group" -- and
    # ties the borrower's own name token, so it must not silently resolve.
    result = tool.execute(
        args_mod.CreateLoan(
            borrower_name="Ravi Kumar",
            borrower_group="sharma",
            depositor_name="Meena Shah",
            amount=150000,
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "CONFIRM_REQUIRED"
    assert reports_store == []


def test_create_obs_never_echoes_names() -> None:
    """Every field of the success observation, scanned as a whole -- no
    borrower/depositor name or group text anywhere in it."""
    seed = _known_group_loan()
    tool, reports_store = _build_create([seed])

    result = tool.execute(
        args_mod.CreateLoan(
            borrower_name="Ravi Kumar",
            borrower_group="sharma group",
            depositor_name="Meena Shah",
            depositor_group="chennai circle",
            amount=150000,
            due_period=3,
        )
    )

    assert result["ok"] is True
    assert_no_npi_leak(
        result,
        "Ravi Kumar", "Meena Shah", "sharma group", "chennai circle",
        seed.borrower_name, seed.depositor_name,
    )
