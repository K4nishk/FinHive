"""
Integration tests for Interest Calculator date filtering logic.

Tests the date-based filtering functionality that filters loans by due_date
greater than the selected filter date.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import date, timedelta
from app.main import app

client = TestClient(app)


class TestDateFilteringLogic:
    """Test date-based filtering for Interest Calculator."""

    @pytest.fixture(autouse=True)
    def setup_and_cleanup(self):
        """Set up test loans and clean up after each test."""
        # Clean up before test
        response = client.get("/api/v1/loans/")
        if response.status_code == 200:
            loans = response.json()
            for loan in loans:
                client.delete(f"/api/v1/loans/{loan['id']}")

        yield

        # Clean up after test
        response = client.get("/api/v1/loans/")
        if response.status_code == 200:
            loans = response.json()
            for loan in loans:
                client.delete(f"/api/v1/loans/{loan['id']}")

    def test_filter_loans_greater_than_filter_date(self):
        """Test filtering loans with due dates > selected filter date."""
        today = date.today()
        filter_date = today - timedelta(days=10)  # Filter date 10 days ago

        # Create loans with different due dates
        loans_data = [
            {
                "borrower_name": "After Filter Date",
                "amount": 10000.00,
                "depositor_name": "Bank A",
                "giving_date": (filter_date - timedelta(days=30)).isoformat(),
                "due_date": (filter_date + timedelta(days=5)).isoformat(),  # After filter date
            },
            {
                "borrower_name": "Before Filter Date",
                "amount": 20000.00,
                "depositor_name": "Bank B",
                "giving_date": (filter_date - timedelta(days=60)).isoformat(),
                "due_date": (filter_date - timedelta(days=1)).isoformat(),  # Before filter date
            },
            {
                "borrower_name": "Far Future",
                "amount": 30000.00,
                "depositor_name": "Bank C",
                "giving_date": filter_date.isoformat(),
                "due_date": (today + timedelta(days=60)).isoformat(),  # Far in future
            }
        ]

        # Create loans
        for loan_data in loans_data:
            response = client.post("/api/v1/loans/", json=loan_data)
            assert response.status_code in [200, 201]

        # Get all loans
        response = client.get("/api/v1/loans/")
        all_loans = response.json()

        # FILTER LOGIC: due_date > filter_date (strictly greater than)
        filtered = []
        for loan in all_loans:
            if loan['due_date'] == '1970-01-01' or loan['status'] == 'paid_off':
                continue
            loan_due_date = date.fromisoformat(loan['due_date'])
            if loan_due_date > filter_date:
                filtered.append(loan)

        # Should include 2 loans (after filter date + far future) - NOT before filter date
        assert len(filtered) == 2
        borrower_names = {loan['borrower_name'] for loan in filtered}
        assert borrower_names == {'After Filter Date', 'Far Future'}

    def test_filter_excludes_paid_off_loans(self):
        """Test that paid_off loans are excluded from filtering."""
        today = date.today()
        filter_date = today - timedelta(days=5)

        loans_data = [
            {
                "borrower_name": "Active User",
                "amount": 10000.00,
                "depositor_name": "Bank A",
                "giving_date": (filter_date - timedelta(days=30)).isoformat(),
                "due_date": (filter_date + timedelta(days=10)).isoformat(),
            },
            {
                "borrower_name": "Paid Off User",
                "amount": 20000.00,
                "depositor_name": "Bank B",
                "giving_date": (filter_date - timedelta(days=30)).isoformat(),
                "due_date": (filter_date + timedelta(days=10)).isoformat(),
            }
        ]

        # Create loans and set one to paid_off
        loan_ids = []
        for loan_data in loans_data:
            response = client.post("/api/v1/loans/", json=loan_data)
            assert response.status_code in [200, 201]
            loan_ids.append(response.json()['id'])

        # Update second loan to paid_off status
        response = client.patch(f"/api/v1/loans/{loan_ids[1]}", json={"status": "paid_off"})
        assert response.status_code == 200

        # Get all loans
        response = client.get("/api/v1/loans/")
        all_loans = response.json()

        # FILTER LOGIC: due_date > filter_date (strictly greater than)
        filtered = []
        for loan in all_loans:
            if loan['due_date'] == '1970-01-01' or loan['status'] == 'paid_off':
                continue
            loan_due_date = date.fromisoformat(loan['due_date'])
            if loan_due_date > filter_date:
                filtered.append(loan)

        # Should only include active loan
        assert len(filtered) == 1
        assert filtered[0]['borrower_name'] == 'Active User'

    def test_filter_excludes_no_due_date_loans(self):
        """Test that loans with 1970-01-01 (no due date) are excluded."""
        today = date.today()
        filter_date = today - timedelta(days=10)

        loans_data = [
            {
                "borrower_name": "With Due Date",
                "amount": 10000.00,
                "depositor_name": "Bank A",
                "giving_date": (filter_date - timedelta(days=30)).isoformat(),
                "due_date": (filter_date + timedelta(days=5)).isoformat()
            },
            {
                "borrower_name": "No Due Date",
                "amount": 20000.00,
                "depositor_name": "Bank B",
                "giving_date": (filter_date - timedelta(days=30)).isoformat(),
                "due_date": "1970-01-01"
            }
        ]

        # Create loans
        for loan_data in loans_data:
            response = client.post("/api/v1/loans/", json=loan_data)
            assert response.status_code in [200, 201]

        # Get all loans
        response = client.get("/api/v1/loans/")
        all_loans = response.json()

        # Filter logic
        filtered = []
        for loan in all_loans:
            if loan['due_date'] == '1970-01-01' or loan['status'] == 'paid_off':
                continue
            loan_due_date = date.fromisoformat(loan['due_date'])
            if loan_due_date > filter_date:
                filtered.append(loan)

        # Should only include loan with actual due date
        assert len(filtered) == 1
        assert filtered[0]['borrower_name'] == 'With Due Date'

    def test_filter_specific_date_march_10_2026(self):
        """Test filtering for a specific date (March 10, 2026)."""
        # Create loans with various due dates
        loans_data = [
            {
                "borrower_name": "After Filter Date 1",
                "amount": 10000.00,
                "depositor_name": "Bank A",
                "giving_date": "2026-01-01",
                "due_date": "2026-03-15",  # After Mar 10
                "status": "active"
            },
            {
                "borrower_name": "After Filter Date 2",
                "amount": 15000.00,
                "depositor_name": "Bank B",
                "giving_date": "2026-02-01",
                "due_date": "2026-03-20",  # After Mar 10
                "status": "active"
            },
            {
                "borrower_name": "After Filter Date 3",
                "amount": 20000.00,
                "depositor_name": "Bank C",
                "giving_date": "2026-01-01",
                "due_date": "2026-04-01",  # After Mar 10
                "status": "active"
            },
            {
                "borrower_name": "Before Filter Date",
                "amount": 12000.00,
                "depositor_name": "Bank D",
                "giving_date": "2026-01-01",
                "due_date": "2026-02-28",  # Before Mar 10
                "status": "active"
            }
        ]

        # Create loans
        for loan_data in loans_data:
            response = client.post("/api/v1/loans/", json=loan_data)
            assert response.status_code in [200, 201]

        # Get all loans
        response = client.get("/api/v1/loans/")
        all_loans = response.json()

        # Filter for March 10, 2026
        filter_date = date(2026, 3, 10)

        filtered = []
        for loan in all_loans:
            if loan['due_date'] == '1970-01-01' or loan['status'] == 'paid_off':
                continue
            loan_due_date = date.fromisoformat(loan['due_date'])
            if loan_due_date > filter_date:
                filtered.append(loan)

        # Should include 3 loans (all after March 10)
        assert len(filtered) == 3
        borrower_names = {loan['borrower_name'] for loan in filtered}
        assert borrower_names == {'After Filter Date 1', 'After Filter Date 2', 'After Filter Date 3'}

    def test_filter_empty_result_all_loans_before_filter_date(self):
        """Test filtering returns empty when all loans are before filter date."""
        # Create loans with due dates all before filter date
        loans_data = [
            {
                "borrower_name": "January Loan",
                "amount": 10000.00,
                "depositor_name": "Bank A",
                "giving_date": "2025-12-01",
                "due_date": "2026-01-15",
                "status": "active"
            },
            {
                "borrower_name": "February Loan",
                "amount": 20000.00,
                "depositor_name": "Bank B",
                "giving_date": "2026-01-01",
                "due_date": "2026-02-15",
                "status": "active"
            }
        ]

        # Create loans
        for loan_data in loans_data:
            response = client.post("/api/v1/loans/", json=loan_data)
            assert response.status_code in [200, 201]

        # Get all loans
        response = client.get("/api/v1/loans/")
        all_loans = response.json()

        # Filter for March 1, 2026 (all loans are before this date)
        filter_date = date(2026, 3, 1)

        filtered = []
        for loan in all_loans:
            if loan['due_date'] == '1970-01-01' or loan['status'] == 'paid_off':
                continue
            loan_due_date = date.fromisoformat(loan['due_date'])
            if loan_due_date > filter_date:
                filtered.append(loan)

        # Should have no loans (all are before March 1)
        assert len(filtered) == 0

    def test_filter_boundary_exactly_on_filter_date(self):
        """Test that loans due exactly on the filter date are EXCLUDED (must be greater than)."""
        today = date.today()
        filter_date = today - timedelta(days=10)

        loan_data = {
            "borrower_name": "Exactly On Filter Date",
            "amount": 10000.00,
            "depositor_name": "Bank A",
            "giving_date": (filter_date - timedelta(days=30)).isoformat(),
            "due_date": filter_date.isoformat(),  # Exactly on filter date
            "status": "active"
        }

        response = client.post("/api/v1/loans/", json=loan_data)
        assert response.status_code in [200, 201]

        # Get all loans
        response = client.get("/api/v1/loans/")
        all_loans = response.json()

        # Filter logic: due_date > filter_date (strictly greater than)
        filtered = []
        for loan in all_loans:
            if loan['due_date'] == '1970-01-01' or loan['status'] == 'paid_off':
                continue
            loan_due_date = date.fromisoformat(loan['due_date'])
            if loan_due_date > filter_date:
                filtered.append(loan)

        # Should NOT include the loan (boundary: not strictly greater than)
        assert len(filtered) == 0

    def test_filter_boundary_one_day_after_filter_date(self):
        """Test that loans due one day after filter date are included."""
        today = date.today()
        filter_date = today - timedelta(days=10)
        one_day_after = filter_date + timedelta(days=1)

        loan_data = {
            "borrower_name": "One Day After",
            "amount": 10000.00,
            "depositor_name": "Bank A",
            "giving_date": (filter_date - timedelta(days=30)).isoformat(),
            "due_date": one_day_after.isoformat(),  # One day after filter date
            "status": "active"
        }

        response = client.post("/api/v1/loans/", json=loan_data)
        assert response.status_code in [200, 201]

        # Get all loans
        response = client.get("/api/v1/loans/")
        all_loans = response.json()

        # Filter logic: due_date > filter_date
        filtered = []
        for loan in all_loans:
            if loan['due_date'] == '1970-01-01' or loan['status'] == 'paid_off':
                continue
            loan_due_date = date.fromisoformat(loan['due_date'])
            if loan_due_date > filter_date:
                filtered.append(loan)

        # Should include the loan (one day after is greater than)
        assert len(filtered) == 1
        assert filtered[0]['borrower_name'] == 'One Day After'

    def test_filter_includes_future_dates(self):
        """Test that loans with future due dates ARE INCLUDED."""
        today = date.today()
        filter_date = today - timedelta(days=10)
        tomorrow = today + timedelta(days=1)
        next_month = today + timedelta(days=60)

        loans_data = [
            {
                "borrower_name": "Before Filter Date",
                "amount": 10000.00,
                "depositor_name": "Bank A",
                "giving_date": (filter_date - timedelta(days=30)).isoformat(),
                "due_date": (filter_date - timedelta(days=5)).isoformat(),  # Before filter date
                "status": "active"
            },
            {
                "borrower_name": "After Filter Near Future",
                "amount": 20000.00,
                "depositor_name": "Bank B",
                "giving_date": filter_date.isoformat(),
                "due_date": tomorrow.isoformat(),  # Tomorrow (after filter date)
                "status": "active"
            },
            {
                "borrower_name": "After Filter Far Future",
                "amount": 30000.00,
                "depositor_name": "Bank C",
                "giving_date": filter_date.isoformat(),
                "due_date": next_month.isoformat(),  # Next month (after filter date)
                "status": "active"
            }
        ]

        # Create loans
        for loan_data in loans_data:
            response = client.post("/api/v1/loans/", json=loan_data)
            assert response.status_code in [200, 201]

        # Get all loans
        response = client.get("/api/v1/loans/")
        all_loans = response.json()

        # FILTER LOGIC: due_date > filter_date (includes all dates after filter)
        filtered = []
        for loan in all_loans:
            if loan['due_date'] == '1970-01-01' or loan['status'] == 'paid_off':
                continue
            loan_due_date = date.fromisoformat(loan['due_date'])
            if loan_due_date > filter_date:
                filtered.append(loan)

        # Should include 2 loans (both after filter date, not the one before)
        assert len(filtered) == 2
        borrower_names = {loan['borrower_name'] for loan in filtered}
        assert borrower_names == {'After Filter Near Future', 'After Filter Far Future'}


class TestDateFilterValidation:
    """Test date filter input validation."""

    def test_date_format_validation_valid(self):
        """Test that valid date format (YYYY-MM-DD) is accepted."""
        import re
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

        valid_dates = [
            '2026-01-15',
            '2026-06-30',
            '2026-12-31',
            '2025-03-01',
            '2027-09-15'
        ]

        for date_str in valid_dates:
            assert date_pattern.match(date_str), f"{date_str} should be valid"

    def test_date_format_validation_invalid(self):
        """Test that invalid date formats are rejected."""
        import re
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

        invalid_dates = [
            'june',  # Text month name
            '2026-06',  # Month only (no day)
            '26-06-15',  # Two-digit year
            '2026/06/15',  # Wrong separator
            '2026-6-5',  # Missing leading zeros
            '',  # Empty
            '2026',  # Year only
        ]

        for date_str in invalid_dates:
            assert not date_pattern.match(date_str), f"{date_str} should be invalid"

        # Note: '2026-13-01' matches the pattern but would be caught by the Date constructor
        # The frontend date picker won't allow invalid dates anyway
