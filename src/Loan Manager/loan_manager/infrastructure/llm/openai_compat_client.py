"""KCH-234: `LLMPort` over any OpenAI-compatible `/chat/completions`
endpoint (ARB D-4a). Talks OpenRouter today; `base_url` is config, so a
self-hosted vLLM/Ollama swap needs no code change (ARB:490-496).

The ONLY module in `loan_manager/**` allowed to import `openai` — enforced by
`tests/unit/infrastructure/llm/test_llm_import_boundary.py`.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any

import httpx
import openai
from openai import OpenAI

from loan_manager.application.agent.llm_port import (
    Completion,
    LLMConfigError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
    ToolCall,
    Usage,
)
from loan_manager.infrastructure.llm import pricing
from loan_manager.infrastructure.llm.request_body import build_request_body
from loan_manager.infrastructure.llm.settings import LLMSettings
from loan_manager.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class OpenAICompatClient:
    def __init__(
        self,
        settings: LLMSettings,
        *,
        api_key: str | None = None,
        clock: Callable[[], float] = time.monotonic,
        # Test-only seam: lets a test inject an httpx.Client wired to an
        # httpx.MockTransport so it can see the real bytes this client puts
        # on the wire, without ever opening a socket. The leading underscore
        # marks it as not part of the production surface -- no code path
        # under loan_manager/** may pass it; only tests/** may (KCH-234
        # review round 2, item 7; enforced by
        # test_llm_import_boundary.py::test_no_production_module_uses_the_http_client_test_seam).
        _http_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        key = api_key or os.environ.get(settings.api_key_env)
        if not key:
            raise LLMConfigError(
                f"environment variable {settings.api_key_env!r} is not set "
                "(LLMSettings.api_key_env)"
            )
        self._clock = clock
        self._client = OpenAI(
            base_url=str(settings.base_url),
            api_key=key,
            timeout=settings.timeout_s,
            max_retries=0,  # the agent loop (KCH-239) owns retry/step budget, not the SDK
            default_headers={"X-Title": "FinHive Loan Manager"},
            # OpenAI(http_client=None) is its own default -- production
            # callers never pass `_http_client`, so this is None for them.
            http_client=_http_client,
        )

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
    ) -> Completion:
        body = build_request_body(self._settings, messages, tools)
        # `usage` is not a chat.completions.create() kwarg on the SDK's own
        # signature; OpenRouter reads it back out of extra_body.
        create_kwargs = {key: value for key, value in body.items() if key != "usage"}

        start = self._clock()
        try:
            response = self._client.chat.completions.create(
                **create_kwargs, extra_body={"usage": body["usage"]}
            )
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except openai.APIConnectionError as exc:
            raise LLMUnavailableError(str(exc), status=None) from exc
        except openai.APIStatusError as exc:
            raise LLMUnavailableError(str(exc), status=exc.status_code) from exc
        except (ValueError, ArithmeticError, RecursionError) as exc:
            # A 200 response whose body is truncated/invalid JSON is not an
            # openai.API*Error at all -- the SDK's own body parsing raises a
            # raw json.JSONDecodeError (a ValueError subclass) that would
            # otherwise escape this port uncaught (KCH-234 review round 2,
            # item 2). A pathologically deeply-nested (but syntactically
            # valid) 200 JSON body blows Python's own recursive JSON decoder
            # instead, raising a bare RecursionError -- also not an
            # openai.API*Error, and also must not escape this port (KCH-234
            # fix cycle 3).
            raise LLMResponseError(f"malformed completion response: {exc}") from exc
        latency_ms = (self._clock() - start) * 1000

        return self._to_completion(response, latency_ms)

    def _to_completion(self, response: Any, latency_ms: float) -> Completion:
        # A 200 body can still be malformed -- an empty/`null` `choices`, a
        # `{"error": ...}` payload the SDK happily parses into an
        # all-`None` ChatCompletion, or a shape too different to have the
        # attributes below at all. Every one of those must become
        # LLMResponseError, never a raw TypeError/AttributeError escaping
        # this port.
        try:
            choices = response.choices or []
            if not choices:
                raise LLMResponseError("completion response has no choices")
            choice = choices[0]
            message = choice.message
            if message is None:
                raise LLMResponseError("completion choice has no message")

            tool_calls = tuple(
                ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments)
                for tc in (message.tool_calls or [])
            )
            usage_obj = response.usage
            model_name = response.model or self._settings.model
            # Some backends omit finish_reason on an otherwise-valid choice;
            # Completion.finish_reason is always a str, never None.
            finish_reason = choice.finish_reason or "unknown"
        except LLMResponseError:
            raise
        except (AttributeError, TypeError, LookupError) as exc:
            # LookupError, not just IndexError -- a `choices` shaped as a
            # JSON object (`{"a": 1}`) parses through the SDK as a dict, and
            # `choices[0]` then raises KeyError, a LookupError sibling of
            # IndexError, not IndexError itself (KCH-234 fix cycle 3).
            raise LLMResponseError(f"malformed completion response: {exc}") from exc

        prompt_tokens = getattr(usage_obj, "prompt_tokens", None) if usage_obj is not None else None
        completion_tokens = (
            getattr(usage_obj, "completion_tokens", None) if usage_obj is not None else None
        )
        cost_usd, version = self._cost(usage_obj, prompt_tokens, completion_tokens)

        return Completion(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=model_name,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                price_version=version,
            ),
        )

    def _cost(
        self, usage_obj: Any, prompt_tokens: int | None, completion_tokens: int | None
    ) -> tuple[Decimal | None, str | None]:
        # A free-tier model's cost accounting measures quota, not money
        # (ARB:298-304): reporting `$0.0000` here would look like "spend is
        # controlled" when the real answer is "this metric doesn't apply".
        is_free_tier = self._settings.model.endswith(":free")
        raw_cost = getattr(usage_obj, "cost", None) if usage_obj is not None else None

        if raw_cost is not None:
            if is_free_tier:
                return None, None
            # Provider-reported cost is real, already-computed money -- keep
            # it exact, never re-round it to our own precision. But it is
            # untrusted input off the wire: a non-numeric usage.cost
            # ("n/a", True, {}) must become LLMResponseError, never a raw
            # decimal.InvalidOperation escaping this port (KCH-234 review
            # round 2, item 2).
            try:
                cost = Decimal(str(raw_cost))
                # `Decimal("NaN")`/`Decimal("sNaN")`/`Decimal("Infinity")` all
                # construct without raising -- the finiteness check must run
                # INSIDE this try, or a NaN/Infinity cost escapes silently
                # (Infinity: `cost < 0` is False, no exception at all) or as a
                # raw decimal.InvalidOperation from `cost < 0` on a NaN
                # (KCH-234 fix cycle 3), instead of becoming LLMResponseError.
                if not cost.is_finite() or cost < 0:
                    raise LLMResponseError(
                        "non-finite or negative usage.cost in completion "
                        f"response: {raw_cost!r}"
                    )
            except (ValueError, ArithmeticError) as exc:
                raise LLMResponseError(
                    f"non-numeric usage.cost in completion response: {raw_cost!r}"
                ) from exc
            return cost, None

        if is_free_tier or prompt_tokens is None or completion_tokens is None:
            return None, None
        return pricing.cost_for(self._settings.model, prompt_tokens, completion_tokens)
