"""Unit tests for loan_manager.application.agent.tools.args (KCH-235).

Exercises the pydantic argument models directly — no LLM, no registry, no DB.
"""
from __future__ import annotations

import typing
from decimal import Decimal

import pytest
from loan_manager.application.agent.tool_registry import TOOL_SPECS, tool_schemas
from loan_manager.application.agent.tools import args as args_mod
from loan_manager.domain.value_objects.status import LoanStatus
from pydantic import ValidationError

from .conftest import VALID_PAYLOADS

# Fields whose description/name is allowed to mention "date". Empty: no field
# anywhere in the agent tool boundary may name a date, per CLAUDE.md
# ("giving_date is never used in interest or time-period calculations").
_DATE_ALLOWLIST: frozenset[str] = frozenset()


def _flatten_optional(prop: dict) -> dict:
    """A pydantic Optional field's real constraints (description, min, max,
    type) live INSIDE its `anyOf`'s non-null branch, not at the property's
    own top level — `{"anyOf": [{"type": "integer", ...}, {"type": "null"}],
    "default": null}`. Reading `prop.get("type")`/`prop.get("description")`
    directly, without unwrapping this, silently skips every optional field:
    exactly the review-cycle-1 MAJOR finding for these two checks below.
    Independent of (does not import) tool_registry._flatten_schema, so a bug
    in this test can't be masked by sharing logic with the code it checks."""
    any_of = prop.get("anyOf")
    if not any_of:
        return prop
    non_null = [branch for branch in any_of if branch.get("type") != "null"]
    if len(non_null) == 1:
        merged = dict(non_null[0])
        if "default" in prop:
            merged["default"] = prop["default"]
        return merged
    return prop


def _schemas_to_check() -> list[tuple[str, dict]]:
    """(label, schema) pairs for BOTH the raw pydantic schema per tool AND
    the flattened `tool_schemas()` parameters per tool — the latter is what
    the LLM actually receives over the wire. Review-cycle-2: a bug in
    `_flatten_schema` (e.g. dropping `maximum` while collapsing `anyOf`)
    would pass every check that only looks at the raw per-model schema,
    because flattening runs strictly after `model_json_schema()`."""
    pairs = [
        (f"{tool_name} (raw)", spec.args_model.model_json_schema())
        for tool_name, spec in TOOL_SPECS.items()
    ]
    pairs += [
        (f"{schema['function']['name']} (tool_schemas)", schema["function"]["parameters"])
        for schema in tool_schemas()
    ]
    return pairs


def _numeric_properties(schema: dict) -> dict[str, dict]:
    out = {}
    for name, prop in schema.get("properties", {}).items():
        flat = _flatten_optional(prop)
        if flat.get("type") in ("integer", "number"):
            out[name] = flat
    return out


@pytest.mark.parametrize("tool_name", sorted(TOOL_SPECS))
def test_undeclared_field_raises(tool_name: str) -> None:
    """extra='forbid': an invented argument, notably giving_date, is rejected."""
    model = TOOL_SPECS[tool_name].args_model
    payload = {**VALID_PAYLOADS[tool_name], "giving_date": "2026-01-01"}
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_calculate_interest_rejects_fractional_rate_naming_unit() -> None:
    with pytest.raises(ValidationError) as excinfo:
        args_mod.CalculateInterestArgs(ref_id="2026_03_004", rate=Decimal("0.12"), months=3)
    # Literal message, not just a substring guess at it.
    assert "rate is a percentage, not a fraction - did you mean 12?" in str(excinfo.value)


def test_rate_12_and_0_accepted() -> None:
    assert args_mod.CalculateInterestArgs(
        ref_id="2026_03_004", rate=12, months=3
    ).rate == Decimal("12")
    assert args_mod.CalculateInterestArgs(
        ref_id="2026_03_004", rate=0, months=3
    ).rate == Decimal("0")


def test_rate_above_100_rejected() -> None:
    with pytest.raises(ValidationError):
        args_mod.CalculateInterestArgs(ref_id="2026_03_004", rate=101, months=3)


@pytest.mark.parametrize("rate", [Decimal("0.5"), Decimal("0.99")])
def test_rate_fraction_strictly_between_zero_and_one_rejected(rate: Decimal) -> None:
    with pytest.raises(ValidationError, match="did you mean 12"):
        args_mod.CalculateInterestArgs(ref_id="2026_03_004", rate=rate, months=3)


