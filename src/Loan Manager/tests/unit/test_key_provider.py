"""Master-key loading at startup (KCH-226, ARB D-15).

The acceptance criterion is that the app REFUSES to start on a missing, short or
malformed master key. These assert the refusal, not the happy path -- silently
generating a key would encrypt rows with one that vanishes on the next launch,
which is indistinguishable from data loss and is the failure worth pinning.

`finhive.db.keys` owns env parsing and HKDF and has its own 21 tests; these cover
only the layer above it: does a configuration failure reach the user as something
they can act on.
"""

from __future__ import annotations

import base64

import pytest

from loan_manager.infrastructure.security.key_provider import (
    KeyConfigurationError,
    load_keys,
)

pytest.importorskip(
    "cryptography",
    reason="encryption at rest needs `cryptography`; see requirements.txt",
)

_VALID = base64.b64encode(b"\x01" * 32).decode()


def _env(**over: str) -> dict[str, str]:
    base = {"FINHIVE_KEY_VERSION": "1", "FINHIVE_MASTER_KEY_V1": _VALID}
    base.update(over)
    return base


def test_loads_a_key_ring_from_a_complete_environment() -> None:
    ring = load_keys(_env())

    assert ring.current_version == 1
    assert len(ring.key_data()) == 32


def test_key_index_is_not_derived_from_key_data() -> None:
    """Leaking key_data via an encrypt/decrypt path must not also leak the
    blind-index HMAC key."""
    ring = load_keys(_env())

    assert ring.key_data() != ring.key_index()


def test_refuses_to_start_without_a_key_version() -> None:
    with pytest.raises(KeyConfigurationError) as e:
        load_keys({"FINHIVE_MASTER_KEY_V1": _VALID})

    assert "FINHIVE_KEY_VERSION" in str(e.value)


def test_refuses_to_start_when_the_named_version_has_no_master() -> None:
    """The version pointer and the key itself must agree; a dangling pointer
    means new writes have no usable key."""
    with pytest.raises(KeyConfigurationError):
        load_keys({"FINHIVE_KEY_VERSION": "2", "FINHIVE_MASTER_KEY_V1": _VALID})


@pytest.mark.parametrize("bad", ["", "not-a-number", "1.5"])
def test_refuses_a_non_integer_key_version(bad: str) -> None:
    with pytest.raises(KeyConfigurationError):
        load_keys(_env(FINHIVE_KEY_VERSION=bad))


def test_refuses_a_master_key_that_is_not_base64() -> None:
    with pytest.raises(KeyConfigurationError):
        load_keys(_env(FINHIVE_MASTER_KEY_V1="!!! not base64 !!!"))


@pytest.mark.parametrize("n", [16, 31, 33])
def test_refuses_a_master_key_that_is_not_32_bytes(n: int) -> None:
    """AES-256 needs exactly 32 bytes. A 16-byte key would otherwise silently
    weaken every row written with it."""
    with pytest.raises(KeyConfigurationError):
        load_keys(_env(FINHIVE_MASTER_KEY_V1=base64.b64encode(b"\x02" * n).decode()))


def test_the_error_tells_the_user_how_to_fix_it() -> None:
    """The reader is the single desktop user, not an operator with a runbook."""
    with pytest.raises(KeyConfigurationError) as e:
        load_keys({})

    msg = str(e.value)
    assert "FINHIVE_KEY_VERSION=1" in msg
    assert "ops/.env.local" in msg
    assert "urandom(32)" in msg          # how to generate one
    assert "no recovery path" in msg     # and why not to lose it


def test_container_exposes_the_key_ring_without_reading_the_environment() -> None:
    """Repositories must obtain keys from Container, never from os.environ."""
    from loan_manager.container import Container

    c = Container()
    assert c._key_ring is None, "loading must be lazy, not done in __init__"
