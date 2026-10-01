"""RunAgentTurn -- one user question through the bounded agent loop (KCH-239).

The loop is the only place the tokeniser (KCH-238) and the tool registries
(KCH-235/237/243) meet an `LLMPort` (KCH-234):

  user text --tokenise_prompt--> [system, last HISTORY_TURNS answered turns,
  this turn] --assert_no_plaintext--> LLM --tool calls--> detokenise_args ->
  parse_args -> handler -> tokenise_observation -> delimiter-wrapped tool
  message -> LLM ... -> final text --rehydrate--> the human.

Guarantees, each pinned by `tests/unit/application/agent/test_run_agent_turn.py`:
  - at most MAX_STEPS model calls per turn; the sixth answer that is still a
    tool call ends in `budget_exhausted`, never a truncated answer (the
    sixth step's tool calls DO run -- accepted ruling, REVIEW REQUIRED);
  - the leak guard runs on the WHOLE outbound body before every send, so a
    body that would leak is never sent and the session recovers next turn;
  - a tool call that fails validation is answered with a scrubbed
    `INVALID_ARGS` observation (field and rule names only, never the value);
    the third rejection in one turn ends it (`validation_exhausted`);
  - only ANSWERED turns enter history; a failed turn leaves none of its
    messages behind, and history is trimmed by whole turns;
  - exactly one FINAL trace event and one recorder call per `execute`, on
    every path.

An unexpected exception from a tool handler ends the turn as
`internal_error` with fixed text (its message can carry names); the FINAL
event and the recorder call still happen.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from loan_manager.application.agent.llm_port import (
    Completion,
    LLMError,
    LLMPort,
)
from loan_manager.application.agent.system_prompt import (
    PROMPT_VERSION,
    SYSTEM_MESSAGE,
    UNTRUSTED_CLOSE,
    UNTRUSTED_OPEN,
)
from loan_manager.application.agent.tokeniser import (
    PlaintextLeakError,
    TokenBudgetExceededError,
    TokenMap,
    UnknownTokenError,
    assert_no_plaintext,
)
from loan_manager.application.agent.tool_registry import (
    TOOL_SPECS,
    ToolArgsError,
    ToolMode,
    ToolRegistry,
    UnknownToolError,
    parse_args,
    tool_schemas,
)
from loan_manager.application.agent.tools.observations import ErrorCode, error
from loan_manager.application.agent.trace import TraceEvent, TraceKind, TurnOutcome
from loan_manager.application.agent.turn_mode import turn_mode
from loan_manager.application.interfaces.turn_recorder import (
    NullTurnRecorder,
    TurnRecord,
    TurnRecorder,
)

MAX_STEPS = 6
MAX_VALIDATION_RETRIES = 2
# [REVIEW REQUIRED] how many earlier answered turns the model is shown.
HISTORY_TURNS = 3
# KCH-246 (owner decision D2): longest typed question accepted, in characters.
# Checked in `_guarded` before the tokeniser and before any model call; the
# use case is the only guard (no QLineEdit.setMaxLength: it truncates silently).
MAX_PROMPT_CHARS = 2000

_OUTCOME_TEXT: Mapping[TurnOutcome, str] = {
    TurnOutcome.BUDGET_EXHAUSTED: (
        f"I could not finish within {MAX_STEPS} steps. Please ask a narrower question."
    ),
    TurnOutcome.VALIDATION_EXHAUSTED: (
        "I could not form a valid request for that. Please rephrase the question."
    ),
    TurnOutcome.INCOMPLETE_ANSWER: (
        "The answer came back incomplete. Please ask again."
    ),
    TurnOutcome.BLOCKED_PLAINTEXT: (
        "I stopped before sending the next request: it or an answer contained "
        "data that must not leave this machine. Please rephrase and ask again."
    ),
    TurnOutcome.UNKNOWN_TOKEN: (
        "Codes such as B001 or AMOUNT_1 cannot be typed. Please rewrite the "
        "question without them."
    ),
    TurnOutcome.PROMPT_TOO_LONG: (
        f"That question is too long (limit {MAX_PROMPT_CHARS:,} characters). "
        "Please shorten it."
    ),
    TurnOutcome.CONVERSATION_FULL: (
        "This conversation has reached its limit. Please start a new one."
    ),
    TurnOutcome.LLM_ERROR: "The assistant is unavailable right now. Please try again.",
    TurnOutcome.INTERNAL_ERROR: "Something went wrong while answering. Please try again.",
}

_REJECTED_CODES = frozenset({"INVALID_ARGS", "UNKNOWN_TOKEN", "CHANGE_NOT_REQUESTED"})


@dataclass
class Conversation:
    """One chat session: its own `TokenMap` (a token means the same thing
    for the whole session), the answered turns kept as history, and a
    `closed` flag set when the token budget ran out."""

    conversation_id: str
    token_map: TokenMap
    turns: list[list[dict[str, Any]]] = field(default_factory=list)
    closed: bool = False


@dataclass(frozen=True)
class TurnResult:
    outcome: TurnOutcome
    text: str
    turn_id: str
    step_count: int


@dataclass
class _Turn:
    turn_id: str
    user_text: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    completions: list[Completion] = field(default_factory=list)
    events: list[TraceEvent] = field(default_factory=list)
    step: int = 0
    rejections: int = 0
    proposals: int = 0
    propose_registry: ToolRegistry | None = None
    mode: ToolMode = ToolMode.READ


def _noop(event: TraceEvent) -> None:
    return None


def _default_new_id() -> str:
    return uuid.uuid4().hex


# Every declared argument name across all tools: the only `loc` parts a
# validation error may name back to the model. An invented key could itself
# be a name, so anything else is replaced.
_KNOWN_FIELDS: frozenset[str] = frozenset(
    name for spec in TOOL_SPECS.values() for name in spec.args_model.model_fields
)
_AMOUNT_TOKEN_RE = re.compile(r"AMOUNT_[0-9]+")


def _amount_arg_is_not_a_token(raw: str) -> bool:
    """True when any `amount` argument is present and is not an AMOUNT_n token
    string. The model is never shown a raw amount, so a number there was
    invented; it must not reach a handler (a PROPOSE tool would persist it).
    Whether the token was issued is `detokenise_args`'s check."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return False  # not JSON: parse_args reports it

    def walk(node: Any) -> bool:
        if isinstance(node, Mapping):
            for key, value in node.items():
                if key == "amount" and value is not None:
                    if not (isinstance(value, str) and _AMOUNT_TOKEN_RE.fullmatch(value)):
                        return True
                elif walk(value):
                    return True
        elif isinstance(node, list):
            return any(walk(v) for v in node)
        return False

    return walk(data)


