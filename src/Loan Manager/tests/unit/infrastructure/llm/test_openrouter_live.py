"""KCH-234: the one test in this suite allowed to touch the real network.
Skipped everywhere `OPENROUTER_API_KEY` is unset -- this worktree included,
per BRIEF.md ("No network calls to any LLM (no key exists here)"). Marked
`llm` (pytest.ini) so a CI lane can also exclude it with `-m "not llm"`.
"""

from __future__ import annotations

import os

import pytest
from loan_manager.application.agent.llm_port import Completion
from loan_manager.infrastructure.llm.openai_compat_client import OpenAICompatClient
from loan_manager.infrastructure.llm.settings import load_llm_settings

requires_live_key = pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set -- no live LLM calls without a key",
)


@pytest.mark.llm
@requires_live_key
def test_live_call_returns_completion_through_same_port() -> None:
    settings = load_llm_settings()
    client = OpenAICompatClient(settings)

    completion = client.complete(
        [{"role": "user", "content": "Reply with exactly the word: pong"}]
    )

    assert isinstance(completion, Completion)
    assert completion.model
    # `prompt_tokens` is `int | None` -- `None` when the provider's response
    # carried no usage block at all (KCH-234 review round 2, item 6) -- so a
    # bare `> 0` would raise TypeError against a live response missing usage,
    # rather than failing the assertion cleanly.
    assert completion.usage.prompt_tokens is not None and completion.usage.prompt_tokens > 0
