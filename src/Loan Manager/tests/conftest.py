from pathlib import Path

import loan_manager.application.use_cases.data.export_loans as _export_loans_module
import loan_manager.config as _config
import loan_manager.infrastructure.database.session as _db_session_module
import loan_manager.infrastructure.logging.logger as _logger_module
import loan_manager.infrastructure.migrations.csv_to_sqlite as _csv_to_sqlite_module
import loan_manager.infrastructure.recovery.backup_service as _backup_service_module
import loan_manager.infrastructure.recovery.recovery_service as _recovery_service_module
import loan_manager.presentation.tabs.settings_tab as _settings_tab_module
import pytest
from loan_manager.infrastructure.database.models import Base
from loan_manager.infrastructure.security.key_provider import set_active_key_ring
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# KCH-227 (ARB D-15): every test that writes a LoanModel/LoanHistoryModel/
# ReportRecordModel row now goes through an encrypted-column TypeDecorator,
# which raises KeyConfigurationError unless a key ring is active. In the
# real app that happens once, at startup, via Container.get_key_ring() --
# nothing in this test suite constructs a Container, so nothing would ever
# set it. This autouse fixture is the test-suite equivalent of that startup
# step: it gives every test a deterministic key ring so existing tests keep
# exercising real encrypt/decrypt round-trips transparently, and clears it
# afterwards so tests that assert the no-active-key failure mode
# (tests/unit/test_encrypted_types.py) can do so in isolation by overriding
# it locally.
try:
    from finhive.db.keys import KeyRing

    _TEST_KEY_RING = KeyRing(current_version=1, masters={1: b"\x42" * 32})
except ImportError:  # pragma: no cover - exercised only without finhive/cryptography
    _TEST_KEY_RING = None


@pytest.fixture(autouse=True)
def _active_test_key_ring():
    set_active_key_ring(_TEST_KEY_RING)
    yield
    set_active_key_ring(None)


# --- KCH-231 review 1, item 1c: never let this suite touch the real ledger ---
#
# A mutated `assert_seed_target` guard (see `infrastructure/seed/demo_seed.py`)
# was found, during this issue's own fail-first testing, to have written the
# REAL `src/Loan Manager/data/loans.db` -- the live ledger on any machine that
# has one. Two independent fixtures close that off: `_redirect_data_paths`
# makes it structurally hard (every data-path constant this suite can reach
# points at a throwaway `tmp_path` for the duration of each test), and
# `_guard_real_ledger_untouched` is the tripwire that fails the whole run
# loudly if the real file changes anyway -- a mutation, a new test, or a
# module not yet listed below.

_REAL_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_REAL_LEDGER_FILES = tuple(_REAL_DATA_DIR / f"loans.db{suffix}" for suffix in ("", "-wal", "-shm"))
# The tracked `data/settings.json` (KCH-231 fix cycle 2, item 3) is exactly
# the file `settings_tab.py`/`main.py` would silently overwrite through an
# unpatched `SETTINGS_FILE` -- same tripwire reasoning as the ledger files
# above, watched alongside them rather than in a fixture of its own.
_REAL_SETTINGS_FILE = _REAL_DATA_DIR / "settings.json"
_REAL_WATCHED_FILES = _REAL_LEDGER_FILES + (_REAL_SETTINGS_FILE,)


def _ledger_fingerprint() -> dict[str, tuple[int, int] | None]:
    """(size, mtime_ns) per real watched file, or `None` if it does not
    exist. Cheap enough to take twice a session without reading file
    contents.
    """
    fingerprint: dict[str, tuple[int, int] | None] = {}
    for path in _REAL_WATCHED_FILES:
        if path.exists():
            stat = path.stat()
            fingerprint[str(path)] = (stat.st_size, stat.st_mtime_ns)
        else:
            fingerprint[str(path)] = None
    return fingerprint


