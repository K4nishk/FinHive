"""Integration tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self):
        """Test that health endpoint returns correct data."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "app" in data
        assert "version" in data


class TestLoanAPI:
    """Test loan CRUD API endpoints."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Clean up loans after each test."""
        yield
        # Delete all loans after test
        response = client.get("/api/v1/loans/")
        if response.status_code == 200:
            loans = response.json()
            for loan in loans:
                client.delete(f"/api/v1/loans/{loan['id']}")

    def test_create_loan(self):
        """Test creating a loan via API."""
        loan_data = {
            "borrower_name": "API Test User",
            "amount": 5000.00,
            "depositor_name": "API Test Lender",
            "giving_date": "2026-01-01",
            "due_date": "2026-12-31",
            "borrower_group": "Test",
            "depositor_group": "Test"
        }

        response = client.post("/api/v1/loans/", json=loan_data)
        assert response.status_code in [200, 201]

        data = response.json()
        assert data["borrower_name"] == "API Test User"
        assert float(data["amount"]) == 5000.00
        assert "id" in data

    def test_create_loan_without_optional_fields(self):
        """Test creating loan without optional fields."""
        loan_data = {
            "borrower_name": "Minimal Test",
            "amount": 1000.00,
            "depositor_name": "Lender",
            "giving_date": "2026-01-01",
            "due_date": "1970-01-01"  # Required field, using no-due-date marker
        }

        response = client.post("/api/v1/loans/", json=loan_data)
        assert response.status_code in [200, 201]

        data = response.json()
        assert data["due_date"] == "1970-01-01"
        assert data["borrower_group"] is None or data["borrower_group"] == ""
        assert data["depositor_group"] is None or data["depositor_group"] == ""

    def test_get_all_loans(self):
        """Test retrieving all loans."""
        # Create 2 loans
        for i in range(2):
            loan_data = {
                "borrower_name": f"User {i}",
                "amount": 1000.00 * (i + 1),
                "depositor_name": f"Lender {i}",
                "giving_date": "2026-01-01",
                "due_date": "1970-01-01"
            }
            resp = client.post("/api/v1/loans/", json=loan_data)
            assert resp.status_code in [200, 201], f"Failed to create loan {i}: {resp.text}"

        response = client.get("/api/v1/loans/")
        assert response.status_code == 200

        loans = response.json()
        assert len(loans) == 2

    def test_get_loan_by_id(self):
        """Test retrieving specific loan."""
        # Create loan
        loan_data = {
            "borrower_name": "Get Test",
            "amount": 2000.00,
            "depositor_name": "Lender",
            "giving_date": "2026-01-01",
            "due_date": "1970-01-01"
        }
        create_response = client.post("/api/v1/loans/", json=loan_data)
        assert create_response.status_code in [200, 201], f"Create failed: {create_response.text}"
        loan_id = create_response.json()["id"]

        # Get loan
        response = client.get(f"/api/v1/loans/{loan_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == loan_id
        assert data["borrower_name"] == "Get Test"

    def test_get_nonexistent_loan(self):
        """Test getting loan that doesn't exist."""
        response = client.get("/api/v1/loans/nonexistent-id")
        assert response.status_code == 404

    def test_update_loan(self):
        """Test updating a loan."""
        # Create loan
        loan_data = {
            "borrower_name": "Update Test",
            "amount": 3000.00,
            "depositor_name": "Lender",
            "giving_date": "2026-01-01",
            "due_date": "1970-01-01"
        }
        create_response = client.post("/api/v1/loans/", json=loan_data)
        assert create_response.status_code in [200, 201], f"Create failed: {create_response.text}"
        loan_id = create_response.json()["id"]

        # Update loan
        update_data = {
            "amount": 4000.00,
            "status": "paid_off"
        }
        response = client.patch(f"/api/v1/loans/{loan_id}", json=update_data)
        assert response.status_code == 200

        data = response.json()
        assert float(data["amount"]) == 4000.00
        assert data["status"] == "paid_off"

    def test_delete_loan(self):
        """Test deleting a loan."""
        # Create loan
        loan_data = {
            "borrower_name": "Delete Test",
            "amount": 1500.00,
            "depositor_name": "Lender",
            "giving_date": "2026-01-01",
            "due_date": "1970-01-01"
        }
        create_response = client.post("/api/v1/loans/", json=loan_data)
        assert create_response.status_code in [200, 201], f"Create failed: {create_response.text}"
        loan_id = create_response.json()["id"]

        # Delete loan
        response = client.delete(f"/api/v1/loans/{loan_id}")
        assert response.status_code in [200, 204]  # 200 or 204 No Content

        # Verify deleted
        get_response = client.get(f"/api/v1/loans/{loan_id}")
        assert get_response.status_code == 404


class TestReportsAPI:
    """Test reports API endpoints."""

    @pytest.fixture(autouse=True)
    def setup_loans(self):
        """Create test loans for reports."""
        loans_data = [
            {
                "borrower_name": "John Doe",
                "amount": 10000.00,
                "depositor_name": "Bank A",
                "giving_date": "2026-01-01",
                "due_date": "1970-01-01",
                "borrower_group": "Family",
                "depositor_group": "Bank"
            },
            {
                "borrower_name": "Jane Smith",
                "amount": 5000.00,
                "depositor_name": "Bank B",
                "giving_date": "2026-01-15",
                "due_date": "1970-01-01",
                "borrower_group": "Business",
                "depositor_group": "Bank"
            },
            {
                "borrower_name": "Bob Wilson",
                "amount": 7500.00,
                "depositor_name": "Credit Union",
                "giving_date": "2026-02-01",
                "due_date": "1970-01-01",
                "status": "paid_off"
            }
        ]

        self.loan_ids = []
        for loan_data in loans_data:
            response = client.post("/api/v1/loans/", json=loan_data)
            if response.status_code in [200, 201]:
                self.loan_ids.append(response.json()["id"])

        # Update the third loan to paid_off status
        if len(self.loan_ids) >= 3:
            client.patch(f"/api/v1/loans/{self.loan_ids[2]}", json={"status": "paid_off"})

        yield

        # Cleanup
        for loan_id in self.loan_ids:
            client.delete(f"/api/v1/loans/{loan_id}")

    def test_get_statistics(self):
        """Test getting loan statistics."""
        response = client.get("/api/v1/reports/statistics")
        assert response.status_code == 200

        stats = response.json()
        assert stats["total_loans"] == 3
        assert stats["total_amount"] == 22500.00
        assert stats["active_loans"] == 2
        assert stats["paid_off_loans"] == 1
        assert "by_borrower" in stats
        assert "by_depositor" in stats


class TestConfigAPI:
    """Test configuration API endpoints."""

    def test_get_config(self):
        """Test getting system configuration."""
        response = client.get("/api/v1/config/")
        assert response.status_code == 200

        config = response.json()
        assert "storage_type" in config
        assert "encryption_enabled" in config
        assert "app_version" in config
