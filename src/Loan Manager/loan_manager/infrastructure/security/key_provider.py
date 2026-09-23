"""Master-key loading for the desktop app (KCH-226, ARB D-15).

`finhive.db.keys.load_key_ring` already reads `FINHIVE_MASTER_KEY_V<n>` and
`FINHIVE_KEY_VERSION` from the environment, derives `key_data` and `key_index`
via HKDF, and raises `ConfigError` on anything missing or malformed. This module
does not reimplement any of that. It does two things that layer above it:

1. Turns a configuration failure into an actionable startup message, because
   the person hitting it is the single desktop user, not an operator reading a
   stack trace.
2. Gives `Container` one call site, so swapping the key source later -- the OS
   keychain, per the written trigger in ARB D-15 -- is a change to this file and
   nothing else.

No provider registry and no factory. There is one source today; ARB D-15 records
the trigger for adding a second (a second user, a hosted deployment, or the
database file leaving this machine).

**The master key is INTERIM, and its limit is written down rather than implied.**
It lives in `ops/.env.local` beside the database file, so it defends a stolen
backup or a synced folder and NOT an attacker with read access to this home
directory. That is a deliberate, recorded trade for a single-user prototype.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:  # pragma: no cover - typing only
    from finhive.db.keys import KeyRing


class KeyConfigurationError(RuntimeError):
    """The master key is missing or unusable, so nothing may be written.

    Raised at startup, never mid-write: a partially-configured key would
    encrypt some rows with a key that vanishes on the next launch, which is
    indistinguishable from data loss.
    """


_SETUP_HELP = (
    "Encryption at rest is mandatory (ARB D-15) and the app cannot start "
    "without a master key.\n\n"
    "Generate one:\n"
    "    python3 -c \"import os,base64; "
    'print(base64.b64encode(os.urandom(32)).decode())"\n\n'
    "Then set BOTH variables. run_mac.sh sources ops/.env.local, so on macOS "
    "putting them there and relaunching through it is enough:\n"
    "    export FINHIVE_KEY_VERSION=1\n"
    '    export FINHIVE_MASTER_KEY_V1="<the base64 value>"\n\n'
    "On Windows, or when starting the app directly rather than through a "
    "launcher, export them in the shell you launch from — nothing in the app "
    "reads a dotenv file.\n\n"
    "Keep the key. Losing it makes every encrypted row unreadable and there is "
    "no recovery path.\n\n"
    "Note on what this protects: the key sits beside the database file, so it "
    "defends a stolen backup or a synced folder, NOT someone with read access "
    "to this machine. That is a recorded interim trade for a single-user "
    "prototype (ARB D-15)."
)


def load_keys(env: Mapping[str, str] | None = None) -> KeyRing:
    """Return the configured `KeyRing`, or fail with something actionable.

    `env` is injectable so tests never touch the real environment.
    """
    try:
        from finhive.db.keys import ConfigError, load_key_ring
    except ImportError as exc:  # missing `cryptography`, or finhive not installed
        raise KeyConfigurationError(
            f"Cannot load the encryption module: {exc}.\n\n"
            "The desktop app depends on the finhive package and on "
            "`cryptography`. Install them into this virtualenv:\n"
            "    pip install -r requirements.txt\n\n"
            "If finhive itself is missing, install the repository root as an "
            "editable package:\n"
            "    pip install -e ../.."
        ) from exc

    try:
        return load_key_ring(env)
    except ConfigError as exc:
        raise KeyConfigurationError(f"{exc}\n\n{_SETUP_HELP}") from exc


# --- Process-wide active key, for the ORM<->DB encryption boundary --------
#
# `encrypted_types.py`'s TypeDecorators run inside SQLAlchemy's bind/result
# machinery, far from any call site that has a `Container` in scope, so they
# cannot take the key ring as a constructor argument the way a repository
# could. This module-level slot is the one place they reach instead.
#
# `Container.get_key_ring()` calls `set_active_key_ring` immediately after
# `load_keys()` succeeds, so the app's existing startup path (main.py step 3a
# already calls `get_key_ring()` before anything can write) wires this up
# with no additional call site. Deliberately just one variable and one
# accessor -- no registry, no provider abstraction, because there is exactly
# one key source today (see the module docstring).

_active: KeyRing | None = None


def set_active_key_ring(ring: KeyRing | None) -> None:
    """Make `ring` the key the encrypted-column TypeDecorators use.

    Called by `Container.get_key_ring()` after a successful load. `None`
    clears it, which tests use to assert the no-active-key failure mode
    (`active_key_data` raising `KeyConfigurationError`) in isolation.
    """
    global _active
    _active = ring


def active_key_data() -> bytes:
    """The 32-byte AES-GCM key the encrypted-column TypeDecorators bind and
    decrypt with.

    Raises `KeyConfigurationError` rather than ever falling back to writing
    or reading plaintext -- a decorator invoked before the key ring is wired
    up (or after it was cleared) must fail loudly, the same contract
    `load_keys` gives the rest of startup.
    """
    if _active is None:
        raise KeyConfigurationError(
            "No active key ring is set -- Container.get_key_ring() must run "
            "before any encrypted column is read or written.\n\n"
            f"{_SETUP_HELP}"
        )
    return _active.key_data()


def active_key_index() -> bytes:
    """The 32-byte HMAC key the identity-column blind-index hooks and
    equality filters use (KCH-227/229, ADR-2.3).

    Deliberately a *separate* accessor from `active_key_data`, not a
    parameter on it: `KeyRing.key_index()` is derived independently from
    the master via its own HKDF info string, precisely so leaking
    `key_data` (which every encrypt/decrypt call touches) never also
    leaks `key_index` -- see `test_key_index_derives_from_the_master_not_from_key_data`
    in `tests/unit/test_key_provider.py`. Raises `KeyConfigurationError`
    on the same no-active-key condition as `active_key_data`.
    """
    if _active is None:
        raise KeyConfigurationError(
            "No active key ring is set -- Container.get_key_ring() must run "
            "before any blind index is computed or queried.\n\n"
            f"{_SETUP_HELP}"
        )
    return _active.key_index()


def active_key_version() -> int:
    """The key version new ciphertext is being written under.

    Rows stamp this into their `key_version` column so a later rotation can
    tell which master produced them. Before KCH-227's follow-up fix that
    column was a hardcoded `default=1`, which recorded a version the row was
    not necessarily encrypted under -- worse than not recording one, because
    it looks authoritative.
    """
    if _active is None:
        raise KeyConfigurationError(
            "No active key ring is set -- Container.get_key_ring() must run "
            "before any encrypted column is written.\n\n"
            f"{_SETUP_HELP}"
        )
    return _active.current_version


def candidate_key_data() -> list[bytes]:
    """Every loaded master's `key_data`, current version FIRST.

    This is what makes rotation actually work. `finhive/db/keys.py` promises:
    "Rows not yet migrated keep decrypting under their existing key_version
    for as long as that version's master stays loaded." Decrypting only with
    `active_key_data()` breaks that promise -- bumping FINHIVE_KEY_VERSION
    would make every pre-rotation row permanently unreadable.

    A `TypeDecorator.process_result_value` receives only its own column's
    bytes, never the sibling `key_version`, and the stored blob is bare
    `iv || ciphertext || tag` with no version header -- so the decorator
    cannot look the version up. Trying each loaded master instead is sound
    because AES-GCM's authentication tag is the discriminator: a wrong key
    fails the tag check rather than returning wrong plaintext, so there are
    no false positives to worry about.

    Ordered current-first so the common case is one attempt. With a single
    configured key -- today's state -- this is exactly as cheap as before.
    """
    if _active is None:
        raise KeyConfigurationError(
            "No active key ring is set -- Container.get_key_ring() must run "
            "before any encrypted column is read.\n\n"
            f"{_SETUP_HELP}"
        )
    current = _active.current_version
    versions = [current] + sorted(v for v in _active.masters if v != current)
    return [_active.key_data(v) for v in versions]


def candidate_key_index() -> list[bytes]:
    """Every loaded master's `key_index`, current version FIRST.

    The read-side counterpart to `candidate_key_data`, and it exists because
    of a failure found by actually rotating a key rather than reasoning about
    it: with only `active_key_index()`, a row whose `_bidx` was computed
    under v1 stops matching any filter the moment the ring advances to v2.

    That failure is SILENT -- the query is valid, it simply returns zero
    rows, so the user sees "no loans matched" for a loan book that is fully
    intact and still decryptable. A filter must therefore match a row
    indexed under ANY loaded version, which is an `IN` over these values.
    Unlike `candidate_key_data`, there is no authentication tag to tell a
    right index from a wrong one, so this cannot be a try-each loop -- the
    match itself has to span the versions.
    """
    if _active is None:
        raise KeyConfigurationError(
            "No active key ring is set -- Container.get_key_ring() must run "
            "before any blind index is queried.\n\n"
            f"{_SETUP_HELP}"
        )
    current = _active.current_version
    versions = [current] + sorted(v for v in _active.masters if v != current)
    return [_active.key_index(v) for v in versions]
