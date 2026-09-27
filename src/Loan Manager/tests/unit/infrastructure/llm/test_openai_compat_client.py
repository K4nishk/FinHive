"""KCH-234: OpenAICompatClient, entirely offline.

Two styles of double are used, on purpose:
  - `client._client.chat.completions.create` monkeypatched directly, for
    tests that only care about a Python-level return value or a raised SDK
    exception (fast, no HTTP layer involved at all).
  - `httpx.MockTransport` injected via the `_http_client` constructor
    param (test-only seam), for tests that must see the REAL bytes
    OpenAICompatClient puts on
    the wire -- egress shape, headers, retry count -- which a monkeypatched
    `create()` cannot show, since it never goes through httpx at all.

Neither ever opens a socket. No `OPENROUTER_API_KEY` is required or read
except by the one test that specifically exercises its absence.
"""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace

import httpx
import openai
import pytest
from loan_manager.application.agent.llm_port import (
    LLMConfigError,
    LLMError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from loan_manager.infrastructure.llm.fake import RecordedFakeLLM
from loan_manager.infrastructure.llm.openai_compat_client import OpenAICompatClient
from loan_manager.infrastructure.llm.settings import LLMSettings

FIXTURE_MESSAGES = [{"role": "user", "content": "hi", "name": "someone"}]
FIXTURE_TOOLS = [{"type": "function", "function": {"name": "resolve_entity"}}]


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


def _ticking_clock(*values: float):
    """A clock stub that returns `values` in order, one per call -- a bare
    `lambda: [a, b].pop(0)` rebuilds and re-pops the SAME first element every
    call, which is not a clock at all."""
    it = iter(values)
    return lambda: next(it)


def _client(clock=None) -> OpenAICompatClient:
    return OpenAICompatClient(
        _settings(), api_key="test-key", clock=clock or _ticking_clock(0.0, 0.5)
    )


def _mock_client(handler) -> OpenAICompatClient:
    """An OpenAICompatClient wired to a MockTransport -- real httpx request
    building and real SDK response parsing, zero network."""
    return OpenAICompatClient(
        _settings(), api_key="test-key",
        _http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _fake_response(*, content=None, tool_calls=None, finish_reason="stop", cost=None):
    tool_call_objs = [
        SimpleNamespace(
            id=tc["id"],
            function=SimpleNamespace(name=tc["name"], arguments=tc["arguments"]),
        )
        for tc in (tool_calls or [])
    ]
    usage_kwargs = {"prompt_tokens": 100, "completion_tokens": 20}
    if cost is not None:
        usage_kwargs["cost"] = cost
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=tool_call_objs or None),
                finish_reason=finish_reason,
            )
        ],
        model="qwen/qwen-2.5-72b-instruct",
        usage=SimpleNamespace(**usage_kwargs),
    )


def _req() -> httpx.Request:
    return httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")


def _wire_success_body(
    *, content="ok", tool_calls=None, finish_reason="stop",
    model="qwen/qwen-2.5-72b-instruct", usage_extra=None,
) -> dict:
    usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
    if usage_extra is not None:
        usage.update(usage_extra)
    return {
        "id": "chatcmpl-test", "object": "chat.completion", "created": 0, "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content, "tool_calls": tool_calls},
            "finish_reason": finish_reason,
        }],
        "usage": usage,
    }


# --------------------------------------------------------------------------
# Egress: what actually goes on the wire (MockTransport)
# --------------------------------------------------------------------------

