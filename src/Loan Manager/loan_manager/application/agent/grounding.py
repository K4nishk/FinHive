"""KCH-250: grounding PROXIES for an Ask FinHive turn.

PROXIES -- definitions differ from RAGAS; thresholds are not RAGAS-comparable.
Every public score/key ends in `_proxy` so nobody mistakes one for the RAGAS
metric of the same name.

Pure and stdlib-only (plus `TOKEN_RE`/`MONEY_RE` from the tokeniser and the
trace/completion types). No floats anywhere in an output: ratios are
`Decimal` quantised to 4 places (`ROUND_HALF_UP`) and travel as `str`.

What each proxy measures
- `faithfulness_proxy(raw_answer, context)`: the share of checkable FACTS in
  the model's RAW answer (tokens, reference ids, dates, counts, rates) that
  also appear in the turn's tool context. Money is never a fact: a raw money
  rendering is a LEAK (`raw_money_leak`), reported separately. A
  fact-free answer scores 1 (0/0 -> 1, vacuously faithful).
- `context_precision_proxy` / `context_recall`: set overlap of the reference
  ids a `query_loans` call returned against ground truth. Both are exposed;
  KCH-249 gates on both (R4).
- `trace_relevancy_proxy`: did the tool calls target the asked entity,
  metric and period; did the agent touch an entity it should have asked
  about (`wrong_entity`).

Production vs evals (R2). `production_scores` fills ONLY `faithfulness_proxy`
and `raw_money_leak` (plus counts/kinds): the other two need ground truth
and are `None` there, computed by the eval harness. Production context is
THIS turn's OBSERVATION and PROPOSAL payloads only (R3), so a token the user
typed (Q/N) or a fact carried over from a prior turn scores as unsupported: a
documented false-negative rate, not a leak.

grounding never sees the TokenMap (R6). The answer it scores is the model's
raw text, tokens intact; a caller that needs real values detokenises first.
`unsupported_kinds` carries kinds only, never values (R8).
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any

from loan_manager.application.agent.llm_port import Completion
from loan_manager.application.agent.tokeniser import MONEY_RE, TOKEN_RE
from loan_manager.application.agent.trace import TraceEvent, TraceKind

GROUNDING_VERSION = "1"

_FOUR_DP = Decimal("0.0001")
_ONE = Decimal(1)


def _q(value: Decimal) -> Decimal:
    return value.quantize(_FOUR_DP, rounding=ROUND_HALF_UP)


class FactKind(str, Enum):
    REF_ID = "ref_id"
    AMOUNT_TOKEN = "amount_token"  # noqa: S105 - a kind name, not a secret
    NAME_TOKEN = "name_token"  # noqa: S105 - a kind name, not a secret
    DATE = "date"
    COUNT = "count"
    RATE = "rate"


@dataclass(frozen=True)
class Fact:
    kind: FactKind
    value: str


@dataclass(frozen=True)
class Ratio:
    hits: int
    total: int

    @property
    def value(self) -> Decimal:
        """hits/total to 4dp; total == 0 -> 1 (vacuous, documented)."""
        if self.total == 0:
            return _q(_ONE)
        return _q(Decimal(self.hits) / Decimal(self.total))

    @property
    def text(self) -> str:
        return format(self.value, "f")


# --- extraction -------------------------------------------------------------

_REF_ID_RE = re.compile(r"(?<![\w])\d{4}_\d{2}_\d+(?![\w])")
_ISO_DATE_RE = re.compile(r"(?<![\w])(\d{4})-(\d{2})-(\d{2})(?![\w])")
_DMY_DATE_RE = re.compile(r"(?<![\w.,/-])(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?![\w])")
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_LONG_DATE_RE = re.compile(
    r"(?<![\w])(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?,?\s+(\d{4})(?![\w])",
    re.IGNORECASE,
)
_RATE_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?%")
_COUNT_RE = re.compile(r"(?<![\w.,])\d+(?:\.\d+)?(?![\w%]|[.,]\d)")
_NUMERIC_LEAF_RE = re.compile(r"\d+(?:\.\d+)?")
_YEAR_MIN, _YEAR_MAX = 1900, 2099
_NUMERIC_KINDS = (FactKind.COUNT, FactKind.RATE)
_INVALID = "invalid:"


def _num(text: str) -> str:
    """Canonical fixed-point text: "12.00" -> "12", "100" -> "100" (never 1E+2)."""
    return format(Decimal(text).normalize(), "f")


def _date_fact(year: str, month: int, day: str, raw: str) -> Fact:
    try:
        return Fact(FactKind.DATE, date(int(year), month, int(day)).isoformat())
    except ValueError:
        return Fact(FactKind.DATE, _INVALID + raw)


def _blank(rx: re.Pattern[str], text: str, on_match: Any) -> str:
    def repl(m: re.Match[str]) -> str:
        on_match(m)
        return " " * len(m.group())

    return rx.sub(repl, text)


def _scan(text: str) -> tuple[list[Fact], bool]:
    """(facts in first-seen order, raw_money_leak). Each pass blanks the spans
    it consumed so a later pass cannot re-read them."""
    facts: list[Fact] = []

    def token(m: re.Match[str]) -> None:
        v = m.group()
        if v.startswith("AMOUNT_"):
            facts.append(Fact(FactKind.AMOUNT_TOKEN, v))
        elif v[0] in "BDG":  # Q/N are user-typed, not facts
            facts.append(Fact(FactKind.NAME_TOKEN, v))

    text = _blank(TOKEN_RE, text, token)
    text = _blank(_REF_ID_RE, text, lambda m: facts.append(Fact(FactKind.REF_ID, m.group())))
    text = _blank(
        _ISO_DATE_RE, text,
        lambda m: facts.append(_date_fact(m[1], int(m[2]), m[3], m.group())),
    )
    text = _blank(
        _DMY_DATE_RE, text,
        lambda m: facts.append(_date_fact(m[3], int(m[2]), m[1], m.group())),
    )
    text = _blank(
        _LONG_DATE_RE, text,
        lambda m: facts.append(
            _date_fact(m[3], _MONTHS.index(m[2][:3].lower()) + 1, m[1], m.group())
        ),
    )

    leak = MONEY_RE.search(text) is not None
    text = MONEY_RE.sub(lambda m: " " * len(m.group()), text)

    text = _blank(_RATE_RE, text, lambda m: facts.append(Fact(FactKind.RATE, _num(m[1]))))

    def count(m: re.Match[str]) -> None:
        v = m.group()
        if not (v.isdigit() and len(v) == 4 and _YEAR_MIN <= int(v) <= _YEAR_MAX):
            facts.append(Fact(FactKind.COUNT, _num(v)))

    _blank(_COUNT_RE, text, count)
    return facts, leak


def extract_facts(raw_text: str) -> tuple[Fact, ...]:
    """The checkable facts in `raw_text`, deduplicated, first-seen order."""
    return tuple(dict.fromkeys(_scan(raw_text)[0]))


def raw_money_leak(raw_text: str) -> bool:
    """True when `raw_text` renders a money amount (MONEY_RE), tokens,
    reference ids and dates excluded."""
    return _scan(raw_text)[1]


def _leaves(node: Any) -> Iterable[Any]:
    if isinstance(node, Mapping):
        for v in node.values():
            yield from _leaves(v)
    elif isinstance(node, (list, tuple, set, frozenset)):
        for v in node:
            yield from _leaves(v)
    else:
        yield node


def context_facts(context: Iterable[Any]) -> frozenset[Fact]:
    """Every fact in the tool context, over every string leaf. int/Decimal
    leaves and pure-numeric strings are COUNTs. COUNT and RATE are compared by
    numeric value, so a numeric fact is stored under both kinds."""
    out: set[Fact] = set()
    for leaf in _leaves(list(context)):
        if isinstance(leaf, bool) or leaf is None:
            continue
        if isinstance(leaf, (int, Decimal)):
            out.add(Fact(FactKind.COUNT, _num(str(leaf))))
        elif isinstance(leaf, str):
            if _NUMERIC_LEAF_RE.fullmatch(leaf):
                out.add(Fact(FactKind.COUNT, _num(leaf)))
            else:
                out.update(_scan(leaf)[0])
    for fact in [f for f in out if f.kind in _NUMERIC_KINDS]:
        out.update(Fact(k, fact.value) for k in _NUMERIC_KINDS)
    return frozenset(out)


# --- faithfulness -----------------------------------------------------------


@dataclass(frozen=True)
class Faithfulness:
    ratio: Ratio
    unsupported: tuple[Fact, ...]
    raw_money_leak: bool


def faithfulness_proxy(raw_answer: str, context: Iterable[Any]) -> Faithfulness:
    """Supported facts / facts in `raw_answer`. An invalid date is never
    supported, whatever the context says."""
    facts, leak = _scan(raw_answer)
    unique = tuple(dict.fromkeys(facts))
    ctx = context_facts(context)
    unsupported = tuple(
        f for f in unique if f.value.startswith(_INVALID) or f not in ctx
    )
    return Faithfulness(Ratio(len(unique) - len(unsupported), len(unique)), unsupported, leak)


# --- retrieval --------------------------------------------------------------


def context_precision_proxy(retrieved: Iterable[str], expected: Iterable[str]) -> Ratio:
    """|R & G| / |R| over sets. Empty R: 1/1 when G is empty too, else 0/1."""
    got, want = set(retrieved), set(expected)
    if not got:
        return Ratio(0, 1) if want else Ratio(1, 1)
    return Ratio(len(got & want), len(got))


def context_recall(retrieved: Iterable[str], expected: Iterable[str]) -> Ratio:
    """|R & G| / |G|; empty G is vacuously 1/1."""
    got, want = set(retrieved), set(expected)
    if not want:
        return Ratio(1, 1)
    return Ratio(len(got & want), len(want))


def average_precision_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> Decimal:
    """(1/min(k,|G|)) * sum P@i * rel(i) over the first k distinct ranked items.
    Empty G -> 1."""
    if k < 1:
        raise ValueError("k must be >= 1")
    want = set(relevant)
    if not want:
        return _q(_ONE)
    hits = 0
    total = Decimal(0)
    for i, item in enumerate(list(dict.fromkeys(ranked))[:k], start=1):
        if item in want:
            hits += 1
            total += Decimal(hits) / Decimal(i)
    return _q(total / Decimal(min(k, len(want))))


# --- trace helpers ----------------------------------------------------------


def query_loans_ref_ids(events: Iterable[TraceEvent]) -> tuple[str, ...]:
    """Reference ids every `query_loans` observation returned, in order, unique."""
    out: list[str] = []
    for e in events:
        if e.kind is TraceKind.OBSERVATION and e.tool == "query_loans" and e.payload:
            ids = e.payload.get("ref_ids")
            if isinstance(ids, list):
                out.extend(i for i in ids if isinstance(i, str))
    return tuple(dict.fromkeys(out))


def raw_answer(completions: Sequence[Completion]) -> str | None:
    """The model's final text: the last completion, when it asked for no tool."""
    if not completions:
        return None
    last = completions[-1]
    return last.content if last.content and not last.tool_calls else None


