"""Unit tests for loan_manager.application.agent.tools.read_format (KCH-237)."""
from __future__ import annotations

from decimal import Decimal

import pytest
from loan_manager.application.agent.tool_registry import parse_args
from loan_manager.application.agent.tools.read_format import FormatInrTool, format_inr


def test_indian_grouping_185000() -> None:
    assert format_inr(Decimal("185000")) == "₹1,85,000.00"


def test_crore_grouping() -> None:
    assert format_inr(Decimal("12345678")) == "₹1,23,45,678.00"


def test_exponent_form_decimal() -> None:
    """A Decimal built in exponent form (e.g. from `parse_float=Decimal` on a
    provider's `1.85e5`) must render as plain digits, not "1.85E+5.00" —
    `str(d)` alone would keep the exponent; `f"{q:f}"` does not."""
    assert format_inr(Decimal("1.85E+5")) == "₹1,85,000.00"


def test_half_up_rounding() -> None:
    """CLAUDE.md: ROUND_HALF_UP, not Python's default half-even — 100.005
    must round to 100.01, not 100.00."""
    assert format_inr(Decimal("100.005")) == "₹100.01"


def test_small_amounts() -> None:
    assert format_inr(Decimal("5")) == "₹5.00"
    assert format_inr(Decimal("0")) == "₹0.00"
    assert format_inr(Decimal("500")) == "₹500.00"


def test_negative_amount_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        format_inr(Decimal("-1"))


def test_negative_zero_decimal_renders_as_positive_zero() -> None:
    """`Decimal("-0")` is not `< 0` (it equals 0), so it slips past the
    negative guard; unnormalised, `f"{Decimal('-0.00'):f}"` renders "-0.00",
    a sign no rupee amount should ever carry."""
    assert format_inr(Decimal("-0")) == "₹0.00"


def test_negative_zero_via_parse_args_json() -> None:
    """A provider's JSON literal `-0.0`, parsed with `parse_float=Decimal`
    (tool_registry.parse_args), also reaches format_inr as a negative zero —
    `FormatInr.amount`'s `ge=0` constraint accepts it since `-0.0 >= 0` is
    numerically true."""
    args = parse_args("format_inr", '{"amount": -0.0}')
    result = FormatInrTool().execute(args)
    assert result == {"ok": True, "formatted": "₹0.00"}


def test_format_inr_tool_wraps_pure_function() -> None:
    class _Args:
        amount = Decimal("185000")

    result = FormatInrTool().execute(_Args())
    assert result == {"ok": True, "formatted": "₹1,85,000.00"}
