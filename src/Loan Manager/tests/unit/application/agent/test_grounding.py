"""KCH-250: grounding proxies. Pure functions; no database."""
from __future__ import annotations

import json
import re
from decimal import Decimal

import pytest
from loan_manager.application.agent import grounding as g
from loan_manager.application.agent.grounding import (
    Fact,
    FactKind,
    Focus,
    Ratio,
    ToolCallView,
)
from loan_manager.application.agent.llm_port import Completion, ToolCall, Usage
from loan_manager.application.agent.trace import TraceEvent, TraceKind
from loan_manager.domain.value_objects.reference_id import REFERENCE_ID_PATTERN


def _kinds(text: str) -> list[tuple[str, str]]:
    return [(f.kind.value, f.value) for f in g.extract_facts(text)]


def _completion(content, calls=()) -> Completion:
    return Completion(content=content, tool_calls=tuple(calls), finish_reason="stop", model="m",
                      usage=Usage(1, 1, 1.0, None, None))


def _obs(payload, tool="query_loans", kind=TraceKind.OBSERVATION) -> TraceEvent:
    return TraceEvent(kind, 1, 6, tool=tool, payload=payload)


def _act(tool, args) -> TraceEvent:
    text = args if isinstance(args, str) else json.dumps(args)
    return TraceEvent(TraceKind.ACTION, 1, 6, text=text, tool=tool)


# --- money leak -------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "₹1,50,000", "150000", "1.5 lakh", "Rs. 1,50,000.00", "2 crore", "1.5 cr",
    "45000/-", "INR 45000", "1,500,000",
])
def test_raw_money_leak_true(text) -> None:
    assert g.raw_money_leak(f"the loan is {text} today") is True


@pytest.mark.parametrize("text", [
    "AMOUNT_1", "AMOUNT_150000", "2026_09_001", "12%", "3 months", "2026", "Q001",
])
def test_raw_money_leak_false(text) -> None:
    assert g.raw_money_leak(f"see {text} here") is False


def test_bare_four_digit_is_not_a_leak_but_is_an_unsupported_count() -> None:
    assert g.raw_money_leak("owes 5000") is False
    f = g.faithfulness_proxy("owes 5000", [])
    assert f.unsupported == (Fact(FactKind.COUNT, "5000"),)


def test_money_is_never_a_fact() -> None:
    assert g.extract_facts("₹1,50,000 and 2 crore and 45000/-") == ()


# --- dates ------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "due 2026-04-01", "due 01/04/2026", "due 01-04-2026", "due 1.4.2026",
    "due 1st April 2026", "due 1 Apr, 2026",
])
def test_dates_normalise_to_iso(text) -> None:
    assert _kinds(text) == [("date", "2026-04-01")]


def test_september_long_form_and_ordinals() -> None:
    assert _kinds("on 3rd September 2026") == [("date", "2026-09-03")]
    assert _kinds("on 30 sept 2026") == [("date", "2026-09-30")]


def test_invalid_date_is_unsupported_even_if_context_has_it() -> None:
    assert _kinds("on 31/02/2026") == [("date", "invalid:31/02/2026")]
    f = g.faithfulness_proxy("on 31/02/2026", [{"note": "31/02/2026"}])
    assert f.ratio == Ratio(0, 1)


def test_dates_are_never_read_month_first() -> None:
    # 12/31/2026 is day 12, month 31: invalid, not 31 December.
    assert _kinds("12/31/2026") == [("date", "invalid:12/31/2026")]
    assert g.faithfulness_proxy("12/31/2026", [{"d": "2026-12-31"}]).ratio == Ratio(0, 1)


def test_date_supported_across_formats() -> None:
    f = g.faithfulness_proxy("due 1 April 2026", [{"due": "2026-04-01"}])
    assert f.ratio == Ratio(1, 1)


# --- reference ids ----------------------------------------------------------

@pytest.mark.parametrize("text", ["2026_09_001.", "(2026_09_001)", "ids: 2026_09_001, x"])
def test_ref_id_boundaries_match(text) -> None:
    assert _kinds(text) == [("ref_id", "2026_09_001")]