def turn_context(events: Iterable[TraceEvent]) -> tuple[Mapping[str, Any], ...]:
    """This turn's OBSERVATION and PROPOSAL payloads (R3)."""
    return tuple(
        e.payload
        for e in events
        if e.kind in (TraceKind.OBSERVATION, TraceKind.PROPOSAL) and e.payload is not None
    )


@dataclass(frozen=True)
class ToolCallView:
    name: str
    args: Mapping[str, Any]


def tool_calls(events: Iterable[TraceEvent]) -> tuple[ToolCallView, ...]:
    """ACTION events as (tool, parsed arguments); bad JSON or a non-object -> {}."""
    out: list[ToolCallView] = []
    for e in events:
        if e.kind is not TraceKind.ACTION or e.tool is None:
            continue
        try:
            args = json.loads(e.text)
        except ValueError:
            args = {}
        out.append(ToolCallView(e.tool, args if isinstance(args, dict) else {}))
    return tuple(out)


# --- trace relevancy --------------------------------------------------------

ENTITY_ARG_KEYS = ("borrower_group", "depositor_group", "borrower_name", "depositor_name", "ref_id")
PERIOD_ARG_KEYS = ("months", "due_period", "period", "new_due_date")
_RESOLVE_TOOL = "resolve_entity"


