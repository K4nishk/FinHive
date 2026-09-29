"""Unit tests for loan_manager.application.agent.entity_index (KCH-238R).

The acceptance suite (`test_tokeniser_acceptance.py`) proves the end-to-end
properties through `TokenMap`; these pin the index's own rules one at a
time, so a mutant of one rule fails a test named after it."""
from __future__ import annotations

import pytest
from loan_manager.application.agent.entity_index import (
    HONORIFIC_SUFFIXES,
    EntityIndex,
    HitKind,
    ScanMode,
    _runs,
    fold,
)
from loan_manager.domain.services.entity_resolver import EntityResolver


def _index(protected=None, **values) -> EntityIndex:
    return EntityIndex(EntityResolver(values), protected)


def _kinds(index: EntityIndex, text: str, mode: ScanMode = ScanMode.INGRESS):
    return [(text[h.start : h.end], h.kind) for h in index.scan(text, mode)]


# ── view ───────────────────────────────────────────────────────────────────


def test_fold_is_nfkc_casefold_with_apostrophes_and_latin_accents_folded() -> None:
    assert fold("ＡＮＩＬ　Ｓｈａｒｍａ").text == "anil sharma"
    assert fold("O’Brien ʼ‘`´").text == "o'brien ''''"
    assert fold("ANİL ańil ánil").text == "anil anil anil"


def test_fold_drops_format_characters_and_maps_offsets_back() -> None:
    view = fold("an​il x")
    assert view.text == "anil x"
    assert view.orig_start(2) == 3  # "i" sits after the dropped ZWSP
    assert view.orig_end(4) == 5  # end of "anil" is the space's offset


def test_fold_keeps_devanagari_marks() -> None:
    assert fold("शर्मा").text == "शर्मा"


def test_fold_end_inside_one_characters_expansion_covers_the_character() -> None:
    view = fold("½")
    assert view.text == "1⁄2"
    assert view.orig_end(1) == 1


def test_fold_opaque_span_is_a_hard_break() -> None:
    runs = _runs(fold("anil B001 sharma", [(5, 9)]).text)
    assert [(r.word, r.brk) for r in runs] == [("anil", False), ("sharma", True)]


def test_runs_split_on_every_separator_and_on_a_script_change() -> None:
    words = [r.word for r in _runs(fold("a_b-c.d'e,f/g&h—i:jk sharmaजी Иyer").text)]
    assert words == ["a", "b", "c", "d", "e", "f", "g", "h", "i", "jk", "sharma", "जी", "и", "yer"]


def test_runs_ascii_digits_join_any_script() -> None:
    assert [r.word for r in _runs(fold("bg13 ४५ शर्मा1").text)] == ["bg13", "४५", "शर्मा1"]


# ── whole names ────────────────────────────────────────────────────────────


def test_whole_name_is_separator_blind_and_exact_via_the_resolver() -> None:
    index = _index(borrower_name=["anil sharma"], borrower_group=["iyerchem"])
    for text in ("anil sharma", "anil_sharma", "anil-sharma", "anilsharma"):
        assert _kinds(index, text) == [(text, HitKind.ENTITY)]
    # found separator-blind, but the RESOLVER decides exactness: "." is not
    # one of its separators, so this is a mention (still tokenised)
    assert _kinds(index, "anil.sharma") == [("anil.sharma", HitKind.MENTION)]
    assert _kinds(index, "iyer chem") == [("iyer chem", HitKind.ENTITY)]


def test_whole_name_needs_matching_digit_runs() -> None:
    index = _index(borrower_group=["bg1", "bg10"])
    assert [(h.value, h.kind) for h in index.scan("bg1 0", ScanMode.INGRESS)] == [
        ("bg1", HitKind.ENTITY)
    ]
    assert [h.value for h in index.scan("bg 10", ScanMode.INGRESS)] == ["bg10"]


def test_whole_run_is_tried_before_a_suffix_is_peeled() -> None:
    index = _index(borrower_name=["azim premji", "prem kumar"])
    hits = index.scan("azim premji", ScanMode.INGRESS)
    assert [(h.value, h.kind) for h in hits] == [("azim premji", HitKind.ENTITY)]
    hits = index.scan("premji", ScanMode.INGRESS)
    assert [(h.key, h.suffixed) for h in hits] == [("premji", False)]


