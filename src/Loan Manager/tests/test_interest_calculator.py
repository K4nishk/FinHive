"""
Tests for interest_calculator pure calculation functions.

Public API under test (loan_manager.interest_calculator):
    months_between(giving_date: date, due_date: date) -> int
        Returns whole months elapsed; partial month rounds UP.
    calculate_monthly(record: dict) -> dict
        Adds keys: interest_amount, commission_amount, tds_amount, time_months
        Uses BC-05 Interpretation B formulas (confirmed by R5 example):
            Time = extension_period (months)
            Interest = (Amount * interest_rate * extension_period) / (12 * 100)
            Commission = (Amount * commission_rate * extension_period) / (12 * 100)
            TDS = 0.1 * Interest   (when tds_flag=True, else 0.0)
    calculate_daily(record: dict) -> dict
        Adds keys: interest_amount, commission_amount, tds_amount, time_days
        Uses BC-05 Interpretation B formulas (confirmed by R5 example):
            Time = extension_period (days)
            Interest = (Amount * interest_rate * extension_period) / (365 * 100)
            Commission = (Amount * commission_rate * extension_period) / (365 * 100)
            TDS = 0.1 * Interest   (when tds_flag=True, else 0.0)
    calculate_both(record: dict) -> dict
        Routes by extension_period_unit: "months" -> calculate_monthly,
        "days" -> calculate_daily. Raises ValueError for unknown units.

Formula source: BC-05 Interpretation B confirmed (CLARIFICATIONS.md run_2, PD-16).
R5 authoritative example: (10000 * 12 * 1) / (12 * 100) = 100. Time = extension_period = 1.
"""

import pytest
from datetime import date

from loan_manager.interest_calculator import (  # type: ignore[import]
    months_between,
    calculate_monthly,
    calculate_daily,
    calculate_both,
)

TODAY: date = date(2026, 3, 22)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _monthly_record(
    reference_id: str = "2026_01_001",
    borrower_name: str = "b1",
    amount: int = 10000,
    giving_date: date = date(2026, 1, 2),
    due_date: date = date(2026, 4, 2),
    interest_rate: float = 12.0,
    commission_rate: float = 2.0,
    extension_period: int = 0,
    tds_flag: bool = False,
) -> dict:
    return {
        "reference_id": reference_id,
        "borrower_name": borrower_name,
        "amount": amount,
        "giving_date": giving_date,
        "due_date": due_date,
        "interest_rate": interest_rate,
        "commission_rate": commission_rate,
        "extension_period": extension_period,
        "extension_period_unit": "months",
        "tds_flag": tds_flag,
    }


def _daily_record(
    reference_id: str = "2026_01_001",
    borrower_name: str = "b1",
    amount: int = 10000,
    giving_date: date = date(2026, 1, 2),
    due_date: date = date(2026, 4, 2),
    interest_rate: float = 12.0,
    commission_rate: float = 2.0,
    extension_period: int = 0,
    tds_flag: bool = False,
) -> dict:
    return {
        "reference_id": reference_id,
        "borrower_name": borrower_name,
        "amount": amount,
        "giving_date": giving_date,
        "due_date": due_date,
        "interest_rate": interest_rate,
        "commission_rate": commission_rate,
        "extension_period": extension_period,
        "extension_period_unit": "days",
        "tds_flag": tds_flag,
    }


# ---------------------------------------------------------------------------
# months_between
# ---------------------------------------------------------------------------

