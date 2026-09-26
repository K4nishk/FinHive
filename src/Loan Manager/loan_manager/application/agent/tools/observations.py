"""Uniform tool-observation shape for every READ tool (KCH-237).

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
