"""Master key loading, HKDF derivation and rotation (KCH-97, ADR-2.3).

Covers the pieces `finhive/db/encryption.py` and `finhive/db/blind_index.py`
explicitly defer: turning a `key_version` into usable `key_data`/`key_index`,
loading masters from the environment, and rotating one row's ciphertext (and
blind index) from an old version's key to a new one. The rotation tests are
the acceptance exercise from the ticket: re-encrypt a subset while the ring
still reads both versions.
"""

from __future__ import annotations

import base64

import pytest

from finhive.db.blind_index import compute_blind_index, derive_key_index
from finhive.db.encryption import KEY_LENGTH, DecryptionError, decrypt_field, encrypt_field
from finhive.db.keys import (
    ConfigError,
    KeyRing,
    derive_key_data,
    load_key_ring,
    rotate_field,
    rotate_identity_field,
)

_MASTER = b"\x01" * KEY_LENGTH
_OTHER_MASTER = b"\x02" * KEY_LENGTH


def _b64(key: bytes) -> str:
    return base64.b64encode(key).decode("ascii")


# ── derive_key_data ──────────────────────────────────────────────────────────


def test_derive_key_data_differs_from_the_master() -> None:
    assert derive_key_data(_MASTER) != _MASTER


def test_derive_key_data_is_deterministic_for_the_same_master() -> None:
    assert derive_key_data(_MASTER) == derive_key_data(_MASTER)


def test_derive_key_data_differs_across_masters() -> None:
    assert derive_key_data(_MASTER) != derive_key_data(_OTHER_MASTER)


def test_derive_key_data_and_derive_key_index_never_collide() -> None:
    """ADR-2.3: key_data and key_index must never be the same bytes, even
    though both are ultimately derived from the same master.
    """
    key_data = derive_key_data(_MASTER)
    key_index = derive_key_index(key_data)

    assert key_data != key_index


@pytest.mark.parametrize("bad_key", [b"\x00" * 16, b"\x00" * 31, b"\x00" * 33])
def test_derive_key_data_rejects_a_master_that_is_not_32_bytes(bad_key: bytes) -> None:
    with pytest.raises(ValueError):
        derive_key_data(bad_key)


# ── load_key_ring ────────────────────────────────────────────────────────────


def test_load_key_ring_reads_the_current_version_and_its_master() -> None:
    ring = load_key_ring({"FINHIVE_KEY_VERSION": "1", "FINHIVE_MASTER_KEY_V1": _b64(_MASTER)})

    assert ring.current_version == 1
    assert ring.key_data() == derive_key_data(_MASTER)


def test_load_key_ring_loads_every_master_key_version_present() -> None:
    ring = load_key_ring(
        {
            "FINHIVE_KEY_VERSION": "2",
            "FINHIVE_MASTER_KEY_V1": _b64(_MASTER),
            "FINHIVE_MASTER_KEY_V2": _b64(_OTHER_MASTER),
        }
    )

    assert ring.key_data(1) == derive_key_data(_MASTER)
    assert ring.key_data(2) == derive_key_data(_OTHER_MASTER)
    assert ring.key_data() == ring.key_data(2)  # defaults to current_version


def test_load_key_ring_ignores_unrelated_environment_variables() -> None:
    ring = load_key_ring(
        {
            "FINHIVE_KEY_VERSION": "1",
            "FINHIVE_MASTER_KEY_V1": _b64(_MASTER),
            "PATH": "/usr/bin",
            "FINHIVE_MASTER_KEY_VX": "not-a-version",
        }
    )

    assert ring.masters == {1: _MASTER}


def test_load_key_ring_requires_key_version() -> None:
    with pytest.raises(ConfigError, match="FINHIVE_KEY_VERSION"):
        load_key_ring({"FINHIVE_MASTER_KEY_V1": _b64(_MASTER)})


def test_load_key_ring_rejects_a_non_numeric_key_version() -> None:
    with pytest.raises(ConfigError, match="FINHIVE_KEY_VERSION"):
        load_key_ring({"FINHIVE_KEY_VERSION": "latest", "FINHIVE_MASTER_KEY_V1": _b64(_MASTER)})


