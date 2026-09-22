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

# Applied per-test, NOT at module scope: the Container laziness test needs no
# cryptography at all, and a module-scope importorskip would hide it in exactly
# the environment where it is cheapest to run. A test that always skips looks
# like coverage without being any.
needs_crypto = pytest.mark.skipif(
    __import__("importlib.util", fromlist=["util"]).find_spec("cryptography") is None,
    reason="encryption at rest needs `cryptography`; see requirements.txt",
)

_VALID = base64.b64encode(b"\x01" * 32).decode()


def _env(**over: str) -> dict[str, str]:
    base = {"FINHIVE_KEY_VERSION": "1", "FINHIVE_MASTER_KEY_V1": _VALID}
    base.update(over)
    return base


@needs_crypto
def test_loads_a_key_ring_from_a_complete_environment() -> None:
    ring = load_keys(_env())

    assert ring.current_version == 1
    assert len(ring.key_data()) == 32


@needs_crypto
def test_key_index_derives_from_the_master_not_from_key_data() -> None:
    """Leaking key_data via an encrypt/decrypt path must not also leak the
    blind-index HMAC key.

    Asserting only `key_data() != key_index()` would NOT prove this — that holds
    even if key_index were HKDF(key_data), which is the exact design being ruled
    out. Assert the derivation INPUT instead.
    """
    from finhive.db.blind_index import derive_key_index
    from finhive.db.keys import derive_key_data

    master = b"\x01" * 32
    ring = load_keys(_env())

    assert ring.key_index() == derive_key_index(master)
    assert ring.key_index() != derive_key_index(derive_key_data(master))


@needs_crypto
def test_refuses_to_start_without_a_key_version() -> None:
    with pytest.raises(KeyConfigurationError) as e:
        load_keys({"FINHIVE_MASTER_KEY_V1": _VALID})

    assert "FINHIVE_KEY_VERSION" in str(e.value)


@needs_crypto
def test_refuses_to_start_when_the_named_version_has_no_master() -> None:
    """The version pointer and the key itself must agree; a dangling pointer
    means new writes have no usable key."""
    with pytest.raises(KeyConfigurationError):
        load_keys({"FINHIVE_KEY_VERSION": "2", "FINHIVE_MASTER_KEY_V1": _VALID})


# "" is deliberately NOT here: keys.py:148 `if not current_raw` catches it as a
# MISSING variable before the int() branch is reached, so it would pass through a
# different code path and go green for the wrong reason.
@needs_crypto
@pytest.mark.parametrize("bad", ["not-a-number", "1.5", "one"])
def test_refuses_a_non_integer_key_version(bad: str) -> None:
    with pytest.raises(KeyConfigurationError, match="integer"):
        load_keys(_env(FINHIVE_KEY_VERSION=bad))


@needs_crypto
def test_an_empty_key_version_reads_as_missing_not_as_non_integer() -> None:
    with pytest.raises(KeyConfigurationError, match="missing required"):
        load_keys(_env(FINHIVE_KEY_VERSION=""))


@needs_crypto
def test_refuses_a_hex_key_mistaken_for_base64() -> None:
    """The likeliest real mistake: 64 hex chars are VALID base64 and decode to
    48 bytes, so this is caught on length rather than on encoding."""
    with pytest.raises(KeyConfigurationError):
        load_keys(_env(FINHIVE_MASTER_KEY_V1="ab" * 32))


@needs_crypto
def test_refuses_a_master_key_that_is_not_base64() -> None:
    with pytest.raises(KeyConfigurationError):
        load_keys(_env(FINHIVE_MASTER_KEY_V1="!!! not base64 !!!"))


@needs_crypto
@pytest.mark.parametrize("n", [16, 31, 33])
def test_refuses_a_master_key_that_is_not_32_bytes(n: int) -> None:
    """AES-256 needs exactly 32 bytes. A 16-byte key would otherwise silently
    weaken every row written with it."""
    with pytest.raises(KeyConfigurationError):
        load_keys(_env(FINHIVE_MASTER_KEY_V1=base64.b64encode(b"\x02" * n).decode()))


@needs_crypto
def test_the_error_tells_the_user_how_to_fix_it() -> None:
    """The reader is the single desktop user, not an operator with a runbook."""
    with pytest.raises(KeyConfigurationError) as e:
        load_keys({})

    msg = str(e.value)
    assert "FINHIVE_KEY_VERSION=1" in msg
    assert "ops/.env.local" in msg
    assert "urandom(32)" in msg          # how to generate one
    assert "no recovery path" in msg     # and why not to lose it


def test_container_does_not_load_the_key_ring_in_init() -> None:
    """Constructing a Container in a test that never touches encryption must not
    require a configured key."""
    from loan_manager.container import Container

    c = Container()
    assert c._key_ring is None


@needs_crypto
def test_container_caches_the_key_ring_across_calls(monkeypatch) -> None:
    """Repositories obtain keys from Container, never from os.environ — and the
    ring is loaded once per process, not per call."""
    from loan_manager.container import Container

    monkeypatch.setenv("FINHIVE_KEY_VERSION", "1")
    monkeypatch.setenv("FINHIVE_MASTER_KEY_V1", _VALID)

    c = Container()
    first = c.get_key_ring()

    assert first.current_version == 1
    assert c.get_key_ring() is first
