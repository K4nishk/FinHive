from __future__ import annotations

from typing import Callable


class GetAutocompleteValues:
    def __init__(self, uow_factory: Callable) -> None:
        self._uow_factory = uow_factory

    def execute(self, field: str) -> list[str]:
        """Returns unique non-null lowercase values for the given field from active loans."""
        with self._uow_factory() as uow:
            values = uow.loans.get_unique_values(field, active_only=True)
        return [v.lower() for v in values if v]
