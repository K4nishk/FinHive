"""KCH-238: TokenMap ingress/egress tokenisation, detokenisation, rehydration
and the plaintext leak guard.

Fail-first evidence for every test here is recorded in the KCH-238 tester's
final report (command run, the mutation applied, the assertion line that
failed for the stated reason, and confirmation `tokeniser.py` was restored
byte-identically before the suite was run green).
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from loan_manager.application.agent.tokeniser import (
    _AMOUNT_CANDIDATE_RE,
    MONEY_RE,
    PlaintextLeakError,
    TokenBudgetExceededError,
    TokenKind,
    TokenMap,
    UnknownTokenError,
    _amount_text_variants,
    _value_boundary_pattern,
    assert_no_plaintext,
    key_is_classified,
    parse_amount,
)
from loan_manager.application.agent.tool_registry import parse_args
from loan_manager.application.agent.tools.args import (
    FormatInr,
    GetPortfolioSummary,
    QueryLoans,
    ResolveEntity,
    UpdateLoan,
)
from loan_manager.application.agent.tools.read_tools import build_read_registry
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.domain.services.entity_resolver import EntityResolver

from .conftest import make_loan, uow_factory_for

TODAY = date(2026, 9, 25)


def _resolver(**values) -> EntityResolver:
    return EntityResolver(values)


# ── token stability & sharing ───────────────────────────────────────────────


def test_tokens_stable_first_appearance() -> None:
    """Tokens are issued in FIRST-APPEARANCE order within a kind, and the
    same value always maps back to the same token thereafter -- never
    re-numbered, never re-issued."""
    tm = TokenMap(_resolver())

    first = tm.token_for(TokenKind.BORROWER, "charlie")
    second = tm.token_for(TokenKind.BORROWER, "alice")
    repeat = tm.token_for(TokenKind.BORROWER, "charlie")

    assert first == "B001"
    assert second == "B002"
    assert repeat == "B001"


def test_typed_and_returned_amount_share_token() -> None:
    """A user-typed unit-word amount and a tool-returned decimal amount for
    the SAME rupee value key to the identical token."""
    tm = TokenMap(_resolver())

    typed = tm.token_for(TokenKind.AMOUNT, parse_amount("1.5 lakh"))
    returned = tm.token_for(TokenKind.AMOUNT, Decimal("150000.00"))

    assert typed == "AMOUNT_1"
    assert returned == "AMOUNT_1"


def test_token_for_amount_quantises_half_up_not_half_even() -> None:
    """Mutant M6 (review1 M5 table): quantising without `ROUND_HALF_UP`
    falls back to Decimal's default ROUND_HALF_EVEN, which rounds
    2.345 -> 2.34 (4 is already even) instead of MVP1's 2.35 (CLAUDE.md:
    money is always ROUND_HALF_UP)."""
    tm = TokenMap(_resolver())

    token = tm.token_for(TokenKind.AMOUNT, Decimal("2.345"))

    assert tm.value_of(token) == Decimal("2.35")


# ── ingress: tokenise_prompt ─────────────────────────────────────────────────


def test_ingress_exact_group_substituted_rest_passes_through() -> None:
    tm = TokenMap(_resolver(borrower_group=["sharma group"]))

    result = tm.tokenise_prompt("loans in sharma group please")

    assert result == "loans in G001 please"


def test_ingress_exact_three_word_group_name_still_matches() -> None:
    """Mutant M15 (review1 M5 table): the greedy window cap must track the
    longest stored entity's word count, not a fixed ceiling -- a 3-word
    group name ('gupta & sons') must still resolve exactly."""
    tm = TokenMap(_resolver(borrower_group=["gupta & sons"]))

    result = tm.tokenise_prompt("loans for gupta & sons please")

    assert result == "loans for G001 please"


def test_ingress_pure_punctuation_window_has_no_core_and_is_skipped() -> None:
    """A word that strips to an empty core (pure punctuation, e.g. '--')
    must not be handed to `resolver.resolve` -- it is simply skipped."""
    tm = TokenMap(_resolver(borrower_name=["rakesh sharma"]))

    result = tm.tokenise_prompt("well -- anyway")

    assert result == "well -- anyway"


def test_ingress_noise_token_never_starts_a_pass3_ambiguous_match() -> None:
    """Mutant M7 (review1 M5 table): pass 3 (fuzzy/ambiguous) must never
    START a window at a NOISE_TOKENS word -- 'family' alone must not become
    its own Q mention just because 'family trust' is a stored value it
    fuzzy-matches on shared tokens."""
    tm = TokenMap(_resolver(borrower_name=["family trust"]))

    result = tm.tokenise_prompt("the family owes money")

    assert result == "the family owes money"


def test_ingress_ambiguous_mention_becomes_q_token() -> None:
    tm = TokenMap(
        _resolver(
            borrower_name=["suresh iyer", "lakshmi iyer"],
            depositor_name=["meera iyer"],
        )
    )

    result = tm.tokenise_prompt("how much does iyer owe")

    assert result == "how much does Q001 owe"
    assert tm.value_of("Q001") == "iyer"


# ── B1/M4: punctuation and possessives next to a name (review1 reproducers) ─


def test_ingress_possessive_apostrophe_s_preserved_around_exact_name() -> None:
    """B1 reproducer 1: 'Meera Iyer's exposure' -- the possessive must not
    zero the fuzzy score and downgrade an otherwise-exact full name to a
    no_match; the stripped `'s` is kept in the output, glued to the token."""
    tm = TokenMap(_resolver(depositor_name=["meera iyer"]))

    result = tm.tokenise_prompt("What is Meera Iyer's exposure?")

    assert result == "What is D001's exposure?"


def test_ingress_curly_quote_possessive_preserved_around_exact_name() -> None:
    """B1 reproducer 2: the curly-quote 'S form, upper-cased."""
    tm = TokenMap(_resolver(depositor_name=["meera iyer"]))

    result = tm.tokenise_prompt("MEERA IYER’S loans")

    assert result == "D001’S loans"


def test_ingress_possessive_on_ambiguous_mention_preserved() -> None:
    """B1 reproducer 3: a bare first name ('Meera's') is not itself a stored
    value, so it becomes a Q mention (KCH-236 confirm contract), not a
    silent match -- but the possessive must still be stripped before
    resolving and glued back onto the Q token afterwards."""
    tm = TokenMap(
        _resolver(borrower_name=["suresh iyer", "lakshmi iyer"], depositor_name=["meera iyer"])
    )

    result = tm.tokenise_prompt("Meera's loans")

    assert result.startswith("Q001's ")
    assert tm.value_of("Q001") == "Meera"


def test_ingress_punctuation_next_to_exact_names_resolves_exact_not_q() -> None:
    """M4: a comma/semicolon/period fused to the last word of an exact name
    must not downgrade it to a Q mention -- it resolves exact (a real
    token), and the punctuation is preserved in the output untouched."""
    tm = TokenMap(
        _resolver(
            borrower_name=["ramesh gupta", "pooja verma", "asha bhat"],
        )
    )

    result = tm.tokenise_prompt("ramesh gupta, pooja verma; asha bhat.")

    assert result == "B001, B002; B003."


def test_ingress_quoted_exact_name_resolves_exact_with_quotes_preserved() -> None:
    tm = TokenMap(_resolver(depositor_name=["deepak menon"]))

    result = tm.tokenise_prompt('"deepak menon"')

    assert result == '"D001"'


