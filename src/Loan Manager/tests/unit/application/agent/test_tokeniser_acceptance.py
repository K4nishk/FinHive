"""KCH-238R acceptance suite (plan §6 A-G), written BEFORE the redesign and
run against the cycle-2 tokeniser first (fail-first evidence: R1, R2, F1,
F3).

The leak oracle here is deliberately independent of the code under test: it
never imports `entity_index` or any tokeniser helper. It folds text its own
way (NFKC, drop format chars, casefold, drop EVERY combining mark on both
sides) and splits it into Latin/digit runs and other-script runs with one
regex. A stored name is "in clear" when:
  - its runs appear as consecutive output runs, whatever separates them
    (separator-blind), or
  - one of its words (>= 3 chars at ingress; >= 4 and not a safe word in
    system text) appears as a whole output run, or as a run minus an Indian
    honorific suffix.
Token-shaped spans are blanked before the check.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import time
import unicodedata
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import pytest
from loan_manager.application.agent import tokeniser as tk
from loan_manager.application.agent.safe_words import SAFE_WORDS
from loan_manager.application.agent.tool_registry import ToolMode, parse_args, tool_schemas
from loan_manager.application.agent.tools.observations import ErrorCode, error
from loan_manager.application.agent.tools.propose_tools import build_propose_registry
from loan_manager.application.agent.tools.read_tools import build_read_registry
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.build_entity_resolver import BuildEntityResolver
from loan_manager.application.use_cases.loans.get_autocomplete import GetAutocompleteValues
from loan_manager.domain.services.entity_resolver import NAME_FIELDS, EntityResolver
from loan_manager.infrastructure.llm.request_body import build_request_body
from loan_manager.infrastructure.llm.settings import LLMSettings
from loan_manager.infrastructure.seed.demo_fixture import DEMO_LOANS, FIXTURE_TODAY

from . import tokeniser_reproducers as rp
from .conftest import make_loan, uow_factory_for

# ── universes ──────────────────────────────────────────────────────────────


def _demo_values() -> dict[str, list[str]]:
    """Every DEMO loan, paid-off included -- the universe the review probes
    (`common.py`) ran the ingress reproducers against."""
    values: dict[str, list[str]] = {f: [] for f in NAME_FIELDS}
    for fl in DEMO_LOANS:
        for f in NAME_FIELDS:
            v = getattr(fl, f)
            if v:
                values[f].append(v)
    return values


def _r4_f1_values() -> dict[str, list[str]]:
    values: dict[str, list[str]] = {f: [] for f in NAME_FIELDS}
    for row in rp.R4_F1_ROWS:
        for f, v in zip(NAME_FIELDS, row, strict=True):
            values[f].append(v)
    return values


UNIVERSES: dict[str, Callable[[], dict[str, list[str]]]] = {
    "DEMO": _demo_values,
    "P5": lambda: rp.P5_UNIVERSE,
    "IYER": lambda: rp.IYER_UNIVERSE,
    "R4_F1": _r4_f1_values,
    "V": lambda: rp.V_UNIVERSE,
    "V2": lambda: rp.V2_UNIVERSE,
    "V3": lambda: rp.V3_UNIVERSE,
    "V4": lambda: rp.V4_UNIVERSE,
    "BIG": lambda: rp.BIG_UNIVERSE,
}

_RESOLVERS: dict[str, EntityResolver] = {}


def _resolver(name: str) -> EntityResolver:
    if name not in _RESOLVERS:
        _RESOLVERS[name] = EntityResolver(UNIVERSES[name]())
    return _RESOLVERS[name]


def _entries(name: str) -> list[tuple[str, str]]:
    return [(f, v) for f, vs in UNIVERSES[name]().items() for v in vs]


# ── independent leak oracle ────────────────────────────────────────────────

_TOKEN_SHAPE = re.compile(r"(?:[BDGQN][0-9]{3}|AMOUNT_[0-9]+)")
_ORACLE_RUN = re.compile(r"[a-z0-9]+|[^\W_a-z0-9]+")
_ORACLE_SUFFIXES = (
    "bhaiya", "bhai", "behen", "ben", "didi", "jee", "ji", "sahab", "saheb", "sahib",
    "saab", "s", "जी", "भाई",
)
_ORACLE_NOISE = frozenset({"group", "grp", "family", "the", "co", "and"})
_GROUP_FIELDS = ("borrower_group", "depositor_group")


def _oracle_fold(text: str) -> str:
    text = _TOKEN_SHAPE.sub(" \x00 ", text)
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    text = unicodedata.normalize("NFD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.category(ch).startswith("M"))


def _oracle_runs(text: str) -> list[str]:
    """Runs, with "\x00" standing in for a token (a hard break)."""
    return [m.group(0) for m in re.finditer(r"\x00|" + _ORACLE_RUN.pattern, _oracle_fold(text))]


def _safe_fold(word: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFD", word)
        if not unicodedata.category(ch).startswith("M")
    )


_SAFE_FOLDED = frozenset(_safe_fold(w) for w in SAFE_WORDS)


class Oracle:
    def __init__(self, entries: list[tuple[str, str]]) -> None:
        self.wholes = {"".join(r for r in _oracle_runs(v) if r != "\x00") for _f, v in entries}
        by_word: dict[str, set[str]] = {}
        for f, v in entries:
            for w in _oracle_runs(v):
                by_word.setdefault(w, set()).add(f)
        self.ingress_words: set[str] = set()
        self.system_words: set[str] = set()
        for w, fields in by_word.items():
            if len(w) < 3 or w.isdigit() or w in _ORACLE_NOISE:
                continue
            weak = w in _SAFE_FOLDED and fields <= set(_GROUP_FIELDS)
            if not weak:
                self.ingress_words.add(w)
            if len(w) >= 4 and w not in _SAFE_FOLDED:
                self.system_words.add(w)
        self.max_whole = max((len(k) for k in self.wholes), default=0)

    def leaks(self, text: str, *, system: bool = False) -> list[str]:
        runs = _oracle_runs(text)
        found: list[str] = []
        for i in range(len(runs)):
            acc = ""
            for j in range(i, len(runs)):
                if runs[j] == "\x00":
                    break
                acc += runs[j]
                if len(acc) > self.max_whole:
                    break
                if acc in self.wholes:
                    found.append(acc)
        words = self.system_words if system else self.ingress_words
        for r in runs:
            if r in words:
                found.append(r)
                continue
            for suf in _ORACLE_SUFFIXES:
                if r.endswith(suf) and r[: -len(suf)] in words:
                    found.append(r)
                    break
        return found


_ORACLES: dict[str, Oracle] = {}


def _oracle(name: str) -> Oracle:
    if name not in _ORACLES:
        _ORACLES[name] = Oracle(_entries(name))
    return _ORACLES[name]


def _guard_text(text: str, tm) -> None:
    tk.assert_no_plaintext({"messages": [{"role": "user", "content": text}]}, tm)


def _check_ingress(universe: str, prompt: str):
    tm = tk.TokenMap(_resolver(universe))
    out = tm.tokenise_prompt(prompt)
    assert _oracle(universe).leaks(out) == [], f"{prompt!r} -> {out!r}"
    _guard_text(out, tm)
    return out, tm


# ── A. reproducer corpus ───────────────────────────────────────────────────

_DEMO_CORPUS = (
    rp.PROBE1_PROMPTS + rp.PROBE4_PROMPTS + rp.A1_PROMPTS + rp.A2_PROMPTS + rp.P6_PROMPTS
    + rp.CODE_PROMPTS + rp.A10_PROMPTS + rp.R4_F2_PROMPTS + [rp.PROSE]
)


@pytest.mark.parametrize("prompt", _DEMO_CORPUS)
def test_a_demo_corpus_leaves_no_stored_name_in_clear(prompt: str) -> None:
    _check_ingress("DEMO", prompt)


@pytest.mark.parametrize(
    ("universe", "prompt"),
    [("P5", p) for p in rp.P5_PROMPTS]
    + [("R4_F1", p) for p in rp.R4_F1_PROMPTS]
    + [("V", p) for p in rp.V_PROMPTS]
    + [("V2", p) for p in rp.V2_PROMPTS]
    + [("V3", p) for p in rp.V3_PROMPTS]
    + [("V4", p) for p in rp.V4_PROMPTS]
    + [("IYER", "how much does iyer owe"), ("BIG", rp.BIG_PROSE)],
)
def test_a_other_universes_leave_no_stored_name_in_clear(universe: str, prompt: str) -> None:
    _check_ingress(universe, prompt)


@pytest.mark.parametrize(("universe", "prompt", "expected"), rp.PINNED)
def test_a_pinned_ingress_output(universe: str, prompt: str, expected: str) -> None:
    out, _ = _check_ingress(universe, prompt)
    assert out == expected


def test_r1_stored_name_ending_in_ji_is_one_exact_borrower_at_ingress() -> None:
    tm = tk.TokenMap(_resolver("R4_F1"))
    assert tm.tokenise_prompt("azim premji") == "B001"
    assert tm.value_of("B001") == "azim premji"
    assert tm.tokenise_prompt("rameshbhai patel") == "B002"
    assert tm.value_of("B002") == "rameshbhai patel"


@pytest.mark.parametrize("text", rp.R4_F1_EGRESS_TEXTS)
def test_r1_egress_free_text_scrubs_stored_names_ending_in_honorifics(text: str) -> None:
    tm = tk.TokenMap(_resolver("R4_F1"))
    tm.tokenise_prompt("hello")
    out = tm.tokenise_observation({"message": text})["message"]
    assert _oracle("R4_F1").leaks(out, system=True) == [], f"{text!r} -> {out!r}"
    _guard_text(out, tm)


def test_r1_guard_sees_a_stored_ji_name_split_by_a_hyphen() -> None:
    tm = tk.TokenMap(_resolver("R4_F1"))
    with pytest.raises(tk.PlaintextLeakError):
        _guard_text("azim prem-ji owes", tm)
    with pytest.raises(tk.PlaintextLeakError):
        _guard_text("ramesh-bhai patel owes", tm)


def test_r2_iyer_chem_typed_with_a_space_is_the_stored_group_token() -> None:
    tm = tk.TokenMap(_resolver("V4"))
    assert tm.tokenise_prompt("iyer chem") == "G001"
    assert tm.value_of("G001") == "iyerchem"


def test_r2_guard_sees_an_unseparated_stored_value_typed_with_a_space() -> None:
    tm = tk.TokenMap(_resolver("V4"))
    with pytest.raises(tk.PlaintextLeakError):
        _guard_text("ask about iyer chem today", tm)


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        # review 1 M1 ruling: a peeled hit is a Q of the full typed text
        ("anil sharmaji", "Q001"),
        ("Sharmaji", "Q001"),
        ("Guptaji ko 5000 do", "Q001 ko AMOUNT_1 do"),
        ("naveen raoji", "Q001"),
        # a Devanagari suffix is a separate run (script change): whole name
        # exact, not a peel
        ("anil sharmaजी", "B001-जी"),
    ],
)
def test_f1_glued_honorific_never_leaves_the_surname_in_clear(prompt: str, expected: str) -> None:
    out, _ = _check_ingress("DEMO", prompt)
    assert out == expected


def test_f1_guard_sees_a_glued_honorific_on_a_stored_surname() -> None:
    tm = tk.TokenMap(_resolver("DEMO"))
    with pytest.raises(tk.PlaintextLeakError):
        _guard_text("ask Sharmaji to confirm", tm)


@pytest.mark.parametrize("prompt", rp.A7_STAY_PLAIN)
def test_a_false_positive_list_stays_plain(prompt: str) -> None:
    out, _ = _check_ingress("DEMO", prompt)
    assert out == prompt


@pytest.mark.parametrize(("prompt", "expected"), rp.ACCEPTED_OVER_TOKENISING)
def test_a_accepted_over_tokenising_is_pinned(prompt: str, expected: str) -> None:
    out, _ = _check_ingress("DEMO", prompt)
    assert out == expected


@pytest.mark.parametrize("prompt", rp.TYPED_TOKEN_PROMPTS)
def test_a_typed_token_literal_is_rejected(prompt: str) -> None:
    with pytest.raises(tk.UnknownTokenError):
        tk.TokenMap(_resolver("DEMO")).tokenise_prompt(prompt)


def test_a_novel_name_is_an_n_token_that_detokenises_to_the_typed_text() -> None:
    tm = tk.TokenMap(_resolver("DEMO"))
    out = tm.tokenise_prompt("create a loan for Rohan Kapadia, 2 lakh")
    assert out == "create a loan for N001, AMOUNT_1"
    assert tm.value_of("N001") == "Rohan Kapadia"
    args = tm.detokenise_args(json.dumps({"borrower_name": "N001", "amount": "AMOUNT_1"}))
    assert args == {"borrower_name": "Rohan Kapadia", "amount": 200000}
    # later mention of the same novel name reuses the token, any casing
    assert tm.tokenise_prompt("is rohan kapadia ok?") == "is N001 ok?"
    with pytest.raises(tk.PlaintextLeakError):
        _guard_text("Rohan Kapadia will pay", tm)


@pytest.mark.parametrize("prompt", rp.A10_PROMPTS)
@pytest.mark.parametrize("later", rp.A10_LATER_BODIES)
def test_a_year_shaped_amount_never_bricks_a_later_date(prompt: str, later: str) -> None:
    tm = tk.TokenMap(_resolver("DEMO"))
    user = tm.tokenise_prompt(prompt)
    tk.assert_no_plaintext(
        {"messages": [{"role": "user", "content": user}, {"role": "tool", "content": later}]}, tm
    )


def test_a_year_shaped_amount_does_not_corrupt_dates_in_egress_text() -> None:
    tm = tk.TokenMap(_resolver("DEMO"))
    tm.tokenise_prompt("Q2 2026")
    out = tm.tokenise_observation(
        {"message": "no loans due after 2026-09-25", "next_action": "retry in FY2026-27"}
    )
    assert out == {"message": "no loans due after 2026-09-25", "next_action": "retry in FY2026-27"}


def test_a_protected_set_covers_inactive_and_pending_report_names() -> None:
    """D3: names of inactive loans and of pending reports are protected
    (tokenised, guarded) though the resolver stays active-only."""
    from loan_manager.application.use_cases.loans.get_protected_names import GetProtectedNames
    from loan_manager.application.use_cases.reports.get_reports import GetPendingReports

    active = make_loan(borrower_name="anil sharma", borrower_group="sharma group",
                       depositor_name="meera iyer", depositor_group="dg1")
    inactive = make_loan(borrower_name="old kumar", borrower_group="kumar family",
                         depositor_name="gone mehra", depositor_group="dg2", is_active=False)
    reports: list = []
    uf = uow_factory_for([active, inactive], reports)
    create = build_propose_registry(uf, FixedClock(date(2026, 6, 1)), EventBus(),
                                    user_request="new loan").handler("create_loan")
    obs = create(parse_args("create_loan", {
        "borrower_name": "Pending Pandit", "borrower_group": "sharma group",
        "depositor_name": "meera iyer", "amount": 150000,
    }))
    assert obs["ok"] is True

    get_autocomplete = GetAutocompleteValues(uf)
    resolver = BuildEntityResolver(get_autocomplete).execute()
    protected = GetProtectedNames(get_autocomplete, GetPendingReports(uf)).execute()
    assert "old kumar" in protected["borrower_name"]
    assert "pending pandit" in protected["borrower_name"]
    assert resolver.resolve("old kumar").status == "no_match"  # resolver stays active-only

    tm = tk.TokenMap(resolver, protected=protected)
    out = tm.tokenise_prompt("did old kumar or pending pandit or gone mehra pay?")
    assert out == "did Q001 or Q002 or Q003 pay?"
    for leak in ("old kumar paid", "pending-pandit", "gone mehra"):
        with pytest.raises(tk.PlaintextLeakError):
            _guard_text(leak, tm)


# ── B. variant fuzz ────────────────────────────────────────────────────────


def _fullwidth(s: str) -> str:
    return "".join(
        "　" if c == " " else chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in s
    )


_VARIANTS: list[tuple[str, Callable[[str], str]]] = [
    ("as-is", lambda v: v),
    ("upper", str.upper),
    ("title", str.title),
    ("possessive", lambda v: v + "'s loan"),
    ("curly-possessive", lambda v: v + "’s loan"),
    ("modifier-apostrophe", lambda v: v + "ʼs loan"),
    ("fullwidth", _fullwidth),
    ("zwsp-in-word", lambda v: v[:1] + "​" + v[1:]),
    ("nbsp", lambda v: v.replace(" ", " ")),
    ("glued", lambda v: v.replace(" ", "")),
    ("hyphen", lambda v: v.replace(" ", "-")),
    ("underscore", lambda v: v.replace(" ", "_") + "_loans"),
    ("dot", lambda v: v.replace(" ", ".")),
    ("quoted", lambda v: f'"{v}"'),
    ("parens", lambda v: f"({v})?!"),
    ("glued-ji", lambda v: v + "ji ko do"),
    ("hyphen-ji", lambda v: v + "-ji"),
    ("space-ji", lambda v: v + " ji"),
    ("title-prefix", lambda v: "Mr. " + v),
    ("accent", lambda v: v[:1] + "́" + v[1:]),
    ("dotted-capital-i", lambda v: v.upper().replace("I", "İ")),
    ("tab-newline", lambda v: v.replace(" ", "\t\n")),
    ("in-sentence", lambda v: f"how much does {v} owe, and since when?"),
]


def _fuzz_cases() -> Iterator[tuple[str, str, str]]:
    for universe in ("DEMO", "P5", "R4_F1", "IYER", "V2", "V4"):
        for _f, value in _entries(universe):
            for label, _fn in _VARIANTS:
                yield universe, value, label


@pytest.mark.parametrize(("universe", "value", "variant"), list(_fuzz_cases()))
def test_b_every_stored_value_variant_leaves_nothing_in_clear(
    universe: str, value: str, variant: str
) -> None:
    prompt = dict(_VARIANTS)[variant](value)
    _check_ingress(universe, prompt)


# ── C. egress ──────────────────────────────────────────────────────────────


def _demo_loans() -> list:
    return [
        make_loan(
            borrower_name=f.borrower_name, borrower_group=f.borrower_group,
            depositor_name=f.depositor_name, depositor_group=f.depositor_group,
            amount=f.amount, giving_date=f.giving_date, due_date=f.due_date,
        )
        for f in DEMO_LOANS
        if f.paidoff_date is None
    ]


def _leaves(obj, key=None):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _leaves(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from _leaves(v, key)
    else:
        yield key, obj


_MONEY_INT_KEYS = frozenset(
    {"amount", "total_amount", "exposure", "total_exposure", "principal", "interest",
     "total_interest"}
)


def _raw_amount_renderings(obs) -> set[str]:
    """Money-shaped raw leaves of an untokenised observation, >= 4 digits."""
    out: set[str] = set()
    for k, v in _leaves(obs):
        if k in ("rate_percent", "score"):
            continue
        money_str = isinstance(v, str) and re.fullmatch(r"\d+\.\d\d", v)
        money_int = isinstance(v, int) and not isinstance(v, bool) and k in _MONEY_INT_KEYS
        if money_str or money_int:
            q = Decimal(str(v)).quantize(Decimal("0.01"))
            for r in (f"{q:f}", str(int(q)) if q == q.to_integral_value() else None):
                if r and len(r.replace(".", "")) >= 4:
                    out.add(r)
    return out


def _egress_leaks(oracle: Oracle, raw_obs, tokenised) -> list[str]:
    s = json.dumps(tokenised, ensure_ascii=False)
    found = oracle.leaks(s, system=True)
    for r in _raw_amount_renderings(raw_obs):
        # "/1200" is the interest formula's divisor, never an amount (NM3)
        if re.search(r"(?<![\d./])" + re.escape(r) + r"(?![\d])", s):
            found.append(r)
    return found


def _read_setup():
    loans = _demo_loans()
    undated = make_loan(borrower_name="undated guy", borrower_group="nodate grp",
                        depositor_name="dx", depositor_group="dg", amount=40000,
                        giving_date=date(2026, 1, 1), due_date=None)
    loans.append(undated)
    uf = uow_factory_for(loans)
    reg = build_read_registry(uf, FixedClock(FIXTURE_TODAY))
    resolver = BuildEntityResolver(GetAutocompleteValues(uf)).execute()
    oracle = Oracle([(f, v) for f, v in resolver.entities()])
    return loans, reg, resolver, oracle


def _sweep_calls(loans) -> list[tuple[str, dict]]:
    calls: list[tuple[str, dict]] = [
        ("resolve_entity", {"text": t}) for t in rp.SWEEP_RESOLVE_TEXTS
    ]
    calls += [("query_loans", {"status": s}) for s in rp.SWEEP_STATUSES]
    calls += [("query_loans", {"status": "overdue", "borrower_group": g})
              for g in rp.SWEEP_GROUP_FILTERS]
    calls += [("get_portfolio_summary", {"limit": 50}), ("format_inr", {"amount": "250000"})]
    refs = sorted(str(loan.reference_id) for loan in loans)
    calls += [("calculate_interest", {"ref_id": r, "rate": 12, "months": 3}) for r in refs[:40]]
    return calls


@pytest.mark.parametrize("mode", ["fresh", "shared"])
def test_c_read_sweep_has_no_leak_and_no_guard_raise(mode: str) -> None:
    loans, reg, resolver, oracle = _read_setup()
    calls = _sweep_calls(loans)
    # probe2's list (every active DEMO ref, not 40) plus the 10 p7 error calls
    assert len(calls) + len(rp.P7_CALLS) >= 53
    tm = tk.TokenMap(resolver)
    leaks: list = []
    for name, args in calls + rp.P7_CALLS:
        if mode == "fresh":
            tm = tk.TokenMap(resolver)
        obs = reg.handler(name)(parse_args(name, args))
        tok = tm.tokenise_observation(obs)
        leaks += [(name, args, x) for x in _egress_leaks(oracle, obs, tok)]
        tk.assert_no_plaintext(
            {"messages": [{"role": "tool", "content": json.dumps(tok, ensure_ascii=False)}]}, tm
        )
    assert leaks == []


@pytest.mark.parametrize("query", rp.R4_F1_RESOLVE_QUERIES)
def test_r1_resolve_entity_candidates_in_next_action_are_tokenised(query: str) -> None:
    loans = [
        make_loan(borrower_name=b, borrower_group=bg, depositor_name=d, depositor_group=dg,
                  amount=50000 + i * 1000, giving_date=date(2026, 1, 1), due_date=date(2026, 6, 1))
        for i, (b, bg, d, dg) in enumerate(rp.R4_F1_ROWS)
    ]
    uf = uow_factory_for(loans)
    reg = build_read_registry(uf, FixedClock(date(2026, 9, 25)))
    resolver = BuildEntityResolver(GetAutocompleteValues(uf)).execute()
    tm = tk.TokenMap(resolver)
    tm.tokenise_prompt(query)
    obs = reg.handler("resolve_entity")(parse_args("resolve_entity", {"text": query}))
    tok = tm.tokenise_observation(obs)
    oracle = Oracle(list(resolver.entities()))
    assert _egress_leaks(oracle, obs, tok) == [], json.dumps(tok, ensure_ascii=False)
    tk.assert_no_plaintext({"messages": [{"role": "tool", "content": json.dumps(tok)}]}, tm)


def _propose_sweep():
    loans = _demo_loans()
    undated = make_loan(borrower_name="undated guy", borrower_group="sharma group",
                        depositor_name="dx", depositor_group="dg1", amount=40000,
                        giving_date=date(2026, 1, 1), due_date=None)
    loans.append(undated)
    reports: list = []
    uf = uow_factory_for(loans, reports)
    reg = build_propose_registry(uf, FixedClock(FIXTURE_TODAY), EventBus(),
                                 user_request="sweep")
    dated = sorted((x for x in loans if x.due_date is not None and x.due_date < FIXTURE_TODAY),
                   key=lambda x: str(x.reference_id))
    a, b, c, d = (str(x.reference_id) for x in dated[:4])
    other_group = next(g for g in ("iyer chem", "gupta & sons") if g != dated[3].borrower_group)
    calls: list[tuple[str, dict]] = [
        ("extend_loan", {"ref_id": a, "months": 3, "rate": 12, "tds_flag": True}),
        ("extend_loan", {"ref_id": a, "months": 3, "rate": 12}),  # ALREADY_PENDING
        ("extend_loan", {"ref_id": "2099_01_001", "months": 3, "rate": 12}),  # REF_ID_NOT_FOUND
        ("extend_loan", {"ref_id": str(undated.reference_id), "months": 3, "rate": 12}),
        ("extend_loan", {"ref_id": str(undated.reference_id), "months": 3, "rate": 12,
                         "new_due_date": "2020-01-01"}),  # NEW_DUE_DATE_INVALID
        ("extend_loan", {"ref_id": b, "months": 3, "rate": 12,
                         "new_due_date": "2030-01-01"}),  # NEW_DUE_DATE_INVALID
        ("update_loan", {"ref_id": c, "amount": 175500}),
        ("update_loan", {"ref_id": d, "borrower_name": "sunita sharma",
                         "borrower_group": other_group}),  # GROUP_MISMATCH
        ("update_loan", {"ref_id": b, "borrower_name": dated[1].borrower_name.title()}),
        ("create_loan", {"borrower_name": "Rohan Kapadia", "borrower_group": "iyer chem",
                         "depositor_name": "meera iyer", "amount": 150000, "due_period": 6}),
        ("extend_overdue_batch", {"borrower_group": "sharma group", "months": 3, "rate": 12}),
        ("extend_overdue_batch", {"borrower_group": "sharma group", "months": 3, "rate": 12}),
        ("extend_overdue_batch", {"borrower_group": "zzz nowhere", "months": 3, "rate": 12}),
        ("extend_overdue_batch", {"borrower_group": "sharmaa group", "months": 3, "rate": 12}),
    ]
    resolver = BuildEntityResolver(GetAutocompleteValues(uf)).execute()
    observations = [(n, a_, reg.handler(n)(parse_args(n, a_))) for n, a_ in calls]
    observations.append(("synthetic", {}, error(
        ErrorCode.UNKNOWN_TOKEN, "the model used a token this conversation never issued",
        "ask the user to restate the name")))
    # KCH-239: the loop's own scrubbed validation error (field + rule names only).
    observations.append(("synthetic", {}, error(
        ErrorCode.INVALID_ARGS, "argument 'amount' failed rule 'greater_than_equal'",
        "fix the named arguments and call the tool again")))
    # KCH-246: the loop's own refusal of a PROPOSE call on a READ turn.
    observations.append(("synthetic", {}, error(
        ErrorCode.CHANGE_NOT_REQUESTED, "the user did not ask for a change in this question",
        "answer from reads; tell the user to ask for the change explicitly")))
    return resolver, observations


def test_c_propose_sweep_covers_every_error_code_with_no_leak() -> None:
    resolver, observations = _propose_sweep()
    seen = {obs["error"]["code"] for _n, _a, obs in observations if not obs["ok"]}
    assert seen == {c.value for c in ErrorCode} - {"UNSUPPORTED_STATUS"}
    tm = tk.TokenMap(resolver)
    tm.tokenise_prompt("create a loan for Rohan Kapadia")
    oracle = Oracle(list(resolver.entities()))
    for name, args, obs in observations:
        tok = tm.tokenise_observation(obs)
        assert _egress_leaks(oracle, obs, tok) == [], (name, args, tok)
        tk.assert_no_plaintext({"messages": [{"role": "tool", "content": json.dumps(tok)}]}, tm)


def test_c_every_propose_observation_key_is_classified() -> None:
    _resolver_, observations = _propose_sweep()
    keys = set()
    for _n, _a, obs in observations:
        stack = [obs]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                keys.update(node)
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    unclassified = sorted(k for k in keys if not tk.key_is_classified(k))
    assert unclassified == []


# ── D. conversation replay ─────────────────────────────────────────────────


def _settings() -> LLMSettings:
    return LLMSettings(base_url="https://openrouter.ai/api/v1", model="x",
                       api_key_env="OPENROUTER_API_KEY", temperature=0.1, max_steps=6,
                       timeout_s=60)


def _issued(tm, prefix: str) -> list[str]:
    out = []
    for n in range(1, 200):
        tok = f"{prefix}{n:03d}"
        try:
            tm.value_of(tok)
        except tk.UnknownTokenError:
            break
        out.append(tok)
    return out


def _replay(turn5: str, protected=None, *, guard_each: bool = True):
    loans = _demo_loans()
    uf = uow_factory_for(loans)
    reg = build_read_registry(uf, FixedClock(FIXTURE_TODAY))
    resolver = BuildEntityResolver(GetAutocompleteValues(uf)).execute()
    tm = tk.TokenMap(resolver, protected=protected) if protected else tk.TokenMap(resolver)
    tools = tool_schemas(frozenset({ToolMode.READ}))
    msgs: list[dict] = [{"role": "system", "content": rp.SYSTEM_PROMPT}]
    bodies: list[dict] = []
    raw_amounts: set[str] = set()
    false_raises: list[str] = []
    guard_ms: list[float] = []
    ids = [0]

    def check() -> None:
        body = build_request_body(_settings(), msgs, tools)
        bodies.append(body)
        if not guard_each:
            return
        t = time.perf_counter()
        try:
            tk.assert_no_plaintext(body, tm)
        except tk.PlaintextLeakError as exc:
            false_raises.append(str(exc)[:120])
        guard_ms.append((time.perf_counter() - t) * 1000)

    def tool(name: str, args: dict) -> dict:
        ids[0] += 1
        cid = f"call_{ids[0]}"
        raw = json.dumps(args)
        msgs.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": cid, "type": "function", "function": {"name": name, "arguments": raw}}]})
        obs = reg.handler(name)(parse_args(name, tm.detokenise_args(raw)))
        raw_amounts.update(_raw_amount_renderings(obs))
        tok = tm.tokenise_observation(obs)
        msgs.append({"role": "tool", "tool_call_id": cid, "name": name,
                     "content": json.dumps(tok, ensure_ascii=False)})
        check()
        return tok

    def user(text: str) -> None:
        msgs.append({"role": "user", "content": tm.tokenise_prompt(text)})
        check()

    def say(text: str) -> None:
        msgs.append({"role": "assistant", "content": text})
        check()

    refs = sorted(str(x.reference_id) for x in loans)
    turns = list(rp.A9_USER_TURNS)
    turns[3] = turns[3].format(ref3=refs[3], ref7=refs[7])
    turns[4] = turn5
    texts = rp.A9_ASSISTANT_TEXTS
    user(turns[0])
    tool("get_current_context", {})
    say(texts[0])
    user(turns[1])
    group = _issued(tm, "G")[0]
    tool("query_loans", {"status": "overdue", "borrower_group": group})
    say(texts[1].format(group=group, amount="AMOUNT_1"))
    user(turns[2])
    tool("get_portfolio_summary", {"limit": 5})
    say(texts[2].format(borrower="B001", amount="AMOUNT_2"))
    user(turns[3])
    t1 = tool("calculate_interest", {"ref_id": refs[3], "rate": 12, "months": 3})
    t2 = tool("calculate_interest", {"ref_id": refs[7], "rate": "14.5", "months": 6})
    tool("format_inr", {"amount": t1["interest"]})
    say(texts[3].format(ref3=refs[3], ref7=refs[7], i1=t1["interest"], i2=t2["interest"]))
    user(turns[4])
    mention = _issued(tm, "Q")[-1]
    tool("resolve_entity", {"text": mention})
    say(texts[4].format(mention=mention))
    user(turns[5])
    for status in ("overdue", "active", "pending"):
        tool("query_loans", {"status": status})
    say(texts[5])
    for t in ("Q001", "G001", "B001", "D001"):
        if t in _issued(tm, t[0]):
            tool("resolve_entity", {"text": t})
    tool("get_portfolio_summary", {"limit": 50})
    tool("format_inr", {"amount": "AMOUNT_1"})
    for r in refs[:40]:
        tool("calculate_interest", {"ref_id": r, "rate": 12, "months": 3})
    say("Done.")
    return tm, bodies, raw_amounts, false_raises, guard_ms, resolver


def _body_leaks(bodies, raw_amounts, oracle: Oracle) -> set[str]:
    found: set[str] = set()
    for body in bodies:
        s = json.dumps(body["messages"], ensure_ascii=False)
        found.update(oracle.leaks(s, system=True))
        for r in raw_amounts:
            if re.search(r"(?<![\d./])" + re.escape(r) + r"(?![\d])", s):
                found.add(r)
    return found


@pytest.mark.parametrize("variant", ["a9_q2_2026", "a9b_this_quarter"])
@pytest.mark.parametrize("scale", ["demo", "1200"])
def test_d_conversation_replay_has_no_false_raise_and_no_leak(variant: str, scale: str) -> None:
    turn5 = rp.A9_USER_TURNS[4] if variant == "a9_q2_2026" else rp.A9B_TURN_5
    protected = rp.BIG_UNIVERSE if scale == "1200" else None
    tm, bodies, raw_amounts, false_raises, _ms, resolver = _replay(turn5, protected)
    assert len(bodies) >= 55
    assert false_raises == []
    entries = list(resolver.entities())
    if protected:
        entries += [(f, v) for f, vs in protected.items() for v in vs]
    assert _body_leaks(bodies, raw_amounts, Oracle(entries)) == set()


# ── E. properties ──────────────────────────────────────────────────────────


def _differential_windows(universe: str) -> list[str]:
    windows: list[str] = []
    for _f, v in _entries(universe):
        words = v.split()
        windows += [v, v.upper(), v.replace(" ", ""), v.replace(" ", "-"), v.replace(" ", "_")]
        windows += words
        windows += [" ".join(words[i : i + 2]) for i in range(len(words) - 1)]
        windows += [v + " group", v[:-1], v + v[-1]]
    return [w for w in dict.fromkeys(windows) if w.strip() and not re.search(r"\d{4}", w)]


@pytest.mark.parametrize("universe", ["DEMO", "R4_F1", "P5", "V3", "V4"])
def test_e_exactness_agrees_with_the_resolver(universe: str) -> None:
    resolver = _resolver(universe)
    windows = _differential_windows(universe)
    assert len(windows) >= 10
    for w in windows:
        res = resolver.resolve(w)
        tm = tk.TokenMap(resolver)
        out = tm.tokenise_prompt(w)
        single = re.fullmatch(r"[BDG][0-9]{3}", out)
        if res.exact:
            assert single, (w, out)
            assert tm.value_of(out) == res.top.value, (w, out)
        else:
            assert not single, (w, out, res.status)


def _corpus_outputs() -> Iterator[tuple[str, str, object]]:
    for prompt in _DEMO_CORPUS:
        tm = tk.TokenMap(_resolver("DEMO"))
        yield prompt, tm.tokenise_prompt(prompt), tm
    for p in rp.R4_F1_PROMPTS:
        tm = tk.TokenMap(_resolver("R4_F1"))
        yield p, tm.tokenise_prompt(p), tm


def test_e_every_emitted_token_is_found_by_token_re_and_rehydrates() -> None:
    for prompt, out, tm in _corpus_outputs():
        shaped = _TOKEN_SHAPE.findall(out)
        assert tk.TOKEN_RE.findall(out) == shaped, (prompt, out)
        for token in shaped:
            tm.value_of(token)  # raises if not issued
        assert _TOKEN_SHAPE.search(tm.rehydrate(out)) is None, (prompt, out)


def test_e_guard_never_raises_on_tokenised_output() -> None:
    for _prompt, out, tm in _corpus_outputs():
        _guard_text(out, tm)


def test_e_q_and_n_rehydrate_to_what_the_user_typed() -> None:
    tm = tk.TokenMap(_resolver("DEMO"))
    out = tm.tokenise_prompt("did Sharmaa pay Rohan Kapadia?")
    assert out == "did Q001 pay N001?"
    assert tm.rehydrate(out) == "did Sharmaa pay Rohan Kapadia?"


# ── F. performance ─────────────────────────────────────────────────────────


@contextmanager
def _tracing_suspended() -> Iterator[None]:
    """Timing must not measure a coverage/debug tracer: suspend
    `sys.settrace` and, on 3.12+, every active `sys.monitoring` tool's
    global events, restoring both afterwards."""
    old = sys.gettrace()
    sys.settrace(None)
    monitoring = getattr(sys, "monitoring", None)
    saved: list[tuple[int, int]] = []
    if monitoring is not None:  # pragma: no cover - Python 3.12+
        for tool_id in range(6):
            if monitoring.get_tool(tool_id) is not None:
                saved.append((tool_id, monitoring.get_events(tool_id)))
                monitoring.set_events(tool_id, 0)
    try:
        yield
    finally:
        for tool_id, events in saved:  # pragma: no cover - Python 3.12+
            monitoring.set_events(tool_id, events)
        sys.settrace(old)


def _median_ms(fn: Callable[[], object], runs: int = 5, budget_ms: float | None = None) -> float:
    times: list[float] = []
    with _tracing_suspended():
        for _ in range(runs):
            t = time.perf_counter()
            fn()
            times.append((time.perf_counter() - t) * 1000)
            if budget_ms is not None and times[-1] > 20 * budget_ms:
                break  # hopeless; do not burn minutes repeating it
    return statistics.median(times)


def _tokenise_ms(universe: str, prompt: str) -> float:
    resolver = _resolver(universe)
    maps = [tk.TokenMap(resolver) for _ in range(5)]
    it = iter(maps)
    return _median_ms(lambda: next(it).tokenise_prompt(prompt), budget_ms=100)


def test_f3_distinct_prose_is_tokenised_under_100ms_on_demo() -> None:
    assert len(rp.PROSE) >= 2000
    assert _tokenise_ms("DEMO", rp.PROSE) < 100


def test_f3_distinct_prose_is_tokenised_under_100ms_at_1200_names() -> None:
    assert len(rp.BIG_PROSE) >= 2000
    assert len(rp.BIG_NAMES) == 1200
    assert _tokenise_ms("BIG", rp.BIG_PROSE) < 100


_PATHOLOGICAL: dict[str, str] = {
    "names-only": ("anil sharma " * 170)[:2000],
    "big-names-only": (" ".join(rp.BIG_NAMES))[:2000],
    "no-space": "a" * 2000,
    "punct": ",;/" * 667,
    "digits": "1" * 2000,
    "sep-glued": ("b1," * 667)[:2000],
    "devanagari": ("शर्मा " * 334)[:2000],
    "apostrophes": "o'" * 1000,
    "novel-words": " ".join(
        f"zq{a}{b}x" for a in "abcdefghijklmnopqrst" for b in "abcdefghijklmnopqrst"
    )[:2000],
}


@pytest.mark.parametrize("label", list(_PATHOLOGICAL))
@pytest.mark.parametrize("universe", ["DEMO", "BIG"])
def test_f3_pathological_inputs_stay_under_100ms(label: str, universe: str) -> None:
    assert _tokenise_ms(universe, _PATHOLOGICAL[label]) < 100


def test_f3_index_build_is_under_100ms_at_1200_names() -> None:
    resolver = _resolver("BIG")
    assert _median_ms(lambda: tk.TokenMap(resolver), budget_ms=100) < 100


@pytest.mark.parametrize("scale", ["demo", "1200"])
def test_f3_guard_replay_under_50ms_and_under_10ms_per_new_message(scale: str) -> None:
    protected = rp.BIG_UNIVERSE if scale == "1200" else None
    tm, bodies, _raw, false_raises, _ms, _r = _replay(rp.A9_USER_TURNS[4], protected,
                                                      guard_each=False)
    assert false_raises == []
    final = bodies[-1]
    with _tracing_suspended():
        t = time.perf_counter()
        tk.assert_no_plaintext(final, tm)
        cold = (time.perf_counter() - t) * 1000
    assert cold < 50, cold
    # incremental: the real loop guards after every appended message
    _tm2, _b2, _r2, false2, guard_ms, _r3 = _replay(rp.A9_USER_TURNS[4], protected)
    assert false2 == []
    assert statistics.median(guard_ms) < 10, statistics.median(guard_ms)


# ── helpers exercised directly ─────────────────────────────────────────────


def test_oracle_itself_catches_what_it_must() -> None:
    """The oracle is the independent test authority -- pin that it does see
    the classes it claims (so a green suite is not a blind oracle)."""
    o = _oracle("DEMO")
    assert o.leaks("ask anil_sharma now") == ["anilsharma", "anil", "sharma"]
    assert "sharmaji" in o.leaks("ask Sharmaji")
    assert o.leaks("ask ａｎｉｌ　ｓｈａｒｍａ") == ["anilsharma", "anil", "sharma"]
    assert o.leaks("B001 and G002") == []
    assert o.leaks("gupta & sons", system=True) == ["guptasons", "gupta"]
    assert o.leaks("the desk and the sons") == []


def test_oracle_mapping_is_plain_data() -> None:
    assert isinstance(rp.PINNED, list)
    assert isinstance(UNIVERSES, Mapping)


# ── KCH-238R review 1 fix cycle 1 ──────────────────────────────────────────


@pytest.mark.parametrize(("prompt", "expected", "typed"), rp.R1_PEEL_PROMPTS)
def test_m1_a_name_found_only_by_peeling_a_suffix_is_a_q_of_the_full_typed_text(
    prompt: str, expected: str, typed: str
) -> None:
    tm = tk.TokenMap(EntityResolver(rp.R1_PEEL_UNIVERSE))
    out = tm.tokenise_prompt(prompt)
    assert out == expected
    assert tm.value_of("Q001") == typed


def test_m1_glued_honorific_on_a_stored_name_is_masked_as_q_not_exact() -> None:
    tm = tk.TokenMap(_resolver("DEMO"))
    out = tm.tokenise_prompt("anil sharmaji owes")
    assert out == "Q001 owes"
    assert tm.value_of("Q001") == "anil sharmaji"
    with pytest.raises(tk.PlaintextLeakError):  # guard still catches the peeled form
        _guard_text("ask anil sharmaji", tm)


@pytest.mark.parametrize(("prompt", "reply"), list(zip(rp.R1_PARAS, rp.R1_REPLIES, strict=True)))
def test_m2_the_models_own_reply_never_raises_on_an_issued_q_or_n_text(
    prompt: str, reply: str
) -> None:
    tm = tk.TokenMap(_resolver("DEMO"))
    user = tm.tokenise_prompt(prompt)
    tk.assert_no_plaintext(
        {"messages": [{"role": "user", "content": user}, {"role": "assistant", "content": reply}]},
        tm,
    )


@pytest.mark.parametrize("word", ["unconfirmed", "overwrites"])
def test_m2_a_word_typed_later_never_bricks_the_already_sent_system_prompt(word: str) -> None:
    tm = tk.TokenMap(_resolver("DEMO"))
    msgs = [{"role": "system", "content": rp.SYSTEM_PROMPT},
            {"role": "user", "content": tm.tokenise_prompt("hello")}]
    tk.assert_no_plaintext({"messages": msgs}, tm)
    typed = tm.tokenise_prompt(f"what does {word} mean")
    assert typed == "what does N001 mean"
    msgs.append({"role": "user", "content": typed})
    for _ in range(3):  # every later request
        tk.assert_no_plaintext({"messages": msgs}, tm)


def test_m2_an_issued_q_or_n_text_in_a_user_or_tool_message_still_raises() -> None:
    tm = tk.TokenMap(_resolver("DEMO"))
    tm.tokenise_prompt("lend to Rohan Kapadia")
    for role in ("user", "tool"):
        with pytest.raises(tk.PlaintextLeakError):
            tk.assert_no_plaintext(
                {"messages": [{"role": role, "content": "rohan kapadia will pay"}]}, tm
            )
    with pytest.raises(tk.PlaintextLeakError):  # G1 still applies to the model's own text
        tk.assert_no_plaintext(
            {"messages": [{"role": "assistant", "content": "anil sharma will pay"}]}, tm
        )


@pytest.mark.xfail(strict=True, reason="DEBT KCH-239: stored name glued to digits (owner ruling)")
@pytest.mark.parametrize(("prompt", "leaked"), rp.DIGIT_GLUED_LEAKS)
def test_known_leak_stored_name_glued_to_digits(prompt: str, leaked: str) -> None:
    tm = tk.TokenMap(_resolver("DEMO"))
    out = tm.tokenise_prompt(prompt)
    assert leaked not in out.lower()


@pytest.mark.parametrize("word", ["unconfirmed", "overwrites"])
def test_m2_a_word_typed_in_the_first_turn_never_bricks_the_system_prompt(word: str) -> None:
    """Reviewer probe p_sysp.py: the system prompt is first checked AFTER the
    word became an N token (turn 1), so the no-recheck rule alone does not
    help; the app-authored system prompt, like the model's own text, is not
    checked against issued Q/N texts (G1/G2/G4 still apply)."""
    tm = tk.TokenMap(_resolver("DEMO"))
    typed = tm.tokenise_prompt(f"what does {word} mean")
    assert typed == "what does N001 mean"
    tk.assert_no_plaintext(
        {"messages": [{"role": "system", "content": rp.SYSTEM_PROMPT},
                      {"role": "user", "content": typed}]},
        tm,
    )
    with pytest.raises(tk.PlaintextLeakError):  # G1 still applies to system text
        tk.assert_no_plaintext({"messages": [{"role": "system", "content": "anil sharma"}]}, tm)


# ── KCH-238R review 2 (cycle 2): n1, n3, n4 ────────────────────────────────


def test_n1_a_body_that_raises_caches_nothing_so_a_resend_is_rechecked() -> None:
    """Reviewer probe p2_m2.py: verdicts are committed only when the WHOLE
    body passes -- a raised request left nothing on the wire."""
    tm = tk.TokenMap(_resolver("DEMO"))
    obs = json.dumps(tm.tokenise_observation({"message": "note: call kapadia before friday"}))
    with pytest.raises(tk.PlaintextLeakError):  # turn 1 raises on its second leaf
        tk.assert_no_plaintext(
            {"messages": [{"role": "tool", "content": obs},
                          {"role": "tool", "content": "anil sharma"}]},
            tm,
        )
    assert tm.tokenise_prompt("lend 5000 to kapadia") == "lend AMOUNT_1 to N001"
    with pytest.raises(tk.PlaintextLeakError):  # first real send of 'kapadia' as N001
        tk.assert_no_plaintext({"messages": [{"role": "tool", "content": obs}]}, tm)


def test_n3_a_string_cleared_in_an_assistant_message_is_rechecked_in_a_tool_message() -> None:
    """Reviewer probe p2_c7.py: the guard cache is keyed on the G3 flag too."""
    tm = tk.TokenMap(_resolver("DEMO"))
    tm.tokenise_prompt("lend to Rohan Kapadia")
    text = "rohan kapadia will pay"
    tk.assert_no_plaintext({"messages": [{"role": "assistant", "content": text}]}, tm)
    with pytest.raises(tk.PlaintextLeakError):
        tk.assert_no_plaintext({"messages": [{"role": "tool", "content": text}]}, tm)


@pytest.mark.parametrize(
    "message",
    [
        {"role": "developer", "content": "rohan kapadia will pay"},
        {"role": "System", "content": "rohan kapadia will pay"},
        {"content": "rohan kapadia will pay"},
        ["rohan kapadia will pay"],
    ],
    ids=["developer", "System", "no-role", "non-mapping"],
)
def test_n4_an_unknown_missing_or_differently_cased_role_still_gets_g3(message) -> None:
    tm = tk.TokenMap(_resolver("DEMO"))
    tm.tokenise_prompt("lend to Rohan Kapadia")
    with pytest.raises(tk.PlaintextLeakError):
        tk.assert_no_plaintext({"messages": [message]}, tm)
