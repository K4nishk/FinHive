"""Unit tests for EntityResolver (KCH-236).

KCH-229 made autocomplete/filter matching exact against a blind index; this
resolver is the fuzzy layer in front of it for conversational agent input
-- domain layer, stdlib-only (Ponytail rung 4: difflib).

Fixture used by most tests in this module (built via `resolver()`/`VALUES`
below):
    borrower_name:    rohit sharma, rohit verma, b1, b13
    borrower_group:   bg1, bg10, bg13, sharma
    depositor_name:   meera iyer
    depositor_group:  dg1, iyer chem

Measured baseline (whole-string SequenceMatcher.ratio() only, no token
score, no digit guard, no edit-distance gate -- the pre-KCH-236 approach):
"sharma group" vs "sharma" = 0.667; "iyer" vs "iyer chem" = 0.615; "bg1" vs
"bg10"/"bg13" = 0.857; "sharma" vs "sharmila" = 0.857 (same ratio as
"iyr" vs "iyer" = 0.857 -- see TestFalsePositives for why ratio alone can't
tell these two apart, and edit distance can: 2 vs 1).

Review cycle 1 (2026-09-25) findings addressed here:
  1 BLOCKER  -- Candidate.value/entities() return the ORIGINAL stored value,
    never the normalised form (the blind-index filter can't match a
    normalised value back to its stored row).
  2 ORCH ruling -- a "group"/"grp" token in the query restricts candidate
    fields to *_group only.
  3 MAJOR -- recall scored via `top` (None counts as a miss); the one
    genuinely ambiguous case removed from the recall set.
  4 MAJOR -- multi-word queries (real whitespace) score via token-only,
    never whole-string; single-token/compact (underscore/hyphen-joined,
    no real space) queries additionally require edit distance <=1 on the
    whole-string path.
  5 ORCH ruling (supersedes the original exact-wins rule) -- an exact
    match resolves only when it is the unique top scorer.
"""
from __future__ import annotations

import math

import pytest
from loan_manager.domain.services.entity_resolver import (
    NAME_FIELDS,
    EntityResolver,
    _is_exact,
    _levenshtein,
    _token_score,
)

VALUES = {
    "borrower_name": ["rohit sharma", "rohit verma", "b1", "b13"],
    "borrower_group": ["bg1", "bg10", "bg13", "sharma"],
    "depositor_name": ["meera iyer"],
    "depositor_group": ["dg1", "iyer chem"],
}


@pytest.fixture
def resolver() -> EntityResolver:
    return EntityResolver(VALUES)


def _values_of(candidates) -> set[str]:
    return {c.value for c in candidates}


