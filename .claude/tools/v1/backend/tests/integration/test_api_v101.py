"""Integration tests for v1.0.1 API enhancements."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestAPIWithNoDueDate:
    """Test API handling of loans without due dates (1970-01-01)."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Clean up loans after each test."""
        yield
        response = client.get("/api/v1/loans/")
        if response.status_code == 200:
            loans = response.json()
            for loan in loans:
                client.delete(f"/api/v1/loans/{loan['id']}")

    def test_create_loan_without_due_date_no_422_error(self):
        """Test that creating loan without due_date does NOT return 422 (bug fix)."""
        loan_data = {
            "borrower_name": "No Due Date Test",
            "amount": 10000.00,
            "currency": "INR",
            "depositor_name": "Test Lender",
            "giving_date": "2026-03-08",
            "due_date": "1970-01-01"  # Special marker for "no due date"
        }

        response = client.post("/api/v1/loans/", json=loan_data)

        # Should NOT return 422
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["due_date"] == "1970-01-01"
        assert data["status"] == "active"  # Should be active, not overdue

    def test_create_loan_empty_due_date_defaults_to_1970(self):
        """Test that 1970-01-01 due_date is accepted as no due date marker."""
        loan_data = {
            "borrower_name": "Default Date",
            "amount": 5000.00,
            "currency": "INR",
            "depositor_name": "Lender",
            "giving_date": "2026-03-08",
            "due_date": "1970-01-01"  # Required field, using no-due-date marker
        }

        response = client.post("/api/v1/loans/", json=loan_data)

        assert response.status_code in [200, 201]
        data = response.json()
        assert data["due_date"] == "1970-01-01"
        assert data["status"] == "active"

    def test_get_all_loans_no_nan_in_groups(self):
        """Test that retrieving loans with null groups doesn't return NaN."""
        # Create loan with null groups
        loan_data = {
            "borrower_name": "Null Groups",
            "amount": 3000.00,
            "currency": "INR",
            "depositor_name": "Lender",
            "giving_date": "2026-03-08",
            "due_date": "1970-01-01"
            # borrower_group and depositor_group omitted
        }

        create_response = client.post("/api/v1/loans/", json=loan_data)
        assert create_response.status_code in [200, 201]

        # Get all loans
        get_response = client.get("/api/v1/loans/")
        assert get_response.status_code == 200

        loans = get_response.json()
        assert len(loans) > 0

        # Find our loan
        our_loan = None
        for loan in loans:
            if loan["borrower_name"] == "Null Groups":
                our_loan = loan
                break

        assert our_loan is not None

        # Verify no NaN values
        import json
        try:
            json_str = json.dumps(our_loan)
            assert "NaN" not in json_str
            assert "nan" not in json_str.lower()
        except (ValueError, TypeError):
            pytest.fail("JSON serialization failed - NaN values present")

        # Groups should be None or empty string, not NaN
        assert our_loan["borrower_group"] is None or our_loan["borrower_group"] == ""
        assert our_loan["depositor_group"] is None or our_loan["depositor_group"] == ""


class TestAPICurrencyHandling:
    """Test API currency field handling."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Clean up loans after each test."""
        yield
        response = client.get("/api/v1/loans/")
        if response.status_code == 200:
            loans = response.json()
            for loan in loans:
                client.delete(f"/api/v1/loans/{loan['id']}")

    def test_currency_defaults_to_inr(self):
        """Test that currency defaults to INR."""
        loan_data = {
            "borrower_name": "Currency Default",
            "amount": 1000.00,
            "depositor_name": "Lender",
            "giving_date": "2026-03-08",
            "due_date": "1970-01-01"
            # currency not provided
        }

        response = client.post("/api/v1/loans/", json=loan_data)

        assert response.status_code in [200, 201]
        data = response.json()
        assert data["currency"] == "INR"

    def test_explicit_inr_currency_accepted(self):
        """Test that explicit INR is accepted."""
        loan_data = {
            "borrower_name": "Explicit INR",
            "amount": 5000.00,
            "currency": "INR",
            "depositor_name": "Lender",
            "giving_date": "2026-03-08",
            "due_date": "1970-01-01"
        }

        response = client.post("/api/v1/loans/", json=loan_data)

        assert response.status_code in [200, 201]
        data = response.json()
        assert data["currency"] == "INR"

    def test_all_loans_return_inr_currency(self):
        """Test that all loans in GET /loans return INR currency."""
        # Create 3 loans
        for i in range(3):
            loan_data = {
                "borrower_name": f"User {i}",
                "amount": 1000.00 * (i + 1),
                "depositor_name": "Lender",
                "giving_date": "2026-03-08",
                "due_date": "1970-01-01"
            }
            client.post("/api/v1/loans/", json=loan_data)

        # Get all loans
        response = client.get("/api/v1/loans/")

        assert response.status_code in [200, 201]
        loans = response.json()
        assert len(loans) == 3

        # Verify all have INR
        for loan in loans:
            assert loan["currency"] == "INR"