def test_ingress_trailing_question_mark_preserved_around_exact_name() -> None:
    tm = TokenMap(_resolver(borrower_name=["anil"]))

    result = tm.tokenise_prompt("What's the status of Anil?")

    assert result == "What's the status of B001?"


@pytest.mark.parametrize(
    ("form", "expected"),
    [
        ("₹45,000", Decimal("45000")),
        ("Rs 45000", Decimal("45000")),
        ("Rs. 45,000", Decimal("45000")),
        ("INR 45000", Decimal("45000")),
        ("1,85,000", Decimal("185000")),
        ("185,000", Decimal("185000")),
        ("1.5 lakh", Decimal("150000")),
        ("2 crore", Decimal("20000000")),
        ("50k", Decimal("50000")),
    ],
)
def test_ingress_amount_forms(form: str, expected: Decimal) -> None:
    tm = TokenMap(_resolver())

    result = tm.tokenise_prompt(f"the amount is {form} total")

    assert result == "the amount is AMOUNT_1 total"
    assert tm.value_of("AMOUNT_1") == expected.quantize(Decimal("0.01"))


@pytest.mark.parametrize(
    ("form", "expected"),
    [
        # B2 reproducers (review1): cheque "/-", bare "rs" suffix (no
        # space), "L"/"l" lakh shorthand.
        ("45000/-", Decimal("45000")),
        ("45,000/-", Decimal("45000")),
        ("45000rs", Decimal("45000")),
        ("45000 rs", Decimal("45000")),
        ("1.5L", Decimal("150000")),
        ("1.5l", Decimal("150000")),
    ],
)
def test_ingress_amount_forms_with_notation(form: str, expected: Decimal) -> None:
    tm = TokenMap(_resolver())

    result = tm.tokenise_prompt(f"lend him {form}")

    assert result == "lend him AMOUNT_1"
    assert tm.value_of("AMOUNT_1") == expected.quantize(Decimal("0.01"))


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("lend him 45000.", "lend him AMOUNT_1."),
        ("lend 50000, then stop", "lend AMOUNT_1, then stop"),
    ],
)
def test_ingress_amount_keeps_trailing_sentence_punctuation(prompt: str, expected: str) -> None:
    """B2: a sentence-final '.' or an Oxford ',' right after a bare amount
    must not block the match (old lookahead rejected any following '.'/',')
    -- and must not be swallowed into the token either."""
    tm = TokenMap(_resolver())

    result = tm.tokenise_prompt(prompt)

    assert result == expected


@pytest.mark.parametrize(
    "text",
    [
        "ref 2026_03_004 is the loan",
        "due on 2026-09-26",
        "due 26 Sep 2026",
        "in 2026 we started",
        "rate is 12%",
        "extend for 3 months",
        "overdue by 45 days",
        "across 10 loans",
        "show top 10 borrowers",
        # >=4-digit forms, so these actually reach the candidate regex and
        # exercise `_is_excluded_amount`'s %/following-word/"top" branches
        # (a 1-2 digit number never matches the bare-amount pattern at all).
        "rate is 1200% too high",
        "extend for 3000 months",
        "overdue by 4500 days",
        "show top 5000 borrowers",
        # ORCH ruling (B2, review1): "loan(s)" no longer excludes a
        # currency-/unit-marked OR a >=4-digit bare number -- only a bare
        # number BELOW 1000 before "loan(s)" would be a count, and that can
        # never reach this regex at all (needs 4+ digits to match). So the
        # only true non-amount case above is "across 10 loans" (a 2-digit
        # count); see test_ingress_bare_amount_before_loans_is_tokenised for
        # the >=4-digit cases, which now DO tokenise.
    ],
)
def test_ingress_non_amounts_pass_through(text: str) -> None:
    tm = TokenMap(_resolver())

    result = tm.tokenise_prompt(text)

    assert result == text
    assert "AMOUNT_" not in result


@pytest.mark.parametrize(
    "prompt",
    [
        "gave a 5000 loan to him",
        "across 1000 loans",
    ],
)
def test_ingress_bare_amount_before_loans_is_tokenised(prompt: str) -> None:
    """B2 ORCH ruling: currency/unit-marked numbers are ALWAYS amounts, and
    a bare number >= 1000 is an amount even directly before 'loan(s)' -- the
    old exclusion of every number before 'loan(s)' is gone."""
    tm = TokenMap(_resolver())

    result = tm.tokenise_prompt(prompt)

    assert "AMOUNT_" in result
    assert "5000" not in result
    assert "1000" not in result


def test_bare_year_range_amount_is_tokenised_without_date_context() -> None:
    """M1: a bare 1900-2099 number is a year only when a date-context word
    or a month name sits next to it; otherwise it is an ordinary amount,
    even though it falls in the plausible-year range."""
    tm = TokenMap(_resolver())

    result = tm.tokenise_prompt("gave 2000 to him")

    assert result == "gave AMOUNT_1 to him"
    assert tm.value_of("AMOUNT_1") == Decimal("2000.00")


@pytest.mark.parametrize(
    "text",
    [
        "in 2026 we started",
        "since 2026 things changed",
        "FY 2026 targets",
        "Sep 2026 was slow",
        "2026 September was slow",
    ],
)
def test_year_context_word_or_month_name_still_excludes_the_amount(text: str) -> None:
    tm = TokenMap(_resolver())

    result = tm.tokenise_prompt(text)

    assert "AMOUNT_" not in result


def test_amount_candidate_and_parse_amount_regexes_stay_in_lockstep() -> None:
    """m4: keep both `# pragma: no cover` guards, but pin that the two
    regexes never drift apart -- every `_AMOUNT_CANDIDATE_RE` match over a
    corpus covering every accepted notation must be `parse_amount`-able."""
    corpus = [
        "the amount is 45000 total",
        "₹45,000 due",
        "Rs. 45,000 due",
        "INR 45000 due",
        "1,85,000 paid",
        "185,000 paid",
        "1.5 lakh given",
        "2 crore loan",
        "50k transferred",
        "45000/- received",
        "45,000/- received",
        "45000rs paid",
        "45000 rs paid",
        "1.5L given",
        "1.5l given",
        "lend him 45000.",
        "lend 50000, then stop",
        "gave a 5000 loan to him",
        "across 1000 loans",
    ]
    for text in corpus:
        for match in _AMOUNT_CANDIDATE_RE.finditer(text):
            assert parse_amount(match.group(0)) is not None, match.group(0)


def test_user_typed_token_shaped_literal_is_rejected_at_ingress() -> None:
    """m1 ORCH ruling: TOKEN_RE is tightened to EXACTLY 3 digits for
    B/D/G/Q, and a user-typed token-shaped literal is rejected at ingress
    with a clear message -- never silently passed through (the old
    behaviour) and never trusted later even once that exact token has been
    issued to someone else (a confused/adversarial user must never be able
    to make the model's later echo detokenise to someone else's real
    name)."""
    tm = TokenMap(_resolver(borrower_name=["rakesh sharma"]))

    with pytest.raises(UnknownTokenError, match="token codes cannot be typed"):
        tm.tokenise_prompt("what about B001's loan")


def test_user_typed_token_shaped_literal_rejected_even_after_issuance() -> None:
    tm = TokenMap(_resolver(borrower_name=["rakesh sharma"]))
    b_token = tm.token_for(TokenKind.BORROWER, "rakesh sharma")  # B001, now real

    with pytest.raises(UnknownTokenError, match="token codes cannot be typed"):
        tm.tokenise_prompt(f"what about {b_token}'s loan")


