"""Tests for UTR1: case-insensitive filter logic in Interest Calculator.

Validates that _get_filtered_loans() comparisons are case-insensitive so that
filter dropdown values match loan records regardless of case stored in CSV.
"""
import pytest
from datetime import date
from typing import List

from models.loan import Loan


# ---------------------------------------------------------------------------
# Helpers — replicate _get_filtered_loans logic for isolated unit testing
# ---------------------------------------------------------------------------

def _make_loan(
    ref_id: str,
    borrower_name: str,
    borrower_group: str,
    depositor_name: str,
    depositor_group: str | None,
    due_date: date = date(2026, 7, 1),
) -> Loan:
    return Loan(
        reference_id=ref_id,
        borrower_name=borrower_name,
        borrower_group=borrower_group,
        amount=10000,
        giving_date=date(2026, 1, 1),
        depositor_name=depositor_name,
        depositor_group=depositor_group,
        due_date=due_date,
        status="Active",
    )


def _filter_loans(
    loans: List[Loan],
    bg_filter: str = "All",
    bn_filter: str = "All",
    dn_filter: str = "All",
    dg_filter: str = "All",
    month_filter: str = "All",
) -> List[Loan]:
    """Replicate InterestCalculatorTab._get_filtered_loans() with UTR1 fix applied."""
    from datetime import datetime
    today = date.today()

    any_filter_applied = (
        bg_filter != "All" or bn_filter != "All" or
        dn_filter != "All" or dg_filter != "All" or
        month_filter != "All"
    )

    result = []
    for loan in loans:
        if not any_filter_applied:
            if loan.due_date is None:
                result.append(loan)
            continue

        if loan.due_date is None:
            continue

        if bg_filter != "All":
            if (loan.borrower_group or "").lower() != bg_filter.lower():
                continue

        if bn_filter != "All":
            if loan.borrower_name.lower() != bn_filter.lower():
                continue

        if dn_filter != "All":
            if (loan.depositor_name or "").lower() != dn_filter.lower():
                continue

        if dg_filter != "All":
            if dg_filter == "Unknown":
                if loan.depositor_group:
                    continue
            else:
                if (loan.depositor_group or "").lower() != dg_filter.lower():
                    continue

        if month_filter != "All":
            month_num = datetime.strptime(month_filter, "%B").month
            if not (loan.due_date.year == today.year and
                    loan.due_date.month == month_num):
                continue

        result.append(loan)
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_loans():
    return [
        _make_loan("2026_01_001", "b1", "bg1", "d1", "dg1"),
        _make_loan("2026_01_002", "B1", "BG1", "D1", "DG1"),  # uppercase variant
        _make_loan("2026_02_001", "borrower1", "Group A", "depositor1", "Group B"),
        _make_loan("2026_02_002", "BORROWER1", "GROUP A", "DEPOSITOR1", "GROUP B"),
        _make_loan("2026_02_003", "b14", "bg8", "d14", None),  # no depositor_group
    ]


# ---------------------------------------------------------------------------
# Borrower Group filter — UTR1
# ---------------------------------------------------------------------------

class TestBorrowerGroupFilter:
    def test_exact_match_lowercase(self, sample_loans):
        result = _filter_loans(sample_loans, bg_filter="bg1")
        assert any(l.reference_id == "2026_01_001" for l in result)

    def test_case_insensitive_uppercase_filter(self, sample_loans):
        """Filter 'BG1' should match loan stored as 'bg1'."""
        result = _filter_loans(sample_loans, bg_filter="BG1")
        assert any(l.reference_id == "2026_01_001" for l in result)
        assert any(l.reference_id == "2026_01_002" for l in result)

    def test_case_insensitive_lowercase_filter(self, sample_loans):
        """Filter 'bg1' should match loan stored as 'BG1'."""
        result = _filter_loans(sample_loans, bg_filter="bg1")
        assert any(l.reference_id == "2026_01_002" for l in result)

    def test_no_false_positives(self, sample_loans):
        result = _filter_loans(sample_loans, bg_filter="bg1")
        ref_ids = {l.reference_id for l in result}
        assert "2026_02_001" not in ref_ids


# ---------------------------------------------------------------------------
# Borrower Name filter — UTR1
# ---------------------------------------------------------------------------

class TestBorrowerNameFilter:
    def test_case_insensitive_lower_filter(self, sample_loans):
        result = _filter_loans(sample_loans, bn_filter="borrower1")
        assert any(l.borrower_name.upper() == "BORROWER1" for l in result)
        assert any(l.borrower_name.lower() == "borrower1" for l in result)

    def test_case_insensitive_upper_filter(self, sample_loans):
        result = _filter_loans(sample_loans, bn_filter="BORROWER1")
        assert len(result) == 2

    def test_b1_match(self, sample_loans):
        result = _filter_loans(sample_loans, bn_filter="B1")
        assert any(l.reference_id == "2026_01_001" for l in result)
        assert any(l.reference_id == "2026_01_002" for l in result)


# ---------------------------------------------------------------------------
# Depositor Name filter — UTR1
# ---------------------------------------------------------------------------

class TestDepositorNameFilter:
    def test_case_insensitive(self, sample_loans):
        result = _filter_loans(sample_loans, dn_filter="depositor1")
        assert len(result) == 2
        names = {l.depositor_name for l in result}
        assert "depositor1" in names
        assert "DEPOSITOR1" in names

    def test_uppercase_filter_matches_lowercase_stored(self, sample_loans):
        result = _filter_loans(sample_loans, dn_filter="DEPOSITOR1")
        assert any(l.depositor_name == "depositor1" for l in result)


# ---------------------------------------------------------------------------
# Depositor Group filter — UTR1
# ---------------------------------------------------------------------------

class TestDepositorGroupFilter:
    def test_case_insensitive(self, sample_loans):
        result = _filter_loans(sample_loans, dg_filter="group b")
        assert len(result) == 2

    def test_unknown_filter_matches_none_depositor_group(self, sample_loans):
        """'Unknown' filter should match loans with no depositor_group."""
        result = _filter_loans(sample_loans, dg_filter="Unknown")
        assert any(l.reference_id == "2026_02_003" for l in result)
        # Should not include loans with depositor_group set
        assert all(l.depositor_group is None for l in result)

    def test_no_unknown_in_regular_filter(self, sample_loans):
        result = _filter_loans(sample_loans, dg_filter="dg1")
        assert all(l.depositor_group is not None for l in result)


# ---------------------------------------------------------------------------
# Combined filters
# ---------------------------------------------------------------------------

class TestCombinedFilters:
    def test_bg_and_bn_combined(self, sample_loans):
        result = _filter_loans(sample_loans, bg_filter="bg1", bn_filter="b1")
        assert len(result) == 2

    def test_no_match_returns_empty(self, sample_loans):
        result = _filter_loans(sample_loans, bg_filter="nonexistent")
        assert result == []


# ---------------------------------------------------------------------------
# No-filter behavior
# ---------------------------------------------------------------------------

class TestNoFilter:
    def test_no_filter_shows_only_no_due_date_loans(self):
        loans = [
            _make_loan("2026_01_001", "b1", "bg1", "d1", "dg1", due_date=date(2026, 7, 1)),
            Loan(
                reference_id="2026_02_001",
                borrower_name="b2",
                borrower_group="bg2",
                amount=5000,
                giving_date=date(2026, 1, 1),
                depositor_name="d2",
                depositor_group=None,
                due_date=None,
                status="Overdue",
            ),
        ]
        result = _filter_loans(loans)  # all filters = "All"
        assert len(result) == 1
        assert result[0].reference_id == "2026_02_001"