class TestScoring:
    def test_sharma_group_resolves_to_group_field(self, resolver):
        # ORCH ruling #2: "group" in the query restricts the search to
        # borrower_group/depositor_group, so "rohit sharma" (borrower_name)
        # is never a competing candidate and this RESOLVES cleanly, rather
        # than merely producing a same-scoring candidate list.
        result = resolver.resolve("sharma group")
        assert result.status == "resolved"
        assert result.top is not None
        assert result.top.field == "borrower_group"
        assert result.top.value == "sharma"
        assert {c.field for c in result.candidates} <= {
            "borrower_group",
            "depositor_group",
        }

    def test_iyer_returns_group_and_depositor_ambiguous_top2(self, resolver):
        # Whole-string ratio("iyer", "iyer chem") = 0.615 (measured above);
        # only token scoring (query token "iyer" against each value's
        # tokens) surfaces both "meera iyer" and "iyer chem" as candidates,
        # and with neither an exact full-string match this must be
        # ambiguous, never a guessed single winner.
        result = resolver.resolve("iyer")
        assert result.status == "ambiguous"
        assert result.ambiguous is True
        assert result.top is None
        top2_values = {c.value for c in result.top2}
        assert top2_values == {"meera iyer", "iyer chem"}
        top2_fields = {c.field for c in result.top2}
        assert top2_fields == {"depositor_name", "depositor_group"}

    def test_exact_sharma_ambiguous_when_tied_with_rohit_sharma(self, resolver):
        # ORCH ruling #5 (supersedes the original exact-wins rule): "sharma"
        # token-matches both the group value "sharma" (exact, 1.0) and the
        # name value "rohit sharma" (token match, also 1.0). A second
        # candidate tied at the exact match's own score means the pick is
        # NOT safe -- ambiguous, not an automatic exact-match win.
        result = resolver.resolve("sharma")
        assert _values_of(result.candidates) == {"sharma", "rohit sharma"}
        assert result.status == "ambiguous"
        assert result.top is None

    def test_exact_match_wins_when_no_other_candidate_ties_at_1(self):
        # Same exact-match machinery, but the only other candidate
        # ("sharmaa", score 0.923) does NOT tie at 1.0 -- the exact match is
        # the unique top scorer and safely resolves.
        r = EntityResolver(
            {"borrower_group": ["sharma"], "depositor_name": ["sharmaa"]}
        )
        result = r.resolve("sharma")
        assert _values_of(result.candidates) == {"sharma", "sharmaa"}
        assert result.status == "resolved"
        assert result.top.value == "sharma"
        assert result.top.field == "borrower_group"

    def test_bg1_resolves_exactly_not_bg10_or_bg13(self, resolver):
        # Whole-string ratio("bg1", "bg10") = ratio("bg1", "bg13") = 0.857
        # (measured above) -- above THRESHOLD on shared-prefix alone. The
        # digit guard must zero both because their digit runs ("10", "13")
        # differ from the query's ("1").
        result = resolver.resolve("bg1")
        assert result.status == "resolved"
        assert result.top.value == "bg1"
        assert "bg10" not in _values_of(result.candidates)
        assert "bg13" not in _values_of(result.candidates)

    def test_bg13_does_not_match_bg1(self, resolver):
        result = resolver.resolve("bg13")
        assert result.status == "resolved"
        assert result.top.value == "bg13"
        assert "bg1" not in _values_of(result.candidates)
        assert "bg10" not in _values_of(result.candidates)

    def test_no_match_returns_empty_not_substring(self, resolver):
        # A naive `if query in value: score = 0.9` shortcut would make "bg"
        # match bg1/bg10/bg13 purely by containment. No substring path
        # exists anywhere in `score`, so a short, unrelated query returns
        # nothing rather than every value that happens to contain it.
        result = resolver.resolve("bg")
        assert result.status == "no_match"
        assert result.candidates == ()

        result = resolver.resolve("zzz")
        assert result.status == "no_match"
        assert result.candidates == ()

    def test_short_token_needs_exact_match(self):
        # A query token under 3 chars is compared for equality only, never
        # by ratio -- so "am" must not get fuzzy credit against "amc" (a
        # plain ratio would give 0.8, itself below THRESHOLD=0.85 in this
        # case, but the point of the rule is that short tokens never get
        # ANY partial credit, at any threshold).
        assert EntityResolver.score("am", "amc") == 0.0
        assert EntityResolver.score("am", "am") == 1.0

    def test_ranking_deterministic_tiebreak_by_field_order(self, resolver):
        # Both candidates score exactly 1.0 for "iyer" (see the ambiguous
        # test above); with scores tied, rank must break on NAME_FIELDS
        # order: depositor_name (index 2) before depositor_group (index 3).
        result = resolver.resolve("iyer")
        assert [c.field for c in result.candidates] == [
            "depositor_name",
            "depositor_group",
        ]
        assert [c.rank for c in result.candidates] == [1, 2]

    def test_two_exact_matches_is_ambiguous(self):
        # Two different fields sharing one normalised value: an exact query
        # for it must be ambiguous, not an arbitrary pick between them.
        r = EntityResolver({"borrower_name": ["dup"], "borrower_group": ["dup"]})
        result = r.resolve("dup")
        assert result.status == "ambiguous"
        assert result.top is None
        assert {c.field for c in result.candidates} == {
            "borrower_name",
            "borrower_group",
        }

    def test_single_non_exact_candidate_resolves(self, resolver):
        # "meera and iyer" token-matches only "meera iyer" (score 1.0, noise
        # word "and" dropped) and is not an exact match of it -- exactly
        # one candidate, zero exact matches, must still resolve rather than
        # report ambiguous/no_match.
        result = resolver.resolve("meera and iyer")
        assert result.status == "resolved"
        assert result.top is not None
        assert result.top.value == "meera iyer"

    def test_noise_only_query_falls_back_to_original_tokens(self):
        # Every token of "group" is itself a noise token; filtering must
        # fall back to the original tokens rather than compare nothing.
        assert EntityResolver.score("group", "group") == 1.0
        # Item 6 mutant-kill: the fallback must reach the VALUE's other
        # tokens too, not just an exact single-word value.
        assert EntityResolver.score("group", "shah group") == 1.0

    def test_token_score_empty_inputs_return_zero(self):
        assert _token_score((), ("a",)) == 0.0
        assert _token_score(("a",), ()) == 0.0

    def test_is_exact_blank_inputs_return_false(self):
        # Coverage: unreachable through Resolution itself (blank queries
        # never produce candidates, so `_exact_candidates` never calls
        # `_is_exact` with a blank side) -- exercised directly.
        assert _is_exact("", "sharma") is False
        assert _is_exact("sharma", "") is False
        assert _is_exact("  ", "sharma") is False

    def test_unknown_field_rejected(self):
        with pytest.raises(ValueError):
            EntityResolver({"not_a_name_field": ["x"]})

    def test_entities_sorted_stable(self, resolver):
        first = resolver.entities()
        second = resolver.entities()
        assert first == second
        field_index = {f: i for i, f in enumerate(NAME_FIELDS)}
        assert list(first) == sorted(first, key=lambda pair: (field_index[pair[0]], pair[1]))
        assert ("borrower_group", "bg1") in first
        assert ("depositor_name", "meera iyer") in first

    def test_blank_and_none_values_ignored(self):
        dirty = {
            "borrower_name": ["rohit sharma", "", None, "  "],
            "borrower_group": [None],
        }
        r = EntityResolver(dirty)
        entities = r.entities()
        assert entities == (("borrower_name", "rohit sharma"),)
        result = r.resolve("")
        assert result.status == "no_match"

    def test_dedupe_collapses_identical_original_values(self):
        r = EntityResolver({"borrower_name": ["rohit sharma", "rohit sharma"]})
        assert r.entities() == (("borrower_name", "rohit sharma"),)

    def test_separator_normalisation_underscore_and_hyphen(self):
        assert EntityResolver.score("rohit_sharma", "rohit sharma") == 1.0
        assert EntityResolver.score("rohit-sharma", "rohit sharma") == 1.0

    def test_threshold_boundary_is_inclusive(self):
        # score("bg_13", "bg13") is exactly 0.8888... (measured). A resolver
        # built with THAT exact threshold must still include it (`>=`, not
        # `>`); nudging the threshold to the next representable float must
        # exclude it. "sharmaa"/"sharma" (0.923, measured) is a genuine
        # fuzzy ratio, not a case the review-cycle-2 collapsed-form
        # equality check short-circuits to a flat 1.0 (their collapsed
        # forms differ), so it stays a real boundary value.
        score = EntityResolver.score("sharmaa", "sharma")
        at_boundary = EntityResolver({"borrower_group": ["sharma"]}, threshold=score)
        assert at_boundary.resolve("sharmaa").status == "resolved"

        just_above = EntityResolver(
            {"borrower_group": ["sharma"]}, threshold=math.nextafter(score, 1.0)
        )
        assert just_above.resolve("sharmaa").status == "no_match"