def test_four_digit_q_mention_is_not_token_shaped() -> None:
    """m1: TOKEN_RE now requires EXACTLY 3 digits, so a 4-digit lookalike
    like 'Q1000' is not token-shaped at all -- it is ordinary text on
    ingress, and `detokenise_args` must not raise `UnknownTokenError` for it
    either (the old `\\d{3,}` pattern flagged it as a fabricated token)."""
    tm = TokenMap(_resolver())

    assert tm.tokenise_prompt("Q1000 results") == "Q1000 results"
    assert tm.detokenise_args('{"text": "Q1000 results"}') == {"text": "Q1000 results"}


# ── egress: tokenise_observation ────────────────────────────────────────────


def test_egress_tokenises_each_read_tool_projection() -> None:
    tm = TokenMap(
        _resolver(
            borrower_name=["rakesh sharma"],
            borrower_group=["sharma group"],
            depositor_name=["meera iyer"],
        )
    )

    obs = {
        "ok": True,
        "total_amount": "550000.00",
        "exposure": "300000.00",
        "total_exposure": "300000.00",
        "principal": "10000.00",
        "interest": "1200.00",
        "formatted": "₹1,50,000.00",
        "borrower_name": "rakesh sharma",
        "borrower_group": "sharma group",
        "depositor_name": "meera iyer",
    }

    tokenised = tm.tokenise_observation(obs)

    for key in (
        "total_amount",
        "exposure",
        "total_exposure",
        "principal",
        "interest",
        "formatted",
    ):
        assert tokenised[key].startswith("AMOUNT_"), f"{key} was not tokenised: {tokenised[key]!r}"
    assert tokenised["borrower_name"] == "B001"
    assert tokenised["borrower_group"] == "G001"
    assert tokenised["depositor_name"] == "D001"


def test_principal_and_interest_are_classified_amount_keys() -> None:
    """Mutant M16 (review1 M5 table): pins the STRUCTURED AMOUNT_KEYS path
    directly for 'principal'/'interest', rather than relying on the scrub
    fallback that made the mutant survive originally -- with the M3
    fail-closed rule below, dropping either key from AMOUNT_KEYS now makes
    `tokenise_observation` RAISE instead of silently falling through, so
    this test kills the mutant robustly."""
    tm = TokenMap(_resolver())

    obs = tm.tokenise_observation({"principal": "10000.00", "interest": "1200.00"})

    assert obs["principal"].startswith("AMOUNT_")
    assert obs["interest"].startswith("AMOUNT_")


def test_depositor_group_shares_group_namespace_with_borrower_group() -> None:
    """Mutant M5 (review1 M5 table): `depositor_group` must share ONE `G`
    namespace with `borrower_group` -- a group is a group regardless of
    which side of the loan it names (module docstring)."""
    tm = TokenMap(
        _resolver(borrower_group=["sharma group"], depositor_group=["chennai circle"])
    )

    obs = tm.tokenise_observation(
        {"borrower_group": "sharma group", "depositor_group": "chennai circle"}
    )

    assert obs["borrower_group"].startswith("G")
    assert obs["depositor_group"].startswith("G")


def test_candidate_value_kind_follows_sibling_field() -> None:
    """Mutant M3 (review1 M5 table): a `candidates[].value`'s TokenKind
    must follow its OWN sibling `field`, not a fixed kind."""
    tm = TokenMap(_resolver(depositor_name=["meera iyer"]))

    obs = tm.tokenise_observation(
        {
            "candidates": [
                {"field": "depositor_name", "value": "meera iyer", "score": 1.0, "rank": 1}
            ]
        }
    )

    token = obs["candidates"][0]["value"]
    assert token.startswith("D")
    assert tm.value_of(token) == "meera iyer"


def test_unclassified_numeric_key_fails_closed() -> None:
    """M3 ORCH ruling: a genuinely unclassified key carrying a bare
    int/Decimal/numeric-string is a programmer error at egress (a new
    READ-tool field nobody classified) -- fail closed rather than let it
    slip through untouched (the old behaviour) or get silently absorbed by
    the free-text scrub fallback. A non-numeric string under an unknown key
    still goes through `_scrub` untouched (see
    test_egress_falsy_and_unparseable_fields_pass_through's "code" case)."""
    tm = TokenMap(_resolver())

    with pytest.raises(PlaintextLeakError):
        tm.tokenise_observation({"amount": 250000})

    with pytest.raises(PlaintextLeakError):
        tm.tokenise_observation({"new_amount": "250000.00"})

    with pytest.raises(PlaintextLeakError):
        tm.tokenise_observation({"paid": Decimal("5000.00")})


def test_unclassified_bool_passes_through() -> None:
    """A bool is an `int` subclass -- `_tokenise_unclassified` must not
    treat it as a numeric leak."""
    tm = TokenMap(_resolver())

    obs = tm.tokenise_observation({"is_new_field": True})

    assert obs["is_new_field"] is True


def test_every_read_tool_key_classified() -> None:
    """Every key the six READ tools actually produce -- success AND error
    paths, including the nested `candidates`/`top`/`error`/`notes`
    structures -- is accounted for by the egress classification tables.
    KCH-243 extending the tool surface must extend these tables too."""
    loans = [
        make_loan(
            borrower_name="rakesh sharma",
            borrower_group="sharma group",
            depositor_name="meera iyer",
            depositor_group="chennai circle",
            amount=250000,
            giving_date=date(2026, 4, 10),
            due_date=TODAY - timedelta(days=10),
        ),
        make_loan(
            borrower_name="deepak menon",
            borrower_group="menon traders",
            depositor_name="arjun rao",
            depositor_group=None,
            amount=80000,
            giving_date=date(2026, 6, 15),
            due_date=None,  # overdue, undated -> "notes"
        ),
    ]
    uow_factory = uow_factory_for(loans)
    clock = FixedClock(TODAY)
    registry = build_read_registry(uow_factory, clock)

    observations: list[dict] = []
    observations.append(registry.handler("get_current_context")(None))
    observations.append(
        registry.handler("resolve_entity")(ResolveEntity.model_validate({"text": "sharma"}))
    )
    observations.append(
        registry.handler("query_loans")(QueryLoans.model_validate({"status": "overdue"}))
    )
    observations.append(
        registry.handler("query_loans")(
            QueryLoans.model_validate({"status": "paidoff"})
        )  # error path
    )
    observations.append(
        registry.handler("get_portfolio_summary")(GetPortfolioSummary.model_validate({}))
    )
    observations.append(
        registry.handler("calculate_interest")(
            parse_args("calculate_interest", {"ref_id": "9999_01_001", "rate": 12, "months": 3})
        )  # error path: ref not found
    )
    observations.append(
        registry.handler("format_inr")(FormatInr.model_validate({"amount": "1500"}))
    )

    found_keys: set[str] = set()

    def _collect(node) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                found_keys.add(k)
                _collect(v)
        elif isinstance(node, list):
            for item in node:
                _collect(item)

    for obs in observations:
        _collect(obs)

    unclassified = {k for k in found_keys if not key_is_classified(k)}
    assert unclassified == set(), f"unclassified keys: {unclassified}"


def test_egress_scrubs_free_text_next_action() -> None:
    """A free-text field (`next_action`) that mentions a KNOWN entity value
    the tool itself did not put in a structured name/amount field still
    gets tokenised, via `_scrub`."""
    tm = TokenMap(_resolver(borrower_group=["sharma group"]))
    obs = {
        "ok": False,
        "next_action": "ask the user to confirm they mean sharma group before proceeding",
    }

    tokenised = tm.tokenise_observation(obs)

    assert "sharma group" not in tokenised["next_action"]
    assert "G001" in tokenised["next_action"]