_RULE_RE = re.compile(r"^[a-z0-9_.]{1,60}$")


def _scrub_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for item in exc.errors(include_input=False, include_url=False, include_context=False):
        loc = ".".join(
            str(p) if isinstance(p, int) or p in _KNOWN_FIELDS else "?" for p in item["loc"]
        )
        rule = item["type"] if _RULE_RE.match(item["type"]) else "invalid"
        parts.append(f"argument '{loc}' failed rule '{rule}'")
    return "; ".join(parts) or "arguments failed validation"


def _tool_message(call_id: str, observation: Mapping[str, Any]) -> dict[str, Any]:
    # A JSON payload can only hold "<" inside a string, where < is the
    # same character: escaping it means data can never spell UNTRUSTED_CLOSE.
    body = json.dumps(observation, ensure_ascii=False).replace("<", "\\u003c")
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": f"{UNTRUSTED_OPEN}\n{body}\n{UNTRUSTED_CLOSE}",
    }


def _assistant_message(completion: Completion) -> dict[str, Any]:
    """The model's own message exactly as it came back (KCH-238 review 2 n2:
    the tokeniser skips its Q/N-text check for the assistant role, so what is
    stored under that role must be the raw completion, never rehydrated)."""
    message: dict[str, Any] = {"role": "assistant", "content": completion.content}
    if completion.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in completion.tool_calls
        ]
    return message