class TestOriginalValuePreservation:
    """Review cycle 1, BLOCKER #1."""

    def test_resolve_returns_original_stored_value_not_normalised(self):
        r = EntityResolver({"depositor_group": ["iyer_chem"]})
        result = r.resolve("iyer chem")
        assert result.status == "resolved"
        assert result.top.value == "iyer_chem"

    def test_distinct_originals_that_normalise_equal_stay_distinct_entities(self):
        r = EntityResolver({"depositor_group": ["iyer_chem", "iyer chem"]})
        assert set(r.entities()) == {
            ("depositor_group", "iyer_chem"),
            ("depositor_group", "iyer chem"),
        }
        assert len(r.entities()) == 2


class TestFalsePositives:
    """Review cycle 1, MAJOR #4."""

    def test_different_full_names_sharing_a_surname_do_not_match(self):
        r = EntityResolver(
            {"borrower_name": ["sunil kumar", "sohan lal", "ramesh raju"]}
        )
        # Multi-word queries score via token-only (no whole-string ratio):
        # whole-string ratio("anil kumar","sunil kumar")=0.857 would
        # otherwise be a false positive on the shared "kumar" alone.
        assert r.resolve("anil kumar").status == "no_match"
        assert r.resolve("mohan lal").status == "no_match"
        assert r.resolve("ramesh rao").status == "no_match"

    def test_single_token_prefix_name_does_not_match_longer_name(self):
        # ratio("sharma","sharmila") = 0.857, numerically IDENTICAL to
        # ratio("iyr","iyer") = 0.857 used (successfully) in the recall set
        # -- ratio alone can't distinguish them. Levenshtein distance can:
        # "sharmila" is 2 edits from "sharma" (two insertions); "sharmaa"
        # and "iyer" are each 1 edit from their queries. The compact/
        # single-token path requires edit distance <=1 in addition to
        # ratio>=THRESHOLD.
        r = EntityResolver({"borrower_group": ["sharmila"]})
        result = r.resolve("sharma")
        assert result.status == "no_match"
        assert result.candidates == ()


