"""KCH-241 TraceModel: grouping, FINAL never shows event.text, proposal pointer,
theme colours."""
from __future__ import annotations

from loan_manager.application.agent.trace import TraceEvent, TraceKind, TurnOutcome
from loan_manager.presentation.themes.theme_manager import ThemeManager
from loan_manager.presentation.widgets.trace_model import PROPOSAL_TEXT, TraceModel
from PySide6.QtCore import QModelIndex, Qt

from .conftest import LEAK_TEXT

DISPLAY = Qt.ItemDataRole.DisplayRole
TOOLTIP = Qt.ItemDataRole.ToolTipRole
FOREGROUND = Qt.ItemDataRole.ForegroundRole


def _ev(kind, step, **kw) -> TraceEvent:
    return TraceEvent(kind, step, 6, **kw)


def _model(qapp) -> TraceModel:
    return TraceModel(ThemeManager)


def _texts(model: TraceModel, parent=None, column=0) -> list[str]:
    parent = QModelIndex() if parent is None else parent
    rows = range(model.rowCount(parent))
    return [model.data(model.index(r, column, parent), DISPLAY) for r in rows]


def test_events_group_under_their_step_and_final_is_a_top_level_answer_row(qapp) -> None:
    model = _model(qapp)
    model.append(_ev(TraceKind.ACTION, 1, tool="get_current_context", text="{}"))
    model.append(_ev(TraceKind.OBSERVATION, 1, tool="get_current_context", payload={"ok": True}))
    model.append(_ev(TraceKind.THOUGHT, 2, text="check the group"))
    model.append(_ev(TraceKind.FINAL, 2, text="x", outcome=TurnOutcome.ANSWERED))

    assert _texts(model) == ["Step 1 / 6", "Step 2 / 6", "Answer"]
    step1 = model.index(0, 0)
    assert _texts(model, step1) == ["Action", "Observation"]
    assert _texts(model, model.index(1, 0)) == ["Thought"]
    answer = model.index(2, 0)
    assert model.rowCount(answer) == 0
    assert model.parent(answer) == QModelIndex()


def test_final_row_never_displays_event_text(qapp) -> None:
    model = _model(qapp)
    model.append(_ev(TraceKind.FINAL, 2, text=LEAK_TEXT, outcome=TurnOutcome.INTERNAL_ERROR))

    for column in range(3):
        index = model.index(0, column)
        for role in (DISPLAY, TOOLTIP):
            assert LEAK_TEXT not in str(model.data(index, role) or "")
            assert "550000" not in str(model.data(index, role) or "")
    assert model.data(model.index(0, 2), DISPLAY) == "Stopped: internal error"


def test_proposal_row_points_to_pending_approval_and_is_counted(qapp) -> None:
    model = _model(qapp)
    model.append(_ev(TraceKind.PROPOSAL, 1, tool="create_loan",
                     payload={"ok": True, "draft": {"amount": "AMOUNT_1"}}))

    step = model.index(0, 0)
    detail = model.data(model.index(0, 2, step), DISPLAY)
    assert detail == PROPOSAL_TEXT
    assert "Pending Approval" in detail
    assert "AMOUNT_1" not in detail
    assert model.proposal_count() == 1


def test_only_the_last_successful_query_loans_supplies_ref_ids(qapp) -> None:
    model = _model(qapp)
    model.append(_ev(TraceKind.OBSERVATION, 1, tool="query_loans",
                     payload={"ok": True, "ref_ids": ["A1"]}))
    model.append(_ev(TraceKind.OBSERVATION, 2, tool="query_loans",
                     payload={"ok": False, "ref_ids": ["X"],
                             "error": {"code": "INVALID_ARGS"}}))
    model.append(_ev(TraceKind.OBSERVATION, 2, tool="get_portfolio_summary",
                     payload={"ok": True, "ref_ids": ["Z9"]}))
    assert model.last_ref_ids() == ["A1"]
    model.append(_ev(TraceKind.OBSERVATION, 3, tool="query_loans",
                     payload={"ok": True, "ref_ids": ["B2", "B3"]}))
    assert model.last_ref_ids() == ["B2", "B3"]
    model.clear()
    assert model.last_ref_ids() == [] and model.proposal_count() == 0


def test_long_observation_is_truncated_in_display_but_whole_in_tooltip(qapp) -> None:
    model = _model(qapp)
    model.append(_ev(TraceKind.OBSERVATION, 1, tool="query_loans",
                     payload={"ok": True, "ref_ids": [f"2026_01_{i:03d}" for i in range(60)]}))
    detail = model.index(0, 2, model.index(0, 0))
    assert len(model.data(detail, DISPLAY)) <= 200
    assert "2026_01_059" in model.data(detail, TOOLTIP)


def test_foreground_comes_from_theme_config_and_absent_key_gives_none(qapp, monkeypatch) -> None:
    monkeypatch.setattr(
        ThemeManager, "_current_config",
        {"trace_colours": {"action": "#123456", "error": "#654321"}},
    )
    model = _model(qapp)
    model.append(_ev(TraceKind.ACTION, 1, tool="t", text="{}"))
    model.append(_ev(TraceKind.THOUGHT, 1, text="hm"))
    model.append(_ev(TraceKind.FINAL, 1, outcome=TurnOutcome.LLM_ERROR))
    step = model.index(0, 0)

    action = model.data(model.index(0, 0, step), FOREGROUND)
    assert action.color().name() == "#123456"
    assert model.data(model.index(1, 0, step), FOREGROUND) is None  # no "thought" key
    assert model.data(model.index(1, 0), FOREGROUND).color().name() == "#654321"
    assert ThemeManager.get_trace_colour("thought") is None
    assert ThemeManager.get_trace_colour("action").name() == "#123456"


def test_both_shipped_themes_define_every_trace_colour(qapp) -> None:
    for name in ("dark", "light"):
        ThemeManager.apply_theme(name, qapp)
        for key in ("thought", "action", "observation", "proposal", "final", "error"):
            assert ThemeManager.get_trace_colour(key) is not None, (name, key)
    ThemeManager.apply_theme("dark", qapp)


def test_a_later_final_replaces_the_earlier_answer_row(qapp) -> None:
    """Recorder failure after an ANSWERED FINAL: the trace must end on the failure."""
    model = _model(qapp)
    model.append(_ev(TraceKind.ACTION, 1, tool="t", text="{}"))
    model.append(_ev(TraceKind.FINAL, 1, text="x", outcome=TurnOutcome.ANSWERED))
    model.append(_ev(TraceKind.FINAL, 1, outcome=TurnOutcome.INTERNAL_ERROR))

    assert _texts(model) == ["Step 1 / 6", "Answer"]
    assert model.data(model.index(1, 2), DISPLAY) == "Stopped: internal error"


def test_prompt_too_long_final_row_has_its_own_label(qapp) -> None:
    """KCH-246: not the generic "Stopped" fallback."""
    model = _model(qapp)
    model.append(_ev(TraceKind.FINAL, 0, outcome=TurnOutcome.PROMPT_TOO_LONG))

    assert model.data(model.index(0, 2), DISPLAY) == "Stopped: question too long"


def test_every_outcome_has_its_own_trace_label() -> None:
    """Slice 1 added outcomes; the 'Stopped' fallback must not hide them."""
    from loan_manager.application.agent.trace import TurnOutcome
    from loan_manager.presentation.widgets.trace_model import OUTCOME_LABEL

    assert set(OUTCOME_LABEL) == set(TurnOutcome)
