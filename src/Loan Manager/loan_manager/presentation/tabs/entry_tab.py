from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLineEdit, QSpinBox, QPushButton, QLabel, QCompleter, QMessageBox,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QIntValidator
from dateutil.relativedelta import relativedelta

from loan_manager.application.dtos.loan_dto import LoanCreateDTO
from loan_manager.application.use_cases.loans.create_loan import CreateLoan
from loan_manager.application.use_cases.loans.get_autocomplete import GetAutocompleteValues
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.presentation.widgets.date_edit import DateEditFixed


class EntryTab(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._main_window = parent
        self._name_group_map: dict[str, str] = {}
        self._depositor_group_map: dict[str, str] = {}
        self._setup_ui()
        self._load_autocomplete()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("New Loan Entry"))

        form = QFormLayout()

        self._borrower_name = QLineEdit()
        self._borrower_name.setPlaceholderText("Enter borrower name")
        self._borrower_name.textChanged.connect(self._on_borrower_name_changed)
        form.addRow("Borrower Name:", self._borrower_name)

        self._borrower_group = QLineEdit()
        self._borrower_group.setPlaceholderText("Enter borrower group")
        form.addRow("Borrower Group:", self._borrower_group)

        self._depositor_name = QLineEdit()
        self._depositor_name.setPlaceholderText("Enter depositor name")
        self._depositor_name.textChanged.connect(self._on_depositor_name_changed)
        form.addRow("Depositor Name:", self._depositor_name)

        self._depositor_group = QLineEdit()
        self._depositor_group.setPlaceholderText("Enter depositor group (optional)")
        form.addRow("Depositor Group:", self._depositor_group)

        self._amount = QLineEdit()
        self._amount.setPlaceholderText("Enter amount")
        self._amount.setValidator(QIntValidator(0, 999999999))
        form.addRow("Amount:", self._amount)

        self._giving_date = DateEditFixed()
        form.addRow("Giving Date:", self._giving_date)

        self._due_period = QSpinBox()
        self._due_period.setRange(0, 999)
        self._due_period.setValue(0)
        self._due_period.setSpecialValueText("Not set")
        self._due_period.valueChanged.connect(self._on_due_period_changed)
        form.addRow("Due Period (months):", self._due_period)

        self._due_date = DateEditFixed()
        form.addRow("Due Date:", self._due_date)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        layout.addStretch()

    def _load_autocomplete(self) -> None:
        try:
            autocomplete = GetAutocompleteValues(self._container.get_uow)

            b_names = autocomplete.execute("borrower_name")
            self._borrower_name.setCompleter(
                QCompleter(b_names, self._borrower_name)
            )

            b_groups = autocomplete.execute("borrower_group")
            self._borrower_group.setCompleter(
                QCompleter(b_groups, self._borrower_group)
            )

            d_names = autocomplete.execute("depositor_name")
            self._depositor_name.setCompleter(
                QCompleter(d_names, self._depositor_name)
            )

            d_groups = autocomplete.execute("depositor_group")
            self._depositor_group.setCompleter(
                QCompleter(d_groups, self._depositor_group)
            )

            # Build name->group mapping for auto-fill
            self._build_name_group_maps()
        except Exception:
            pass

    def _build_name_group_maps(self) -> None:
        try:
            from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
            get_loans = GetAllLoans(self._container.get_uow)
            loans = get_loans.execute()
            for loan in loans:
                if loan.borrower_name and loan.borrower_group:
                    self._name_group_map[loan.borrower_name.lower()] = loan.borrower_group
                if loan.depositor_name and loan.depositor_group:
                    self._depositor_group_map[loan.depositor_name.lower()] = loan.depositor_group
        except Exception:
            pass

    def _on_borrower_name_changed(self, text: str) -> None:
        key = text.strip().lower()
        if key in self._name_group_map:
            self._borrower_group.setText(self._name_group_map[key])

    def _on_depositor_name_changed(self, text: str) -> None:
        key = text.strip().lower()
        if key in self._depositor_group_map:
            self._depositor_group.setText(self._depositor_group_map[key])

    def _on_due_period_changed(self, value: int) -> None:
        if value > 0:
            qd = self._giving_date.date()
            giving = date(qd.year(), qd.month(), qd.day())
            new_due = giving + relativedelta(months=value)
            self._due_date.setDate(QDate(new_due.year, new_due.month, new_due.day))

    def _clear_form(self) -> None:
        self._borrower_name.clear()
        self._borrower_group.clear()
        self._depositor_name.clear()
        self._depositor_group.clear()
        self._amount.clear()
        self._giving_date.setDate(QDate.currentDate())
        self._due_period.setValue(0)
        self._due_date.setDate(QDate.currentDate())

    def _on_save(self) -> None:
        borrower_name = self._borrower_name.text().strip()
        borrower_group = self._borrower_group.text().strip()
        depositor_name = self._depositor_name.text().strip()
        depositor_group = self._depositor_group.text().strip() or None
        amount_text = self._amount.text().strip()

        if not borrower_name or not borrower_group or not depositor_name or not amount_text:
            QMessageBox.warning(self, "Validation Error", "Please fill in all required fields.")
            return

        try:
            amount = int(amount_text)
        except ValueError:
            QMessageBox.warning(self, "Validation Error", "Amount must be a valid integer.")
            return

        qd_giving = self._giving_date.date()
        giving_date = date(qd_giving.year(), qd_giving.month(), qd_giving.day())

        due_period = self._due_period.value() if self._due_period.value() > 0 else None

        due_date = None
        if due_period is not None:
            qd_due = self._due_date.date()
            due_date = date(qd_due.year(), qd_due.month(), qd_due.day())
        else:
            # Check if user manually set a due date different from today
            qd_due = self._due_date.date()
            candidate = date(qd_due.year(), qd_due.month(), qd_due.day())
            if candidate != date.today():
                due_date = candidate

        try:
            dto = LoanCreateDTO(
                borrower_name=borrower_name,
                borrower_group=borrower_group,
                depositor_name=depositor_name,
                depositor_group=depositor_group,
                amount=amount,
                giving_date=giving_date,
                due_period=due_period,
                due_date=due_date,
            )

            ref_id_service = ReferenceIdService()
            create_uc = CreateLoan(
                self._container.get_uow,
                ref_id_service,
                self._container.event_bus,
            )
            result = create_uc.execute(dto)

            if self._main_window:
                self._main_window.show_status(
                    f"Loan saved successfully. Reference ID: {result.reference_id}."
                )

            self._clear_form()
            self._load_autocomplete()

            # Refresh view tab if available
            if hasattr(self._main_window, '_view_tab'):
                self._main_window._view_tab.refresh()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save loan: {e}")
