"""Tool catalogue and dispatch for Ask FinHive (KCH-235).

`TOOL_SPECS` is the single source of truth for every agent tool: its name,
its LLM-facing description, whether it is READ (safe, answers a question) or
PROPOSE (drafts a change for human approval; never writes), and the pydantic
model that validates its arguments (see `tools/args.py`).

`tool_schemas()` renders `TOOL_SPECS` into the OpenAI function-calling shape
used by the OpenRouter client (ARB D-4a), with every optional field's
`anyOf: [X, {"type": "null"}]` flattened to `X` (OpenRouter/OpenAI function
schemas don't need pydantic's Optional shape, and a flat schema is what an
LLM reads best) and every `"title"` stripped (noise a JSON Schema consumer
does not need). `parse_args()` and `ToolRegistry` are the runtime dispatch
surface a later issue (handlers) wires up; this issue ships the schema and
validation only.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

from loan_manager.application.agent.tools.args import (
    CalculateInterestArgs,
    CreateLoan,
    ExtendLoan,
    ExtendOverdueBatch,
    FormatInr,
    GetCurrentContext,
    GetPortfolioSummary,
    QueryLoans,
    ResolveEntity,
    ToolArgs,
    UpdateLoan,
)


class ToolMode(str, Enum):
    READ = "read"
    PROPOSE = "propose"


class UnknownToolError(KeyError):
    """Raised for a tool name absent from TOOL_SPECS (or, from
    ToolRegistry.handler, absent from that registry's handlers)."""


class ToolArgsError(ValueError):
    """Raised for arguments that are not even parseable JSON. A value that
    parses but fails a field's constraints raises pydantic.ValidationError
    instead — that distinction matters to a caller deciding whether to
    re-prompt the model (bad JSON: retry the call shape) or surface the
    validation message (bad value: retry the arguments)."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    mode: ToolMode
    args_model: type[ToolArgs]


TOOL_SPECS: Mapping[str, ToolSpec] = MappingProxyType(
    {
        "get_current_context": ToolSpec(
            name="get_current_context",
            description=(
                "Today's date, quarter and financial-year boundaries. "
                "The model does not know what day it is."
            ),
            mode=ToolMode.READ,
            args_model=GetCurrentContext,
        ),
        "resolve_entity": ToolSpec(
            name="resolve_entity",
            description=(
                "Resolve free text to a canonical borrower or group slug. "
                "Call this BEFORE querying by name."
            ),
            mode=ToolMode.READ,
            args_model=ResolveEntity,
        ),
        "query_loans": ToolSpec(
            name="query_loans",
            description=(
                "Filtered aggregate query over loans. Returns counts and totals, "
                "never rows. Group filters must be values returned by resolve_entity."
            ),
            mode=ToolMode.READ,
            args_model=QueryLoans,
        ),
        "get_portfolio_summary": ToolSpec(
            name="get_portfolio_summary",
            description="Top-N borrowers by outstanding exposure.",
            mode=ToolMode.READ,
            args_model=GetPortfolioSummary,
        ),
        "calculate_interest": ToolSpec(
            name="calculate_interest",
            description="Deterministic interest arithmetic. NEVER compute interest yourself.",
            mode=ToolMode.READ,
            args_model=CalculateInterestArgs,
        ),
        "format_inr": ToolSpec(
            name="format_inr",
            description="Format a rupee amount for display.",
            mode=ToolMode.READ,
            args_model=FormatInr,
        ),
        "extend_loan": ToolSpec(
            name="extend_loan",
            description=(
                "PROPOSE extending a loan's due date. Creates a proposal for "
                "human approval; never writes."
            ),
            mode=ToolMode.PROPOSE,
            args_model=ExtendLoan,
        ),
        "create_loan": ToolSpec(
            name="create_loan",
            description=(
                "PROPOSE a new loan. Creates a proposal for human approval; never writes."
            ),
            mode=ToolMode.PROPOSE,
            args_model=CreateLoan,
        ),
        "update_loan": ToolSpec(
            name="update_loan",
            description=(
                "PROPOSE updating an existing loan's fields. Creates a proposal "
                "for human approval; never writes."
            ),
            mode=ToolMode.PROPOSE,
            args_model=UpdateLoan,
        ),
        "extend_overdue_batch": ToolSpec(
            name="extend_overdue_batch",
            description=(
                "PROPOSE extending every overdue loan in a borrower group. "
                "Creates a proposal for human approval; never writes."
            ),
            mode=ToolMode.PROPOSE,
            args_model=ExtendOverdueBatch,
        ),
    }
)


def _flatten_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Strip pydantic's `title` keys and collapse `Optional[X]`'s
    `anyOf: [X-schema, {"type": "null"}]` down to `X-schema` (merging back
    any sibling `default`). A property already excluded from `required`
    stays excluded — flattening only changes its own shape, never the
    model-level `required` list."""
    out = dict(schema)
    out.pop("title", None)
    properties = out.get("properties")
    if properties:
        flattened: dict[str, Any] = {}
        for prop_name, prop in properties.items():
            prop = dict(prop)
            any_of = prop.pop("anyOf", None)
            if any_of is not None:
                non_null = [branch for branch in any_of if branch.get("type") != "null"]
                if len(non_null) == 1:
                    merged = dict(non_null[0])
                    if "default" in prop:
                        merged["default"] = prop["default"]
                    prop = merged
                else:
                    prop["anyOf"] = [
                        {k: v for k, v in branch.items() if k != "title"} for branch in any_of
                    ]
            prop.pop("title", None)
            flattened[prop_name] = prop
        out["properties"] = flattened
    return out


def tool_schemas(modes: frozenset[ToolMode] = frozenset(ToolMode)) -> list[dict[str, Any]]:
    """OpenAI function-calling schemas for every spec whose mode is in `modes`."""
    out: list[dict[str, Any]] = []
    for spec in TOOL_SPECS.values():
        if spec.mode not in modes:
            continue
        # additionalProperties: false is not injected here — ToolArgs'
        # extra="forbid" already makes pydantic emit it on every model.
        schema = _flatten_schema(spec.args_model.model_json_schema())
        out.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": schema,
                },
            }
        )
    return out


