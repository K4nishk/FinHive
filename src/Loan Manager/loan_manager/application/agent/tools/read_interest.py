"""calculate_interest: deterministic interest arithmetic (KCH-237).

A thin wrapper over `InterestCalculator.calculate` — the model must never
compute interest itself (CLAUDE.md: `(amount * rate * months) / 1200`, and
`giving_date` never enters this or any time calculation; only `args.months`,
supplied by the caller, is used).

DEBT: there is no read-by-ref use case, so this scans every active loan via
`GetAllLoans` to find `ref_id` — fine at MVP1.1's loan-book size, wrong at
scale. Flagged in the accepted plan, not this issue's scope to fix.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from loan_manager.application.agent.tools.observations import ErrorCode, error, ok
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.domain.services.interest_calculator import InterestCalculator
from loan_manager.domain.value_objects.status import ExtensionPeriodUnit

_TWO_PLACES = Decimal("0.01")


class CalculateInterestTool:
    def __init__(self, get_all_loans: GetAllLoans) -> None:
        self._get_all_loans = get_all_loans

    def execute(self, args: Any) -> dict[str, Any]:
        loans = self._get_all_loans.execute()
        loan = next((loan for loan in loans if loan.reference_id == args.ref_id), None)
        if loan is None:
            return error(
                ErrorCode.REF_ID_NOT_FOUND,
                f"no active loan found for reference_id {args.ref_id!r}",
                "confirm the reference_id with the user, or use query_loans/"
                "resolve_entity to find the correct one",
                ref_id=args.ref_id,
            )

        interest = InterestCalculator.calculate(
            loan.amount, args.rate, args.months, ExtensionPeriodUnit.MONTHS
        )
        principal = Decimal(loan.amount).quantize(_TWO_PLACES)
        rate_percent = args.rate.quantize(_TWO_PLACES)

        return ok(
            ref_id=args.ref_id,
            principal=principal,
            rate_percent=rate_percent,
            months=args.months,
            interest=interest,
            basis="amount×rate×months/1200",
        )
