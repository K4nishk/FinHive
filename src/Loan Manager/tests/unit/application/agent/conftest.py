"""Shared fixtures for the KCH-235/KCH-237 agent tool tests."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.domain.value_objects.status import LoanStatus

# One minimal, VALID payload per tool name, reused across test_tool_args.py
# and test_tool_registry.py so the two files can't drift on what "valid"
# means for a given tool.
VALID_PAYLOADS: dict[str, dict[str, Any]] = {
    "get_current_context": {},
    "resolve_entity": {"text": "sharma group"},
    "query_loans": {"status": "overdue"},
    "get_portfolio_summary": {},
    "calculate_interest": {"ref_id": "2026_03_004", "rate": 12, "months": 3},
    "format_inr": {"amount": "1500.50"},
    "extend_loan": {"ref_id": "2026_03_004", "months": 3, "rate": 12},
    "create_loan": {
        "borrower_name": "Ravi Kumar",
        "borrower_group": "sharma-group",
        "depositor_name": "Meena Shah",
        "amount": 150000,
    },
    "update_loan": {"ref_id": "2026_03_004", "amount": 200000},
    "extend_overdue_batch": {"borrower_group": "sharma-group", "months": 3, "rate": 12},
}


# ── fake unit-of-work for the KCH-237 READ-tool tests ──────────────────────
# Same shape as tests/unit/application/test_get_all_loans_by_months.py's
# fakes, extended with get_unique_values so GetAutocompleteValues (and, via
# it, BuildEntityResolver) also work against it — no DB anywhere in this
# directory's tests.

_ref_counter = 0


def make_loan(
    *,
    borrower_name: str = "borrower",
    borrower_group: str = "bg1",
    depositor_name: str = "depositor",
    depositor_group: str | None = "dg1",
    amount: int = 10000,
    giving_date=None,
    due_date=None,
    due_period: int | None = None,
    status=None,
    is_active: bool = True,
) -> Loan:
    """A minimally-specified active Loan for fake-repo fixtures. `status` is
    accepted only to prove tools ignore it (StatusEngine derives the real
    one) — it defaults to something a computed status would never equal by
    accident-free construction (PENDING), never left implicit."""
    global _ref_counter
    _ref_counter += 1
    now = datetime(2026, 1, 1)
    return Loan(
        id=_ref_counter,
        reference_id=ReferenceId(f"2026_01_{_ref_counter:03d}"),
        borrower_name=borrower_name,
        borrower_group=borrower_group,
        depositor_name=depositor_name,
        depositor_group=depositor_group,
        amount=Money(amount),
        giving_date=giving_date if giving_date is not None else date(2026, 1, 1),
        due_period=due_period,
        due_date=due_date,
        status=status if status is not None else LoanStatus.PENDING,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


class FakeLoanRepo:
    def __init__(self, loans: list[Loan]) -> None:
        self._loans = loans

    def get_all_active(self, filters: dict | None = None) -> list[Loan]:
        loans = list(self._loans)
        if filters:
            for field_name, value in filters.items():
                if not value:
                    continue
                norm = value.strip().lower()
                loans = [
                    loan
                    for loan in loans
                    if (getattr(loan, field_name, None) or "").strip().lower() == norm
                ]
        return loans

    def get_unique_values(self, field: str, active_only: bool = True) -> list[str]:
        values = {getattr(loan, field, None) for loan in self._loans}
        return sorted(v for v in values if v)


class FakeUnitOfWork:
    def __init__(self, loans: list[Loan]) -> None:
        self.loans = FakeLoanRepo(loans)

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(self, *exc_info) -> bool:
        return False


def uow_factory_for(loans: list[Loan]) -> Callable[[], FakeUnitOfWork]:
    return lambda: FakeUnitOfWork(loans)
