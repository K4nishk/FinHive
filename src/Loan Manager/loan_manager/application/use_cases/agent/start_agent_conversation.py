"""StartAgentConversation -- opens one Ask FinHive session (KCH-239).

One `TokenMap` for the session's whole life, built over the active-only
entity resolver plus the protected set (every name on every loan, inactive
included, and every name in a pending report -- KCH-238R owner decision D3),
so a name that is not in the live book still never leaves in clear.
"""
from __future__ import annotations

from collections.abc import Callable

from loan_manager.application.agent.tokeniser import TokenMap
from loan_manager.application.use_cases.agent.run_agent_turn import Conversation
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_protected_names import (
    GetProtectedNames,
)


class StartAgentConversation:
    def __init__(
        self,
        build_resolver: BuildEntityResolver,
        get_protected_names: GetProtectedNames,
        *,
        new_id: Callable[[], str],
    ) -> None:
        self._build_resolver = build_resolver
        self._get_protected_names = get_protected_names
        self._new_id = new_id

    def execute(self) -> Conversation:
        token_map = TokenMap(
            self._build_resolver.execute(), protected=self._get_protected_names.execute()
        )
        return Conversation(conversation_id=self._new_id(), token_map=token_map)
