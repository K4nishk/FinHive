"""Interest calculator — pure functions, no I/O, no app state.

BC-05 Interpretation B (confirmed by R5 worked example):
    Time = extension_period ONLY.
    The formula charges only the extension window, not the original tenure.

    R5 authoritative example:
        Rs 10,000 at 12% for 1-month extension -> Rs 100
        Proof: (10000 * 12 * 1) / (12 * 100) = 100. Correct only if Time = 1 (extension_period).

Formulae from REQUIREMENTS.md R5:
    Monthly:
        Time       = extension_period (in months)
        Interest   = (Amount * interest_rate * extension_period) / (12 * 100)
        Commission = (Amount * commission_rate * extension_period) / (12 * 100)

    Daily:
        Time       = extension_period (in days)
        Interest   = (Amount * interest_rate * extension_period) / (365 * 100)
        Commission = (Amount * commission_rate * extension_period) / (365 * 100)

    TDS (when tds_flag=True):
        TDS = 0.1 * Interest

Partial-month rounding applies to months_between() utility only (used for display/UI).
It does not affect interest calculation since Time = extension_period directly.

Public API:
    months_between(giving_date, due_date) -> int
    days_between(giving_date, due_date) -> int
    calculate_monthly(record: dict) -> dict
        Accepts a record dict with keys: amount, interest_rate, commission_rate,
        giving_date, due_date, extension_period, tds_flag.
        Returns a new dict with computed keys merged in:
        interest_amount, commission_amount, tds_amount, time_months.
    calculate_daily(record: dict) -> dict
        Same as calculate_monthly but for Daily mode.
        Returns computed keys: interest_amount, commission_amount, tds_amount, time_days.
    calculate_both(record: dict) -> dict
        Orchestrator for Mode = Both (R5). Routes by extension_period_unit:
            "months" -> calculate_monthly(record), result includes time_months key
            "days"   -> calculate_daily(record), result includes time_days key
        Raises ValueError for unknown extension_period_unit values.
"""
from datetime import date

from dateutil.relativedelta import relativedelta


def months_between(giving_date: date, due_date: date) -> int:
    """Return the number of complete months between giving_date and due_date.

    Partial months are rounded UP.
    Example: 2026-01-02 to 2026-04-02 = 3 months exactly.
    Example: 2026-01-15 to 2026-02-16 = 2 months (1 month + 1 day, rounded up).

    Used for display and UI purposes. Does not affect interest calculation
    since Time = extension_period directly per BC-05 Interpretation B.
    """
    if due_date <= giving_date:
        return 0

    rd = relativedelta(due_date, giving_date)
    whole_months = rd.years * 12 + rd.months

    if rd.days > 0 or rd.hours > 0 or rd.minutes > 0 or rd.seconds > 0:
        whole_months += 1  # round up partial month

    return whole_months


def days_between(giving_date: date, due_date: date) -> int:
    """Return the number of calendar days between giving_date and due_date.

    Returns 0 if due_date <= giving_date.
    Used for display and UI purposes. Does not affect interest calculation
    since Time = extension_period directly per BC-05 Interpretation B.
    """
    if due_date <= giving_date:
        return 0
    return (due_date - giving_date).days


def calculate_monthly(record: dict) -> dict:
    """Compute interest, commission, and optional TDS for Monthly mode.

    Accepts a record dict with keys:
        amount, interest_rate, commission_rate, giving_date, due_date,
        extension_period, tds_flag
    Returns a new dict containing the input fields plus computed keys:
        interest_amount, commission_amount, tds_amount, time_months

    Formula (R5, Monthly mode, BC-05 Interpretation B confirmed):
        Time       = extension_period (months)
        Interest   = (Amount * interest_rate * extension_period) / (12 * 100)
        Commission = (Amount * commission_rate * extension_period) / (12 * 100)
        TDS        = 0.1 * Interest  (only when tds_flag=True, else 0.0)

    giving_date and due_date are passed through in the result for compatibility
    with UI and report code; they do not affect the calculation.
    """
    amount = record["amount"]
    interest_rate = record["interest_rate"]
    commission_rate = record["commission_rate"]
    extension_period = record.get("extension_period", 0)
    tds_flag = record.get("tds_flag", False)

    time_months = extension_period

    interest_amount = (amount * interest_rate * time_months) / (12 * 100)
    commission_amount = (amount * commission_rate * time_months) / (12 * 100)
    tds_amount = 0.1 * interest_amount if tds_flag else 0.0

    result = dict(record)
    result["interest_amount"] = interest_amount
    result["commission_amount"] = commission_amount
    result["tds_amount"] = tds_amount
    result["time_months"] = time_months
    return result


def calculate_daily(record: dict) -> dict:
    """Compute interest, commission, and optional TDS for Daily mode.

    Accepts a record dict with keys:
        amount, interest_rate, commission_rate, giving_date, due_date,
        extension_period, tds_flag
    Returns a new dict containing the input fields plus computed keys:
        interest_amount, commission_amount, tds_amount, time_days

    Formula (R5, Daily mode, BC-05 Interpretation B confirmed):
        Time       = extension_period (days)
        Interest   = (Amount * interest_rate * extension_period) / (365 * 100)
        Commission = (Amount * commission_rate * extension_period) / (365 * 100)
        TDS        = 0.1 * Interest  (only when tds_flag=True, else 0.0)

    giving_date and due_date are passed through in the result for compatibility
    with UI and report code; they do not affect the calculation.
    """
    amount = record["amount"]
    interest_rate = record["interest_rate"]
    commission_rate = record["commission_rate"]
    extension_period = record.get("extension_period", 0)
    tds_flag = record.get("tds_flag", False)

    time_days = extension_period

    interest_amount = (amount * interest_rate * time_days) / (365 * 100)
    commission_amount = (amount * commission_rate * time_days) / (365 * 100)
    tds_amount = 0.1 * interest_amount if tds_flag else 0.0

    result = dict(record)
    result["interest_amount"] = interest_amount
    result["commission_amount"] = commission_amount
    result["tds_amount"] = tds_amount
    result["time_days"] = time_days
    return result


def calculate_both(record: dict) -> dict:
    """Orchestrator for Mode = Both (R5). Routes by extension_period_unit.

    Accepts a record dict with keys:
        amount, interest_rate, commission_rate, giving_date, due_date,
        extension_period, extension_period_unit, tds_flag

    Routes:
        extension_period_unit == "months" -> calculate_monthly(record)
            Result includes time_months key.
        extension_period_unit == "days"   -> calculate_daily(record)
            Result includes time_days key.
        Any other value -> raises ValueError.

    Returns the result dict from the routed function.
    """
    unit = record.get("extension_period_unit", "")
    if unit == "months":
        return calculate_monthly(record)
    if unit == "days":
        return calculate_daily(record)
    raise ValueError(f"Unknown extension_period_unit: {unit!r}")
