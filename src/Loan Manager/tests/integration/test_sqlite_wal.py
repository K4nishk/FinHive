"""WAL journal mode and `DatabaseSession.initialize(db_path=...)` (KCH-231).

Real files, not `:memory:` -- WAL is a filesystem-journalling mode and has
nothing to assert against an in-memory database.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from loan_manager.infrastructure.database.session import (
    DatabaseSession,
    create_sqlite_engine,
)


@pytest.fixture
def _reset_database_session():
    """`DatabaseSession` holds process-wide class attributes. Save/restore
    them around this module's tests so `initialize()` here can't leak a
    file-backed engine into any test that runs after (none currently reads
    `DatabaseSession` state directly, but the class is a global regardless).
    """
    saved_engine = DatabaseSession._engine
    saved_session_local = DatabaseSession._SessionLocal
    DatabaseSession._engine = None
    DatabaseSession._SessionLocal = None
    yield
    if DatabaseSession._engine is not None:
        DatabaseSession._engine.dispose()
    DatabaseSession._engine = saved_engine
    DatabaseSession._SessionLocal = saved_session_local


def test_engine_uses_wal_journal_mode(tmp_path: Path) -> None:
    db_path = tmp_path / "wal_engine.db"
    engine = create_sqlite_engine(db_path)

    try:
        with engine.connect() as conn:
            mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
        assert mode == "wal"
    finally:
        engine.dispose()


def test_a_second_connection_on_the_same_engine_is_also_wal(tmp_path: Path) -> None:
    """The `connect` listener must fire per-connection, not once for the
    engine -- SQLAlchemy's pool can open more than one DBAPI connection.
    """
    db_path = tmp_path / "wal_second_conn.db"
    engine = create_sqlite_engine(db_path)

    try:
        with engine.connect() as first:
            first.exec_driver_sql("PRAGMA journal_mode").scalar()
        with engine.connect() as second:
            mode = second.exec_driver_sql("PRAGMA journal_mode").scalar()
        assert mode == "wal"
    finally:
        engine.dispose()


def test_initialize_honours_db_path(tmp_path: Path, _reset_database_session) -> None:
    db_path = tmp_path / "custom" / "chosen.db"

    DatabaseSession.initialize(db_path=db_path)

    assert db_path.exists()
    engine = DatabaseSession.get_engine()
    assert Path(engine.url.database).resolve() == db_path.resolve()

    session = DatabaseSession.get_session()
    try:
        mode = session.connection().exec_driver_sql("PRAGMA journal_mode").scalar()
        assert mode == "wal"
    finally:
        session.close()


def test_worker_thread_reads_while_main_thread_holds_write(tmp_path: Path) -> None:
    """KCH-241: Ask FinHive reads the ledger from a QThread while the UI thread
    may be mid-write. In WAL a reader never blocks on the writer; in a rollback
    journal the read would raise `database is locked` (or hang to the timeout).
    """
    import threading

    from sqlalchemy import text

    engine = create_sqlite_engine(tmp_path / "wal_threads.db")
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
            conn.execute(text("INSERT INTO t (v) VALUES ('committed')"))

        outcome: dict[str, object] = {}

        def reader() -> None:
            try:
                with engine.connect() as conn:
                    outcome["rows"] = conn.execute(text("SELECT v FROM t")).scalars().all()
            except Exception as exc:  # noqa: BLE001 - reported through the assert below
                outcome["error"] = type(exc).__name__

        writer = engine.connect()
        try:
            # EXCLUSIVE is the strongest write lock: in a rollback journal it shuts
            # every reader out; in WAL it degrades to a plain write lock.
            writer.exec_driver_sql("BEGIN EXCLUSIVE")
            writer.execute(text("INSERT INTO t (v) VALUES ('uncommitted')"))
            thread = threading.Thread(target=reader)
            thread.start()
            thread.join(timeout=3)
            assert not thread.is_alive(), "reader blocked behind the open write transaction"
        finally:
            writer.rollback()
            writer.close()

        assert outcome == {"rows": ["committed"]}
    finally:
        engine.dispose()
