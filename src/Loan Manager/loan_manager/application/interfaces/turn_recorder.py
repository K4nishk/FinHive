"""KCH-239: where a finished agent turn is handed for the audit/replay trail.

`NullTurnRecorder` is the only implementation today (the Container wires it);
a persisting recorder is a later issue (KCH-240). `TurnRecord.user_text` is
what the user TYPED, and the text of the FINAL event in `events` is the
answer REHYDRATED (real names, rupee amounts): both are NPI, so any
implementation that persists them must encrypt them at rest (ARB D-15) -- the
application layer does not decide storage. Every other event, and the
`completions`, carry tokens only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from loan_manager.application.agent.llm_port import Completion
from loan_manager.application.agent.trace import TraceEvent, TurnOutcome


@dataclass(frozen=True)
class TurnRecord:
    conversation_id: str
    turn_id: str
    prompt_version: str
    user_text: str
    outcome: TurnOutcome
    step_count: int
    events: tuple[TraceEvent, ...]
    completions: tuple[Completion, ...]


class TurnRecorder(Protocol):
    def record(self, record: TurnRecord) -> None: ...


class NullTurnRecorder:
    def record(self, record: TurnRecord) -> None:
        return None
