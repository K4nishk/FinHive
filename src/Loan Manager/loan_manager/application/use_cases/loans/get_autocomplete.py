from __future__ import annotations

from typing import Callable


class GetAutocompleteValues:
    def __init__(self, uow_factory: Callable) -> None:
        self._uow_factory = uow_factory

    def execute(self, field: str) -> list[str]:
        """Returns unique non-null lowercase values for the given field from active loans.

        Propagates `DataUnreadableError` rather than swallowing it: a caller
        that cannot decrypt the loan book needs to say so, not render an
        empty dropdown that looks like "you have no borrowers yet".
        """
        with self._uow_factory() as uow:
            values = uow.loans.get_unique_values(field, active_only=True)
        return [v.lower() for v in values if v]
