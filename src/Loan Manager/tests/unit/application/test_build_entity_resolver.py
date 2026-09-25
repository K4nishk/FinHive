"""Unit tests for BuildEntityResolver (KCH-236).

Not wired into the Container -- KCH-238 will consume it from the agent tool
surface. Uses a fake GetAutocompleteValues (duck-typed, matching the
`.execute(field)` interface) rather than the real DB-backed use case.
"""
from __future__ import annotations

import pytest
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.domain.errors import DataUnreadableError
from loan_manager.domain.services.entity_resolver import NAME_FIELDS, EntityResolver


class _FakeGetAutocompleteValues:
    def __init__(
        self,
        values_by_field: dict[str, list[str]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._values_by_field = values_by_field or {}
        self._error = error
        self.calls: list[str] = []

    def execute(self, field: str) -> list[str]:
        self.calls.append(field)
        if self._error is not None:
            raise self._error
        return self._values_by_field.get(field, [])


class TestBuildEntityResolver:
    def test_loads_all_four_fields_via_get_autocomplete(self):
        fake = _FakeGetAutocompleteValues(
            {
                "borrower_name": ["rohit sharma"],
                "borrower_group": ["sharma"],
                "depositor_name": ["meera iyer"],
                "depositor_group": ["dg1"],
            }
        )
        resolver = BuildEntityResolver(fake).execute()

        assert fake.calls == list(NAME_FIELDS)
        assert isinstance(resolver, EntityResolver)
        assert resolver.entities() == (
            ("borrower_name", "rohit sharma"),
            ("borrower_group", "sharma"),
            ("depositor_name", "meera iyer"),
            ("depositor_group", "dg1"),
        )

    def test_data_unreadable_propagates(self):
        fake = _FakeGetAutocompleteValues(error=DataUnreadableError("key mismatch"))
        with pytest.raises(DataUnreadableError):
            BuildEntityResolver(fake).execute()
