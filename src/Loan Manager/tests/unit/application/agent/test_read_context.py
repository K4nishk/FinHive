"""Unit tests for loan_manager.application.agent.tools.read_context (KCH-237)."""
from __future__ import annotations

from datetime import date

from loan_manager.application.agent.tools.read_context import (
    GetCurrentContextTool,
    period_bounds,
)
from loan_manager.application.interfaces.clock import FixedClock


def test_fy_boundary_march_31_vs_april_1() -> None:
    before = period_bounds(date(2026, 3, 31))
    after = period_bounds(date(2026, 4, 1))
    assert before["fy_label"] == "FY2025-26"
    assert before["fy_start"] == "2025-04-01"
    assert before["fy_end"] == "2026-03-31"
    assert after["fy_label"] == "FY2026-27"
    assert after["fy_start"] == "2026-04-01"
    assert after["fy_end"] == "2027-03-31"


def test_quarter_q4_jan() -> None:
    bounds = period_bounds(date(2027, 1, 15))
    assert bounds["quarter"] == "Q4"
    assert bounds["quarter_start"] == "2027-01-01"
    assert bounds["quarter_end"] == "2027-03-31"
    # Jan 2027 belongs to the FY that started April 2026, not January's own
    # calendar year.
    assert bounds["fy_label"] == "FY2026-27"


def test_month_end_february_non_leap_and_leap() -> None:
    non_leap = period_bounds(date(2026, 2, 10))
    assert non_leap["month_end"] == "2026-02-28"
    leap = period_bounds(date(2028, 2, 10))
    assert leap["month_end"] == "2028-02-29"


def test_month_end_31_day_month() -> None:
    bounds = period_bounds(date(2026, 7, 15))
    assert bounds["month_start"] == "2026-07-01"
    assert bounds["month_end"] == "2026-07-31"


def test_quarter_bounds_q1_through_q4() -> None:
    """FY2026-27: Q1 Apr-Jun, Q2 Jul-Sep, Q3 Oct-Dec, Q4 Jan-Mar (into 2027)."""
    q1 = period_bounds(date(2026, 5, 1))
    assert q1["quarter"] == "Q1"
    assert q1["quarter_start"] == "2026-04-01"
    assert q1["quarter_end"] == "2026-06-30"

    q2 = period_bounds(date(2026, 8, 1))
    assert q2["quarter"] == "Q2"
    assert q2["quarter_start"] == "2026-07-01"
    assert q2["quarter_end"] == "2026-09-30"

    q3 = period_bounds(date(2026, 11, 1))
    assert q3["quarter"] == "Q3"
    assert q3["quarter_start"] == "2026-10-01"
    assert q3["quarter_end"] == "2026-12-31"

    q4 = period_bounds(date(2027, 2, 1))
    assert q4["quarter"] == "Q4"
    assert q4["quarter_start"] == "2027-01-01"
    assert q4["quarter_end"] == "2027-03-31"


def test_today_from_clock() -> None:
    """`today` comes from the injected Clock, never `date.today()` directly."""
    clock = FixedClock(date(2026, 9, 26))
    tool = GetCurrentContextTool(clock)
    result = tool.execute()
    assert result["ok"] is True
    assert result["today"] == "2026-09-26"
    assert result["weekday"] == "Saturday"
    assert result["month_start"] == "2026-09-01"
    assert result["month_end"] == "2026-09-30"
