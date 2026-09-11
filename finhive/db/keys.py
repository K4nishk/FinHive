"""Master key loading, HKDF derivation and rotation (ADR-2.3 "Key management", KCH-97).

`finhive/db/encryption.py` and `finhive/db/blind_index.py` both take a raw
32-byte `key_data` from their caller and do no key management of their own.
This module is that caller: it loads one 32-byte master per `key_version`
from the environment, derives `key_data` from the master via HKDF with an
info string distinct from every other key this project derives (mirroring
how `blind_index.derive_key_index` derives `key_index` from `key_data`), and
re-encrypts a field from one `key_version`'s key to another's for rotation.

Master keys live in `ops/.env.local` for M1a (gitignored, never committed) --
see `docs/LOCAL_SETUP_MACOS.md` "Encryption master key" and
`docs/KEY_MANAGEMENT.md` for generation, rotation and backup/restore. M3+
moves them to Supabase Vault or a KMS, fetched at boot and held in memory
only -- `load_key_ring`'s `env` parameter exists so that swap doesn't need to
change any caller, only what mapping gets passed in.

Environment variables:

    FINHIVE_KEY_VERSION           The `key_version` new writes are encrypted
                                   under. Must name a version that also has a
                                   `FINHIVE_MASTER_KEY_V<n>` set.
    FINHIVE_MASTER_KEY_V<n>       Base64-encoded 32-byte master for
                                   `key_version` n. One var per version still
                                   needed for reading -- keep the old
                                   version's var set until rotation has
                                   migrated every row off it.

Rotation is incremental, never a big-bang re-encrypt: `rotate_field` (and
`rotate_identity_field`, which also recomputes the paired blind index)
re-encrypt one row's ciphertext from an old `key_version` to a new one. The
caller persists the returned blob(s) together with the new `key_version` in
the same row update. Rows not yet migrated keep decrypting under their
existing `key_version` for as long as that version's master stays loaded --
so reads never block on rotation completing.
"""

from __future__ import annotations

import base64
import binascii
import os
from collections.abc import Mapping
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from finhive.db.blind_index import compute_blind_index, derive_key_index
from finhive.db.encryption import KEY_LENGTH, decrypt_field, encrypt_field

_MASTER_KEY_ENV_PREFIX = "FINHIVE_MASTER_KEY_V"
_CURRENT_VERSION_ENV = "FINHIVE_KEY_VERSION"

# Distinct from `blind_index._KEY_INDEX_INFO` and from any other info string
# this project derives a key with -- the whole point is that `key_data` can
# never be recomputed as, or confused with, any other derived key.
_KEY_DATA_INFO = b"finhive-aes-gcm-key-v1"


class ConfigError(Exception):
    """A required key-management environment variable is missing or malformed."""


def derive_key_data(master_key: bytes) -> bytes:
    """HKDF-derive the AES-GCM key from a 32-byte master.

    `blind_index.derive_key_index` then derives `key_index` from this
    `key_data` with its own distinct info string, so the two keys used for
    one `key_version` are never the same bytes -- ADR-2.3 "Key management":
    "Never the same key for both -- reusing it lets a blind index leak
    information about the encryption key's use."
    """
    if len(master_key) != KEY_LENGTH:
        raise ValueError(f"master key must be {KEY_LENGTH} bytes, got {len(master_key)}")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=None,
        info=_KEY_DATA_INFO,
    ).derive(master_key)


def _decode_master_key(raw: str, *, env_name: str) -> bytes:
    try:
        key = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ConfigError(f"{env_name} is not valid base64") from exc
    if len(key) != KEY_LENGTH:
        raise ConfigError(f"{env_name} must decode to {KEY_LENGTH} bytes, got {len(key)}")
    return key


@dataclass(frozen=True)
class KeyRing:
    """Every master key still loaded, plus which `key_version` new writes use.

    `key_data`/`key_index` derive on every call rather than caching, since
    this is a handful of HKDF derivations per request, not a hot loop --
    caching key material longer than necessary is a cost with no measured
    benefit here.
    """

    current_version: int
    masters: Mapping[int, bytes]

    def key_data(self, version: int | None = None) -> bytes:
        return derive_key_data(self._master(self.current_version if version is None else version))

    def key_index(self, version: int | None = None) -> bytes:
        return derive_key_index(self.key_data(version))

    def _master(self, version: int) -> bytes:
        try:
            return self.masters[version]
        except KeyError:
            raise ConfigError(
                f"no master key loaded for key_version {version} -- set "
                f"{_MASTER_KEY_ENV_PREFIX}{version}"
            ) from None


def load_key_ring(env: Mapping[str, str] | None = None) -> KeyRing:
    """Load every `FINHIVE_MASTER_KEY_V<n>` present in `env` (defaults to `os.environ`).

    Raises `ConfigError` if `FINHIVE_KEY_VERSION` is missing, non-numeric, or
    names a version with no corresponding master key set -- new writes must
    always have a usable key.
    """
    env = os.environ if env is None else env
    current_raw = env.get(_CURRENT_VERSION_ENV)
    if not current_raw:
        raise ConfigError(f"missing required environment variable: {_CURRENT_VERSION_ENV}")
    try:
        current_version = int(current_raw)
    except ValueError:
        raise ConfigError(
            f"{_CURRENT_VERSION_ENV} must be an integer, got {current_raw!r}"
        ) from None

    masters: dict[int, bytes] = {}
    for name, raw in env.items():
        if not name.startswith(_MASTER_KEY_ENV_PREFIX):
            continue
        suffix = name[len(_MASTER_KEY_ENV_PREFIX) :]
        if not suffix.isdigit():
            continue
        masters[int(suffix)] = _decode_master_key(raw, env_name=name)

    if current_version not in masters:
        raise ConfigError(
            f"{_CURRENT_VERSION_ENV}={current_version} but "
            f"{_MASTER_KEY_ENV_PREFIX}{current_version} is not set"
        )
    return KeyRing(current_version=current_version, masters=masters)


def rotate_field(blob: bytes, *, from_version: int, to_version: int, ring: KeyRing) -> bytes:
    """Re-encrypt a `_ct` blob from `from_version`'s key to `to_version`'s.

    Only performs the decrypt/re-encrypt -- the caller writes the returned
    blob together with `key_version = to_version` in the same row update.
    """
    plaintext = decrypt_field(blob, ring.key_data(from_version))
    return encrypt_field(plaintext, ring.key_data(to_version))


def rotate_identity_field(
    blob: bytes, *, from_version: int, to_version: int, ring: KeyRing, column: str
) -> tuple[bytes, bytes]:
    """Re-encrypt a `_ct` blob and recompute its paired `_bidx` under `to_version`.

    `key_index` is derived per `key_version` (via that version's `key_data`),
    so rotating the ciphertext without recomputing the blind index would
    leave a `_bidx` value that no longer matches what `to_version`'s key
    computes for the same plaintext -- silently breaking A5.8 exact-match
    filtering for that row. Never used for amount columns (ADR-2.4): those
    have no blind index to recompute, so `rotate_field` alone is correct
    there.
    """
    plaintext = decrypt_field(blob, ring.key_data(from_version))
    new_blob = encrypt_field(plaintext, ring.key_data(to_version))
    new_bidx = compute_blind_index(plaintext, ring.key_data(to_version), column=column)
    return new_blob, new_bidx
