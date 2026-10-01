"""Uniform tool-observation shape for every READ and PROPOSE tool (KCH-237,
extended by KCH-243 for the PROPOSE error codes below).

Every tool returns plain JSON: `ok(**payload)` for success,
`error(code, message, next_action, **details)` for failure. Both walk their
payload recursively and turn any `Decimal` into `str` (`_jsonable`), so a
handler that forgets to `str()` a Decimal itself does not leak a
non-JSON-serialisable value to the LLM boundary (`json.dumps` would raise on
a raw Decimal).

`error()` always carries `next_action` — a plain "no" is a dead end for the
agent loop; every failure tells the model what to try next (e.g. "call
resolve_entity with the user's text, then retry").
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    UNRESOLVED_ENTITY = "UNRESOLVED_ENTITY"
    UNSUPPORTED_STATUS = "UNSUPPORTED_STATUS"
    REF_ID_NOT_FOUND = "REF_ID_NOT_FOUND"
    UNKNOWN_TOKEN = "UNKNOWN_TOKEN"  # noqa: S105 - an error code, not a secret
    # KCH-243, PROPOSE tools only, below.
    # A group value resolved to a candidate, but not exactly (ambiguous, or
    # only a fuzzy match) -- the caller must ask the user before acting.
    CONFIRM_REQUIRED = "CONFIRM_REQUIRED"
    # extend_loan on a loan with no due_date, called without new_due_date.
    UNDATED_LOAN = "UNDATED_LOAN"
    # extend_loan's new_due_date is not after today, or was given for a
    # loan that already has a due_date (it must be omitted there).
    NEW_DUE_DATE_INVALID = "NEW_DUE_DATE_INVALID"
    # update_loan's given borrower_group/depositor_group resolves to a real
    # group, but not the loan's own -- a membership check failure, never an
    # instruction to move the loan.
    GROUP_MISMATCH = "GROUP_MISMATCH"
    # The ref_id is already named by another PENDING report.
    ALREADY_PENDING = "ALREADY_PENDING"
    # Nothing would change: every candidate record was filtered out (all
    # undated, all already pending) or every proposed field already matches
    # the loan's current value. No report is generated.
    NOTHING_TO_PROPOSE = "NOTHING_TO_PROPOSE"
    # KCH-239: the model's tool call failed argument validation (bad JSON,
    # unknown tool, a field rule). The message is scrubbed to field names and
    # rule names -- never the value the model sent.
    INVALID_ARGS = "INVALID_ARGS"
    # KCH-246: a PROPOSE tool was called on a turn whose typed text named no
    # change verb (application/agent/turn_mode.py). Nothing was persisted.
    CHANGE_NOT_REQUESTED = "CHANGE_NOT_REQUESTED"


def _jsonable(value: Any) -> Any:
    """`value` with every `Decimal` replaced by `str(value)`, recursively
    through mappings, lists and tuples. Everything else passes through
    unchanged (str, int, bool, None already serialise fine)."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def ok(**payload: Any) -> dict[str, Any]:
    """A successful tool observation: `{"ok": True, **payload}`."""
    return {"ok": True, **_jsonable(payload)}


def error(code: ErrorCode, message: str, next_action: str, **details: Any) -> dict[str, Any]:
    """A failed tool observation: `{"ok": False, "error": {"code", "message",
    "next_action", **details}}`. `next_action` is required, never optional —
    see module docstring."""
    return {
        "ok": False,
        "error": {
            "code": code.value,
            "message": message,
            "next_action": next_action,
            **_jsonable(details),
        },
    }