class RunAgentTurn:
    def __init__(
        self,
        llm: LLMPort,
        read_registry: ToolRegistry,
        propose_registry_for: Callable[..., ToolRegistry],
        *,
        recorder: TurnRecorder | None = None,
        new_id: Callable[[], str] = _default_new_id,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._llm = llm
        self._read_registry = read_registry
        self._propose_registry_for = propose_registry_for
        self._recorder: TurnRecorder = recorder or NullTurnRecorder()
        self._new_id = new_id
        self._monotonic = monotonic
        # KCH-246: schemas per turn mode. A READ turn is never offered a
        # PROPOSE tool (structural, not a prompt request).
        self._tools_by_mode = {
            ToolMode.READ: tool_schemas(frozenset({ToolMode.READ})),
            ToolMode.PROPOSE: tool_schemas(),
        }

    def execute(
        self,
        conversation: Conversation,
        user_text: str,
        emit: Callable[[TraceEvent], None] = _noop,
    ) -> TurnResult:
        t0 = self._monotonic()
        turn = _Turn(turn_id=self._new_id(), user_text=user_text)

        def emit_event(event: TraceEvent) -> None:
            turn.events.append(event)
            emit(event)

        outcome, text = self._guarded(conversation, turn, emit_event)
        if outcome is not TurnOutcome.ANSWERED and turn.proposals:
            # A proposal is persisted the moment its tool returns; a turn that
            # then fails must not leave the user thinking nothing happened.
            text += (
                f" {turn.proposals} draft proposal(s) from this question were "
                "queued for approval; review them in Pending Approval."
            )
        emit_event(
            TraceEvent(
                kind=TraceKind.FINAL,
                step=turn.step,
                max_steps=MAX_STEPS,
                text=text,
                outcome=outcome,
            )
        )
        self._recorder.record(
            TurnRecord(
                conversation_id=conversation.conversation_id,
                turn_id=turn.turn_id,
                prompt_version=PROMPT_VERSION,
                # R1: an oversized prompt is never stored.
                user_text="" if outcome is TurnOutcome.PROMPT_TOO_LONG else user_text,
                outcome=outcome,
                step_count=turn.step,
                events=tuple(turn.events),
                completions=tuple(turn.completions),
                latency_ms=int((self._monotonic() - t0) * 1000),
            )
        )
        return TurnResult(outcome, text, turn.turn_id, turn.step)

    def _guarded(
        self,
        conversation: Conversation,
        turn: _Turn,
        emit: Callable[[TraceEvent], None],
    ) -> tuple[TurnOutcome, str]:
        if conversation.closed:
            return self._failed(TurnOutcome.CONVERSATION_FULL)
        if len(turn.user_text) > MAX_PROMPT_CHARS:
            return self._failed(TurnOutcome.PROMPT_TOO_LONG)
        try:
            return self._run(conversation, turn, emit)
        # Order matters: TokenBudgetExceededError IS a PlaintextLeakError.
        except TokenBudgetExceededError:
            conversation.closed = True
            return self._failed(TurnOutcome.CONVERSATION_FULL)
        except PlaintextLeakError:
            return self._failed(TurnOutcome.BLOCKED_PLAINTEXT)
        except UnknownTokenError:
            return self._failed(TurnOutcome.UNKNOWN_TOKEN)
        except LLMError:
            return self._failed(TurnOutcome.LLM_ERROR)
        except Exception:
            # A handler bug. Fixed text only: str(exc) can carry names.
            return self._failed(TurnOutcome.INTERNAL_ERROR)

    @staticmethod
    def _failed(outcome: TurnOutcome) -> tuple[TurnOutcome, str]:
        return outcome, _OUTCOME_TEXT[outcome]

    def _run(
        self,
        conversation: Conversation,
        turn: _Turn,
        emit: Callable[[TraceEvent], None],
    ) -> tuple[TurnOutcome, str]:
        tm = conversation.token_map
        # Latched once from the user's typed text only (KCH-246 D1).
        turn.mode = turn_mode(turn.user_text)
        tools = self._tools_by_mode[turn.mode]
        # Ingress: a typed token-shaped literal raises UnknownTokenError here,
        # before any model call.
        turn.messages.append({"role": "user", "content": tm.tokenise_prompt(turn.user_text)})
        history = [m for past in conversation.turns[-HISTORY_TURNS:] for m in past]

        for step in range(1, MAX_STEPS + 1):
            messages = [dict(SYSTEM_MESSAGE), *history, *turn.messages]
            # The infrastructure body builder is off limits here (AST guard),
            # so guard the messages themselves: the same leaves it would send.
            assert_no_plaintext({"messages": messages}, tm)
            completion = self._llm.complete(messages, tools)
            turn.step = step
            turn.completions.append(completion)
            assistant = _assistant_message(completion)
            turn.messages.append(assistant)

            if not completion.tool_calls:
                return self._final(conversation, turn, completion, assistant)

            if completion.content and completion.content.strip():
                emit(
                    TraceEvent(
                        TraceKind.THOUGHT, step, MAX_STEPS, text=completion.content
                    )
                )
            for call in completion.tool_calls:
                emit(
                    TraceEvent(
                        TraceKind.ACTION,
                        step,
                        MAX_STEPS,
                        text=call.arguments,
                        tool=call.name,
                    )
                )
                observation, is_proposal = self._dispatch(turn, tm, call.name, call.arguments)
                tokenised = tm.tokenise_observation(observation)
                turn.messages.append(_tool_message(call.id, tokenised))
                emit(
                    TraceEvent(
                        TraceKind.PROPOSAL if is_proposal else TraceKind.OBSERVATION,
                        step,
                        MAX_STEPS,
                        tool=call.name,
                        payload=tokenised,
                    )
                )
                code = (observation.get("error") or {}).get("code")
                if is_proposal:
                    turn.proposals += 1
                if code in _REJECTED_CODES:
                    turn.rejections += 1
                    if turn.rejections > MAX_VALIDATION_RETRIES:
                        return self._failed(TurnOutcome.VALIDATION_EXHAUSTED)
        return self._failed(TurnOutcome.BUDGET_EXHAUSTED)

    def _final(
        self,
        conversation: Conversation,
        turn: _Turn,
        completion: Completion,
        assistant: dict[str, Any],
    ) -> tuple[TurnOutcome, str]:
        text = completion.content
        if completion.finish_reason == "length" or text is None or not text.strip():
            return self._failed(TurnOutcome.INCOMPLETE_ANSWER)
        tm = conversation.token_map
        # The answer is about to be stored as history and shown: a name or a
        # raw amount in it is stopped here, not one step later.
        assert_no_plaintext({"messages": [assistant]}, tm)
        conversation.turns.append(list(turn.messages))
        return TurnOutcome.ANSWERED, tm.rehydrate(text)

    def _dispatch(
        self,
        turn: _Turn,
        tm: TokenMap,
        name: str,
        raw_arguments: str,
    ) -> tuple[dict[str, Any], bool]:
        """(observation, is_proposal). Every model-side mistake becomes an
        observation the model can read; nothing about the offending value is
        echoed back."""
        try:
            mode = self._read_registry.mode(name)
            if mode is ToolMode.PROPOSE and turn.mode is not ToolMode.PROPOSE:
                return (
                    error(
                        ErrorCode.CHANGE_NOT_REQUESTED,
                        "the user did not ask for a change in this question",
                        "answer from reads; tell the user to ask for the change explicitly",
                    ),
                    False,
                )
            if _amount_arg_is_not_a_token(raw_arguments):
                return (
                    error(
                        ErrorCode.INVALID_ARGS,
                        "argument 'amount' must be an AMOUNT_n token from this conversation",
                        "pass the AMOUNT_n token you were shown, as a string; never a number",
                    ),
                    False,
                )
            args = parse_args(name, tm.detokenise_args(raw_arguments))
            if mode is ToolMode.READ:
                handler = self._read_registry.handler(name)
            else:
                if turn.propose_registry is None:
                    turn.propose_registry = self._propose_registry_for(
                        user_request=turn.user_text, turn_id=turn.turn_id
                    )
                handler = turn.propose_registry.handler(name)
        except UnknownTokenError:
            return (
                error(
                    ErrorCode.UNKNOWN_TOKEN,
                    "an argument contains a token that was never issued in this conversation",
                    "use only tokens you were shown, exactly as written, then retry",
                ),
                False,
            )
        except ValidationError as exc:
            return (
                error(
                    ErrorCode.INVALID_ARGS,
                    _scrub_validation_error(exc),
                    "fix the named arguments and call the tool again",
                ),
                False,
            )
        except (ToolArgsError, UnknownToolError):
            return (
                error(
                    ErrorCode.INVALID_ARGS,
                    "the tool call was not valid: unknown tool, or arguments that "
                    "are not a JSON object",
                    "call one of the listed tools with valid JSON arguments",
                ),
                False,
            )
        observation = handler(args)
        return observation, mode is ToolMode.PROPOSE and observation.get("ok") is True
