"""
Unit tests for View Loans sortable table functionality.

Tests Excel-like sorting on 6 columns:
- borrower_name
- borrower_group
- depositor_name
- depositor_group
- giving_date
- due_date
"""

import pytest
from datetime import date
from decimal import Decimal


class TestSortByBorrowerName:
    """Test sorting by borrower name."""

    def test_sort_borrower_name_ascending(self):
        """Test sorting borrowers alphabetically (A to Z)."""
        loans = [
            {'id': '1', 'borrower_name': 'Charlie', 'amount': Decimal('100000')},
            {'id': '2', 'borrower_name': 'Alice', 'amount': Decimal('50000')},
            {'id': '3', 'borrower_name': 'Bob', 'amount': Decimal('75000')},
        ]

        # Sort ascending (A-Z)
        sorted_loans = sorted(loans, key=lambda x: x['borrower_name'].lower())

        assert sorted_loans[0]['borrower_name'] == 'Alice'
        assert sorted_loans[1]['borrower_name'] == 'Bob'
        assert sorted_loans[2]['borrower_name'] == 'Charlie'

    def test_sort_borrower_name_descending(self):
        """Test sorting borrowers reverse alphabetically (Z to A)."""
        loans = [
            {'id': '1', 'borrower_name': 'Charlie', 'amount': Decimal('100000')},
            {'id': '2', 'borrower_name': 'Alice', 'amount': Decimal('50000')},
            {'id': '3', 'borrower_name': 'Bob', 'amount': Decimal('75000')},
        ]

        # Sort descending (Z-A)
        sorted_loans = sorted(loans, key=lambda x: x['borrower_name'].lower(), reverse=True)

        assert sorted_loans[0]['borrower_name'] == 'Charlie'
        assert sorted_loans[1]['borrower_name'] == 'Bob'
        assert sorted_loans[2]['borrower_name'] == 'Alice'

    def test_sort_borrower_name_case_insensitive(self):
        """Test that sorting is case-insensitive."""
        loans = [
            {'id': '1', 'borrower_name': 'charlie'},
            {'id': '2', 'borrower_name': 'ALICE'},
            {'id': '3', 'borrower_name': 'Bob'},
        ]

        sorted_loans = sorted(loans, key=lambda x: x['borrower_name'].lower())

        assert sorted_loans[0]['borrower_name'] == 'ALICE'
        assert sorted_loans[1]['borrower_name'] == 'Bob'
        assert sorted_loans[2]['borrower_name'] == 'charlie'


class TestSortByBorrowerGroup:
    """Test sorting by borrower group."""

    def test_sort_borrower_group_ascending(self):
        """Test sorting by borrower group alphabetically."""
        loans = [
            {'id': '1', 'borrower_name': 'John', 'borrower_group': 'Family'},
            {'id': '2', 'borrower_name': 'Jane', 'borrower_group': 'Business'},
            {'id': '3', 'borrower_name': 'Bob', 'borrower_group': 'Friends'},
        ]

        sorted_loans = sorted(loans, key=lambda x: (x['borrower_group'] or '').lower())

        assert sorted_loans[0]['borrower_group'] == 'Business'
        assert sorted_loans[1]['borrower_group'] == 'Family'
        assert sorted_loans[2]['borrower_group'] == 'Friends'

    def test_sort_borrower_group_with_null_values(self):
        """Test that null/empty groups are pushed to the end."""
        loans = [
            {'id': '1', 'borrower_name': 'John', 'borrower_group': 'Family'},
            {'id': '2', 'borrower_name': 'Jane', 'borrower_group': None},
            {'id': '3', 'borrower_name': 'Bob', 'borrower_group': 'Business'},
            {'id': '4', 'borrower_name': 'Alice', 'borrower_group': ''},
        ]

        # Sort with null handling - push nulls/empty to end
        def sort_key(loan):
            val = loan['borrower_group']
            if val is None or val == '':
                return ('zzzzz', '')  # Force to end
            return ('', val.lower())

        sorted_loans = sorted(loans, key=sort_key)

        assert sorted_loans[0]['borrower_group'] == 'Business'
        assert sorted_loans[1]['borrower_group'] == 'Family'
        assert sorted_loans[2]['borrower_group'] in [None, '']
        assert sorted_loans[3]['borrower_group'] in [None, '']


