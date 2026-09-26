"""Unit tests for loan_manager.application.agent.tools.read_interest (KCH-237)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from loan_manager.application.agent.tools.read_interest import CalculateInterestTool
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.domain.services.interest_calculator import InterestCalculator
from loan_manager.domain.value_objects.status import ExtensionPeriodUnit

from .conftest import make_loan, uow_factory_for


@dataclass(frozen=True)
class _Args:
    ref_id: str
    rate: Decimal
    months: int


def test_interest_matches_calculator_as_string() -> None:
    # A decoy loan ahead of the target one in the list, so a match that
    # accidentally picked the first active loan (rather than the one whose
    # reference_id equals args.ref_id) would be caught, not accidentally
    # right.
    decoy = make_loan(amount=999999)
    loan = make_loan(amount=150000)
    get_all_loans = GetAllLoans(uow_factory_for([decoy, loan]), clock=FixedClock(date(2026, 1, 1)))
    tool = CalculateInterestTool(get_all_loans)

    result = tool.execute(_Args(ref_id=str(loan.reference_id), rate=Decimal("12"), months=3))

    expected = InterestCalculator.calculate(150000, Decimal("12"), 3, ExtensionPeriodUnit.MONTHS)
    assert result["ok"] is True
    assert result["interest"] == str(expected)
    assert result["ref_id"] == str(loan.reference_id)
    assert result["months"] == 3
    assert result["principal"] == "150000.00"
    assert result["rate_percent"] == "12.00"


def test_unknown_ref_id_error() -> None:
    get_all_loans = GetAllLoans(uow_factory_for([]), clock=FixedClock(date(2026, 1, 1)))
    tool = CalculateInterestTool(get_all_loans)

    result = tool.execute(_Args(ref_id="2099_01_001", rate=Decimal("12"), months=3))

    assert result["ok"] is False
    assert result["error"]["code"] == "REF_ID_NOT_FOUND"
    assert result["error"]["ref_id"] == "2099_01_001"