def test_wire_body_matches_fake_for_same_inputs() -> None:
    """MAJOR (review round 1, item 1): compare the REAL bytes
    OpenAICompatClient sends -- not a hand-assembled kwargs dict -- against
    RecordedFakeLLM's recorded body for the identical call."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json=_wire_success_body())

    client = _mock_client(handler)
    client.complete(FIXTURE_MESSAGES, tools=FIXTURE_TOOLS)

    fake = RecordedFakeLLM([{
        "content": "ok", "tool_calls": [], "finish_reason": "stop",
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }], _settings())
    fake.complete(FIXTURE_MESSAGES, tools=FIXTURE_TOOLS)

    wire_body = json.loads(captured["request"].content)
    assert wire_body == fake.requests[0]


def test_no_extra_headers_carry_secrets() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json=_wire_success_body())

    client = OpenAICompatClient(
        _settings(), api_key="super-secret-key-value",
        _http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client.complete(FIXTURE_MESSAGES)

    headers = captured["headers"]
    assert headers["authorization"] == "Bearer super-secret-key-value"
    assert headers["x-title"] == "FinHive Loan Manager"
    for name, value in headers.items():
        if name.lower() == "authorization":
            continue
        assert "super-secret-key-value" not in value, f"header {name!r} leaked the API key"


def test_wire_tool_choice_and_tools_absent_without_tools() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_wire_success_body())

    _mock_client(handler).complete(FIXTURE_MESSAGES)  # no tools argument

    assert "tool_choice" not in captured["body"]
    assert "tools" not in captured["body"]


def test_wire_usage_include_is_requested() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_wire_success_body())

    _mock_client(handler).complete(FIXTURE_MESSAGES)

    assert captured["body"]["usage"] == {"include": True}


def test_wire_temperature_matches_settings() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_wire_success_body())

    client = OpenAICompatClient(
        _settings(temperature=0.37), api_key="k",
        _http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client.complete(FIXTURE_MESSAGES)

    assert captured["body"]["temperature"] == pytest.approx(0.37)


def test_api_key_env_honours_custom_variable_name(monkeypatch) -> None:
    monkeypatch.setenv("MY_CUSTOM_OPENROUTER_KEY", "from-custom-env")
    settings = _settings(api_key_env="MY_CUSTOM_OPENROUTER_KEY")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=_wire_success_body())

    client = OpenAICompatClient(
        settings, _http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    client.complete(FIXTURE_MESSAGES)

    assert captured["auth"] == "Bearer from-custom-env"


def test_max_retries_zero_means_a_429_triggers_exactly_one_http_call() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    with pytest.raises(LLMUnavailableError):
        _mock_client(handler).complete(FIXTURE_MESSAGES)
    assert calls["n"] == 1


def test_max_retries_zero_means_a_500_triggers_exactly_one_http_call() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"error": {"message": "boom"}})

    with pytest.raises(LLMUnavailableError):
        _mock_client(handler).complete(FIXTURE_MESSAGES)
    assert calls["n"] == 1


def test_connection_error_maps_to_llm_unavailable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(LLMUnavailableError) as exc:
        _mock_client(handler).complete(FIXTURE_MESSAGES)
    assert exc.value.status is None


def test_timeout_setting_is_passed_to_the_sdk_client() -> None:
    client = _client()
    assert client._client.timeout == pytest.approx(60.0)


# --------------------------------------------------------------------------
# Exception mapping (monkeypatched create -- no HTTP layer needed)
# --------------------------------------------------------------------------

def test_timeout_maps_to_llm_timeout_error() -> None:
    client = _client()

    def raise_timeout(**kwargs):
        raise openai.APITimeoutError(request=_req())

    client._client.chat.completions.create = raise_timeout
    with pytest.raises(LLMTimeoutError):
        client.complete(FIXTURE_MESSAGES)


def test_http_429_maps_to_llm_unavailable_error() -> None:
    client = _client()
    response = httpx.Response(429, request=_req(), json={"error": "rate limited"})

    def raise_429(**kwargs):
        raise openai.RateLimitError("rate limited", response=response, body=None)

    client._client.chat.completions.create = raise_429
    with pytest.raises(LLMUnavailableError) as exc:
        client.complete(FIXTURE_MESSAGES)
    assert exc.value.status == 429


def test_missing_key_env_raises_config_error(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(LLMConfigError):
        OpenAICompatClient(_settings())


# --------------------------------------------------------------------------
# Malformed 200 responses (MAJOR, review round 1 item 2): LLMResponseError,
# never a raw TypeError/AttributeError escaping the port.
# --------------------------------------------------------------------------

def test_choices_none_raises_llm_response_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": None,
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    with pytest.raises(LLMResponseError, match="no choices"):
        _mock_client(handler).complete(FIXTURE_MESSAGES)


def test_choices_empty_list_raises_llm_response_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    with pytest.raises(LLMResponseError, match="no choices"):
        _mock_client(handler).complete(FIXTURE_MESSAGES)


def test_error_shaped_200_body_raises_llm_response_error_not_type_error() -> None:
    """OpenRouter can return HTTP 200 with an `{"error": ...}` body (rather
    than a proper HTTP error status) on some backend failures. The SDK
    parses this into a ChatCompletion with every field `None` -- must not
    surface as an uncaught TypeError from `None[0]`."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "error": {"message": "something broke", "type": "invalid_request_error"},
        })

    with pytest.raises(LLMResponseError):
        _mock_client(handler).complete(FIXTURE_MESSAGES)


