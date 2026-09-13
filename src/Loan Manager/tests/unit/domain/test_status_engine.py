"""StatusEngine unit tests."""
from datetime import date

import pytest

from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.status import LoanStatus


class TestStatusEngine:
    def test_giving_date_in_future_returns_pending(self):
        today = date(2026, 6, 15)
        giving = date(2026, 7, 1)
        due = date(2026, 8, 1)
        assert StatusEngine.compute(giving, due, today) == LoanStatus.PENDING

    def test_giving_date_in_future_no_due_date_returns_pending(self):
        today = date(2026, 6, 15)
        giving = date(2026, 7, 1)
        assert StatusEngine.compute(giving, None, today) == LoanStatus.PENDING

    def test_no_due_date_giving_in_past_returns_overdue(self):
        today = date(2026, 6, 15)
        giving = date(2026, 5, 1)
        assert StatusEngine.compute(giving, None, today) == LoanStatus.OVERDUE

    def test_no_due_date_giving_equals_today_returns_overdue(self):
        today = date(2026, 6, 15)
        giving = date(2026, 6, 15)
        assert StatusEngine.compute(giving, None, today) == LoanStatus.OVERDUE

    def test_giving_past_due_in_future_returns_active(self):
        today = date(2026, 6, 15)
        giving = date(2026, 5, 1)
        due = date(2026, 7, 1)
        assert StatusEngine.compute(giving, due, today) == LoanStatus.ACTIVE

    def test_giving_equals_today_due_in_future_returns_active(self):
        today = date(2026, 6, 15)
        giving = date(2026, 6, 15)
        due = date(2026, 7, 15)
        assert StatusEngine.compute(giving, due, today) == LoanStatus.ACTIVE

    def test_due_date_equals_today_returns_overdue(self):
        today = date(2026, 6, 15)
        giving = date(2026, 5, 1)
        due = date(2026, 6, 15)
        assert StatusEngine.compute(giving, due, today) == LoanStatus.OVERDUE

    def test_due_date_in_past_returns_overdue(self):
        today = date(2026, 6, 15)
        giving = date(2026, 3, 1)
        due = date(2026, 5, 1)
        assert StatusEngine.compute(giving, due, today) == LoanStatus.OVERDUE

    def test_giving_equals_today_due_equals_today_returns_overdue(self):
        today = date(2026, 6, 15)
        assert StatusEngine.compute(today, today, today) == LoanStatus.OVERDUE

    def test_giving_today_due_tomorrow_returns_active(self):
        today = date(2026, 6, 15)
        due = date(2026, 6, 16)
        assert StatusEngine.compute(today, due, today) == LoanStatus.ACTIVE
