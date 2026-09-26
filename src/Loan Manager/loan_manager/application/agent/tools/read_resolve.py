"""resolve_entity: free text -> canonical borrower/group slug (KCH-237).

Wraps `EntityResolver` (KCH-236) for the agent boundary. Names reach this
tool UNTOKENISED — the projections it returns are the raw stored
borrower/depositor names and groups a human typed at data-entry time, which
the model needs verbatim to ask "did you mean X?" or to hand back to
query_loans. KCH-238 tokenises names on the way OUT to the LLM (egress);
this tool's own return value is not that boundary.

No amounts appear anywhere in this tool's output — it only ever resolves
names, never loan values.
"""
from __future__ import annotations

from typing import Any

from loan_manager.application.agent.tools.observations import ok
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.domain.services.entity_resolver import GROUP_FIELDS, Candidate

_MAX_CANDIDATES = 5
_TOP_N = 2


def _select_candidates(candidates: tuple[Candidate, ...]) -> list[Candidate]:
    """top2 (union) every group-field candidate (union) up to `_MAX_CANDIDATES`
    total padded from the remaining highest-ranked candidates -- rank-ordered.

    A plain `candidates[:_MAX_CANDIDATES]` cap can silently drop the ONLY
    candidate whose field is `borrower_group`/`depositor_group` -- the one
    signal that the query meant a group, not a name -- whenever 5 or more
    name candidates outscore it, and can drop the #2 candidate an ambiguous
    result needs to name. Both are kept even if that pushes the total past
    `_MAX_CANDIDATES`; only the long tail beyond top2+group gets capped.
    """
    selected: dict[int, Candidate] = {}
    for c in candidates[:_TOP_N]:
        selected[c.rank] = c
    for c in candidates:
        if c.field in GROUP_FIELDS:
            selected[c.rank] = c
    for c in candidates:
        if len(selected) >= _MAX_CANDIDATES:
            break
        selected.setdefault(c.rank, c)
    return sorted(selected.values(), key=lambda c: c.rank)


class ResolveEntityTool:
    def __init__(self, build_resolver: BuildEntityResolver) -> None:
        self._build_resolver = build_resolver

    def execute(self, args: Any) -> dict[str, Any]:
        # Rebuilt on every call, never cached: a borrower/group added or
        # renamed since the resolver was last built must be resolvable on
        # the very next turn, and this is a bounded read (autocomplete over
        # active loans), not a hot loop.
        resolver = self._build_resolver.execute()
        resolution = resolver.resolve(args.text)

        candidates = [
            {
                "field": c.field,
                "value": c.value,
                "rank": c.rank,
                "score": round(c.score, 3),
            }
            for c in _select_candidates(resolution.candidates)
        ]

        if resolution.status == "no_match":
            next_action = (
                "no candidate matched; tell the user their text did not match any "
                "known borrower or group and ask them to check the spelling"
            )
        elif resolution.exact:
            next_action = "use the returned value directly; no confirmation needed"
        elif resolution.status == "resolved":
            top_value = resolution.top.value if resolution.top else None
            next_action = (
                f"not an exact match; ask the user 'did you mean {top_value}?' "
                "and wait for confirmation before using it"
            )
        else:  # ambiguous
            top2_values = [c.value for c in resolution.top2]
            names = " or ".join(f"'{v}'" for v in top2_values)
            next_action = (
                f"ambiguous; ask the user to choose between {names} before proceeding"
            )

        return ok(
            query=args.text,
            status=resolution.status,
            exact=resolution.exact,
            # Nothing to confirm when there is no candidate at all (no_match)
            # -- confirmation only makes sense once there is a value the
            # user could be asked about.
            confirm_required=resolution.status != "no_match" and not resolution.exact,
            candidates=candidates,
            next_action=next_action,
        )
