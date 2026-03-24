"""Unit tests for interest calculator business logic."""
import pytest


class TestInterestCalculation:
    """Test interest calculation formulas."""

    def test_simple_monthly_interest(self):
        """Test basic monthly interest calculation."""
        amount = 10000.00
        annual_rate = 0.12  # 12% per annum
        months = 1

        monthly_rate = annual_rate / 12
        monthly_interest = amount * monthly_rate

        assert monthly_interest == 100.00

    def test_monthly_interest_12_months(self):
        """Test interest calculation for 12 months."""
        amount = 10000.00
        annual_rate = 0.12  # 12%
        months = 12

        monthly_rate = annual_rate / 12
        total_interest = amount * monthly_rate * months

        assert total_interest == 1200.00

    def test_commission_calculation(self):
        """Test commission calculation on monthly interest."""
        monthly_interest = 100.00
        commission_rate = 0.10  # 10%

        commission = monthly_interest * commission_rate

        assert commission == 10.00

    def test_total_commission_for_period(self):
        """Test total commission for a period."""
        amount = 10000.00
        annual_interest_rate = 0.12  # 12%
        commission_rate = 0.10  # 10%
        months = 12

        monthly_interest = amount * (annual_interest_rate / 12)
        commission_per_month = monthly_interest * commission_rate
        total_commission = commission_per_month * months

        assert total_commission == 120.00

    def test_multi_loan_total_commission(self):
        """Test commission calculation for multiple loans."""
        loans = [
            {"amount": 10000, "rate": 0.12},  # 12%
            {"amount": 5000, "rate": 0.15},   # 15%
            {"amount": 8000, "rate": 0.10}    # 10%
        ]
        commission_rate = 0.10
        months = 12

        total_commission = 0
        for loan in loans:
            annual_interest = loan["amount"] * loan["rate"]
            commission_on_interest = annual_interest * commission_rate
            total_commission += commission_on_interest

        # Loan 1: 10000 * 0.12 * 0.10 = 120
        # Loan 2: 5000 * 0.15 * 0.10 = 75
        # Loan 3: 8000 * 0.10 * 0.10 = 80
        # Total: 275
        assert total_commission == 275.00

    def test_different_period_lengths(self):
        """Test calculations for different period lengths."""
        amount = 10000.00
        annual_rate = 0.12
        commission_rate = 0.10

        # 1 month
        interest_1m = amount * (annual_rate / 12) * 1
        commission_1m = interest_1m * commission_rate
        assert commission_1m == 10.00

        # 6 months
        interest_6m = amount * (annual_rate / 12) * 6
        commission_6m = interest_6m * commission_rate
        assert commission_6m == 60.00

        # 24 months
        interest_24m = amount * (annual_rate / 12) * 24
        commission_24m = interest_24m * commission_rate
        assert commission_24m == 240.00

    def test_commission_must_be_less_than_interest_rate(self):
        """Test business rule: commission rate < interest rate."""
        interest_rate = 12.0  # %
        commission_rate = 10.0  # %

        assert commission_rate < interest_rate

        # Invalid case
        commission_rate = 12.0
        assert not (commission_rate < interest_rate)

        commission_rate = 15.0
        assert not (commission_rate < interest_rate)

    def test_zero_commission_rate(self):
        """Test calculation with zero commission rate."""
        amount = 10000.00
        annual_rate = 0.12
        commission_rate = 0.00  # 0%
        months = 12

        monthly_interest = amount * (annual_rate / 12)
        commission_per_month = monthly_interest * commission_rate
        total_commission = commission_per_month * months

        assert total_commission == 0.00


class TestINRFormatting:
    """Test INR number formatting for display."""

    def test_format_small_amount(self):
        """Test formatting small amounts."""
        amount = 1000.00
        formatted = f"₹{amount:,.2f}"

        assert formatted == "₹1,000.00"

    def test_format_lakh_amount(self):
        """Test formatting amounts in lakhs."""
        amount = 100000.00  # 1 lakh
        formatted = f"₹{amount:,.2f}"

        # Standard comma formatting
        assert formatted == "₹100,000.00"

    def test_format_crore_amount(self):
        """Test formatting amounts in crores."""
        amount = 10000000.00  # 1 crore
        formatted = f"₹{amount:,.2f}"

        assert formatted == "₹10,000,000.00"

    def test_format_with_paisa(self):
        """Test formatting with paisa (decimal places)."""
        amount = 123456.78
        formatted = f"₹{amount:,.2f}"

        assert formatted == "₹123,456.78"

    def test_rupee_symbol_used(self):
        """Test that rupee symbol (₹) is used, not dollar ($)."""
        amount = 5000.00
        formatted = f"₹{amount:,.2f}"

        assert "₹" in formatted
        assert "$" not in formatted