def parse_args(name: str, raw: str | Mapping[str, Any] | None) -> ToolArgs:
    """Validate `raw` (a JSON string, an already-parsed mapping, or the
    absence of arguments) against the named tool's args model.

    Raises UnknownToolError for an unknown tool name, ToolArgsError for a
    `raw` string that is not valid JSON, or pydantic.ValidationError for
    arguments that parse but fail the model's constraints.

    A zero-argument tool call comes back from different providers as `None`,
    `""`, or the JSON literal `"null"` — all three are treated as `{}` here,
    same as an absent argument (a tool with required fields still fails
    validation normally against an empty mapping; this only spares a
    zero-argument tool like get_current_context from an artificial
    ToolArgsError over what is, in every provider's intent, "no arguments").

    A JSON string is decoded with `parse_float=Decimal` so a rate like
    `12.345` reaches PercentRate as the exact Decimal the model wrote —
    never rounded through `float` first — and its `decimal_places=2`
    constraint can reject it precisely.
    """
    spec = TOOL_SPECS.get(name)
    if spec is None:
        raise UnknownToolError(name)
    if raw is None or raw == "":
        data: Mapping[str, Any] = {}
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw, parse_float=Decimal)
        except json.JSONDecodeError as exc:
            raise ToolArgsError(f"{name}: arguments are not valid JSON: {exc}") from exc
        data = {} if parsed is None else parsed
    else:
        data = raw
    return spec.args_model.model_validate(data)


class ToolRegistry:
    """Binds handler callables to tool names, refusing any name TOOL_SPECS
    does not declare."""

    def __init__(self, handlers: Mapping[str, Callable[[ToolArgs], dict[str, Any]]]) -> None:
        unknown = sorted(set(handlers) - set(TOOL_SPECS))
        if unknown:
            raise UnknownToolError(f"unregistered tool handler(s): {unknown}")
        self._handlers = dict(handlers)

    def mode(self, name: str) -> ToolMode:
        spec = TOOL_SPECS.get(name)
        if spec is None:
            raise UnknownToolError(name)
        return spec.mode

    def handler(self, name: str) -> Callable[[ToolArgs], dict[str, Any]]:
        """The callable registered for `name`. Raises UnknownToolError when
        `name` is a valid tool but this particular registry was never given
        a handler for it (as well as when `name` is not a tool at all)."""
        handler = self._handlers.get(name)
        if handler is None:
            raise UnknownToolError(name)
        return handler
