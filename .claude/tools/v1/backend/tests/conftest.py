"""Pytest configuration and shared fixtures."""
import pytest
import os
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Set test environment variables
os.environ["STORAGE_TYPE"] = "csv"
os.environ["CSV_OUTPUT_DIR"] = str(backend_dir / "tests" / "test_data")
os.environ["CSV_FILENAME"] = "test_loans.csv"
os.environ["ENCRYPTION_KEY"] = ""  # Disable encryption for tests
os.environ["LOG_LEVEL"] = "ERROR"  # Reduce log noise during tests


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment before all tests."""
    # Create test data directory
    test_data_dir = backend_dir / "tests" / "test_data"
    test_data_dir.mkdir(exist_ok=True)

    yield

    # Cleanup test data directory after all tests
    import shutil
    if test_data_dir.exists():
        shutil.rmtree(test_data_dir)


@pytest.fixture
def sample_loan_data():
    """Provide sample loan data for tests."""
    return {
        "borrower_name": "John Doe",
        "amount": 10000.00,
        "depositor_name": "Jane Smith",
        "giving_date": "2025-01-01",
        "due_date": "2025-12-31",
        "borrower_group": "Family",
        "depositor_group": "Personal"
    }
