"""KCH-238: end-to-end proof that a full agent turn -- prompt in, several
tool round-trips, final answer -- never puts a real fixture name or amount
into an outbound LLM request body.

Drives the six-step loop MANUALLY (KCH-239 owns the real loop): tokenise the
prompt, hand it to a `RecordedFakeLLM` (which records the exact body
`OpenAICompatClient` would send), detokenise the model's tool-call
arguments, run the real handler against `DEMO_LOANS`, tokenise its
observation, append it, repeat. The scanner at the end is deliberately NOT
`assert_no_plaintext` -- an independent, from-scratch check over the raw
fixture data, so a bug shared between the production guard and this test
could not hide a real leak from both at once.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal

from loan_manager.application.agent.tokeniser import TokenMap, assert_no_plaintext
from loan_manager.application.agent.tool_registry import ToolMode, parse_args, tool_schemas
from loan_manager.application.agent.tools.args import (
    CalculateInterestArgs,
    FormatInr,
    GetPortfolioSummary,
    QueryLoans,
    ResolveEntity,
)
from loan_manager.application.agent.tools.read_tools import build_read_registry
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.build_entity_resolver import BuildEntityResolver
from loan_manager.application.use_cases.loans.get_autocomplete import GetAutocompleteValues
from loan_manager.infrastructure.llm.fake import RecordedFakeLLM
from loan_manager.infrastructure.llm.settings import LLMSettings
from loan_manager.infrastructure.seed.demo_fixture import DEMO_LOANS, FIXTURE_TODAY

from .conftest import make_loan, uow_factory_for


def _settings() -> LLMSettings:
    return LLMSettings(
        base_url="https://openrouter.ai/api/v1",
        model="qwen/qwen-2.5-72b-instruct",
        api_key_env="OPENROUTER_API_KEY",
        temperature=0.1,
        max_steps=6,
        timeout_s=60,
    )


def _fixture_loans() -> list:
    return [
        make_loan(
            borrower_name=fl.borrower_name,
            borrower_group=fl.borrower_group,
            depositor_name=fl.depositor_name,
            depositor_group=fl.depositor_group,
            amount=fl.amount,
            giving_date=fl.giving_date,
            due_date=fl.due_date,
        )
        for fl in DEMO_LOANS
        if fl.paidoff_date is None
    ]


def _iter_observation_leaves(node: object, key: str | None = None):
    """(key, leaf) for every leaf under `node` -- the immediate dict key it
    sits under, so callers can exclude e.g. `rate_percent` (a percentage,
    never rupees) without excluding `interest`/`principal`/`exposure`."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _iter_observation_leaves(v, k)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_observation_leaves(v, key)
    else:
        yield key, node


def _fixture_scanner_patterns(extra_amounts: frozenset[Decimal] = frozenset()) -> list[re.Pattern]:
    """Independent (does not import anything from `tokeniser.py`'s own
    regex/rendering helpers) collection of every name and every amount
    rendering that must never appear in an outbound message. `extra_amounts`
    adds raw handler-returned sums/interest/exposure values on top of the
    DEMO_LOANS principals (M5 ORCH ruling: scan for those too, not only
    principals)."""
    name_values: set[str] = set()
    amounts: set[Decimal] = set(extra_amounts)
    for fl in DEMO_LOANS:
        for value in (fl.borrower_name, fl.borrower_group, fl.depositor_name, fl.depositor_group):
            if value:
                name_values.add(value)
        amounts.add(Decimal(fl.amount))

    name_patterns = [
        re.compile(
            r"(?<!\w)" + r"\s+".join(re.escape(w) for w in name.split()) + r"(?!\w)",
            re.IGNORECASE,
        )
        for name in name_values
    ]

    amount_variants: set[str] = set()
    for amount in amounts:
        q = amount.quantize(Decimal("0.01"))
        int_part = str(int(q))
        amount_variants.add(f"{q:f}")
        amount_variants.add(int_part)
        # Indian grouping
        if len(int_part) > 3:
            last3, rest = int_part[-3:], int_part[:-3]
            pairs = []
            while len(rest) > 2:
                pairs.insert(0, rest[-2:])
                rest = rest[:-2]
            if rest:
                pairs.insert(0, rest)
            amount_variants.add(",".join([*pairs, last3]))
            # Western grouping
            groups = []
            rest_w = int_part
            while len(rest_w) > 3:
                groups.insert(0, rest_w[-3:])
                rest_w = rest_w[:-3]
            groups.insert(0, rest_w)
            amount_variants.add(",".join(groups))
    amount_patterns = [
        re.compile(rf"(?<!\w){re.escape(v)}(?!\w)") for v in amount_variants
    ]
    return name_patterns + amount_patterns


