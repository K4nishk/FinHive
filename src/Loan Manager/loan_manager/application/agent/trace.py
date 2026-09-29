"""KCH-239: the trace one agent turn emits (the UI's thought/action/observation
feed, KCH-241, and the turn recorder, `interfaces/turn_recorder.py`).

Every non-final event carries TOKENISED text only (B001/AMOUNT_n ...): the
trace is what a recorder persists and what a debug pane shows, and neither may
hold a name or an amount the model was never given. Only the FINAL event
carries text a human reads, rehydrated from the model's answer.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TraceKind(str, Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    PROPOSAL = "proposal"
    FINAL = "final"


class TurnOutcome(str, Enum):
    ANSWERED = "answered"
    BUDGET_EXHAUSTED = "budget_exhausted"
    VALIDATION_EXHAUSTED = "validation_exhausted"
    INCOMPLETE_ANSWER = "incomplete_answer"
    BLOCKED_PLAINTEXT = "blocked_plaintext"
    UNKNOWN_TOKEN = "unknown_token"  # noqa: S105 - an outcome name, not a secret
    CONVERSATION_FULL = "conversation_full"
    LLM_ERROR = "llm_error"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class TraceEvent:
    """`step` is the 1-based model call this event belongs to (0 before the
    first call); `max_steps` is the turn's hard cap. `outcome` is set on the
    FINAL event only."""

    kind: TraceKind
    step: int
    max_steps: int
    text: str = ""
    tool: str | None = None
    payload: dict[str, Any] | None = None
    outcome: TurnOutcome | None = None