# ── the model's tool-call arguments, detokenised ────────────────────────────


def test_detokenised_amount_passes_parse_args() -> None:
    tm = TokenMap(_resolver())
    tm.token_for(TokenKind.AMOUNT, Decimal("200000.00"))  # AMOUNT_1

    format_args = tm.detokenise_args('{"amount": "AMOUNT_1"}')
    parsed_format = FormatInr.model_validate(format_args)
    assert parsed_format.amount == Decimal("200000.00")

    update_args = tm.detokenise_args('{"ref_id": "2026_03_004", "amount": "AMOUNT_1"}')
    parsed_update = UpdateLoan.model_validate(update_args)
    assert parsed_update.amount == 200000
    assert isinstance(parsed_update.amount, int)


def test_detokenise_args_accepts_matching_field_kind() -> None:
    tm = TokenMap(_resolver(borrower_name=["rakesh sharma"], borrower_group=["sharma group"]))
    b_token = tm.token_for(TokenKind.BORROWER, "rakesh sharma")
    g_token = tm.token_for(TokenKind.GROUP, "sharma group")

    result = tm.detokenise_args(
        f'{{"borrower_name": "{b_token}", "borrower_group": "{g_token}"}}'
    )

    assert result == {"borrower_name": "rakesh sharma", "borrower_group": "sharma group"}


def test_detokenise_args_rejects_borrower_token_in_group_field() -> None:
    """m6: a token's kind must match the argument field it appears under --
    a BORROWER token used where borrower_group is expected round-trips to
    the wrong kind of value (a person's name where a group slug belongs),
    which downstream validation only catches by accident (review1 m6:
    'query_loans then rejects it, safe today because the rejected value is
    scrubbed'). Reject it here instead, loudly."""
    tm = TokenMap(_resolver(borrower_name=["rakesh sharma"]))
    b_token = tm.token_for(TokenKind.BORROWER, "rakesh sharma")

    with pytest.raises(UnknownTokenError):
        tm.detokenise_args(f'{{"borrower_group": "{b_token}"}}')


def test_detokenise_args_rejects_amount_token_in_name_field() -> None:
    tm = TokenMap(_resolver())
    amount_token = tm.token_for(TokenKind.AMOUNT, Decimal("5000"))

    with pytest.raises(UnknownTokenError):
        tm.detokenise_args(f'{{"depositor_name": "{amount_token}"}}')


def test_detokenise_args_bare_top_level_token_has_no_field_to_check() -> None:
    """`raw` need not be a JSON object -- a bare top-level token string has
    no enclosing field, so the kind check is a no-op (`field is None`)."""
    tm = TokenMap(_resolver())
    tm.token_for(TokenKind.AMOUNT, Decimal("200000.00"))

    assert tm.detokenise_args('"AMOUNT_1"') == 200000


def test_detokenise_args_field_kind_check_ignores_unmapped_fields() -> None:
    """A field this table does not name (e.g. `text`, `items`) is never
    kind-checked -- the model may legitimately hand a G/B/D/Q token back
    into a free-text field like resolve_entity's `text`."""
    tm = TokenMap(_resolver(borrower_group=["sharma group"]))
    g_token = tm.token_for(TokenKind.GROUP, "sharma group")

    result = tm.detokenise_args(f'{{"text": "{g_token}"}}')

    assert result == {"text": "sharma group"}


def test_unknown_token_raises() -> None:
    tm = TokenMap(_resolver())

    with pytest.raises(UnknownTokenError):
        tm.value_of("B999")
    with pytest.raises(UnknownTokenError):
        tm.detokenise_args('{"text": "B999"}')


# ── rehydrate: final answer only ────────────────────────────────────────────


def test_rehydrate_final_answer() -> None:
    tm = TokenMap(_resolver(borrower_group=["sharma group"]))
    tokenised_prompt = tm.tokenise_prompt("what does sharma group owe")
    assert tokenised_prompt == "what does G001 owe"
    amount_token = tm.token_for(TokenKind.AMOUNT, Decimal("150000.00"))

    answer = tm.rehydrate(
        f"{TokenKind.GROUP.value}001 owes {amount_token} in total, see UNKNOWN_999"
    )

    assert answer == "sharma group owes ₹1,50,000.00 in total, see UNKNOWN_999"


def test_rehydrate_replaces_mention_token_with_typed_text() -> None:
    """Mutant M4 (review1 M5 table): a Q (MENTION) token must rehydrate to
    the literal text the user typed, not be left as the token itself."""
    tm = TokenMap(_resolver())
    q_token = tm.token_for(TokenKind.MENTION, "iyer")

    answer = tm.rehydrate(f"following up on {q_token}")

    assert answer == "following up on iyer"


# ── leak guard ───────────────────────────────────────────────────────────────

_MUST_NOT_RAISE = [
    "2026_03_004",
    "2026-09-26",
    "26 Sep 2026",
    "FY2026-27",
    "12.00",
    "0.857",
    "AMOUNT_12",
    "G001",
    "call_1234567",
]

_MUST_RAISE = [
    "₹45,000",
    "Rs 45000",
    "1,85,000",
    "185,000",
    "185000.00",
    "1.5 lakh",
    "2 crore",
    "SHARMA GROUP",
    "meera   iyer",
    # B2 ORCH ruling: MONEY_RE must detect every accepted notation so the
    # guard is a real backstop, independent of any specific known amount.
    "45,000/-",
    "45000/-",
    "1.5L",
    "50k",
]


@pytest.mark.parametrize("text", _MUST_RAISE)
def test_guard_raises(text: str) -> None:
    tm = TokenMap(_resolver(borrower_group=["sharma group"], depositor_name=["meera iyer"]))
    tm.token_for(TokenKind.AMOUNT, Decimal("5000"))  # for the "a known 5000" family
    body = {"messages": [{"role": "user", "content": text}]}

    with pytest.raises(PlaintextLeakError):
        assert_no_plaintext(body, tm)


def test_guard_raises_known_short_amount_below_generic_threshold() -> None:
    """MONEY_RE's bare-digit branch alone requires 5+ digits (so a bare year
    never trips it); a KNOWN 4-digit amount must still be caught, by the
    separate per-token-map-amount rendering check."""
    tm = TokenMap(_resolver())
    tm.token_for(TokenKind.AMOUNT, Decimal("5000"))
    assert not MONEY_RE.search("a known 5000")  # the generic regex alone misses it
    body = {"messages": [{"role": "user", "content": "a known 5000"}]}

    with pytest.raises(PlaintextLeakError):
        assert_no_plaintext(body, tm)


@pytest.mark.parametrize("text", _MUST_NOT_RAISE)
def test_guard_no_false_positive(text: str) -> None:
    tm = TokenMap(_resolver(borrower_group=["sharma group"], depositor_name=["meera iyer"]))
    body = {"messages": [{"role": "user", "content": text}]}

    assert_no_plaintext(body, tm)  # must not raise


def test_guard_money_scan_restricted_to_messages_key() -> None:
    """m2/Mutant M2 (review1 M5 table): money-shaped text elsewhere in the
    body (e.g. a tool schema's own description text) must never trip the
    guard -- only `messages` is scanned."""
    tm = TokenMap(_resolver())
    body = {
        "messages": [{"role": "user", "content": "hello"}],
        "tools": [{"description": "amount, e.g. ₹45,000"}],
    }

    assert_no_plaintext(body, tm)  # must not raise


