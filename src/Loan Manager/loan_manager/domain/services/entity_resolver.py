from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from difflib import SequenceMatcher

NAME_FIELDS: tuple[str, ...] = (
    "borrower_name",
    "borrower_group",
    "depositor_name",
    "depositor_group",
)

GROUP_FIELDS: tuple[str, ...] = ("borrower_group", "depositor_group")

THRESHOLD = 0.85

# [REVIEW REQUIRED] Fixed English stopword-style list. A borrower/depositor
# group genuinely named "Group Co" or "The Family Trust" loses those words
# from fuzzy matching. No i18n coverage either. Accepted for MVP1.1 because
# every fixture group name observed in the loan book is "<surname> group" or
# "<surname> family" and the false-negative cost of leaving these in (whole
# name required to match) was measured worse than the false-positive cost of
# stripping them.
NOISE_TOKENS = frozenset({"group", "grp", "family", "the", "co", "and"})

# ORCH ruling (review cycle 1): a query carrying one of these tokens is
# asking for a group specifically ("sharma group"), so the candidate search
# is restricted to the two *_group fields before scoring -- otherwise
# "sharma group" ties "sharma" (borrower_group) against "rohit sharma"
# (borrower_name, matched via the "sharma" token) and never resolves.
GROUP_HINT_TOKENS = frozenset({"group", "grp"})

_WS_RE = re.compile(r"\s+")
_SEP_RE = re.compile(r"[_-]+")
_DIGIT_RE = re.compile(r"\d+")
_RAW_WS_RE = re.compile(r"\s")

_SHORT_TOKEN_LEN = 3

# Review cycle 1, MAJOR #4: the whole-string path (single-word/compact
# queries only -- see _is_multi_word) over-credits a query that is a prefix
# of a longer, DIFFERENT name: ratio("sharma", "sharmila") = 0.857, above
# THRESHOLD, on six shared leading characters alone. "Sharmaa" -> "sharma"
# (edit distance 1: one doubled letter) must still resolve; "sharma" ->
# "sharmila" (edit distance 2: two inserted characters) must not. A plain
# ratio cutoff can't separate these -- ratio("iyr","iyer") is *also* 0.857 --
# so the whole-string path additionally requires the edit distance itself to
# be small. Underscore/hyphen-JOINED compact codes typed with no real space
# ("bg_13" vs "bg13", "b_1" vs "b1") differ by exactly the separator,
# distance 1, so this does not regress them.
#
# Review cycle 2, MAJOR #2 (correcting the claim above): a code typed with a
# literal SPACE ("BG 13") is a *different* case -- real whitespace makes
# _is_multi_word true, so it never reaches this whole-string path at all; it
# is scored via token-only, and no single token clears the gate ("bg" is a
# short token needing equality, "13" is not itself a token of the compact
# value "bg13"). That gap is closed separately, by the collapsed-form
# equality check in `score()` below -- not by this edit-distance mechanism.
_COMPACT_MAX_EDIT_DISTANCE = 1


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = _SEP_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _collapse(normalized: str) -> str:
    """`normalized` with every space removed -- the fully-joined form of a
    reference code, so "bg 13" and "bg13" collapse to the same string.
    Callers pass already-normalised text (underscore/hyphen already folded
    to space by `_normalize`), so removing spaces removes every separator.
    """
    return normalized.replace(" ", "")


def _is_exact(query: str, value: str) -> bool:
    """True iff `value` is an exact normalised OR collapsed match for
    `query` -- the two cases `score()` credits with 1.0 without any fuzzy
    slack (plain equality once case/whitespace/separators are folded, or
    equality once every remaining space is also removed, e.g. "BG 13" vs
    stored "bg13"). Backs both `Resolution.status`'s exact-wins rule and
    `Resolution.exact` (review cycle 2, ORCH ruling): a resolve is only
    ever "exact" through one of these two equalities, never through a
    fuzzy ratio, however high.

    Post-review fix (KCH-236): the collapsed-form equality alone is not
    enough -- "bg1 0" collapses to "bg10", identical to stored "bg10"'s
    collapsed form, even though "bg1" is the intended (and separately
    stored) match. The collapse check additionally requires the digit RUNS
    of each side to match: "bg1 0" has runs ("1", "0"); "bg10" has the
    single run ("10") -- they differ, so this is not an exact collapsed
    match. "BG 13" (runs ("13",)) vs stored "bg13" (runs ("13",)) is
    unaffected.
    """
    query_norm = _normalize(query)
    value_norm = _normalize(value)
    if not query_norm or not value_norm:
        return False
    return query_norm == value_norm or (
        _collapse(query_norm) == _collapse(value_norm)
        and _digit_runs(query_norm) == _digit_runs(value_norm)
    )


