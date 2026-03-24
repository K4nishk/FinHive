"""Unit tests for currency handling (INR-only)."""
import pytest
from datetime import date
from app.schemas.loan import LoanCreate, Currency
from app.services.storage_service import storage_service


@pytest.fixture(autouse=True)
def clean_storage():
    """Clean storage before each test."""
    loans = storage_service.get_all_loans()
    for loan in loans:
        storage_service.delete_loan(loan.id)
    yield
    loans = storage_service.get_all_loans()
    for loan in loans:
        storage_service.delete_loan(loan.id)


class TestCurrencyHandling:
    """Test currency field handling."""

    def test_currency_defaults_to_inr(self):
        """Test that currency defaults to INR when not provided."""
        loan_data = LoanCreate(
            borrower_name="Currency Test",
            amount=10000.00,
            depositor_name="Lender",
            giving_date=date(2026, 3, 8),
            due_date=date(2027, 3, 8)
        )

        loan = storage_service.create_loan(loan_data)

        assert loan.currency == Currency.INR

    def test_explicit_inr_currency_accepted(self):
        """Test that explicit INR currency is accepted."""
        loan_data = LoanCreate(
            borrower_name="Explicit INR",
            amount=5000.00,
            currency=Currency.INR,
            depositor_name="Lender",
            giving_date=date(2026, 3, 8),
            due_date=date(2027, 3, 8)
        )

        loan = storage_service.create_loan(loan_data)

        assert loan.currency == Currency.INR

    def test_inr_amounts_stored_correctly(self):
        """Test that INR amounts are stored with proper precision."""
        loan_data = LoanCreate(
            borrower_name="Precision Test",
            amount=123456.78,  # INR amount with paisa
            currency=Currency.INR,
            depositor_name="Lender",
            giving_date=date(2026, 3, 8),
            due_date=date(2027, 3, 8)
        )

        loan = storage_service.create_loan(loan_data)

        # Should preserve decimal precision
        assert float(loan.amount) == 123456.78

    def test_large_inr_amount(self):
        """Test handling of large INR amounts (lakhs/crores)."""
        loan_data = LoanCreate(
            borrower_name="Large Amount",
            amount=10000000.00,  # 1 crore
            currency=Currency.INR,
            depositor_name="Lender",
            giving_date=date(2026, 3, 8),
            due_date=date(2027, 3, 8)
        )

        loan = storage_service.create_loan(loan_data)

        assert float(loan.amount) == 10000000.00
        assert loan.currency == Currency.INR

    def test_all_loans_have_inr_currency(self):
        """Test that all created loans have INR currency."""
        # Create multiple loans
        amounts = [1000, 5000, 10000, 50000]

        for i, amt in enumerate(amounts):
            loan_data = LoanCreate(
                borrower_name=f"Borrower {i}",
                amount=amt,
                depositor_name="Lender",
                giving_date=date(2026, 3, 8),
                due_date=date(2027, 3, 8)
            )
            storage_service.create_loan(loan_data)

        # Verify all have INR
        loans = storage_service.get_all_loans()

        assert len(loans) == 4
        for loan in loans:
            assert loan.currency == Currency.INR


class TestAmountValidation:
    """Test amount validation for INR."""

    def test_zero_amount_rejected(self):
        """Test that zero amount is rejected."""
        with pytest.raises(Exception):
            LoanCreate(
                borrower_name="Zero Amount",
                amount=0.00,
                currency=Currency.INR,
                depositor_name="Lender",
                giving_date=date(2026, 3, 8),
                due_date=date(2027, 3, 8)
            )

    def test_negative_amount_rejected(self):
        """Test that negative amount is rejected."""
        with pytest.raises(Exception):
            LoanCreate(
                borrower_name="Negative Amount",
                amount=-1000.00,
                currency=Currency.INR,
                depositor_name="Lender",
                giving_date=date(2026, 3, 8),
                due_date=date(2027, 3, 8)
            )

    def test_very_small_amount_accepted(self):
        """Test that very small positive amounts are accepted."""
        loan_data = LoanCreate(
            borrower_name="Small Amount",
            amount=0.01,  # 1 paisa
            currency=Currency.INR,
            depositor_name="Lender",
            giving_date=date(2026, 3, 8),
            due_date=date(2027, 3, 8)
        )

        loan = storage_service.create_loan(loan_data)

        assert float(loan.amount) == 0.01

    def test_amount_with_many_decimals_rounded(self):
        """Test that amounts with many decimal places are handled correctly."""
        loan_data = LoanCreate(
            borrower_name="Many Decimals",
            amount=1234.56789,  # More than 2 decimals
            currency=Currency.INR,
            depositor_name="Lender",
            giving_date=date(2026, 3, 8),
            due_date=date(2027, 3, 8)
        )

        loan = storage_service.create_loan(loan_data)

        # Should be stored (may be rounded to 2 decimals by storage)
        assert hasattr(loan, 'amount')
        assert float(loan.amount) >= 1234.56
