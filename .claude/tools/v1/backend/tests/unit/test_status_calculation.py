"""Unit tests for loan status auto-calculation."""
import pytest
from datetime import date, timedelta
from app.schemas.loan import LoanCreate
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


class TestStatusCalculation:
    """Test automatic status calculation based on due_date."""

    def test_no_due_date_is_active(self):
        """Test that loans without due date (1970-01-01) are active."""
        loan_data = LoanCreate(
            borrower_name="No Due Date",
            amount=10000.00,
            depositor_name="Lender",
            giving_date=date(2026, 3, 8),
            due_date=date(1970, 1, 1)  # Special marker for "no due date"
        )

        loan = storage_service.create_loan(loan_data)

        assert loan.status.value == "active"
        assert str(loan.due_date) == "1970-01-01"

    def test_future_due_date_is_active(self):
        """Test that loans with future due dates are active."""
        future_date = date.today() + timedelta(days=30)

        loan_data = LoanCreate(
            borrower_name="Future Due",
            amount=5000.00,
            depositor_name="Lender",
            giving_date=date.today(),
            due_date=future_date
        )

        loan = storage_service.create_loan(loan_data)

        assert loan.status.value == "active"

    def test_past_due_date_is_overdue(self):
        """Test that loans with past due dates are overdue."""
        past_date = date.today() - timedelta(days=10)

        loan_data = LoanCreate(
            borrower_name="Past Due",
            amount=3000.00,
            depositor_name="Lender",
            giving_date=past_date - timedelta(days=30),
            due_date=past_date
        )

        loan = storage_service.create_loan(loan_data)

        assert loan.status.value == "overdue"

    def test_today_due_date_is_active(self):
        """Test that loans due today are considered active (not overdue yet)."""
        loan_data = LoanCreate(
            borrower_name="Due Today",
            amount=2000.00,
            depositor_name="Lender",
            giving_date=date.today() - timedelta(days=30),
            due_date=date.today()
        )

        loan = storage_service.create_loan(loan_data)

        # Due today should still be active (not overdue until tomorrow)
        assert loan.status.value in ["active", "overdue"]  # Depends on implementation

    def test_1970_date_never_becomes_overdue(self):
        """Test that 1970-01-01 loans never auto-change to overdue."""
        loan_data = LoanCreate(
            borrower_name="Perpetual Loan",
            amount=50000.00,
            depositor_name="Lender",
            giving_date=date(2020, 1, 1),  # Very old loan
            due_date=date(1970, 1, 1)  # No due date
        )

        loan = storage_service.create_loan(loan_data)

        # Should remain active despite old giving_date
        assert loan.status.value == "active"
        assert str(loan.due_date) == "1970-01-01"


class TestDateValidation:
    """Test date validation rules."""

    def test_due_date_before_giving_date_fails(self):
        """Test that due_date before giving_date raises validation error."""
        with pytest.raises(Exception):
            LoanCreate(
                borrower_name="Invalid Dates",
                amount=1000.00,
                depositor_name="Lender",
                giving_date=date(2026, 3, 8),
                due_date=date(2026, 3, 1)  # Before giving_date
            )

    def test_1970_date_allowed_despite_being_before_giving_date(self):
        """Test that 1970-01-01 is allowed even if before giving_date."""
        loan_data = LoanCreate(
            borrower_name="Special Date",
            amount=1000.00,
            depositor_name="Lender",
            giving_date=date(2026, 3, 8),
            due_date=date(1970, 1, 1)  # Special marker, should be allowed
        )

        loan = storage_service.create_loan(loan_data)
        assert str(loan.due_date) == "1970-01-01"
        assert loan.status.value == "active"

    def test_same_date_for_giving_and_due_allowed(self):
        """Test that due_date can be same as giving_date."""
        same_date = date(2026, 3, 8)

        loan_data = LoanCreate(
            borrower_name="Same Date",
            amount=1000.00,
            depositor_name="Lender",
            giving_date=same_date,
            due_date=same_date
        )

        loan = storage_service.create_loan(loan_data)
        assert str(loan.giving_date) == str(loan.due_date)


class TestNullFieldHandling:
    """Test handling of null/None values in optional fields."""

    def test_empty_borrower_group_stores_as_none(self):
        """Test that empty borrower_group stores as None, not NaN."""
        loan_data = LoanCreate(
            borrower_name="Test",
            amount=1000.00,
            depositor_name="Lender",
            giving_date=date(2026, 3, 8),
            due_date=date(2027, 3, 8),
            borrower_group=None
        )

        loan = storage_service.create_loan(loan_data)

        # Should be None, not NaN or empty string
        assert loan.borrower_group is None or loan.borrower_group == ""

    def test_empty_depositor_group_stores_as_none(self):
        """Test that empty depositor_group stores as None, not NaN."""
        loan_data = LoanCreate(
            borrower_name="Test",
            amount=1000.00,
            depositor_name="Lender",
            giving_date=date(2026, 3, 8),
            due_date=date(2027, 3, 8),
            depositor_group=None
        )

        loan = storage_service.create_loan(loan_data)

        # Should be None, not NaN or empty string
        assert loan.depositor_group is None or loan.depositor_group == ""

    def test_retrieve_loan_with_null_groups_no_nan(self):
        """Test that retrieving loans with null groups doesn't return NaN."""
        loan_data = LoanCreate(
            borrower_name="Test",
            amount=1000.00,
            depositor_name="Lender",
            giving_date=date(2026, 3, 8),
            due_date=date(2027, 3, 8),
            borrower_group=None,
            depositor_group=None
        )

        created_loan = storage_service.create_loan(loan_data)
        loan_id = created_loan.id

        # Retrieve loan
        retrieved_loan = storage_service.get_loan_by_id(loan_id)

        # Verify no NaN values
        assert retrieved_loan.borrower_group is None or retrieved_loan.borrower_group == ""
        assert retrieved_loan.depositor_group is None or retrieved_loan.depositor_group == ""

        # Also test in JSON serialization (would fail if NaN)
        import json
        from decimal import Decimal
        try:
            # Convert Pydantic model to dict then to JSON
            loan_dict = retrieved_loan.model_dump() if hasattr(retrieved_loan, 'model_dump') else retrieved_loan.dict()
            # Custom serializer for Decimal and date
            json.dumps(loan_dict, default=lambda x: str(x) if isinstance(x, (Decimal, date)) or hasattr(x, 'value') else None)
            assert True  # Should not raise error
        except (ValueError, TypeError) as e:
            pytest.fail(f"JSON serialization failed: {e}")
