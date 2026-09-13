import shutil
from datetime import datetime
from pathlib import Path

from loan_manager.config import DB_PATH, BACKUP_DIR


class BackupService:
    def create_backup(self) -> Path:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"loans_backup_{timestamp}.db"
        shutil.copy2(DB_PATH, backup_path)
        return backup_path