def test_glued_honorific_on_a_whole_name_is_a_q_of_the_full_typed_text() -> None:
    """Review 1 M1 ruling: found only by peeling -> never exact."""
    index = _index(borrower_name=["anil sharma"])
    (hit,) = index.scan("anil sharmaji ko", ScanMode.INGRESS)
    assert (hit.kind, hit.value, hit.suffixed) == (HitKind.MENTION, None, True)
    assert "anil sharmaji ko"[hit.start : hit.end] == "anil sharmaji"
    (hit,) = index.scan("ask anil sharmaji", ScanMode.SYSTEM)  # guard still sees it
    assert hit.key == "anilsharmaji"


def test_every_honorific_suffix_peels_longest_first() -> None:
    index = _index(borrower_name=["anil sharma"], depositor_name=["राम शर्मा"])
    for suffix in HONORIFIC_SUFFIXES:
        stem = "sharma" if suffix.isascii() else "शर्मा"
        (hit,) = index.scan(f"{stem}{suffix.upper()}", ScanMode.INGRESS)
        assert (hit.key, hit.suffixed) == (stem + suffix, True), suffix
    # a Devanagari suffix glued to a LATIN stem is split by the script change
    (hit,) = index.scan("sharmaजी", ScanMode.INGRESS)
    assert (hit.key, hit.suffixed) == ("sharma", False)
    assert HONORIFIC_SUFFIXES.index("bhaiya") < HONORIFIC_SUFFIXES.index("bhai")


def test_a_suffix_never_leaves_a_stem_shorter_than_three() -> None:
    index = _index(borrower_name=["ra kumar"], borrower_group=["ra"])
    assert _kinds(index, "raji") == [("raji", HitKind.NOVEL)]


def test_a_stored_name_that_ends_in_a_suffix_beats_the_peeled_stem() -> None:
    index = _index(borrower_name=["sharmaji"], borrower_group=["sharma"])
    (hit,) = index.scan("sharmaji", ScanMode.INGRESS)
    assert (hit.kind, hit.value, hit.suffixed) == (HitKind.ENTITY, "sharmaji", False)


def test_non_exact_whole_name_is_a_mention() -> None:
    index = _index(borrower_name=["anil sharma"], borrower_group=["sharma"])
    assert _kinds(index, "sharma") == [("sharma", HitKind.MENTION)]


def test_protected_only_whole_name_is_a_mention_never_an_entity() -> None:
    index = _index({"borrower_name": ["old kumar"]}, borrower_name=["anil sharma"])
    assert _kinds(index, "old kumar") == [("old kumar", HitKind.MENTION)]
    assert index.exact_entity("old kumar") is None


def test_protected_values_skip_blanks_and_duplicates() -> None:
    index = _index({"borrower_name": ["", "  ", "anil sharma"]}, borrower_name=["anil sharma"])
    assert index.entries == (("borrower_name", "anil sharma"),)


def test_a_value_with_no_word_characters_is_ignored() -> None:
    index = _index(borrower_name=["---", "anil sharma"])
    assert _kinds(index, "--- anil sharma") == [("anil sharma", HitKind.ENTITY)]


def test_system_mode_whole_name_takes_the_stored_field() -> None:
    index = _index(borrower_name=["anil sharma"], borrower_group=["sharma"])
    (hit,) = index.scan("ask sharma", ScanMode.SYSTEM)
    assert (hit.kind, hit.field, hit.value) == (HitKind.ENTITY, "borrower_group", "sharma")


# ── exactness tie set ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    ["sharma", "sharma group", "anil sharma", "ANIL-SHARMA", "anilsharma", "bg 13", "bg1 0",
     "gupta & sons", "gupta sons", "the sharma family", "zzz", "iyer chem", "chem iyer"],
)
def test_exact_entity_matches_the_full_resolver(text: str) -> None:
    values = {
        "borrower_name": ["anil sharma", "rakesh sharma"],
        "borrower_group": ["sharma group", "bg13", "bg1", "bg10", "gupta & sons", "iyer chem"],
        "depositor_group": ["sharma"],
    }
    index = EntityIndex(EntityResolver(values))
    resolution = EntityResolver(values).resolve(text)
    expected = (resolution.top.field, resolution.top.value) if resolution.exact else None
    assert index.exact_entity(text) == expected
    assert index.exact_entity(text) == expected  # memoised answer is the same


# ── single runs ────────────────────────────────────────────────────────────


def test_part_precedence_known_name_over_safe_word() -> None:
    index = _index(borrower_name=["rose kapoor"])
    assert _kinds(index, "rose") == [("rose", HitKind.MENTION)]


