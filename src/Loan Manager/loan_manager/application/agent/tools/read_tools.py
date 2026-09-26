"""build_read_registry: assembles the six READ tool handlers (KCH-237) into
a `ToolRegistry` (`tool_registry.py`, KCH-235). PROPOSE tools are KCH-243's
scope — this registry never carries one.
"""
from __future__ import annotations

from collections.abc import Callable

from loan_manager.application.agent.tool_registry import ToolRegistry
from loan_manager.application.agent.tools.read_context import GetCurrentContextTool
from loan_manager.application.agent.tools.read_format import FormatInrTool
from loan_manager.application.agent.tools.read_interest import CalculateInterestTool
from loan_manager.application.agent.tools.read_portfolio import GetPortfolioSummaryTool
from loan_manager.application.agent.tools.read_query_loans import QueryLoansTool
from loan_manager.application.agent.tools.read_resolve import ResolveEntityTool
from loan_manager.application.interfaces.clock import Clock
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans


def build_read_registry(uow_factory: Callable, clock: Clock) -> ToolRegistry:
    get_all_loans = GetAllLoans(uow_factory, clock=clock)
    get_autocomplete = GetAutocompleteValues(uow_factory)
    build_resolver = BuildEntityResolver(get_autocomplete)

    return ToolRegistry(
        {
            "get_current_context": GetCurrentContextTool(clock).execute,
            "resolve_entity": ResolveEntityTool(build_resolver).execute,
            "query_loans": QueryLoansTool(get_all_loans, get_autocomplete, clock).execute,
            "get_portfolio_summary": GetPortfolioSummaryTool(get_all_loans, clock).execute,
            "calculate_interest": CalculateInterestTool(get_all_loans).execute,
            "format_inr": FormatInrTool().execute,
        }
    )
