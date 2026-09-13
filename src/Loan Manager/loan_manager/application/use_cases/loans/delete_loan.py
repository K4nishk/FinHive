from __future__ import annotations

from typing import Callable


class DeleteLoan:
    def __init__(self, uow_factory: Callable) -> None:
        self._uow_factory = uow_factory

    def execute(self, reference_id: str) -> None:
        with self._uow_factory() as uow:
            # Check loan exists
            loan = uow.loans.get_by_reference_id(reference_id)
            if loan is None:
                raise ValueError(f"Loan not found: {reference_id}")

            # Check loan is not in a pending report
            pending_refs = uow.reports.get_pending_reference_ids()
            if reference_id in pending_refs:
                raise ValueError(
                    f"Cannot delete loan {reference_id}: it is part of a pending report"
                )

            uow.loans.delete(reference_id)
            uow.commit()
