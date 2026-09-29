"""KCH-241: the Ask FinHive tab inside the real MainWindow, over a real WAL
SQLite file seeded through the encrypting repository (the KCH-231 seeder).

Only the model is faked: the cassette answers where OpenRouter would. Set
KCH241_SCREENSHOT_DIR to write the review screenshots.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from loan_manager.application.agent.trace import TurnOutcome
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.container import Container
from loan_manager.infrastructure.database.session import DatabaseSession
from loan_manager.infrastructure.llm.fake import RecordedFakeLLM
from loan_manager.infrastructure.seed import demo_seed
from loan_manager.infrastructure.seed.demo_fixture import FIXTURE_TODAY
from loan_manager.presentation.main_window import MainWindow
from loan_manager.presentation.tabs.ask_finhive_tab import OUTCOME_TEXT
from loan_manager.presentation.themes.theme_manager import ThemeManager
from sqlalchemy.orm import sessionmaker

from .conftest import CASSETTE, OVERDUE_QUESTION, llm_settings


@pytest.fixture
def seeded_container(tmp_path: Path, monkeypatch):
    saved = (DatabaseSession._engine, DatabaseSession._SessionLocal)
    DatabaseSession._engine = DatabaseSession._SessionLocal = None
    db_path = tmp_path / "demo.db"  # never data/loans.db
    DatabaseSession.initialize(db_path)
    demo_seed.seed(
        sessionmaker(bind=DatabaseSession.get_engine(), expire_on_commit=False),
        today=FIXTURE_TODAY,
    )
    container = Container()
    container.clock = FixedClock(FIXTURE_TODAY)
    real = container.get_run_agent_turn
    llm = RecordedFakeLLM.from_json(CASSETTE, llm_settings())
    monkeypatch.setattr(container, "get_run_agent_turn", lambda: real(llm=llm))
    yield container, db_path
    DatabaseSession.get_engine().dispose()
    DatabaseSession._engine, DatabaseSession._SessionLocal = saved


def _shot(widget, name: str) -> None:
    out = os.environ.get("KCH241_SCREENSHOT_DIR")
    if out:
        Path(out).mkdir(parents=True, exist_ok=True)
        assert widget.grab().save(str(Path(out) / name)), name


def _window(container, qapp) -> MainWindow:
    window = MainWindow(container, ThemeManager)
    window.resize(1400, 820)
    window.show()
    window._tabs.setCurrentWidget(window._ask_tab)
    qapp.processEvents()
    return window


def test_main_window_has_ask_finhive_as_the_sixth_tab_before_settings(
    qapp, seeded_container
) -> None:
    container, _ = seeded_container
    window = _window(container, qapp)

    titles = [window._tabs.tabText(i) for i in range(window._tabs.count())]
    assert titles == [
        "Entry", "View", "Calculator", "Pending Approval", "Ask FinHive", "Settings",
    ]
    window.close()


def test_one_ask_round_trips_on_the_wal_file_database(
    qapp, wait_until, seeded_container
) -> None:
    container, db_path = seeded_container
    window = _window(container, qapp)
    tab = window._ask_tab
    _shot(window, "01-idle.png")

    tab._input.setText(OVERDUE_QUESTION)
    tab._ask_btn.click()
    wait_until(lambda: not tab._busy and tab._worker is None, timeout_ms=10000)

    assert "overdue" in tab._answer.text()
    assert tab._proxy.rowCount() == 2
    assert tab._trace_model.rowCount() == 4
    assert db_path.exists()
    _shot(window, "02-answered-trace.png")
    window.close()


def test_internal_error_screenshot_shows_fixed_text_only(
    qapp, wait_until, seeded_container, monkeypatch
) -> None:
    container, _ = seeded_container

    def boom():
        raise RuntimeError("sharma group owes 550000")

    monkeypatch.setattr(container, "get_start_agent_conversation", boom)
    window = _window(container, qapp)
    tab = window._ask_tab

    tab._input.setText(OVERDUE_QUESTION)
    tab._ask_btn.click()
    wait_until(lambda: not tab._busy and tab._worker is None, timeout_ms=10000)

    assert tab._answer.text() == OUTCOME_TEXT[TurnOutcome.INTERNAL_ERROR]
    _shot(window, "03-internal-error.png")
    window.close()
