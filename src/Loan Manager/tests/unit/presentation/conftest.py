"""Shared fixtures for the KCH-241 Ask FinHive presentation tests.

Offscreen only, recorded fakes only (no live model call). pytest-qt is not a
dependency: `wait_until` pumps the event loop by hand.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
from loan_manager.application.agent.tools.propose_tools import build_propose_registry  # noqa: E402
from loan_manager.application.agent.tools.read_tools import build_read_registry  # noqa: E402
from loan_manager.application.agent.trace import (  # noqa: E402
    TraceEvent,
    TraceKind,
    TurnOutcome,
)
from loan_manager.application.event_bus import EventBus  # noqa: E402
from loan_manager.application.interfaces.clock import FixedClock  # noqa: E402
from loan_manager.application.use_cases.agent.run_agent_turn import (  # noqa: E402
    MAX_STEPS,
    RunAgentTurn,
    TurnResult,
)
from loan_manager.application.use_cases.agent.start_agent_conversation import (  # noqa: E402
    StartAgentConversation,
)
from loan_manager.application.use_cases.loans.build_entity_resolver import (  # noqa: E402
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (  # noqa: E402
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.loans.get_protected_names import (  # noqa: E402
    GetProtectedNames,
)
from loan_manager.application.use_cases.reports.get_reports import (  # noqa: E402
    GetPendingReports,
)
from loan_manager.infrastructure.llm.fake import RecordedFakeLLM  # noqa: E402
from loan_manager.infrastructure.llm.settings import LLMSettings  # noqa: E402
from loan_manager.infrastructure.seed.demo_fixture import FIXTURE_TODAY  # noqa: E402
from loan_manager.presentation.themes.theme_manager import ThemeManager  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tests.unit.application.agent.conftest import demo_loans, uow_factory_for  # noqa: E402

CASSETTE = Path(__file__).resolve().parents[2] / "fixtures" / "llm" / "agent_turn_4step.json"
OVERDUE_QUESTION = "What does Sharma Group owe that is overdue?"
# Distinctive strings: if either ever shows up on screen after a failure, a
# name or an amount leaked through an exception message or a FINAL text.
LEAK_TEXT = "sharma group owes 550000"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    ThemeManager.apply_theme("dark", app)
    return app


@pytest.fixture
def wait_until(qapp):
    def _wait(predicate, timeout_ms: int = 5000) -> None:
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            qapp.processEvents()
            if predicate():
                return
            time.sleep(0.005)
        qapp.processEvents()
        assert predicate(), f"condition not met within {timeout_ms} ms"

    return _wait


def llm_settings() -> LLMSettings:
    return LLMSettings(
        base_url="https://openrouter.ai/api/v1", model="recorded/agent-turn",
        api_key_env="OPENROUTER_API_KEY", temperature=0.1, max_steps=6, timeout_s=60,
    )


class ThreadRecordingLLM:
    """Wraps a `RecordedFakeLLM`; records which thread `complete` ran on and
    can hold the turn open on a gate."""

    def __init__(self, inner: RecordedFakeLLM, gate: threading.Event | None = None) -> None:
        self._inner = inner
        self.gate = gate
        self.threads: list[int] = []

    def complete(self, messages, tools=None):
        self.threads.append(threading.get_ident())
        if self.gate is not None:
            assert self.gate.wait(10), "gate never released"
        return self._inner.complete(messages, tools)


class RaisingRecorder:
    def record(self, record) -> None:
        raise RuntimeError(LEAK_TEXT)


@dataclass
class FakeRunTurn:
    """Stands in for `RunAgentTurn`: emits scripted events, returns a scripted
    result. `gate` holds the turn open; `raises` escapes the use case."""

    events: list[TraceEvent] = field(default_factory=list)
    result: TurnResult | None = None
    gate: threading.Event | None = None
    raises: Exception | None = None
    calls: int = 0
    threads: list[int] = field(default_factory=list)
    # Slice 1: `notices` are sent to `on_wait` first; `stop_aware` holds the
    # turn open until the worker's cancel token is set (the Stop button).
    notices: list = field(default_factory=list)
    stop_aware: bool = False
    kwargs: dict = field(default_factory=dict)

    def execute(self, conversation, user_text, emit=lambda e: None, **kwargs) -> TurnResult:
        self.calls += 1
        self.kwargs = kwargs
        self.threads.append(threading.get_ident())
        for notice in self.notices:
            kwargs["on_wait"](notice)
        if self.stop_aware:
            deadline = time.monotonic() + 10
            while not kwargs["cancel"].cancelled and time.monotonic() < deadline:
                time.sleep(0.01)
            assert kwargs["cancel"].cancelled, "Stop was never requested"
        if self.gate is not None:
            assert self.gate.wait(10), "gate never released"
        for event in self.events:
            emit(event)
        if self.raises is not None:
            raise self.raises
        assert self.result is not None
        return self.result


def failing_turn(outcome: TurnOutcome, *, leak: str = LEAK_TEXT) -> FakeRunTurn:
    """A turn that failed with `outcome` and whose every text field is `leak`."""
    return FakeRunTurn(
        events=[
            TraceEvent(TraceKind.FINAL, 2, MAX_STEPS, text=leak, outcome=outcome),
        ],
        result=TurnResult(outcome, leak, "turn-x", 2),
    )


class StubContainer:
    """The slice of `Container` the tab and worker use, over the in-memory
    demo ledger. `run_turn` overrides `get_run_agent_turn`."""

    def __init__(self, *, llm=None, run_turn=None, recorder=None, config_error=None,
                 start_error=None) -> None:
        self.loans = demo_loans()
        self.reports: list = []
        self._uow_factory = uow_factory_for(self.loans, self.reports)
        self.clock = FixedClock(FIXTURE_TODAY)
        self.event_bus = EventBus()
        self._llm = llm
        self._run_turn = run_turn
        self._recorder = recorder
        self._config_error = config_error
        self._start_error = start_error
        self.run_turn_builds = 0
        self.conversations_started = 0

    def get_uow(self):
        return self._uow_factory()

    def get_run_agent_turn(self):
        if self._config_error is not None:
            raise self._config_error
        self.run_turn_builds += 1
        if self._run_turn is not None:
            return self._run_turn
        uf, clock = self._uow_factory, self.clock
        kwargs = {"recorder": self._recorder} if self._recorder is not None else {}
        return RunAgentTurn(
            self._llm or ThreadRecordingLLM(RecordedFakeLLM.from_json(CASSETTE, llm_settings())),
            build_read_registry(uf, clock),
            lambda **kw: build_propose_registry(uf, clock, self.event_bus, **kw),
            **kwargs,
        )

    def get_start_agent_conversation(self):
        self.conversations_started += 1
        if self._start_error is not None:
            raise self._start_error
        if self._run_turn is not None:  # scripted turn: the conversation is opaque
            return SimpleNamespace(execute=lambda: SimpleNamespace(closed=False))
        ga = GetAutocompleteValues(self._uow_factory)
        return StartAgentConversation(
            BuildEntityResolver(ga),
            GetProtectedNames(ga, GetPendingReports(self._uow_factory)),
            new_id=lambda: f"conv-{self.conversations_started}",
        )


def cassette_llm(gate: threading.Event | None = None) -> ThreadRecordingLLM:
    return ThreadRecordingLLM(RecordedFakeLLM.from_json(CASSETTE, llm_settings()), gate)


def all_text(tab: Any) -> str:
    """Every string the Ask tab renders: labels, both models (Display and
    ToolTip), for leak assertions."""
    from PySide6.QtCore import QModelIndex, Qt
    from PySide6.QtWidgets import QLabel

    parts = [label.text() for label in tab.findChildren(QLabel)]

    def walk(model, parent=None, *, tree=False):
        parent = QModelIndex() if parent is None else parent
        for row in range(model.rowCount(parent)):
            for col in range(model.columnCount(parent)):
                index = model.index(row, col, parent)
                for role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
                    value = model.data(index, role)
                    if value:
                        parts.append(str(value))
            if tree:
                walk(model, model.index(row, 0, parent), tree=True)

    walk(tab._trace_model, tree=True)
    walk(tab._proxy)
    return "\n".join(parts)
