from __future__ import annotations

from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.reports.get_reports import GetPendingReports
from loan_manager.domain.services.entity_resolver import NAME_FIELDS


class GetProtectedNames:
    """Every borrower/depositor/group name the Ask FinHive tokeniser must
    never let leave in clear (KCH-238R, owner decision D3): the names on
    EVERY loan, inactive included, plus every name in a PENDING report
    (a proposed new borrower is not on any loan yet).

    Feeds `TokenMap(resolver, protected=...)`. The `EntityResolver` itself
    stays active-only (`BuildEntityResolver`): these names are protected,
    never resolved to as if they were live loans.

    Values are lowercased, like `GetAutocompleteValues`.
    """

    def __init__(
        self,
        get_autocomplete: GetAutocompleteValues,
        get_pending_reports: GetPendingReports,
    ) -> None:
        self._get_autocomplete = get_autocomplete
        self._get_pending_reports = get_pending_reports

    def execute(self) -> dict[str, list[str]]:
        names: dict[str, set[str]] = {
            field: set(self._get_autocomplete.execute(field, active_only=False))
            for field in NAME_FIELDS
        }
        for report in self._get_pending_reports.execute():
            for record in report.records:
                for field in NAME_FIELDS:
                    value = getattr(record, field, None)
                    if value and value.strip():
                        names[field].add(value.lower())
        return {field: sorted(values) for field, values in names.items()}
