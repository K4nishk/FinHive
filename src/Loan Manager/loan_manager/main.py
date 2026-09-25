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
from pathlib import Path

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
    from loan_manager.config import DB_PATH

    logger.info(f"Using database at {DB_PATH}")
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
        app_dir = Path(__file__).resolve().parent.parent
        print(
            f"""
Cannot start Loan Manager.

{DB_PATH}
was created before encryption at rest became mandatory (ARB D-15), so it
still holds unencrypted records. It must be encrypted once before the app
will open it.

This is NOT done automatically. Encryption is one-way: afterwards the data
can only be read with the master key you have configured, and that is not a
decision this program should make silently about your only copy of the loan
book.


STEP 1 — Take your own backup, somewhere outside the app folder.

    cp "{DB_PATH}" ~/Desktop/loans-backup-before-encryption.db

  Keep it until you have confirmed the app opens and your records look
  right. The migration also writes its own copy beside the database, as
  loans.db.pre-encryption-backup, but a backup on the same disk in the same
  folder is a convenience, not a backup. Yours is the one that matters.


STEP 2 — Back up your master key, if you have not already.

  It is in ops/.env.local as FINHIVE_KEY_VERSION and FINHIVE_MASTER_KEY_V1.
  Store it somewhere separate from the database backup -- a password
  manager, not the same folder. After Step 3 the two are useless apart:
  losing the key loses the data, and there is no recovery path.


STEP 3 — Run the migration.

    cd "{app_dir}"
    python -m loan_manager.infrastructure.migrations.encrypt_existing_rows

  It encrypts every record in a single transaction, then decrypts each one
  back and compares it to the original value before committing. If any row
  does not survive that round trip, nothing is written at all. It finishes
  by compacting the file, which is what actually removes the old plaintext
  -- encrypting the rows alone leaves the previous values readable in the
  file's free space.


STEP 4 — Start Loan Manager again.

  It will open normally. Check that your loans are present and correct,
  then you can delete the backups from Step 1.
""",
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
