"""KCH-234: the ONE place every OpenRouter/qwen quirk is encoded.

Both `OpenAICompatClient` (real egress) and `RecordedFakeLLM` (tests,
KCH-238's egress assertions) call this and only this to build the outbound
body, so a fixed quirk here is fixed for real traffic and for every fake the
same way — no drift between what is tested and what is sent.

Quirks, each cross-referenced to its evidence:
  - drop `messages[*].name` — never observed to be required, and
    OpenRouter-fronted providers vary on whether they accept it.
  - never `logprobs` / `top_logprobs` / `logit_bias` — not used by the
    tool-calling loop and unevenly supported across OpenRouter backends.
  - `n=1` — the agent loop drives one call at a time; asking for choices it
    would throw away burns tokens for nothing.
  - temperature always explicit — data/settings.json:5-13,
    ops/probe_openrouter.py:148 ("Groq converts 0 to 1e-8; be explicit
    everywhere"): never rely on a provider default.
  - `tool_choice="auto"` only when tools are actually offered — sending it
    with no tools is a 400 on some backends.
  - `usage: {"include": True}` — OpenRouter's own cost accounting
    (ops/probe_openrouter.py:152), read back as `usage.cost` by the client.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from loan_manager.infrastructure.llm.settings import LLMSettings


def build_request_body(
    settings: LLMSettings,
    messages: Sequence[Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    cleaned_messages = [
        {key: value for key, value in dict(message).items() if key != "name"}
        for message in messages
    ]

    body: dict[str, Any] = {
        "model": settings.model,
        "messages": cleaned_messages,
        "temperature": settings.temperature,
        "n": 1,
        "usage": {"include": True},
    }

    if tools:
        body["tools"] = list(tools)
        body["tool_choice"] = "auto"

    return body
