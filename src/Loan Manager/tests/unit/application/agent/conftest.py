"""Shared fixtures for the KCH-235/KCH-237/KCH-243 agent tool tests."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.entities.report import Report
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.domain.value_objects.status import LoanStatus, ReportStatus

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
    """READ methods behave like the real repository over an in-memory list.
    WRITE methods raise instead of mutating -- the PROPOSE-tool guard
    (`test_propose_no_loan_write.py`) hands a PROPOSE tool's handler a UoW
    built on this fake and asserts the handler never trips one, i.e. never
    reaches a loan write, exactly ARB D-6 (agent proposes, never writes)."""

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

    def get_by_reference_id(self, ref_id: str) -> Loan | None:
        return next(
            (loan for loan in self._loans if str(loan.reference_id) == ref_id), None
        )

    def save(self, loan: Loan) -> Loan:
        raise AssertionError("loan write")

    def delete(self, reference_id: str) -> None:
        raise AssertionError("loan write")

    def bulk_update_status(self, updates: list[tuple[str, LoanStatus]]) -> None:
        raise AssertionError("loan write")

    def bulk_update_dates(self, updates: list[dict]) -> None:
        raise AssertionError("loan write")

    def set_inactive(self, reference_id: str) -> None:
        raise AssertionError("loan write")


class FakeReportRepo:
    """Backed by a list the caller supplies, shared across every
    `FakeUnitOfWork` a single `uow_factory_for(...)` call produces -- so a
    report `GenerateReport` saves inside one `with uow_factory() as uow:`
    block is visible to `GetPendingReports`/another use case's own,
    separate `with uow_factory() as uow:` block later, matching how the
    real SQLAlchemy-backed UoW behaves across two `with` blocks over the
    same session/database."""

    def __init__(self, store: list[Report]) -> None:
        self._store = store

    def get_by_report_id(self, report_id: str) -> Report | None:
        return next(
            (r for r in self._store if str(r.report_id) == report_id), None
        )

    def get_all_pending(self) -> list[Report]:
        return [r for r in self._store if r.status == ReportStatus.PENDING]

    def save(self, report: Report) -> Report:
        if report.id is None:
            report.id = len(self._store) + 1
        for i, existing in enumerate(self._store):
            if existing.id == report.id:
                self._store[i] = report
                return report
        self._store.append(report)
        return report

    def mark_approved(self, report_id: str) -> None:
        raise AssertionError("PROPOSE tools never approve a report")

    def mark_declined(self, report_id: str) -> None:
        raise AssertionError("PROPOSE tools never decline a report")

    def mark_reverted(self, report_id: str) -> None:
        raise AssertionError("PROPOSE tools never revert a report")

    def get_pending_reference_ids(self) -> set[str]:
        return {
            rec.reference_id
            for r in self.get_all_pending()
            for rec in r.records
            if rec.reference_id is not None
        }

    def assign_reference_id(self, record_id: int, ref_id: str) -> None:
        raise AssertionError("PROPOSE tools never approve a report")


class FakeReportMeta:
    def __init__(self) -> None:
        self._last_order: dict[str, int] = {}

    def get_last_order(self, date_str: str) -> int | None:
        return self._last_order.get(date_str)

    def set_last_order(self, date_str: str, order: int) -> None:
        self._last_order[date_str] = order


class FakeUnitOfWork:
    def __init__(
        self, loans: list[Loan], reports_store: list[Report], report_meta: FakeReportMeta
    ) -> None:
        self.loans = FakeLoanRepo(loans)
        self.reports = FakeReportRepo(reports_store)
        self.report_meta = report_meta

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(self, *exc_info) -> bool:
        return False

    def commit(self) -> None:
        pass


def uow_factory_for(
    loans: list[Loan], reports_store: list[Report] | None = None
) -> Callable[[], FakeUnitOfWork]:
    store = reports_store if reports_store is not None else []
    report_meta = FakeReportMeta()
    return lambda: FakeUnitOfWork(loans, store, report_meta)


def assert_no_npi_leak(observation: dict, *forbidden_strings: str) -> None:
    """KCH-243 orchestrator ruling: no observation any PROPOSE tool returns
    (`ok()` or `error()`) may contain a borrower/depositor NAME or GROUP
    string. `forbidden_strings` is every such value the calling test's loan
    fixture(s) actually used -- this scans the observation's whole JSON
    form (case-insensitive substring match), not just its top-level keys,
    so a leak nested inside e.g. `items`/`candidates` is caught too."""
    import json

    blob = json.dumps(observation, default=str).lower()
    for s in forbidden_strings:
        if not s:
            continue
        assert s.lower() not in blob, f"observation leaked NPI string {s!r}: {observation!r}"
