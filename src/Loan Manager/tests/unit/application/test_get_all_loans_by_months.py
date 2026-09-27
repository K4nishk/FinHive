"""Unit tests for the ByMonth set-membership predicate in GetAllLoans.

Exercises loan_manager.application.use_cases.loans.get_loans.GetAllLoans
directly against a fake unit of work — no DB required — so the predicate
itself (not a re-implementation of it) is under test.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from loan_manager.application.dtos.loan_dto import LoanFilterDTO
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.domain.value_objects.status import LoanStatus


_reference_counter = 0


def _make_loan(name: str, due_date, status=LoanStatus.ACTIVE) -> Loan:
    global _reference_counter
    _reference_counter += 1
    now = datetime(2026, 1, 1)
    return Loan(
        id=None,
        reference_id=ReferenceId(f"2026_01_{_reference_counter:03d}"),
        borrower_name=name,
        borrower_group="bg1",
        depositor_name="d1",
        depositor_group="dg1",
        amount=Money(10000),
        giving_date=date(2026, 1, 1),
        due_period=None,
        due_date=due_date,
        status=status,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


class _FakeLoanRepo:
    def __init__(self, loans: list[Loan]) -> None:
        self._loans = loans

    def get_all_active(self, filters=None) -> list[Loan]:
        return list(self._loans)


class _FakeUnitOfWork:
    def __init__(self, loans: list[Loan]) -> None:
        self.loans = _FakeLoanRepo(loans)

    def __enter__(self) -> "_FakeUnitOfWork":
        return self

    def __exit__(self, *exc_info) -> bool:
        return False


# A FixedClock, not date.today(): these tests pin "current year" so a run
# straddling a real year boundary (process starts Dec 31, asserts Jan 1)
# can't flake. GetAllLoans below is always given this same clock, so its
# year-scoping matches the fixture's notion of "current year" regardless of
# the wall clock.
_TEST_CLOCK = FixedClock(date(2026, 6, 1))
CURRENT_YEAR = _TEST_CLOCK.today().year


@pytest.fixture
def sample_loans() -> list[Loan]:
    return [
        _make_loan("march_due", date(CURRENT_YEAR, 3, 10)),
        _make_loan("july_due", date(CURRENT_YEAR, 7, 20)),
        _make_loan("june_due", date(CURRENT_YEAR, 6, 5)),
        _make_loan(
            "overdue_march", date(CURRENT_YEAR, 3, 1), status=LoanStatus.OVERDUE
        ),
        _make_loan("no_due_date", None),
        _make_loan("prior_year_march", date(CURRENT_YEAR - 1, 3, 10)),
    ]


def _names(loans) -> set[str]:
    return {loan.borrower_name for loan in loans}


class TestByMonthsSetMembership:
    def test_single_month_matches_only_that_month(self, sample_loans):
        uc = GetAllLoans(lambda: _FakeUnitOfWork(sample_loans), clock=_TEST_CLOCK)
        result = uc.execute(LoanFilterDTO(by_months=[6]))
        assert _names(result) == {"june_due"}

    def test_multiple_months_returns_union(self, sample_loans):
        uc = GetAllLoans(lambda: _FakeUnitOfWork(sample_loans), clock=_TEST_CLOCK)
        result = uc.execute(LoanFilterDTO(by_months=[3, 7]))
        assert _names(result) == {"march_due", "july_due", "overdue_march"}

    def test_month_not_selected_is_excluded(self, sample_loans):
        uc = GetAllLoans(lambda: _FakeUnitOfWork(sample_loans), clock=_TEST_CLOCK)
        result = uc.execute(LoanFilterDTO(by_months=[3, 7]))
        assert "june_due" not in _names(result)

    def test_excludes_records_with_no_due_date(self, sample_loans):
        uc = GetAllLoans(lambda: _FakeUnitOfWork(sample_loans), clock=_TEST_CLOCK)
        result = uc.execute(LoanFilterDTO(by_months=[3, 6, 7]))
        assert "no_due_date" not in _names(result)

    def test_scopes_to_current_calendar_year(self, sample_loans):
        uc = GetAllLoans(lambda: _FakeUnitOfWork(sample_loans), clock=_TEST_CLOCK)
        result = uc.execute(LoanFilterDTO(by_months=[3]))
        assert "prior_year_march" not in _names(result)

    def test_includes_overdue_records_matching_selection(self, sample_loans):
        uc = GetAllLoans(lambda: _FakeUnitOfWork(sample_loans), clock=_TEST_CLOCK)
        result = uc.execute(LoanFilterDTO(by_months=[3]))
        assert "overdue_march" in _names(result)

    def test_empty_selection_behaves_as_no_filter(self, sample_loans):
        uc = GetAllLoans(lambda: _FakeUnitOfWork(sample_loans), clock=_TEST_CLOCK)
        no_filter_result = uc.execute(LoanFilterDTO())
        empty_selection_result = uc.execute(LoanFilterDTO(by_months=[]))
        assert _names(empty_selection_result) == _names(no_filter_result)
        # Select-none must not behave as select-all restricted to due-date
        # presence only — it must be identical to "no filter at all",
        # which includes the no-due-date record.
        assert "no_due_date" in _names(empty_selection_result)

    def test_none_selection_behaves_as_no_filter(self, sample_loans):
        uc = GetAllLoans(lambda: _FakeUnitOfWork(sample_loans), clock=_TEST_CLOCK)
        result = uc.execute(LoanFilterDTO(by_months=None))
        assert _names(result) == _names(sample_loans)

    def test_rejects_month_outside_1_to_12(self):
        with pytest.raises(ValueError):
            LoanFilterDTO(by_months=[0])
        with pytest.raises(ValueError):
            LoanFilterDTO(by_months=[13])


class TestByMonthsUsesInjectedClockYear:
    def test_scopes_to_injected_clock_year_not_wall_clock(self):
        """KCH-233: the by_months year-scoping reads the injected Clock's
        year, not date.today().year. This test's own clock (2020) and
        CURRENT_YEAR (2026, this module's pinned test year -- itself
        independent of the real wall clock) are different, so a GetAllLoans
        that ignored its injected clock and fell back to the real system
        date would return neither "clock_year" (2020) nor -- except by the
        year-2026 coincidence this test does not rely on -- "wall_clock_year"
        (2026), and the assertion below would fail either way.
        """
        loans = [
            _make_loan("clock_year", date(2020, 3, 10)),
            _make_loan("wall_clock_year", date(CURRENT_YEAR, 3, 10)),
        ]
        uc = GetAllLoans(lambda: _FakeUnitOfWork(loans), clock=FixedClock(date(2020, 6, 1)))
        result = uc.execute(LoanFilterDTO(by_months=[3]))
        assert _names(result) == {"clock_year"}
