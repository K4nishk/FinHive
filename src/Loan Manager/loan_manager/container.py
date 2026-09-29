"""
ApplicationServiceLocator -- wires dependencies together.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from loan_manager.infrastructure.database.session import DatabaseSession
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService
from loan_manager.infrastructure.recovery.backup_service import BackupService
from loan_manager.infrastructure.security.key_provider import (
    load_keys,
    set_active_key_ring,
)
from loan_manager.application.event_bus import EventBus
from loan_manager.application.agent.llm_port import LLMPort
from loan_manager.application.agent.tools.propose_tools import build_propose_registry
from loan_manager.application.agent.tools.read_tools import build_read_registry
from loan_manager.application.interfaces.clock import Clock, SystemClock
from loan_manager.application.interfaces.turn_recorder import (
    NullTurnRecorder,
    TurnRecorder,
)
from loan_manager.application.use_cases.agent.run_agent_turn import RunAgentTurn
from loan_manager.application.use_cases.agent.start_agent_conversation import (
    StartAgentConversation,
)
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.loans.get_protected_names import (
    GetProtectedNames,
)
from loan_manager.application.use_cases.reports.get_reports import GetPendingReports

if TYPE_CHECKING:  # pragma: no cover - typing only
    from finhive.db.keys import KeyRing


class Container:
    def __init__(self) -> None:
        self.recovery_service = RecoveryService()
        self.backup_service = BackupService()
        self.event_bus = EventBus()
        self.clock: Clock = SystemClock()
        self.turn_recorder: TurnRecorder = NullTurnRecorder()
        self._key_ring: KeyRing | None = None

    def get_uow(self) -> SqlAlchemyUnitOfWork:
        session = DatabaseSession.get_session()
        return SqlAlchemyUnitOfWork(session)

    def get_key_ring(self) -> KeyRing:
        """The master key ring, loaded once per process.

        Lazy rather than loaded in `__init__` so constructing a Container in a
        test that never touches encryption does not require a configured key.
        Callers that write NPI must go through here -- repositories never read
        the environment themselves.
        """
        if self._key_ring is None:
            self._key_ring = load_keys()
            # Wires up the encrypted-column TypeDecorators (KCH-227) -- they
            # cannot reach this Container, so this is the one call site that
            # makes the just-loaded ring the active key they read.
            set_active_key_ring(self._key_ring)
        return self._key_ring

    def get_run_agent_turn(self, llm: LLMPort | None = None) -> RunAgentTurn:
        """The Ask FinHive turn loop. `llm` is injectable (tests pass a
        `RecordedFakeLLM`); by default it is the OpenRouter client built from
        `data/settings.json`. Construction opens no connection -- the first
        `complete()` call does -- but a missing API key raises
        `LLMConfigError` here, at construction."""
        if llm is None:
            from loan_manager.infrastructure.llm.openai_compat_client import (
                OpenAICompatClient,
            )
            from loan_manager.infrastructure.llm.settings import load_llm_settings

            llm = OpenAICompatClient(load_llm_settings())
        uow_factory = self.get_uow

        def propose_registry_for(*, user_request: str, turn_id: str):
            return build_propose_registry(
                uow_factory,
                self.clock,
                self.event_bus,
                user_request=user_request,
                turn_id=turn_id,
            )

        return RunAgentTurn(
            llm,
            build_read_registry(uow_factory, self.clock),
            propose_registry_for,
            recorder=self.turn_recorder,
        )

    def get_start_agent_conversation(self) -> StartAgentConversation:
        uow_factory = self.get_uow
        get_autocomplete = GetAutocompleteValues(uow_factory)
        return StartAgentConversation(
            BuildEntityResolver(get_autocomplete),
            GetProtectedNames(get_autocomplete, GetPendingReports(uow_factory)),
            new_id=lambda: uuid.uuid4().hex,
        )
