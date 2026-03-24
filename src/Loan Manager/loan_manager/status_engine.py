"""Status auto-recompute engine for loan records.

Authoritative implementation lives here (loan_manager layer).
data/status_engine.py re-exports from this module.
"""
import logging
from datetime import date
from typing import Any, Dict, List, Optional, Union

from models.loan import Loan

logger = logging.getLogger(__name__)

# Type alias for the dict form used by tests
LoanDict = Dict[str, Any]
LoanLike = Union[Loan, LoanDict]


def compute_status(
    loan: Optional[Loan] = None,
    today: Optional[date] = None,
    *,
    giving_date: Optional[date] = None,
    due_date: Optional[date] = None,
    current_status: Optional[str] = None,
) -> str:
    """Compute the auto-derived status for a loan based on today's date.

    Supports two calling conventions:
    1. compute_status(loan, today)          — Loan dataclass
    2. compute_status(giving_date=..., due_date=..., current_status=..., today=...)

    Rules:
    - Paidoff:  current_status == 'Paidoff' -> never auto-recomputed
    - Pending:  giving_date > today
    - Active:   giving_date <= today AND due_date is set AND today < due_date
    - Overdue:  due_date <= today OR (no due_date AND giving_date <= today)

    BC-01 confirmed (PD-01): due_date == today -> Overdue (inclusive boundary).
    BC-01 confirmed: no due_date + giving_date <= today -> Overdue.
    BC-01 confirmed: no due_date + giving_date > today -> Pending.
    """
    # Resolve parameters from Loan object or keyword args
    if loan is not None and today is not None and isinstance(loan, Loan):
        _giving = loan.giving_date
        _due = loan.due_date
        _status = loan.status
        _today = today
    else:
        # Keyword-arg calling convention (used by tests)
        if today is None:
            raise ValueError("today must be provided")
        _giving = giving_date
        _due = due_date
        _status = current_status or ""
        _today = today

    if _giving is None:
        raise ValueError("giving_date must be provided")

    if _status == "Paidoff":
        return "Paidoff"

    if _giving > _today:
        return "Pending"

    # giving_date <= today
    if _due is None:
        return "Overdue"

    if _today < _due:
        return "Active"

    # today >= due_date
    return "Overdue"


def recompute_all(
    loans: List[LoanLike],
    today: date,
) -> List[LoanLike]:
    """Recompute status for all non-Paidoff loans and return updated list.

    Accepts either a list of Loan dataclasses or a list of dicts (for tests).
    Paidoff records are left unchanged.
    Returns a new list; the original list items are NOT mutated.
    """
    result: List[LoanLike] = []
    for loan in loans:
        if isinstance(loan, Loan):
            if loan.status == "Paidoff":
                result.append(loan)
                continue
            new_status = compute_status(loan, today)
            if new_status != loan.status:
                logger.debug(
                    "Status recomputed for %s: %s -> %s",
                    loan.reference_id,
                    loan.status,
                    new_status,
                )
                loan.status = new_status
            result.append(loan)
        else:
            # Dict form (used by tests)
            loan_copy = dict(loan)
            current = loan_copy.get("status", "")
            if current == "Paidoff":
                result.append(loan_copy)
                continue
            new_status = compute_status(
                giving_date=loan_copy.get("giving_date"),
                due_date=loan_copy.get("due_date"),
                current_status=current,
                today=today,
            )
            loan_copy["status"] = new_status
            result.append(loan_copy)
    return result