class TestRecallAt1:
    # 25 typo/case/underscore/space/noise-word queries against the module
    # fixture (review cycle 2, MAJOR #2: "BG 13"/"bg 13"/"dg 1"/"b 1"
    # restored -- literal-space codes now resolve via collapsed-form
    # equality). Each pair is (query, expected `top` value) -- `top` is None
    # unless resolved, so an ambiguous or no-match result on a case
    # expecting a single golden answer counts as a miss (item 3: score via
    # `top`, not merely rank-1 of `candidates`). Every case here has an
    # unambiguous intended answer; genuinely ambiguous queries ("iyer" - see
    # TestScoring) are not part of this metric.
    CASES = [
        ("Rohit Sharmaa", "rohit sharma"),
        ("rohit_sharma", "rohit sharma"),
        ("ROHIT VERMA", "rohit verma"),
        ("rohit verrma", "rohit verma"),
        ("iyer_chem", "iyer chem"),
        ("IYER-CHEM", "iyer chem"),
        ("iyerchem", "iyer chem"),
        ("meera iyr", "meera iyer"),
        ("meera_iyer", "meera iyer"),
        ("MEERA IYER", "meera iyer"),
        ("Bg13", "bg13"),
        ("bg_13", "bg13"),
        ("BG 13", "bg13"),
        ("bg 13", "bg13"),
        ("Bg1", "bg1"),
        ("bg_1", "bg1"),
        ("Bg10", "bg10"),
        ("DG1", "dg1"),
        ("dg_1", "dg1"),
        ("dg 1", "dg1"),
        ("b_13", "b13"),
        ("B13", "b13"),
        ("b_1", "b1"),
        ("b 1", "b1"),
        ("meera and iyer", "meera iyer"),
    ]

    def test_recall_at_1_on_fixture_at_least_0_95(self, resolver):
        hits = 0
        misses = []
        for query, expected in self.CASES:
            result = resolver.resolve(query)
            top = result.top.value if result.top else None
            if top == expected:
                hits += 1
            else:
                misses.append((query, expected, top, result.status))
        recall = hits / len(self.CASES)
        assert recall >= 0.95, f"recall={recall}, misses={misses}"


