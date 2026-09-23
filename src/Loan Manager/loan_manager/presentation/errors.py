"""Surfacing storage failures in the UI instead of swallowing them.

Four tabs populated autocomplete and name/group maps inside
`try: ... except Exception: pass`. That was survivable when those reads were
plaintext -- the worst case was an empty dropdown on a genuinely empty
database. Once the columns became encrypted (KCH-227) the same swallow
started hiding a `DataUnreadableError`, so a wrong or missing master key
rendered an intact loan book as an empty one, with no error anywhere and
nothing in the log.

That is the failure this module exists to prevent: an unreadable loan book
and an empty loan book must never look alike.

`except Exception: pass` is replaced by a context manager that
  - reports `DataUnreadableError` to the user, ONCE per process rather than
    once per tab (four tabs populate on startup; four identical modal
    dialogs would be its own bug), and
  - logs anything else with a traceback instead of discarding it, so the
    next unexpected failure leaves evidence.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from PySide6.QtWidgets import QMessageBox

from loan_manager.domain.errors import DataUnreadableError
from loan_manager.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# One dialog per process. Tabs populate independently at startup, so without
# this the same key problem is reported once per tab.
_already_reported = False


def reset_unreadable_report_state() -> None:
    """Test seam: clear the once-per-process latch."""
    global _already_reported
    _already_reported = False


@contextmanager
def surfacing_storage_errors(parent: Any, what: str) -> Iterator[None]:
    """Run a block that reads stored records, reporting failure rather than
    hiding it.

    `what` names the operation for the log and the dialog, e.g.
    "loading borrower autocomplete".
    """
    global _already_reported
    try:
        yield
    except DataUnreadableError as exc:
        logger.error("%s failed: records could not be decrypted", what)
        if not _already_reported:
            _already_reported = True
            QMessageBox.critical(
                parent,
                "Cannot read stored records",
                f"{exc}\n\nThe application is running, but any view of your "
                f"loans will be empty or incomplete until the correct key is "
                f"configured. Your data has not been changed.",
            )
    except Exception:
        # Deliberately not re-raised: a failure to populate a convenience
        # dropdown must not stop the tab from opening. But it IS recorded --
        # the previous `pass` left no trace of any kind.
        logger.exception("%s failed unexpectedly", what)