def test_choices_as_dict_raises_llm_response_error_not_key_error() -> None:
    """KCH-234 fix cycle 3: a `choices` shaped as a JSON object (not an
    array) parses through the SDK as a `dict`, not a `list` -- `choices[0]`
    then raises `KeyError` (a `LookupError`, but not an `IndexError`), which
    must not escape this port uncaught."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": {"a": 1},
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    with pytest.raises(LLMResponseError, match="malformed completion response"):
        _mock_client(handler).complete(FIXTURE_MESSAGES)


def test_wholly_unexpected_response_shape_raises_llm_response_error() -> None:
    """A response shaped nothing like a ChatCompletion at all (no `.choices`
    attribute to even be `None`) must still become LLMResponseError -- the
    generic safety net behind the explicit choices/message guards."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1, 2, 3])

    with pytest.raises(LLMResponseError, match="malformed completion response"):
        _mock_client(handler).complete(FIXTURE_MESSAGES)


def test_choice_with_no_message_raises_llm_response_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": None}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    with pytest.raises(LLMResponseError, match="no message"):
        _mock_client(handler).complete(FIXTURE_MESSAGES)


def test_missing_finish_reason_is_normalised_not_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_wire_success_body(finish_reason=None))

    completion = _mock_client(handler).complete(FIXTURE_MESSAGES)

    assert completion.finish_reason == "unknown"
    assert isinstance(completion.finish_reason, str)


@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_calls", "stop"])
def test_finish_reason_passes_through_unchanged(reason: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_wire_success_body(finish_reason=reason))

    completion = _mock_client(handler).complete(FIXTURE_MESSAGES)

    assert completion.finish_reason == reason


# --------------------------------------------------------------------------
# Usage / cost accounting
# --------------------------------------------------------------------------

def test_usage_reports_tokens_latency_and_cost() -> None:
    client = _client(clock=_ticking_clock(10.0, 10.75))
    client._client.chat.completions.create = lambda **kwargs: _fake_response(
        content="ok", cost=0.00037
    )

    completion = client.complete(FIXTURE_MESSAGES)

    assert completion.usage.prompt_tokens == 100
    assert completion.usage.completion_tokens == 20
    assert completion.usage.latency_ms == pytest.approx(750.0)
    assert completion.usage.cost_usd == Decimal("0.00037")
    # provider-reported cost, not our price table
    assert completion.usage.price_version is None


def test_provider_cost_is_kept_exact_not_rounded() -> None:
    """MINOR (review round 1, item 8): a provider-reported cost is already
    real money -- it must come back byte-for-byte as `Decimal(str(cost))`,
    never re-quantised to our own precision."""
    client = _client()
    client._client.chat.completions.create = lambda **kwargs: _fake_response(
        content="ok", cost=0.0001234567
    )

    completion = client.complete(FIXTURE_MESSAGES)

    assert completion.usage.cost_usd == Decimal("0.0001234567")


def test_unknown_price_gives_cost_none_not_zero() -> None:
    client = _client()
    client._client.chat.completions.create = lambda **kwargs: _fake_response(content="ok")

    completion = client.complete(FIXTURE_MESSAGES)

    assert completion.usage.cost_usd is None
    assert completion.usage.cost_usd != Decimal("0")


