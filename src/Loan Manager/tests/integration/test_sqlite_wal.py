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
