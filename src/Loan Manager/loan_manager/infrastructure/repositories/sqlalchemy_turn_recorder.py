"""KCH-240: persists one finished Ask FinHive turn to `agent_turns`.

NPI: `user_text` and the FINAL event's text are rehydrated (real names and
rupee amounts); THOUGHT/ACTION text and the completions can echo a name the
model was never given a token for. So the WHOLE trace goes into one
`EncryptedJSON` blob and the user's words into an `EncryptedString`; the
plaintext columns carry only counts, ids, versions and the outcome name.
Never lift a payload field into a plaintext column without re-running that
audit.

`record()` never raises (the `TurnRecorder` contract): a lost audit row must
not fail the user's answer. Failures are counted in `failure_count` and
logged as the exception CLASS NAME only -- `str(exc)` and the record can
carry names.

`eval_scores_ct` (KCH-250) holds the grounding proxies of `application/agent/
grounding.py`: `faithfulness_proxy` and `raw_money_leak` only; the two proxies
that need ground truth are None in production. Scoring is best-effort and
caught on its own: a scoring bug yields `eval_scores=None`, the row is still
written and `failure_count` is untouched.

Deliberately its own session, not `SqlAlchemyUnitOfWork`: a turn row is not
part of any loan/report transaction.
"""
from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from loan_manager.application.agent.grounding import production_scores
from loan_manager.application.agent.llm_port import Completion
from loan_manager.application.agent.trace import TraceEvent
from loan_manager.application.interfaces.turn_recorder import TurnRecord
from loan_manager.infrastructure.database.models import AgentTurnModel
from loan_manager.infrastructure.security.key_provider import active_key_version

logger = logging.getLogger(__name__)


def _no_floats(value: Any) -> Any:
    # encrypt_json rejects floats. Money is Decimal end to end, so a float in a
    # payload is a score or ratio (resolve_entity's `score`); keep its text.
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dict):
        return {k: _no_floats(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_no_floats(v) for v in value]
    return value


def _event_json(event: TraceEvent) -> dict[str, Any]:
    return {
        "kind": event.kind.value,
        "step": event.step,
        "max_steps": event.max_steps,
        "text": event.text,
        "tool": event.tool,
        "payload": _no_floats(event.payload),
        "outcome": event.outcome.value if event.outcome is not None else None,
    }


def _cost_str(cost: Decimal | None) -> str | None:
    # Canonical fixed-point text: `str()` can emit "1.23E-7", and encrypt_json
    # would quantise a Decimal to 2 places, so cost travels as a string.
    return None if cost is None else format(cost, "f")


def _completion_json(completion: Completion) -> dict[str, Any]:
    usage = completion.usage
    return {
        "content": completion.content,
        "finish_reason": completion.finish_reason,
        "model": completion.model,
        "tool_calls": [
            {"id": c.id, "name": c.name, "arguments": c.arguments}
            for c in completion.tool_calls
        ],
        "usage": {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "cost_usd": _cost_str(usage.cost_usd),
        },
    }


def _trace_json(record: TurnRecord) -> dict[str, Any]:
    return {
        "events": [_event_json(e) for e in record.events],
        "completions": [_completion_json(c) for c in record.completions],
    }


def _total(values: list[Any]) -> Any:
    """Sum only when every completion reported it; else None (a partial sum
    would claim a count nobody made). None when there are no completions."""
    if not values or any(v is None for v in values):
        return None
    return sum(values)


class SqlAlchemyTurnRecorder:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._session_factory = session_factory
        self._now = now
        self.failure_count = 0

    def record(self, record: TurnRecord) -> None:
        session: Session | None = None
        try:
            session = self._session_factory()
            session.add(self._row(record))
            session.commit()
        except Exception as exc:  # noqa: BLE001 - the contract: never raise
            if session is not None:
                with contextlib.suppress(Exception):
                    session.rollback()
            self.failure_count += 1
            logger.warning("agent turn not recorded: %s", type(exc).__name__)
        finally:
            if session is not None:
                with contextlib.suppress(Exception):
                    session.close()

    @staticmethod
    def _eval_scores(record: TurnRecord) -> dict[str, Any] | None:
        try:
            return production_scores(record.events, record.completions)
        except Exception as exc:  # noqa: BLE001 - scoring must never lose the row
            logger.warning("agent turn not scored: %s", type(exc).__name__)
            return None

    def _row(self, record: TurnRecord) -> AgentTurnModel:
        completions = record.completions
        last = completions[-1] if completions else None
        cost = _total([c.usage.cost_usd for c in completions])
        return AgentTurnModel(
            id=record.turn_id,
            conversation_id=record.conversation_id,
            user_message=record.user_text,
            react_trace=_trace_json(record),
            prompt_tokens=_total([c.usage.prompt_tokens for c in completions]),
            completion_tokens=_total([c.usage.completion_tokens for c in completions]),
            cost_usd=_cost_str(cost),
            latency_ms=record.latency_ms or 0,
            model=last.model if last else None,
            key_version=active_key_version(),
            # SQLite DateTime is naive: store UTC wall-clock, tz stripped.
            created_at=self._now().replace(tzinfo=None),
            prompt_version=record.prompt_version,
            outcome=record.outcome.value,
            step_count=record.step_count,
            finish_reason=last.finish_reason if last else None,
            eval_scores=self._eval_scores(record),
        )
