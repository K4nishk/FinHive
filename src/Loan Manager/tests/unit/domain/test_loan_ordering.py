"""loan_ordering unit tests (KCH-105): numeric rank, decimal totals, name sort.

Works across both Loan (amount: Money, reference_id: ReferenceId) and LoanDTO
(amount: int, reference_id: str) via duck typing.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from loan_manager.application.dtos.loan_dto import LoanDTO
from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.services.loan_ordering import (
    rank_by_amount,
    sort_by_name,
    total_amount,
)
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.domain.value_objects.status import LoanStatus


def _loan(
    ref: str,
    amount: int,
    borrower_name: str = "borrower",
    borrower_group: str = "group",
    depositor_name: str = "depositor",
    depositor_group: str | None = "dgroup",
) -> Loan:
    return Loan(
        id=None,
        reference_id=ReferenceId(ref),
        borrower_name=borrower_name,
        borrower_group=borrower_group,
        depositor_name=depositor_name,
        depositor_group=depositor_group,
        amount=Money(amount),
        giving_date=date(2026, 1, 1),
        due_period=1,
        due_date=date(2026, 2, 1),
        status=LoanStatus.ACTIVE,
        is_active=True,
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime(2026, 1, 1, 0, 0, 0),
    )


def _loan_dto(ref: str, amount: int, **overrides) -> LoanDTO:
    fields = {
        "id": None,
        "reference_id": ref,
        "borrower_name": "borrower",
        "borrower_group": "group",
        "depositor_name": "depositor",
        "depositor_group": "dgroup",
        "amount": amount,
        "giving_date": date(2026, 1, 1),
        "due_period": 1,
        "due_date": date(2026, 2, 1),
        "status": LoanStatus.ACTIVE,
        "is_active": True,
        "created_at": datetime(2026, 1, 1, 0, 0, 0),
        "updated_at": datetime(2026, 1, 1, 0, 0, 0),
    }
    fields.update(overrides)
    return LoanDTO.model_construct(**fields)


class TestRankByAmount:
    def test_rank_by_amount_is_numeric_not_lexicographic(self):
        # Lexicographically ("10000" < "9000" < "950") a str-keyed descending sort
        # yields [950, 9000, 10000] -- wrong. Numeric descending is [10000, 9000, 950].
        loans = [_loan("2026_01_001", 9000), _loan("2026_01_002", 10000), _loan("2026_01_003", 950)]
        ranked = rank_by_amount(loans)
        assert [int(loan.amount) for loan in ranked] == [10000, 9000, 950]

    def test_rank_by_amount_ascending_and_limit_slices_after_sort(self):
        # Original order deliberately not amount-sorted: slicing first 2 *before*
        # sorting would give amounts [700, 100] -> sorted [100, 700] (wrong).
        # Sorting first then slicing gives the true two smallest: [100, 300].
        loans = [_loan("2026_01_001", 700), _loan("2026_01_002", 100),
                  _loan("2026_01_003", 500), _loan("2026_01_004", 300)]
        ranked = rank_by_amount(loans, descending=False, limit=2)
        assert [int(loan.amount) for loan in ranked] == [100, 300]

    def test_rank_by_amount_ties_are_stable_by_reference_id(self):
        # All amounts tie; input order is scrambled relative to reference_id.
        # Ties must resolve to ascending reference_id regardless of input order.
        loans = [_loan("2026_01_003", 1000), _loan("2026_01_001", 1000), _loan("2026_01_002", 1000)]
        ranked = rank_by_amount(loans)
        expected = ["2026_01_001", "2026_01_002", "2026_01_003"]
        assert [str(loan.reference_id) for loan in ranked] == expected

    def test_rank_by_amount_negative_limit_rejected(self):
        loans = [_loan("2026_01_001", 100)]
        with pytest.raises(ValueError):
            rank_by_amount(loans, limit=-1)

    def test_rank_by_amount_ties_are_stable_ascending(self):
        # Same property as the descending-tie test above, but for descending=False:
        # ties must still resolve to ascending reference_id.
        loans = [_loan("2026_01_003", 500), _loan("2026_01_001", 500), _loan("2026_01_002", 500)]
        ranked = rank_by_amount(loans, descending=False)
        expected = ["2026_01_001", "2026_01_002", "2026_01_003"]
        assert [str(loan.reference_id) for loan in ranked] == expected

    def test_rank_by_amount_works_with_loan_dto(self):
        # Duck typing: LoanDTO.amount is a bare int, reference_id is a bare str.
        dtos = [
            _loan_dto("2026_01_001", 9000),
            _loan_dto("2026_01_002", 10000),
            _loan_dto("2026_01_003", 950),
        ]
        ranked = rank_by_amount(dtos)
        assert [loan.amount for loan in ranked] == [10000, 9000, 950]


class TestTotalAmount:
    def test_total_amount_returns_decimal_quantised_2dp(self):
        loans = [_loan("2026_01_001", 9000), _loan("2026_01_002", 10000)]
        result = total_amount(loans)
        assert isinstance(result, Decimal)
        assert str(result) == "19000.00"
        assert result.as_tuple().exponent == -2

        # Empty case folded in here: quantize is what makes it a 2dp Decimal, not a
        # bare int 0; the "drop quantize" fail-first above covers both assertions.
        empty = total_amount([])
        assert empty == Decimal("0.00")
        assert str(empty) == "0.00"

    def test_total_amount_accepts_money_and_int_amounts(self):
        mixed = [_loan("2026_01_001", 100), _loan_dto("2026_01_002", 200)]
        result = total_amount(mixed)
        assert result == Decimal("300.00")

    def test_total_amount_rejects_non_integer_amount(self):
        # Money is a plain (unvalidated-by-type) dataclass; a caller could smuggle a
        # float/Decimal into it. Unwrapping must reject that, not truncate it.
        loan = _loan("2026_01_001", 100)
        object.__setattr__(loan.amount, "amount", 1.9)
        with pytest.raises(TypeError):
            total_amount([loan])


class TestSortByName:
    def test_sort_by_name_is_case_insensitive_alphabetical(self):
        loans = [
            _loan("2026_01_001", 100, borrower_name="Zara"),
            _loan("2026_01_002", 100, borrower_name="adam"),
            _loan("2026_01_003", 100, borrower_name="Beta"),
        ]
        ranked = sort_by_name(loans, "borrower_name")
        assert [loan.borrower_name for loan in ranked] == ["adam", "Beta", "Zara"]

    def test_sort_by_name_rejects_unknown_field(self):
        loans = [_loan("2026_01_001", 100)]
        with pytest.raises(ValueError):
            sort_by_name(loans, "notes")

    def test_sort_by_name_ties_are_stable_by_reference_id(self):
        # All names tie; input order is scrambled relative to reference_id.
        loans = [
            _loan("2026_01_003", 100, borrower_name="same"),
            _loan("2026_01_001", 100, borrower_name="same"),
            _loan("2026_01_002", 100, borrower_name="same"),
        ]
        ranked = sort_by_name(loans, "borrower_name")
        expected = ["2026_01_001", "2026_01_002", "2026_01_003"]
        assert [str(loan.reference_id) for loan in ranked] == expected

    def test_sort_by_name_descending_ties_still_ascending_by_reference_id(self):
        # Two loans tie on name "same" (scrambled refs); one distinct "alpha" sorts
        # after them under descending=True. Ties stay ascending by reference_id
        # regardless of descending; forcing reverse=False would flip the "alpha" vs
        # "same" group order and fail this.
        loans = [
            _loan("2026_01_003", 100, borrower_name="same"),
            _loan("2026_01_001", 100, borrower_name="same"),
            _loan("2026_01_002", 100, borrower_name="alpha"),
        ]
        ranked = sort_by_name(loans, "borrower_name", descending=True)
        assert [loan.borrower_name for loan in ranked] == ["same", "same", "alpha"]
        assert [str(loan.reference_id) for loan in ranked] == [
            "2026_01_001", "2026_01_003", "2026_01_002",
        ]

    def test_sort_by_name_none_group_sorts_first_without_crash(self):
        # depositor_group=None must not crash the sort; it sorts as "" (first,
        # ascending) rather than raising on a bare None.casefold().
        loans = [
            _loan("2026_01_001", 100, depositor_group="zeta"),
            _loan("2026_01_002", 100, depositor_group=None),
        ]
        ranked = sort_by_name(loans, "depositor_group")
        assert [loan.depositor_group for loan in ranked] == [None, "zeta"]