def _is_multi_word(query: str) -> bool:
    """True iff the caller typed real whitespace, before _/- substitution.

    Distinguishes a natural-language, multi-word query ("anil kumar",
    "sharma group" -- real space) from a single compact identifier typed
    with an underscore or hyphen joiner ("bg_13", "rohit-sharma" -- no real
    space, one logical token once normalized). Only the former is restricted
    to token-only scoring (MAJOR #4); the latter keeps the whole-string path
    so separator normalisation keeps working.
    """
    return bool(_RAW_WS_RE.search(query.strip()))


def _digit_runs(text: str) -> tuple[str, ...]:
    return tuple(_DIGIT_RE.findall(text))


def _digit_guard_blocks(a: str, b: str) -> bool:
    """True when both sides carry digits and those digit runs differ.

    "bg1" must not match "bg10" or "bg13": ordinary ratio scoring puts all
    three at 0.75-0.86, above THRESHOLD, purely on the shared "bg" prefix. A
    reference-code family like this is exactly where fuzzy text matching is
    the wrong tool, so digits are compared for equality, not similarity.
    """
    digits_a, digits_b = _digit_runs(a), _digit_runs(b)
    return bool(digits_a) and bool(digits_b) and digits_a != digits_b


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _levenshtein(a: str, b: str) -> int:
    """Optimal String Alignment (restricted Damerau-Levenshtein): plain
    Levenshtein plus an adjacent-transposition move costing 1.

    Review cycle 2, MAJOR #1: plain Levenshtein prices an adjacent swap as
    2 (delete+insert, or two substitutions), so _guarded_ratio zeroed real
    keystroke-adjacent-swap typos past _COMPACT_MAX_EDIT_DISTANCE=1 --
    "agrawal"->"agarwal", "kulkanri"->"kulkarni", "malhtora"->"malhotra",
    "venaktesh"->"venkatesh", "srinviasan"->"srinivasan" (all one adjacent
    swap, OSA distance 1; measured ratios 0.857-0.9, all >= THRESHOLD once
    let through). "Restricted" (a transposed pair may not be edited again
    afterwards) is enough here -- names are short and this is a threshold
    gate, not an alignment -- and it does not shrink non-transposition
    distances: "sharma"/"sharmila" (two insertions, no adjacent swap)
    stays at 2, still past the gate, still no_match.
    """
    if a == b:
        return 0
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cb = b[j - 1]
            cost = 0 if ca == cb else 1
            d[i][j] = min(
                d[i - 1][j] + 1,  # deletion
                d[i][j - 1] + 1,  # insertion
                d[i - 1][j - 1] + cost,  # substitution
            )
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)  # transposition
    return d[la][lb]


def _guarded_ratio(a: str, b: str) -> float:
    """ratio(a, b), zeroed by the digit guard or by an edit distance beyond
    _COMPACT_MAX_EDIT_DISTANCE. Shared by the whole-string comparison and by
    per-token comparison: a query with exactly one token IS a whole-string
    comparison, so both paths need the same guards -- otherwise a
    single-token query ("sharma" vs "sharmila", ratio 0.857) sails through
    on the token path even after the whole-string path rejects it.
    """
    if _digit_guard_blocks(a, b):
        return 0.0
    if _levenshtein(a, b) > _COMPACT_MAX_EDIT_DISTANCE:
        return 0.0
    return _ratio(a, b)


def _token_ratio(query_token: str, value_token: str) -> float:
    if len(query_token) < _SHORT_TOKEN_LEN:
        # A short token ("b1", "dg") is mostly its own prefix of any longer
        # token, so ordinary ratio scoring over-credits it. Require equality.
        return 1.0 if query_token == value_token else 0.0
    return _guarded_ratio(query_token, value_token)


def _token_score(query_tokens: tuple[str, ...], value_tokens: tuple[str, ...]) -> float:
    if not query_tokens or not value_tokens:
        return 0.0
    return min(
        max(_token_ratio(q, v) for v in value_tokens) for q in query_tokens
    )


