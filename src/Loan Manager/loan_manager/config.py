import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "loans.db"
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"
RECOVERY_FILE = DATA_DIR / "approval_recovery.tmp"
BACKUP_DIR = DATA_DIR / "backups"
SETTINGS_FILE = DATA_DIR / "settings.json"
EXPORT_DIR = DATA_DIR / "exports"

DATABASE_URL = f"sqlite:///{DB_PATH}"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB
LOG_BACKUP_COUNT = 3