def test_guard_does_not_scan_tool_schemas_for_names() -> None:
    """m2: the guard's name scan covers `messages` only -- a stored
    single-word name that also happens to be an ordinary word in a tool
    schema description must never brick the whole conversation."""
    tm = TokenMap(_resolver(borrower_name=["amount"]))
    body = {"messages": [], "tools": [{"description": "the loan amount in rupees"}]}

    assert_no_plaintext(body, tm)  # must not raise


def test_guard_duration_field_not_confused_with_known_amount() -> None:
    """m2: `months: 3` must never trip the guard merely because AMOUNT 3
    happens to be a known token-map amount elsewhere in the conversation --
    a duration/count field is never money-shaped."""
    tm = TokenMap(_resolver())
    tm.token_for(TokenKind.AMOUNT, Decimal("3"))
    body = {"messages": [{"role": "tool", "months": 3}]}

    assert_no_plaintext(body, tm)  # must not raise


def test_guard_skips_numeric_leaf_under_opaque_id_key() -> None:
    """m2: do not flag a numeric id once it appears under a key known to be
    an id -- an id is never money."""
    tm = TokenMap(_resolver())
    tm.token_for(TokenKind.AMOUNT, Decimal("12345"))
    body = {"messages": [{"role": "tool", "id": 12345}]}

    assert_no_plaintext(body, tm)  # must not raise


def test_guard_name_pattern_compiled_once_per_name_then_cached(monkeypatch) -> None:
    """m3: `assert_no_plaintext` must not recompile a name's boundary regex
    on every call -- once a name's pattern is built it is cached and
    reused."""
    tm = TokenMap(_resolver(borrower_name=["rakesh sharma"]))
    calls: list[str] = []
    original = _value_boundary_pattern

    def counting(value: str):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(
        "loan_manager.application.agent.tokeniser._value_boundary_pattern", counting
    )
    body = {"messages": [{"role": "user", "content": "hello"}]}

    assert_no_plaintext(body, tm)
    assert_no_plaintext(body, tm)
    assert_no_plaintext(body, tm)

    assert calls.count("rakesh sharma") <= 1


# ── remaining coverage: edge cases exercised nowhere above ─────────────────


def test_parse_amount_edge_cases() -> None:
    assert parse_amount("") is None
    assert parse_amount("not an amount at all") is None


def test_amount_text_variants_across_magnitudes() -> None:
    """Exercises `_group_indian`/`_group_western`'s short-circuit (<=3
    digits) AND multi-group (>=6 digits, so the grouping loop actually
    iterates more than once) paths -- no test above ever calls this
    directly, since the ingress/rehydrate tests never round-trip an amount
    back through `_scrub`/`assert_no_plaintext`."""
    small = _amount_text_variants(Decimal("500.00"))
    assert "500" in small
    assert "500.00" in small

    large = _amount_text_variants(Decimal("12345678.00"))
    assert "1,23,45,678" in large  # Indian grouping, 3 group boundaries
    assert "12,345,678" in large  # Western grouping, 2 group boundaries


def test_token_map_rejects_entity_value_shaped_like_token() -> None:
    with pytest.raises(ValueError, match="collides with the token format"):
        TokenMap(_resolver(borrower_name=["B001"]))


def test_egress_falsy_and_unparseable_fields_pass_through() -> None:
    tm = TokenMap(_resolver())

    obs = tm.tokenise_observation(
        {
            "depositor_group": None,
            "total_amount": None,
            "formatted": None,
            "notes": None,
            "candidates": ["not-a-candidate-dict"],
            "code": {"detail": "nested, not a real READ-tool shape"},
        }
    )

    assert obs["depositor_group"] is None
    assert obs["total_amount"] is None
    assert obs["formatted"] is None
    assert obs["notes"] is None
    assert obs["candidates"] == ["not-a-candidate-dict"]
    assert obs["code"] == {"detail": "nested, not a real READ-tool shape"}

    unparseable = tm.tokenise_observation({"formatted": "not a rupee amount"})
    assert unparseable["formatted"] == "not a rupee amount"


def test_scrub_reuses_already_issued_amount_in_later_free_text() -> None:
    tm = TokenMap(_resolver())
    tokenised_prompt = tm.tokenise_prompt("they typed 1.5 lakh")
    assert "AMOUNT_1" in tokenised_prompt

    obs = tm.tokenise_observation({"next_action": "confirm the 150000 total with the user"})

    assert "150000" not in obs["next_action"]
    assert "AMOUNT_1" in obs["next_action"]


def test_scrub_tokenises_previously_unseen_amount_in_free_text() -> None:
    """Mutant M9 (review1 M5 table): `_scrub` must still run the generic
    amount pass for a NUMBER never issued a token before -- distinct from
    the "reuse an already-issued amount" test above, which an
    amount-pass-skipping mutant could otherwise pass by accident via the
    issued-rendering substitution alone."""
    tm = TokenMap(_resolver())

    obs = tm.tokenise_observation({"next_action": "confirm the 45000 total with the user"})

    assert "45000" not in obs["next_action"]
    assert "AMOUNT_" in obs["next_action"]


def test_scrub_replaces_issued_amount_rendering_below_pass_amounts_threshold() -> None:
    """Mutant M10 (review1 M5 table): a small already-issued amount's exact
    decimal rendering ("500.00") has only 3 integer digits -- below
    `_AMOUNT_CANDIDATE_RE`'s bare 4-digit floor, and no comma to match its
    grouped branch either -- so only the issued-rendering substitution can
    catch it; `_pass_amounts` alone never would (this is what makes it kill
    the mutant, unlike the 150000 case above, which `_pass_amounts` would
    re-derive to the same token anyway)."""
    tm = TokenMap(_resolver())
    token = tm.token_for(TokenKind.AMOUNT, Decimal("500"))

    obs = tm.tokenise_observation({"next_action": "confirm 500.00 with the user"})

    assert "500.00" not in obs["next_action"]
    assert token in obs["next_action"]


def test_scrub_merges_issued_and_resolver_names_longest_first() -> None:
    """M2 ORCH ruling / mutant M1 (review1 M5 table): a single longest-first
    pass over issued values AND resolver entities together, so a full name
    always wins over a sub-name/mention it contains. Reproduces the
    ordering bug directly (review1 M2): if the merge ran shortest-first (or
    as two separate passes, issued-before-resolver), the already-issued Q
    mention 'iyer' would be swapped inside 'meera iyer' and 'iyer chem'
    FIRST, leaving 'meera' and 'chem' in plaintext."""
    tm = TokenMap(
        _resolver(
            borrower_name=["suresh iyer", "lakshmi iyer"],
            depositor_name=["meera iyer"],
            borrower_group=["iyer chem"],
        )
    )
    tm.tokenise_prompt("how much does iyer owe")  # issues Q001 = "iyer"

    obs = tm.tokenise_observation({"message": "meera iyer and iyer chem are linked"})

    assert "meera" not in obs["message"]
    assert "chem" not in obs["message"]
    assert "iyer" not in obs["message"].lower()


class _FakeResolverWithUnusableEntities:
    """Duck-typed stand-in for `EntityResolver` (only `.entities()` is
    accessed by the code paths under test) carrying two entries a REAL
    `EntityResolver` can never produce: a field name outside `NAME_KEYS`,
    and a blank value (its own constructor filters those out). Used only to
    exercise the defensive `kind is None or not value` guards that a real
    resolver's contract makes otherwise unreachable."""

    def entities(self):
        return (("unclassified_field", "something"), ("borrower_name", ""))


