"""Unit tests for loan_manager.application.agent.tools.read_tools (KCH-237)."""
from __future__ import annotations

from datetime import date

import pytest
from loan_manager.application.agent.tool_registry import (
    TOOL_SPECS,
    ToolMode,
    UnknownToolError,
    parse_args,
)
from loan_manager.application.agent.tools.read_tools import build_read_registry
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.domain.value_objects.status import LoanStatus

from .conftest import make_loan, uow_factory_for

_READ_NAMES = {name for name, spec in TOOL_SPECS.items() if spec.mode is ToolMode.READ}
_PROPOSE_NAMES = {name for name, spec in TOOL_SPECS.items() if spec.mode is ToolMode.PROPOSE}


def test_registry_covers_exactly_read_specs() -> None:
    registry = build_read_registry(uow_factory_for([]), FixedClock(date(2026, 6, 1)))
    for name in _READ_NAMES:
        assert callable(registry.handler(name))
    for name in _PROPOSE_NAMES:
        with pytest.raises(UnknownToolError):
            registry.handler(name)


def test_handlers_dispatch_parsed_args() -> None:
    loan = make_loan(
        status=LoanStatus.ACTIVE, giving_date=date(2026, 1, 1), due_date=date(2026, 12, 31)
    )
    registry = build_read_registry(uow_factory_for([loan]), FixedClock(date(2026, 6, 1)))

    context_args = parse_args("get_current_context", {})
    context_result = registry.handler("get_current_context")(context_args)
    assert context_result["ok"] is True
    assert context_result["today"] == "2026-06-01"

    query_args = parse_args("query_loans", {"status": "active"})
    query_result = registry.handler("query_loans")(query_args)
    assert query_result["ok"] is True
    assert query_result["count"] == 1

    format_args = parse_args("format_inr", {"amount": "1500"})
    format_result = registry.handler("format_inr")(format_args)
    assert format_result == {"ok": True, "formatted": "₹1,500.00"}
