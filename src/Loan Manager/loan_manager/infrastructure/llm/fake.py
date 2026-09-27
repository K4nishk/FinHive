"""KCH-234: deterministic `LLMPort` stand-in (ARB U-3 — no live LLM calls from
cloud agents; recorded fakes only).

Runs the exact same `build_request_body()` as `OpenAICompatClient` and
records every body it produces in `.requests`, so KCH-238's egress test
("no name/group/amount in outbound bodies") and any shared-body assertion
work identically against either implementation. No `openai` import — this
module must never touch the network.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from loan_manager.application.agent.llm_port import (
    Completion,
    LLMResponseError,
    ToolCall,
    Usage,
)
from loan_manager.infrastructure.llm.request_body import build_request_body
from loan_manager.infrastructure.llm.settings import LLMSettings


class RecordedFakeLLM:
    def __init__(
        self, recordings: Sequence[Mapping[str, Any]], settings: LLMSettings
    ) -> None:
        self._recordings = list(recordings)
        self._settings = settings
        self._next = 0
        self.requests: list[dict[str, Any]] = []

    @classmethod
    def from_json(cls, path: str | Path, settings: LLMSettings) -> RecordedFakeLLM:
        recordings = json.loads(Path(path).read_text())
        return cls(recordings, settings)

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
    ) -> Completion:
        body = build_request_body(self._settings, messages, tools)
        # deepcopy: a caller mutating its own `.requests` entry later must
        # never let that mutation leak back into what the fake itself holds,
        # or a test could pass by accident on a body it never actually sent.
        self.requests.append(copy.deepcopy(body))

        if self._next >= len(self._recordings):
            raise LLMResponseError("fake exhausted: no more recorded turns")
        recording = self._recordings[self._next]
        self._next += 1
        return self._to_completion(recording)

    def _to_completion(self, recording: Mapping[str, Any]) -> Completion:
        # Mirrors OpenAICompatClient._to_completion() exactly (KCH-234 review
        # round 2, item 6): a recording missing `usage` entirely, or with a
        # `finish_reason` of `None`, or missing individual token counts, must
        # produce the same Completion shape a real malformed-but-200 provider
        # response would -- never a raw KeyError from this fake, and never a
        # `finish_reason` of `None` where `Completion.finish_reason` is
        # documented as always `str`.
        usage = recording.get("usage") or {}
        cost_raw = usage.get("cost_usd")
        return Completion(
            content=recording.get("content"),
            tool_calls=tuple(
                ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
                for tc in recording.get("tool_calls", [])
            ),
            finish_reason=recording.get("finish_reason") or "unknown",
            model=recording.get("model", self._settings.model),
            usage=Usage(
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                latency_ms=usage.get("latency_ms", 0.0),
                cost_usd=Decimal(str(cost_raw)) if cost_raw is not None else None,
                price_version=usage.get("price_version"),
            ),
        )
