from __future__ import annotations

from datetime import date
from typing import Callable

from loan_manager.domain.services.status_engine import StatusEngine


class RecomputeAllStatuses:
    def __init__(self, uow_factory: Callable) -> None:
        self._uow_factory = uow_factory

    def execute(self) -> int:
        """Recompute statuses for all active loans. Returns count of updated loans."""
        today = date.today()

        with self._uow_factory() as uow:
            loans = uow.loans.get_all_active()
            updates = []

            for loan in loans:
                new_status = StatusEngine.compute(loan.giving_date, loan.due_date, today)
                if new_status != loan.status:
                    updates.append((str(loan.reference_id), new_status))

            if updates:
                uow.loans.bulk_update_status(updates)
                uow.commit()

        return len(updates)