class TestMonthsBetween:
    def test_exact_three_months(self) -> None:
        """2026-01-02 to 2026-04-02 = exactly 3 months."""
        assert months_between(date(2026, 1, 2), date(2026, 4, 2)) == 3

    def test_exact_one_month(self) -> None:
        assert months_between(date(2026, 1, 1), date(2026, 2, 1)) == 1

    def test_exact_twelve_months(self) -> None:
        assert months_between(date(2026, 1, 15), date(2027, 1, 15)) == 12

    def test_same_day_returns_zero(self) -> None:
        """Same giving_date and due_date = 0 months elapsed."""
        assert months_between(date(2026, 3, 22), date(2026, 3, 22)) == 0

    def test_partial_month_rounds_up(self) -> None:
        """Jan 15 to Feb 16 = 1 month + 1 day → rounds UP to 2."""
        assert months_between(date(2026, 1, 15), date(2026, 2, 16)) == 2

    def test_one_day_short_of_full_month_rounds_up(self) -> None:
        """Jan 1 to Jan 31 = 0 full months + 30 days → rounds UP to 1."""
        assert months_between(date(2026, 1, 1), date(2026, 1, 31)) == 1

    def test_one_day_into_new_month_rounds_up(self) -> None:
        """Mar 1 to Apr 2 = 1 month + 1 day → rounds UP to 2."""
        assert months_between(date(2026, 3, 1), date(2026, 4, 2)) == 2

    @pytest.mark.parametrize("giving,due,expected", [
        (date(2026, 1, 4),  date(2026, 5, 4),  4),   # b2: exact 4 months
        (date(2026, 2, 6),  date(2026, 5, 6),  3),   # b3: exact 3 months
        (date(2026, 2, 7),  date(2026, 6, 7),  4),   # b4: exact 4 months
        (date(2026, 2, 8),  date(2026, 6, 8),  4),   # b5: exact 4 months
        (date(2026, 2, 8),  date(2026, 7, 8),  5),   # b6: exact 5 months
        (date(2026, 2, 15), date(2026, 7, 15), 5),   # b7: exact 5 months
        (date(2026, 2, 18), date(2026, 6, 18), 4),   # b8: exact 4 months
        (date(2026, 2, 20), date(2026, 6, 20), 4),   # b9: exact 4 months
        (date(2026, 2, 25), date(2026, 5, 25), 3),   # b10: exact 3 months
        (date(2026, 2, 28), date(2026, 5, 28), 3),   # b11: exact 3 months
    ])
    def test_months_between_sample_records(
        self, giving: date, due: date, expected: int
    ) -> None:
        assert months_between(giving, due) == expected


# ---------------------------------------------------------------------------
# calculate_monthly
# ---------------------------------------------------------------------------

