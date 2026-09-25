from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, TypeVar

from loan_manager.domain.value_objects.money import Money

NAME_FIELDS = ("borrower_name", "borrower_group", "depositor_name", "depositor_group")
NameField = Literal["borrower_name", "borrower_group", "depositor_name", "depositor_group"]

T = TypeVar("T")


def _ref_key(loan: T) -> str:
    """Reference-id tiebreak, uniform across Loan (ReferenceId) and LoanDTO (str).

    Compared lexicographically as a string. `ReferenceId.build` zero-pads the
    per-month order to 3 digits only below 1000 (reference_id.py); an order
    >=1000 is unpadded and would sort incorrectly against padded ones (e.g.
    "1000" < "999" as strings). Not reachable below 1000 loans/month.
    """
    return str(loan.reference_id)


def _whole_rupees(loan: T) -> int:
    """Unwrap `loan.amount` (Money or bare int) and require a whole-rupee int.

    A float or Decimal amount is rejected rather than silently truncated.
    """
    amount = loan.amount
    if isinstance(amount, Money):
        amount = amount.amount
    if not isinstance(amount, int):
        raise TypeError("amount must be whole rupees (int)")
    return amount


def total_amount(loans: Iterable[T]) -> Decimal:
    """Sum of loan amounts (Loan.amount: Money or LoanDTO.amount: int), 2dp Decimal.

    Never uses float.
    """
    total = sum((Decimal(_whole_rupees(loan)) for loan in loans), start=Decimal("0"))
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def rank_by_amount(
    loans: Sequence[T],
    *,
    descending: bool = True,
    limit: int | None = None,
) -> list[T]:
    """Rank loans by amount, numerically (never lexicographically).

    Ties are broken by ascending reference_id, independent of `descending`, via a
    two-pass stable sort. `limit` is applied AFTER sorting (slices the ranked list),
    never before. A negative `limit` is rejected.
    """
    if limit is not None and limit < 0:
        raise ValueError(f"limit must be non-negative, got {limit}")

    by_ref = sorted(loans, key=_ref_key)
    ranked = sorted(by_ref, key=lambda loan: int(loan.amount), reverse=descending)

    if limit is not None:
        ranked = ranked[:limit]
    return ranked


def sort_by_name(
    loans: Sequence[T],
    field: NameField,
    *,
    descending: bool = False,
) -> list[T]:
    """Sort loans by a name field, case-insensitively.

    Ties are broken by ascending reference_id via a two-pass stable sort. `field`
    must be one of the four name fields; anything else is rejected.
    """
    if field not in NAME_FIELDS:
        raise ValueError(f"Unknown name field {field!r}; expected one of {NAME_FIELDS}")

    by_ref = sorted(loans, key=_ref_key)
    return sorted(
        by_ref,
        key=lambda loan: (getattr(loan, field, None) or "").casefold(),
        reverse=descending,
    )
