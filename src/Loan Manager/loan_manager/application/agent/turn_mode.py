"""KCH-246: the per-turn tool-mode latch (owner decision D1, keyword gate).

PROPOSE tools are offered to the model only when the user's OWN typed text
asks for a change. The decision reads `user_text` and nothing else (never a
tool result, a stored name or a model message), so data the model reads
cannot unlock a write; it fails closed to READ.

Matching is whole-word on the lower-cased raw text: "renewal" and "extended"
do not match "renew" / "extend". A question that merely contains a verb
("can I extend loan X?") does unlock PROPOSE; that false positive is
accepted, because a proposal is only a draft a human approves.
[REVIEW REQUIRED] English verbs only; Hinglish verbs are debt (KCH-249/253).
"""
from __future__ import annotations

import re

from loan_manager.application.agent.tool_registry import ToolMode

CHANGE_VERBS: tuple[str, ...] = (
    "create",
    "add",
    "new loan",
    "extend",
    "renew",
    "update",
    "change",
    "rename",
    "correct",
    "edit",
    "modify",
)

_CHANGE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(v) for v in CHANGE_VERBS) + r")\b"
)


def turn_mode(user_text: str) -> ToolMode:
    """PROPOSE when the typed text names a change verb, else READ."""
    return ToolMode.PROPOSE if _CHANGE_RE.search(user_text.lower()) else ToolMode.READ
