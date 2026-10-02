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

**Where the key comes from (F-006).** The environment first (macOS users who
put it in `ops/.env.local`, which `run_mac.sh` sources), else the key file
`data/encryption/master_key.key`, else a new key is created in that file on
first launch -- never when a database already holds encrypted data, because
a new key cannot read it. A key that lived only in one PowerShell window was
lost with the window, and blocking a first-time user until they set up a
password manager is a failure mode, not a safeguard.

**The master key is INTERIM, and its limit is written down rather than implied.**
It lives beside the database file (key file or `ops/.env.local`), so it defends
a stolen database copy or a synced database file and NOT an attacker with read
access to this home directory. That is a deliberate, recorded trade for a
single-user prototype (ARB D-15).
"""

from __future__ import annotations

import base64
import os
import secrets
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING

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
    "without its master key.\n\n"
    "Normally there is nothing to set up: on first launch the app creates the "
    "key in src/Loan Manager/data/encryption/master_key.key and reuses it on "
    "every launch after that. Keep a copy of that file somewhere else (a USB "
    "drive or a password manager), apart from your database backups.\n\n"
    "A key can also come from the environment, which takes priority over the "
    "file: FINHIVE_KEY_VERSION=1 and FINHIVE_MASTER_KEY_V1=<base64 of 32 "
    "random bytes>. run_mac.sh loads these from ops/.env.local.\n\n"
    "Losing the key makes every encrypted row unreadable and there is no "
    "recovery path."
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



# --- The key file (F-006) ---------------------------------------------------

_VERSION_NAME = "FINHIVE_KEY_VERSION"
_MASTER_PREFIX = "FINHIVE_MASTER_KEY_V"

_KEY_FILE_HEADER = """\
# FinHive Loan Manager master encryption key.
# Created automatically on first launch. The app reads it on every start.
#
# BACK THIS FILE UP somewhere other than this computer (USB drive, password
# manager), separately from your database backups. Without it your encrypted
# ledger can never be read again. Do not edit it and never share or commit it.
"""


def _key_vars(values: Mapping[str, str]) -> dict[str, str]:
    return {
        k: v for k, v in values.items()
        if k == _VERSION_NAME or k.startswith(_MASTER_PREFIX)
    }


def _read_key_file(path: Path) -> dict[str, str]:
    """`NAME=value` lines; `#` comments, blank lines, `export `, quotes, CRLF
    and a Notepad BOM tolerated. Errors name the line, never its value."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise KeyConfigurationError(f"Cannot read the key file {path}: {exc}") from exc
    values: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, sep, value = line.partition("=")
        if not sep:
            raise KeyConfigurationError(
                f"The key file {path} is damaged: line {number} is not NAME=value.\n\n"
                "Restore it from your backup. Do not delete it: a new key "
                "cannot read data the old one encrypted."
            )
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def _create_key_file(path: Path) -> dict[str, str]:
    values = {
        _VERSION_NAME: "1",
        f"{_MASTER_PREFIX}1": base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
    }
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    body = _KEY_FILE_HEADER + "".join(f"{k}={v}\n" for k, v in values.items())
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return values


def _announce_new_key(path: Path) -> None:
    from loan_manager.infrastructure.logging.logger import get_logger

    get_logger(__name__).warning("Created a new master encryption key at %s", path)
    rule = "=" * 72
    print(
        f"\n{rule}\n"
        "  A new encryption key was created for Loan Manager:\n\n"
        f"      {path}\n\n"
        "  BACK THIS FILE UP NOW (USB drive or password manager), apart from\n"
        "  your database backups. Without it your encrypted ledger can never\n"
        "  be read again. The app reuses this key on every launch.\n"
        f"{rule}\n",
        file=sys.stderr,
    )


def load_or_create_keys(
    env: Mapping[str, str] | None = None,
    key_file: Path | str | None = None,
    db_paths: Iterable[Path | str] | None = None,
) -> KeyRing:
    """The app's key ring: environment, else key file, else a new key file.

    `db_paths` are the databases this key will be used with (default: the
    app's `DB_PATH`). A new key is created only when none of them holds
    encrypted data; otherwise the person is told to restore their key.

    Raises `KeyConfigurationError` when the environment and the key file give
    different masters for one version -- rows written under one would be
    unreadable under the other, so neither is picked silently.
    """
    from loan_manager import config
    from loan_manager.infrastructure.migrations.encrypt_existing_rows import (
        holds_encrypted_rows,
    )

    env = os.environ if env is None else env
    path = Path(config.KEY_FILE if key_file is None else key_file)
    dbs = [Path(p) for p in ((config.DB_PATH,) if db_paths is None else db_paths)]
    from_file = _read_key_file(path) if path.exists() else None

    if env.get(_VERSION_NAME):
        if from_file is not None:
            env_vars, file_vars = _key_vars(env), _key_vars(from_file)
            clash = sorted(
                k for k in env_vars.keys() & file_vars.keys()
                if k.startswith(_MASTER_PREFIX) and env_vars[k] != file_vars[k]
            )
            if clash:
                raise KeyConfigurationError(
                    f"There are two different master keys for {', '.join(clash)}: one "
                    f"in the environment and one in {path}.\n\n"
                    "Data written under one cannot be read under the other, so the "
                    "app will not guess. Keep the one your ledger was encrypted with: "
                    "either remove the environment variables (setx / ops/.env.local) "
                    "or move the key file aside."
                )
        return load_keys(env)

    if from_file is not None:
        try:
            return load_keys(_key_vars(from_file))
        except KeyConfigurationError as exc:
            first_line = str(exc).split("\n", 1)[0]
            raise KeyConfigurationError(
                f"The key file {path} is damaged: {first_line}\n\n"
                "Restore it from your backup. Do not delete it: a new key "
                "cannot read data the old one encrypted."
            ) from exc

    locked = [db for db in dbs if holds_encrypted_rows(db)]
    if locked:
        listing = "\n".join(f"    {db}" for db in locked)
        raise KeyConfigurationError(
            "No master key was found, but this database already holds data "
            f"encrypted with one:\n{listing}\n\n"
            "A new key cannot read it, so none was created. Restore your key:\n"
            f"  - copy your backed-up key file to\n    {path}\n"
            "  - or set FINHIVE_KEY_VERSION and FINHIVE_MASTER_KEY_V1 as before.\n\n"
            "If this is the synthetic demo ledger, start it over instead:\n"
            "    ./run_local_mac.sh demo-reset      (macOS)\n"
            "    .\\run_local_windows.bat demo-reset (Windows)"
        )

    created = _create_key_file(path)
    _announce_new_key(path)
    return load_keys(created)
