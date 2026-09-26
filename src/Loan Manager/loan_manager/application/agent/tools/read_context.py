"""get_current_context: today's date, quarter and financial-year boundaries
(KCH-237). The model has no wall clock of its own.

[REVIEW REQUIRED] Financial year is assumed Indian (1 Apr - 31 Mar, Q1 =
Apr-Jun): FinHive's loan book, borrower/depositor naming and rupee formatting
are all India-specific (see `read_format.py`), but no ARB decision pins the
FY convention explicitly. Flagging for confirmation rather than blocking on
it — every other MVP1.1 date convention already assumes India.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta

from loan_manager.application.agent.tools.observations import ok
from loan_manager.application.interfaces.clock import Clock


def period_bounds(today: date) -> dict[str, str]:
    """Pure: today's ISO date/weekday plus its Indian-FY, quarter and
    calendar-month boundaries, all as ISO-8601 date strings.

    FY runs 1 Apr - 31 Mar; Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec,
    Q4 = Jan-Mar. `relativedelta` does the month arithmetic (CLAUDE.md: no
    manual month maths) so a start-of-FY/quarter/month is never off by a day
    across a leap year or a 30-vs-31-day month boundary.
    """
    fy_start_year = today.year if today.month >= 4 else today.year - 1
    fy_start = date(fy_start_year, 4, 1)
    fy_end = fy_start + relativedelta(years=1) - timedelta(days=1)
    fy_label = f"FY{fy_start_year}-{str(fy_start_year + 1)[-2:]}"

    months_into_fy = (today.year - fy_start.year) * 12 + (today.month - fy_start.month)
    quarter_index = months_into_fy // 3 + 1  # 1..4
    quarter_start = fy_start + relativedelta(months=3 * (quarter_index - 1))
    quarter_end = quarter_start + relativedelta(months=3) - timedelta(days=1)

    month_start = today.replace(day=1)
    month_end = month_start + relativedelta(months=1) - timedelta(days=1)

    return {
        "today": today.isoformat(),
        "weekday": today.strftime("%A"),
        "fy_label": fy_label,
        "fy_start": fy_start.isoformat(),
        "fy_end": fy_end.isoformat(),
        "quarter": f"Q{quarter_index}",
        "quarter_start": quarter_start.isoformat(),
        "quarter_end": quarter_end.isoformat(),
        "month_start": month_start.isoformat(),
        "month_end": month_end.isoformat(),
    }


class GetCurrentContextTool:
    """`today` comes from the injected `Clock` only — never `date.today()`
    directly (CLAUDE.md; tests pin a `FixedClock`)."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def execute(self, args: Any = None) -> dict[str, Any]:
        return ok(**period_bounds(self._clock.today()))