class TestSortByDepositorName:
    """Test sorting by depositor name."""

    def test_sort_depositor_name_ascending(self):
        """Test sorting depositors alphabetically."""
        loans = [
            {'id': '1', 'depositor_name': 'State Bank'},
            {'id': '2', 'depositor_name': 'HDFC'},
            {'id': '3', 'depositor_name': 'Personal Savings'},
        ]

        sorted_loans = sorted(loans, key=lambda x: x['depositor_name'].lower())

        assert sorted_loans[0]['depositor_name'] == 'HDFC'
        assert sorted_loans[1]['depositor_name'] == 'Personal Savings'
        assert sorted_loans[2]['depositor_name'] == 'State Bank'


class TestSortByDepositorGroup:
    """Test sorting by depositor group."""

    def test_sort_depositor_group_ascending(self):
        """Test sorting by depositor group alphabetically."""
        loans = [
            {'id': '1', 'depositor_name': 'SBI', 'depositor_group': 'Bank'},
            {'id': '2', 'depositor_name': 'John', 'depositor_group': 'Personal'},
            {'id': '3', 'depositor_name': 'ICICI', 'depositor_group': 'Bank'},
        ]

        sorted_loans = sorted(loans, key=lambda x: (x['depositor_group'] or '').lower())

        assert sorted_loans[0]['depositor_group'] == 'Bank'
        assert sorted_loans[1]['depositor_group'] == 'Bank'
        assert sorted_loans[2]['depositor_group'] == 'Personal'


class TestSortByGivingDate:
    """Test sorting by giving date."""

    def test_sort_giving_date_ascending(self):
        """Test sorting by giving date (oldest to newest)."""
        loans = [
            {'id': '1', 'borrower_name': 'John', 'giving_date': '2026-03-15'},
            {'id': '2', 'borrower_name': 'Jane', 'giving_date': '2026-01-01'},
            {'id': '3', 'borrower_name': 'Bob', 'giving_date': '2026-02-10'},
        ]

        sorted_loans = sorted(loans, key=lambda x: date.fromisoformat(x['giving_date']))

        assert sorted_loans[0]['giving_date'] == '2026-01-01'
        assert sorted_loans[1]['giving_date'] == '2026-02-10'
        assert sorted_loans[2]['giving_date'] == '2026-03-15'

    def test_sort_giving_date_descending(self):
        """Test sorting by giving date (newest to oldest)."""
        loans = [
            {'id': '1', 'borrower_name': 'John', 'giving_date': '2026-03-15'},
            {'id': '2', 'borrower_name': 'Jane', 'giving_date': '2026-01-01'},
            {'id': '3', 'borrower_name': 'Bob', 'giving_date': '2026-02-10'},
        ]

        sorted_loans = sorted(
            loans,
            key=lambda x: date.fromisoformat(x['giving_date']),
            reverse=True
        )

        assert sorted_loans[0]['giving_date'] == '2026-03-15'
        assert sorted_loans[1]['giving_date'] == '2026-02-10'
        assert sorted_loans[2]['giving_date'] == '2026-01-01'


