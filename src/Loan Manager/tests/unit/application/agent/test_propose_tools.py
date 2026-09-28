"""Unit tests for loan_manager.application.agent.tools.propose_tools
(KCH-243)."""
from __future__ import annotations

from datetime import date

import pytest
from loan_manager.application.agent.tool_registry import (
    TOOL_SPECS,
    ToolMode,
    UnknownToolError,
    parse_args,
)
from loan_manager.application.agent.tools.propose_tools import build_propose_registry
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.domain.value_objects.status import ReportActor

from .conftest import make_loan, uow_factory_for

_READ_NAMES = {name for name, spec in TOOL_SPECS.items() if spec.mode is ToolMode.READ}
_PROPOSE_NAMES = {name for name, spec in TOOL_SPECS.items() if spec.mode is ToolMode.PROPOSE}


def _build(loans, reports_store=None, **kwargs):
    reports_store = reports_store if reports_store is not None else []
    uow_factory = uow_factory_for(loans, reports_store)
    registry = build_propose_registry(
        uow_factory, FixedClock(date(2026, 6, 1)), EventBus(), **kwargs
    )
    return registry, reports_store


def test_registry_is_exactly_propose_specs() -> None:
    registry, _ = _build([], user_request="test")
    for name in _PROPOSE_NAMES:
        assert callable(registry.handler(name))
    for name in _READ_NAMES:
        with pytest.raises(UnknownToolError):
            registry.handler(name)


def test_context_reaches_report() -> None:
    """user_request/turn_id passed to build_propose_registry land on the
    ReportDTO every one of this registry's PROPOSE tools writes, with
    actor always AGENT -- never left to a call site to forget."""
    loan = make_loan(giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1))
    registry, reports_store = _build(
        [loan], user_request="please extend this loan", turn_id="turn-42"
    )

    args = parse_args(
        "extend_loan", {"ref_id": str(loan.reference_id), "months": 3, "rate": 12}
    )
    result = registry.handler("extend_loan")(args)

    assert result["ok"] is True
    assert len(reports_store) == 1
    report = reports_store[0]
    assert report.actor == ReportActor.AGENT
    assert report.user_request == "please extend this loan"
    assert report.turn_id == "turn-42"


def test_context_turn_id_optional() -> None:
    loan = make_loan(giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1))
    registry, reports_store = _build([loan], user_request="please extend this loan")

    args = parse_args(
        "extend_loan", {"ref_id": str(loan.reference_id), "months": 3, "rate": 12}
    )
    result = registry.handler("extend_loan")(args)

    assert result["ok"] is True
    assert reports_store[0].turn_id is None