def test_scrub_resolver_names_skips_unclassified_or_blank_entities() -> None:
    tm = TokenMap(_FakeResolverWithUnusableEntities())

    result = tm._scrub_names("mentions something here, nothing to tokenise")

    assert result == "mentions something here, nothing to tokenise"


def test_guard_skips_blank_name_in_names_set() -> None:
    tm = TokenMap(_FakeResolverWithUnusableEntities())
    body = {"messages": [{"role": "user", "content": "hello, nothing sensitive"}]}

    assert_no_plaintext(body, tm)  # must not raise despite an empty name in names()


def test_detokenise_args_none_empty_and_invalid_json() -> None:
    tm = TokenMap(_resolver())

    assert tm.detokenise_args(None) is None
    assert tm.detokenise_args("") == ""
    assert tm.detokenise_args("not-valid-json{") == "not-valid-json{"


def test_detokenise_args_list_and_embedded_tokens() -> None:
    tm = TokenMap(_resolver(borrower_name=["rakesh sharma"]))
    b_token = tm.token_for(TokenKind.BORROWER, "rakesh sharma")
    amount_token = tm.token_for(TokenKind.AMOUNT, Decimal("150000.00"))

    result = tm.detokenise_args(
        f'{{"items": ["{b_token}", "regarding {b_token} amount {amount_token} total"]}}'
    )

    assert result["items"][0] == "rakesh sharma"
    assert result["items"][1] == "regarding rakesh sharma amount 150000 total"


def test_rehydrate_leaves_unmapped_token_shaped_string() -> None:
    tm = TokenMap(_resolver())

    assert tm.rehydrate("ask about B999 please") == "ask about B999 please"


def test_guard_body_without_messages_key_is_safe() -> None:
    tm = TokenMap(_resolver())

    assert_no_plaintext({"tools": []}, tm)  # no "messages" key at all -- must not raise


def test_guard_raises_on_known_amount_as_raw_number_leaf() -> None:
    tm = TokenMap(_resolver())
    tm.token_for(TokenKind.AMOUNT, Decimal("45000"))
    body = {"messages": [{"role": "tool", "amount": 45000}]}

    with pytest.raises(PlaintextLeakError):
        assert_no_plaintext(body, tm)


def test_guard_bool_leaf_never_treated_as_a_number() -> None:
    """`bool` is a subclass of `int` in Python -- a `True`/`False` leaf must
    be skipped outright, never coerced through `Decimal(str(leaf))`."""
    tm = TokenMap(_resolver())
    body = {"messages": [{"role": "tool", "ok": True}]}

    assert_no_plaintext(body, tm)  # must not raise


def test_ingress_whitespace_only_prompt_is_a_no_op() -> None:
    tm = TokenMap(_resolver(borrower_name=["rakesh sharma"]))

    assert tm.tokenise_prompt("   ") == "   "


def test_detokenise_args_accepts_a_mapping_directly() -> None:
    """`raw` need not be a JSON string -- `tool_registry.parse_args` also
    accepts an already-parsed mapping, and so does `detokenise_args`."""
    tm = TokenMap(_resolver())
    tm.token_for(TokenKind.AMOUNT, Decimal("200000.00"))

    result = tm.detokenise_args({"amount": "AMOUNT_1"})

    assert result == {"amount": 200000}


def test_detokenise_args_passes_non_string_scalars_through() -> None:
    tm = TokenMap(_resolver())

    result = tm.detokenise_args('{"limit": 10, "flag": true, "missing": null}')

    assert result == {"limit": 10, "flag": True, "missing": None}


# ═══════════════════════════════════════════════════════════════════════════
# KCH-238 review 2 (re-review after fix cycle 1): NB1, NB2, NM1-NM5, MINORs
# and the 4 mutation survivors (N4, N7, N15, N19/N20). Every test below
# reproduces a review2 finding or ORCH ruling verbatim from
# kch-238.review2.md.
# ═══════════════════════════════════════════════════════════════════════════


# ── NB2 (structural): word spans, not \S+ windows ───────────────────────────


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("meera iyer,anil sharma", "D001,B001"),
        ("meera iyer/anil sharma", "D001/B001"),
        ("meera iyer&anil sharma", "D001&B001"),
        ("(meera iyer)", "(D001)"),
        ("[Meera Iyer]", "[D001]"),
        ("«meera iyer»", "«D001»"),
        ("meera iyer…", "D001…"),  # ellipsis
        ("meera iyer—exposure", "D001—exposure"),  # em dash
        ("@meera iyer", "@D001"),
        ("meera_iyer", "D001"),
        ("meera\tiyer", "D001"),
        ("MEERA\nIYER", "D001"),
    ],
)
def test_nb2_punctuation_glued_names_resolve_per_name(prompt: str, expected: str) -> None:
    """NB2 BLOCKER (review2): a name glued to its neighbour by punctuation
    other than whitespace (comma, slash, ampersand, brackets, em dash, an
    '@', an underscore, a tab/newline) must resolve exactly, per name, with
    the separator preserved verbatim -- the old `\\S+` windowing made the
    whole glued span `no_match`, leaking both names in clear."""
    tm = TokenMap(
        _resolver(depositor_name=["meera iyer"], borrower_name=["anil sharma"])
    )

    result = tm.tokenise_prompt(prompt)

    assert result == expected


def test_nb2_indian_honorific_hyphen_suffix_preserved() -> None:
    """NB2 reproducer: 'anil sharma-ji' -- the honorific hyphen suffix must
    not swallow the surname into `no_match`."""
    tm = TokenMap(_resolver(borrower_name=["anil sharma"]))

    result = tm.tokenise_prompt("anil sharma-ji")

    assert result == "B001-ji"


def test_nb2_period_glued_title_resolves_surname() -> None:
    """NB2 reproducer: 'Mr.Sharma' -- the period must not glue 'Mr' and the
    surname into one unresolvable span."""
    tm = TokenMap(_resolver(borrower_name=["anil sharma"]))

    result = tm.tokenise_prompt("Mr.Sharma")

    assert "Sharma" not in result
    assert result.startswith("Mr.")


def test_nb2_hyphenated_compact_code_still_normalises_via_resolver() -> None:
    """NB2 must not regress the EntityResolver's own hyphen/underscore
    normalisation for a compact code typed with a real hyphen (not an
    honorific) -- the resolver already folds '-'/'_' to a space, so a
    2-word window's raw text ("rohit-sharma") still resolves exact."""
    tm = TokenMap(_resolver(borrower_name=["rohit sharma"]))

    result = tm.tokenise_prompt("loan for rohit-sharma please")

    assert result == "loan for B001 please"


def test_nb2_group_name_containing_ampersand_still_matches() -> None:
    """A REAL stored value containing '&' as one of its own words ("gupta &
    sons") must still resolve exact -- NB2's separator treatment of '&'
    between two DIFFERENT names must not break this."""
    tm = TokenMap(_resolver(borrower_group=["gupta & sons"]))

    result = tm.tokenise_prompt("loans for gupta & sons please")

    assert result == "loans for G001 please"


# ── NM4: combining marks stay in the word ───────────────────────────────────


def test_nm4_devanagari_name_with_trailing_matra_resolves_exact() -> None:
    """NM4 MAJOR (review2): a combining mark (Unicode category M*, e.g. the
    vowel sign on "शर्मा") is not `str.isalnum()`, so the old edge-punctuation
    strip peeled it off as if it were trailing punctuation -- downgrading an
    exact Devanagari name to a Q mention. Fixed by `_is_word_char` treating
    any M*-category character as part of the word."""
    tm = TokenMap(_resolver(depositor_name=["राम शर्मा"]))

    result = tm.tokenise_prompt("राम शर्मा का लोन")

    assert result == "D001 का लोन"


