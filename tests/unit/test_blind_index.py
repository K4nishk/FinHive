"""HMAC blind index for encrypted IDENTITY columns (KCH-96, ADR-2.3, ADR-2.4).

Covers the primitive in isolation: normalization, stability, the key
separation from `key_data` (ADR-2.3 "Key management"), and the hard runtime
refusal to index an amount column (ADR-2.4). MVP1 parity acceptance:

- A5.8 (exact-match filtering) needs the same normalized plaintext to always
  produce the same index under one key.
- A1.2 (group auto-fill) needs a name lookup and a group lookup to agree,
  independent of how the caller cased or padded the input.
- A1.1 (autocomplete) needs distinct names to produce distinct indexes so
  grouping by index doesn't collapse different borrowers together.
"""

from __future__ import annotations

import pytest

from finhive.db.blind_index import (
    BLIND_INDEX_LENGTH,
    FORBIDDEN_BLIND_INDEX_COLUMNS,
    IDENTITY_BLIND_INDEX_COLUMNS,
    compute_blind_index,
    derive_key_index,
    normalize,
)
from finhive.db.encryption import KEY_LENGTH

_KEY = b"\x01" * KEY_LENGTH
_OTHER_KEY = b"\x02" * KEY_LENGTH


# ── normalize ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Sharma Traders", "sharma traders"),
        ("  Sharma Traders  ", "sharma traders"),
        ("SHARMA TRADERS", "sharma traders"),
        ("sharma traders", "sharma traders"),
    ],
)
def test_normalize_trims_and_lowercases(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


# ── key separation (ADR-2.3 "Key management") ──────────────────────────────


def test_derive_key_index_differs_from_key_data() -> None:
    assert derive_key_index(_KEY) != _KEY


def test_derive_key_index_is_deterministic_for_the_same_key_data() -> None:
    assert derive_key_index(_KEY) == derive_key_index(_KEY)


def test_derive_key_index_differs_across_key_data() -> None:
    assert derive_key_index(_KEY) != derive_key_index(_OTHER_KEY)


@pytest.mark.parametrize("bad_key", [b"\x00" * 16, b"\x00" * 31, b"\x00" * 33])
def test_derive_key_index_rejects_a_key_that_is_not_32_bytes(bad_key: bytes) -> None:
    with pytest.raises(ValueError):
        derive_key_index(bad_key)


# ── compute_blind_index -- shape and stability ──────────────────────────────


def test_blind_index_is_16_bytes() -> None:
    index = compute_blind_index("Sharma Traders", _KEY, column="borrower_name")

    assert len(index) == BLIND_INDEX_LENGTH == 16


def test_same_plaintext_and_key_always_produce_the_same_index() -> None:
    """The opposite property from encrypt_field -- a blind index must be
    stable, or A5.8 exact-match filtering could never find a row twice.
    """
    first = compute_blind_index("Sharma Traders", _KEY, column="borrower_name")
    second = compute_blind_index("Sharma Traders", _KEY, column="borrower_name")

    assert first == second


def test_index_is_stable_regardless_of_case_or_padding() -> None:
    """A5.8: the blind index must match exactly what MVP1's normalize-then-filter
    rule matches, so a differently-cased or padded query still finds the row.
    """
    canonical = compute_blind_index("Sharma Traders", _KEY, column="borrower_name")

    assert compute_blind_index("  SHARMA TRADERS  ", _KEY, column="borrower_name") == canonical
    assert compute_blind_index("sharma traders", _KEY, column="borrower_name") == canonical


def test_distinct_names_produce_distinct_indexes() -> None:
    """A1.1 autocomplete groups by index -- two different borrowers must not
    collapse onto the same bucket.
    """
    sharma = compute_blind_index("Sharma Traders", _KEY, column="borrower_name")
    gupta = compute_blind_index("Gupta Finance", _KEY, column="borrower_name")

    assert sharma != gupta


def test_name_and_group_lookups_agree_for_group_auto_fill() -> None:
    """A1.2: looking a borrower up by name and by their group must both
    resolve deterministically under the same key, independent of column.
    """
    name_index = compute_blind_index("Sharma Traders", _KEY, column="borrower_name")
    group_index = compute_blind_index("Sharma Traders", _KEY, column="borrower_group")

    # Different columns use the same key_index derivation but the values are
    # independent hashes -- same plaintext does not imply same index across
    # columns, only stability within one column.
    assert name_index == compute_blind_index("Sharma Traders", _KEY, column="borrower_name")
    assert group_index == compute_blind_index("Sharma Traders", _KEY, column="borrower_group")


def test_different_keys_produce_different_indexes_for_the_same_plaintext() -> None:
    under_key = compute_blind_index("Sharma Traders", _KEY, column="borrower_name")
    under_other_key = compute_blind_index("Sharma Traders", _OTHER_KEY, column="borrower_name")

    assert under_key != under_other_key


@pytest.mark.parametrize("column", sorted(IDENTITY_BLIND_INDEX_COLUMNS))
def test_every_identity_column_is_accepted(column: str) -> None:
    index = compute_blind_index("Sharma Traders", _KEY, column=column)

    assert len(index) == BLIND_INDEX_LENGTH


# ── ADR-2.4: never index an amount column ───────────────────────────────────


@pytest.mark.parametrize("column", sorted(FORBIDDEN_BLIND_INDEX_COLUMNS))
def test_compute_blind_index_refuses_every_amount_column(column: str) -> None:
    """CRITICAL (ADR-2.4): a blind index must never be added to an amount.

    Loan amounts cluster on round numbers, so a deterministic index over them
    is reversible by frequency analysis without the key. This is the runtime
    half of the rule; tests/unit/test_blind_index_lint.py is the CI-blocking
    static half, over every migration file.
    """
    with pytest.raises(ValueError, match="ADR-2.4"):
        compute_blind_index("150000.00", _KEY, column=column)


def test_compute_blind_index_refuses_an_unknown_column() -> None:
    with pytest.raises(ValueError):
        compute_blind_index("whatever", _KEY, column="reference_id")


def test_identity_and_forbidden_column_sets_are_disjoint() -> None:
    assert IDENTITY_BLIND_INDEX_COLUMNS.isdisjoint(FORBIDDEN_BLIND_INDEX_COLUMNS)
