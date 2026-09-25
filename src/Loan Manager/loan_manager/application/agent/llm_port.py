"""KCH-234: the LLM boundary the application layer programs against.

Pure port (ARB D-4a) — no `openai`, no `httpx`, no `sqlalchemy`, no PySide6.
`infrastructure/llm/openai_compat_client.py` and
`infrastructure/llm/fake.py` are the only implementations; both return
`Completion` and raise only the errors below, so the six-step agent loop
(KCH-239) and its tests never see a provider-specific exception or shape.

Enforced, not just documented: `tests/unit/infrastructure/llm/
test_llm_import_boundary.py::test_llm_port_imports_no_infrastructure`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    """One tool invocation the model asked for. `arguments` is the raw JSON
    text exactly as the provider sent it — unparsed, so a malformed payload
    is the caller's problem to validate (KCH-235's arg models), never
    silently swallowed here."""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class Usage:
    """`cost_usd` is `None` — never `Decimal("0")` — whenever the price is
    not evidenced, the model is on a free tier, or the provider omitted its
    own accounting (ARB:298-304): a real free-tier zero must stay
    distinguishable from "we don't know". `prompt_tokens`/`completion_tokens`
    are `None`, not `0`, when the provider's response carried no usage block
    at all — `0` would claim a real, counted turn that used no tokens."""

    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: float
    cost_usd: Decimal | None
    price_version: str | None


@dataclass(frozen=True)
class Completion:
    content: str | None
    tool_calls: tuple[ToolCall, ...]
    finish_reason: str
    model: str
    usage: Usage


class LLMPort(Protocol):
    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
    ) -> Completion: ...


class LLMError(Exception):
    """Base for every failure an `LLMPort` implementation may raise."""


class LLMTimeoutError(LLMError):
    """The request timed out (`timeout_s`, `openai.APITimeoutError`)."""


class LLMUnavailableError(LLMError):
    """Transport failure or an HTTP error status (401/403/404/429/5xx,
    `openai.APIConnectionError` / `openai.APIStatusError`). `status` is the
    HTTP status code when one exists, `None` for a connection failure."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class LLMResponseError(LLMError):
    """The response could not be parsed into a `Completion` — no choices,
    an unparsable tool-call shape — or a `RecordedFakeLLM` ran out of
    recorded turns."""


class LLMConfigError(LLMError):
    """`settings.api_key_env` names an environment variable that is not
    set. Raised at client construction, never at call time."""
