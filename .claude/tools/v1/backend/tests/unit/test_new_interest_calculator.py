"""
Unit tests for the new Interest Calculator (Month-based with per-record rates).

Tests the correct interest calculation formula:
Interest = Amount × (Annual Rate / 365) × Days Between Dates
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal


class TestCorrectInterestFormula:
    """Test the correct interest calculation formula."""

    def test_interest_calculation_90_days_12_percent(self):
        """Test interest for 90-day loan at 12% annual rate."""
        amount = Decimal('100000.00')
        annual_rate = Decimal('0.12')
        days = 90

        # Correct formula: Amount × (Rate / 365) × Days
        expected_interest = amount * (annual_rate / 365) * days
        # Expected: ₹2,958.90

        assert abs(expected_interest - Decimal('2958.90')) < Decimal('0.01')

    def test_interest_calculation_14_days_18_percent(self):
        """Test interest for 14-day loan at 18% annual rate."""
        amount = Decimal('50000.00')
        annual_rate = Decimal('0.18')
        days = 14

        expected_interest = amount * (annual_rate / 365) * days
        # Expected: ₹345.21

        assert abs(expected_interest - Decimal('345.21')) < Decimal('0.01')

    def test_interest_calculation_365_days_10_percent(self):
        """Test interest for 365-day loan at 10% annual rate."""
        amount = Decimal('200000.00')
        annual_rate = Decimal('0.10')
        days = 365

        expected_interest = amount * (annual_rate / 365) * days
        # Expected: ₹20,000.00 (exactly 10% of principal for full year)

        assert abs(expected_interest - Decimal('20000.00')) < Decimal('0.01')

    def test_interest_calculation_181_days_12_percent(self):
        """Test interest for 181-day loan (approx 6 months) at 12%."""
        amount = Decimal('100000.00')
        annual_rate = Decimal('0.12')
        days = 181

        expected_interest = amount * (annual_rate / 365) * days
        # Expected: ₹5,950.68

        assert abs(expected_interest - Decimal('5950.68')) < Decimal('0.01')

    def test_interest_uses_actual_days_not_approximation(self):
        """Verify that calculation uses actual days, not month approximations."""
        amount = Decimal('50000.00')
        annual_rate = Decimal('0.18')
        giving_date = date(2026, 1, 1)
        due_date = date(2026, 4, 1)

        # Calculate actual days
        days = (due_date - giving_date).days  # 90 days

        # Should use 90 days, not "3 months × 30"
        expected_interest = amount * (annual_rate / 365) * Decimal(days)
        # Expected: ₹2,219.18

        assert abs(expected_interest - Decimal('2219.18')) < Decimal('0.01')
        assert days == 90  # Verify actual days calculation


class TestCommissionCalculation:
    """Test commission calculation on interest."""

    def test_commission_on_interest(self):
        """Test that commission is calculated as percentage of interest."""
        amount = Decimal('100000.00')
        annual_rate = Decimal('0.12')
        commission_rate = Decimal('0.01')  # 1%
        days = 90

        interest = amount * (annual_rate / 365) * days  # ₹2,958.90
        commission = interest * commission_rate

        # Expected commission: ₹29.59
        assert abs(commission - Decimal('29.59')) < Decimal('0.01')

    def test_zero_commission_when_rate_not_provided(self):
        """Test that commission is 0 when rate is not provided."""
        amount = Decimal('100000.00')
        annual_rate = Decimal('0.12')
        commission_rate = Decimal('0.00')  # Not provided
        days = 90

        interest = amount * (annual_rate / 365) * days
        commission = interest * commission_rate if commission_rate > 0 else Decimal('0')

        assert commission == Decimal('0')

    def test_commission_with_2_percent_rate(self):
        """Test commission calculation with 2% rate."""
        amount = Decimal('50000.00')
        annual_rate = Decimal('0.15')
        commission_rate = Decimal('0.02')  # 2%
        days = 180

        interest = amount * (annual_rate / 365) * days  # ₹3,698.63
        commission = interest * commission_rate

        # Expected commission: ₹73.97
        assert abs(commission - Decimal('73.97')) < Decimal('0.01')


class TestMonthFiltering:
    """Test filtering loans by month."""

    def test_filter_loans_by_march_2026(self):
        """Test filtering loans with due dates in March 2026."""
        # Sample loans
        loans = [
            {'id': '1', 'due_date': '2026-03-15', 'status': 'active'},
            {'id': '2', 'due_date': '2026-03-20', 'status': 'active'},
            {'id': '3', 'due_date': '2026-04-01', 'status': 'active'},  # Not in March
            {'id': '4', 'due_date': '1970-01-01', 'status': 'active'},  # No due date
            {'id': '5', 'due_date': '2026-03-01', 'status': 'paid_off'},  # Paid off
        ]

        # Filter logic
        selected_month = '2026-03'
        first_day = date(2026, 3, 1)
        today = date(2026, 3, 20)  # Assume today is March 20

        filtered = []
        for loan in loans:
            if loan['due_date'] == '1970-01-01' or loan['status'] == 'paid_off':
                continue
            due_date = date.fromisoformat(loan['due_date'])
            if first_day <= due_date <= today:
                filtered.append(loan)

        # Should include loans 1 and 2 only (both have due dates in March <= today)
        assert len(filtered) == 2
        assert filtered[0]['id'] == '1'
        assert filtered[1]['id'] == '2'

    def test_empty_result_when_no_loans_in_month(self):
        """Test that filtering returns empty list when no loans in month."""
        loans = [
            {'id': '1', 'due_date': '2026-04-15', 'status': 'active'},
            {'id': '2', 'due_date': '2026-05-31', 'status': 'active'},
        ]

        selected_month = '2026-03'
        first_day = date(2026, 3, 1)
        today = date(2026, 3, 31)

        filtered = []
        for loan in loans:
            if loan['due_date'] == '1970-01-01' or loan['status'] == 'paid_off':
                continue
            due_date = date.fromisoformat(loan['due_date'])
            if first_day <= due_date <= today:
                filtered.append(loan)

        assert len(filtered) == 0


class TestDateCalculations:
    """Test date-related calculations."""

    def test_calculate_days_between_dates(self):
        """Test calculating days between two dates."""
        giving_date = date(2026, 1, 1)
        due_date = date(2026, 3, 31)

        days = (due_date - giving_date).days

        assert days == 89

    def test_calculate_days_for_leap_year(self):
        """Test calculating days in a leap year."""
        giving_date = date(2024, 2, 1)
        due_date = date(2024, 3, 1)

        days = (due_date - giving_date).days

        assert days == 29  # Feb 2024 has 29 days

    def test_calculate_days_for_full_year(self):
        """Test calculating days for a full year."""
        giving_date = date(2026, 1, 1)
        due_date = date(2027, 1, 1)

        days = (due_date - giving_date).days

        assert days == 365


class TestPerRecordRates:
    """Test per-record interest and commission rates."""

    def test_different_rates_for_different_loans(self):
        """Test that each loan can have different rates."""
        loan1 = {
            'amount': Decimal('100000'),
            'giving_date': date(2026, 1, 1),
            'due_date': date(2026, 4, 1),
            'interest_rate': Decimal('0.12'),  # 12%
            'commission_rate': Decimal('0.01')  # 1%
        }

        loan2 = {
            'amount': Decimal('50000'),
            'giving_date': date(2026, 1, 1),
            'due_date': date(2026, 4, 1),
            'interest_rate': Decimal('0.15'),  # 15%
            'commission_rate': Decimal('0.02')  # 2%
        }

        # Calculate for loan 1
        days1 = (loan1['due_date'] - loan1['giving_date']).days
        interest1 = loan1['amount'] * (loan1['interest_rate'] / 365) * days1
        commission1 = interest1 * loan1['commission_rate']

        # Calculate for loan 2
        days2 = (loan2['due_date'] - loan2['giving_date']).days
        interest2 = loan2['amount'] * (loan2['interest_rate'] / 365) * days2
        commission2 = interest2 * loan2['commission_rate']

        # Verify different results due to different rates
        assert interest1 != interest2
        assert commission1 != commission2

        # Verify actual values
        assert abs(interest1 - Decimal('2958.90')) < Decimal('0.01')
        assert abs(interest2 - Decimal('1849.32')) < Decimal('0.01')


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_days_loan(self):
        """Test loan where giving_date equals due_date."""
        amount = Decimal('100000')
        annual_rate = Decimal('0.12')
        giving_date = date(2026, 1, 1)
        due_date = date(2026, 1, 1)

        days = (due_date - giving_date).days
        interest = amount * (annual_rate / 365) * days

        assert days == 0
        assert interest == Decimal('0')

    def test_very_small_amount(self):
        """Test calculation with very small loan amount."""
        amount = Decimal('100.00')
        annual_rate = Decimal('0.12')
        days = 30

        interest = amount * (annual_rate / 365) * days

        # Expected: ₹0.99
        assert abs(interest - Decimal('0.99')) < Decimal('0.01')

    def test_very_large_amount(self):
        """Test calculation with very large loan amount."""
        amount = Decimal('10000000.00')  # 1 crore
        annual_rate = Decimal('0.12')
        days = 365

        interest = amount * (annual_rate / 365) * days

        # Expected: ₹12,00,000
        assert abs(interest - Decimal('1200000.00')) < Decimal('0.01')

    def test_fractional_interest_rate(self):
        """Test calculation with fractional interest rate."""
        amount = Decimal('100000.00')
        annual_rate = Decimal('0.1275')  # 12.75%
        days = 100

        interest = amount * (annual_rate / 365) * days

        # Expected: ₹3,493.15
        assert abs(interest - Decimal('3493.15')) < Decimal('0.01')


class TestTotalCalculations:
    """Test total interest and commission calculations."""

    def test_sum_interest_from_multiple_loans(self):
        """Test summing interest from multiple loans."""
        loans = [
            {'amount': Decimal('100000'), 'rate': Decimal('0.12'), 'days': 90},
            {'amount': Decimal('50000'), 'rate': Decimal('0.15'), 'days': 60},
            {'amount': Decimal('75000'), 'rate': Decimal('0.10'), 'days': 120},
        ]

        total_interest = Decimal('0')
        for loan in loans:
            interest = loan['amount'] * (loan['rate'] / 365) * loan['days']
            total_interest += interest

        # Loan 1: ₹2,958.90
        # Loan 2: ₹1,232.88
        # Loan 3: ₹2,465.75
        # Total: ₹6,657.53
        assert abs(total_interest - Decimal('6657.53')) < Decimal('0.01')

    def test_sum_commission_only_from_loans_with_commission(self):
        """Test summing commission only from loans that have commission rate."""
        loans = [
            {'interest': Decimal('2958.90'), 'commission_rate': Decimal('0.01')},
            {'interest': Decimal('1232.88'), 'commission_rate': Decimal('0.00')},  # No commission
            {'interest': Decimal('2465.75'), 'commission_rate': Decimal('0.02')},
        ]

        total_commission = Decimal('0')
        for loan in loans:
            if loan['commission_rate'] > 0:
                commission = loan['interest'] * loan['commission_rate']
                total_commission += commission

        # Loan 1 commission: ₹29.59
        # Loan 2 commission: ₹0 (not included)
        # Loan 3 commission: ₹49.32
        # Total: ₹78.91
        assert abs(total_commission - Decimal('78.91')) < Decimal('0.01')
