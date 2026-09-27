"""format_inr: render a rupee amount the Indian way (KCH-237).

`grep -r "₹" loan_manager` returns zero hits today — no display code formats
INR with the Indian digit-grouping convention (last 3 digits, then pairs:
1,85,000.00, not the Western 185,000.00). This is that one function.

Negative amounts are rejected outright: `FormatInr.amount` already carries
`Field(ge=0, ...)` at the tool-args boundary (`tools/args.py`), so a negative
value can only reach the pure `format_inr` function via a direct call, never
through the tool; rejecting it here too keeps the pure function's contract
honest on its own, independent of that boundary.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from loan_manager.application.agent.tools.observations import ok

_TWO_PLACES = Decimal("0.01")


def _group_indian(integer_part: str) -> str:
    """Indian digit grouping: the last 3 digits form one group, everything
    before that groups in pairs. "185000" -> "1,85,000"; "12345678" ->
    "1,23,45,678"."""
    if len(integer_part) <= 3:
        return integer_part
    last_three = integer_part[-3:]
    rest = integer_part[:-3]
    pairs: list[str] = []
    while len(rest) > 2:
        pairs.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        pairs.insert(0, rest)
    return ",".join([*pairs, last_three])


def format_inr(amount: Decimal) -> str:
    """"₹1,85,000.00" for `Decimal("185000")`. Quantises to 2dp with
    ROUND_HALF_UP (CLAUDE.md: Python's default context rounds half-even).
    Formats via `f"{q:f}"`, never `str(q)`, so an amount that arrived in
    exponent form (e.g. `Decimal("1.85E+5")`) renders as plain digits rather
    than "1.85E+5.00"."""
    if amount < 0:
        raise ValueError("format_inr does not support negative amounts")
    if amount == 0:
        # Decimal("-0") is not `< 0` (it equals 0) so it passes the guard
        # above unnormalised; left alone, `f"{Decimal('-0.00'):f}"` renders
        # "-0.00" -- a sign no rupee amount should ever carry.
        amount = Decimal(0)
    quantized = amount.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    text = f"{quantized:f}"
    integer_part, _, fractional_part = text.partition(".")
    fractional_part = fractional_part.ljust(2, "0")[:2]
    return f"₹{_group_indian(integer_part)}.{fractional_part}"


class FormatInrTool:
    def execute(self, args: Any) -> dict[str, Any]:
        return ok(formatted=format_inr(args.amount))