def test_weak_part_is_a_safe_word_only_ever_in_a_group() -> None:
    index = _index(borrower_group=["gupta & sons"], borrower_name=["sons kapoor"])
    assert _kinds(index, "sons") == [("sons", HitKind.MENTION)]  # also a person's word
    index = _index(borrower_group=["gupta & sons"])
    assert _kinds(index, "sons") == []


def test_typo_of_a_part_is_a_mention_but_a_safe_word_never_is() -> None:
    index = _index(depositor_name=["meera iyer"])
    assert _kinds(index, "meeraa") == [("meeraa", HitKind.MENTION)]
    assert _kinds(index, "mera") == []  # safe (Hindi "my") beats typo


def test_typo_needs_the_resolver_gate_not_just_a_shared_deletion() -> None:
    index = _index(borrower_group=["bg13"])
    assert _kinds(index, "bg14") == []  # digits differ -> resolver scores 0


def test_overlong_word_is_never_a_typo() -> None:
    index = _index(borrower_name=["anil"])
    assert _kinds(index, "a" * 40) == [("a" * 40, HitKind.NOVEL)]


def test_novel_needs_three_letters_and_no_digit() -> None:
    index = _index(borrower_name=["anil sharma"])
    assert _kinds(index, "kapoor ab xyz9 grp") == [("kapoor", HitKind.NOVEL)]


def test_system_mode_has_no_typo_and_no_novel_and_needs_distinct_parts() -> None:
    index = _index(borrower_name=["anil rao", "deep kapoor"])
    assert _kinds(index, "meeraa kapoorr zzzz rao deep", ScanMode.SYSTEM) == []
    assert _kinds(index, "kapoor anil", ScanMode.SYSTEM) == [
        ("kapoor", HitKind.MENTION), ("anil", HitKind.MENTION)
    ]
    assert _kinds(index, "kapoorji", ScanMode.SYSTEM) == [("kapoorji", HitKind.MENTION)]


# ── merge ──────────────────────────────────────────────────────────────────


def test_adjacent_partial_hits_merge_across_space_dot_and_hyphen() -> None:
    index = _index(borrower_name=["anil sharma"])
    assert _kinds(index, "anil kapoor") == [("anil kapoor", HitKind.MENTION)]
    assert _kinds(index, "rohan kapadia") == [("rohan kapadia", HitKind.NOVEL)]
    assert _kinds(index, "rohan.kapadia-x") == [("rohan.kapadia", HitKind.NOVEL)]


def test_partial_hits_do_not_merge_across_a_comma_or_a_token() -> None:
    index = _index(borrower_name=["anil sharma"])
    assert len(index.scan("rohan, kapadia", ScanMode.INGRESS)) == 2
    text = "rohan B001 kapadia"
    assert len(index.scan(text, ScanMode.INGRESS, [(6, 10)])) == 2


def test_exact_whole_name_is_never_merged() -> None:
    index = _index(borrower_name=["anil sharma"])
    assert _kinds(index, "anil sharma kapoor") == [
        ("anil sharma", HitKind.ENTITY), ("kapoor", HitKind.NOVEL)
    ]


def test_a_following_group_word_joins_a_partial_hit() -> None:
    index = _index(borrower_name=["anil sharma"])
    assert _kinds(index, "sharma family loans") == [("sharma family", HitKind.MENTION)]
    assert _kinds(index, "sharmaji family") == [("sharmaji", HitKind.MENTION)]


# ── dynamic (issued Q/N) texts ─────────────────────────────────────────────


def test_dynamic_text_is_reused_separator_blind_and_optional_for_the_guard() -> None:
    index = _index(borrower_name=["anil sharma"])
    index.add_dynamic("rohankapadia", "N001")
    index.add_dynamic("rohankapadia", "N009")  # first one wins
    hits = index.scan("ask Rohan-Kapadia", ScanMode.SYSTEM)
    assert [(h.kind, h.value) for h in hits] == [(HitKind.REUSE, "N001")]
    assert index.dynamic_token("rohankapadia") == "N001"
    assert index.first_leak("rohan kapadia!") == "rohankapadia"
    assert index.first_leak("rohan kapadiaji!") == "rohankapadiaji"  # peeled, still caught
    assert index.first_leak("rohan kapadia!", dynamic=False) is None
    assert index.first_leak("nothing here") is None