def test_free_tier_model_cost_is_none_even_when_provider_reports_zero() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_wire_success_body(usage_extra={"cost": 0}))

    client = OpenAICompatClient(
        _settings(model="meta-llama/llama-3.3-70b-instruct:free"), api_key="k",
        _http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    completion = client.complete(FIXTURE_MESSAGES)

    assert completion.usage.cost_usd is None


def test_free_tier_model_cost_is_none_even_when_provider_reports_nonzero() -> None:
    """A `:free`-suffixed model id means the tier's accounting is quota, not
    money, regardless of what number the provider happens to report."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_wire_success_body(usage_extra={"cost": 0.5}))

    client = OpenAICompatClient(
        _settings(model="meta-llama/llama-3.3-70b-instruct:free"), api_key="k",
        _http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    completion = client.complete(FIXTURE_MESSAGES)

    assert completion.usage.cost_usd is None


@pytest.mark.parametrize("bad_cost", ["n/a", True, {}])
def test_non_numeric_usage_cost_raises_llm_response_error_not_decimal_error(bad_cost) -> None:
    """MAJOR (review round 2, item 2): `usage.cost` off the wire is
    untrusted -- a non-numeric value must become LLMResponseError, never a
    raw decimal.InvalidOperation escaping this port."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_wire_success_body(usage_extra={"cost": bad_cost}))

    with pytest.raises(LLMResponseError, match="non-numeric"):
        _mock_client(handler).complete(FIXTURE_MESSAGES)


def test_negative_usage_cost_raises_llm_response_error() -> None:
    """MAJOR (review round 2, item 2): a negative reported cost is also
    nonsensical and must not be trusted as real accounting."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_wire_success_body(usage_extra={"cost": -0.01}))

    with pytest.raises(LLMResponseError, match="negative"):
        _mock_client(handler).complete(FIXTURE_MESSAGES)


@pytest.mark.parametrize("bad_cost", ["NaN", "Infinity", "sNaN"])
def test_non_finite_usage_cost_raises_llm_response_error(bad_cost: str) -> None:
    """KCH-234 fix cycle 3: `Decimal("NaN")` / `Decimal("sNaN")` /
    `Decimal("Infinity")` all construct without raising ValueError or
    ArithmeticError -- unlike the non-numeric case above, the finiteness
    check must run to reject these, or a NaN/Infinity silently becomes (or
    is reported as) a real `Usage.cost_usd`."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_wire_success_body(usage_extra={"cost": bad_cost}))

    with pytest.raises(LLMResponseError):
        _mock_client(handler).complete(FIXTURE_MESSAGES)


def test_json_nan_literal_usage_cost_raises_llm_response_error() -> None:
    """A literal (non-string) `NaN` token on the wire -- not valid per the
    JSON spec, but Python's own `json` module both emits and parses it by
    default -- must be rejected the same way as the string `"NaN"`."""
    raw = json.dumps(_wire_success_body(usage_extra={"cost": float("nan")}))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=raw.encode(), headers={"content-type": "application/json"}
        )

    with pytest.raises(LLMResponseError):
        _mock_client(handler).complete(FIXTURE_MESSAGES)


def test_truncated_200_json_body_raises_llm_response_error_not_json_decode_error() -> None:
    """MAJOR (review round 2, item 2): the openai SDK's own response parsing
    raises a raw json.JSONDecodeError (a ValueError) for a 200
    application/json response whose body is truncated -- this must not
    escape the port uncaught."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{trunc", headers={"content-type": "application/json"})

    with pytest.raises(LLMResponseError, match="malformed completion response"):
        _mock_client(handler).complete(FIXTURE_MESSAGES)


def test_deeply_nested_200_json_body_raises_llm_error_not_recursion_error() -> None:
    """KCH-234 fix cycle 3: a syntactically valid but pathologically
    deeply-nested 200 JSON body (~100000 levels) blows Python's own
    recursive JSON decoder inside the SDK's `create()` call, raising a bare
    `RecursionError` -- not an `openai.API*Error` -- that must not escape
    this port uncaught."""
    body = ("[" * 100_000 + "]" * 100_000).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    with pytest.raises(LLMError):
        _mock_client(handler).complete(FIXTURE_MESSAGES)


def test_missing_usage_reports_tokens_as_none_not_zero() -> None:
    """MINOR (review round 1, item 7): the port types tokens as `int | None`
    -- a response with no usage block at all must report `None`, not `0`
    (which would falsely claim a real, counted zero-token turn)."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = _wire_success_body()
        body["usage"] = None
        return httpx.Response(200, json=body)

    completion = _mock_client(handler).complete(FIXTURE_MESSAGES)

    assert completion.usage.prompt_tokens is None
    assert completion.usage.completion_tokens is None
    assert completion.usage.cost_usd is None