class TestAPIDateValidation:
    """Test API date validation for v1.0.1."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Clean up loans after each test."""
        yield
        response = client.get("/api/v1/loans/")
        if response.status_code == 200:
            loans = response.json()
            for loan in loans:
                client.delete(f"/api/v1/loans/{loan['id']}")

    def test_due_date_before_giving_date_returns_422(self):
        """Test that due_date before giving_date returns 422."""
        loan_data = {
            "borrower_name": "Invalid Dates",
            "amount": 1000.00,
            "currency": "INR",
            "depositor_name": "Lender",
            "giving_date": "2026-03-08",
            "due_date": "2026-03-01"  # Before giving_date
        }

        response = client.post("/api/v1/loans/", json=loan_data)

        # Should return validation error
        assert response.status_code == 422

    def test_1970_date_allowed_despite_being_before_giving_date(self):
        """Test that 1970-01-01 is allowed even if before giving_date."""
        loan_data = {
            "borrower_name": "1970 Special Date",
            "amount": 1000.00,
            "currency": "INR",
            "depositor_name": "Lender",
            "giving_date": "2026-03-08",
            "due_date": "1970-01-01"  # Special marker, should be allowed
        }

        response = client.post("/api/v1/loans/", json=loan_data)

        # Should succeed
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["due_date"] == "1970-01-01"
        assert data["status"] == "active"

    def test_same_giving_and_due_date_allowed(self):
        """Test that due_date can equal giving_date."""
        loan_data = {
            "borrower_name": "Same Date",
            "amount": 1000.00,
            "currency": "INR",
            "depositor_name": "Lender",
            "giving_date": "2026-03-08",
            "due_date": "2026-03-08"  # Same as giving_date
        }

        response = client.post("/api/v1/loans/", json=loan_data)

        assert response.status_code in [200, 201]
        data = response.json()
        assert data["giving_date"] == data["due_date"]


class TestAPIStatusCalculation:
    """Test API status auto-calculation."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Clean up loans after each test."""
        yield
        response = client.get("/api/v1/loans/")
        if response.status_code == 200:
            loans = response.json()
            for loan in loans:
                client.delete(f"/api/v1/loans/{loan['id']}")

    def test_1970_date_results_in_active_status(self):
        """Test that 1970-01-01 due_date results in 'active' status."""
        loan_data = {
            "borrower_name": "Active Test",
            "amount": 1000.00,
            "currency": "INR",
            "depositor_name": "Lender",
            "giving_date": "2026-03-08",
            "due_date": "1970-01-01"
        }

        response = client.post("/api/v1/loans/", json=loan_data)

        assert response.status_code in [200, 201]
        data = response.json()
        assert data["status"] == "active"  # NOT overdue

    def test_future_due_date_results_in_active_status(self):
        """Test that future due_date results in 'active' status."""
        loan_data = {
            "borrower_name": "Future Due",
            "amount": 1000.00,
            "currency": "INR",
            "depositor_name": "Lender",
            "giving_date": "2026-03-08",
            "due_date": "2027-03-08"  # Future date
        }

        response = client.post("/api/v1/loans/", json=loan_data)

        assert response.status_code in [200, 201]
        data = response.json()
        assert data["status"] == "active"

    def test_past_due_date_results_in_overdue_status(self):
        """Test that past due_date results in 'overdue' status."""
        loan_data = {
            "borrower_name": "Past Due",
            "amount": 1000.00,
            "currency": "INR",
            "depositor_name": "Lender",
            "giving_date": "2024-01-01",
            "due_date": "2024-12-31"  # Past date
        }

        response = client.post("/api/v1/loans/", json=loan_data)

        assert response.status_code in [200, 201]
        data = response.json()
        assert data["status"] == "overdue"


class TestAPIAmountValidation:
    """Test API amount validation."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Clean up loans after each test."""
        yield
        response = client.get("/api/v1/loans/")
        if response.status_code == 200:
            loans = response.json()
            for loan in loans:
                client.delete(f"/api/v1/loans/{loan['id']}")

    def test_zero_amount_returns_422(self):
        """Test that zero amount returns 422."""
        loan_data = {
            "borrower_name": "Zero Amount",
            "amount": 0.00,
            "currency": "INR",
            "depositor_name": "Lender",
            "giving_date": "2026-03-08",
            "due_date": "1970-01-01"
        }

        response = client.post("/api/v1/loans/", json=loan_data)

        assert response.status_code == 422

    def test_negative_amount_returns_422(self):
        """Test that negative amount returns 422."""
        loan_data = {
            "borrower_name": "Negative Amount",
            "amount": -1000.00,
            "currency": "INR",
            "depositor_name": "Lender",
            "giving_date": "2026-03-08",
            "due_date": "1970-01-01"
        }

        response = client.post("/api/v1/loans/", json=loan_data)

        assert response.status_code == 422

    def test_large_inr_amount_accepted(self):
        """Test that large INR amounts are accepted."""
        loan_data = {
            "borrower_name": "Large Amount",
            "amount": 10000000.00,  # 1 crore
            "currency": "INR",
            "depositor_name": "Lender",
            "giving_date": "2026-03-08",
            "due_date": "1970-01-01"
        }

        response = client.post("/api/v1/loans/", json=loan_data)

        assert response.status_code in [200, 201]
        data = response.json()
        assert float(data["amount"]) == 10000000.00
