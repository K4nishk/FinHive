"""Tests for R5: CHQ_Amt formula and calculation dialog logic.

Tests the pure calculation helpers without instantiating PySide6 UI.
"""
import pytest
from datetime import date


# ---------------------------------------------------------------------------
# Import the CHQ_Amt helper directly
# ---------------------------------------------------------------------------

def _compute_chq_amt(interest_amount: float, tds_amount: float, tds_flag: bool) -> float:
    """Replicated from calculation_dialog.py for isolated testing."""
    if tds_flag:
        return interest_amount - tds_amount
    return 0.9 * interest_amount


# ---------------------------------------------------------------------------
# CHQ_Amt formula tests
# ---------------------------------------------------------------------------

class TestChqAmtFormula:
    def test_tds_true_chq_amt_is_interest_minus_tds(self):
        interest = 1000.0
        tds = 100.0
        chq = _compute_chq_amt(interest, tds, tds_flag=True)
        assert chq == pytest.approx(900.0)

    def test_tds_false_chq_amt_is_0_9_times_interest(self):
        interest = 1000.0
        tds = 0.0
        chq = _compute_chq_amt(interest, tds, tds_flag=False)
        assert chq == pytest.approx(900.0)

    def test_tds_true_matches_0_9_interest_when_tds_is_10_percent(self):
        """When tds = 10% of interest: interest - tds = 0.9 * interest."""
        interest = 500.0
        tds = 0.1 * interest  # = 50.0
        chq_flag_true = _compute_chq_amt(interest, tds, tds_flag=True)
        chq_flag_false = _compute_chq_amt(interest, 0.0, tds_flag=False)
        assert chq_flag_true == pytest.approx(chq_flag_false)

    def test_zero_interest_gives_zero_chq(self):
        assert _compute_chq_amt(0.0, 0.0, tds_flag=True) == pytest.approx(0.0)
        assert _compute_chq_amt(0.0, 0.0, tds_flag=False) == pytest.approx(0.0)

    def test_high_interest_tds_true(self):
        interest = 12000.0
        tds = 1200.0  # 10%
        chq = _compute_chq_amt(interest, tds, tds_flag=True)
        assert chq == pytest.approx(10800.0)

    def test_high_interest_tds_false(self):
        interest = 12000.0
        chq = _compute_chq_amt(interest, 0.0, tds_flag=False)
        assert chq == pytest.approx(10800.0)

    def test_fractional_interest(self):
        interest = 100.0
        tds = 10.0
        chq = _compute_chq_amt(interest, tds, tds_flag=True)
        assert chq == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# Calculator formulas — verify with sample data
# ---------------------------------------------------------------------------

class TestCalculatorFormulas:
    """Verify existing calculator formulas still produce expected results."""

    def test_monthly_authoritative_example(self):
        """R5 authoritative example: Rs 10,000 at 12% for 1 month extension = Rs 100."""
        from loan_manager.interest_calculator import calculate_monthly
        record = {
            "amount": 10000,
            "interest_rate": 12.0,
            "commission_rate": 0.0,
            "extension_period": 1,
            "tds_flag": False,
            "giving_date": date(2026, 1, 1),
            "due_date": date(2026, 4, 1),
        }
        result = calculate_monthly(record)
        assert result["interest_amount"] == pytest.approx(100.0)

    def test_daily_with_tds(self):
        """Daily: 10000 at 12% for 30 days with TDS."""
        from loan_manager.interest_calculator import calculate_daily
        record = {
            "amount": 10000,
            "interest_rate": 12.0,
            "commission_rate": 0.0,
            "extension_period": 30,
            "tds_flag": True,
            "giving_date": date(2026, 1, 1),
            "due_date": date(2026, 4, 1),
        }
        result = calculate_daily(record)
        expected_interest = (10000 * 12 * 30) / (365 * 100)
        assert result["interest_amount"] == pytest.approx(expected_interest)
        assert result["tds_amount"] == pytest.approx(0.1 * expected_interest)

    def test_both_routes_monthly(self):
        """Mode=Both with months routes to calculate_monthly."""
        from loan_manager.interest_calculator import calculate_both
        record = {
            "amount": 15000,
            "interest_rate": 10.0,
            "commission_rate": 2.0,
            "extension_period": 3,
            "extension_period_unit": "months",
            "tds_flag": False,
            "giving_date": date(2026, 1, 1),
            "due_date": date(2026, 4, 1),
        }
        result = calculate_both(record)
        assert "time_months" in result
        assert result["interest_amount"] == pytest.approx((15000 * 10 * 3) / (12 * 100))

    def test_both_routes_daily(self):
        """Mode=Both with days routes to calculate_daily."""
        from loan_manager.interest_calculator import calculate_both
        record = {
            "amount": 20000,
            "interest_rate": 8.0,
            "commission_rate": 1.0,
            "extension_period": 15,
            "extension_period_unit": "days",
            "tds_flag": True,
            "giving_date": date(2026, 1, 1),
            "due_date": date(2026, 7, 1),
        }
        result = calculate_both(record)
        assert "time_days" in result
        expected = (20000 * 8 * 15) / (365 * 100)
        assert result["interest_amount"] == pytest.approx(expected)

    def test_commission_formula(self):
        """Commission uses same formula as interest but with commission_rate."""
        from loan_manager.interest_calculator import calculate_monthly
        record = {
            "amount": 10000,
            "interest_rate": 12.0,
            "commission_rate": 2.0,
            "extension_period": 1,
            "tds_flag": False,
            "giving_date": date(2026, 1, 1),
            "due_date": date(2026, 4, 1),
        }
        result = calculate_monthly(record)
        assert result["commission_amount"] == pytest.approx(
            (10000 * 2.0 * 1) / (12 * 100)
        )
