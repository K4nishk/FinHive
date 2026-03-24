"""Unit tests for loan CRUD operations."""
import pytest
from datetime import date
from app.schemas.loan import LoanCreate, LoanUpdate
from app.services.storage_service import storage_service


@pytest.fixture(autouse=True)
def clean_storage():
    """Clean storage before each test."""
    # Clear all loans before test
    loans = storage_service.get_all_loans()
    for loan in loans:
        storage_service.delete_loan(loan.id)
    yield
    # Clean up after test
    loans = storage_service.get_all_loans()
    for loan in loans:
        storage_service.delete_loan(loan.id)


class TestLoanCreation:
    """Test loan creation functionality."""

    def test_create_loan_with_all_fields(self):
        """Test creating a loan with all fields provided."""
        loan_data = LoanCreate(
            borrower_name="John Doe",
            amount=10000.00,
            depositor_name="Jane Smith",
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 12, 31),
            borrower_group="Family",
            depositor_group="Personal"
        )

        loan = storage_service.create_loan(loan_data)

        assert loan.borrower_name == "John Doe"
        assert float(loan.amount) == 10000.00
        assert loan.depositor_name == "Jane Smith"
        assert str(loan.giving_date) == "2026-01-01"
        assert str(loan.due_date) == "2026-12-31"
        assert loan.borrower_group == "Family"
        assert loan.depositor_group == "Personal"
        assert loan.status.value == "active"
        assert hasattr(loan, 'id')
        assert hasattr(loan, 'created_at')

    def test_create_loan_with_optional_fields_empty(self):
        """Test creating loan with optional fields empty."""
        loan_data = LoanCreate(
            borrower_name="Test User",
            amount=5000.00,
            depositor_name="Test Bank",
            giving_date=date(2026, 1, 15),
            due_date=date(1970, 1, 1),  # No due date marker
            borrower_group=None,
            depositor_group=None
        )

        loan = storage_service.create_loan(loan_data)

        assert loan.borrower_name == "Test User"
        assert str(loan.due_date) == "1970-01-01"  # Default value
        assert loan.borrower_group is None or loan.borrower_group == ""
        assert loan.depositor_group is None or loan.depositor_group == ""

    def test_create_loan_with_no_due_date(self):
        """Test creating loan without due date defaults to 1970-01-01."""
        loan_data = LoanCreate(
            borrower_name="No Due Date User",
            amount=3000.00,
            depositor_name="Lender",
            giving_date=date(2026, 2, 1),
            due_date=date(1970, 1, 1)  # No due date marker
        )

        loan = storage_service.create_loan(loan_data)

        assert str(loan.due_date) == "1970-01-01"
        assert loan.status.value == "active"  # Should be active, not overdue


class TestLoanRetrieval:
    """Test loan retrieval operations."""

    def test_get_all_loans_empty(self):
        """Test getting loans when database is empty."""
        loans = storage_service.get_all_loans()
        assert loans == []

    def test_get_all_loans_multiple(self):
        """Test getting multiple loans."""
        # Create 3 loans
        for i in range(3):
            loan_data = LoanCreate(
                borrower_name=f"Borrower {i}",
                amount=1000.00 * (i + 1),
                depositor_name=f"Depositor {i}",
                giving_date=date(2026, 1, i + 1),
                due_date=date(1970, 1, 1)  # No due date marker
            )
            storage_service.create_loan(loan_data)

        loans = storage_service.get_all_loans()
        assert len(loans) == 3

    def test_get_loan_by_id(self):
        """Test retrieving a specific loan by ID."""
        loan_data = LoanCreate(
            borrower_name="Specific User",
            amount=7500.00,
            depositor_name="Specific Lender",
            giving_date=date(2026, 3, 1),
            due_date=date(1970, 1, 1)
        )

        created_loan = storage_service.create_loan(loan_data)
        loan_id = created_loan.id

        retrieved_loan = storage_service.get_loan_by_id(loan_id)
        assert retrieved_loan is not None
        assert retrieved_loan.id == loan_id
        assert retrieved_loan.borrower_name == "Specific User"

    def test_get_nonexistent_loan(self):
        """Test retrieving a loan that doesn't exist."""
        from app.core.exceptions import LoanNotFoundException
        with pytest.raises(LoanNotFoundException):
            storage_service.get_loan_by_id("nonexistent-id")