class TestCalculateMonthly:
    def test_b1_exact_three_months_no_extension_no_tds(self) -> None:
        """b1: amount=10000, extension_period=0, rate=12%, commission=2%, no TDS.

        Time = extension_period = 0
        Interest = (10000 * 12 * 0) / (12 * 100) = 0.00
        Commission = (10000 * 2 * 0) / (12 * 100) = 0.00
        TDS = 0.00
        """
        record = _monthly_record(
            amount=10000,
            giving_date=date(2026, 1, 2),
            due_date=date(2026, 4, 2),
            interest_rate=12.0,
            commission_rate=2.0,
            extension_period=0,
            tds_flag=False,
        )
        result = calculate_monthly(record)
        assert result["time_months"] == 0
        assert abs(result["interest_amount"] - 0.0) < 0.01
        assert abs(result["commission_amount"] - 0.0) < 0.01
        assert abs(result["tds_amount"] - 0.0) < 0.01

    def test_monthly_with_extension_period(self) -> None:
        """extension_period=2, rate=12%, amount=10000:

        Time = extension_period = 2
        Interest = (10000 * 12 * 2) / (12 * 100) = 200.00
        Commission = (10000 * 2 * 2) / (12 * 100) = 33.33...
        """
        record = _monthly_record(
            amount=10000,
            giving_date=date(2026, 1, 2),
            due_date=date(2026, 4, 2),
            interest_rate=12.0,
            commission_rate=2.0,
            extension_period=2,
            tds_flag=False,
        )
        result = calculate_monthly(record)
        assert result["time_months"] == 2
        assert abs(result["interest_amount"] - 200.0) < 0.01

    def test_monthly_tds_flag_true(self) -> None:
        """TDS = 0.1 * Interest when tds_flag=True.

        extension_period=1, amount=10000, rate=12%:
        Time = 1, interest = (10000 * 12 * 1) / (12 * 100) = 100.00
        TDS = 0.1 * 100.00 = 10.00
        """
        record = _monthly_record(
            amount=10000,
            giving_date=date(2026, 1, 2),
            due_date=date(2026, 4, 2),
            interest_rate=12.0,
            commission_rate=2.0,
            extension_period=1,
            tds_flag=True,
        )
        result = calculate_monthly(record)
        assert abs(result["interest_amount"] - 100.0) < 0.01
        assert abs(result["tds_amount"] - 10.0) < 0.01

    def test_monthly_tds_flag_false_gives_zero_tds(self) -> None:
        record = _monthly_record(tds_flag=False)
        result = calculate_monthly(record)
        assert abs(result["tds_amount"] - 0.0) < 0.01

    def test_monthly_zero_interest_rate(self) -> None:
        """Zero interest rate -> interest=0, commission still calculated.

        extension_period=3, amount=10000, commission_rate=2%:
        interest = 0.0
        commission = (10000 * 2 * 3) / (12 * 100) = 50.00
        """
        record = _monthly_record(
            amount=10000,
            giving_date=date(2026, 1, 2),
            due_date=date(2026, 4, 2),
            interest_rate=0.0,
            commission_rate=2.0,
            extension_period=3,
            tds_flag=False,
        )
        result = calculate_monthly(record)
        assert abs(result["interest_amount"] - 0.0) < 0.01
        assert abs(result["commission_amount"] - 50.0) < 0.01
        assert abs(result["tds_amount"] - 0.0) < 0.01

    def test_monthly_zero_commission_rate(self) -> None:
        """Zero commission rate -> commission=0, interest still calculated.

        extension_period=3, amount=10000, interest_rate=12%:
        interest = (10000 * 12 * 3) / (12 * 100) = 300.00
        commission = 0.0
        """
        record = _monthly_record(
            amount=10000,
            giving_date=date(2026, 1, 2),
            due_date=date(2026, 4, 2),
            interest_rate=12.0,
            commission_rate=0.0,
            extension_period=3,
            tds_flag=False,
        )
        result = calculate_monthly(record)
        assert abs(result["interest_amount"] - 300.0) < 0.01
        assert abs(result["commission_amount"] - 0.0) < 0.01

    def test_monthly_both_rates_zero(self) -> None:
        """All monetary outputs are zero when both rates are zero."""
        record = _monthly_record(interest_rate=0.0, commission_rate=0.0)
        result = calculate_monthly(record)
        assert abs(result["interest_amount"] - 0.0) < 0.01
        assert abs(result["commission_amount"] - 0.0) < 0.01
        assert abs(result["tds_amount"] - 0.0) < 0.01

    def test_monthly_extension_period_one_gives_r5_example(self) -> None:
        """R5 authoritative example: Rs 10,000 at 12% for 1-month extension = Rs 100.

        Time = extension_period = 1
        Interest = (10000 * 12 * 1) / (12 * 100) = 100.00
        """
        record = _monthly_record(
            amount=10000,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
            interest_rate=12.0,
            commission_rate=0.0,
            extension_period=1,
            tds_flag=False,
        )
        result = calculate_monthly(record)
        assert result["time_months"] == 1
        assert abs(result["interest_amount"] - 100.0) < 0.01

    def test_monthly_result_preserves_input_fields(self) -> None:
        """calculate_monthly must return a dict that includes the original fields."""
        record = _monthly_record(amount=10000)
        result = calculate_monthly(record)
        assert result["amount"] == 10000
        assert result["reference_id"] == "2026_01_001"

    def test_monthly_tds_equals_ten_percent_of_interest(self) -> None:
        """TDS is exactly 10% of interest_amount when tds_flag=True."""
        record = _monthly_record(
            amount=15000,
            giving_date=date(2026, 2, 6),
            due_date=date(2026, 5, 6),
            interest_rate=10.0,
            commission_rate=1.0,
            extension_period=1,
            tds_flag=True,
        )
        result = calculate_monthly(record)
        assert abs(result["tds_amount"] - 0.1 * result["interest_amount"]) < 0.001

    @pytest.mark.parametrize("reference_id,amount,giving,due,rate,comm,ext,tds,exp_time,exp_interest,exp_commission", [
        # b1: ext=0 -> Time=0, interest=0, commission=0
        ("2026_01_001", 10000, date(2026, 1, 2), date(2026, 4, 2), 12.0, 2.0, 0, False, 0, 0.0, 0.0),
        # b3: ext=0 -> Time=0, interest=0, commission=0
        ("2026_02_001", 15000, date(2026, 2, 6), date(2026, 5, 6), 10.0, 1.5, 0, False, 0, 0.0, 0.0),
        # b4: ext=1 -> Time=1, interest=(20000*8*1)/(12*100)=133.33, commission=(20000*1*1)/(12*100)=16.67
        ("2026_02_002", 20000, date(2026, 2, 7), date(2026, 6, 7), 8.0, 1.0, 1, False, 1, 133.33, 16.67),
    ])
    def test_monthly_parametrized_records(
        self,
        reference_id: str,
        amount: int,
        giving: date,
        due: date,
        rate: float,
        comm: float,
        ext: int,
        tds: bool,
        exp_time: int,
        exp_interest: float,
        exp_commission: float,
    ) -> None:
        record = _monthly_record(
            reference_id=reference_id,
            amount=amount,
            giving_date=giving,
            due_date=due,
            interest_rate=rate,
            commission_rate=comm,
            extension_period=ext,
            tds_flag=tds,
        )
        result = calculate_monthly(record)
        assert result["time_months"] == exp_time
        assert abs(result["interest_amount"] - exp_interest) < 0.01
        assert abs(result["commission_amount"] - exp_commission) < 0.01


