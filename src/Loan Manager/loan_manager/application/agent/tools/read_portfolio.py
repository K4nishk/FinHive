"""get_portfolio_summary: top-N borrowers by outstanding exposure (KCH-237).

Exposure is computed ACTIVE + OVERDUE only (PENDING excluded — a loan not
yet given is not outstanding exposure yet); status is always derived via
`StatusEngine`, never the persisted `LoanDTO.status` column, for the same
staleness reason as `read_query_loans.py`.

Loans are grouped by `(borrower_name, borrower_group)` — the same borrower
name can appear in more than one group, and those are kept as separate
aggregates rather than merged, since a group is part of a borrower's
identity in this domain (two loans differing only in `borrower_group` are
not necessarily the same underlying party). Each aggregate is ranked with
`loan_ordering.rank_by_amount`, which needs a `reference_id` string to break
ties on; `f"{borrower_name}|{borrower_group}"` is used for that (documented
here since nothing else names it) — it never leaves this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from loan_manager.application.agent.tools.observations import ok
from loan_manager.application.dtos.loan_dto import LoanDTO
from loan_manager.application.interfaces.clock import Clock
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.domain.services import loan_ordering
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.status import LoanStatus

_EXPOSURE_STATUSES = (LoanStatus.ACTIVE, LoanStatus.OVERDUE)


@dataclass(frozen=True)
class _BorrowerAggregate:
    """One (borrower_name, borrower_group) group's summed exposure.
    `reference_id` exists only so `loan_ordering.rank_by_amount`'s tiebreak
    (ascending by `str(reference_id)`) has something deterministic to sort
    equal-exposure aggregates by — see module docstring."""

    reference_id: str
    borrower_name: str
    borrower_group: str
    amount: Decimal
    ref_ids: tuple[str, ...]


def _group(loans: list[LoanDTO]) -> list[_BorrowerAggregate]:
    grouped: dict[tuple[str, str], list[LoanDTO]] = {}
    for loan in loans:
        key = (loan.borrower_name, loan.borrower_group)
        grouped.setdefault(key, []).append(loan)
    return [
        _BorrowerAggregate(
            reference_id=f"{name}|{group}",
            borrower_name=name,
            borrower_group=group,
            amount=loan_ordering.total_amount(members),
            ref_ids=tuple(sorted(m.reference_id for m in members)),
        )
        for (name, group), members in grouped.items()
    ]


class GetPortfolioSummaryTool:
    def __init__(self, get_all_loans: GetAllLoans, clock: Clock) -> None:
        self._get_all_loans = get_all_loans
        self._clock = clock

    def execute(self, args: Any) -> dict[str, Any]:
        today = self._clock.today()
        loans = self._get_all_loans.execute()
        exposed = [
            loan
            for loan in loans
            if StatusEngine.compute(loan.giving_date, loan.due_date, today)
            in _EXPOSURE_STATUSES
        ]

        aggregates = _group(exposed)
        ranked = loan_ordering.rank_by_amount(aggregates, limit=args.limit)

        top = [
            {
                "rank": i,
                "borrower_name": agg.borrower_name,
                "borrower_group": agg.borrower_group,
                "exposure": agg.amount,
                "loan_count": len(agg.ref_ids),
                "ref_ids": list(agg.ref_ids),
            }
            for i, agg in enumerate(ranked, start=1)
        ]

        return ok(
            as_of=today.isoformat(),
            total_exposure=loan_ordering.total_amount(exposed),
            borrower_count=len(aggregates),
            top=top,
        )