class TestLoanUpdate:
    """Test loan update operations."""

    def test_update_loan_amount(self):
        """Test updating loan amount."""
        # Create loan
        loan_data = LoanCreate(
            borrower_name="Update Test",
            amount=1000.00,
            depositor_name="Test Lender",
            giving_date=date(2026, 1, 1),
            due_date=date(1970, 1, 1)
        )
        loan = storage_service.create_loan(loan_data)
        loan_id = loan.id

        # Update amount
        update_data = LoanUpdate(amount=2000.00)
        updated_loan = storage_service.update_loan(loan_id, update_data)

        assert float(updated_loan.amount) == 2000.00
        assert updated_loan.borrower_name == "Update Test"  # Unchanged

    def test_update_loan_status(self):
        """Test updating loan status."""
        loan_data = LoanCreate(
            borrower_name="Status Test",
            amount=5000.00,
            depositor_name="Lender",
            giving_date=date(2026, 1, 1),
            due_date=date(1970, 1, 1)
        )
        loan = storage_service.create_loan(loan_data)
        loan_id = loan.id

        # Update status
        update_data = LoanUpdate(status="paid_off")
        updated_loan = storage_service.update_loan(loan_id, update_data)

        assert updated_loan.status.value == "paid_off"

    def test_update_multiple_fields(self):
        """Test updating multiple fields at once."""
        loan_data = LoanCreate(
            borrower_name="Multi Update",
            amount=3000.00,
            depositor_name="Original Lender",
            giving_date=date(2026, 1, 1),
            due_date=date(1970, 1, 1)
        )
        loan = storage_service.create_loan(loan_data)
        loan_id = loan.id

        # Update multiple fields
        update_data = LoanUpdate(
            amount=4000.00,
            status="overdue"
        )
        updated_loan = storage_service.update_loan(loan_id, update_data)

        assert float(updated_loan.amount) == 4000.00
        assert updated_loan.borrower_name == "Multi Update"  # Unchanged
        assert updated_loan.status.value == "overdue"


class TestLoanDeletion:
    """Test loan deletion (soft delete) operations."""

    def test_delete_loan(self):
        """Test soft deleting a loan."""
        loan_data = LoanCreate(
            borrower_name="Delete Test",
            amount=1500.00,
            depositor_name="Lender",
            giving_date=date(2026, 1, 1),
            due_date=date(1970, 1, 1)
        )
        loan = storage_service.create_loan(loan_data)
        loan_id = loan.id

        # Delete loan
        result = storage_service.delete_loan(loan_id)
        assert result is True

        # Verify loan no longer appears in get_all
        loans = storage_service.get_all_loans()
        assert not any(l.id == loan_id for l in loans)

    def test_delete_nonexistent_loan(self):
        """Test deleting a loan that doesn't exist."""
        from app.core.exceptions import LoanNotFoundException
        with pytest.raises(LoanNotFoundException):
            storage_service.delete_loan("nonexistent-id")


class TestLoanValidation:
    """Test loan data validation."""

    def test_create_loan_missing_required_field(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(Exception):
            LoanCreate(
                # Missing borrower_name
                amount=1000.00,
                depositor_name="Lender",
                giving_date=date(2026, 1, 1),
                due_date=date(1970, 1, 1)
            )

    def test_create_loan_negative_amount(self):
        """Test that negative amount raises validation error."""
        with pytest.raises(Exception):
            LoanCreate(
                borrower_name="Test",
                amount=-1000.00,  # Invalid
                depositor_name="Lender",
                giving_date=date(2026, 1, 1),
                due_date=date(1970, 1, 1)
            )

    def test_create_loan_zero_amount(self):
        """Test that zero amount raises validation error."""
        with pytest.raises(Exception):
            LoanCreate(
                borrower_name="Test",
                amount=0.00,  # Invalid
                depositor_name="Lender",
                giving_date=date(2026, 1, 1),
                due_date=date(1970, 1, 1)
            )


class TestDueDateDefault:
    """Test due date default behavior."""

    def test_due_date_defaults_to_1970(self):
        """Test that 1970-01-01 due_date is accepted as no due date marker."""
        loan_data = LoanCreate(
            borrower_name="Default Date Test",
            amount=2000.00,
            depositor_name="Lender",
            giving_date=date(2026, 1, 1),
            due_date=date(1970, 1, 1)  # Special marker for "no due date"
        )

        loan = storage_service.create_loan(loan_data)
        assert str(loan.due_date) == "1970-01-01"

    def test_explicit_due_date_respected(self):
        """Test that explicit due_date is used when provided."""
        loan_data = LoanCreate(
            borrower_name="Explicit Date Test",
            amount=2000.00,
            depositor_name="Lender",
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 6, 1)
        )

        loan = storage_service.create_loan(loan_data)
        assert str(loan.due_date) == "2026-06-01"