# ── MINOR: curly apostrophe folded before resolving ─────────────────────────


def test_curly_apostrophe_in_stored_name_resolves_exact() -> None:
    """MINOR (review2): a name typed with a curly apostrophe ("O’Brien
    Shah") must resolve EXACT against a stored value spelled with a
    straight one ("o'brien shah") -- a phone keyboard's "smart quote" must
    not force an unnecessary KCH-236 confirm round-trip."""
    tm = TokenMap(_resolver(borrower_name=["o'brien shah"]))

    result = tm.tokenise_prompt("O’Brien Shah owes")

    assert result == "B001 owes"


# ── NB1: a currency/unit-marked number is ALWAYS an amount, any size ────────


@pytest.mark.parametrize(
    "prompt",
    [
        "a loan of 2000 rupees",
        "of 2000/-",
        "of 2000rs",
        "by 2000 inr",
        "in 2000 rs",
        "since 2000/-",
        "sep 2000 rupees",
        "500 rupees",
        "750rs",
        "999/-",
    ],
)
def test_nb1_currency_or_unit_marked_number_always_an_amount(prompt: str) -> None:
    """NB1 BLOCKER (review2): every one of these has an explicit currency
    marker (rs/rupees/inr/'/-'), so it must ALWAYS become an amount --
    whatever its size, and never subject to the year/date-context rule
    (several of these sit right next to 'of'/'by'/'in'/'since'/'sep', which
    would otherwise exclude a bare 4-digit number as a year)."""
    tm = TokenMap(_resolver())

    result = tm.tokenise_prompt(prompt)

    assert "AMOUNT_" in result


def test_nb1_guard_matches_currency_suffixed_number_below_1000() -> None:
    """NB1: MONEY_RE (the guard) must match a currency-suffixed number of
    ANY size too, not only the ingress detector."""
    for text in ("999/-", "750rs", "500 rupees"):
        assert MONEY_RE.search(text), text


# ── NM5: thousand/hundred units ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("prompt", "expected_value"),
    [
        ("50 thousand", Decimal("50000")),
        ("5 thousand rupees", Decimal("5000")),
    ],
)
def test_nm5_thousand_unit_recognised(prompt: str, expected_value: Decimal) -> None:
    tm = TokenMap(_resolver())

    result = tm.tokenise_prompt(prompt)

    assert result == "AMOUNT_1"
    assert tm.value_of("AMOUNT_1") == expected_value.quantize(Decimal("0.01"))


def test_nm5_lakh_and_thousand_both_tokenise_in_one_prompt() -> None:
    tm = TokenMap(_resolver())

    result = tm.tokenise_prompt("1 lakh 50 thousand")

    assert result == "AMOUNT_1 AMOUNT_2"
    assert tm.value_of("AMOUNT_1") == Decimal("100000.00")
    assert tm.value_of("AMOUNT_2") == Decimal("50000.00")


# ── M1 (cycle 2 correction): "of" dropped from year-context words ──────────


def test_m1_of_no_longer_excludes_a_bare_year_shaped_amount() -> None:
    """ORCH ruling (review2): drop 'of' from the year-context list -- it is
    the most common amount preposition in this domain, and over-tokenising
    is safe. Also kills mutant N4 (re-adding 'of' to the set)."""
    tm = TokenMap(_resolver())

    result = tm.tokenise_prompt("a loan of 2000")

    assert result == "a loan of AMOUNT_1"


# ── NM1: fail-closed walks lists/nested containers, and free-text keys ─────


def test_nm1_int_inside_list_under_unclassified_key_fails_closed() -> None:
    tm = TokenMap(_resolver())

    with pytest.raises(PlaintextLeakError):
        tm.tokenise_observation({"x": [250000]})


def test_nm1_int_inside_nested_list_fails_closed() -> None:
    tm = TokenMap(_resolver())

    with pytest.raises(PlaintextLeakError):
        tm.tokenise_observation({"x": [[250000]]})


def test_nm1_decimal_inside_list_fails_closed() -> None:
    tm = TokenMap(_resolver())

    with pytest.raises(PlaintextLeakError):
        tm.tokenise_observation({"x": [Decimal("5000.00")]})


def test_nm1_bare_number_directly_under_free_text_key_fails_closed() -> None:
    """'A free-text key holding a non-string is a programmer error'
    (review2 NM1 ORCH ruling)."""
    tm = TokenMap(_resolver())

    with pytest.raises(PlaintextLeakError):
        tm.tokenise_observation({"message": 250000})


def test_nm1_list_under_free_text_key_with_a_bare_int_fails_closed() -> None:
    tm = TokenMap(_resolver())

    with pytest.raises(PlaintextLeakError):
        tm.tokenise_observation({"notes": [250000, "a"]})


def test_nm1_bool_inside_list_under_free_text_key_passes_through() -> None:
    """A bool is an `int` subclass -- `_tokenise_free`'s list-recursion must
    not treat one buried inside a list as a numeric leak."""
    tm = TokenMap(_resolver())

    obs = tm.tokenise_observation({"notes": [True, "ok"]})

    assert obs["notes"] == [True, "ok"]


def test_nm1_float_under_unclassified_key_fails_closed() -> None:
    """The old check excluded `float` entirely (`isinstance(value, (int,
    Decimal))` never matches a `float`) -- review2 NM1 explicitly calls
    this out."""
    tm = TokenMap(_resolver())

    with pytest.raises(PlaintextLeakError):
        tm.tokenise_observation({"x": 5000.5})


# ── NM2: the 1000th token of a kind fails closed ────────────────────────────


def test_nm2_999th_mention_succeeds_1000th_raises() -> None:
    tm = TokenMap(_resolver())
    for i in range(999):
        tm.token_for(TokenKind.MENTION, f"x{i}")

    last = tm.token_for(TokenKind.MENTION, "x998")  # already issued: no new mint
    assert last == "Q999"

    with pytest.raises(TokenBudgetExceededError):
        tm.token_for(TokenKind.MENTION, "brand new value")


def test_nm2_amount_kind_has_no_999_cap() -> None:
    """AMOUNT tokens are `f"{kind.value}{n}"` with no zero-padding and no
    digit-count restriction in `TOKEN_RE` (`AMOUNT_\\d+`), so the 999 cap
    applies only to B/D/G/Q."""
    tm = TokenMap(_resolver())
    for i in range(1001):
        tm.token_for(TokenKind.AMOUNT, Decimal(i))

    assert tm.token_for(TokenKind.AMOUNT, Decimal(1000)) == "AMOUNT_1001"


# ── NM3: the guard's known-amount check is money-shaped everywhere ─────────


def test_nm3_guard_does_not_raise_on_calculate_interest_basis_divisor() -> None:
    """NM3 MAJOR (review2): the fixed divisor literal inside `basis`
    ("amount×rate×months/1200") must never collide with a genuinely known
    amount that happens to equal 1200 -- interest on 40000 @ 12% for 3
    months IS 1200 (CLAUDE.md formula), so this is not a contrived number."""
    tm = TokenMap(_resolver())
    tm.token_for(TokenKind.AMOUNT, Decimal("1200"))
    content = json.dumps(
        {
            "ok": True,
            "ref_id": "2026_01_021",
            "principal": "AMOUNT_1",
            "rate_percent": "12.00",
            "months": 3,
            "interest": "AMOUNT_2",
            "basis": "amount×rate×months/1200",
        },
        ensure_ascii=False,
    )
    body = {"messages": [{"role": "tool", "content": content}]}

    assert_no_plaintext(body, tm)  # must not raise