def test_ref_id_longer_is_distinct_and_lookalikes_do_not_match() -> None:
    assert _kinds("2026_09_0012") == [("ref_id", "2026_09_0012")]
    assert _kinds("2026_09_1000") == [("ref_id", "2026_09_1000")]
    assert _kinds("X2026_09_001") == []
    assert _kinds("2026_09_001a") == []


@pytest.mark.parametrize("ref", ["2026_09_001", "2026_09_1000", "2025_12_042"])
def test_ref_id_regex_agrees_with_reference_id_value_object(ref) -> None:
    assert re.match(REFERENCE_ID_PATTERN, ref)
    assert _kinds(ref) == [("ref_id", ref)]


# --- tokens -----------------------------------------------------------------

def test_tokens_kinds_and_user_typed_tokens_are_not_facts() -> None:
    assert _kinds("B001 D002 G003 AMOUNT_7") == [
        ("name_token", "B001"), ("name_token", "D002"), ("name_token", "G003"),
        ("amount_token", "AMOUNT_7"),
    ]
    assert _kinds("Q001 N002") == []
    assert _kinds("B0012") == []  # 4 digits: not a token


# --- counts and rates -------------------------------------------------------

def test_count_supported_by_int_and_by_numeric_string() -> None:
    assert g.faithfulness_proxy("3 loans", [{"count": 3}]).ratio == Ratio(1, 1)
    assert g.faithfulness_proxy("3 loans", [{"count": "3"}]).ratio == Ratio(1, 1)
    assert g.faithfulness_proxy("3 loans", [{"count": Decimal("3.00")}]).ratio == Ratio(1, 1)
    assert g.faithfulness_proxy("3 loans", [{"count": 4}]).ratio == Ratio(0, 1)


def test_rate_matches_by_numeric_value_across_kinds() -> None:
    assert g.faithfulness_proxy("at 12%", [{"rate": "12.00"}]).ratio == Ratio(1, 1)
    assert g.faithfulness_proxy("12 loans", [{"rate": "12.00%"}]).ratio == Ratio(1, 1)
    assert g.faithfulness_proxy("at 12.5%", [{"rate": "12.00"}]).ratio == Ratio(0, 1)


def test_year_is_no_fact_and_canonical_value_never_uses_exponent() -> None:
    assert _kinds("in 2026") == []
    assert _kinds("100 loans") == [("count", "100")]
    assert _kinds("12.50%") == [("rate", "12.5")]


def test_context_ignores_bool_none_float_and_walks_nesting() -> None:
    ctx = g.context_facts([{"a": True, "b": None, "c": 1.5, "d": [{"e": (7, {"AMOUNT_2"})}]}])
    assert Fact(FactKind.COUNT, "7") in ctx and Fact(FactKind.AMOUNT_TOKEN, "AMOUNT_2") in ctx
    assert Fact(FactKind.COUNT, "1") not in ctx and Fact(FactKind.COUNT, "5") not in ctx
    assert Fact(FactKind.COUNT, "0") not in ctx  # True is not 1


# --- ratio / faithfulness ---------------------------------------------------

def test_ratio_zero_over_zero_is_one_and_four_dp() -> None:
    assert Ratio(0, 0).value == Decimal("1.0000")
    assert Ratio(3, 4).text == "0.7500"
    assert Ratio(1, 3).text == "0.3333"
    assert Ratio(2, 3).text == "0.6667"


def test_fact_free_answer_is_faithful_and_dedupes_facts() -> None:
    assert g.faithfulness_proxy("all good", []).ratio == Ratio(0, 0)
    f = g.faithfulness_proxy("3 and 3 and 2026_09_001", [{"n": 3}])
    assert f.ratio == Ratio(1, 2) and f.unsupported == (Fact(FactKind.REF_ID, "2026_09_001"),)


def test_faithfulness_reports_leak_alongside_ratio() -> None:
    f = g.faithfulness_proxy("B001 owes ₹1,50,000", [{"n": "B001"}])
    assert f.raw_money_leak is True and f.ratio == Ratio(1, 1)


# --- retrieval --------------------------------------------------------------

