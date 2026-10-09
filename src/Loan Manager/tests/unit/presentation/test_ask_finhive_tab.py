"""KCH-241 AskFinHiveTab smoke tests (offscreen, recorded fake only)."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest
from loan_manager.application.agent.llm_port import LLMConfigError
from loan_manager.application.agent.trace import TraceEvent, TraceKind, TurnOutcome
from loan_manager.application.use_cases.agent.run_agent_turn import MAX_STEPS, TurnResult
from loan_manager.presentation.tabs import ask_finhive_tab as tab_module
from loan_manager.presentation.tabs.ask_finhive_tab import (
    LOAN_LOOKUP_FAILED_TEXT,
    NOT_CONFIGURED_TEXT,
    NOTE_DIGIT_GLUED,
    NOTE_NPI,
    OUTCOME_TEXT,
    TRACE_LEGEND,
    AskFinHiveTab,
)
from loan_manager.presentation.themes.theme_manager import ThemeManager
from loan_manager.presentation.widgets.trace_model import PROPOSAL_TEXT
from loan_manager.presentation.workers.agent_worker import WorkerResult
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel

from .conftest import (
    LEAK_TEXT,
    OVERDUE_QUESTION,
    FakeRunTurn,
    RaisingRecorder,
    StubContainer,
    all_text,
    cassette_llm,
    failing_turn,
)


def _tab(container) -> AskFinHiveTab:
    tab = AskFinHiveTab(container, ThemeManager)
    tab.resize(1100, 700)
    tab.show()
    return tab


def _ask(tab, wait_until, text: str = OVERDUE_QUESTION) -> None:
    tab._input.setText(text)
    tab._ask_btn.click()
    wait_until(lambda: not tab._busy and tab._worker is None)


def test_answered_turn_streams_trace_hydrates_table_and_ends_busy(qapp, wait_until) -> None:
    llm = cassette_llm()
    container = StubContainer(llm=llm)
    tab = _tab(container)

    _ask(tab, wait_until)

    assert not tab._busy and tab._ask_btn.isEnabled() and tab._input.isEnabled()
    assert "overdue" in tab._answer.text()
    model = tab._trace_model
    assert [model.data(model.index(r, 0)) for r in range(model.rowCount())] == [
        "Step 1 / 6", "Step 2 / 6", "Step 3 / 6", "Answer",
    ]
    # table: exactly the ref_ids query_loans returned, not the whole ledger
    wanted = set(model.last_ref_ids())
    assert len(wanted) == 2 and len(container.loans) > 2
    shown = {tab._proxy.data(tab._proxy.index(r, 1)) for r in range(tab._proxy.rowCount())}
    assert shown == wanted
    assert "Step 4 / 6" in tab._status.text()
    # the trace holds tokens: the borrower group's real name is not in it
    assert "sharma" not in all_text_of_trace(tab).lower()
    assert "G001" in all_text_of_trace(tab)


def all_text_of_trace(tab) -> str:
    from PySide6.QtCore import QModelIndex, Qt

    out: list[str] = []
    model = tab._trace_model

    def walk(parent):
        for r in range(model.rowCount(parent)):
            for c in range(3):
                for role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
                    v = model.data(model.index(r, c, parent), role)
                    if v:
                        out.append(str(v))
            walk(model.index(r, 0, parent))

    walk(QModelIndex())
    return "\n".join(out)


def test_ui_stays_responsive_while_a_turn_is_running(qapp, wait_until) -> None:
    gate = threading.Event()
    tab = _tab(StubContainer(llm=cassette_llm(gate)))
    ticks: list[int] = []

    tab._input.setText(OVERDUE_QUESTION)
    tab._ask_btn.click()
    assert tab._busy and not tab._ask_btn.isEnabled() and not tab._new_btn.isEnabled()
    QTimer.singleShot(30, lambda: ticks.append(1))
    wait_until(lambda: bool(ticks), timeout_ms=2000)  # fires only if the loop is free
    assert tab._busy, "the gated turn must still be running"

    gate.set()
    wait_until(lambda: not tab._busy)
    assert "overdue" in tab._answer.text()


def test_use_case_exception_ends_busy_with_fixed_text_and_no_leak(qapp, wait_until) -> None:
    for container in (
        StubContainer(run_turn=FakeRunTurn(raises=RuntimeError(LEAK_TEXT))),
        StubContainer(llm=cassette_llm(), recorder=RaisingRecorder()),
        StubContainer(start_error=RuntimeError(LEAK_TEXT)),
    ):
        tab = _tab(container)
        _ask(tab, wait_until)

        assert not tab._busy and tab._ask_btn.isEnabled()
        assert tab._answer.text() == OUTCOME_TEXT[TurnOutcome.INTERNAL_ERROR]
        text = all_text(tab).lower()
        assert "sharma group" not in text and "550000" not in text, text


@pytest.mark.parametrize(
    "outcome",
    [TurnOutcome.INTERNAL_ERROR, TurnOutcome.LLM_ERROR, TurnOutcome.BLOCKED_PLAINTEXT,
     TurnOutcome.BUDGET_EXHAUSTED, TurnOutcome.PROMPT_TOO_LONG],
)
def test_failed_outcome_renders_fixed_text_and_never_the_turns_own_words(
    qapp, wait_until, outcome
) -> None:
    tab = _tab(StubContainer(run_turn=failing_turn(outcome, leak="LEAK sharma 550000")))

    _ask(tab, wait_until)

    assert tab._answer.text() == OUTCOME_TEXT[outcome]
    assert "LEAK" not in all_text(tab)


def test_prompt_too_long_renders_the_fixed_limit_text(qapp, wait_until) -> None:
    """KCH-246 T9: the tab shows the fixed sentence naming the 2,000 limit."""
    tab = _tab(StubContainer(run_turn=failing_turn(TurnOutcome.PROMPT_TOO_LONG, leak="LEAK")))

    _ask(tab, wait_until)

    assert tab._answer.text() == (
        "That question is too long (limit 2,000 characters). Please shorten it."
    )


def test_missing_key_renders_the_not_configured_text(qapp, wait_until) -> None:
    tab = _tab(StubContainer(config_error=LLMConfigError(f"key {LEAK_TEXT}")))

    _ask(tab, wait_until)

    assert tab._answer.text() == NOT_CONFIGURED_TEXT
    assert LEAK_TEXT not in all_text(tab)
    assert not tab._busy


def test_outcome_text_covers_every_non_answered_outcome() -> None:
    missing = [o for o in TurnOutcome if o is not TurnOutcome.ANSWERED and not OUTCOME_TEXT.get(o)]
    assert missing == []
    assert TurnOutcome.ANSWERED not in OUTCOME_TEXT


def test_both_input_notes_and_the_trace_legend_are_visible_with_required_wording(
    qapp,
) -> None:
    tab = _tab(StubContainer(llm=cassette_llm()))

    notes = {
        lbl.text(): lbl for lbl in tab.findChildren(QLabel) if lbl.objectName() == "askFinhiveNote"
    }
    assert NOTE_NPI in notes and NOTE_DIGIT_GLUED in notes and TRACE_LEGEND in notes
    assert "UPI IDs, e-mail addresses or phone numbers" in NOTE_NPI
    assert "'anil sharma 2026', not 'anilsharma2026'" in NOTE_DIGIT_GLUED
    assert "B001, AMOUNT_1" in TRACE_LEGEND
    for text in (NOTE_NPI, NOTE_DIGIT_GLUED, TRACE_LEGEND):
        assert notes[text].isVisible() and notes[text].wordWrap()
    # "directly under the input": both notes sit above the trace/table splitter
    input_bottom = tab._input.mapTo(tab, tab._input.rect().bottomLeft()).y()
    splitter_top = tab._trace_view.mapTo(tab, tab._trace_view.rect().topLeft()).y()
    for text in (NOTE_NPI, NOTE_DIGIT_GLUED):
        top = notes[text].mapTo(tab, notes[text].rect().topLeft()).y()
        assert input_bottom <= top < splitter_top


def test_proposal_turn_points_to_pending_approval_and_signals_the_window(
    qapp, wait_until
) -> None:
    run_turn = FakeRunTurn(
        events=[
            TraceEvent(TraceKind.PROPOSAL, 1, MAX_STEPS, tool="create_loan",
                       payload={"ok": True}),
            TraceEvent(TraceKind.FINAL, 2, MAX_STEPS, text="Drafted.",
                       outcome=TurnOutcome.ANSWERED),
        ],
        result=TurnResult(TurnOutcome.ANSWERED, "Drafted.", "t", 2),
    )
    tab = _tab(StubContainer(run_turn=run_turn))
    queued: list[int] = []
    tab.proposals_queued.connect(queued.append)

    _ask(tab, wait_until)

    assert queued == [1]
    assert "Pending Approval" in tab._answer.text()
    assert tab._answer.text().startswith("Drafted.")
    assert tab._trace_model.proposal_count() == 1
    assert PROPOSAL_TEXT in all_text(tab)


def test_new_conversation_is_disabled_while_busy_and_resets_the_session(
    qapp, wait_until
) -> None:
    gate = threading.Event()
    run_turn = FakeRunTurn(
        events=[TraceEvent(TraceKind.FINAL, 1, MAX_STEPS, text="ok",
                           outcome=TurnOutcome.ANSWERED)],
        result=TurnResult(TurnOutcome.ANSWERED, "ok", "t", 1),
        gate=gate,
    )
    container = StubContainer(run_turn=run_turn)
    tab = _tab(container)

    tab._input.setText("first")
    tab._ask_btn.click()
    assert tab._busy and not tab._new_btn.isEnabled()
    tab._on_new_conversation()  # a forced call while busy must be ignored too
    assert tab._trace_model.rowCount() == 0 and tab._busy
    gate.set()
    wait_until(lambda: not tab._busy and tab._worker is None)
    assert tab._new_btn.isEnabled() and tab._answer.text() == "ok"
    assert container.conversations_started == 1

    tab._on_new_conversation()
    assert tab._answer.text() == "" and tab._trace_model.rowCount() == 0
    assert tab._proxy.rowCount() == 0

    _ask(tab, wait_until, "second")
    assert container.conversations_started == 2, "a new conversation must start fresh"
    assert container.run_turn_builds == 1, "the RunAgentTurn is cached across conversations"


def test_shutdown_detaches_a_stuck_worker_instead_of_destroying_it(
    qapp, wait_until, monkeypatch
) -> None:
    gate = threading.Event()
    run_turn = FakeRunTurn(
        events=[TraceEvent(TraceKind.FINAL, 1, MAX_STEPS, text="ok",
                           outcome=TurnOutcome.ANSWERED)],
        result=TurnResult(TurnOutcome.ANSWERED, "ok", "t", 1),
        gate=gate,
    )
    tab = _tab(StubContainer(run_turn=run_turn))
    tab._input.setText("q")
    tab._ask_btn.click()
    worker = tab._worker
    monkeypatch.setattr(worker, "wait", lambda ms=0: False)  # "still running after 2 s"

    tab.shutdown()

    assert worker in tab_module._DETACHED_WORKERS and worker.parent() is None
    assert worker.isRunning()
    gate.set()
    wait_until(lambda: worker not in tab_module._DETACHED_WORKERS)


@pytest.mark.parametrize(
    "outcome", [o for o in TurnOutcome if o is not TurnOutcome.ANSWERED]
)
def test_tab_renders_fixed_text_even_if_the_worker_result_carries_text(
    qapp, outcome
) -> None:
    """Layer 2 of the fixed-text defence, independent of the worker."""
    tab = _tab(StubContainer(llm=cassette_llm()))

    tab._on_done(WorkerResult(outcome, "LEAK sharma 550000", None, None))

    assert tab._answer.text() == OUTCOME_TEXT[outcome]
    assert "LEAK" not in all_text(tab)


def test_not_configured_text_names_the_env_var_and_the_restart_not_settings() -> None:
    assert "OPENROUTER_API_KEY" in NOT_CONFIGURED_TEXT
    assert "restart" in NOT_CONFIGURED_TEXT.lower()
    assert "in Settings" not in NOT_CONFIGURED_TEXT


def test_digit_glued_note_examples_match_what_the_real_tokeniser_does() -> None:
    from loan_manager.application.agent import tokeniser as tk

    from tests.unit.application.agent.test_tokeniser_acceptance import _resolver

    def tokenise(text: str) -> str:
        return tk.TokenMap(_resolver("DEMO")).tokenise_prompt(text)

    assert "'anilsharma2026'" in NOTE_DIGIT_GLUED and "'b1ji'" in NOTE_DIGIT_GLUED
    # the "bad" examples really are not recognised ...
    assert "anilsharma" in tokenise("anilsharma2026")
    assert "b1ji" in tokenise("ask b1ji")
    # ... and the advised spellings really are
    assert "sharma" not in tokenise("anil sharma 2026")
    assert "b1" not in tokenise("ask b1 ji")


def test_internal_error_drops_the_conversation_so_the_next_ask_starts_fresh(
    qapp, wait_until
) -> None:
    """A recorder failure leaves an answer in history the user never saw."""
    container = StubContainer(llm=cassette_llm(), recorder=RaisingRecorder())
    tab = _tab(container)

    _ask(tab, wait_until)
    assert tab._answer.text() == OUTCOME_TEXT[TurnOutcome.INTERNAL_ERROR]
    assert tab._conversation is None

    tab._input.setText("again")
    tab._ask_btn.click()
    wait_until(lambda: not tab._busy and tab._worker is None)
    assert container.conversations_started == 2


def test_trace_ends_on_the_failure_after_a_recorder_error(qapp, wait_until) -> None:
    tab = _tab(StubContainer(llm=cassette_llm(), recorder=RaisingRecorder()))

    _ask(tab, wait_until)

    model = tab._trace_model
    last = model.index(model.rowCount() - 1, 2)
    assert model.data(model.index(model.rowCount() - 1, 0)) == "Answer"
    assert model.data(last) == "Stopped: internal error"


def test_hydration_failure_shows_fixed_text_and_logs_type_name_only(
    qapp, wait_until, caplog, monkeypatch
) -> None:
    container = StubContainer(llm=cassette_llm())
    tab = _tab(container)

    class Boom:  # only the tab's own lookup: the agent's tools keep the real use case
        def __init__(self, *args, **kwargs) -> None:
            pass

        def execute(self, filters=None):
            raise ValueError("Amount must be non-negative, got -550000")

    monkeypatch.setattr(tab_module, "GetAllLoans", Boom)
    with caplog.at_level(logging.DEBUG):
        _ask(tab, wait_until)

    assert LOAN_LOOKUP_FAILED_TEXT in tab._answer.text()
    assert tab._answer.text().startswith("sharma group has")
    assert tab._proxy.rowCount() == 0 and not tab._busy
    assert "ValueError" in caplog.text
    assert "550000" not in caplog.text


_EXIT_PROBE = textwrap.dedent(
    """
    import sys, time
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    from loan_manager.application.agent.trace import TurnOutcome
    from loan_manager.application.use_cases.agent.run_agent_turn import TurnResult
    from loan_manager.presentation.tabs import ask_finhive_tab as m
    from loan_manager.presentation.themes.theme_manager import ThemeManager
    from types import SimpleNamespace

    class Slow:
        def execute(self, conv, text, emit=None, **_kw):
            time.sleep(float(sys.argv[1]))
            return TurnResult(TurnOutcome.ANSWERED, "ok", "t", 1)

    container = SimpleNamespace(
        get_run_agent_turn=lambda: Slow(),
        get_start_agent_conversation=lambda: SimpleNamespace(execute=lambda: object()),
    )
    tab = m.AskFinHiveTab(container, ThemeManager)
    tab.show()
    tab._input.setText("q")
    tab._ask_btn.click()

    def close():
        tab.shutdown()
        print("detached", len(m._DETACHED_WORKERS), flush=True)
        app.quit()

    QTimer.singleShot(100, close)
    sys.exit(app.exec())
    """
)


def _run_exit_probe(tmp_path, seconds: int):
    script = tmp_path / "probe.py"
    script.write_text(_EXIT_PROBE)
    root = Path(__file__).resolve().parents[3]
    started = time.monotonic()
    proc = subprocess.run(  # noqa: S603 - fixed argv, our own script
        [sys.executable, str(script), str(seconds)], cwd=root, capture_output=True,
        text=True, timeout=60,
        env={**os.environ, "PYTHONPATH": str(root), "QT_QPA_PLATFORM": "offscreen"},
    )
    return proc, time.monotonic() - started


def test_app_exit_with_a_detached_running_worker_does_not_abort(tmp_path) -> None:
    """Closing the window mid-turn detaches the worker (shutdown waits 2 s); the
    process must then wait for it at exit instead of destroying a running
    QThread (qFatal, exit 134)."""
    proc, _ = _run_exit_probe(tmp_path, 3)

    assert "detached 1" in proc.stdout, proc.stdout + proc.stderr
    assert "Destroyed while thread" not in proc.stderr
    assert proc.returncode == 0, proc.stderr


def test_app_exit_with_a_turn_longer_than_the_wait_ends_cleanly_and_promptly(tmp_path) -> None:
    """A 30 s turn outlives shutdown (2 s) and the quit budget (5 s): the process
    must flush logs and exit 0 in well under 10 s, not abort and not hang."""
    proc, elapsed = _run_exit_probe(tmp_path, 30)

    assert "detached 1" in proc.stdout, proc.stdout + proc.stderr
    assert "Destroyed while thread" not in proc.stderr
    assert proc.returncode == 0, proc.stderr
    assert elapsed < 10, f"exit took {elapsed:.1f}s"


# ── slice 1 (D-18): Stop button and retry status ───────────────────────────


def _held_turn(**kwargs) -> FakeRunTurn:
    outcome = kwargs.pop("outcome", TurnOutcome.ANSWERED)
    return FakeRunTurn(
        events=[TraceEvent(TraceKind.FINAL, 1, MAX_STEPS, text="ok", outcome=outcome)],
        result=TurnResult(outcome, "ok", "t", 1),
        **kwargs,
    )


def test_stop_button_is_enabled_only_while_a_question_runs(qapp, wait_until) -> None:
    gate = threading.Event()
    tab = _tab(StubContainer(run_turn=_held_turn(gate=gate)))
    assert not tab._stop_btn.isEnabled()

    tab._input.setText("q")
    tab._ask_btn.click()
    assert tab._stop_btn.isEnabled()

    gate.set()
    wait_until(lambda: not tab._busy and tab._worker is None)
    assert not tab._stop_btn.isEnabled()


def test_stop_cancels_the_running_turn_and_says_so(qapp, wait_until) -> None:
    run_turn = _held_turn(outcome=TurnOutcome.CANCELLED, stop_aware=True)
    tab = _tab(StubContainer(run_turn=run_turn))
    tab._input.setText("q")
    tab._ask_btn.click()

    tab._stop_btn.click()

    assert "Stopping" in tab._status.text()
    assert not tab._stop_btn.isEnabled()
    wait_until(lambda: not tab._busy and tab._worker is None)
    assert run_turn.kwargs["cancel"].cancelled
    assert tab._answer.text() == OUTCOME_TEXT[TurnOutcome.CANCELLED]


@pytest.mark.parametrize(
    ("kind", "words"),
    [("busy", "warming up"), ("unreachable", "can't reach")],
)
def test_a_retry_notice_says_why_the_tab_is_waiting(qapp, wait_until, kind, words) -> None:
    from loan_manager.application.agent.retry import FailureKind, RetryNotice

    gate = threading.Event()
    notice = RetryNotice(FailureKind(kind), 2, 8.0)
    tab = _tab(StubContainer(run_turn=_held_turn(gate=gate, notices=[notice])))
    tab._input.setText("q")
    tab._ask_btn.click()

    wait_until(lambda: words in tab._status.text().lower())
    assert "attempt 2" in tab._status.text()

    gate.set()
    wait_until(lambda: not tab._busy and tab._worker is None)
    assert words not in tab._status.text().lower()


def test_closing_the_window_asks_a_running_turn_to_stop(qapp, wait_until) -> None:
    run_turn = _held_turn(outcome=TurnOutcome.CANCELLED, stop_aware=True)
    tab = _tab(StubContainer(run_turn=run_turn))
    tab._input.setText("q")
    tab._ask_btn.click()

    tab.shutdown()

    assert run_turn.kwargs["cancel"].cancelled
