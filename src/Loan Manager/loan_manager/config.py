from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "loans.db"


def resolve_db_path(env: Mapping[str, str] | None = None) -> Path:
    """The SQLite file the app opens: `FINHIVE_DB_PATH` if set, else
    `DEFAULT_DB_PATH` (KCH-231 -- lets the demo seeder and manual testing
    point at a throwaway file without touching the live database).

    A blank, whitespace-only, or unset `FINHIVE_DB_PATH` falls back to
    `DEFAULT_DB_PATH` rather than resolving `""` (or `" "`) to the current
    directory. Any other value is
    `expanduser()`-ed and `resolve()`-ed to an absolute path, so it can be
    compared reliably (`==`, `os.path.samefile`) against `DEFAULT_DB_PATH`
    regardless of how it was spelled -- see
    `infrastructure/seed/demo_seed.py::assert_seed_target`, which depends on
    that to refuse seeding onto the live database.

    `env` is injectable so tests never touch the real environment; `None`
    (the default) reads `os.environ`, as `finhive.db.keys.load_key_ring`
    does for the same reason.
    """
    env = os.environ if env is None else env
    raw = env.get("FINHIVE_DB_PATH", "").strip()
    if not raw:
        return DEFAULT_DB_PATH
    return Path(raw).expanduser().resolve()


DB_PATH = resolve_db_path()
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"
RECOVERY_FILE = DATA_DIR / "approval_recovery.tmp"
BACKUP_DIR = DATA_DIR / "backups"
SETTINGS_FILE = DATA_DIR / "settings.json"
EXPORT_DIR = DATA_DIR / "exports"

# Derived from DB_PATH, not DEFAULT_DB_PATH, so this stays consistent with
# whichever database FINHIVE_DB_PATH actually selected.
DATABASE_URL = f"sqlite:///{DB_PATH}"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB
LOG_BACKUP_COUNT = 3
