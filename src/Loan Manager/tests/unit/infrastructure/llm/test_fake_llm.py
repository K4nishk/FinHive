"""KCH-234: RecordedFakeLLM proves the recorded-fake contract ARB U-3 leans
on -- it must run the exact request-building code the real client runs, and
it must fail loudly, not silently repeat, once its recordings are used up.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from loan_manager.application.agent.llm_port import Completion, LLMResponseError
from loan_manager.infrastructure.llm.fake import RecordedFakeLLM
from loan_manager.infrastructure.llm.settings import LLMSettings

FIXTURE = (
    Path(__file__).resolve().parents[3] / "fixtures" / "llm" / "qwen_tool_call.json"
)


def _settings(**overrides) -> LLMSettings:
    data = dict(
        base_url="https://openrouter.ai/api/v1",
        model="qwen/qwen-2.5-72b-instruct",
        api_key_env="OPENROUTER_API_KEY",
        temperature=0.1,
        max_steps=6,
        timeout_s=60,
    )
    data.update(overrides)
    return LLMSettings(**data)


def test_round_trip_returns_completion_with_tool_call() -> None:
    fake = RecordedFakeLLM.from_json(FIXTURE, _settings())

    completion = fake.complete([{"role": "user", "content": "hi"}])

    assert isinstance(completion, Completion)
    assert completion.finish_reason == "tool_calls"
    assert len(completion.tool_calls) == 1
    call = completion.tool_calls[0]
    assert call.name == "resolve_entity"
    assert json.loads(call.arguments) == {"text": "acme group"}
    assert completion.usage.prompt_tokens == 412
    assert completion.usage.cost_usd == Decimal("0.00037")


def test_captures_outbound_request_bodies_in_order() -> None:
    fake = RecordedFakeLLM.from_json(FIXTURE, _settings())

    fake.complete([{"role": "user", "content": "first"}])
    fake.complete([{"role": "user", "content": "second"}])

    assert len(fake.requests) == 2
    assert fake.requests[0]["messages"][0]["content"] == "first"
    assert fake.requests[1]["messages"][0]["content"] == "second"


def test_captured_body_never_contains_unsupported_params() -> None:
    fake = RecordedFakeLLM.from_json(FIXTURE, _settings())

    fake.complete(
        [{"role": "user", "content": "hi", "name": "someone"}],
        tools=[{"type": "function", "function": {"name": "resolve_entity"}}],
    )

    body = fake.requests[0]
    for banned in ("logprobs", "top_logprobs", "logit_bias"):
        assert banned not in body
    assert body["n"] == 1
    assert "temperature" in body
    assert all("name" not in m for m in body["messages"])


def test_recorded_request_is_immune_to_later_mutation() -> None:
    """`.requests` must hold what was actually sent, forever -- a caller
    mutating a tool/message dict it passed in AFTER the call (a totally
    ordinary thing to do with a mutable schema object) must never rewrite
    history. A shallow `copy.copy(body)` still shares the inner dicts nested
    inside `messages`/`tools`, so it would let exactly this happen."""
    fake = RecordedFakeLLM.from_json(FIXTURE, _settings())
    tools = [{"type": "function", "function": {"name": "resolve_entity"}}]

    fake.complete([{"role": "user", "content": "hi"}], tools=tools)
    tools[0]["function"]["name"] = "MUTATED_AFTER_THE_CALL"

    assert fake.requests[0]["tools"][0]["function"]["name"] == "resolve_entity"


def test_null_finish_reason_is_normalised_not_none() -> None:
    """MINOR (review round 2, item 6): fake.py must mirror
    OpenAICompatClient's own normalisation -- `Completion.finish_reason` is
    documented as always `str`, never `None`."""
    fake = RecordedFakeLLM(
        [{
            "content": "ok", "tool_calls": [], "finish_reason": None,
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }],
        _settings(),
    )

    completion = fake.complete([{"role": "user", "content": "hi"}])

    assert completion.finish_reason == "unknown"
    assert isinstance(completion.finish_reason, str)


def test_missing_usage_block_reports_tokens_as_none_not_key_error() -> None:
    """MINOR (review round 2, item 6): a recording with no `usage` key at all
    must report `prompt_tokens`/`completion_tokens` as `None` -- exactly what
    OpenAICompatClient reports for a real response missing its usage block --
    never a raw KeyError from this fake."""
    fake = RecordedFakeLLM(
        [{"content": "ok", "tool_calls": [], "finish_reason": "stop"}],
        _settings(),
    )

    completion = fake.complete([{"role": "user", "content": "hi"}])

    assert completion.usage.prompt_tokens is None
    assert completion.usage.completion_tokens is None
    assert completion.usage.cost_usd is None


def test_fake_exhausted_raises_llm_response_error() -> None:
    fake = RecordedFakeLLM.from_json(FIXTURE, _settings())
    fake.complete([{"role": "user", "content": "one"}])
    fake.complete([{"role": "user", "content": "two"}])

    with pytest.raises(LLMResponseError, match="exhausted"):
        fake.complete([{"role": "user", "content": "three"}])
