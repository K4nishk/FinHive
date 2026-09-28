"""build_propose_registry: assembles the four PROPOSE tool handlers
(extend_loan, extend_overdue_batch, create_loan, update_loan -- KCH-243)
into a `ToolRegistry` (`tool_registry.py`, KCH-235). READ tools are
`read_tools.build_read_registry`'s scope -- this registry never carries one.

Built fresh per agent turn: `user_request`/`turn_id` are turn-scoped
(`ProposalContext`), so a new registry -- not a cached one -- is the unit
that ties every report a turn's tool calls write back to that turn.
"""
from __future__ import annotations

from collections.abc import Callable

from loan_manager.application.agent.tool_registry import ToolRegistry
from loan_manager.application.agent.tools.propose_common import ProposalContext
from loan_manager.application.agent.tools.propose_create import CreateLoanTool
from loan_manager.application.agent.tools.propose_extend import (
    ExtendLoanTool,
    ExtendOverdueBatchTool,
)
from loan_manager.application.agent.tools.propose_update import UpdateLoanTool
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import Clock
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.application.use_cases.reports.calculate_interest import (
    CalculateInterest,
)
from loan_manager.application.use_cases.reports.generate_report import GenerateReport
from loan_manager.application.use_cases.reports.get_reports import GetPendingReports


def build_propose_registry(
    uow_factory: Callable,
    clock: Clock,
    event_bus: EventBus,
    *,
    user_request: str,
    turn_id: str | None = None,
) -> ToolRegistry:
    ctx = ProposalContext(user_request=user_request, turn_id=turn_id)

    get_all_loans = GetAllLoans(uow_factory, clock=clock)
    get_autocomplete = GetAutocompleteValues(uow_factory)
    build_resolver = BuildEntityResolver(get_autocomplete)
    get_pending_reports = GetPendingReports(uow_factory)
    calculate_interest = CalculateInterest(uow_factory)
    generate_report = GenerateReport(uow_factory, event_bus)

    extend_tool = ExtendLoanTool(
        get_all_loans, get_pending_reports, generate_report, clock, ctx
    )
    batch_tool = ExtendOverdueBatchTool(
        get_all_loans,
        get_autocomplete,
        build_resolver,
        get_pending_reports,
        calculate_interest,
        generate_report,
        clock,
        ctx,
    )
    create_tool = CreateLoanTool(get_autocomplete, build_resolver, generate_report, clock, ctx)
    update_tool = UpdateLoanTool(
        get_all_loans, get_autocomplete, build_resolver, get_pending_reports, generate_report, ctx
    )

    return ToolRegistry(
        {
            "extend_loan": extend_tool.execute,
            "extend_overdue_batch": batch_tool.execute,
            "create_loan": create_tool.execute,
            "update_loan": update_tool.execute,
        }
    )