def _scan_request_bodies_for_leaks(
    requests: list[dict], extra_amounts: frozenset[Decimal] = frozenset()
) -> list[str]:
    patterns = _fixture_scanner_patterns(extra_amounts)
    leaks: list[str] = []
    for body in requests:
        messages = body.get("messages", [])
        for message in messages:
            for value in message.values():
                text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                for pattern in patterns:
                    if pattern.search(text):
                        leaks.append(f"{pattern.pattern} in {text!r}")
    return leaks


def test_recorded_bodies_contain_zero_fixture_names_or_amounts() -> None:
    loans = _fixture_loans()
    uow_factory = uow_factory_for(loans)
    clock = FixedClock(FIXTURE_TODAY)
    registry = build_read_registry(uow_factory, clock)
    resolver = BuildEntityResolver(GetAutocompleteValues(uow_factory)).execute()
    token_map = TokenMap(resolver)
    interest_ref_id = loans[0].reference_id.value

    recordings = [
        {
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "resolve_entity",
                    "arguments": json.dumps({"text": "Q001"}),
                }
            ],
            "finish_reason": "tool_calls",
        },
        {
            "tool_calls": [
                {
                    "id": "call_2",
                    "name": "query_loans",
                    "arguments": json.dumps({"status": "overdue", "borrower_group": "G001"}),
                }
            ],
            "finish_reason": "tool_calls",
        },
        {
            "tool_calls": [
                {"id": "call_3", "name": "get_portfolio_summary", "arguments": "{}"}
            ],
            "finish_reason": "tool_calls",
        },
        {
            "tool_calls": [
                {
                    "id": "call_4",
                    "name": "format_inr",
                    "arguments": json.dumps({"amount": "AMOUNT_1"}),
                }
            ],
            "finish_reason": "tool_calls",
        },
        {
            "tool_calls": [
                {
                    "id": "call_5",
                    "name": "calculate_interest",
                    "arguments": json.dumps(
                        {"ref_id": interest_ref_id, "rate": 12, "months": 3}
                    ),
                }
            ],
            "finish_reason": "tool_calls",
        },
        {
            "content": "Q001's matching borrowers together owe AMOUNT_1 across G001.",
            "tool_calls": [],
            "finish_reason": "stop",
        },
    ]
    fake = RecordedFakeLLM(recordings, _settings())
    tools = tool_schemas(frozenset({ToolMode.READ}))

    prompt = "Check on iyer loans in sharma group and give me the total in rupees."
    tokenised_prompt = token_map.tokenise_prompt(prompt)
    assert "iyer" not in tokenised_prompt.lower().split()  # sanity: prompt itself is tokenised

    messages: list[dict] = [{"role": "user", "content": tokenised_prompt}]

    ARGS_MODELS = {
        "resolve_entity": ResolveEntity,
        "query_loans": QueryLoans,
        "get_portfolio_summary": GetPortfolioSummary,
        "format_inr": FormatInr,
        "calculate_interest": CalculateInterestArgs,
    }

    # M5 ORCH ruling: scan the RAW (pre-tokenisation) handler observations
    # for every money-shaped leaf too (sums/interest/exposure), not only the
    # DEMO_LOANS principals -- excluding `rate_percent`, a percentage, never
    # rupees.
    observed_amounts: set[Decimal] = set()

    for _ in range(5):
        completion = fake.complete(messages, tools=tools)
        call = completion.tool_calls[0]
        messages.append(
            {
                "role": "assistant",
                "content": completion.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": call.arguments},
                    }
                ],
            }
        )
        detokenised = token_map.detokenise_args(call.arguments)
        args = parse_args(call.name, detokenised)
        assert isinstance(args, ARGS_MODELS[call.name])
        handler = registry.handler(call.name)
        observation = handler(args)
        for leaf_key, leaf_value in _iter_observation_leaves(observation):
            if leaf_key == "rate_percent":
                continue
            if isinstance(leaf_value, str) and re.fullmatch(r"\d+\.\d\d", leaf_value):
                observed_amounts.add(Decimal(leaf_value))
        tokenised_observation = token_map.tokenise_observation(observation)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "name": call.name,
                "content": json.dumps(tokenised_observation, ensure_ascii=False),
            }
        )

    final = fake.complete(messages, tools=tools)
    assert final.tool_calls == ()
    assert final.content is not None

    leaks = _scan_request_bodies_for_leaks(fake.requests, frozenset(observed_amounts))
    assert leaks == [], f"plaintext fixture data leaked into outbound bodies: {leaks[:5]}"

    # Pin the production guard too: it must never false-positive on any of
    # these real recorded bodies (independent evidence from the from-scratch
    # scanner above -- a bug shared by both would otherwise hide a leak from
    # each).
    for body in fake.requests:
        assert_no_plaintext(body, token_map)
