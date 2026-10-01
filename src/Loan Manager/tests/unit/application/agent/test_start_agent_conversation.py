"""KCH-239 StartAgentConversation: one session TokenMap over active + protected names."""
from __future__ import annotations

from datetime import date

import pytest
from loan_manager.application.agent import tokeniser as tk
from loan_manager.application.agent.tool_registry import parse_args
from loan_manager.application.agent.tools.propose_tools import build_propose_registry
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.agent.start_agent_conversation import (
    StartAgentConversation,
)
from loan_manager.application.use_cases.loans.build_entity_resolver import BuildEntityResolver
from loan_manager.application.use_cases.loans.get_autocomplete import GetAutocompleteValues
from loan_manager.application.use_cases.loans.get_protected_names import GetProtectedNames
from loan_manager.application.use_cases.reports.get_reports import GetPendingReports

from .conftest import make_loan, uow_factory_for


def _start(uf) -> StartAgentConversation:
    ga = GetAutocompleteValues(uf)
    ids = iter(["c-1", "c-2"])
    return StartAgentConversation(
        BuildEntityResolver(ga), GetProtectedNames(ga, GetPendingReports(uf)),
        new_id=lambda: next(ids),
    )


def test_inactive_and_pending_report_names_are_masked() -> None:
    active = make_loan(borrower_name="anil sharma", borrower_group="sharma group",
                       depositor_name="meera iyer", depositor_group="dg1")
    inactive = make_loan(borrower_name="old kumar", borrower_group="kumar family",
                         depositor_name="gone mehra", depositor_group="dg2", is_active=False)
    reports: list = []
    uf = uow_factory_for([active, inactive], reports)
    create = build_propose_registry(uf, FixedClock(date(2026, 6, 1)), EventBus(),
                                    user_request="new loan").handler("create_loan")
    assert create(parse_args("create_loan", {
        "borrower_name": "Pending Pandit", "borrower_group": "sharma group",
        "depositor_name": "meera iyer", "amount": 150000,
    }))["ok"] is True

    conv = _start(uf).execute()

    out = conv.token_map.tokenise_prompt("did old kumar or pending pandit or gone mehra pay?")
    assert out == "did Q001 or Q002 or Q003 pay?"
    with pytest.raises(tk.PlaintextLeakError):
        tk.assert_no_plaintext({"messages": [{"role": "user", "content": "old kumar paid"}]},
                               conv.token_map)


def test_each_conversation_has_its_own_id_token_map_and_empty_state() -> None:
    uf = uow_factory_for([make_loan(borrower_name="anil sharma", borrower_group="sharma group",
                                    depositor_name="meera iyer", depositor_group="dg1")])
    start = _start(uf)

    first, second = start.execute(), start.execute()

    assert (first.conversation_id, second.conversation_id) == ("c-1", "c-2")
    assert first.token_map is not second.token_map
    assert first.turns == [] and first.closed is False
    first.token_map.tokenise_prompt("anil sharma")
    assert second.token_map.tokenise_prompt("anil sharma") == "B001"