def test_rate_exactly_one_accepted() -> None:
    """1 is a boundary, not a fraction: `_reject_fraction` only rejects the
    OPEN interval 0 < v < 1, so 1% must go through."""
    assert args_mod.CalculateInterestArgs(
        ref_id="2026_03_004", rate=1, months=3
    ).rate == Decimal("1")


def test_every_numeric_property_declares_unit_and_range() -> None:
    """Every integer/number field must carry a non-empty description AND an
    explicit minimum and maximum — the LLM has no other way to learn the unit
    or the valid range for e.g. a rate vs. a whole-rupee amount. Checked
    against BOTH the raw per-model schema and tool_schemas()'s flattened
    output (what the LLM actually receives): they can diverge if
    `_flatten_schema` ever drops a constraint while collapsing `anyOf`."""
    for label, schema in _schemas_to_check():
        for prop_name, prop in _numeric_properties(schema).items():
            assert prop.get("description"), f"{label}.{prop_name} has no description"
            assert "minimum" in prop, f"{label}.{prop_name} has no minimum"
            assert "maximum" in prop, f"{label}.{prop_name} has no maximum"


def test_no_schema_property_mentions_date_unless_allowlisted() -> None:
    """Checked against BOTH the raw per-model schema and tool_schemas()'s
    flattened output — see test_every_numeric_property_declares_unit_and_range."""
    for label, schema in _schemas_to_check():
        for prop_name, prop in schema.get("properties", {}).items():
            if prop_name in _DATE_ALLOWLIST:
                continue
            flat = _flatten_optional(prop)
            haystack = f"{prop_name} {flat.get('description', '')}".lower()
            assert "date" not in haystack, f"{label}.{prop_name} mentions 'date': {prop!r}"


def _annotation_mentions_float(annotation: object) -> bool:
    if annotation is float:
        return True
    args = typing.get_args(annotation)
    return any(_annotation_mentions_float(a) for a in args)


def test_float_never_used() -> None:
    """CLAUDE.md: never use float for monetary or rate values."""
    for tool_name, spec in TOOL_SPECS.items():
        for field_name, field_info in spec.args_model.model_fields.items():
            assert not _annotation_mentions_float(field_info.annotation), (
                f"{tool_name}.{field_name} uses float: {field_info.annotation!r}"
            )


def test_status_literal_matches_loan_status() -> None:
    expected = {s.value.lower() for s in LoanStatus}
    actual = set(typing.get_args(args_mod.StatusLiteral))
    assert actual == expected


def test_update_loan_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError, match="at least one field"):
        args_mod.UpdateLoan(ref_id="2026_03_004")


@pytest.mark.parametrize("bad", [True, "3", 3.0])
def test_months_strict_int_rejects_bool_str_float(bad: object) -> None:
    with pytest.raises(ValidationError):
        args_mod.ExtendLoan(ref_id="2026_03_004", months=bad, rate=12)


def test_months_plain_json_int_accepted() -> None:
    assert args_mod.ExtendLoan(ref_id="2026_03_004", months=3, rate=12).months == 3


@pytest.mark.parametrize("bad", [True, "150000", 150000.0])
def test_rupees_whole_strict_int_rejects_bool_str_float(bad: object) -> None:
    with pytest.raises(ValidationError):
        args_mod.CreateLoan(
            borrower_name="Ravi Kumar",
            borrower_group="sharma-group",
            depositor_name="Meena Shah",
            amount=bad,
        )


@pytest.mark.parametrize("bad", [True, "5"])
def test_portfolio_limit_strict_int_rejects_bool_and_str(bad: object) -> None:
    with pytest.raises(ValidationError):
        args_mod.GetPortfolioSummary(limit=bad)


def test_portfolio_limit_rejects_float() -> None:
    with pytest.raises(ValidationError):
        args_mod.GetPortfolioSummary(limit=5.0)


def test_portfolio_limit_null_falls_back_to_default() -> None:
    assert args_mod.GetPortfolioSummary(limit=None).limit == 10


def test_extend_loan_tds_flag_null_falls_back_to_default() -> None:
    assert (
        args_mod.ExtendLoan(ref_id="2026_03_004", months=3, rate=12, tds_flag=None).tds_flag
        is False
    )
