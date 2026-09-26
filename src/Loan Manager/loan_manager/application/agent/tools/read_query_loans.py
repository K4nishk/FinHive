"""query_loans: filtered aggregate query over loans (KCH-237).

Returns counts and totals, never rows and never names (`GetAllLoans`'
`LoanDTO`s never leave this module) — the UI hydrates row detail from the
returned `ref_ids` itself, through its own use cases.

Two guardrails ahead of any query:

1. A `borrower_group`/`depositor_group` value must already be a value
   `resolve_entity` would return for THAT field — checked with a per-field
   known-slug set (`GetAutocompleteValues`), never fuzzy and never across
   fields (a value that is a real `borrower_group` but was passed as
   `depositor_group` is rejected, not silently accepted). `_normalize`
   mirrors `finhive.db.blind_index.normalize` (strip + lowercase) rather
   than importing it: this is an application-layer module and
   `finhive.db` is an infrastructure-adjacent package outside
   `loan_manager` entirely; `test_read_query_loans.py::
   test_normalize_parity_with_blind_index` pins the two in lockstep. This
   also deliberately does NOT reuse `EntityResolver`'s own `_normalize`
   (that one additionally folds `_`/`-` to space for fuzzy matching, a
   different, looser equality than the exact blind-index one this check
   must mirror).
2. `status="paidoff"` is refused outright: a paid-off loan is archived to
   `loan_history` (CLAUDE.md), invisible to `GetAllLoans`, so answering with
   a count/total of zero would be a confident lie about a status this tool
   simply cannot see.

Status is always derived via `StatusEngine.compute(giving_date, due_date,
today)` — NEVER `LoanDTO.status`, which is a persisted column that goes
stale the moment a loan is extended or paid off outside a full app restart
(CLAUDE.md; KCH-229 fixed one such staleness bug, this must not reintroduce
another).
"""
from __future__ import annotations

from typing import Any

from loan_manager.application.agent.tools.observations import ErrorCode, error, ok
from loan_manager.application.dtos.loan_dto import LoanFilterDTO
from loan_manager.application.interfaces.clock import Clock
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.domain.services import loan_ordering
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.status import LoanStatus

_GROUP_FIELDS = ("borrower_group", "depositor_group")


def _normalize(value: str) -> str:
    """Mirrors `finhive.db.blind_index.normalize` exactly (strip + lower) —
    see module docstring for why this is a mirror, not an import."""
    return value.strip().lower()


class QueryLoansTool:
    def __init__(
        self,
        get_all_loans: GetAllLoans,
        get_autocomplete: GetAutocompleteValues,
        clock: Clock,
    ) -> None:
        self._get_all_loans = get_all_loans
        self._get_autocomplete = get_autocomplete
        self._clock = clock

    def execute(self, args: Any) -> dict[str, Any]:
        if args.status == "paidoff":
            return error(
                ErrorCode.UNSUPPORTED_STATUS,
                "paidoff loans are archived to loan_history and are not visible to "
                "this tool; a count or total here would be a confident lie",
                "do not report a paidoff figure from this tool; if the user needs "
                "paid-off history, say that it is out of scope for this query",
            )

        for field_name in _GROUP_FIELDS:
            value = getattr(args, field_name)
            if value is None:
                continue
            known = {_normalize(v) for v in self._get_autocomplete.execute(field_name)}
            if _normalize(value) not in known:
                return error(
                    ErrorCode.UNRESOLVED_ENTITY,
                    f"{value!r} is not a known {field_name}",
                    "call resolve_entity with the user's text, then retry "
                    "query_loans with the exact value it returns",
                    field=field_name,
                    rejected_value=value,
                )

        loans = self._get_all_loans.execute(
            LoanFilterDTO(
                borrower_group=args.borrower_group,
                depositor_group=args.depositor_group,
            )
        )

        today = self._clock.today()
        matched = [
            loan
            for loan in loans
            if StatusEngine.compute(loan.giving_date, loan.due_date, today).value.lower()
            == args.status
        ]

        overdue_loans = [
            loan for loan in matched
            if StatusEngine.compute(loan.giving_date, loan.due_date, today)
            == LoanStatus.OVERDUE
        ]
        overdue_undated = [loan for loan in overdue_loans if loan.due_date is None]
        overdue_dated = [loan for loan in overdue_loans if loan.due_date is not None]
        max_days_overdue = (
            max((today - loan.due_date).days for loan in overdue_dated)
            if overdue_dated
            else None
        )

        payload: dict[str, Any] = {
            "status": args.status,
            "count": len(matched),
            "total_amount": loan_ordering.total_amount(matched),
            "overdue": len(overdue_loans),
            "overdue_undated": len(overdue_undated),
            "ref_ids": sorted(loan.reference_id for loan in matched),
            "max_days_overdue": max_days_overdue,
        }
        if overdue_undated:
            payload["notes"] = [
                f"{len(overdue_undated)} overdue loan(s) have no due date agreed; "
                "excluded from max_days_overdue"
            ]
        return ok(**payload)