class TestTranspositionTypos:
    """Review cycle 2, MAJOR #1: plain Levenshtein prices an adjacent swap
    at 2, past _COMPACT_MAX_EDIT_DISTANCE=1, so _guarded_ratio zeroed
    these keystroke-adjacent-swap typos. OSA (restricted Damerau) prices
    an adjacent transposition at 1. Measured ratios (all >= THRESHOLD once
    the gate lets them through): agrawal/agarwal=0.857,
    kulkanri/kulkarni=0.875, malhtora/malhotra=0.875,
    venaktesh/venkatesh=0.889, srinviasan/srinivasan=0.9.
    """

    def test_single_letter_transposition_typos_resolve(self):
        cases = [
            ("agrawal", "agarwal"),
            ("kulkanri", "kulkarni"),
            ("malhtora", "malhotra"),
            ("venaktesh", "venkatesh"),
            ("srinviasan", "srinivasan"),
        ]
        for query, value in cases:
            r = EntityResolver({"borrower_group": [value]})
            result = r.resolve(query)
            assert result.status == "resolved", (query, value, result.status)
            assert result.top.value == value

    def test_transposition_typo_in_multiword_name_resolves(self):
        r = EntityResolver({"borrower_name": ["neha agarwal"]})
        result = r.resolve("neha agrawal")
        assert result.status == "resolved"
        assert result.top.value == "neha agarwal"

    def test_osa_transposition_cost_is_one_not_zero(self):
        # Pins the OSA transposition move's cost at 1, not 0: an adjacent
        # swap is a real edit, not a free one. "ab"->"ba" is exactly one
        # adjacent transposition.
        assert _levenshtein("ab", "ba") == 1

    def test_osa_two_disjoint_transpositions_cost_two(self):
        # "abcd"->"badc" is two adjacent transpositions ("ab"->"ba",
        # "cd"->"dc"), non-overlapping, so OSA prices it at 2 -- distinct
        # from plain Levenshtein's 4 (each pair needs two single-character
        # edits) and from a broken transposition rule that undercounts
        # multiple swaps.
        assert _levenshtein("abcd", "badc") == 2

    def test_two_insertion_typo_still_no_match(self):
        # Must NOT regress: "sharmila" is 2 edits from "sharma" (two
        # insertions, no adjacent swap) -- OSA does not shrink this, so it
        # stays past _COMPACT_MAX_EDIT_DISTANCE.
        r = EntityResolver({"borrower_group": ["sharmila"]})
        result = r.resolve("sharma")
        assert result.status == "no_match"

    def test_different_full_names_sharing_a_surname_still_no_match(self):
        # No adjacent transposition present in any of these pairs -- OSA
        # must not widen the gate for them.
        r = EntityResolver(
            {"borrower_name": ["sunil kumar", "sohan lal", "ramesh raju"]}
        )
        assert r.resolve("anil kumar").status == "no_match"
        assert r.resolve("mohan lal").status == "no_match"
        assert r.resolve("ramesh rao").status == "no_match"


class TestCollapsedFormEquality:
    """Review cycle 2, MAJOR #2: a code typed with a literal space ("BG
    13") normalises to "bg 13" -- real whitespace, so it never reaches the
    whole-string path (token-only scoring), and no token independently
    clears the gate ("bg" is a short token needing equality; "13" is not
    itself a token of the compact value "bg13"). Collapsed-form equality
    (every space removed from both normalised sides) scores 1.0 directly.
    """

    def test_space_separated_code_resolves_exactly(self, resolver):
        cases = [
            ("BG 13", "bg13"),
            ("bg 13", "bg13"),
            ("b 1", "b1"),
            ("dg 1", "dg1"),
        ]
        for query, expected in cases:
            result = resolver.resolve(query)
            assert result.status == "resolved", (query, result.status)
            assert result.top.value == expected

    def test_space_separated_code_still_respects_digit_guard(self, resolver):
        # Collapsed forms of "bg1"/"bg10"/"bg13" all differ from each
        # other, so the digit-guard family stays separated even through
        # the new collapsed-equality path.
        result = resolver.resolve("bg 1")
        assert result.status == "resolved"
        assert result.top.value == "bg1"
        assert "bg10" not in _values_of(result.candidates)
        assert "bg13" not in _values_of(result.candidates)

    def test_split_digit_runs_do_not_collapse_match_a_different_stored_code(
        self, resolver
    ):
        # Post-review fix (KCH-236): "bg1 0" collapses to "bg10", identical
        # to stored "bg10"'s collapsed form -- but the query's digit runs
        # are ("1", "0"), split by the literal space, not ("10"). Without
        # the digit-run equality guard on the collapse check, this used to
        # resolve exactly to "bg10" even though "bg1" is separately stored
        # and is the intended match. It must not resolve-exact to "bg10".
        result = resolver.resolve("bg1 0")
        assert not (
            result.status == "resolved"
            and result.top.value == "bg10"
            and result.exact
        )
        assert not _is_exact("bg1 0", "bg10")
        # "BG 13" (single digit run "13" on both sides) must still resolve
        # exactly -- the guard must not overreach.
        exact_result = resolver.resolve("BG 13")
        assert exact_result.status == "resolved"
        assert exact_result.top.value == "bg13"
        assert exact_result.exact is True