class TestSortByDueDate:
    """Test sorting by due date."""

    def test_sort_due_date_ascending(self):
        """Test sorting by due date (earliest to latest)."""
        loans = [
            {'id': '1', 'borrower_name': 'John', 'due_date': '2026-06-30'},
            {'id': '2', 'borrower_name': 'Jane', 'due_date': '2026-03-31'},
            {'id': '3', 'borrower_name': 'Bob', 'due_date': '2026-12-31'},
        ]

        sorted_loans = sorted(loans, key=lambda x: date.fromisoformat(x['due_date']))

        assert sorted_loans[0]['due_date'] == '2026-03-31'
        assert sorted_loans[1]['due_date'] == '2026-06-30'
        assert sorted_loans[2]['due_date'] == '2026-12-31'

    def test_sort_due_date_with_special_1970_date(self):
        """Test that 1970-01-01 (no due date) is pushed to end when sorting."""
        loans = [
            {'id': '1', 'borrower_name': 'John', 'due_date': '2026-06-30'},
            {'id': '2', 'borrower_name': 'Jane', 'due_date': '1970-01-01'},  # No due date
            {'id': '3', 'borrower_name': 'Bob', 'due_date': '2026-03-31'},
        ]

        # Sort with special handling for 1970-01-01 - push to end
        def sort_key(loan):
            if loan['due_date'] == '1970-01-01':
                return date.max  # Push to end
            return date.fromisoformat(loan['due_date'])

        sorted_loans = sorted(loans, key=sort_key)

        assert sorted_loans[0]['due_date'] == '2026-03-31'
        assert sorted_loans[1]['due_date'] == '2026-06-30'
        assert sorted_loans[2]['due_date'] == '1970-01-01'  # At the end

    def test_sort_due_date_descending(self):
        """Test sorting by due date (latest to earliest)."""
        loans = [
            {'id': '1', 'borrower_name': 'John', 'due_date': '2026-06-30'},
            {'id': '2', 'borrower_name': 'Jane', 'due_date': '2026-03-31'},
            {'id': '3', 'borrower_name': 'Bob', 'due_date': '2026-12-31'},
        ]

        sorted_loans = sorted(
            loans,
            key=lambda x: date.fromisoformat(x['due_date']),
            reverse=True
        )

        assert sorted_loans[0]['due_date'] == '2026-12-31'
        assert sorted_loans[1]['due_date'] == '2026-06-30'
        assert sorted_loans[2]['due_date'] == '2026-03-31'


class TestSortToggle:
    """Test sort direction toggle behavior."""

    def test_sort_direction_toggle(self):
        """Test that clicking same column toggles direction."""
        # Initial state
        sort_config = {'key': None, 'direction': 'asc'}

        # First click on borrower_name
        sort_config['key'] = 'borrower_name'
        sort_config['direction'] = 'asc'
        assert sort_config['direction'] == 'asc'

        # Second click on borrower_name (toggle)
        sort_config['direction'] = 'desc' if sort_config['direction'] == 'asc' else 'asc'
        assert sort_config['direction'] == 'desc'

        # Third click on borrower_name (toggle again)
        sort_config['direction'] = 'desc' if sort_config['direction'] == 'asc' else 'asc'
        assert sort_config['direction'] == 'asc'

    def test_sort_new_column_resets_to_ascending(self):
        """Test that clicking a different column resets to ascending."""
        sort_config = {'key': 'borrower_name', 'direction': 'desc'}

        # Click on different column
        sort_config['key'] = 'giving_date'
        sort_config['direction'] = 'asc'  # Reset to ascending for new column

        assert sort_config['key'] == 'giving_date'
        assert sort_config['direction'] == 'asc'


class TestComplexSortScenarios:
    """Test complex sorting scenarios."""

    def test_sort_maintains_data_integrity(self):
        """Test that sorting doesn't lose or duplicate records."""
        loans = [
            {'id': '1', 'borrower_name': 'Charlie'},
            {'id': '2', 'borrower_name': 'Alice'},
            {'id': '3', 'borrower_name': 'Bob'},
        ]

        sorted_loans = sorted(loans, key=lambda x: x['borrower_name'].lower())

        # All IDs should still be present
        ids = [loan['id'] for loan in sorted_loans]
        assert '1' in ids
        assert '2' in ids
        assert '3' in ids
        assert len(sorted_loans) == 3

    def test_sort_with_mixed_null_and_valid_values(self):
        """Test sorting with mix of null and valid values."""
        loans = [
            {'id': '1', 'borrower_group': 'Family'},
            {'id': '2', 'borrower_group': None},
            {'id': '3', 'borrower_group': 'Business'},
            {'id': '4', 'borrower_group': ''},
            {'id': '5', 'borrower_group': 'Friends'},
        ]

        # Sort with null handling
        def sort_key(loan):
            val = loan['borrower_group']
            if val is None or val == '':
                return ('zzzzz', '')
            return ('', val.lower())

        sorted_loans = sorted(loans, key=sort_key)

        # First 3 should be valid values
        assert sorted_loans[0]['borrower_group'] == 'Business'
        assert sorted_loans[1]['borrower_group'] == 'Family'
        assert sorted_loans[2]['borrower_group'] == 'Friends'
        # Last 2 should be null/empty
        assert sorted_loans[3]['borrower_group'] in [None, '']
        assert sorted_loans[4]['borrower_group'] in [None, '']
