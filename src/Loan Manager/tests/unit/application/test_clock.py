"""Unit tests for the Clock seam (KCH-233).

SystemClock is the only place in application/ allowed to call
`date.today()`; FixedClock lets use-case tests pin "today" instead of
monkeypatching the `date` builtin at each call site.
"""
from __future__ import annotations

from datetime import date

from loan_manager.application.interfaces.clock import FixedClock, SystemClock
from loan_manager.container import Container


class TestSystemClock:
    def test_system_clock_returns_today(self):
        clock = SystemClock()
        assert clock.today() == date.today()


class TestFixedClock:
    def test_fixed_clock_returns_pinned_date(self):
        pinned = date(2020, 1, 15)
        clock = FixedClock(pinned)
        assert clock.today() == pinned
        # Pinning is stable across repeated calls -- it never drifts to the
        # real wall-clock date the way SystemClock would.
        assert clock.today() == pinned


class TestContainerClock:
    def test_container_exposes_system_clock(self):
        container = Container()
        assert isinstance(container.clock, SystemClock)