# ---------------------------------------------------------------------------
# calculate_daily
# ---------------------------------------------------------------------------

class TestCalculateDaily:
    def test_b1_daily_exact_days_no_extension_no_tds(self) -> None:
        """extension_period=0 -> Time=0, interest=0, commission=0, tds=0."""
        record = _daily_record(
            amount=10000,
            giving_date=date(2026, 1, 2),
            due_date=date(2026, 4, 2),
            interest_rate=12.0,
            commission_rate=2.0,
            extension_period=0,
            tds_flag=False,
        )
        result = calculate_daily(record)
        assert result["time_days"] == 0
        assert abs(result["interest_amount"] - 0.0) < 0.01
        assert abs(result["commission_amount"] - 0.0) < 0.01
        assert abs(result["tds_amount"] - 0.0) < 0.01

    def test_daily_with_extension_period(self) -> None:
        """extension_period=30 -> Time=30 (giving/due dates do not affect calculation).

        Interest = (10000 * 12 * 30) / (365 * 100) = 98.63...
        """
        record = _daily_record(
            amount=10000,
            giving_date=date(2026, 1, 2),
            due_date=date(2026, 4, 2),
            interest_rate=12.0,
            commission_rate=2.0,
            extension_period=30,
            tds_flag=False,
        )
        result = calculate_daily(record)
        assert result["time_days"] == 30
        expected_interest = (10000 * 12.0 * 30) / (365 * 100)
        assert abs(result["interest_amount"] - expected_interest) < 0.01

    def test_daily_tds_flag_true(self) -> None:
        """TDS = 0.1 * interest_amount when tds_flag=True."""
        record = _daily_record(
            amount=10000,
            giving_date=date(2026, 1, 2),
            due_date=date(2026, 4, 2),
            interest_rate=12.0,
            commission_rate=2.0,
            extension_period=0,
            tds_flag=True,
        )
        result = calculate_daily(record)
        assert abs(result["tds_amount"] - 0.1 * result["interest_amount"]) < 0.001

    def test_daily_tds_flag_false_gives_zero_tds(self) -> None:
        record = _daily_record(tds_flag=False)
        result = calculate_daily(record)
        assert abs(result["tds_amount"] - 0.0) < 0.01

    def test_daily_zero_interest_rate(self) -> None:
        """Zero interest rate -> interest=0, commission calculated from extension_period.

        extension_period=30, commission_rate=2%, amount=10000:
        commission = (10000 * 2 * 30) / (365 * 100) = 16.44...
        """
        record = _daily_record(
            amount=10000,
            giving_date=date(2026, 1, 2),
            due_date=date(2026, 4, 2),
            interest_rate=0.0,
            commission_rate=2.0,
            extension_period=30,
            tds_flag=False,
        )
        result = calculate_daily(record)
        assert abs(result["interest_amount"] - 0.0) < 0.01
        assert result["commission_amount"] > 0.0
        assert abs(result["tds_amount"] - 0.0) < 0.01

    def test_daily_zero_commission_rate(self) -> None:
        """Zero commission rate -> commission=0, interest calculated from extension_period.

        extension_period=30, interest_rate=12%, amount=10000:
        interest = (10000 * 12 * 30) / (365 * 100) = 98.63...
        """
        record = _daily_record(
            amount=10000,
            giving_date=date(2026, 1, 2),
            due_date=date(2026, 4, 2),
            interest_rate=12.0,
            commission_rate=0.0,
            extension_period=30,
            tds_flag=False,
        )
        result = calculate_daily(record)
        assert result["interest_amount"] > 0.0
        assert abs(result["commission_amount"] - 0.0) < 0.01

    def test_daily_both_rates_zero(self) -> None:
        record = _daily_record(interest_rate=0.0, commission_rate=0.0)
        result = calculate_daily(record)
        assert abs(result["interest_amount"] - 0.0) < 0.01
        assert abs(result["commission_amount"] - 0.0) < 0.01
        assert abs(result["tds_amount"] - 0.0) < 0.01

    def test_daily_result_preserves_input_fields(self) -> None:
        record = _daily_record(amount=15000)
        result = calculate_daily(record)
        assert result["amount"] == 15000
        assert result["reference_id"] == "2026_01_001"

    def test_daily_time_is_extension_period_only(self) -> None:
        """time_days == extension_period. giving/due dates do not affect time."""
        ext = 15
        record = _daily_record(
            giving_date=date(2026, 2, 8),
            due_date=date(2026, 6, 8),
            extension_period=ext,
        )
        result = calculate_daily(record)
        assert result["time_days"] == ext

    @pytest.mark.parametrize("reference_id,amount,giving,due,rate,comm,ext,tds", [
        ("2026_01_001", 10000, date(2026, 1, 2),  date(2026, 4, 2),  12.0, 2.0, 0, False),
        ("2026_01_002", 10000, date(2026, 1, 4),  date(2026, 5, 4),  10.0, 1.5, 0, True),
        ("2026_02_001", 15000, date(2026, 2, 6),  date(2026, 5, 6),   8.0, 1.0, 7, False),
        ("2026_02_002", 20000, date(2026, 2, 7),  date(2026, 6, 7),  12.0, 2.0, 0, True),
        ("2026_02_008", 20000, date(2026, 2, 18), date(2026, 6, 18), 15.0, 3.0, 0, False),
    ])
    def test_daily_formula_matches_manual_calculation(
        self,
        reference_id: str,
        amount: int,
        giving: date,
        due: date,
        rate: float,
        comm: float,
        ext: int,
        tds: bool,
    ) -> None:
        """Verify formula: Interest = (amount * rate * time) / (365 * 100)."""
        record = _daily_record(
            reference_id=reference_id,
            amount=amount,
            giving_date=giving,
            due_date=due,
            interest_rate=rate,
            commission_rate=comm,
            extension_period=ext,
            tds_flag=tds,
        )
        result = calculate_daily(record)
        time_days = ext
        expected_interest = (amount * rate * time_days) / (365 * 100)
        expected_commission = (amount * comm * time_days) / (365 * 100)
        expected_tds = 0.1 * expected_interest if tds else 0.0

        assert result["time_days"] == time_days
        assert abs(result["interest_amount"] - expected_interest) < 0.01
        assert abs(result["commission_amount"] - expected_commission) < 0.01
        assert abs(result["tds_amount"] - expected_tds) < 0.001


