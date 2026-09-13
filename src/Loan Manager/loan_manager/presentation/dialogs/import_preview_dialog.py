from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
)

from loan_manager.application.dtos.import_dto import ImportPreviewDTO


class ImportPreviewDialog(QDialog):
    """Shows import preview with overwrite warnings."""

    def __init__(self, preview: ImportPreviewDTO, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Preview")
        self.setModal(True)
        self.setMinimumWidth(450)
        self._proceed = False

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"File: {preview.file_path}"))
        layout.addWidget(QLabel(f"New records: {preview.total_new}"))
        layout.addWidget(QLabel(f"Overwrite records: {preview.total_overwrite}"))

        if preview.total_overwrite > 0:
            ids_str = ", ".join(preview.sample_overwrite_ids[:10])
            warning = QLabel(
                f"{preview.total_overwrite} records will be overwritten: [{ids_str}]."
            )
            warning.setWordWrap(True)
            warning.setStyleSheet("font-weight: bold;")
            layout.addWidget(warning)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        proceed_btn = QPushButton("Proceed")
        proceed_btn.clicked.connect(self._on_proceed)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(proceed_btn)
        layout.addLayout(btn_layout)

    def _on_proceed(self) -> None:
        self._proceed = True
        self.accept()

    def should_proceed(self) -> bool:
        return self._proceed