class TestExactField:
    """Review cycle 2, ORCH ruling (finding 3): KCH-238/239 need to know
    whether `top` is a genuine exact match (normalised or collapsed) or
    merely a fuzzy one, since only an exact resolve may act without a "did
    you mean" confirmation.
    """

    def test_exact_true_for_exact_normalised_match(self):
        r = EntityResolver(
            {"borrower_group": ["sharma"], "depositor_name": ["sharmaa"]}
        )
        result = r.resolve("sharma")
        assert result.status == "resolved"
        assert result.exact is True

    def test_exact_false_for_fuzzy_resolve(self, resolver):
        result = resolver.resolve("Rohit Sharmaa")
        assert result.status == "resolved"
        assert result.top.value == "rohit sharma"
        assert result.exact is False

    def test_exact_false_for_transposition_typo_resolve(self):
        # One of the measured MAJOR #1 pairs: resolves, but not exactly.
        r = EntityResolver({"borrower_group": ["agarwal"]})
        result = r.resolve("agrawal")
        assert result.status == "resolved"
        assert result.exact is False

    def test_exact_true_for_collapsed_match(self, resolver):
        result = resolver.resolve("BG 13")
        assert result.status == "resolved"
        assert result.exact is True

    def test_exact_false_when_no_top(self, resolver):
        result = resolver.resolve("iyer")
        assert result.status == "ambiguous"
        assert result.exact is False

        result = resolver.resolve("zzz")
        assert result.status == "no_match"
        assert result.exact is False


class TestReviewCycle2MutantSurvivors:
    """Review cycle 2, MINOR #4: mutation-tested gaps."""

    def test_substitution_typo_through_the_gate(self):
        # A plain substitution ('m'->'n'), not a transposition -- distance
        # 1 under both plain and OSA Levenshtein. Guards against an OSA
        # implementation that only special-cases transpositions and breaks
        # the ordinary substitution path.
        r = EntityResolver({"borrower_group": ["kulkarni"]})
        result = r.resolve("kulkarmi")
        assert result.status == "resolved"
        assert result.top.value == "kulkarni"

    def test_leading_trailing_whitespace_on_compact_query(self):
        r = EntityResolver({"depositor_group": ["iyerchem"], "borrower_group": ["bg1"]})
        result = r.resolve(" iyerchem")
        assert result.status == "resolved"
        assert result.top.value == "iyerchem"
        result = r.resolve("  bg1  ")
        assert result.status == "resolved"
        assert result.top.value == "bg1"

    def test_grp_hint_restricts_to_group_fields(self, resolver):
        result = resolver.resolve("sharma grp")
        assert result.status == "resolved"
        assert result.top.field == "borrower_group"
        assert result.top.value == "sharma"

    def test_top2_with_three_or_more_candidates_returns_exactly_two_in_rank_order(
        self,
    ):
        r = EntityResolver(
            {
                "borrower_name": ["meera iyer"],
                "borrower_group": ["iyer"],
                "depositor_name": ["iyer chem"],
            }
        )
        result = r.resolve("iyer")
        assert len(result.candidates) >= 3
        assert result.status == "ambiguous"
        top2 = result.top2
        assert len(top2) == 2
        assert tuple(top2) == result.candidates[:2]
        assert [c.rank for c in top2] == [1, 2]