# ---------------------------------------------------------------------------
# TDS cross-check: monthly vs daily TDS behaves identically given same flag
# ---------------------------------------------------------------------------

class TestTDSCalculation:
    def test_tds_is_ten_percent_of_interest_monthly(self) -> None:
        """TDS = 0.1 * interest_amount for monthly mode."""
        record = _monthly_record(
            amount=20000,
            interest_rate=15.0,
            commission_rate=3.0,
            extension_period=2,
            tds_flag=True,
        )
        result = calculate_monthly(record)
        assert abs(result["tds_amount"] - 0.1 * result["interest_amount"]) < 0.0001

    def test_tds_is_ten_percent_of_interest_daily(self) -> None:
        """TDS = 0.1 * interest_amount for daily mode."""
        record = _daily_record(
            amount=20000,
            interest_rate=15.0,
            commission_rate=3.0,
            extension_period=10,
            tds_flag=True,
        )
        result = calculate_daily(record)
        assert abs(result["tds_amount"] - 0.1 * result["interest_amount"]) < 0.0001

    def test_tds_zero_when_flag_false_monthly(self) -> None:
        record = _monthly_record(tds_flag=False, interest_rate=12.0)
        result = calculate_monthly(record)
        assert result["tds_amount"] == 0.0

    def test_tds_zero_when_flag_false_daily(self) -> None:
        record = _daily_record(tds_flag=False, interest_rate=12.0)
        result = calculate_daily(record)
        assert result["tds_amount"] == 0.0

    def test_tds_independent_of_commission(self) -> None:
        """TDS applies to interest only, not commission.

        extension_period=1, amount=10000, interest_rate=12%, commission_rate=100%:
        interest = (10000 * 12 * 1) / (12 * 100) = 100.00
        commission = (10000 * 100 * 1) / (12 * 100) = 833.33...
        tds = 0.1 * 100.00 = 10.00 < 833.33 (commission)
        """
        record = _monthly_record(
            amount=10000,
            giving_date=date(2026, 1, 2),
            due_date=date(2026, 4, 2),
            interest_rate=12.0,
            commission_rate=100.0,
            extension_period=1,
            tds_flag=True,
        )
        result = calculate_monthly(record)
        assert abs(result["tds_amount"] - 0.1 * result["interest_amount"]) < 0.0001
        assert result["tds_amount"] < result["commission_amount"]