def test_context_precision_cases() -> None:
    assert g.context_precision_proxy(["a", "b"], ["a"]) == Ratio(1, 2)
    assert g.context_precision_proxy(["a", "a"], ["a"]) == Ratio(1, 1)
    assert g.context_precision_proxy([], []) == Ratio(1, 1)
    assert g.context_precision_proxy([], ["a"]) == Ratio(0, 1)
    assert g.context_precision_proxy(["a"], []) == Ratio(0, 1)


def test_context_recall_cases() -> None:
    assert g.context_recall(["a"], ["a", "b"]) == Ratio(1, 2)
    assert g.context_recall(["a", "x"], ["a"]) == Ratio(1, 1)
    assert g.context_recall(["a"], []) == Ratio(1, 1)
    assert g.context_recall([], ["a"]) == Ratio(0, 1)


def test_average_precision_at_k() -> None:
    assert g.average_precision_at_k(["a", "x", "b"], ["a", "b"], 3) == Decimal("0.8333")
    assert g.average_precision_at_k(["x", "a"], ["a"], 1) == Decimal("0.0000")
    assert g.average_precision_at_k(["a", "a", "b"], ["a", "b"], 3) == Decimal("1.0000")
    assert g.average_precision_at_k(["a", "b", "c"], ["a"], 5) == Decimal("1.0000")
    assert g.average_precision_at_k(["a", "b"], ["a", "b", "c"], 2) == Decimal("1.0000")
    assert g.average_precision_at_k(["x"], [], 3) == Decimal("1.0000")
    with pytest.raises(ValueError):
        g.average_precision_at_k(["a"], ["a"], 0)


# --- trace helpers ----------------------------------------------------------

def test_query_loans_ref_ids_ordered_unique_and_only_from_query_loans() -> None:
    events = [
        _obs({"ref_ids": ["2026_03_001", "2026_03_002"]}),
        _obs({"ref_ids": ["2026_03_002", 5, "2026_03_003"]}),
        _obs({"ref_ids": ["9999_99_999"]}, tool="get_context"),
        _obs({"ref_ids": ["9999_99_998"]}, kind=TraceKind.ACTION),
        _obs({"ref_ids": "nope"}),
        _obs(None),
    ]
    assert g.query_loans_ref_ids(events) == ("2026_03_001", "2026_03_002", "2026_03_003")


def test_raw_answer_is_last_completion_without_tool_calls() -> None:
    call = ToolCall("c", "t", "{}")
    assert g.raw_answer([]) is None
    assert g.raw_answer([_completion("hi")]) == "hi"
    assert g.raw_answer([_completion("hi"), _completion(None, [call])]) is None
    assert g.raw_answer([_completion("thinking", [call])]) is None
    assert g.raw_answer([_completion("")]) is None


def test_turn_context_takes_observation_and_proposal_payloads_only() -> None:
    events = [
        _obs({"a": 1}), _obs({"b": 2}, kind=TraceKind.PROPOSAL), _obs(None),
        _obs({"c": 3}, kind=TraceKind.ACTION), TraceEvent(TraceKind.THOUGHT, 1, 6, text="x"),
    ]
    assert g.turn_context(events) == ({"a": 1}, {"b": 2})


def test_tool_calls_parse_arguments_and_bad_json_is_empty() -> None:
    events = [
        _act("query_loans", {"status": "overdue"}),
        _act("query_loans", "{not json"),
        _act("query_loans", "[1, 2]"),
        TraceEvent(TraceKind.ACTION, 1, 6, text="{}"),  # no tool
        TraceEvent(TraceKind.THOUGHT, 1, 6, text="{}", tool="x"),
    ]
    assert g.tool_calls(events) == (
        ToolCallView("query_loans", {"status": "overdue"}),
        ToolCallView("query_loans", {}),
        ToolCallView("query_loans", {}),
    )


# --- trace relevancy --------------------------------------------------------

def _tr(calls, focus, **kw):
    return g.trace_relevancy_proxy([ToolCallView(n, a) for n, a in calls], focus, **kw)


def test_relevancy_right_entity_metric_and_period() -> None:
    focus = Focus(entity="acme", metric="calc_interest", metric_args={"months": 3}, period=True)
    r = _tr([("resolve_entity", {"text": "Acme"}),
             ("calc_interest", {"borrower_group": " ACME ", "months": 3})], focus)
    assert (r.entity_match, r.wrong_entity, r.metric_match, r.period_match, r.capability_gap) == (
        True, False, True, True, False)


