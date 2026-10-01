"""KCH-245 regression: ApprovalReportPrinter crashed on any report
containing a CREATE-mode record (KCH-242's `giving_date=None` until
approval mints a loan) -- `sort(key=lambda r: r.giving_date)` raised
`TypeError: '<' not supported between instances of 'NoneType' and
'datetime.date'` the moment two records needed comparing, and the row's own
"Orig G.Date" cell rendered the literal string "None" when there was only
one. Exercises the real `_paint` (bypassing the interactive QPrintDialog)
against a PDF-backed QPrinter so the sort-crash bug is caught for real, not
just by reading the diff; `_optional_date_text` (the "N/A" fix, KCH-245
review cycle 1 m5) is exercised directly below, as a pure function, so it is
no longer only incidentally covered by whatever `_paint` happens to render.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from loan_manager.application.dtos.report_dto import ReportDTO, ReportRecordDTO
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    ReportActor,
    ReportStatus,
)
from loan_manager.presentation.widgets.report_printer import (
    ApprovalReportPrinter,
    _optional_date_text,
)
from PySide6.QtGui import QPainter
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication


def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _create_row(borrower_name: str) -> ReportRecordDTO:
    return ReportRecordDTO(
        id=1, report_id="RPT_20260410_001", reference_id=None,
        borrower_name=borrower_name, depositor_name="depositor",
        depositor_group=None, amount=15000, giving_date=None, due_date=None,
        extension_period=0, extension_period_unit=ExtensionPeriodUnit.MONTHS,
        interest_rate=Decimal("0"), commission_rate=Decimal("0"), tds_flag=False,
        interest_amount=None, commission_amount=None, tds_amount=None, chq_amount=None,
        post_extension_giving_date=date(2026, 4, 10),
        post_extension_due_date=date(2026, 7, 10), paidoff_date=None,
        borrower_group="new-group", due_period=3,
    )


def test_printing_a_report_with_two_create_rows_does_not_crash(tmp_path):
    _qapp()
    report = ReportDTO(
        id=1, report_id="RPT_20260410_001", report_mode=CalculationMode.CREATE,
        status=ReportStatus.PENDING,
        # SAME borrower name for both -- the printer groups rows by
        # borrower and only compares giving_date WITHIN one group's list
        # (`_paint` sorts each group), so two distinct borrowers (one row
        # each) would never actually trigger the comparison this test
        # guards against.
        records=[_create_row("borrower a"), _create_row("borrower a")],
        created_at=datetime(2026, 4, 10), updated_at=datetime(2026, 4, 10),
        actor=ReportActor.AGENT, user_request="add two borrowers", turn_id="turn-1",
    )

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(tmp_path / "report.pdf"))

    painter = QPainter()
    assert painter.begin(printer)
    try:
        # Must not raise -- the bug this regression guards crashed here.
        ApprovalReportPrinter()._paint(painter, printer, report)
    finally:
        painter.end()

    assert (tmp_path / "report.pdf").exists()


class TestOptionalDateText:
    """KCH-245 review cycle 1, m5: the "N/A" fix as a direct, pure-function
    assertion -- no QPrinter/QPainter needed, and no dependence on _paint's
    internal grouping/sorting to even reach the cell."""

    def test_none_renders_as_na(self):
        assert _optional_date_text(None) == "N/A"

    def test_a_real_date_renders_as_its_iso_string(self):
        assert _optional_date_text(date(2026, 4, 10)) == "2026-04-10"