def test_load_key_ring_requires_a_master_for_the_current_version() -> None:
    with pytest.raises(ConfigError, match="FINHIVE_MASTER_KEY_V2"):
        load_key_ring({"FINHIVE_KEY_VERSION": "2", "FINHIVE_MASTER_KEY_V1": _b64(_MASTER)})


def test_load_key_ring_rejects_invalid_base64() -> None:
    with pytest.raises(ConfigError, match="base64"):
        load_key_ring({"FINHIVE_KEY_VERSION": "1", "FINHIVE_MASTER_KEY_V1": "not base64!!"})


def test_load_key_ring_rejects_a_master_of_the_wrong_length() -> None:
    with pytest.raises(ConfigError, match="32 bytes"):
        load_key_ring(
            {"FINHIVE_KEY_VERSION": "1", "FINHIVE_MASTER_KEY_V1": base64.b64encode(b"\x00" * 16).decode()}
        )


def test_key_ring_raises_on_an_unloaded_version() -> None:
    ring = KeyRing(current_version=1, masters={1: _MASTER})

    with pytest.raises(ConfigError, match="key_version 2"):
        ring.key_data(2)


def test_key_ring_key_index_matches_derive_key_index_of_its_key_data() -> None:
    ring = KeyRing(current_version=1, masters={1: _MASTER})

    assert ring.key_index() == derive_key_index(ring.key_data())


# ── rotation (the ticket's acceptance exercise) ─────────────────────────────


@pytest.fixture
def two_version_ring() -> KeyRing:
    return KeyRing(current_version=2, masters={1: _MASTER, 2: _OTHER_MASTER})


def test_rotate_field_re_encrypts_under_the_new_version(two_version_ring: KeyRing) -> None:
    old_blob = encrypt_field("Sharma Traders", two_version_ring.key_data(1))

    new_blob = rotate_field(old_blob, from_version=1, to_version=2, ring=two_version_ring)

    assert decrypt_field(new_blob, two_version_ring.key_data(2)) == "Sharma Traders"


def test_rotated_blob_no_longer_decrypts_under_the_old_version(two_version_ring: KeyRing) -> None:
    old_blob = encrypt_field("Sharma Traders", two_version_ring.key_data(1))
    new_blob = rotate_field(old_blob, from_version=1, to_version=2, ring=two_version_ring)

    with pytest.raises(DecryptionError):
        decrypt_field(new_blob, two_version_ring.key_data(1))


def test_rotate_identity_field_recomputes_a_matching_blind_index(two_version_ring: KeyRing) -> None:
    old_blob = encrypt_field("Sharma Traders", two_version_ring.key_data(1))

    new_blob, new_bidx = rotate_identity_field(
        old_blob, from_version=1, to_version=2, ring=two_version_ring, column="borrower_name"
    )

    assert decrypt_field(new_blob, two_version_ring.key_data(2)) == "Sharma Traders"
    assert new_bidx == compute_blind_index(
        "Sharma Traders", two_version_ring.key_data(2), column="borrower_name"
    )


def test_rotating_a_subset_leaves_the_ring_able_to_read_both_versions(
    two_version_ring: KeyRing,
) -> None:
    """The acceptance exercise: rotate some rows, leave others alone, and
    confirm the same ring reads both `key_version`s correctly -- rotation
    never has to be a big-bang, all-rows-at-once operation.
    """
    rows = {
        "sharma": (encrypt_field("Sharma Traders", two_version_ring.key_data(1)), 1),
        "gupta": (encrypt_field("Gupta Finance", two_version_ring.key_data(1)), 1),
        "verma": (encrypt_field("Verma Loans", two_version_ring.key_data(1)), 1),
    }

    rotated_blob, _ = rotate_identity_field(
        rows["gupta"][0], from_version=1, to_version=2, ring=two_version_ring, column="borrower_name"
    )
    rows["gupta"] = (rotated_blob, 2)

    decrypted = {
        name: decrypt_field(blob, two_version_ring.key_data(version))
        for name, (blob, version) in rows.items()
    }

    assert decrypted == {
        "sharma": "Sharma Traders",
        "gupta": "Gupta Finance",
        "verma": "Verma Loans",
    }