@dataclass(frozen=True)
class Candidate:
    field: str
    value: str  # the ORIGINAL stored value, never the normalised form
    score: float
    rank: int  # 1-based


@dataclass(frozen=True)
class Resolution:
    query: str
    candidates: tuple[Candidate, ...] = field(default_factory=tuple)

    @property
    def _exact_candidates(self) -> tuple[Candidate, ...]:
        return tuple(c for c in self.candidates if _is_exact(self.query, c.value))

    @property
    def status(self) -> str:
        """"resolved" | "ambiguous" | "no_match".

        ORCH ruling (review cycle 1, supersedes the original exact-wins
        rule): an exact normalised match resolves ONLY when it is the
        UNIQUE top-scoring candidate. If some other candidate ties it at
        score 1.0 (e.g. "sharma" exact vs "rohit sharma" token-matched, both
        1.0), the result is ambiguous -- a wrong pick costs more than one
        extra clarifying question. With no exact match at all, a lone
        candidate still resolves; two or more is ambiguous.
        """
        if not self.candidates:
            return "no_match"
        max_score = max(c.score for c in self.candidates)
        top_scorers = [c for c in self.candidates if c.score == max_score]
        if self._exact_candidates:
            return "resolved" if len(top_scorers) == 1 else "ambiguous"
        if len(self.candidates) == 1:
            return "resolved"
        return "ambiguous"

    @property
    def ambiguous(self) -> bool:
        return self.status == "ambiguous"

    @property
    def top(self) -> Candidate | None:
        """The resolved candidate, or None. Never a guess among ties.

        Review cycle 2, MINOR #4 (dead-branch simplification): an exact
        match always scores 1.0, the maximum any candidate can reach, so
        whenever `_exact_candidates` is non-empty it is a subset of the
        score==max_score top scorers; `status` only returns "resolved" in
        that branch when there is exactly one such top scorer, which must
        then be the exact one -- and `candidates` is already sorted
        highest-score-first, so it is `candidates[0]`. In the other
        "resolved" branch (no exact match, exactly one candidate)
        `candidates[0]` is trivially the answer. `exact[0] if exact else
        candidates[0]` and plain `candidates[0]` are therefore the same
        value in every case this property can be reached.
        """
        if self.status != "resolved":
            return None
        return self.candidates[0]

    @property
    def top2(self) -> tuple[Candidate, ...]:
        """The two highest-ranked candidates, for surfacing an ambiguity."""
        return self.candidates[:2]

    @property
    def exact(self) -> bool:
        """True iff `status == "resolved"` and `top` is an exact
        normalised-or-collapsed match for the query (see `_is_exact`) --
        never merely a high fuzzy ratio.

        KCH-238/239 contract: a tool acting on a resolve where `exact` is
        False MUST confirm with the user ("did you mean <top.value>?")
        before treating it as the answer -- e.g. a one-insertion pair like
        "amit shah"/"amita shah" or "krishna iyer"/"krishnan iyer" can
        resolve (single stored candidate, score >= THRESHOLD) while naming
        the wrong person. Only an `exact` resolve may act without asking.
        """
        if self.status != "resolved":
            return False
        return _is_exact(self.query, self.top.value)


