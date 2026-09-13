from __future__ import annotations

from datetime import date

from loan_manager.domain.value_objects.status import LoanStatus


class StatusEngine:
    @staticmethod
    def compute(giving_date: date, due_date: date | None, today: date) -> LoanStatus:
        """Compute loan status based on giving_date, due_date, and today.

        Rules (evaluated in order):
        1. giving_date > today -> Pending
        2. due_date is None and giving_date <= today -> Overdue
        3. giving_date <= today < due_date -> Active
        4. due_date <= today -> Overdue
        """
        if giving_date > today:
            return LoanStatus.PENDING

        if due_date is None:
            return LoanStatus.OVERDUE

        if today < due_date:
            return LoanStatus.ACTIVE

        return LoanStatus.OVERDUE
