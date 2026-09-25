from __future__ import annotations

from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.domain.services.entity_resolver import NAME_FIELDS, EntityResolver


class BuildEntityResolver:
    """Assembles an EntityResolver over the four NAME_FIELDS.

    Not wired into the Container (KCH-236 scope is the resolver itself;
    KCH-238 wires it into the agent tool surface). Reuses
    GetAutocompleteValues rather than a new repository query -- Ponytail
    rung 2: the encrypted-at-rest values are already fetched, decrypted and
    lowercased there.
    """

    def __init__(self, get_autocomplete: GetAutocompleteValues) -> None:
        self._get_autocomplete = get_autocomplete

    def execute(self) -> EntityResolver:
        values = {field: self._get_autocomplete.execute(field) for field in NAME_FIELDS}
        return EntityResolver(values)
