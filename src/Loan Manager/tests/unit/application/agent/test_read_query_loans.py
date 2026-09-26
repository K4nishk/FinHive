"""Unit tests for loan_manager.application.agent.tools.read_query_loans (KCH-237)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from loan_manager.application.agent.tools.read_query_loans import QueryLoansTool, _normalize
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.domain.value_objects.status import LoanStatus

from finhive.db import blind_index

from .conftest import make_loan, uow_factory_for

_TODAY = date(2026, 6, 1)


@dataclass(frozen=True)
class _Args:
    status: str
    borrower_group: str | None = None
    depositor_group: str | None = None


def _build(loans):
    clock = FixedClock(_TODAY)
    get_all_loans = GetAllLoans(uow_factory_for(loans), clock=clock)
    get_autocomplete = GetAutocompleteValues(uow_factory_for(loans))
    return QueryLoansTool(get_all_loans, get_autocomplete, clock)


def _active_loan(**overrides):
    defaults = dict(
        status=LoanStatus.ACTIVE, giving_date=date(2026, 1, 1), due_date=date(2026, 12, 31)
    )
    defaults.update(overrides)
    return make_loan(**defaults)


def test_unresolved_borrower_group_returns_resolve_first_error_not_zero() -> None:
    loans = [_active_loan(borrower_group="sharma")]
    tool = _build(loans)
    result = tool.execute(_Args(status="active", borrower_group="sharma group"))
    assert result["ok"] is False
    assert result["error"]["code"] == "UNRESOLVED_ENTITY"
    assert result["error"]["field"] == "borrower_group"
    assert result["error"]["rejected_value"] == "sharma group"
    # Never a lying zero-count success on an unresolved slug.
    assert "count" not in result


def test_unresolved_depositor_group_returns_resolve_first_error() -> None:
    loans = [_active_loan(depositor_group="chennai")]
    tool = _build(loans)
    result = tool.execute(_Args(status="active", depositor_group="chennai circle"))
    assert result["ok"] is False
    assert result["error"]["code"] == "UNRESOLVED_ENTITY"
    assert result["error"]["field"] == "depositor_group"
    assert result["error"]["rejected_value"] == "chennai circle"


def test_group_from_wrong_field_rejected() -> None:
    """"sharma" is a real borrower_group but never a depositor_group — the
    known-slug check is per-field, never a union of every name field."""
    loans = [_active_loan(borrower_group="sharma", depositor_group="mumbai")]
    tool = _build(loans)
    result = tool.execute(_Args(status="active", depositor_group="sharma"))
    assert result["ok"] is False
    assert result["error"]["code"] == "UNRESOLVED_ENTITY"
    assert result["error"]["field"] == "depositor_group"


def test_known_group_case_insensitive_accepted() -> None:
    loans = [_active_loan(borrower_group="sharma")]
    tool = _build(loans)
    result = tool.execute(_Args(status="active", borrower_group="SHARMA"))
    assert result["ok"] is True
    assert result["count"] == 1


def test_undated_loan_counted_in_overdue_not_in_max_days() -> None:
    dated_overdue = _active_loan(due_date=date(2026, 3, 1))  # 92 days overdue at _TODAY
    undated_overdue = _active_loan(due_date=None)  # giving_date past, no due_date -> OVERDUE
    tool = _build([dated_overdue, undated_overdue])
    result = tool.execute(_Args(status="overdue"))
    assert result["count"] == 2
    assert result["overdue"] == 2
    assert result["overdue_undated"] == 1
    assert result["max_days_overdue"] == 92


def test_undated_note_present() -> None:
    dated_overdue = _active_loan(due_date=date(2026, 3, 1))
    undated_overdue = _active_loan(due_date=None)
    tool = _build([dated_overdue, undated_overdue])
    result = tool.execute(_Args(status="overdue"))
    assert result["notes"] == [
        "1 overdue loan(s) have no due date agreed; excluded from max_days_overdue"
    ]


def test_status_from_status_engine_not_stored_column() -> None:
    """Persisted status says ACTIVE, but giving_date/due_date make the
    COMPUTED status OVERDUE — the tool must go by the computed status."""
    loan = _active_loan(due_date=date(2026, 3, 1), status=LoanStatus.ACTIVE)
    tool = _build([loan])

    overdue_result = tool.execute(_Args(status="overdue"))
    assert overdue_result["count"] == 1

    active_result = tool.execute(_Args(status="active"))
    assert active_result["count"] == 0


def test_projection_has_no_names_and_exact_keys() -> None:
    dated_overdue = _active_loan(due_date=date(2026, 3, 1))
    undated_overdue = _active_loan(due_date=None)
    tool = _build([dated_overdue, undated_overdue])

    with_notes = tool.execute(_Args(status="overdue"))
    assert set(with_notes.keys()) == {
        "ok", "status", "count", "total_amount", "overdue",
        "overdue_undated", "ref_ids", "max_days_overdue", "notes",
    }

    without_notes = tool.execute(_Args(status="active"))
    assert set(without_notes.keys()) == {
        "ok", "status", "count", "total_amount", "overdue",
        "overdue_undated", "ref_ids", "max_days_overdue",
    }

    for name_field in ("borrower_name", "borrower_group", "depositor_name", "depositor_group"):
        assert name_field not in with_notes
        assert name_field not in without_notes


def test_total_amount_is_decimal_string_via_loan_ordering() -> None:
    loans = [_active_loan(amount=10000), _active_loan(amount=20000)]
    tool = _build(loans)
    result = tool.execute(_Args(status="active"))
    assert result["total_amount"] == "30000.00"


def test_paidoff_status_rejected() -> None:
    tool = _build([])
    result = tool.execute(_Args(status="paidoff"))
    assert result["ok"] is False
    assert result["error"]["code"] == "UNSUPPORTED_STATUS"
    assert result["error"]["next_action"]


def test_output_json_serialisable() -> None:
    loan = _active_loan(due_date=None)
    tool = _build([loan])
    success = tool.execute(_Args(status="overdue"))
    failure = tool.execute(_Args(status="paidoff"))
    json.dumps(success)
    json.dumps(failure)


def test_normalize_parity_with_blind_index() -> None:
    """`_normalize` mirrors `finhive.db.blind_index.normalize` (strip +
    lowercase) exactly, without importing it (see module docstring)."""
    samples = [
        "Sharma Group", "  chennai circle  ", "MUMBAI", "b1", " b_1 ",
        # "Straße" kills a `.casefold()` mutant: casefold() maps 'ß' -> "ss"
        # ("strasse"), .lower() does not ("straße") -- only .lower() mirrors
        # blind_index.normalize.
        "Straße",
        # Tab-padded, not just space-padded: kills a `.strip(" ")`-only
        # mutant that a plain-looking `.strip()` reimplementation could
        # regress to.
        "\t\tSharma Group\t\t",
    ]
    for sample in samples:
        assert _normalize(sample) == blind_index.normalize(sample)
