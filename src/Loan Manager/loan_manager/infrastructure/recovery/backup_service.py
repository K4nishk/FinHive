from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from loan_manager.config import BACKUP_DIR, DB_PATH


class BackupService:
    def create_backup(self, db_path: Path | None = None) -> Path:
        """Snapshot the database via SQLite's own online backup API.

        `db_path` defaults to the configured `DB_PATH`. Was `shutil.copy2`
        before KCH-231 turned WAL journalling on: `copy2` only copies the
        main `.db` file, and in WAL mode a committed row can live solely in
        `<db>-wal` until it is checkpointed back in -- a `copy2` backup taken
        while that's the case silently drops it, no error, no short read.
        `sqlite3.Connection.backup` reads through SQLite's own backup API,
        which merges the WAL for you, and it is safe to run against a
        database another connection (the running app) has open.
        """
        db_path = DB_PATH if db_path is None else db_path
        if not db_path.exists():
            # `sqlite3.connect()` CREATES an empty file at a path that does
            # not yet exist rather than raising -- unlike the old
            # `shutil.copy2`, which raised `FileNotFoundError` for a missing
            # source. Without this check a "backup" of a database that was
            # never created (or was moved/deleted under us) silently
            # produces an empty, useless backup file instead of failing
            # loudly (KCH-231 review 1, item 4).
            raise FileNotFoundError(f"cannot back up {db_path}: no such database file")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"loans_backup_{timestamp}.db"

        source = sqlite3.connect(str(db_path))
        try:
            dest = sqlite3.connect(str(backup_path))
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()

        return backup_path
