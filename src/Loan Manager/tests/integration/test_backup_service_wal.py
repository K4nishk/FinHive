"""`BackupService.create_backup` must survive WAL journalling (KCH-231).

`shutil.copy2` only copies the main `.db` file; in WAL mode a committed row
can live solely in `<db>-wal` until checkpointed back in, so a `copy2`
backup silently drops it. `sqlite3.Connection.backup` reads through
SQLite's own backup API instead, which merges the WAL.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import loan_manager.infrastructure.recovery.backup_service as backup_module
import pytest
from loan_manager.infrastructure.recovery.backup_service import BackupService


def _make_wal_db_with_uncheckpointed_row(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (x TEXT)")
    conn.commit()
    conn.execute("INSERT INTO t VALUES ('row-in-wal-only')")
    conn.commit()
    # Left open, deliberately: closing the last connection to a WAL
    # database auto-checkpoints it, which would erase the very
    # condition this test exercises (a row that exists only in -wal).
    return conn


def test_backup_contains_rows_still_in_wal(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(backup_module, "BACKUP_DIR", backup_dir)

    source_conn = _make_wal_db_with_uncheckpointed_row(db_path)
    try:
        assert db_path.with_name(db_path.name + "-wal").exists(), (
            "test setup did not actually produce a WAL sidecar -- nothing "
            "to prove here"
        )

        backup_path = BackupService().create_backup(db_path)

        backup_conn = sqlite3.connect(str(backup_path))
        try:
            rows = backup_conn.execute("SELECT x FROM t").fetchall()
        finally:
            backup_conn.close()

        assert rows == [("row-in-wal-only",)]
    finally:
        source_conn.close()


def test_backup_raises_for_a_missing_source_db(tmp_path: Path, monkeypatch) -> None:
    """`sqlite3.connect()` happily CREATES an empty file at a path that does
    not exist yet, unlike the old `shutil.copy2` (which raised
    `FileNotFoundError`) -- a "backup" of a database that was never created
    must fail loudly, not silently produce an empty, useless backup file.
    """
    db_path = tmp_path / "missing.db"
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(backup_module, "BACKUP_DIR", backup_dir)
    assert not db_path.exists()

    with pytest.raises(FileNotFoundError):
        BackupService().create_backup(db_path)

    assert not backup_dir.exists() or list(backup_dir.iterdir()) == [], (
        "an empty backup file was created for a missing source database"
    )
