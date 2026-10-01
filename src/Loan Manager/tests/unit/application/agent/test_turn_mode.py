"""KCH-246 T7: the keyword gate (owner decision D1). Pure function, typed text only."""
from __future__ import annotations

import pytest
from loan_manager.application.agent.tool_registry import ToolMode
from loan_manager.application.agent.turn_mode import turn_mode


@pytest.mark.parametrize(
    "text",
    [
        "Create a loan for Rohan Kapadia, 150000",
        "Extend overdue loans in sharma group",
        "EXTEND the loan please",
        "please add a new loan",
        "new loan for meera iyer",
        "Update the amount to 5000",
        "change the rate",
        "Rename this borrower",
        "correct the due date",
        "edit loan 2026_01_001",
        "modify the group",
        "renew it",
        # a QUESTION that contains a verb still unlocks PROPOSE: accepted false
        # positive (the result is only a draft a human approves).
        "Can I extend loan 2026_01_001?",
        "extend, then tell me",
    ],
)
def test_a_change_verb_in_the_typed_text_unlocks_propose(text: str) -> None:
    assert turn_mode(text) is ToolMode.PROPOSE


@pytest.mark.parametrize(
    "text",
    [
        "Which loans are overdue?",
        "What does Sharma Group owe that is overdue?",
        "",
        "   ",
        # whole-word only: inflections and look-alikes do not match.
        "When is the renewal date?",
        "Which loans were extended last month?",
        "Show the address book",
        "What is the newest loan?",
        "Who created loan 2026_01_001?",
        "updated yesterday?",
        "nothing new, loans only",
        "उधार कितना है",
    ],
)
def test_no_change_verb_stays_read(text: str) -> None:
    assert turn_mode(text) is ToolMode.READ
