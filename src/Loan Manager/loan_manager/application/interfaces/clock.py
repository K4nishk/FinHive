"""Clock -- the one seam for "today" in the application layer.

`SystemClock` is the production implementation and the only place in
`application/` allowed to call `date.today()`. Every use case that needs
"today" for a status or ref-id computation takes a `Clock` (defaulting to
`SystemClock()`), so tests can pin a `FixedClock` instead of monkeypatching
the `date` builtin at each call site.
"""
from __future__ import annotations

from datetime import date
from typing import Protocol


class Clock(Protocol):
    def today(self) -> date: ...


class SystemClock:
    def today(self) -> date:
        return date.today()


class FixedClock:
    def __init__(self, today: date) -> None:
        self._today = today

    def today(self) -> date:
        return self._today
