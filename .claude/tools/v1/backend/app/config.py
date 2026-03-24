"""Application configuration management."""
from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App Settings
    app_name: str = "LoanTracker"
    app_version: str = "1.0.0"
    environment: str = "production"

    # Storage Configuration
    storage_type: str = "csv"  # csv or sqlite
    csv_output_dir: str = "./engine_output"
    csv_filename: str = "loan_records.csv"
    sqlite_db_path: str = "./engine_output/loantracker.db"

    # Encryption Configuration
    encryption_key: Optional[str] = None

    # Backend API Settings
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_reload: bool = False

    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/loantracker.log"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env (e.g., frontend vars)

    @property
    def is_encryption_enabled(self) -> bool:
        """Check if encryption is enabled."""
        return bool(self.encryption_key and len(self.encryption_key) > 0)

    @property
    def csv_file_path(self) -> Path:
        """Get full path to CSV file."""
        return Path(self.csv_output_dir) / self.csv_filename

    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        Path(self.csv_output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
settings.ensure_directories()