def test_relevancy_wrong_entity_and_entity_never_used() -> None:
    focus = Focus(entity="acme")
    r = _tr([("query_loans", {"borrower_group": "other"})], focus)
    assert r.wrong_entity is True and r.entity_match is False
    assert _tr([("query_loans", {"status": "overdue"})], focus).entity_match is False
    # resolving the wrong name is exploration, not action
    assert _tr([("resolve_entity", {"borrower_name": "other"})], focus).wrong_entity is False


def test_relevancy_ambiguous_focus_any_entity_use_before_asking_is_wrong() -> None:
    focus = Focus(entity=None, ambiguous=("acme corp", "acme ltd"))
    assert _tr([("query_loans", {"borrower_group": "acme corp"})], focus).wrong_entity is True
    assert _tr([("resolve_entity", {"borrower_group": "acme"})], focus).wrong_entity is False
    assert _tr([], focus).wrong_entity is False


def test_relevancy_no_entity_focus_is_vacuously_matched() -> None:
    r = _tr([("query_loans", {"ref_id": "2026_03_001"})], Focus(entity=None))
    assert (r.entity_match, r.wrong_entity) == (True, False)


def test_relevancy_metric_and_period_mismatch() -> None:
    focus = Focus(entity=None, metric="calc_interest", metric_args={"months": 3}, period=True)
    r = _tr([("calc_interest", {"months": 6}), ("query_loans", {"months": ""})], focus)
    assert (r.metric_match, r.period_match) == (False, True)
    focus = Focus(None, metric="query_loans", period=True)
    r = _tr([("calc_interest", {"status": "x", "period": ""})], focus)
    assert (r.metric_match, r.period_match) == (False, False)


def test_capability_gap_needs_metric_miss_and_unsupported_facts() -> None:
    focus = Focus(entity=None, metric="calc_interest")
    grounded = g.faithfulness_proxy("all good", [])
    invented = g.faithfulness_proxy("it is 9 loans", [])
    assert _tr([], focus, faithfulness=grounded).capability_gap is False
    assert _tr([], focus, faithfulness=invented).capability_gap is True
    assert _tr([], focus).capability_gap is True
    assert _tr([("calc_interest", {})], focus, faithfulness=invented).capability_gap is False


# --- production -------------------------------------------------------------

def test_production_scores_shape_and_string_scores() -> None:
    events = [_obs({"count": 3, "ref_ids": ["2026_03_001"], "total": "AMOUNT_1"})]
    scores = g.production_scores(
        events, [_completion("3 loans, 2026_03_001, AMOUNT_1 and 2026_03_009, 12%")])
    assert scores == {
        "grounding_version": "1", "faithfulness_proxy": "0.6000", "facts_total": 5,
        "facts_unsupported": 2, "unsupported_kinds": ["rate", "ref_id"],
        "raw_money_leak": False, "context_precision_proxy": None, "trace_relevancy_proxy": None,
    }


def test_production_scores_contain_no_floats() -> None:
    events = [_obs({"count": 3, "ref_ids": ["2026_03_001"], "total": "AMOUNT_1"})]
    scores = g.production_scores(events, [_completion("3 loans and 12% of 2026_03_009")])

    def no_float(node):
        assert not isinstance(node, float), node
        if isinstance(node, dict):
            [no_float(v) for v in node.values()]
        elif isinstance(node, list):
            [no_float(v) for v in node]

    no_float(scores)
    json.dumps(scores)


def test_production_scores_carry_kinds_never_values() -> None:
    scores = g.production_scores([], [_completion("2026_03_009 and B007 owes ₹1,50,000")])
    blob = json.dumps(scores)
    assert scores["raw_money_leak"] is True
    assert "2026_03_009" not in blob and "B007" not in blob and "150000" not in blob


def test_production_scores_none_without_a_raw_answer() -> None:
    assert g.production_scores([], []) is None
    assert g.production_scores([], [_completion(None, [ToolCall("c", "t", "{}")])]) is None


def test_fact_free_answer_scores_one() -> None:
    scores = g.production_scores([], [_completion("nothing to report")])
    assert scores["faithfulness_proxy"] == "1.0000"
