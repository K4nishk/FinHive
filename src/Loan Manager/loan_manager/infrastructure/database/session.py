from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import Session, sessionmaker

from loan_manager.config import BACKUP_DIR, DATA_DIR, DB_PATH, EXPORT_DIR, LOG_DIR
from loan_manager.infrastructure.database.models import Base


def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    """`PRAGMA journal_mode=WAL` on every new DBAPI connection.

    docs/MVP1_1_ASK_FINHIVE.md §4 requires WAL: Ask FinHive (KCH-241) reads
    from a worker `QThread` on its own SQLite connection while the UI thread
    may be mid-write on another. SQLite's default (DELETE/rollback-journal)
    mode takes an exclusive lock for the whole write, which would stall the
    UI thread's own queries behind the agent's, and vice versa; WAL lets
    readers proceed against the last-committed snapshot concurrently with a
    writer. This is connection CONFIGURATION, not a data query -- ORCH
    ruling (KCH-231 plan) is that it belongs here, in the `connect` event
    listener, same as `check_same_thread` below.

    WAL keeps `<db>-wal`/`<db>-shm` sidecar files beside the main one and
    depends on POSIX shared-memory semantics between processes mapping them.
    It does NOT work correctly on a network filesystem or a folder synced by
    Dropbox/OneDrive/iCloud Drive/Google Drive -- writes are not guaranteed
    visible to another reader of the same file there. `data/` (and any
    `FINHIVE_DB_PATH` override) must stay on local disk.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def create_sqlite_engine(db_path: Path) -> Engine:
    """One SQLite `Engine` bound to `db_path`, WAL-enabled via the `connect`
    listener above.

    `check_same_thread=False` is required for the same reason as WAL: a
    `QThread` worker and the UI thread each open their own `Session` (never
    share one connection unsynchronised), but SQLAlchemy's own connection
    pool is what actually recycles the underlying DBAPI connection, and its
    housekeeping can run off the thread that first created it.
    """
    engine = create_engine(
        URL.create("sqlite", database=str(db_path)),
        connect_args={"check_same_thread": False},
        echo=False,
    )
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


class DatabaseSession:
    _engine: Engine | None = None
    _SessionLocal = None

    @classmethod
    def initialize(cls, db_path: Path | None = None) -> None:
        """Wire the process-wide engine/session factory.

        `db_path` defaults to the module-level `DB_PATH` (itself
        `FINHIVE_DB_PATH` or `DEFAULT_DB_PATH`, see `config.py`) so existing
        callers (`main.py`) are unaffected; the demo seeder passes an
        explicit path instead of relying on the environment.
        """
        db_path = DB_PATH if db_path is None else db_path

        # Create required directories, including db_path's own parent when
        # it differs from DATA_DIR (a demo DB living elsewhere).
        for d in [DATA_DIR, LOG_DIR, BACKUP_DIR, EXPORT_DIR, db_path.parent]:
            d.mkdir(parents=True, exist_ok=True)

        cls._engine = create_sqlite_engine(db_path)
        Base.metadata.create_all(cls._engine)
        cls._SessionLocal = sessionmaker(bind=cls._engine, expire_on_commit=False)

    @classmethod
    def get_session(cls) -> Session:
        if cls._SessionLocal is None:
            raise RuntimeError("DatabaseSession not initialized. Call initialize() first.")
        return cls._SessionLocal()

    @classmethod
    def get_engine(cls):
        return cls._engine
