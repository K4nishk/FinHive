"""Loan entry form tab (Requirement 1)."""
import logging
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QCompleter,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.widgets import ClickableDateEdit

from data.csv_manager import read_autocomplete_values, write_loan
from data.ref_id_manager import generate_ref_id
from data.status_engine import compute_status
from models.loan import Loan

logger = logging.getLogger(__name__)


class EntryTab(QWidget):
    """Tab widget for entering new loan records."""

    loan_added = Signal()  # emitted after successful save

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.refresh_completers()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignTop)

        group = QGroupBox("New Loan Entry")
        form_layout = QFormLayout(group)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Borrower Name
        self._borrower_name = QLineEdit()
        self._borrower_name.setPlaceholderText("Borrower name")
        form_layout.addRow("Borrower Name:", self._borrower_name)

        # Borrower Group
        self._borrower_group = QLineEdit()
        self._borrower_group.setPlaceholderText("Borrower group")
        form_layout.addRow("Borrower Group:", self._borrower_group)

        # Amount
        self._amount = QSpinBox()
        self._amount.setMinimum(0)
        self._amount.setMaximum(999_999_999)
        self._amount.setSingleStep(1000)
        self._amount.setSuffix(" INR")
        form_layout.addRow("Amount (INR):", self._amount)

        # Giving Date
        self._giving_date = ClickableDateEdit()
        self._giving_date.setDate(QDate.currentDate())
        self._giving_date.setDisplayFormat("yyyy-MM-dd")
        form_layout.addRow("Giving Date:", self._giving_date)

        # Due Date (optional)
        due_date_widget = QWidget()
        due_date_row = QHBoxLayout(due_date_widget)
        due_date_row.setContentsMargins(0, 0, 0, 0)

        self._due_date = ClickableDateEdit()
        self._due_date.setDate(QDate.currentDate())
        self._due_date.setDisplayFormat("yyyy-MM-dd")
        due_date_row.addWidget(self._due_date)

        self._no_due_date_cb = QCheckBox("No Due Date")
        self._no_due_date_cb.setChecked(False)
        self._no_due_date_cb.toggled.connect(self._on_no_due_date_toggled)
        due_date_row.addWidget(self._no_due_date_cb)

        form_layout.addRow("Due Date (Optional):", due_date_widget)

        # Depositor Name
        self._depositor_name = QLineEdit()
        self._depositor_name.setPlaceholderText("Depositor name (optional)")
        form_layout.addRow("Depositor Name:", self._depositor_name)

        # Depositor Group
        self._depositor_group = QLineEdit()
        self._depositor_group.setPlaceholderText("Depositor group (optional)")
        form_layout.addRow("Depositor Group (Optional):", self._depositor_group)

        outer.addWidget(group)

        # Submit button
        self._submit_btn = QPushButton("Submit Loan Entry")
        self._submit_btn.setFixedHeight(36)
        self._submit_btn.clicked.connect(self._on_submit)
        outer.addWidget(self._submit_btn)

        # Status display
        self._status_label = QLabel("")
        outer.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_no_due_date_toggled(self, checked: bool) -> None:
        self._due_date.setEnabled(not checked)

    def _on_submit(self) -> None:
        if not self._validate():
            return

        today = date.today()
        q_giving = self._giving_date.date()
        giving = date(q_giving.year(), q_giving.month(), q_giving.day())

        due: date | None = None
        if not self._no_due_date_cb.isChecked():
            q_due = self._due_date.date()
            due = date(q_due.year(), q_due.month(), q_due.day())

        try:
            ref_id = generate_ref_id(today.year, today.month)
        except Exception as exc:
            logger.error("Failed to generate reference_id: %s", exc)
            QMessageBox.critical(self, "Error", f"Could not generate reference ID: {exc}")
            return

        loan = Loan(
            reference_id=ref_id,
            borrower_name=self._borrower_name.text().strip(),
            borrower_group=self._borrower_group.text().strip(),
            amount=self._amount.value(),
            giving_date=giving,
            depositor_name=self._depositor_name.text().strip() or None,
            depositor_group=self._depositor_group.text().strip() or None,
            due_date=due,
            status="Pending",
        )
        loan.status = compute_status(loan, today)

        try:
            write_loan(loan)
        except Exception as exc:
            logger.error("Failed to save loan: %s", exc)
            QMessageBox.critical(self, "Error", f"Could not save loan: {exc}")
            return

        logger.info("New loan saved: %s", loan.reference_id)
        self._status_label.setText(
            f"Loan saved successfully. Reference ID: {loan.reference_id}"
        )
        self._reset_form()
        self.refresh_completers()
        self.loan_added.emit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate(self) -> bool:
        errors = []
        if not self._borrower_name.text().strip():
            errors.append("Borrower Name is required.")
        if not self._borrower_group.text().strip():
            errors.append("Borrower Group is required.")
        if self._amount.value() < 0:
            errors.append("Amount must be a non-negative integer.")
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return False
        return True

    def _reset_form(self) -> None:
        self._borrower_name.clear()
        self._borrower_group.clear()
        self._amount.setValue(0)
        self._giving_date.setDate(QDate.currentDate())
        self._due_date.setDate(QDate.currentDate())
        self._no_due_date_cb.setChecked(False)
        self._depositor_name.clear()
        self._depositor_group.clear()

    def refresh_completers(self) -> None:
        """Reload autocomplete values from CSV."""
        try:
            values = read_autocomplete_values()
        except Exception as exc:
            logger.warning("Could not load autocomplete values: %s", exc)
            return

        def _set_completer(widget: QLineEdit, items: list) -> None:
            completer = QCompleter(items, widget)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            widget.setCompleter(completer)

        _set_completer(self._borrower_name, values.get("borrower_name", []))
        _set_completer(self._borrower_group, values.get("borrower_group", []))
        _set_completer(self._depositor_name, values.get("depositor_name", []))
        _set_completer(self._depositor_group, values.get("depositor_group", []))
