"""ReferenceIdService unit tests."""
import pytest

from loan_manager.domain.services.reference_id_service import ReferenceIdService


class TestNextId:
    def test_first_id_none_last_order(self):
        assert ReferenceIdService.next_id(2026, 3, None) == "2026_03_001"

    def test_second_id(self):
        assert ReferenceIdService.next_id(2026, 3, 1) == "2026_03_002"

    def test_triple_digit(self):
        assert ReferenceIdService.next_id(2026, 12, 998) == "2026_12_999"

    def test_four_digit_overflow(self):
        assert ReferenceIdService.next_id(2026, 12, 999) == "2026_12_1000"

    def test_beyond_1000(self):
        assert ReferenceIdService.next_id(2026, 1, 1000) == "2026_01_1001"

    def test_single_digit_month(self):
        assert ReferenceIdService.next_id(2026, 1, None) == "2026_01_001"


class TestParse:
    def test_basic_parse(self):
        assert ReferenceIdService.parse("2026_03_001") == (2026, 3, 1)

    def test_four_digit_order(self):
        assert ReferenceIdService.parse("2026_12_1000") == (2026, 12, 1000)

    def test_large_order(self):
        assert ReferenceIdService.parse("2025_06_12345") == (2025, 6, 12345)

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            ReferenceIdService.parse("invalid")

    def test_too_few_parts_raises(self):
        with pytest.raises(ValueError):
            ReferenceIdService.parse("2026_03")


class TestFormatOrder:
    def test_single_digit(self):
        assert ReferenceIdService.format_order(1) == "001"

    def test_three_digit(self):
        assert ReferenceIdService.format_order(999) == "999"

    def test_four_digit(self):
        assert ReferenceIdService.format_order(1000) == "1000"


class TestYearMonthKey:
    def test_basic(self):
        assert ReferenceIdService.year_month_key(2026, 3) == "2026_03"

    def test_december(self):
        assert ReferenceIdService.year_month_key(2026, 12) == "2026_12"
