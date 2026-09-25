"""Unit tests for loan_manager.application.agent.tool_registry (KCH-235).

test_schema_names_match_probe obtains the probe's tool names by AST-parsing
ops/probe_openrouter.py directly (ORCH ruling) — never by importing `ops` or
touching sys.path, since `ops/` sits outside the Loan Manager package and the
probe script is not import-safe from here (it calls sys.exit(main()) at
module scope only under __main__, but pulling it onto sys.path is still the
wrong direction of dependency for a unit test).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from loan_manager.application.agent.tool_registry import (
    TOOL_SPECS,
    ToolArgsError,
    ToolMode,
    ToolRegistry,
    UnknownToolError,
    _flatten_schema,
    parse_args,
    tool_schemas,
)
from loan_manager.application.agent.tools import args as args_mod
from pydantic import ValidationError

from .conftest import VALID_PAYLOADS


def _probe_path() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "ops" / "probe_openrouter.py"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"ops/probe_openrouter.py not found above {here}")


def _probe_full_tools() -> list[tuple[str, str, dict, list[str]]]:
    """(name, description, props, required) for every entry in the probe's
    FULL_TOOLS list literal, extracted with ast.literal_eval — never by
    importing the module."""
    tree = ast.parse(_probe_path().read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "FULL_TOOLS" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("FULL_TOOLS assignment not found in probe_openrouter.py")


_KNOWN_PROPOSE_NAMES = {"extend_loan", "create_loan", "update_loan", "extend_overdue_batch"}
_KNOWN_READ_NAMES = {
    "get_current_context",
    "resolve_entity",
    "query_loans",
    "get_portfolio_summary",
    "calculate_interest",
    "format_inr",
}


def test_read_mode_schemas_exclude_propose() -> None:
    # Ground truth is hardcoded here, independent of TOOL_SPECS' own .mode
    # values, so that mislabeling a tool's mode in the registry cannot make
    # this test trivially agree with itself.
    assert set(TOOL_SPECS) == _KNOWN_PROPOSE_NAMES | _KNOWN_READ_NAMES
    read_schemas = tool_schemas(modes=frozenset({ToolMode.READ}))
    names = {s["function"]["name"] for s in read_schemas}
    assert names & _KNOWN_PROPOSE_NAMES == set()
    assert names == _KNOWN_READ_NAMES


def test_schema_names_match_probe() -> None:
    probe_tools = _probe_full_tools()
    probe_names = {t[0] for t in probe_tools}
    # Every tool the probe exercises must exist in our registry under the
    # same name (our set is a superset: format_inr, update_loan and
    # extend_overdue_batch are not part of the D-4a probe).
    assert probe_names <= set(TOOL_SPECS)

    for name, _desc, props, required in probe_tools:
        our_schema = TOOL_SPECS[name].args_model.model_json_schema()
        our_required = set(our_schema.get("required", []))
        for field_name in props:
            if field_name not in our_schema.get("properties", {}):
                continue  # our model may carry fields the probe's mini-schema omits
            assert (field_name in required) == (field_name in our_required), (
                f"{name}.{field_name} required mismatch: "
                f"probe={field_name in required} ours={field_name in our_required}"
            )


def test_additional_properties_false_in_every_schema() -> None:
    for schema in tool_schemas():
        params = schema["function"]["parameters"]
        assert params.get("additionalProperties") is False, schema["function"]["name"]


def test_no_anyof_or_title_in_any_schema() -> None:
    """Optional[X]'s anyOf: [X, {"type": "null"}] must be flattened to X, and
    pydantic's "title" noise stripped, everywhere in the emitted schema —
    not merely at the top level."""
    for schema in tool_schemas():
        dumped = json.dumps(schema)
        assert "anyOf" not in dumped, schema["function"]["name"]
        assert "title" not in dumped, schema["function"]["name"]


def test_flatten_schema_falls_back_for_multi_variant_anyof() -> None:
    """None of the 10 real tool schemas has an Optional field with more than
    one non-null variant, so this exercises `_flatten_schema`'s fallback
    branch directly: it strips `title` from each branch but leaves `anyOf`
    itself in place, rather than guessing which variant is "the" type."""
    synthetic = {
        "title": "Synthetic",
        "type": "object",
        "properties": {
            "either": {
                "anyOf": [
                    {"type": "string", "title": "A"},
                    {"type": "integer", "title": "B"},
                    {"type": "null"},
                ],
                "default": None,
                "title": "Either",
            }
        },
    }
    flattened = _flatten_schema(synthetic)
    assert "title" not in flattened
    assert "title" not in flattened["properties"]["either"]
    assert flattened["properties"]["either"]["anyOf"] == [
        {"type": "string"},
        {"type": "integer"},
        {"type": "null"},
    ]


def test_optional_fields_keep_constraints_after_flattening() -> None:
    update_loan = next(s for s in tool_schemas() if s["function"]["name"] == "update_loan")
    amount = update_loan["function"]["parameters"]["properties"]["amount"]
    assert amount["type"] == "integer"
    assert amount["minimum"] == 1
    assert "description" in amount
    assert "amount" not in update_loan["function"]["parameters"].get("required", [])


def test_unknown_handler_name_rejected() -> None:
    with pytest.raises(UnknownToolError):
        ToolRegistry({"not_a_real_tool": lambda a: {}})


def test_registry_accepts_known_handlers_and_exposes_mode() -> None:
    registry = ToolRegistry({name: (lambda a: {}) for name in TOOL_SPECS})
    for name, spec in TOOL_SPECS.items():
        assert registry.mode(name) is spec.mode
    with pytest.raises(UnknownToolError):
        registry.mode("not_a_real_tool")


def test_registry_handler_returns_the_registered_callable() -> None:
    def resolve_entity_handler(a):
        return {"tool": "resolve_entity"}

    def query_loans_handler(a):
        return {"tool": "query_loans"}

    registry = ToolRegistry(
        {"resolve_entity": resolve_entity_handler, "query_loans": query_loans_handler}
    )
    # Identity, not just "returns something callable" — a registry that
    # returned the WRONG handler for a valid name would still pass a test
    # that only checked callable-ness.
    assert registry.handler("resolve_entity") is resolve_entity_handler
    assert registry.handler("query_loans") is query_loans_handler
    assert registry.handler("resolve_entity")(None) == {"tool": "resolve_entity"}


def test_registry_handler_unregistered_name_raises() -> None:
    registry = ToolRegistry({"resolve_entity": lambda a: {}})
    # calculate_interest is a real TOOL_SPECS name but was never registered
    # with THIS registry.
    with pytest.raises(UnknownToolError):
        registry.handler("calculate_interest")
    with pytest.raises(UnknownToolError):
        registry.handler("not_a_real_tool")


def test_parse_args_json_and_mapping() -> None:
    for tool_name, payload in VALID_PAYLOADS.items():
        from_json = parse_args(tool_name, json.dumps(payload))
        from_mapping = parse_args(tool_name, payload)
        assert from_json == from_mapping

    with pytest.raises(UnknownToolError):
        parse_args("not_a_real_tool", {})


@pytest.mark.parametrize("empty_raw", ["", "null", None])
def test_parse_args_empty_or_null_treated_as_no_arguments(empty_raw) -> None:
    """Different providers send "", "null" or None for a zero-argument tool
    call; all three must reach get_current_context the same as an absent
    argument would, not raise ToolArgsError/ValidationError."""
    assert parse_args("get_current_context", empty_raw) == args_mod.GetCurrentContext()


@pytest.mark.parametrize("empty_raw", ["", "null", None])
def test_parse_args_empty_or_null_still_enforces_required_fields(empty_raw) -> None:
    """The {} coercion doesn't bypass validation — a tool with a required
    field still fails normally against an empty mapping."""
    with pytest.raises(ValidationError):
        parse_args("resolve_entity", empty_raw)

    with pytest.raises(ValidationError):
        parse_args("resolve_entity", {})


def test_parse_args_malformed_json_raises_tool_args_error() -> None:
    with pytest.raises(ToolArgsError):
        parse_args("resolve_entity", "{not valid json")
    # A structurally-valid-but-wrong-shape value is a ValidationError, not a
    # ToolArgsError: only "not parseable at all" gets the new error type.
    with pytest.raises(ValidationError):
        parse_args("resolve_entity", "null")


def test_parse_args_long_decimal_rate_rejected() -> None:
    """A JSON string rate with more than 2 decimal digits must be rejected —
    parse_float=Decimal preserves every digit exactly, and PercentRate's
    decimal_places=2 then catches it."""
    raw = '{"ref_id": "2026_03_004", "rate": 12.345, "months": 3}'
    with pytest.raises(ValidationError, match="decimal places"):
        parse_args("calculate_interest", raw)


def test_parse_args_preserves_full_decimal_text_not_float_rounded() -> None:
    """A number with more significant digits than a double can hold proves
    parse_float=Decimal is doing real work, not just decimal_places=2:
    parsed as a plain float first, 12.10000000000000000001 rounds to the
    nearest double (str(float(...)) == "12.1", 1 decimal place — WOULD pass
    decimal_places=2 wrongly); parsed with parse_float=Decimal, every digit
    of the literal survives and decimal_places=2 correctly rejects it."""
    raw = '{"ref_id": "2026_03_004", "rate": 12.10000000000000000001, "months": 3}'
    with pytest.raises(ValidationError, match="decimal places"):
        parse_args("calculate_interest", raw)