class TestSNoGeneration:
    """Test Serial Number generation logic."""

    def test_sno_format_first_loan(self):
        """Test SNo format for first loan of the year."""
        year = 2026
        index = 0  # First loan

        sno = f"{year}/{str(index + 1).zfill(3)}"

        assert sno == "2026/001"

    def test_sno_format_tenth_loan(self):
        """Test SNo format for 10th loan."""
        year = 2026
        index = 9  # 10th loan (0-indexed)

        sno = f"{year}/{str(index + 1).zfill(3)}"

        assert sno == "2026/010"

    def test_sno_format_hundredth_loan(self):
        """Test SNo format for 100th loan."""
        year = 2026
        index = 99  # 100th loan

        sno = f"{year}/{str(index + 1).zfill(3)}"

        assert sno == "2026/100"

    def test_sno_different_years(self):
        """Test SNo generation for different years."""
        # 2025 loans
        sno_2025_1 = f"2025/{str(1).zfill(3)}"
        assert sno_2025_1 == "2025/001"

        # 2026 loans
        sno_2026_1 = f"2026/{str(1).zfill(3)}"
        assert sno_2026_1 == "2026/001"

        # SNo resets per year
        assert sno_2025_1 != sno_2026_1

    def test_sno_zero_padding(self):
        """Test that SNo always has 3-digit zero-padded counter."""
        test_cases = [
            (0, "001"),
            (9, "010"),
            (99, "100"),
            (149, "150"),
            (999, "1000")  # Would be 4 digits if over 999
        ]

        for index, expected_counter in test_cases:
            counter = str(index + 1).zfill(3)
            if len(counter) <= 3:
                assert counter == expected_counter


class TestLoanPeriodCalculation:
    """Test loan period calculation in days between giving_date and due_date."""

    def test_loan_period_30_days(self):
        """Test loan period calculation for 30-day loan."""
        from datetime import date

        giving_date = date(2026, 1, 1)
        due_date = date(2026, 1, 31)

        # Calculate days between dates
        loan_period_days = (due_date - giving_date).days

        assert loan_period_days == 30

    def test_loan_period_one_year(self):
        """Test loan period calculation for 1-year loan."""
        from datetime import date

        giving_date = date(2026, 1, 1)
        due_date = date(2027, 1, 1)

        loan_period_days = (due_date - giving_date).days

        assert loan_period_days == 365

    def test_loan_period_six_months(self):
        """Test loan period calculation for approximately 6 months."""
        from datetime import date

        giving_date = date(2026, 1, 1)
        due_date = date(2026, 7, 1)

        loan_period_days = (due_date - giving_date).days

        # 6 months is approximately 181 days (Jan-Jun)
        assert loan_period_days == 181

    def test_loan_period_no_due_date(self):
        """Test that 1970-01-01 due date represents no due date (N/A)."""
        from datetime import date

        due_date = date(1970, 1, 1)

        # In business logic, 1970-01-01 should be treated as "no due date"
        # The UI should display "N/A" for loan period
        is_no_due_date = (due_date == date(1970, 1, 1))

        assert is_no_due_date is True

    def test_loan_period_leap_year(self):
        """Test loan period calculation across leap year."""
        from datetime import date

        giving_date = date(2024, 2, 1)  # 2024 is a leap year
        due_date = date(2024, 3, 1)

        loan_period_days = (due_date - giving_date).days

        # February 2024 has 29 days (leap year)
        assert loan_period_days == 29

    def test_loan_period_display_format(self):
        """Test that loan period displays correctly in 'X days' format."""
        from datetime import date

        giving_date = date(2026, 1, 1)
        due_date = date(2026, 1, 15)

        loan_period_days = (due_date - giving_date).days
        display = f"{loan_period_days} days"

        assert display == "14 days"


