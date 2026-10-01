"""Run one eval case through the real `RunAgentTurn` and check it (KCH-248).

Everything but the model is real: the seeded encrypted database, the tool
registries, the tokeniser, the leak guard. The model is an `LLMPort` -- a
`RecordedFakeLLM` replaying a cassette offline, or the live client in the
opt-in `llm` lane -- wrapped in `CapturingLLM` so a run reports exactly what
was sent and what came back.

`check_case` is deterministic and returns human-readable failures; an empty
list is a pass. It checks the trace, the entity resolution, the refs and
totals the tools returned, and that the turn was ANSWERED. Whether the model's
prose is right is KCH-250's scoring (`metrics.py`), not this file's.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from loan_manager.application.agent.llm_port import Completion, LLMPort
from loan_manager.application.agent.tokeniser import TokenMap
from loan_manager.application.agent.trace import TraceEvent, TraceKind, TurnOutcome
from loan_manager.application.use_cases.agent.run_agent_turn import TurnResult
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.infrastructure.llm.fake import RecordedFakeLLM
from loan_manager.infrastructure.llm.settings import LLMSettings

from tests.evals.fixture import seeded_container
from tests.evals.schema import Case

CASSETTES_DIR = Path(__file__).parent / "cassettes"

# Never sent anywhere: `RecordedFakeLLM` only uses it to build request bodies.
REPLAY_SETTINGS = LLMSettings(
    base_url="https://replay.invalid/v1",
    model="eval/replay",
    api_key_env="OPENROUTER_API_KEY",
    temperature=0.1,
    max_steps=6,
    timeout_s=30,
)


@dataclass(frozen=True)
class Cassette:
    """`meta.source` is "hand" (authored, proves the harness) or "recorded"
    (`record.py`, proves a model). Format: {"meta": {...}, "completions": [...]}."""

    meta: dict[str, Any]
    completions: list[dict[str, Any]]


def cassette_path(case_id: str) -> Path:
    return CASSETTES_DIR / f"{case_id}.json"


def load_cassette(path: Path) -> Cassette:
    data = json.loads(Path(path).read_text())
    return Cassette(meta=data["meta"], completions=data["completions"])


def completion_to_dict(completion: Completion) -> dict[str, Any]:
    """The cassette shape `RecordedFakeLLM` reads back, for `record.py`."""
    usage = completion.usage
    return {
        "content": completion.content,
        "tool_calls": [
            {"id": c.id, "name": c.name, "arguments": c.arguments}
            for c in completion.tool_calls
        ],
        "finish_reason": completion.finish_reason,
        "model": completion.model,
        "usage": {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "latency_ms": usage.latency_ms,
            "cost_usd": None if usage.cost_usd is None else str(usage.cost_usd),
            "price_version": usage.price_version,
        },
    }


class CapturingLLM:
    """Delegates to `inner`, keeping every request body's messages and every
    completion it returned."""

    def __init__(self, inner: LLMPort) -> None:
        self._inner = inner
        self.requests: list[list[dict[str, Any]]] = []
        self.completions: list[Completion] = []

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
    ) -> Completion:
        self.requests.append([dict(m) for m in messages])
        completion = self._inner.complete(messages, tools)
        self.completions.append(completion)
        return completion


def replay_llm(cassette: Cassette) -> RecordedFakeLLM:
    return RecordedFakeLLM(cassette.completions, REPLAY_SETTINGS)


@dataclass
class CaseRun:
    result: TurnResult
    events: list[TraceEvent]
    token_map: TokenMap
    requests: list[list[dict[str, Any]]]
    completions: list[Completion]
    raw_final: str
    actions: list[str]
    ref_ids_R: list[str]
    facts_R: dict[str, Any] | None
    resolution: dict[str, Any]
    expected_completions: int | None = None
    notes: list[str] = field(default_factory=list)


def _query_observations(events: Sequence[TraceEvent]) -> list[dict[str, Any]]:
    return [
        e.payload
        for e in events
        if e.kind is TraceKind.OBSERVATION
        and e.tool == "query_loans"
        and e.payload
        and e.payload.get("ok") is True
    ]


def _facts(query: Mapping[str, Any], token_map: TokenMap) -> dict[str, Any]:
    """The last `query_loans` observation as `expected_facts` shape. Its
    `total_amount` reaches the trace as an AMOUNT_n token; the token map
    (the run's own) turns it back into the figure."""
    total = query.get("total_amount")
    if isinstance(total, str) and total.startswith("AMOUNT_"):
        total = token_map.value_of(total)
    return {
        "count": query.get("count"),
        "total_amount": str(Decimal(str(total)).quantize(Decimal("0.01"))),
        "overdue_undated": query.get("overdue_undated"),
    }


def run_case(
    case: Case, llm: LLMPort, *, expected_completions: int | None = None
) -> CaseRun:
    """One turn of `case.question` at `case.frozen_today` against the eval
    book. `expected_completions` (a replay's cassette length) lets
    `check_case` flag a cassette the turn did not fully consume."""
    capture = CapturingLLM(llm)
    events: list[TraceEvent] = []
    with seeded_container(case.frozen_today) as container:
        conversation = container.get_start_agent_conversation().execute()
        result = container.get_run_agent_turn(llm=capture).execute(
            conversation, case.question, emit=events.append
        )
        resolver = BuildEntityResolver(
            GetAutocompleteValues(container.get_uow)
        ).execute()
        resolution = resolver.resolve(case.focus["entity"])

    queries = _query_observations(events)
    ref_ids = sorted({ref for q in queries for ref in q.get("ref_ids", [])})
    facts = _facts(queries[-1], conversation.token_map) if queries else None
    final = next(e for e in reversed(events) if e.kind is TraceKind.FINAL)
    return CaseRun(
        result=result,
        events=events,
        token_map=conversation.token_map,
        requests=capture.requests,
        completions=capture.completions,
        raw_final=final.text,
        actions=[e.tool for e in events if e.kind is TraceKind.ACTION and e.tool],
        ref_ids_R=ref_ids,
        facts_R=facts,
        resolution={
            "status": resolution.status,
            "top": resolution.top.value if resolution.top else None,
            "top2": [c.value for c in resolution.top2],
        },
        expected_completions=expected_completions,
    )


def _is_subsequence(wanted: Sequence[str], actual: Sequence[str]) -> bool:
    remaining = iter(actual)
    return all(name in remaining for name in wanted)


def check_case(case: Case, run: CaseRun) -> list[str]:
    """Every way `run` fails `case`; `[]` is a pass."""
    failures: list[str] = []

    if run.result.outcome is not TurnOutcome.ANSWERED:
        failures.append(f"outcome {run.result.outcome.value!r}, expected 'answered'")

    if not _is_subsequence(case.expected_trace, run.actions):
        failures.append(
            f"trace {run.actions} does not contain {list(case.expected_trace)} in order"
        )
    for tool in case.must_not_call:
        if tool in run.actions:
            failures.append(f"must_not_call: {tool} was called")

    if case.expected_ref_ids is None:
        failures.append("expected_ref_ids missing: run gen_expected")
    elif run.ref_ids_R != list(case.expected_ref_ids):
        failures.append(
            f"ref_ids {run.ref_ids_R} != expected {list(case.expected_ref_ids)}"
        )
    if case.expected_facts and run.facts_R != case.expected_facts:
        failures.append(f"facts {run.facts_R} != expected {case.expected_facts}")

    entity = case.expected_entity
    if "slug" in entity:
        if run.resolution["top"] != entity["slug"]:
            failures.append(
                f"resolver top {run.resolution['top']!r} != expected slug {entity['slug']!r}"
            )
    elif sorted(run.resolution["top2"]) != sorted(entity["ambiguous"]):
        failures.append(
            f"resolver top-2 {run.resolution['top2']} != expected ambiguous "
            f"{entity['ambiguous']}"
        )

    if run.expected_completions is not None and len(run.completions) < run.expected_completions:
        failures.append(
            f"cassette not fully consumed: used {len(run.completions)} of "
            f"{run.expected_completions} completions"
        )
    return failures