@pytest.fixture(scope="session", autouse=True)
def _guard_real_ledger_untouched():
    """Session-wide tripwire around the ENTIRE test run (session-scoped, so
    its snapshot is taken before the first test and its assertion runs after
    the last): the real `data/loans.db` and its `-wal`/`-shm` sidecars, and
    the tracked `data/settings.json`, must come out exactly as they went in,
    or the run fails.
    """
    before = _ledger_fingerprint()
    yield
    after = _ledger_fingerprint()
    changed = {path: (before[path], after[path]) for path in before if before[path] != after[path]}
    assert not changed, (
        f"a test wrote to a REAL watched file under {_REAL_DATA_DIR} -- this "
        f"must never happen: {changed}"
    )


@pytest.fixture(autouse=True)
def _redirect_data_paths(tmp_path, monkeypatch):
    """Redirect `DB_PATH`/`DEFAULT_DB_PATH` and the `DATA_DIR`-derived log,
    backup and export directories and `RECOVERY_FILE` to a per-test
    `tmp_path`, so nothing under this suite can create or write to the real
    `src/Loan Manager/data/` tree.

    Patching `loan_manager.config`'s own attributes is not enough: several
    modules did `from loan_manager.config import X` -- a BY-VALUE import
    that copies the object into that module's own namespace at import time.
    Reassigning `config.X` afterwards never reaches an already-bound name in
    one of those modules (this is exactly the bug `demo_seed.
    assert_seed_target` had -- see its docstring), so each such module is
    patched here too, directly, alongside `config` itself.
    """
    fake_data_dir = tmp_path / "data"
    fake_db_path = fake_data_dir / "loans.db"
    fake_log_dir = fake_data_dir / "logs"
    fake_log_file = fake_log_dir / "app.log"
    fake_backup_dir = fake_data_dir / "backups"
    fake_export_dir = fake_data_dir / "exports"
    fake_recovery_file = fake_data_dir / "approval_recovery.tmp"
    fake_settings_file = fake_data_dir / "settings.json"

    patches = (
        (
            _config,
            {
                "DATA_DIR": fake_data_dir,
                "DB_PATH": fake_db_path,
                "DEFAULT_DB_PATH": fake_db_path,
                "LOG_DIR": fake_log_dir,
                "LOG_FILE": fake_log_file,
                "BACKUP_DIR": fake_backup_dir,
                "EXPORT_DIR": fake_export_dir,
                "RECOVERY_FILE": fake_recovery_file,
                "SETTINGS_FILE": fake_settings_file,
            },
        ),
        (
            _db_session_module,
            {
                "DATA_DIR": fake_data_dir,
                "DB_PATH": fake_db_path,
                "LOG_DIR": fake_log_dir,
                "BACKUP_DIR": fake_backup_dir,
                "EXPORT_DIR": fake_export_dir,
            },
        ),
        (_backup_service_module, {"BACKUP_DIR": fake_backup_dir, "DB_PATH": fake_db_path}),
        (_recovery_service_module, {"RECOVERY_FILE": fake_recovery_file}),
        (_logger_module, {"LOG_DIR": fake_log_dir, "LOG_FILE": fake_log_file}),
        (_export_loans_module, {"EXPORT_DIR": fake_export_dir}),
        # `settings_tab.py` does `from loan_manager.config import
        # SETTINGS_FILE, DATA_DIR` at its OWN module load (a by-value import,
        # same trap as everything else in this fixture's docstring), so
        # patching `config.SETTINGS_FILE` alone never reaches its already-
        # bound name -- it must be patched here directly too (KCH-231 fix
        # cycle 2, item 3; `main.py`'s `_load_saved_theme`/
        # `_load_custom_colours` re-import `SETTINGS_FILE` from `config`
        # fresh on every call, so patching `config` alone already covers
        # them).
        (_settings_tab_module, {"SETTINGS_FILE": fake_settings_file, "DATA_DIR": fake_data_dir}),
        # `csv_to_sqlite.py` does `from loan_manager.config import DATA_DIR`
        # at its own module load too -- same reasoning.
        (_csv_to_sqlite_module, {"DATA_DIR": fake_data_dir}),
    )
    for module, attrs in patches:
        for attr, value in attrs.items():
            monkeypatch.setattr(module, attr, value)

    yield


@pytest.fixture(scope="function")
def in_memory_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(in_memory_engine):
    Session = sessionmaker(bind=in_memory_engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()
