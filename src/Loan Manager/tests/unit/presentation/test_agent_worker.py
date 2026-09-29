"""KCH-241 AgentWorker: off-thread turn, one `done`, fixed failure handling."""
from __future__ import annotations

import logging
import threading

import pytest
from loan_manager.application.agent.llm_port import LLMConfigError
from loan_manager.application.agent.trace import TraceKind, TurnOutcome
from loan_manager.presentation.workers.agent_worker import AgentWorker, WorkerResult
from PySide6.QtCore import QObject, Slot

from .conftest import (
    LEAK_TEXT,
    OVERDUE_QUESTION,
    FakeRunTurn,
    RaisingRecorder,
    StubContainer,
    cassette_llm,
    failing_turn,
)


class Collector(QObject):
    """A QObject receiver, so delivery is queued onto the thread it lives in
    (a bare lambda would run on the emitting thread)."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list = []
        self.results: list[WorkerResult] = []
        self.threads: list[int] = []

    @Slot(object)
    def on_event(self, event) -> None:
        self.threads.append(threading.get_ident())
        self.events.append(event)

    @Slot(object)
    def on_done(self, result) -> None:
        self.threads.append(threading.get_ident())
        self.results.append(result)


def _run(container, wait_until, run_turn=None):
    collector = Collector()
    worker = AgentWorker(container, None, run_turn, OVERDUE_QUESTION)
    worker.event.connect(collector.on_event)
    worker.done.connect(collector.on_done)
    worker.start()
    wait_until(lambda: bool(collector.results))
    worker.wait(5000)
    return worker, collector


def test_worker_streams_events_then_done_from_a_worker_thread(qapp, wait_until) -> None:
    llm = cassette_llm()
    container = StubContainer(llm=llm)

    _, collector = _run(container, wait_until)

    main = threading.get_ident()
    assert llm.threads and all(t != main for t in llm.threads), "model call ran on the UI thread"
    assert all(t == main for t in collector.threads), "signals must be delivered on the UI thread"
    kinds = [e.kind for e in collector.events]
    assert kinds.count(TraceKind.ACTION) == 3 and kinds[-1] is TraceKind.FINAL
    assert len(collector.results) == 1
    result = collector.results[0]
    assert result.outcome is TurnOutcome.ANSWERED
    assert "overdue" in result.text
    assert result.conversation is not None and result.run_turn is not None


@pytest.mark.parametrize(
    "case",
    ["use_case_raises", "recorder_raises", "conversation_start_raises"],
)
def test_exception_escaping_the_turn_gives_internal_error_and_logs_type_only(
    qapp, wait_until, caplog, case
) -> None:
    if case == "use_case_raises":
        container = StubContainer(run_turn=FakeRunTurn(raises=RuntimeError(LEAK_TEXT)))
    elif case == "recorder_raises":
        container = StubContainer(llm=cassette_llm(), recorder=RaisingRecorder())
    else:
        container = StubContainer(start_error=RuntimeError(LEAK_TEXT))

    with caplog.at_level(logging.DEBUG):
        _, collector = _run(container, wait_until)

    assert len(collector.results) == 1
    result = collector.results[0]
    assert result.outcome is TurnOutcome.INTERNAL_ERROR
    assert result.text == ""  # fixed copy is the tab's job; nothing to leak
    finals = [e for e in collector.events if e.kind is TraceKind.FINAL]
    # recorder failure: the use case already emitted ANSWERED, then ours follows
    assert len(finals) == (2 if case == "recorder_raises" else 1)
    assert finals[-1].outcome is TurnOutcome.INTERNAL_ERROR
    assert all(f.text != LEAK_TEXT for f in finals)
    logged = caplog.text
    assert "RuntimeError" in logged
    assert "sharma" not in logged.lower() and "550000" not in logged


def test_missing_api_key_is_reported_as_not_configured_without_the_message(
    qapp, wait_until, caplog
) -> None:
    container = StubContainer(config_error=LLMConfigError(f"OPENROUTER_API_KEY {LEAK_TEXT}"))

    with caplog.at_level(logging.DEBUG):
        _, collector = _run(container, wait_until)

    result = collector.results[0]
    assert result.outcome is TurnOutcome.LLM_ERROR
    assert result.not_configured is True
    assert result.text == ""
    assert LEAK_TEXT not in caplog.text


@pytest.mark.parametrize(
    "outcome",
    [o for o in TurnOutcome if o is not TurnOutcome.ANSWERED],
)
def test_worker_blanks_the_text_of_every_failed_turn(qapp, wait_until, outcome) -> None:
    """Layer 1 of the fixed-text defence, independent of the tab: whatever a
    failed `TurnResult` carries, `WorkerResult.text` is empty."""
    container = StubContainer(run_turn=failing_turn(outcome, leak="LEAK sharma 550000"))

    _, collector = _run(container, wait_until)

    result = collector.results[0]
    assert result.outcome is outcome
    assert result.text == ""
    assert "LEAK" not in repr(result.text)


# Direct `run()` calls: coverage does not trace a QThread's body, so these run
# the same code on the calling thread (signals connect directly).

def _run_direct(container, run_turn=None):
    collector = Collector()
    worker = AgentWorker(container, None, run_turn, OVERDUE_QUESTION)
    worker.event.connect(collector.on_event)
    worker.done.connect(collector.on_done)
    worker.run()
    return collector


def test_direct_run_answered(qapp) -> None:
    c = _run_direct(StubContainer(llm=cassette_llm()))
    assert c.results[0].outcome is TurnOutcome.ANSWERED and c.results[0].text


def test_direct_run_use_case_raises(qapp) -> None:
    c = _run_direct(StubContainer(run_turn=FakeRunTurn(raises=RuntimeError(LEAK_TEXT))))
    assert c.results[0].outcome is TurnOutcome.INTERNAL_ERROR
    assert c.events[-1].outcome is TurnOutcome.INTERNAL_ERROR


def test_direct_run_recorder_raises_ends_on_internal_error(qapp) -> None:
    c = _run_direct(StubContainer(llm=cassette_llm(), recorder=RaisingRecorder()))
    finals = [e for e in c.events if e.kind is TraceKind.FINAL]
    assert [f.outcome for f in finals] == [TurnOutcome.ANSWERED, TurnOutcome.INTERNAL_ERROR]


def test_direct_run_conversation_start_raises(qapp) -> None:
    c = _run_direct(StubContainer(start_error=RuntimeError(LEAK_TEXT)))
    assert c.results[0].outcome is TurnOutcome.INTERNAL_ERROR


def test_direct_run_config_error(qapp) -> None:
    c = _run_direct(StubContainer(config_error=LLMConfigError("x")))
    assert c.results[0].not_configured is True


def test_direct_run_counts_proposals(qapp) -> None:
    from loan_manager.application.agent.trace import TraceEvent
    from loan_manager.application.use_cases.agent.run_agent_turn import MAX_STEPS, TurnResult

    turn = FakeRunTurn(
        events=[TraceEvent(TraceKind.PROPOSAL, 1, MAX_STEPS, tool="create_loan", payload={})],
        result=TurnResult(TurnOutcome.ANSWERED, "ok", "t", 1),
    )
    c = _run_direct(StubContainer(run_turn=turn))
    assert c.results[0].proposals == 1