@dataclass(frozen=True)
class Focus:
    """What the user asked about. `ambiguous` non-empty means the right move
    was to ask, so any entity argument in a non-resolve call is wrong (R5)."""

    entity: str | None
    ambiguous: tuple[str, ...] = ()
    metric: str | None = None
    metric_args: Mapping[str, Any] = field(default_factory=dict)
    period: bool = False


@dataclass(frozen=True)
class TraceRelevancy:
    entity_match: bool
    wrong_entity: bool
    metric_match: bool
    period_match: bool
    capability_gap: bool


def _norm(value: Any) -> str | None:
    return value.strip().lower() if isinstance(value, str) and value.strip() else None


def trace_relevancy_proxy(
    calls: Sequence[ToolCallView],
    focus: Focus,
    *,
    faithfulness: Faithfulness | None = None,
) -> TraceRelevancy:
    """`capability_gap`: the asked metric was never called AND the answer
    stated facts no tool supplied (or faithfulness was not given)."""
    used = [
        (c.name, n) for c in calls for k in ENTITY_ARG_KEYS if (n := _norm(c.args.get(k)))
    ]
    acted_on = [n for name, n in used if name != _RESOLVE_TOOL]
    target = _norm(focus.entity)
    entity_match = target is None or any(n == target for _, n in used)
    if focus.ambiguous:
        wrong_entity = bool(acted_on)
    else:
        wrong_entity = target is not None and any(n != target for n in acted_on)
    metric_match = focus.metric is None or any(
        c.name == focus.metric and all(c.args.get(k) == v for k, v in focus.metric_args.items())
        for c in calls
    )
    period_match = not focus.period or any(
        c.args.get(k) not in (None, "") for c in calls for k in PERIOD_ARG_KEYS
    )
    capability_gap = not metric_match and (faithfulness is None or bool(faithfulness.unsupported))
    return TraceRelevancy(entity_match, wrong_entity, metric_match, period_match, capability_gap)


# --- production -------------------------------------------------------------


def production_scores(
    events: Sequence[TraceEvent], completions: Sequence[Completion]
) -> dict[str, Any] | None:
    """The `agent_turns.eval_scores` payload; None when the turn has no raw
    answer. No floats; `unsupported_kinds` are kind names only (R8)."""
    answer = raw_answer(completions)
    if answer is None:
        return None
    f = faithfulness_proxy(answer, turn_context(events))
    return {
        "grounding_version": GROUNDING_VERSION,
        "faithfulness_proxy": f.ratio.text,
        "facts_total": f.ratio.total,
        "facts_unsupported": len(f.unsupported),
        "unsupported_kinds": sorted({u.kind.value for u in f.unsupported}),
        "raw_money_leak": f.raw_money_leak,
        "context_precision_proxy": None,
        "trace_relevancy_proxy": None,
    }
