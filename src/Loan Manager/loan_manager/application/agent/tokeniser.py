"""TokenMap: names and amounts tokenised before crossing the LLM boundary
(KCH-238 — ARB D-12, D-15; OQ-01 amended: only inference crosses a border,
so anything that reaches the model must already be a token, ingress AND
egress).

One `TokenMap` per conversation (KCH-239 keeps it alive for the session).
Five token kinds share one instance so the same stored value always maps to
the same token everywhere it appears in that conversation:

  B001 borrower_name   D001 depositor_name   G001 borrower_group/
  depositor_group (the two share ONE namespace — a group is a group
  regardless of which side of the loan it names)   Q001 an unresolved or
  ambiguous free-text mention (KCH-236 confirm contract: the model must ask
  "did you mean X?" before treating it as real, so no name value backs the
  token — reversing it gives back exactly what the user typed)   AMOUNT_n
  an amount, keyed by its `Decimal` value quantised to 2dp, so "1.5 lakh"
  typed by the user and "150000.00" returned by a tool share one token.

Token shape: `f"{prefix}{n:03d}"` for B/D/G/Q, `f"AMOUNT_{n}"` (no padding)
for amounts. `TOKEN_RE` is the single detection regex every consumer of this
module uses to find a token substring: `\\b(?:[BDGQ][0-9]{3}|AMOUNT_[0-9]+)\\b`
— EXACTLY 3 ASCII digits for B/D/G/Q (review1 m1 ORCH ruling; `[0-9]`, not
`\\d`, per review2 MINOR: `\\d` also matches non-ASCII Unicode digits, so
ordinary text carrying a Devanagari/Arabic-Indic digit run would otherwise
be mistaken for a token shape), so a 4-digit lookalike a model or user
might type/echo ("Q1000") is never mistaken for one of ours in either
direction. `token_for` refuses to mint a 1000th token of one B/D/G/Q kind
in one conversation (`TokenBudgetExceededError`, review2 NM2 ORCH ruling) —
past 999, `n:03d` would silently overflow to 4+ digits and stop matching
`TOKEN_RE` at all, a silent wrong answer rather than a leak.

A prompt or observation crosses in one of two directions:

  ingress  `tokenise_prompt`       — the user's typed text, BEFORE the model
                                     ever sees it. A token-shaped literal the
                                     user types is REJECTED here (review1
                                     m1 ORCH ruling) — never trusted, even
                                     once that exact token has been issued
                                     to someone else.
  egress   `tokenise_observation`  — a READ tool's JSON result, BEFORE it is
                                     appended to the conversation the model
                                     reads.

and the model's own JSON tool-call arguments cross back the other way,
`detokenise_args`, before they reach `tool_registry.parse_args`. A token's
KIND must match the argument field it appears under (review1 m6 ORCH
ruling) — a borrower token in a group field is rejected, not silently
round-tripped to the wrong kind of value. Only the final answer shown to
the human is ever un-tokenised, via `rehydrate`.

`assert_no_plaintext` is the last-resort guard immediately before a network
call: it does not replace any of the above, it catches what they missed.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum
from typing import Any

from loan_manager.application.agent.tools.read_format import format_inr
from loan_manager.domain.services.entity_resolver import NOISE_TOKENS, EntityResolver

_TWO_PLACES = Decimal("0.01")


class TokenKind(str, Enum):
    BORROWER = "B"
    DEPOSITOR = "D"
    GROUP = "G"
    MENTION = "Q"
    AMOUNT = "AMOUNT_"


class UnknownTokenError(ValueError):
    """A token-shaped string (`TOKEN_RE`) that this `TokenMap` never issued —
    raised by `value_of`/`detokenise_args`/anything that must trust the
    value behind a token (including a token whose KIND does not match the
    argument field it was found under — review1 m6), and by
    `tokenise_prompt` for a token-shaped literal the user typed (review1
    m1). Never raised by `rehydrate`, which is the final-answer path and
    leaves an unmapped token exactly as written rather than blow up a
    user-facing answer over one bad token (KCH-239 maps this error, where
    it IS raised, to `error(UNKNOWN_TOKEN, ...)`)."""


class PlaintextLeakError(AssertionError):
    """`assert_no_plaintext` found a known name, a known amount, or a
    money-shaped string in a body about to leave the machine. Also raised
    by `tokenise_observation`/`_tokenise_free` (review1 M3, review2 NM1
    ORCH rulings, fail closed) for a genuinely unclassified key -- or a
    free-text key, or any depth inside a list under either -- carrying a
    bare numeric value: a programmer error (a new READ-tool field nobody
    added to the classification tables, or a free-text field handed a raw
    number instead of a string), not something to silently tokenise or
    pass through."""


class TokenBudgetExceededError(PlaintextLeakError):
    """`token_for` was asked to mint the 1000th token of one B/D/G/Q kind
    in a single conversation (review2 NM2 ORCH ruling). `TOKEN_RE` stays
    EXACTLY 3 digits (never widened), so a 1000th token would silently stop
    matching it everywhere -- `rehydrate` would show the model's raw
    "Q1000" to the user, and `detokenise_args` would pass the literal string
    straight through to a tool instead of raising. Neither is a plaintext
    leak, but both are a silent wrong answer, which this raises to prevent
    by refusing to mint the token in the first place. A `PlaintextLeakError`
    subclass (not a bare `ValueError`) because a conversation this long is
    itself the kind of thing the fail-closed posture in this module treats
    as unsafe to proceed past silently."""


# Every token this module issues matches this and nothing else does by
# accident: B/D/G/Q require EXACTLY 3 ASCII digits (never colliding with a
# two-digit reference-id fragment, never mistaking a 4+-digit lookalike like
# "Q1000" for a real token — review1 m1 — and never matching a non-ASCII
# Unicode digit run that `\d` would accept — review2 MINOR), AMOUNT_ is its
# own literal prefix.
TOKEN_RE = re.compile(r"\b(?:[BDGQ][0-9]{3}|AMOUNT_[0-9]+)\b")

# The four NAME_FIELDS from EntityResolver, each pointing at the TokenKind
# that owns it. borrower_group and depositor_group intentionally share
# GROUP — see module docstring.
NAME_KEYS: Mapping[str, TokenKind] = {
    "borrower_name": TokenKind.BORROWER,
    "depositor_name": TokenKind.DEPOSITOR,
    "borrower_group": TokenKind.GROUP,
    "depositor_group": TokenKind.GROUP,
}

# review1 m6 ORCH ruling: `detokenise_args` checks a token's kind against
# the argument FIELD it was found under. Only fields with one unambiguous
# expected kind are listed; every other field (free text like
# `resolve_entity.text`, opaque containers like `items`) is never checked.
_FIELD_EXPECTED_KINDS: Mapping[str, frozenset[TokenKind]] = {
    "borrower_name": frozenset({TokenKind.BORROWER}),
    "depositor_name": frozenset({TokenKind.DEPOSITOR}),
    "borrower_group": frozenset({TokenKind.GROUP}),
    "depositor_group": frozenset({TokenKind.GROUP}),
    "amount": frozenset({TokenKind.AMOUNT}),
}

# ── egress classification tables (KCH-237 READ-tool projections) ───────────
# KCH-243 DEBT: adding a PROPOSE-tool projection or a new READ field means
# extending one of these tables. A genuinely new key whose value is a bare
# number now FAILS CLOSED (review1 M3 ORCH ruling) rather than falling
# through to the FREE_TEXT bucket — see `_tokenise_unclassified`.
AMOUNT_KEYS: frozenset[str] = frozenset(
    {"total_amount", "exposure", "total_exposure", "principal", "interest"}
)
FORMATTED_KEY = "formatted"
PASSTHROUGH_KEYS: frozenset[str] = frozenset(
    {
        "ok",
        "status",
        "exact",
        "confirm_required",
        "field",
        "rank",
        "score",
        "count",
        "overdue",
        "overdue_undated",
        "max_days_overdue",
        "loan_count",
        "borrower_count",
        "ref_ids",
        "ref_id",
        "months",
        "rate_percent",
        "basis",
        "code",
        "as_of",
        "today",
        "weekday",
    }
)
PASSTHROUGH_PREFIXES: tuple[str, ...] = ("fy_", "quarter", "month_")
FREE_TEXT_KEYS: frozenset[str] = frozenset(
    {"query", "message", "next_action", "notes", "rejected_value"}
)
# Keys whose value is itself a container (list/dict of further keys) that
# must be walked, but which carry no scalar of their own to classify.
CONTAINER_KEYS: frozenset[str] = frozenset({"candidates", "top", "error"})
# `candidates[].value` -- its TokenKind depends on the sibling `field`
# entry, handled specially in `_tokenise_candidate`, not by a static key
# lookup; it is still a real key the completeness test must know about.
CANDIDATE_VALUE_KEY = "value"
_CANDIDATES_KEY = "candidates"


def _is_passthrough_key(key: str) -> bool:
    return key in PASSTHROUGH_KEYS or any(key.startswith(p) for p in PASSTHROUGH_PREFIXES)


def key_is_classified(key: str) -> bool:
    """True iff `key` is covered by one of the egress tables above — used by
    `test_every_read_tool_key_classified` to pin that every key the six
    READ tools actually produce is accounted for."""
    return (
        key in NAME_KEYS
        or key in AMOUNT_KEYS
        or key in (FORMATTED_KEY, CANDIDATE_VALUE_KEY)
        or _is_passthrough_key(key)
        or key in FREE_TEXT_KEYS
        or key in CONTAINER_KEYS
    )


# ── amount parsing (ingress amounts, egress `formatted`, scrub) ────────────

_UNIT_MULTIPLIERS: Mapping[str, Decimal] = {
    "lakh": Decimal(100000),
    "lakhs": Decimal(100000),
    "lac": Decimal(100000),
    "lacs": Decimal(100000),
    "l": Decimal(100000),
    "crore": Decimal(10000000),
    "crores": Decimal(10000000),
    "cr": Decimal(10000000),
    "k": Decimal(1000),
    "thousand": Decimal(1000),
    "thousands": Decimal(1000),
    "hundred": Decimal(100),
    "hundreds": Decimal(100),
}

# Shared regex fragments (B2 ORCH ruling, review2 NB1/NM5 ORCH rulings):
# built ONCE and reused by `_PARSE_AMOUNT_RE`, `_AMOUNT_CANDIDATE_RE` and
# `MONEY_RE`, so the three never drift apart on what counts as a unit/suffix
# (m4: a property test pins this explicitly). `_UNIT_WORD_ALTS` is the bare
# alternation (no wrapping group) so it can also be spliced into
# `_CURRENCY_OR_UNIT_SUFFIX_RE` below without a nested-group mismatch.
_UNIT_WORD_ALTS = r"lakhs?|lacs?|crores?|cr|l|k|thousands?|hundreds?"
_UNIT_WORD = r"(?:" + _UNIT_WORD_ALTS + r")"
# An Indian cheque "/-" suffix, or a bare "rs"/"rupees"/"inr" suffix with or
# without a leading space (e.g. "45000rs", "45000 rs", "45000/-").
_MONEY_SUFFIX = r"(?:/-|\s?(?:rs\.?|rupees|inr)\b)?"
# Same suffix, but MANDATORY (not optional) -- used by the "suffixed" branch
# below, which exists precisely so a sub-1000 number ("999/-", "750rs",
# "500 rupees") still matches even though it fails every other branch's
# digit-count floor (review2 NB1 ORCH ruling: a currency-marked number is
# an amount at ANY size).
_MANDATORY_MONEY_SUFFIX = r"(?:/-|\s?(?:rs\.?|rupees|inr)\b)"
# Reject a following word char/hyphen (part of a longer token/date/ref-id),
# or a "."/"," immediately followed by a digit (a decimal/group boundary
# this regex did not fully capture) -- but ALLOW a bare trailing sentence
# "." or Oxford "," (nothing after it but non-digits), unlike the old
# lookahead which rejected any trailing "." or "," outright.
_NO_TRAILING_WORD = r"(?![\w-]|[.,]\d)"

_PARSE_AMOUNT_RE = re.compile(
    r"^(?:₹|Rs\.?|INR)?\s?(?P<num>\d[\d,]*(?:\.\d+)?)\s?(?P<unit>"
    + _UNIT_WORD
    + r")?"
    + _MONEY_SUFFIX
    + r"$",
    re.IGNORECASE,
)

# review2 NB1 ORCH ruling: "a currency- or unit-marked number ... is ALWAYS
# an amount ... never subject to year rules" -- checked against the FULL
# TEXT an `_AMOUNT_CANDIDATE_RE` match captured (`match.group(0)`), not
# against which alternative fired, so it also catches a "bare"/"grouped"
# match that merely happens to carry a suffix (e.g. "2000rs" matches the
# `bare` branch, which has `_MONEY_SUFFIX` embedded, but that alone never
# told `_is_excluded_amount` the match was currency-marked before now).
_CURRENCY_PREFIX_RE = re.compile(r"^(?:₹|rs\.?|inr)\b", re.IGNORECASE)
_CURRENCY_OR_UNIT_SUFFIX_RE = re.compile(
    r"(?:" + _UNIT_WORD_ALTS + r"|rs\.?|rupees|inr|/-)$", re.IGNORECASE
)


def _is_currency_or_unit_marked(matched_text: str) -> bool:
    return bool(_CURRENCY_PREFIX_RE.match(matched_text)) or bool(
        _CURRENCY_OR_UNIT_SUFFIX_RE.search(matched_text)
    )


def parse_amount(text: str) -> Decimal | None:
    """`Decimal` rupee value for a single amount expression — `"₹45,000"`,
    `"Rs. 45000"`, `"INR 45000"`, `"1,85,000"` (Indian grouping), `"185,000"`
    (Western grouping), `"1.5 lakh"`, `"2 crore"`, `"50k"`, `"45000/-"`,
    `"45000rs"`, `"1.5L"`, or a bare `"45000"` — or `None` when `text` is
    not one of these shapes. Not a scanner: `text` is a single
    already-isolated span, never a sentence to search (see
    `_AMOUNT_CANDIDATE_RE` for that)."""
    if not text:
        return None
    match = _PARSE_AMOUNT_RE.match(text.strip())
    if not match:
        return None
    try:
        value = Decimal(match.group("num").replace(",", ""))
    except InvalidOperation:  # pragma: no cover - `_PARSE_AMOUNT_RE`'s `num`
        # group only ever captures digits/commas/one optional decimal point,
        # which Decimal always accepts; kept as a defensive guard for
        # `parse_amount` since it is a PUBLIC function future callers
        # (KCH-239/243) may call directly with arbitrary text, not only
        # through this module's own regex-validated call sites.
        return None
    unit = match.group("unit")
    if unit:
        value *= _UNIT_MULTIPLIERS[unit.lower()]
    return value


def _amount_text_variants(quantised: Decimal) -> tuple[str, ...]:
    """Every plain-text rendering of `quantised` that must never appear
    literally once it has been tokenised: `f"{q:f}"` (e.g. "45000.00"), its
    bare integer form when it IS integral ("45000"), Indian grouping
    ("1,85,000") and Western grouping ("185,000") — used by both
    `assert_no_plaintext` and `_scrub`."""
    int_part = str(int(quantised))
    variants = {f"{quantised:f}", _group_indian(int_part), _group_western(int_part)}
    if quantised == quantised.to_integral_value():
        variants.add(int_part)
    return tuple(variants)


def _group_indian(integer_part: str) -> str:
    if len(integer_part) <= 3:
        return integer_part
    last_three = integer_part[-3:]
    rest = integer_part[:-3]
    pairs: list[str] = []
    while len(rest) > 2:
        pairs.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        pairs.insert(0, rest)
    return ",".join([*pairs, last_three])


def _group_western(integer_part: str) -> str:
    if len(integer_part) <= 3:
        return integer_part
    groups: list[str] = []
    rest = integer_part
    while len(rest) > 3:
        groups.insert(0, rest[-3:])
        rest = rest[:-3]
    groups.insert(0, rest)
    return ",".join(groups)


# ── ingress amount detection (tokenise_prompt pass 1, and _scrub pass 3) ───

_AMOUNT_CANDIDATE_RE = re.compile(
    r"(?P<currency>(?:₹|\bRs\.?|\bINR)\s?\d[\d,]*(?:\.\d+)?"
    r"(?:\s?" + _UNIT_WORD + r"\b)?" + _MONEY_SUFFIX + r")"
    r"|(?P<unit>\d+(?:\.\d+)?\s?" + _UNIT_WORD + r"\b" + _MONEY_SUFFIX + r")"
    r"|(?P<grouped>(?<![\w.,/-])\d{1,3}(?:,\d{2,3})+(?:\.\d+)?"
    + _MONEY_SUFFIX + _NO_TRAILING_WORD + r")"
    r"|(?P<bare>(?<![\w.,/-])\d{4,}(?:\.\d+)?" + _MONEY_SUFFIX + _NO_TRAILING_WORD + r")"
    # review2 NB1: a MANDATORY currency suffix on a number of ANY digit
    # count -- the only way a sub-1000 suffix-marked number ("999/-",
    # "750rs", "500 rupees") ever reaches this regex at all, since the
    # branches above all require either a comma group or 4+ bare digits.
    r"|(?P<suffixed>(?<![\w.,/-])\d+(?:\.\d+)?" + _MANDATORY_MONEY_SUFFIX + r")",
    re.IGNORECASE,
)

# review1 M1 ORCH ruling: a bare 1900-2099 number is a year ONLY when a
# date-context word or a month name sits next to it; otherwise it is an
# ordinary amount (the old rule excluded every such number unconditionally).
# review2 ORCH ruling: "of" dropped -- it is the most common amount
# preposition in this domain, and over-tokenising is safe.
_EXCLUDE_FOLLOWING_WORDS = frozenset({"month", "months", "day", "days"})
_YEAR_MIN, _YEAR_MAX = 1900, 2099
_YEAR_CONTEXT_WORDS = frozenset({"in", "since", "until", "till", "by", "year", "fy"})
_MONTH_NAMES = frozenset(
    {
        "jan", "january", "feb", "february", "mar", "march", "apr", "april",
        "may", "jun", "june", "jul", "july", "aug", "august", "sep", "sept",
        "september", "oct", "october", "nov", "november", "dec", "december",
    }
)


def _following_word(text: str, end: int) -> str | None:
    match = re.match(r"\s*([A-Za-z]+)", text[end : end + 20])
    return match.group(1) if match else None


def _preceding_word(text: str, start: int) -> str | None:
    match = re.search(r"([A-Za-z]+)\s*$", text[max(0, start - 20) : start])
    return match.group(1) if match else None


def _is_year_context(text: str, start: int, end: int) -> bool:
    preceding = _preceding_word(text, start)
    if preceding and (
        preceding.lower() in _YEAR_CONTEXT_WORDS or preceding.lower() in _MONTH_NAMES
    ):
        return True
    following = _following_word(text, end)
    return bool(following and following.lower() in _MONTH_NAMES)


def _is_excluded_amount(text: str, match: re.Match[str]) -> bool:
    """Ingress amount-candidate exclusions (plan §KCH-238, review1 B2/M1,
    review2 NB1 ORCH rulings): a reference id or a date never reaches here
    at all (blocked by the candidate regex's own lookaround on `_`/`-`).

    A currency- or unit-marked match (`_is_currency_or_unit_marked` on the
    FULL captured text, prefix or suffix) is NEVER excluded, at any size --
    checked FIRST, before any of the exclusions below (review2 NB1 ORCH
    ruling). What remains to exclude for an UNMARKED bare/grouped number is
    a percentage/duration ("12%", "3 months", "45 days"), a "top N" limit,
    and a bare four-digit year with a date-context neighbour. "loan(s)" no
    longer excludes anything: an unmarked bare number reaching this regex is
    always >= 1000, always an amount."""
    start, end = match.span()
    matched_text = match.group(0)
    if _is_currency_or_unit_marked(matched_text):
        return False
    if text[end : end + 1] == "%":
        return True
    following = _following_word(text, end)
    if following and following.lower() in _EXCLUDE_FOLLOWING_WORDS:
        return True
    preceding = _preceding_word(text, start)
    if preceding and preceding.lower() == "top":
        return True
    digits_only = re.sub(r"\D", "", matched_text)
    return (
        len(digits_only) == 4
        and _YEAR_MIN <= int(digits_only) <= _YEAR_MAX
        and _is_year_context(text, start, end)
    )


# ── leak-guard money regex (assert_no_plaintext) ────────────────────────────
# Deliberately its OWN regex, not `_AMOUNT_CANDIDATE_RE`: this one's bare-
# digit threshold is 5, not 4, so a bare year (2026) or the day/order
# fragments of a reference id (never 5+ digits) never trips it by accident —
# the trade-off is that a real 4-digit amount ("5000") is NOT caught by this
# generic pattern alone, which is exactly why the per-known-amount rendering
# check below exists as a second, independent net. Mirrors every notation
# `_AMOUNT_CANDIDATE_RE` accepts (B2 ORCH ruling: "MONEY_RE must detect
# every form ... so the guard is a real backstop").
MONEY_RE = re.compile(
    r"(?:₹|\bRs\.?|\bINR)\s?\d[\d,]*(?:\.\d+)?(?:\s?" + _UNIT_WORD + r"\b)?" + _MONEY_SUFFIX
    + r"|(?<![\w.,/-])\d{1,3}(?:,\d{2,3})+(?:\.\d+)?" + _MONEY_SUFFIX + _NO_TRAILING_WORD
    + r"|(?<![\w.,/-])\d{5,}(?:\.\d+)?" + _MONEY_SUFFIX + _NO_TRAILING_WORD
    + r"|\b\d+(?:\.\d+)?\s?" + _UNIT_WORD + r"\b" + _MONEY_SUFFIX
    # review2 NB1: the guard must match a currency-suffixed number at ANY
    # size too, same as `_AMOUNT_CANDIDATE_RE`'s "suffixed" branch.
    + r"|(?<![\w.,/-])\d+(?:\.\d+)?" + _MANDATORY_MONEY_SUFFIX,
    re.IGNORECASE,
)


def _value_boundary_pattern(value: str) -> re.Pattern[str]:
    """Case-insensitive whole-value match for `value`, tolerant of any run
    of whitespace between its words ("meera   iyer" still matches stored
    "meera iyer"), bounded so it never matches inside a longer word."""
    parts = [re.escape(p) for p in value.split()]
    body = r"\s+".join(parts) if parts else re.escape(value)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


# review1 B1/M4 ORCH rulings: a trailing possessive right after the core's
# alnum tail ("Iyer's", curly "Iyer’s") is peeled off separately from plain
# edge punctuation, since the possessive's final "s" is itself alnum and
# would otherwise stop the edge-punctuation strip before reaching the `'`.
_POSSESSIVE_RE = re.compile(r"['’]s$", re.IGNORECASE)

_APOSTROPHES = ("'", "’")
_CURLY_APOSTROPHE = "’"


def _is_word_char(ch: str) -> bool:
    """True iff `ch` belongs INSIDE a name span: alnum, underscore (`\\w`
    semantics), or a Unicode COMBINING MARK (category `Mn`/`Mc`/`Me`,
    category-group `M`) -- `str.isalnum()`/`\\w` do NOT count a combining
    mark on its own (review2 NM4 ORCH ruling: without this, the vowel sign
    on a Devanagari name like "शर्मा" gets peeled off as if it were
    trailing punctuation, downgrading an exact match to a Q mention)."""
    return ch.isalnum() or ch == "_" or unicodedata.category(ch)[0] == "M"


def _word_spans(text: str) -> list[tuple[int, int]]:
    """Every maximal word span in `text`: a run of `_is_word_char`
    characters, extended through an apostrophe (`'`/`’`) ONLY when a word
    character immediately follows it, so an in-word apostrophe ("o'brien")
    stays part of the word while a wrapping quote ("'iyer'") or a genuine
    trailing possessive marker's own edge does not get glued onto whatever
    comes next. Everything between spans -- comma, slash, ampersand, en/em
    dash, hyphen, period, quotes, whitespace -- is a SEPARATOR, never
    consumed here and always preserved verbatim in the output (review2 NB2
    ORCH ruling, structural fix: replaces the old `re.finditer(r"\\S+")`,
    which glued any of that punctuation onto whichever name span it
    happened to touch)."""
    spans: list[tuple[int, int]] = []
    i, n = 0, len(text)
    while i < n:
        if not _is_word_char(text[i]):
            i += 1
            continue
        start = i
        i += 1
        while i < n:
            ch = text[i]
            if _is_word_char(ch):
                i += 1
                continue
            if ch in _APOSTROPHES and i + 1 < n and _is_word_char(text[i + 1]):
                i += 1
                continue
            break
        spans.append((start, i))
    return spans


def _fold_apostrophe(text: str) -> str:
    """`text` with a curly apostrophe folded to a straight one, so a name
    typed with the "smart quote" a phone keyboard inserts ("O’Brien Shah")
    still resolves EXACT against a stored value spelled with a straight one
    ("o'brien shah") -- `EntityResolver._normalize` lowercases and folds
    separators, but never folds apostrophe style (review2 MINOR ORCH
    ruling; the fold lives on the query side only, sufficient whenever the
    stored value already uses a straight apostrophe, as every fixture here
    does)."""
    return text.replace(_CURLY_APOSTROPHE, "'")


def _strip_window_edges(window_text: str) -> tuple[str, str, str]:
    """(prefix, core, suffix): `core` is `window_text` with a trailing
    possessive `'s`/'s peeled off; `prefix` is always `""` and `suffix` is
    `""` or the peeled possessive, glued back onto whatever token is
    issued unchanged, so "Meera Iyer's exposure" tokenises to "D001's
    exposure" (KCH-238 review1 B1/M4). `window_text` is built from
    `_word_spans` (review2 NB2), whose own first/last characters are always
    `_is_word_char` by construction (a span can never start or end on
    punctuation) -- there is no leading/trailing edge-punctuation case left
    to strip here; the possessive is the one exception, since its own
    final "s" is itself a word character and so is glued onto the span by
    `_word_spans` rather than left outside it."""
    end = len(window_text)
    possessive = _POSSESSIVE_RE.search(window_text)
    core = window_text
    if possessive and len(core) > len(possessive.group(0)):
        end = possessive.start()
        core = window_text[:end]
    return "", core, window_text[end:]


class TokenMap:
    """One per conversation (KCH-239 keeps it for the session's lifetime).
    See module docstring for the token shapes and the ingress/egress
    boundary this exists to enforce."""

    def __init__(self, resolver: EntityResolver) -> None:
        for _field, value in resolver.entities():
            if TOKEN_RE.fullmatch(value):
                raise ValueError(
                    f"stored entity value {value!r} collides with the token format "
                    "(TOKEN_RE) -- a real name must never look like a token"
                )
        self._resolver = resolver
        self._counters: dict[TokenKind, int] = dict.fromkeys(TokenKind, 0)
        self._forward: dict[tuple[TokenKind, Any], str] = {}
        self._reverse: dict[str, tuple[TokenKind, Any]] = {}
        # review1 m3 ORCH ruling: compiled name-boundary regexes are cached
        # here, keyed by name value. Names are append-only (the resolver's
        # universe is fixed at construction, Q mentions only ever grow), so
        # a plain memoise-on-first-use cache never needs invalidating -- a
        # brand-new name just gets compiled lazily the first time it is
        # checked.
        self._name_pattern_cache: dict[str, re.Pattern[str]] = {}

    # ── core map ────────────────────────────────────────────────────────

    def token_for(self, kind: TokenKind, value: str | Decimal) -> str:
        """The token for `value` under `kind`, issuing a new one in
        first-appearance order if this is the first time `(kind, value)` has
        been seen. Amounts are keyed by their value quantised to 2dp
        (ROUND_HALF_UP), so `1.5 lakh` typed and `150000.00` returned by a
        tool key to the identical `Decimal` and share one token."""
        key: Any
        if kind is TokenKind.AMOUNT:
            key = Decimal(value).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        else:
            key = value
        existing = self._forward.get((kind, key))
        if existing is not None:
            return existing
        self._counters[kind] += 1
        n = self._counters[kind]
        if kind is not TokenKind.AMOUNT and n > 999:
            # review2 NM2 ORCH ruling: fail closed rather than mint a token
            # `TOKEN_RE` (exactly 3 digits) can never match again.
            raise TokenBudgetExceededError(
                f"more than 999 {kind.name.lower()} values in one conversation; "
                "start a new conversation"
            )
        token = f"{kind.value}{n}" if kind is TokenKind.AMOUNT else f"{kind.value}{n:03d}"
        self._forward[(kind, key)] = token
        self._reverse[token] = (kind, key)
        return token

    def _lookup(self, token: str) -> tuple[TokenKind, Any]:
        entry = self._reverse.get(token)
        if entry is None:
            raise UnknownTokenError(token)
        return entry

    def value_of(self, token: str) -> str | Decimal:
        return self._lookup(token)[1]

    def names(self) -> frozenset[str]:
        """Every name this `TokenMap` must never let leak: the FULL universe
        of stored borrower/depositor/group values from the resolver (not
        only ones already tokenised in this conversation — a name the user
        has not yet mentioned is still a real name), plus every `Q`
        mention's literal typed text."""
        resolver_names = frozenset(value for _field, value in self._resolver.entities())
        q_mentions = frozenset(
            value for (kind, value) in self._reverse.values() if kind is TokenKind.MENTION
        )
        return resolver_names | q_mentions

    def amounts(self) -> frozenset[Decimal]:
        """Every amount tokenised so far in this conversation. Unlike
        `names()` there is no "full universe" to draw on — the resolver
        only knows names, not amounts."""
        return frozenset(
            value for (kind, value) in self._reverse.values() if kind is TokenKind.AMOUNT
        )

    def _compiled_name_pattern(self, name: str) -> re.Pattern[str]:
        pattern = self._name_pattern_cache.get(name)
        if pattern is None:
            pattern = _value_boundary_pattern(name)
            self._name_pattern_cache[name] = pattern
        return pattern

    # ── ingress: tokenise_prompt ────────────────────────────────────────

    def tokenise_prompt(self, text: str) -> str:
        # review1 m1 ORCH ruling: a token-shaped literal the user typed is
        # rejected outright, at ingress, before anything else -- never
        # silently passed through (the old behaviour) and never trusted
        # later even once that exact token has been issued to someone else.
        found = TOKEN_RE.search(text)
        if found:
            raise UnknownTokenError(
                f"token codes cannot be typed: {found.group(0)!r} looks like a "
                "token this system issues, but ingress never trusts a literal "
                "token-shaped string typed by the user"
            )
        text = self._pass_amounts(text)
        text = self._match_windows(text, only_exact=True)
        text = self._match_windows(text, only_exact=False)
        return text

    def _pass_amounts(self, text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            if _is_excluded_amount(text, match):
                return match.group(0)
            value = parse_amount(match.group(0))
            if value is None:  # pragma: no cover - every `_AMOUNT_CANDIDATE_RE`
                # branch produces a strict subset of what `_PARSE_AMOUNT_RE`
                # accepts, so a real match here always parses; kept as a
                # guard against the two regexes drifting apart later (m4:
                # test_amount_candidate_and_parse_amount_regexes_stay_in_lockstep
                # pins this across a corpus covering every accepted form).
                return match.group(0)
            return self.token_for(TokenKind.AMOUNT, value)

        return _AMOUNT_CANDIDATE_RE.sub(repl, text)

    def _max_entity_words(self) -> int:
        longest = 1
        for _field, value in self._resolver.entities():
            longest = max(longest, len(value.split()))
        return longest

    def _match_windows(self, text: str, *, only_exact: bool) -> str:
        """Greedy longest-window-first entity matching over `text`'s
        already amount-substituted words.

        `only_exact=True` is pass 2: only an EXACT `resolver.resolve()`
        match consumes a window, tokenised B/D/G by `top.field`.
        `only_exact=False` is pass 3: a resolved-but-not-exact OR ambiguous
        match becomes a `Q` mention (KCH-236 confirm contract — the model
        must still ask before treating it as real); a window whose first
        word is a `NOISE_TOKENS` word never starts a pass-3 match. Either
        way, a window is skipped if any of its words were already consumed
        by an earlier (longer) match, and unmatched words pass through
        untouched (`no_match`).

        Each window's leading/trailing punctuation and a trailing
        possessive `'s`/'s are stripped before resolving (review1 B1/M4 ORCH
        rulings) and glued back onto whatever token is issued, so
        "Meera Iyer's exposure" tokenises to "D001's exposure" instead of
        losing the match (or the possessive) to the punctuation. Words are
        `_word_spans` (review2 NB2), not whitespace-delimited chunks, so a
        comma/slash/ampersand/dash/em-dash gluing two names together no
        longer makes either of them `no_match` -- each name's own spans are
        still found and windowed correctly, with the separator between them
        copied verbatim into the output untouched.
        """
        spans = _word_spans(text)
        n_words = len(spans)
        if n_words == 0:
            return text
        max_n = self._max_entity_words()  # review1 m5: no fixed ceiling
        replacements: list[tuple[int, int, str]] = []
        # `i` only ever advances by the size of the window just matched (or
        # by 1 when nothing matched at this position), so it strictly
        # increases and never revisits or looks behind an index a previous
        # iteration already consumed -- there is no "already consumed"
        # index left of `i`, and no unconsumed index right of it either.
        i = 0
        while i < n_words:
            upper = min(max_n, n_words - i)
            matched_size = 0
            for size in range(upper, 0, -1):
                first_word_raw = text[spans[i][0] : spans[i][1]]
                _, first_core, _ = _strip_window_edges(first_word_raw)
                if not only_exact and first_core.lower() in NOISE_TOKENS:
                    continue
                window_start = spans[i][0]
                window_end = spans[i + size - 1][1]
                prefix, core, suffix = _strip_window_edges(text[window_start:window_end])
                resolution = self._resolver.resolve(_fold_apostrophe(core))
                if only_exact:
                    hit = resolution.exact
                else:
                    hit = resolution.status in ("resolved", "ambiguous") and not resolution.exact
                if not hit:
                    continue
                if only_exact:
                    kind = NAME_KEYS[resolution.top.field]  # type: ignore[union-attr]
                    token = self.token_for(kind, resolution.top.value)  # type: ignore[union-attr]
                else:
                    token = self.token_for(TokenKind.MENTION, core)
                replacements.append((window_start, window_end, prefix + token + suffix))
                matched_size = size
                break
            i += matched_size if matched_size else 1
        if not replacements:
            return text
        out: list[str] = []
        last = 0
        for start, end, replacement in replacements:
            out.append(text[last:start])
            out.append(replacement)
            last = end
        out.append(text[last:])
        return "".join(out)

    # ── egress: tokenise_observation ────────────────────────────────────

    def tokenise_observation(self, obs: Mapping[str, Any]) -> dict[str, Any]:
        return self._tokenise_mapping(obs)

    def _tokenise_mapping(self, mapping: Mapping[str, Any]) -> dict[str, Any]:
        return {key: self._tokenise_field(key, value) for key, value in mapping.items()}

    def _tokenise_field(self, key: str, value: Any) -> Any:
        if key in NAME_KEYS:
            if isinstance(value, str) and value:
                return self.token_for(NAME_KEYS[key], value)
            return value
        if key in AMOUNT_KEYS:
            if value is None:
                return value
            return self.token_for(TokenKind.AMOUNT, Decimal(str(value)))
        if key == FORMATTED_KEY:
            if isinstance(value, str):
                parsed = parse_amount(value)
                if parsed is not None:
                    return self.token_for(TokenKind.AMOUNT, parsed)
            return value
        if key == _CANDIDATES_KEY and isinstance(value, list):
            return [self._tokenise_candidate(c) for c in value]
        if _is_passthrough_key(key):
            return self._recurse_generic(value)
        if key in FREE_TEXT_KEYS or key in CONTAINER_KEYS:
            return self._tokenise_free(value)
        # A genuinely unclassified key -- fail closed (review1 M3 ORCH
        # ruling) rather than silently pass a bare number through or hand
        # it to the free-text scrub fallback.
        return self._tokenise_unclassified(value)

    def _tokenise_unclassified(self, value: Any) -> Any:
        """A key none of the tables above name (KCH-243 DEBT: a brand-new
        READ-tool field nobody classified yet). Fail closed (review1 M3
        ORCH ruling): a bare int/float/Decimal, or a string that IS itself a
        numeric expression (`parse_amount` matches the whole string), is
        exactly the shape a real, unclassified amount would have -- raise
        rather than let it slip through untouched or get silently absorbed
        by the free-text scrub fallback. An ordinary string (prose,
        possibly WITH a number embedded), and a list/dict container, still
        go through `_tokenise_free` -- which applies this SAME numeric check
        at every depth it recurses into (review2 NM1 ORCH ruling)."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float, Decimal)):
            raise PlaintextLeakError(
                f"unclassified key carries a numeric value {value!r} -- add it to "
                "AMOUNT_KEYS/NAME_KEYS/PASSTHROUGH_KEYS (KCH-243 DEBT)"
            )
        if isinstance(value, str) and parse_amount(value) is not None:
            raise PlaintextLeakError(
                f"unclassified key carries a bare numeric string {value!r} -- add "
                "it to AMOUNT_KEYS/NAME_KEYS/PASSTHROUGH_KEYS (KCH-243 DEBT)"
            )
        return self._tokenise_free(value)

    def _tokenise_candidate(self, candidate: Any) -> Any:
        if not isinstance(candidate, Mapping):
            return candidate
        out = dict(candidate)
        kind = NAME_KEYS.get(candidate.get("field"))
        value = candidate.get("value")
        if kind is not None and isinstance(value, str) and value:
            out["value"] = self.token_for(kind, value)
        return out

    def _recurse_generic(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            return self._tokenise_mapping(value)
        if isinstance(value, list):
            return [self._recurse_generic(v) for v in value]
        return value

    def _tokenise_free(self, value: Any) -> Any:
        """Free text (a `FREE_TEXT_KEYS` value, a `CONTAINER_KEYS` value, or
        an unclassified key's non-numeric-string value): a string is
        scrubbed, a mapping is reclassified key-by-key (so a nested
        `months`/`rank`/etc. under `error`/`top` is still correctly
        passed through, never reaching the check below), a list recurses
        per item -- and at ANY depth this reaches, a bare non-bool
        int/float/Decimal scalar fails closed (review2 NM1 ORCH ruling: a
        free-text key holding a non-string, or a numeric leaf inside an
        unclassified list/nested-list, is a programmer error, e.g. the
        exact KCH-243 shapes `{"notes": [250000, "a"]}` or
        `{"x": [[250000]]}`)."""
        if isinstance(value, str):
            return self._scrub(value)
        if isinstance(value, Mapping):
            return self._tokenise_mapping(value)
        if isinstance(value, list):
            return [self._tokenise_free(v) for v in value]
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float, Decimal)):
            raise PlaintextLeakError(
                f"a free-text or unclassified field carries a bare numeric value "
                f"{value!r} -- a free-text key holding a non-string, or a numeric "
                "leaf inside an unclassified container, is a programmer error "
                "(KCH-243 DEBT)"
            )
        return value

    def _scrub(self, text: str) -> str:
        """Free text leaving the app (a tool's `next_action`, `message`,
        `notes`, `rejected_value`, or any key this module's tables do not
        name): (1) a SINGLE longest-first pass over every name this
        TokenMap already knows -- issued values (Q mentions included) AND
        the resolver's full entity universe, merged together (review1 M2
        ORCH ruling: two separate passes let an already-issued SHORT value
        like a Q mention ("iyer") get substituted inside a longer stored
        name ("meera iyer") before that longer name is ever tried, leaking
        the rest of it) -- then (2) any already-issued amount's literal
        rendering, then (3) any remaining money-shaped text via the same
        detector ingress uses."""
        text = self._scrub_names(text)
        text = self._scrub_issued_amounts(text)
        text = self._pass_amounts(text)
        return text

    def _scrub_names(self, text: str) -> str:
        tokens_by_value: dict[str, str] = {
            value: token
            for (kind, value), token in self._forward.items()
            if kind is not TokenKind.AMOUNT
        }
        kind_by_value: dict[str, TokenKind] = {}
        for field_name, value in self._resolver.entities():
            kind = NAME_KEYS.get(field_name)
            if kind is None or not value:
                continue
            kind_by_value.setdefault(value, kind)

        def repl(match: re.Match[str], value: str) -> str:
            token = tokens_by_value.get(value)
            if token is None:
                token = self.token_for(kind_by_value[value], value)
                tokens_by_value[value] = token
            return token

        for value in sorted(set(tokens_by_value) | set(kind_by_value), key=len, reverse=True):
            text = _value_boundary_pattern(value).sub(lambda m, v=value: repl(m, v), text)
        return text

    def _scrub_issued_amounts(self, text: str) -> str:
        amount_entries = [
            (key, token)
            for (kind, key), token in self._forward.items()
            if kind is TokenKind.AMOUNT
        ]
        for key, token in amount_entries:
            for rendering in sorted(_amount_text_variants(key), key=len, reverse=True):
                pattern = re.compile(rf"(?<!\w){re.escape(rendering)}(?!\w)")
                text = pattern.sub(token, text)
        return text

    # ── the model's tool-call arguments crossing back in ────────────────

    def detokenise_args(self, raw: str | Mapping[str, Any] | None) -> Any:
        """`raw` with every token substituted for the value it maps to, so
        `tool_registry.parse_args` sees the real argument the model meant
        (an amount as `int`/`Decimal`, a name as its stored string) rather
        than a token string a pydantic field would reject.

        A `raw` string that is not valid JSON is returned UNCHANGED —
        `parse_args` still raises its own `ToolArgsError` over it, keeping
        that error's existing meaning ("the model's call shape was
        malformed"), never masked by a detokenisation failure instead.
        `raw` is parsed with `parse_float=Decimal`, matching
        `tool_registry.parse_args` exactly, so a rate typed as a bare
        literal is never rounded through `float` before this function even
        sees it.

        Raises `UnknownTokenError` for any token-shaped substring (`TOKEN_RE`)
        that this `TokenMap` never issued — including one the model
        fabricated, one the user typed literally with no mapping behind it
        (see `test_user_typed_token_shaped_literal_is_rejected_at_ingress`),
        or one whose KIND does not match the argument field it was found
        under (review1 m6: a borrower token under `borrower_group`, etc.).
        """
        if raw is None or raw == "":
            return raw
        if isinstance(raw, str):
            try:
                data = json.loads(raw, parse_float=Decimal)
            except json.JSONDecodeError:
                return raw
        else:
            data = raw
        return self._detokenise_value(data, None)

    def _detokenise_value(self, value: Any, field: str | None) -> Any:
        if isinstance(value, str):
            return self._detokenise_string(value, field)
        if isinstance(value, Mapping):
            return {k: self._detokenise_value(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [self._detokenise_value(v, field) for v in value]
        return value

    def _check_field_kind(self, kind: TokenKind, field: str | None, token: str) -> None:
        if field is None:
            return
        expected = _FIELD_EXPECTED_KINDS.get(field)
        if expected is not None and kind not in expected:
            wanted = "/".join(sorted(k.value for k in expected))
            raise UnknownTokenError(
                f"{token!r} is a {kind.value}-kind token but {field!r} expects "
                f"{wanted} (KCH-238 review1 m6)"
            )

    def _detokenise_string(self, text: str, field: str | None) -> Any:
        whole = TOKEN_RE.fullmatch(text)
        if whole:
            kind, key = self._lookup(text)
            self._check_field_kind(kind, field, text)
            if kind is TokenKind.AMOUNT:
                return int(key) if key == key.to_integral_value() else key
            return key

        def repl(match: re.Match[str]) -> str:
            kind, key = self._lookup(match.group(0))
            self._check_field_kind(kind, field, match.group(0))
            if kind is TokenKind.AMOUNT:
                return str(int(key)) if key == key.to_integral_value() else str(key)
            return str(key)

        return TOKEN_RE.sub(repl, text)

    # ── final answer only ────────────────────────────────────────────────

    def rehydrate(self, text: str) -> str:
        """The model's final answer with every token it used replaced by
        something a human reads: `B`/`D`/`G` -> the stored value, `Q` -> the
        text the user originally typed, `AMOUNT_n` -> `format_inr(value)`.
        Unlike `detokenise_args`, an unmapped token is left exactly as
        written rather than raising — this is the last thing shown to a
        person, and a single bad token should not blank out an entire
        answer.
        """

        def repl(match: re.Match[str]) -> str:
            token = match.group(0)
            entry = self._reverse.get(token)
            if entry is None:
                return token
            kind, key = entry
            if kind is TokenKind.AMOUNT:
                return format_inr(key)
            return str(key)

        return TOKEN_RE.sub(repl, text)


def _walk_keyed_leaves(obj: Any, key: str | None = None):
    """(key, leaf) for every leaf under `obj` -- the immediate mapping key
    it sits under (or the enclosing mapping key, through a list), so callers
    can gate a check on the key without needing a separate walk."""
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            yield from _walk_keyed_leaves(v, k)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_keyed_leaves(v, key)
    else:
        yield key, obj


# review1 m2 ORCH ruling: an opaque identifier is never money or a name,
# whatever its shape -- skip both checks for a leaf sitting directly under
# one of these keys. `months`/`rate_percent`/etc. (duration/count/percentage
# fields, never rupees) are already in PASSTHROUGH_KEYS, reused here so
# `months: 3` never collides with a known AMOUNT 3 elsewhere in the same
# conversation.
_OPAQUE_ID_KEYS: frozenset[str] = frozenset({"id", "tool_call_id", "call_id"})
_NON_AMOUNT_NUMERIC_KEYS: frozenset[str] = PASSTHROUGH_KEYS | _OPAQUE_ID_KEYS


def _is_money_shaped_amount(amount: Decimal, rendering: str) -> bool:
    """True iff `rendering` (one of `_amount_text_variants(amount)`'s
    outputs) is distinctively money-shaped ON ITS OWN, with no surrounding
    currency/unit context needed to tell it apart from a rate, a month
    count, or a "top N" limit: it is a GROUPED rendering (has a comma), or
    the amount's own integer magnitude is >= 4 digits (review2 NM3 ORCH
    ruling). Checked on the amount's magnitude, not the rendering string's
    raw character count, so a 2-digit rate rendered as "12.00" (4 characters
    once the decimal point is stripped) is correctly NOT treated as
    4-digit-money-shaped."""
    if "," in rendering:
        return True
    integer_part = abs(int(amount.to_integral_value()))
    return len(str(integer_part)) >= 4


def assert_no_plaintext(body: Mapping[str, Any], token_map: TokenMap) -> None:
    """The last-resort guard immediately before a network call (ARB D-15,
    OQ-01 amended). Raises `PlaintextLeakError` the instant it finds, over
    every string leaf of `body["messages"]` (review1 m2 ORCH ruling: the
    guard scans MESSAGE CONTENT only -- never a tool schema, which carries
    static descriptions/bounds, not real data, and would otherwise brick a
    whole conversation over an ordinary word that happens to also be a
    stored name):

      - a known name (`token_map.names()` — every resolver entity plus every
        `Q` mention's typed text) as a whole value, case-insensitively;
      - `MONEY_RE` (a generic money-shaped string), OR a literal rendering
        of a known amount (`token_map.amounts()`, in 4 textual forms — this
        second check is why a bare amount as short as "5000" is still
        caught even though `MONEY_RE`'s bare-digit branch alone requires 5+
        digits) — over the string AND number leaves; a numeric leaf under a
        duration/count/percentage key or an opaque id key is never treated
        as money, however it compares to a known amount. The known-amount
        rendering check ALSO only fires when the amount itself is
        money-shaped (`_is_money_shaped_amount`: grouped, or >= 4 digits —
        review2 NM3 ORCH ruling), and uses the same lookbehind as `MONEY_RE`
        (`(?<![\\w.,/-])`), so a small known amount (a rate, a month count,
        a "top N" limit) is never flagged just because it also happens to
        be a `TokenMap` amount, and a fixed formula divisor (e.g. `/1200`
        inside a `basis` string) is never flagged either.

    This is a backstop, not the mechanism: a body built entirely from
    `tokenise_prompt`/`tokenise_observation` output should never trip it.
    """
    messages = body.get("messages")
    if messages is None:
        return

    for name in token_map.names():
        if not name:
            continue
        pattern = token_map._compiled_name_pattern(name)
        for key, leaf in _walk_keyed_leaves(messages):
            if key in _OPAQUE_ID_KEYS:
                continue
            if isinstance(leaf, str) and pattern.search(leaf):
                raise PlaintextLeakError(f"known name found in outbound body: {name!r}")

    amount_patterns = [
        re.compile(rf"(?<![\w.,/-]){re.escape(rendering)}(?!\w)")
        for amount in token_map.amounts()
        for rendering in _amount_text_variants(amount)
        if _is_money_shaped_amount(amount, rendering)
    ]
    for key, leaf in _walk_keyed_leaves(messages):
        if key in _OPAQUE_ID_KEYS:
            continue
        if isinstance(leaf, str):
            if MONEY_RE.search(leaf):
                raise PlaintextLeakError(f"money-shaped text found in outbound message: {leaf!r}")
            for pattern in amount_patterns:
                if pattern.search(leaf):
                    raise PlaintextLeakError(
                        f"known amount literal found in outbound message: {leaf!r}"
                    )
        elif isinstance(leaf, bool):
            continue
        elif isinstance(leaf, (int, float, Decimal)):
            if key in _NON_AMOUNT_NUMERIC_KEYS:
                continue
            leaf_decimal = Decimal(str(leaf))
            if leaf_decimal in token_map.amounts() and _is_money_shaped_amount(
                leaf_decimal, str(leaf)
            ):
                raise PlaintextLeakError(
                    f"known amount literal found in outbound message: {leaf!r}"
                )
