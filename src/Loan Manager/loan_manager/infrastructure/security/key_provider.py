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