@pytest.mark.parametrize(
    ("amount", "content"),
    [
        (Decimal("12"), '{"ref_id":"2026_01_021","rate":12,"months":3}'),
        (Decimal("3"), '{"months":3}'),
        (Decimal("450"), "top 450"),
    ],
)
def test_nm3_small_known_amount_not_flagged_in_serialised_content(
    amount: Decimal, content: str
) -> None:
    """NM3: a known amount is only flagged where its rendering is
    money-shaped (grouped, or >= 4 digits) -- a 1-3 digit known amount
    (a rate, a month count, a "top N" limit) must never trip the guard
    merely because it also happens to be a `TokenMap` amount, EVEN inside a
    serialised JSON string (tool_calls arguments or a `content` blob)."""
    tm = TokenMap(_resolver())
    tm.token_for(TokenKind.AMOUNT, amount)
    body = {"messages": [{"role": "tool", "content": content}]}

    assert_no_plaintext(body, tm)  # must not raise


def test_nm3_guard_still_raises_on_4_digit_known_amount_in_content_string() -> None:
    """The money-shape filter must not become a blanket exemption: a
    genuinely leaked 4+-digit known amount inside a `content` string still
    raises."""
    tm = TokenMap(_resolver())
    tm.token_for(TokenKind.AMOUNT, Decimal("1200"))
    body = {"messages": [{"role": "tool", "content": '{"leaked": "1200 rupees paid"}'}]}

    with pytest.raises(PlaintextLeakError):
        assert_no_plaintext(body, tm)


def test_nm3_guard_tool_calls_arguments_are_scanned() -> None:
    """Confirms `tool_calls[].function.arguments` (a string, nested inside
    `messages`) is reached by the guard at all -- a genuinely leaked known
    4-digit amount there must still raise."""
    tm = TokenMap(_resolver())
    tm.token_for(TokenKind.AMOUNT, Decimal("45000"))
    body = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "c1",
                        "function": {"name": "format_inr", "arguments": '{"amount":"45000"}'},
                    }
                ],
            }
        ]
    }

    with pytest.raises(PlaintextLeakError):
        assert_no_plaintext(body, tm)


def test_nm3_unclassified_small_number_key_unaffected_by_money_shape_filter() -> None:
    """The money-shape filter lives in the GUARD only -- `_tokenise_unclassified`'s
    own fail-closed rule (M3/NM1) still raises for ANY bare numeric value,
    however small, since that is a classification gap, not a guard
    false-positive concern."""
    tm = TokenMap(_resolver())

    with pytest.raises(PlaintextLeakError):
        tm.tokenise_observation({"x": 3})


# ── TOKEN_RE uses [0-9], not \d (MINOR) ─────────────────────────────────────


def test_token_re_does_not_match_non_ascii_digits() -> None:
    """MINOR (review2): `TOKEN_RE` uses `[0-9]`, not `\\d`, so a Unicode
    digit run (Devanagari here) is never mistaken for a token shape and
    does not trigger the ingress token-rejection."""
    tm = TokenMap(_resolver())

    text = "flat B१२३ for rent"
    assert tm.tokenise_prompt(text) == text


def test_ascii_digit_lookalike_is_still_rejected_ruling_mandated() -> None:
    """MINOR (review2): 'flat B101' is ordinary text (a flat number), but
    it is shape-indistinguishable from a real issued token -- rejecting it
    is ruling-mandated (m1: never trust a typed token-shaped literal); KCH-239
    owns showing the user a clear rejection message for this case."""
    tm = TokenMap(_resolver())

    with pytest.raises(UnknownTokenError, match="token codes cannot be typed"):
        tm.tokenise_prompt("flat B101 for rent")


# ── MINOR: documented, accepted fail-closed guard raise ─────────────────────


def test_year_left_in_clear_can_coincide_with_known_amount_and_guard_raises() -> None:
    """MINOR (review2, accepted as fail-safe, ORCH ruling: 'acceptable';
    documented here rather than fixed): 'in 1999 paid 1999' leaves the
    FIRST '1999' in clear (year, date context from 'in'); the SECOND '1999'
    has no date-context neighbour, so it becomes an amount. If amount 1999
    is independently known elsewhere in this conversation, the guard then
    raises on the literal year left in clear -- fail-closed, not a leak,
    and the input is contrived."""
    tm = TokenMap(_resolver())

    result = tm.tokenise_prompt("in 1999 paid 1999")

    assert result == "in 1999 paid AMOUNT_1"
    body = {"messages": [{"role": "user", "content": result}]}

    with pytest.raises(PlaintextLeakError):
        assert_no_plaintext(body, tm)


# ── Mutation survivors from review2's mut2.py: named tests ─────────────────


def test_n7_money_re_matches_bare_5plus_digit_with_rs_or_rupees_suffix() -> None:
    """N7 (review2 mutation table, SURVIVED): MONEY_RE's bare-5+-digit
    branch must keep its `_MONEY_SUFFIX`."""
    for text in ("45000rs", "45000 rupees"):
        assert MONEY_RE.search(text), text


def test_n15_guard_opaque_id_skip_covers_a_string_id_in_the_money_loop() -> None:
    """N15 (review2 mutation table, SURVIVED): the existing opaque-id test
    used an INT id; this one exercises the STRING branch of the money loop,
    which has its own separate `if key in _OPAQUE_ID_KEYS: continue`."""
    tm = TokenMap(_resolver())
    body = {"messages": [{"role": "tool", "id": "45,000"}]}

    assert_no_plaintext(body, tm)  # must not raise: "id" is opaque even as a string


def test_n13_guard_duration_key_exemption_is_independent_of_magnitude() -> None:
    """N13 (review2 mutation table, SURVIVED): the existing 'months: 3'
    test is also protected by the NM3 money-shape magnitude filter (3 has
    only 1 digit), so it alone does not pin the KEY exemption
    (`_NON_AMOUNT_NUMERIC_KEYS`) -- this uses a 4+-digit known amount, which
    IS money-shaped on its own, so only the key exemption (not the
    magnitude filter) can be protecting it here."""
    tm = TokenMap(_resolver())
    tm.token_for(TokenKind.AMOUNT, Decimal("5000"))
    body = {"messages": [{"role": "tool", "months": 5000}]}

    assert_no_plaintext(body, tm)  # must not raise: "months" is never money


def test_n19_dynamic_window_cap_covers_a_four_word_entity() -> None:
    """N19 (review2 mutation table, SURVIVED): no existing fixture entity
    had 4+ words, so a mutant hardcoding the cap at a small fixed number
    (e.g. 3) coincidentally still passed the 3-word 'gupta & sons' test.
    This one needs a real 4-word window."""
    tm = TokenMap(_resolver(borrower_name=["rakesh kumar singh yadav"]))

    result = tm.tokenise_prompt("loan for rakesh kumar singh yadav please")

    assert result == "loan for B001 please"


def test_n20_year_exclusion_covers_the_1900s_not_only_2000s() -> None:
    """N20 (review2 mutation table, SURVIVED): years 1900-1999 were
    untested."""
    tm = TokenMap(_resolver())

    result = tm.tokenise_prompt("in 1950 we started")

    assert result == "in 1950 we started"
    assert "AMOUNT_" not in result