class EntityResolver:
    """Maps free-text agent-tool input to the exact stored values it means.

    KCH-229 made autocomplete/filter matching exact against a blind index;
    this closes the gap for conversational input, where a user types
    "sharma group" or "iyer" and means a specific stored borrower_group or
    depositor_name value. Domain-layer, stdlib-only (Ponytail rung 4):
    difflib.SequenceMatcher: no rapidfuzz/fuzzywuzzy dependency for a
    threshold check over a few hundred short strings.

    Candidates and `entities()` always carry the ORIGINAL stored value, not
    its normalised form: the blind-index filter downstream
    (finhive/db/blind_index.py, sqlalchemy_loan_repo.py) computes its index
    over `strip().lower()` of the stored plaintext, not this resolver's
    normalisation (which also folds "_"/"-" to space) -- returning "iyer
    chem" for a row stored as "iyer_chem" would never match that index. Two
    distinct stored values that happen to normalise the same way (e.g.
    "iyer_chem" and "iyer chem" really are two different rows) stay two
    distinct entities/candidates.
    """

    def __init__(
        self, values: Mapping[str, Iterable[str]], threshold: float = THRESHOLD
    ) -> None:
        for field_name in values:
            if field_name not in NAME_FIELDS:
                raise ValueError(f"Unknown field: {field_name!r}")
        self._threshold = threshold
        self._values: dict[str, tuple[str, ...]] = {}
        for field_name in NAME_FIELDS:
            raw = values.get(field_name, ())
            seen: dict[str, None] = {}
            for v in raw:
                if v is None or not v.strip():
                    continue
                seen.setdefault(v, None)  # dedupe on the ORIGINAL string
            self._values[field_name] = tuple(seen.keys())

    def entities(self) -> tuple[tuple[str, str], ...]:
        field_index = {f: i for i, f in enumerate(NAME_FIELDS)}
        pairs = [
            (field_name, value)
            for field_name in NAME_FIELDS
            for value in self._values[field_name]
        ]
        pairs.sort(key=lambda pair: (field_index[pair[0]], pair[1]))
        return tuple(pairs)

    def resolve(self, text: str) -> Resolution:
        query_norm = _normalize(text)
        query_tokens = tuple(query_norm.split(" ")) if query_norm else ()
        if any(t in GROUP_HINT_TOKENS for t in query_tokens):
            fields_to_search = GROUP_FIELDS
        else:
            fields_to_search = NAME_FIELDS

        field_index = {f: i for i, f in enumerate(NAME_FIELDS)}
        scored: list[tuple[str, str, float]] = []
        for field_name in fields_to_search:
            for value in self._values[field_name]:
                score = self.score(text, value)
                if score >= self._threshold:
                    scored.append((field_name, value, score))
        scored.sort(key=lambda row: (-row[2], field_index[row[0]], row[1]))
        candidates = tuple(
            Candidate(field=f, value=v, score=s, rank=i + 1)
            for i, (f, v, s) in enumerate(scored)
        )
        return Resolution(query=text, candidates=candidates)

    @staticmethod
    def score(query: str, value: str) -> float:
        """No substring shortcut anywhere: a naive `if q in v: score = 0.9`
        would match "bg" against "bg1"/"bg10"/"bg13" indiscriminately and
        "zzz" against nothing correctly only by accident. Every score comes
        from ratio/digit-guard/short-token/edit-distance rules below,
        uniformly.
        """
        query_norm = _normalize(query)
        value_norm = _normalize(value)
        if not query_norm or not value_norm:
            return 0.0

        if _collapse(query_norm) == _collapse(value_norm) and _digit_runs(
            query_norm
        ) == _digit_runs(value_norm):
            # Review cycle 2, MAJOR #2: a code typed with a literal space
            # ("BG 13") normalises to "bg 13" -- multi-word, so it never
            # reaches the whole-string path below, and no token
            # independently clears the gate either. Collapsed-form
            # equality scores it 1.0 directly, ahead of both paths.
            # Equality only, never a ratio over collapsed forms: a ratio
            # here would reopen the exact bg1/bg10/bg13 hole the digit
            # guard closes below.
            #
            # Post-review fix (KCH-236): collapsed-form equality ALONE is
            # not enough -- "bg1 0" collapses to "bg10", same as stored
            # "bg10", even though the space marks two separate digit runs
            # ("1", "0") that don't match "bg10"'s single run ("10"). The
            # added digit-run equality closes that hole while leaving
            # "BG 13" (single run "13" both sides) unaffected.
            return 1.0

        query_tokens = tuple(query_norm.split(" "))
        value_tokens = tuple(value_norm.split(" "))
        filtered_tokens = tuple(t for t in query_tokens if t not in NOISE_TOKENS)
        if not filtered_tokens:
            filtered_tokens = query_tokens
        token = _token_score(filtered_tokens, value_tokens)

        if _is_multi_word(query):
            # MAJOR #4: a real multi-word query ("anil kumar", "ramesh
            # rao") never falls back to whole-string ratio. Whole-string
            # ratio over full names shares too many characters across
            # genuinely different people ("anil kumar"/"sunil kumar" =
            # 0.857) for it to be safe; per-token scoring (each word must
            # itself clear THRESHOLD against some value token) does not.
            return token

        if len(query_norm) < _SHORT_TOKEN_LEN:
            # Same rule as _token_ratio, applied to the whole-string path:
            # a short query ("am", "b1") is a near-prefix of almost
            # anything, so ratio() over-credits it (score("am","amc")
            # would otherwise be 0.8). Require equality.
            whole = 1.0 if query_norm == value_norm else 0.0
        else:
            whole = _guarded_ratio(query_norm, value_norm)

        return max(whole, token)
