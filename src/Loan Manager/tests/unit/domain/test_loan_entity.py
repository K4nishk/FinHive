"""Loan entity and value object unit tests."""
import pytest

from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.report_id import ReportId


class TestReferenceId:
    def test_valid_format(self):
        ref = ReferenceId("2026_03_001")
        assert str(ref) == "2026_03_001"

    def test_valid_four_digit_order(self):
        ref = ReferenceId("2026_12_1000")
        assert str(ref) == "2026_12_1000"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            ReferenceId("invalid_format")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            ReferenceId("")

    def test_missing_order_raises(self):
        with pytest.raises(ValueError):
            ReferenceId("2026_03")

    def test_build_method(self):
        ref = ReferenceId.build(2026, 3, 1)
        assert str(ref) == "2026_03_001"

    def test_build_large_order(self):
        ref = ReferenceId.build(2026, 3, 1000)
        assert str(ref) == "2026_03_1000"


class TestMoney:
    def test_valid_amount(self):
        m = Money(10000)
        assert int(m) == 10000

    def test_zero_amount(self):
        m = Money(0)
        assert int(m) == 0

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError):
            Money(-1)

    def test_frozen(self):
        m = Money(100)
        with pytest.raises(AttributeError):
            m.amount = 200


class TestReportId:
    def test_valid_format(self):
        rid = ReportId("RPT_20260315_001")
        assert str(rid) == "RPT_20260315_001"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            ReportId("invalid")

    def test_build_method(self):
        rid = ReportId.build("20260315", 1)
        assert str(rid) == "RPT_20260315_001"

    def test_build_large_order(self):
        rid = ReportId.build("20260315", 1000)
        assert str(rid) == "RPT_20260315_1000"
