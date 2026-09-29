"""EntityIndex: one scan of a text against the loan book's name universe
(KCH-238R redesign; ARB D-15, OQ-01 amended).

Cycle 2 asked the fuzzy `EntityResolver` about every word window of a prompt
(one resolve ~63 ms at 1,017 names). This index inverts that: the stored
names are indexed once per `TokenMap`, and a text is scanned once, left to
right, longest match first. The resolver is only consulted for the tiny tie
set that could make a whole-name match EXACT, so the exactness rules stay
in KCH-236 (`EntityResolver`), not here.

View. Every character is folded before lookup: NFKC, casefold, the
apostrophe look-alikes ’ʼ‘`´ -> ', Latin accents dropped (a combining mark
after a Latin letter), format characters (category Cf: ZWSP, ZWJ, soft
hyphen) dropped. Each view character remembers the original offset it came
from, so a hit always maps back to the exact original span.

Runs. A run is a maximal stretch of letters, digits and combining marks in
ONE script (ASCII digits join any script). Everything else -- space, _ - .
' , / & — : and so on -- separates runs, and so does a change of script
("sharmaजी" is two runs). A span the caller marks opaque (an issued token)
is a hard break no match may cross.

Tables (built from the resolver's active values plus the caller's
`protected` values -- owner decision D3):
  FULL     collapsed value (its runs joined) -> [(field, value, digit runs)]
  PART     name word (>= 3 chars, not a noise word, not all digits) ->
           fields; "weak" when the word is a safe word AND only ever part
           of a group (e.g. "sons" in "gupta & sons")
  INV      resolver-style token -> active (field, value), for the tie set
  DEL1     every 1-deletion of a PART word -> PART words (SymSpell, d=1)
  DYNAMIC  collapsed text of every issued Q/N token -> that token

Scan, at each run, longest first:
  1. whole name: consecutive runs joined, separator-blind, in FULL (digit
     runs must match) or DYNAMIC; if not, the same minus an honorific
     suffix on the last run (ji/jee/bhai/...). The whole run is always
     tried before the suffix is peeled, so a stored "premji" is never split,
     and a hit found ONLY by peeling is a Q of the FULL typed text, never
     exact ("vishwas" is not stored "vishwa" -- review 1 M1 ruling).
  2. else one run: a PART word, a PART word + honorific suffix, a typo of a
     PART word (DEL1 candidates, then `EntityResolver.score` >= THRESHOLD),
     or -- ingress only -- an unknown non-safe word -> novel name (N).
  Precedence: known name > safe word > typo > unknown.
Ingress then merges adjacent partial hits (Q/N) across whitespace, "." and
"-", and a following "group/family/grp" joins one. An exact whole name is
never merged.

Modes: INGRESS (the user's prompt, and a tool echoing user text) uses all of
the above. SYSTEM (tool-authored text, and the leak guard) uses whole names,
DYNAMIC and distinctive parts only (>= 4 chars, not a safe word, plus a
suffix); no typo, no N -- system text never invents a novel name, and a
guard that flagged every unknown word would brick every conversation.

Stdlib only; no PySide6/sqlalchemy/sqlite3 (application layer).
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum

from loan_manager.application.agent.safe_words import SAFE_WORDS
from loan_manager.domain.services.entity_resolver import (
    GROUP_FIELDS,
    NAME_FIELDS,
    NOISE_TOKENS,
    THRESHOLD,
    EntityResolver,
)

_MIN_STEM = 3
_MIN_PART = 3
_MIN_DISTINCT_PART = 4
_JOIN_WORDS = frozenset({"group", "family", "grp"})
_MERGE_SEPARATORS = frozenset(" .-")
_DIGIT_RE = re.compile(r"\d+")
_RESOLVER_SEP_RE = re.compile(r"[_-]+")
_RESOLVER_WS_RE = re.compile(r"\s+")

_APOSTROPHES = {"’": "'", "ʼ": "'", "‘": "'", "`": "'", "´": "'"}

# Glued Indian honorifics (review 3 F1, review 4 m-R7) plus a plain
# plural/possessive "s". Longest first, so "bhaiya" is tried before "bhai".
HONORIFIC_SUFFIXES: tuple[str, ...] = tuple(
    sorted(
        {"ji", "jee", "bhai", "bhaiya", "ben", "behen", "didi", "sahab", "saheb",
         "sahib", "saab", "s", "जी", "भाई"},
        key=lambda s: (-len(s), s),
    )
)
_MAX_SUFFIX = max(len(s) for s in HONORIFIC_SUFFIXES)
_SUFFIXES_BY_LAST: dict[str, tuple[str, ...]] = {}
for _suffix in HONORIFIC_SUFFIXES:
    _SUFFIXES_BY_LAST[_suffix[-1]] = (*_SUFFIXES_BY_LAST.get(_suffix[-1], ()), _suffix)


def _suffixes_of(word: str) -> tuple[str, ...]:
    """Honorific suffixes `word` ends with, longest first, leaving a stem of
    at least 3 characters."""
    return tuple(
        s
        for s in _SUFFIXES_BY_LAST.get(word[-1:], ())
        if word.endswith(s) and len(word) - len(s) >= _MIN_STEM
    )


class ScanMode(Enum):
    INGRESS = "ingress"
    SYSTEM = "system"


class HitKind(Enum):
    ENTITY = "entity"  # an exact stored value -> B/D/G
    MENTION = "mention"  # a stored-name part, typo, or non-exact whole -> Q
    NOVEL = "novel"  # an unknown non-safe word -> N
    REUSE = "reuse"  # text of an already-issued Q/N token -> that token


@dataclass(frozen=True)
class Hit:
    """One span to replace. `start`/`end` are ORIGINAL offsets; for a hit
    with a peeled honorific, `end` is where the suffix starts (the suffix
    stays in the text). `value` is the stored value (ENTITY) or the token
    (REUSE). `key` is the collapsed folded text, `words` its runs."""

    start: int
    end: int
    kind: HitKind
    key: str
    words: tuple[str, ...]
    first_run: int
    last_run: int
    field: str | None = None
    value: str | None = None
    suffixed: bool = False


@dataclass(frozen=True)
class _Run:
    vs: int
    ve: int
    word: str
    brk: bool  # an opaque span sits between this run and the previous one


@dataclass
class _View:
    text: str
    src: list[int] | None  # original offset per view char; None = identity
    n_orig: int

    def orig_start(self, v: int) -> int:
        return v if self.src is None else self.src[v]

    def orig_end(self, v: int) -> int:
        """Original offset where view position `v` (exclusive end) maps:
        the start of the next kept character, so dropped characters (an
        accent, a ZWSP) inside or right after a run go with it."""
        if self.src is None:
            return v
        if v >= len(self.src):
            return self.n_orig
        if v > 0 and self.src[v] == self.src[v - 1]:
            return self.src[v] + 1  # middle of one character's expansion
        return self.src[v]


def _is_latin_letter(c: str) -> bool:
    """a-z, or a letter in Latin-1 Supplement / Latin Extended-A/B /
    Latin Extended Additional."""
    if "a" <= c <= "z":
        return True
    return ("\u00c0" <= c <= "\u024f" or "\u1e00" <= c <= "\u1eff") and c.isalpha()


def _is_word(c: str) -> bool:
    return c.isalnum() or unicodedata.category(c)[0] == "M"


def _script(c: str) -> object:
    """Coarse script of a word character; None joins any script (ASCII
    digits, combining marks)."""
    if "0" <= c <= "9" or unicodedata.category(c)[0] == "M":
        return None
    if _is_latin_letter(c):
        return "L"
    o = ord(c)
    if 0x0900 <= o <= 0x097F or 0xA8E0 <= o <= 0xA8FF:
        return "D"
    return o >> 7


_ASCII_CHUNK_RE = re.compile(r"[\x00-\x7f]+")
# Maximal stretches free of ASCII separators (controls, space, punctuation,
# "_"); an ASCII-only stretch is exactly one run.
_CHUNK_RE = re.compile(r"[^\x00-\x2f\x3a-\x40\x5b-\x60\x7b-\x7f]+")


def fold(text: str, opaque: Iterable[tuple[int, int]] = ()) -> _View:
    """The folded view of `text` (see module docstring). Characters inside
    an `opaque` span become "\\x00", a separator that also marks a hard
    break. Pure-ASCII text (the common case) takes a C-speed path whose
    offsets are the identity."""
    n_orig = len(text)
    for a, b in sorted(opaque, reverse=True):
        text = text[:a] + "\x00" * (b - a) + text[b:]
    if text.isascii():
        lowered = text.lower()
        return _View("'".join(lowered.split("`")) if "`" in lowered else lowered, None, n_orig)
    out: list[str] = []
    src: list[int] = []
    prev_latin = False
    pos = 0
    for m in _ASCII_CHUNK_RE.finditer(text):
        for i in range(pos, m.start()):
            prev_latin = _fold_char(text[i], i, out, src, prev_latin)
        chunk = m.group(0).lower().replace("`", "'")
        out.append(chunk)
        src.extend(range(m.start(), m.end()))
        prev_latin = "a" <= chunk[-1] <= "z"
        pos = m.end()
    for i in range(pos, len(text)):
        prev_latin = _fold_char(text[i], i, out, src, prev_latin)
    return _View("".join(out), src, n_orig)


def _fold_char(ch: str, i: int, out: list[str], src: list[int], prev_latin: bool) -> bool:
    """Fold one non-ASCII character into `out`/`src`; returns whether the
    view now ends in a Latin letter."""
    if unicodedata.category(ch) == "Cf":
        return prev_latin
    ch = _APOSTROPHES.get(ch, ch)
    for c in unicodedata.normalize("NFKC", ch).casefold():
        if unicodedata.category(c)[0] == "M":
            if not prev_latin:  # a Latin accent is dropped, any other mark kept
                out.append(c)
                src.append(i)
            continue
        base = unicodedata.normalize("NFD", c)
        if len(base) > 1 and _is_latin_letter(base[0]):
            c = base[0]
        out.append(c)
        src.append(i)
        prev_latin = _is_latin_letter(c)
    return prev_latin


def _runs(view: str) -> list[_Run]:
    runs: list[_Run] = []
    last_end = 0
    for m in _CHUNK_RE.finditer(view):
        brk = "\x00" in view[last_end : m.start()]
        chunk = m.group(0)
        if chunk.isascii():
            runs.append(_Run(m.start(), m.end(), chunk, brk))
        else:
            _split_chunk(view, m.start(), m.end(), brk, runs)
        last_end = m.end()
    return runs


def _split_chunk(view: str, k: int, end: int, brk: bool, runs: list[_Run]) -> None:
    """Runs inside one non-ASCII chunk: non-word characters ("×", "—",
    "₹") separate, and so does a change of script."""
    while k < end:
        if not _is_word(view[k]):
            k += 1
            continue
        start = k
        script: object = None
        while k < end:
            c = view[k]
            if not _is_word(c):
                break
            s = _script(c)
            if s is not None:
                if script is None:
                    script = s
                elif s != script:
                    break
            k += 1
        runs.append(_Run(start, k, view[start:k], brk))
        brk = False


def _digit_runs(words: Iterable[str]) -> tuple[str, ...]:
    return tuple(d for w in words for d in _DIGIT_RE.findall(w))


def _deletes(word: str) -> set[str]:
    return {word[:k] + word[k + 1 :] for k in range(len(word))}


def _resolver_tokens(text: str) -> list[str]:
    """Tokens exactly as `EntityResolver._normalize` splits a string
    (lowercase, "_"/"-" -> space, whitespace runs -> one space). Used only
    to find the tie set; the differential test pins the equivalence."""
    norm = _RESOLVER_WS_RE.sub(" ", _RESOLVER_SEP_RE.sub(" ", text.strip().lower())).strip()
    return norm.split(" ") if norm else []


def _novel_shaped(word: str) -> bool:
    """A plausible name word: >= 3 characters, letters and marks only, no
    digit (a code, id or date fragment is never a novel name)."""
    return len(word) >= _MIN_PART and all(
        c.isalpha() or unicodedata.category(c)[0] == "M" for c in word
    )


_MISS = object()


class EntityIndex:
    def __init__(
        self,
        resolver: EntityResolver,
        protected: Mapping[str, Iterable[str]] | None = None,
        safe_words: frozenset[str] = SAFE_WORDS,
    ) -> None:
        self._safe = safe_words
        active = [
            (f, v) for f, v in resolver.entities() if f in NAME_FIELDS and v and v.strip()
        ]
        self._active = frozenset(active)
        entries = list(active)
        seen = set(active)
        for field_name in NAME_FIELDS:
            for value in (protected or {}).get(field_name, ()):
                if value and value.strip() and (field_name, value) not in seen:
                    seen.add((field_name, value))
                    entries.append((field_name, value))
        self.entries: tuple[tuple[str, str], ...] = tuple(entries)

        self._full: dict[str, list[tuple[str, str, tuple[str, ...]]]] = {}
        part_fields: dict[str, set[str]] = {}
        self._inv: dict[str, set[tuple[str, str]]] = {}
        for field_name, value in entries:
            words = [r.word for r in _runs(fold(value).text)]
            key = "".join(words)
            if not key:
                continue
            self._full.setdefault(key, []).append((field_name, value, _digit_runs(words)))
            for w in words:
                if len(w) >= _MIN_PART and not w.isdigit() and w not in NOISE_TOKENS:
                    part_fields.setdefault(w, set()).add(field_name)
            if (field_name, value) in self._active:
                for t in _resolver_tokens(value):
                    self._inv.setdefault(t, set()).add((field_name, value))
        group_fields = set(GROUP_FIELDS)
        self._strong = frozenset(
            w for w, fs in part_fields.items() if not (w in safe_words and fs <= group_fields)
        )
        self._distinct = frozenset(
            w for w in part_fields if len(w) >= _MIN_DISTINCT_PART and w not in safe_words
        )
        self._parts = frozenset(part_fields)
        self._max_part = max((len(w) for w in part_fields), default=0)
        self._del1: dict[str, set[str]] = {}
        for w in part_fields:
            for d in {w} | _deletes(w):
                self._del1.setdefault(d, set()).add(w)
        self._prefixes: set[str] = {k[:i] for k in self._full for i in range(1, len(k) + 1)}
        self._max_key = max((len(k) for k in self._full), default=0)
        self._dynamic: dict[str, str] = {}
        self._exact_memo: dict[str, tuple[str, str] | None] = {}

    # ── dynamic (issued Q/N) texts ──────────────────────────────────────

    def add_dynamic(self, key: str, token: str) -> None:
        if key and key not in self._dynamic:
            self._dynamic[key] = token
            self._prefixes.update(key[:i] for i in range(1, len(key) + 1))
            self._max_key = max(self._max_key, len(key))

    def dynamic_token(self, key: str) -> str | None:
        return self._dynamic.get(key)

    # ── exactness via the real resolver over the tie set ────────────────

    def exact_entity(self, text: str) -> tuple[str, str] | None:
        """(field, value) iff `EntityResolver.resolve(text).exact` over the
        ACTIVE universe would say so. Only values that can score 1.0 can
        make a resolve exact (the unique top scorer must be an exact match,
        and 1.0 is the maximum), and a value scores 1.0 only by collapsed
        equality (FULL) or by containing every non-noise query token (INV).
        So the real resolver is run over that tie set only. Memoised."""
        cached = self._exact_memo.get(text, _MISS)
        if cached is not _MISS:
            return cached  # type: ignore[return-value]
        key = "".join(r.word for r in _runs(fold(text).text))
        tie = {(f, v) for f, v, _d in self._full.get(key, ()) if (f, v) in self._active}
        tokens = _resolver_tokens(text)
        filtered = [t for t in tokens if t not in NOISE_TOKENS] or tokens
        common: set[tuple[str, str]] | None = None
        for t in filtered:
            found = self._inv.get(t, set())
            common = found if common is None else common & found
            if not common:
                break
        tie |= common or set()
        result: tuple[str, str] | None = None
        if tie:
            values: dict[str, list[str]] = {}
            for f, v in sorted(tie):
                values.setdefault(f, []).append(v)
            resolution = EntityResolver(values).resolve(text)
            if resolution.exact and resolution.top is not None:
                result = (resolution.top.field, resolution.top.value)
        self._exact_memo[text] = result
        return result

    # ── scan ─────────────────────────────────────────────────────────────

    def scan(
        self,
        text: str,
        mode: ScanMode,
        opaque: Iterable[tuple[int, int]] = (),
        *,
        first_only: bool = False,
    ) -> list[Hit]:
        return self._scan_view(fold(text, opaque), mode, first_only)

    def _scan_view(
        self, view: _View, mode: ScanMode, first_only: bool = False, dynamic: bool = True
    ) -> list[Hit]:
        runs = _runs(view.text)
        hits: list[Hit] = []
        i = 0
        while i < len(runs):
            hit = self._whole_at(view, runs, i, mode, dynamic) or self._single_at(
                view, runs, i, mode
            )
            if hit is not None:
                hits.append(hit)
                if first_only:
                    return hits
                i = hit.last_run + 1
            else:
                i += 1
        if mode is ScanMode.INGRESS:
            hits = self._merge(view, runs, hits)
        return hits

    def first_leak(
        self, text: str, opaque: Iterable[tuple[int, int]] = (), *, dynamic: bool = True
    ) -> str | None:
        """The collapsed text of the first name the guard must not let leave
        -- G1 whole names, G2 distinctive parts and, with `dynamic`, G3
        issued Q/N texts -- or None."""
        hits = self._scan_view(fold(text, opaque), ScanMode.SYSTEM, True, dynamic)
        return hits[0].key if hits else None

    def _span_hit(
        self,
        view: _View,
        runs: list[_Run],
        i: int,
        j: int,
        kind: HitKind,
        key: str,
        *,
        suffixed: bool = False,
        **extra: object,
    ) -> Hit:
        return Hit(
            start=view.orig_start(runs[i].vs),
            end=view.orig_end(runs[j].ve),
            kind=kind,
            key=key,
            words=tuple(r.word for r in runs[i : j + 1]),
            first_run=i,
            last_run=j,
            suffixed=suffixed,
            **extra,  # type: ignore[arg-type]
        )

    def _peeled_hit(self, view: _View, runs: list[_Run], i: int, j: int) -> Hit:
        """Review 1 M1 ruling: a name found ONLY by peeling a suffix is never
        exact -- "vishwas" is not stored "vishwa", "sai balaji" is not "sai
        bala" -- so it is a Q carrying the FULL typed text, and the KCH-236
        confirm step always applies."""
        key = "".join(r.word for r in runs[i : j + 1])
        return self._span_hit(view, runs, i, j, HitKind.MENTION, key, suffixed=True)

    def _whole_at(
        self, view: _View, runs: list[_Run], i: int, mode: ScanMode, dynamic: bool
    ) -> Hit | None:
        windows: list[tuple[int, str]] = []
        acc = ""
        for j in range(i, len(runs)):
            if j > i and runs[j].brk:
                break
            acc += runs[j].word
            if len(acc) > self._max_key + _MAX_SUFFIX:
                break
            windows.append((j, acc))
            if acc not in self._prefixes:
                break
        for j, acc in reversed(windows):
            hit = self._whole_hit(view, runs, i, j, acc, 0, mode, dynamic)
            if hit is not None:
                return hit
            for suf in _suffixes_of(runs[j].word):
                hit = self._whole_hit(view, runs, i, j, acc[: -len(suf)], len(suf), mode, dynamic)
                if hit is not None:
                    return hit
        return None

    def _whole_hit(
        self,
        view: _View,
        runs: list[_Run],
        i: int,
        j: int,
        key: str,
        suffix_len: int,
        mode: ScanMode,
        dynamic: bool = True,
    ) -> Hit | None:
        """A hit if runs i..j (the last one minus `suffix_len` characters)
        are a stored whole name or, with `dynamic`, an issued Q/N text. With
        `suffix_len` the hit is always the peeled Q of the full typed text
        (review 1 M1), whatever the stem matched."""
        entries = self._full.get(key)
        if entries:
            words = [r.word for r in runs[i:j]] + [runs[j].word[: len(runs[j].word) - suffix_len]]
            digits = _digit_runs(words)
            matching = [(f, v) for f, v, d in entries if d == digits]
            if matching:
                if suffix_len:
                    return self._peeled_hit(view, runs, i, j)
                if mode is ScanMode.SYSTEM:
                    f, v = matching[0]
                    return self._span_hit(
                        view, runs, i, j, HitKind.ENTITY, key, field=f, value=v
                    )
                exact = self.exact_entity(view.text[runs[i].vs : runs[j].ve])
                if exact is not None:
                    return self._span_hit(
                        view, runs, i, j, HitKind.ENTITY, key, field=exact[0], value=exact[1]
                    )
                return self._span_hit(view, runs, i, j, HitKind.MENTION, key)
        token = self._dynamic.get(key) if dynamic else None
        if token is not None:
            if suffix_len:
                return self._peeled_hit(view, runs, i, j)
            return self._span_hit(view, runs, i, j, HitKind.REUSE, key, value=token)
        return None

    def _single_at(self, view: _View, runs: list[_Run], i: int, mode: ScanMode) -> Hit | None:
        w = runs[i].word
        parts = self._strong if mode is ScanMode.INGRESS else self._distinct
        if w in parts:
            return self._span_hit(view, runs, i, i, HitKind.MENTION, w)
        if len(w) < _MIN_PART or w in self._safe or w in NOISE_TOKENS:
            return None
        for suf in _suffixes_of(w):
            if w[: -len(suf)] in parts:
                return self._peeled_hit(view, runs, i, i)
        if mode is ScanMode.SYSTEM:
            return None
        if self._is_typo(w):
            return self._span_hit(view, runs, i, i, HitKind.MENTION, w)
        if _novel_shaped(w):
            return self._span_hit(view, runs, i, i, HitKind.NOVEL, w)
        return None

    def _is_typo(self, word: str) -> bool:
        if len(word) > self._max_part + 1:
            return False
        candidates: set[str] = set()
        for d in {word} | _deletes(word):
            candidates |= self._del1.get(d, set())
        return any(EntityResolver.score(word, c) >= THRESHOLD for c in candidates)

    # ── ingress merge ────────────────────────────────────────────────────

    @staticmethod
    def _separated_softly(view: _View, runs: list[_Run], a: int, b: int) -> bool:
        """Runs a and b (b == a + 1) are separated only by whitespace, "."
        or "-" (no opaque span, no comma/slash/...)."""
        if runs[b].brk:
            return False
        between = view.text[runs[a].ve : runs[b].vs]
        return all(c in _MERGE_SEPARATORS or c.isspace() for c in between)

    def _merge(self, view: _View, runs: list[_Run], hits: list[Hit]) -> list[Hit]:
        partial = (HitKind.MENTION, HitKind.NOVEL)
        taken = {h.first_run for h in hits}
        out: list[Hit] = []
        for h in hits:
            if out:
                prev = out[-1]
                if (
                    prev.kind in partial
                    and h.kind in partial
                    and not prev.suffixed
                    and h.first_run == prev.last_run + 1
                    and self._separated_softly(view, runs, prev.last_run, h.first_run)
                ):
                    kind = HitKind.MENTION if HitKind.MENTION in (prev.kind, h.kind) else (
                        HitKind.NOVEL
                    )
                    out[-1] = Hit(
                        start=prev.start, end=h.end, kind=kind, key=prev.key + h.key,
                        words=prev.words + h.words, first_run=prev.first_run,
                        last_run=h.last_run, suffixed=h.suffixed,
                    )
                    continue
            out.append(h)
        joined: list[Hit] = []
        for h in out:
            nxt = h.last_run + 1
            if (
                h.kind in partial
                and not h.suffixed
                and nxt < len(runs)
                and nxt not in taken
                and runs[nxt].word in _JOIN_WORDS
                and self._separated_softly(view, runs, h.last_run, nxt)
            ):
                h = Hit(
                    start=h.start, end=view.orig_end(runs[nxt].ve), kind=h.kind,
                    key=h.key + runs[nxt].word, words=h.words + (runs[nxt].word,),
                    first_run=h.first_run, last_run=nxt,
                )
            joined.append(h)
        return joined