# ---------------------------------------------------------------------------
# calculate_both
# ---------------------------------------------------------------------------

class TestCalculateBoth:
    def test_both_routes_months(self) -> None:
        """extension_period_unit="months" routes to calculate_monthly.

        extension_period=2, amount=10000, rate=12%:
        interest = (10000 * 12 * 2) / (12 * 100) = 200.00
        """
        record = _monthly_record(extension_period=2, interest_rate=12.0, commission_rate=2.0)
        result = calculate_both(record)
        assert "time_months" in result
        assert abs(result["interest_amount"] - 200.0) < 0.01

    def test_both_routes_days(self) -> None:
        """extension_period_unit="days" routes to calculate_daily.

        extension_period=30, amount=10000, rate=12%:
        interest = (10000 * 12.0 * 30) / (365 * 100) = 98.63...
        """
        record = _daily_record(extension_period=30, interest_rate=12.0, commission_rate=2.0)
        result = calculate_both(record)
        assert "time_days" in result
        expected = (10000 * 12.0 * 30) / (365 * 100)
        assert abs(result["interest_amount"] - expected) < 0.01

    def test_both_invalid_unit_raises(self) -> None:
        """Unknown extension_period_unit raises ValueError."""
        record = _monthly_record(extension_period=1)
        record["extension_period_unit"] = "weeks"
        with pytest.raises(ValueError):
            calculate_both(record)
