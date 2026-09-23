"""
Application entry point.
Startup sequence:
1. Setup logging
2. Check for approval_recovery.tmp
3. Initialize database (create tables)
4. Launch UI (Stage 5)
"""
import logging
import sys

from loan_manager.infrastructure.logging.logger import setup_logging, get_logger
from loan_manager.infrastructure.database.session import DatabaseSession
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService
from loan_manager.container import Container

logger = get_logger(__name__)


def main() -> None:
    setup_logging()
    logger.info("Loan Manager starting up")

    # Step 1: Check for crash recovery file
    recovery = RecoveryService()
    if recovery.exists():
        logger.warning(
            "approval_recovery.tmp detected — an approval was in progress when the app last closed. "
            "Please check the Pending Approval queue and verify loan records."
        )
        print(
            "\nWARNING: An approval was in progress when the application last closed. "
            "Please check the Pending Approval queue and verify loan records.\n"
        )

    # Step 2: Initialize database
    DatabaseSession.initialize()
    logger.info("Database initialized")

    # Step 3: Wire container
    container = Container()
    logger.info("Container initialized")

    # Step 3a: Prove the master key is usable BEFORE anything can write.
    # ARB D-15 makes encryption at rest mandatory. Deferring this to the first
    # encrypting write is the failure mode key_provider exists to prevent: a
    # half-configured key encrypts some rows with a key that is gone on the next
    # launch, which is indistinguishable from data loss.
    from loan_manager.infrastructure.security.key_provider import (
        KeyConfigurationError,
    )

    try:
        container.get_key_ring()
    except KeyConfigurationError as exc:
        logger.error("Encryption key unusable — refusing to start")
        print(f"\nCannot start Loan Manager.\n\n{exc}\n", file=sys.stderr)
        sys.exit(1)
    logger.info("Encryption key ring loaded")

    # Step 3b: Refuse to run against a pre-encryption database.
    # create_all() above creates missing TABLES but never ALTERs an existing
    # one, so a database written before KCH-227 still holds plaintext and
    # lacks the _bidx/key_version columns. Without this check the next line
    # (RecomputeAllStatuses) dies with
    # "no such column: loans.borrower_name_bidx" before any UI exists -- a
    # traceback on a black screen, with the real cause three layers down.
    # The migration is NOT run automatically: encryption is one-way, and
    # doing it to someone's only copy of their loan book without them asking
    # is not a decision this code gets to make.
    from loan_manager.config import DB_PATH
    from loan_manager.infrastructure.migrations.encrypt_existing_rows import (
        needs_migration,
    )

    if needs_migration(DB_PATH):
        logger.error("Database predates encryption at rest — refusing to start")
        print(
            f"\nCannot start Loan Manager.\n\n"
            f"{DB_PATH} was created before encryption at rest became mandatory "
            f"(ARB D-15), so it still holds unencrypted records.\n\n"
            f"Encrypt it once, with the key you just configured:\n\n"
            f"    python -m loan_manager.infrastructure.migrations.encrypt_existing_rows\n\n"
            f"A backup is written beside the database first. This is one-way: "
            f"after it runs, the data cannot be read without that master key.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # Step 4: Recompute statuses on launch
    from loan_manager.application.use_cases.loans.recompute_statuses import RecomputeAllStatuses
    recompute = RecomputeAllStatuses(container.get_uow)
    updated = recompute.execute()
    logger.info(f"Recomputed statuses for {updated} loans")

    # Step 5: Launch UI
    from PySide6.QtWidgets import QApplication
    from loan_manager.presentation.main_window import MainWindow
    from loan_manager.presentation.themes.theme_manager import ThemeManager

    app = QApplication(sys.argv)

    saved_theme = _load_saved_theme()
    custom_colours = _load_custom_colours()
    ThemeManager.apply_theme(saved_theme, app, custom_colours or None)

    window = MainWindow(container, ThemeManager)
    window.show()
    sys.exit(app.exec())


def _load_saved_theme() -> str:
    import json
    from loan_manager.config import SETTINGS_FILE
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text()).get("theme", "dark")
        except Exception:
            pass
    return "dark"


def _load_custom_colours() -> dict:
    import json
    from loan_manager.config import SETTINGS_FILE
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text()).get("custom_colours", {})
        except Exception:
            pass
    return {}


if __name__ == "__main__":
    main()
