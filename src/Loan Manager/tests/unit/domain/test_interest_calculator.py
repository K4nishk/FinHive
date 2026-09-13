"""InterestCalculator unit tests."""
from decimal import Decimal

import pytest

from loan_manager.domain.services.interest_calculator import InterestCalculator
from loan_manager.domain.value_objects.status import ExtensionPeriodUnit


class TestInterestCalculatorMonthly:
    def test_basic_monthly(self):
        # (10000 * 12 * 3) / (12 * 100) = 300.00
        result = InterestCalculator.calculate_monthly(10000, Decimal("12"), 3)
        assert result == Decimal("300.00")

    def test_monthly_single_period(self):
        # (10000 * 12 * 1) / 1200 = 100.00
        result = InterestCalculator.calculate_monthly(10000, Decimal("12"), 1)
        assert result == Decimal("100.00")

    def test_monthly_large_amount(self):
        # (100000 * 18 * 6) / 1200 = 9000.00
        result = InterestCalculator.calculate_monthly(100000, Decimal("18"), 6)
        assert result == Decimal("9000.00")

    def test_monthly_fractional_rate(self):
        # (10000 * 7.5 * 4) / 1200 = 250.00
        result = InterestCalculator.calculate_monthly(10000, Decimal("7.5"), 4)
        assert result == Decimal("250.00")


class TestInterestCalculatorDaily:
    def test_basic_daily(self):
        # (10000 * 12 * 90) / (365 * 100) = 295.890... -> 295.89
        result = InterestCalculator.calculate_daily(10000, Decimal("12"), 90)
        assert result == Decimal("295.89")

    def test_daily_single_day(self):
        # (10000 * 12 * 1) / 36500 = 3.287... -> 3.29
        result = InterestCalculator.calculate_daily(10000, Decimal("12"), 1)
        assert result == Decimal("3.29")

    def test_daily_full_year(self):
        # (10000 * 12 * 365) / 36500 = 1200.00
        result = InterestCalculator.calculate_daily(10000, Decimal("12"), 365)
        assert result == Decimal("1200.00")


class TestTdsAndChq:
    def test_tds_basic(self):
        # 0.1 * 300 = 30.00
        result = InterestCalculator.calculate_tds(Decimal("300.00"))
        assert result == Decimal("30.00")

    def test_tds_fractional(self):
        # 0.1 * 295.89 = 29.589 -> 29.59
        result = InterestCalculator.calculate_tds(Decimal("295.89"))
        assert result == Decimal("29.59")

    def test_chq_basic(self):
        # 300 - 30 = 270.00
        result = InterestCalculator.calculate_chq(Decimal("300.00"), Decimal("30.00"))
        assert result == Decimal("270.00")

    def test_chq_with_fractional(self):
        # 295.89 - 29.59 = 266.30
        result = InterestCalculator.calculate_chq(Decimal("295.89"), Decimal("29.59"))
        assert result == Decimal("266.30")


class TestCalculateDispatch:
    def test_dispatch_monthly(self):
        result = InterestCalculator.calculate(10000, Decimal("12"), 3, ExtensionPeriodUnit.MONTHS)
        assert result == Decimal("300.00")

    def test_dispatch_daily(self):
        result = InterestCalculator.calculate(10000, Decimal("12"), 90, ExtensionPeriodUnit.DAYS)
        assert result == Decimal("295.89")


class TestBothOrchestrator:
    def test_single_monthly_record(self):
        records = [{
            "amount": 10000,
            "interest_rate": Decimal("12"),
            "commission_rate": Decimal("6"),
            "extension_period": 3,
            "extension_period_unit": ExtensionPeriodUnit.MONTHS,
            "tds_flag": True,
        }]
        results = InterestCalculator.calculate_both_orchestrator(records)
        assert len(results) == 1
        r = results[0]
        assert r["interest_amount"] == Decimal("300.00")
        # commission: (10000 * 6 * 3) / 1200 = 150.00
        assert r["commission_amount"] == Decimal("150.00")
        assert r["tds_amount"] == Decimal("30.00")
        assert r["chq_amount"] == Decimal("270.00")

    def test_mixed_units(self):
        records = [
            {
                "amount": 10000,
                "interest_rate": Decimal("12"),
                "commission_rate": Decimal("0"),
                "extension_period": 3,
                "extension_period_unit": ExtensionPeriodUnit.MONTHS,
                "tds_flag": False,
            },
            {
                "amount": 10000,
                "interest_rate": Decimal("12"),
                "commission_rate": Decimal("0"),
                "extension_period": 90,
                "extension_period_unit": ExtensionPeriodUnit.DAYS,
                "tds_flag": False,
            },
        ]
        results = InterestCalculator.calculate_both_orchestrator(records)
        assert results[0]["interest_amount"] == Decimal("300.00")
        assert results[1]["interest_amount"] == Decimal("295.89")

    def test_no_tds(self):
        records = [{
            "amount": 10000,
            "interest_rate": Decimal("12"),
            "commission_rate": Decimal("0"),
            "extension_period": 3,
            "extension_period_unit": "months",
            "tds_flag": False,
        }]
        results = InterestCalculator.calculate_both_orchestrator(records)
        assert results[0]["tds_amount"] == Decimal("0.00")
        assert results[0]["chq_amount"] == Decimal("300.00")

    def test_string_unit_conversion(self):
        """Verify string units are converted to enum."""
        records = [{
            "amount": 10000,
            "interest_rate": "12",
            "commission_rate": "0",
            "extension_period": 3,
            "extension_period_unit": "months",
            "tds_flag": False,
        }]
        results = InterestCalculator.calculate_both_orchestrator(records)
        assert results[0]["interest_amount"] == Decimal("300.00")
