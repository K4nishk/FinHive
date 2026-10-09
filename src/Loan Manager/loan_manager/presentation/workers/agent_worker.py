"""KCH-241: runs ONE Ask FinHive turn off the UI thread.

`RunAgentTurn.execute` blocks on the network for up to six model calls, so it
never runs on the GUI thread. The worker streams each `TraceEvent` through
`event` and finishes with exactly one `done`, whatever happens.

Failure handling is fixed-text by construction: an exception escaping the use
case (a recorder or emit-callback failure, a construction failure) is logged by
TYPE NAME only. `str(exc)` and tracebacks can carry a borrower name or an
amount, and this process's log file is not a place for either.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QThread, Signal

from loan_manager.application.agent.llm_port import LLMConfigError
from loan_manager.application.agent.retry import CancelToken
from loan_manager.application.agent.trace import TraceEvent, TraceKind, TurnOutcome
from loan_manager.application.use_cases.agent.run_agent_turn import MAX_STEPS
from loan_manager.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class WorkerResult:
    """`text` is the answer on ANSWERED and empty otherwise: the UI renders
    fixed copy for every failure and never this field."""

    outcome: TurnOutcome
    text: str
    conversation: Any
    run_turn: Any
    proposals: int = 0
    not_configured: bool = False


class AgentWorker(QThread):
    event = Signal(object)  # TraceEvent
    done = Signal(object)  # WorkerResult
    waiting = Signal(object)  # RetryNotice: why the turn is waiting (slice 1)

    def __init__(self, container, conversation, run_turn, user_text: str, parent=None) -> None:
        super().__init__(parent)
        self._container = container
        self._conversation = conversation
        self._run_turn = run_turn
        self._user_text = user_text
        self._proposals = 0
        self._last_step = 0
        self._cancel = CancelToken()

    def request_stop(self) -> None:
        """Safe from the UI thread. Honoured before the next model call and
        during any retry wait; a request already in flight still finishes or
        times out first."""
        self._cancel.cancel()

    def _emit_event(self, event: TraceEvent) -> None:
        self._last_step = event.step
        if event.kind is TraceKind.PROPOSAL:
            self._proposals += 1
        self.event.emit(event)

    def run(self) -> None:
        result: WorkerResult | None = None
        try:
            if self._run_turn is None:
                self._run_turn = self._container.get_run_agent_turn()
            if self._conversation is None:
                self._conversation = self._container.get_start_agent_conversation().execute()
            turn = self._run_turn.execute(
                self._conversation,
                self._user_text,
                self._emit_event,
                cancel=self._cancel,
                on_wait=self.waiting.emit,
            )
            text = turn.text if turn.outcome is TurnOutcome.ANSWERED else ""
            result = self._result(turn.outcome, text)
        except LLMConfigError:
            self._emit_final(TurnOutcome.LLM_ERROR)
            result = self._result(TurnOutcome.LLM_ERROR, "", not_configured=True)
        except Exception as exc:
            logger.error("Ask FinHive turn failed: %s", type(exc).__name__)
            self._emit_final(TurnOutcome.INTERNAL_ERROR)
            result = self._result(TurnOutcome.INTERNAL_ERROR, "")
        finally:
            if result is None:  # BaseException: still settle the UI
                result = self._result(TurnOutcome.INTERNAL_ERROR, "")
            self.done.emit(result)

    def _result(
        self, outcome: TurnOutcome, text: str, *, not_configured: bool = False
    ) -> WorkerResult:
        return WorkerResult(
            outcome,
            text,
            self._conversation,
            self._run_turn,
            self._proposals,
            not_configured,
        )

    def _emit_final(self, outcome: TurnOutcome) -> None:
        """A turn that died outside `RunAgentTurn` never emitted its FINAL, or died
        after emitting an ANSWERED one (recorder failure): this one replaces it."""
        try:
            self.event.emit(
                TraceEvent(
                    kind=TraceKind.FINAL,
                    step=self._last_step,
                    max_steps=MAX_STEPS,
                    text="",
                    outcome=outcome,
                )
            )
        except Exception as exc:  # pragma: no cover - emit itself failing
            logger.error("Ask FinHive final event failed: %s", type(exc).__name__)