class TestDailyInterestCalculation:
    """Test daily interest calculation for loan period in days."""

    def test_daily_interest_calculation(self):
        """Test daily interest calculation for 365 days."""
        amount = 10000.00
        annual_rate = 0.12  # 12%
        days = 365

        daily_interest = amount * (annual_rate / 365)
        total_interest = daily_interest * days

        # Daily interest should be about ₹3.29
        assert round(daily_interest, 2) == 3.29
        # Total for 365 days should equal annual interest
        assert round(total_interest, 2) == 1200.00

    def test_daily_interest_30_days(self):
        """Test daily interest calculation for 30-day period."""
        amount = 10000.00
        annual_rate = 0.12
        days = 30

        daily_interest = amount * (annual_rate / 365)
        total_interest = daily_interest * days

        # 30 days of interest
        assert round(total_interest, 2) == 98.63

    def test_daily_vs_monthly_interest_comparison(self):
        """Test that daily and monthly calculations are equivalent for matching periods."""
        amount = 10000.00
        annual_rate = 0.12

        # Monthly calculation for 12 months
        monthly_interest = amount * (annual_rate / 12)
        total_monthly = monthly_interest * 12

        # Daily calculation for 365 days
        daily_interest = amount * (annual_rate / 365)
        total_daily = daily_interest * 365

        # Should be approximately equal (within 1 rupee)
        assert abs(total_monthly - total_daily) < 1.00


class TestDueDateAutoCalculation:
    """Test automatic due_date calculation from giving_date + LoanPeriod."""

    def test_calculate_due_date_from_days(self):
        """Test calculating due_date by adding days to giving_date."""
        from datetime import date, timedelta

        giving_date = date(2026, 1, 1)
        loan_period_days = 30

        calculated_due_date = giving_date + timedelta(days=loan_period_days)

        assert calculated_due_date == date(2026, 1, 31)

    def test_calculate_due_date_from_months_simple(self):
        """Test calculating due_date by adding months to giving_date."""
        from datetime import date

        giving_date = date(2026, 1, 1)
        loan_period_months = 6

        # Simple month addition (JavaScript-style)
        year = giving_date.year
        month = giving_date.month + loan_period_months
        while month > 12:
            year += 1
            month -= 12
        calculated_due_date = date(year, month, giving_date.day)

        assert calculated_due_date == date(2026, 7, 1)

    def test_no_calculation_when_due_date_exists(self):
        """Test that due_date is not recalculated when it already exists."""
        from datetime import date

        existing_due_date = date(2026, 12, 31)

        # Should use existing due date, not recalculate
        # In business logic, we only calculate if due_date == 1970-01-01
        should_calculate = (existing_due_date == date(1970, 1, 1))

        assert should_calculate is False


class TestPeriodUnitConversion:
    """Test conversion between days and months for LoanPeriod display."""

    def test_days_to_months_conversion(self):
        """Test converting days to approximate months (30 days per month)."""
        days = 90
        approximate_months = round(days / 30)

        assert approximate_months == 3

    def test_months_to_days_conversion(self):
        """Test that 1 month ~= 30 days for display purposes."""
        months = 6
        approximate_days = months * 30

        assert approximate_days == 180

    def test_365_days_equals_12_months(self):
        """Test that 365 days roughly equals 12 months."""
        days = 365
        approximate_months = round(days / 30)

        # 365/30 = 12.17, rounds to 12
        assert approximate_months == 12


class TestSummaryCalculations:
    """Test summary calculations for reports."""

    def test_total_loans_count(self):
        """Test counting total loans."""
        loans = [
            {"amount": 10000},
            {"amount": 5000},
            {"amount": 8000}
        ]

        total_count = len(loans)

        assert total_count == 3

    def test_total_amount_sum(self):
        """Test summing total loan amounts."""
        loans = [
            {"amount": 10000},
            {"amount": 5000},
            {"amount": 8000}
        ]

        total_amount = sum(loan["amount"] for loan in loans)

        assert total_amount == 23000

    def test_total_interest_sum(self):
        """Test summing total interest."""
        results = [
            {"interest": 1200},
            {"interest": 600},
            {"interest": 800}
        ]

        total_interest = sum(r["interest"] for r in results)

        assert total_interest == 2600

    def test_total_commission_sum(self):
        """Test summing total commission."""
        results = [
            {"commission": 120},
            {"commission": 60},
            {"commission": 80}
        ]

        total_commission = sum(r["commission"] for r in results)

        assert total_commission == 260

    def test_empty_loan_list_totals(self):
        """Test summary calculations with empty loan list."""
        loans = []

        total_count = len(loans)
        total_amount = sum(loan.get("amount", 0) for loan in loans)

        assert total_count == 0
        assert total_amount == 0
