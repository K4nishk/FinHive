"""Unit tests for loan_manager.application.agent.tools.read_resolve (KCH-237)."""
from __future__ import annotations

import json
from dataclasses import dataclass

from loan_manager.application.agent.tools.read_resolve import ResolveEntityTool
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.domain.services.entity_resolver import Candidate, Resolution

from .conftest import make_loan, uow_factory_for


@dataclass(frozen=True)
class _Args:
    text: str


def _build_tool():
    loans = [
        make_loan(
            borrower_name="rohit sharma", borrower_group="sharma group",
            depositor_name="d1", depositor_group="dg1",
        ),
        make_loan(
            borrower_name="amit shah", borrower_group="shah group",
            depositor_name="d2", depositor_group="dg2",
        ),
    ]
    resolver_builder = BuildEntityResolver(GetAutocompleteValues(uow_factory_for(loans)))
    return ResolveEntityTool(resolver_builder)


def test_exact_resolve_no_confirm() -> None:
    tool = _build_tool()
    result = tool.execute(_Args(text="sharma group"))
    assert result["ok"] is True
    assert result["status"] == "resolved"
    assert result["exact"] is True
    assert result["confirm_required"] is False
    assert result["candidates"][0]["value"] == "sharma group"


def test_fuzzy_resolve_requires_confirmation() -> None:
    """"amita shah" is a one-insertion typo of stored "amit shah" — it
    resolves to a single candidate (status == "resolved") but is NOT an
    exact match, so confirmation is still required before acting on it."""
    tool = _build_tool()
    result = tool.execute(_Args(text="amita shah"))
    assert result["ok"] is True
    assert result["status"] == "resolved"
    assert result["exact"] is False
    assert result["confirm_required"] is True
    assert result["candidates"][0]["value"] == "amit shah"
    assert "did you mean" in result["next_action"].lower()


def test_ambiguous_returns_top2() -> None:
    """"sharma" ties "rohit sharma" (borrower_name, token match) against
    "sharma group" (borrower_group, token match) at score 1.0 each -> the
    resolver reports ambiguous, and both are surfaced for the user to
    choose between."""
    tool = _build_tool()
    result = tool.execute(_Args(text="sharma"))
    assert result["ok"] is True
    assert result["status"] == "ambiguous"
    assert result["exact"] is False
    assert result["confirm_required"] is True
    values = {c["value"] for c in result["candidates"][:2]}
    assert values == {"rohit sharma", "sharma group"}


def test_no_match_says_so() -> None:
    tool = _build_tool()
    result = tool.execute(_Args(text="zzz nobody"))
    assert result["ok"] is True
    assert result["status"] == "no_match"
    assert result["candidates"] == []
    # Nothing to confirm when there is no candidate at all -- confirmation
    # only makes sense once there is a value the user could be asked about.
    assert result["confirm_required"] is False
    assert "no candidate matched" in result["next_action"].lower()


class _StubResolver:
    def __init__(self, resolution: Resolution) -> None:
        self._resolution = resolution

    def resolve(self, text: str) -> Resolution:
        return self._resolution


class _StubBuilder:
    def __init__(self, resolution: Resolution) -> None:
        self._resolution = resolution

    def execute(self) -> _StubResolver:
        return _StubResolver(self._resolution)


def test_group_candidate_survives_the_five_cap() -> None:
    """5 tied borrower_name candidates (ranks 1-5) plus a 6th
    borrower_group candidate: a plain `candidates[:5]` cap would drop the
    group candidate entirely, even though it is the ONLY signal the query
    meant a group rather than a name. The output stays capped at 5 overall
    (rank 5's "name5" is the one that gives way), but the group candidate
    and both of the top-2 always survive."""
    candidates = tuple(
        Candidate(field="borrower_name", value=f"name{i}", score=0.9, rank=i)
        for i in range(1, 6)
    ) + (Candidate(field="borrower_group", value="the group", score=0.86, rank=6),)
    resolution = Resolution(query="x", candidates=candidates)
    tool = ResolveEntityTool(_StubBuilder(resolution))

    result = tool.execute(_Args(text="x"))

    values = {c["value"] for c in result["candidates"]}
    assert "the group" in values
    assert {"name1", "name2"} <= values
    assert "name5" not in values  # the one that gives way to make room
    assert len(result["candidates"]) == 5
    ranks = [c["rank"] for c in result["candidates"]]
    assert ranks == sorted(ranks)


def test_multiple_group_candidates_can_exceed_the_five_cap() -> None:
    """2 name candidates (the top2) plus 4 DISTINCT group-field candidates
    ranked below them: the union alone is 6 items, all outside any overlap
    with top2, so the cap must not shrink it back down to 5 -- "remaining
    up to 5" only pads a union that is SMALLER than 5, it never trims one
    that is already bigger."""
    candidates = (
        Candidate(field="borrower_name", value="name1", score=0.95, rank=1),
        Candidate(field="borrower_name", value="name2", score=0.94, rank=2),
        Candidate(field="borrower_group", value="group3", score=0.93, rank=3),
        Candidate(field="depositor_group", value="group4", score=0.92, rank=4),
        Candidate(field="borrower_group", value="group5", score=0.91, rank=5),
        Candidate(field="depositor_group", value="group6", score=0.90, rank=6),
    )
    resolution = Resolution(query="x", candidates=candidates)
    tool = ResolveEntityTool(_StubBuilder(resolution))

    result = tool.execute(_Args(text="x"))

    values = {c["value"] for c in result["candidates"]}
    assert values == {"name1", "name2", "group3", "group4", "group5", "group6"}
    ranks = [c["rank"] for c in result["candidates"]]
    assert ranks == sorted(ranks)


def test_ambiguous_next_action_names_top2_values() -> None:
    candidates = (
        Candidate(field="borrower_name", value="rohit sharma", score=1.0, rank=1),
        Candidate(field="borrower_group", value="sharma group", score=1.0, rank=2),
    )
    resolution = Resolution(query="sharma", candidates=candidates)
    tool = ResolveEntityTool(_StubBuilder(resolution))

    result = tool.execute(_Args(text="sharma"))

    assert result["status"] == "ambiguous"
    assert "rohit sharma" in result["next_action"]
    assert "sharma group" in result["next_action"]


def test_no_amounts_in_output() -> None:
    tool = _build_tool()
    result = tool.execute(_Args(text="sharma group"))
    dumped = json.dumps(result)
    assert "amount" not in dumped.lower()
    for candidate in result["candidates"]:
        assert set(candidate.keys()) == {"field", "value", "rank", "score"}
