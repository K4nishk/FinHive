"""Unit tests for GetProtectedNames and GetAutocompleteValues(active_only)
(KCH-238R, owner decision D3: the tokeniser protects inactive-loan names and
names in pending reports, while the resolver stays active-only)."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from loan_manager.application.use_cases.loans.get_autocomplete import GetAutocompleteValues
from loan_manager.application.use_cases.loans.get_protected_names import GetProtectedNames
from loan_manager.domain.services.entity_resolver import NAME_FIELDS

from .agent.conftest import make_loan, uow_factory_for


class _FakePendingReports:
    def __init__(self, reports) -> None:
        self._reports = reports

    def execute(self):
        return self._reports


def _record(**names):
    base = dict.fromkeys(NAME_FIELDS)
    base.update(names)
    return SimpleNamespace(**base)


def test_get_autocomplete_active_only_by_default_all_loans_when_asked() -> None:
    active = make_loan(borrower_name="Anil Sharma")
    inactive = make_loan(borrower_name="Old Kumar", is_active=False, due_date=date(2026, 1, 2))
    uc = GetAutocompleteValues(uow_factory_for([active, inactive]))

    assert uc.execute("borrower_name") == ["anil sharma"]
    assert uc.execute("borrower_name", active_only=False) == ["anil sharma", "old kumar"]


def test_protected_names_are_every_loan_plus_pending_report_names() -> None:
    active = make_loan(borrower_name="anil sharma", borrower_group="sharma group",
                       depositor_name="meera iyer", depositor_group="dg1")
    inactive = make_loan(borrower_name="old kumar", borrower_group="kumar family",
                         depositor_name="gone mehra", depositor_group=None, is_active=False)
    pending = SimpleNamespace(records=[
        _record(borrower_name="Pending Pandit", depositor_name="meera iyer",
                depositor_group="  ", borrower_group="new grp"),
    ])
    uc = GetProtectedNames(
        GetAutocompleteValues(uow_factory_for([active, inactive])), _FakePendingReports([pending])
    )

    names = uc.execute()

    assert names == {
        "borrower_name": ["anil sharma", "old kumar", "pending pandit"],
        "borrower_group": ["kumar family", "new grp", "sharma group"],
        "depositor_name": ["gone mehra", "meera iyer"],
        "depositor_group": ["dg1"],
    }
