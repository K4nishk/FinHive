"""Professional report printers using QPainter on QPrinter.

Contains:
- LoanReportPrinter: prints loan records from the View Tab
- ApprovalReportPrinter: prints borrower-centric grouped approval reports
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QMarginsF
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

from loan_manager.application.dtos.loan_dto import LoanDTO
from loan_manager.application.dtos.report_dto import ReportDTO


# --- Shared Constants ---

_MARGIN_MM = 15.0
_TITLE_FONT_SIZE = 14
_HEADER_FONT_SIZE = 12
_BODY_FONT_SIZE = 10
_ROW_SHADE = QColor("#f5f5f5")
_WHITE = QColor(Qt.GlobalColor.white)
_BLACK = QColor(Qt.GlobalColor.black)
_LINE_COLOR = QColor("#cccccc")
_HEADER_BG = QColor("#e0e0e0")
_COL_PAD = 6  # horizontal padding inside cells
_ROW_PAD = 4  # vertical padding inside cells


def _make_font(size: int, bold: bool = False) -> QFont:
    f = QFont("Arial", size)
    f.setBold(bold)
    return f


def _setup_printer(printer: QPrinter, landscape: bool = False) -> None:
    """Configure printer for A4 with consistent margins."""
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    orientation = (
        QPageLayout.Orientation.Landscape if landscape
        else QPageLayout.Orientation.Portrait
    )
    margins = QMarginsF(_MARGIN_MM, _MARGIN_MM, _MARGIN_MM, _MARGIN_MM)
    layout = QPageLayout(QPageSize(QPageSize.PageSizeId.A4), orientation, margins, QPageLayout.Unit.Millimeter)
    printer.setPageLayout(layout)


def _printable_rect(printer: QPrinter) -> QRectF:
    """Get the printable rectangle in device coordinates."""
    layout = printer.pageLayout()
    rect = layout.paintRect(QPageLayout.Unit.Point)
    # Scale to device pixels
    dpi_x = printer.resolution()
    dpi_y = printer.resolution()
    scale_x = dpi_x / 72.0
    scale_y = dpi_y / 72.0
    return QRectF(
        rect.x() * scale_x,
        rect.y() * scale_y,
        rect.width() * scale_x,
        rect.height() * scale_y,
    )


class _TablePainter:
    """Utility for painting tabular data with QPainter on QPrinter."""

    def __init__(self, painter: QPainter, printer: QPrinter):
        self.painter = painter
        self.printer = printer
        self.rect = _printable_rect(printer)
        self.y = self.rect.top()
        self.page = 1
        self.total_pages: Optional[int] = None
        self.title = ""
        self.timestamp = ""
        self.filters_text = ""

        # Fonts
        self.title_font = _make_font(_TITLE_FONT_SIZE, bold=True)
        self.header_font = _make_font(_HEADER_FONT_SIZE, bold=True)
        self.body_font = _make_font(_BODY_FONT_SIZE)
        self.small_font = _make_font(8)

        # Calculate text heights using font metrics
        self._title_h = self._font_height(self.title_font) + 4
        self._header_h = self._font_height(self.header_font) + _ROW_PAD * 2
        self._body_h = self._font_height(self.body_font) + _ROW_PAD * 2
        self._small_h = self._font_height(self.small_font) + 2

    def _font_height(self, font: QFont) -> float:
        self.painter.setFont(font)
        return self.painter.fontMetrics().height()

    def page_header_height(self) -> float:
        h = self._title_h + self._small_h + 10  # title + timestamp + spacing
        if self.filters_text:
            h += self._small_h + 4
        return h

    def available_body_height(self) -> float:
        return (
            self.rect.bottom()
            - self.rect.top()
            - self.page_header_height()
            - self._small_h  # footer
            - 20  # spacing
        )

    def rows_per_page(self) -> int:
        body_h = self.available_body_height() - self._header_h  # column header row
        return max(1, int(body_h / self._body_h))

    def draw_page_header(self) -> None:
        x = self.rect.left()
        w = self.rect.width()
        self.y = self.rect.top()

        # Title
        self.painter.setFont(self.title_font)
        self.painter.setPen(_BLACK)
        self.painter.drawText(
            QRectF(x, self.y, w, self._title_h),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.title,
        )
        self.y += self._title_h

        # Timestamp
        self.painter.setFont(self.small_font)
        self.painter.drawText(
            QRectF(x, self.y, w, self._small_h),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"Generated: {self.timestamp}",
        )
        self.y += self._small_h + 2

        # Filters
        if self.filters_text:
            self.painter.drawText(
                QRectF(x, self.y, w, self._small_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self.filters_text,
            )
            self.y += self._small_h + 2

        self.y += 6  # spacing

    def draw_page_footer(self) -> None:
        x = self.rect.left()
        w = self.rect.width()
        footer_y = self.rect.bottom() - self._small_h
        self.painter.setFont(self.small_font)
        self.painter.setPen(_BLACK)
        page_text = f"Page {self.page}"
        if self.total_pages:
            page_text = f"Page {self.page} of {self.total_pages}"
        self.painter.drawText(
            QRectF(x, footer_y, w, self._small_h),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            page_text,
        )

    def draw_column_headers(self, headers: list[str], col_widths: list[float]) -> None:
        x = self.rect.left()
        self.painter.setFont(self.header_font)
        pen = QPen(_LINE_COLOR, 1)
        self.painter.setPen(pen)
        # Background
        total_w = sum(col_widths)
        self.painter.fillRect(QRectF(x, self.y, total_w, self._header_h), _HEADER_BG)
        self.painter.drawRect(QRectF(x, self.y, total_w, self._header_h))

        self.painter.setPen(_BLACK)
        cx = x
        for i, hdr in enumerate(headers):
            self.painter.drawText(
                QRectF(cx + _COL_PAD, self.y, col_widths[i] - _COL_PAD * 2, self._header_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                hdr,
            )
            cx += col_widths[i]

        # Vertical lines
        pen = QPen(_LINE_COLOR, 1)
        self.painter.setPen(pen)
        cx = x
        for w in col_widths:
            self.painter.drawLine(int(cx), int(self.y), int(cx), int(self.y + self._header_h))
            cx += w
        self.painter.drawLine(int(cx), int(self.y), int(cx), int(self.y + self._header_h))

        self.y += self._header_h

    def draw_row(self, cells: list[str], col_widths: list[float], shaded: bool) -> None:
        x = self.rect.left()
        total_w = sum(col_widths)
        bg = _ROW_SHADE if shaded else _WHITE
        self.painter.fillRect(QRectF(x, self.y, total_w, self._body_h), bg)

        pen = QPen(_LINE_COLOR, 1)
        self.painter.setPen(pen)
        self.painter.drawRect(QRectF(x, self.y, total_w, self._body_h))

        self.painter.setFont(self.body_font)
        self.painter.setPen(_BLACK)
        cx = x
        for i, cell in enumerate(cells):
            self.painter.drawText(
                QRectF(cx + _COL_PAD, self.y, col_widths[i] - _COL_PAD * 2, self._body_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                cell,
            )
            cx += col_widths[i]

        # Vertical lines
        pen = QPen(_LINE_COLOR, 1)
        self.painter.setPen(pen)
        cx = x
        for w in col_widths:
            self.painter.drawLine(int(cx), int(self.y), int(cx), int(self.y + self._body_h))
            cx += w
        self.painter.drawLine(int(cx), int(self.y), int(cx), int(self.y + self._body_h))

        self.y += self._body_h

    def draw_row_aligned(
        self,
        cells: list[str],
        col_widths: list[float],
        alignments: list[Qt.AlignmentFlag],
        shaded: bool,
        font: QFont | None = None,
    ) -> None:
        """Draw a table row with per-column alignment control."""
        x = self.rect.left()
        total_w = sum(col_widths)
        bg = _ROW_SHADE if shaded else _WHITE
        self.painter.fillRect(QRectF(x, self.y, total_w, self._body_h), bg)

        pen = QPen(_LINE_COLOR, 1)
        self.painter.setPen(pen)
        self.painter.drawRect(QRectF(x, self.y, total_w, self._body_h))

        self.painter.setFont(font or self.body_font)
        self.painter.setPen(_BLACK)
        cx = x
        for i, cell in enumerate(cells):
            h_align = alignments[i] if i < len(alignments) else Qt.AlignmentFlag.AlignLeft
            self.painter.drawText(
                QRectF(cx + _COL_PAD, self.y, col_widths[i] - _COL_PAD * 2, self._body_h),
                h_align | Qt.AlignmentFlag.AlignVCenter,
                cell,
            )
            cx += col_widths[i]

        # Vertical lines
        pen = QPen(_LINE_COLOR, 1)
        self.painter.setPen(pen)
        cx = x
        for w in col_widths:
            self.painter.drawLine(int(cx), int(self.y), int(cx), int(self.y + self._body_h))
            cx += w
        self.painter.drawLine(int(cx), int(self.y), int(cx), int(self.y + self._body_h))

        self.y += self._body_h

    def new_page(self) -> None:
        self.draw_page_footer()
        self.printer.newPage()
        self.page += 1
        self.draw_page_header()

    def remaining_body_space(self) -> float:
        footer_space = self._small_h + 10
        return self.rect.bottom() - self.y - footer_space

    def can_fit_row(self) -> bool:
        return self.remaining_body_space() >= self._body_h

    def can_fit_rows(self, n: int) -> bool:
        return self.remaining_body_space() >= self._body_h * n

    def draw_text_line(self, text: str, font: QFont = None, indent: float = 0) -> None:
        if font is None:
            font = self.body_font
        self.painter.setFont(font)
        h = self._font_height(font) + _ROW_PAD
        self.painter.setPen(_BLACK)
        self.painter.drawText(
            QRectF(self.rect.left() + indent, self.y, self.rect.width() - indent, h),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )
        self.y += h

    def draw_separator(self, char: str = "\u2500", indent: float = 0) -> None:
        """Draw a horizontal line separator."""
        pen = QPen(_LINE_COLOR, 2)
        self.painter.setPen(pen)
        x1 = self.rect.left() + indent
        x2 = self.rect.left() + self.rect.width()
        self.painter.drawLine(int(x1), int(self.y), int(x2), int(self.y))
        self.y += 4

    def draw_thick_separator(self, indent: float = 0) -> None:
        """Draw a thick horizontal line separator."""
        pen = QPen(_BLACK, 3)
        self.painter.setPen(pen)
        x1 = self.rect.left() + indent
        x2 = self.rect.left() + self.rect.width()
        self.painter.drawLine(int(x1), int(self.y), int(x2), int(self.y))
        self.y += 6


class LoanReportPrinter:
    """Prints loan records from the View Tab with professional formatting."""

    _HEADERS = [
        "SNo", "Ref ID", "B Name", "B Grp", "Amt",
        "D Name", "D Grp", "G Date", "D Date", "Status",
    ]

    def print_loans(
        self,
        loans: list[LoanDTO],
        filters: dict[str, list[str]],
        parent_widget,
    ) -> None:
        """Open QPrintDialog and print the loan table."""
        landscape = len(self._HEADERS) > 7
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        _setup_printer(printer, landscape=landscape)

        dialog = QPrintDialog(printer, parent_widget)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return

        painter = QPainter()
        if not painter.begin(printer):
            return

        try:
            self._paint(painter, printer, loans, filters)
        finally:
            painter.end()

    def _paint(
        self,
        painter: QPainter,
        printer: QPrinter,
        loans: list[LoanDTO],
        filters: dict[str, list[str]],
    ) -> None:
        tp = _TablePainter(painter, printer)
        tp.title = "Loan Manager \u2014 Loan Records"
        tp.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build filters text
        if filters:
            parts = [f"{k}: {', '.join(v)}" for k, v in filters.items()]
            tp.filters_text = "Filters: " + "  |  ".join(parts)

        # Calculate column widths (proportional to usable width)
        # Subtract left+right safety margins from the paint rect width
        # to prevent right-edge clipping on printers/PDF viewers
        dpi = printer.resolution()
        left_margin = _MARGIN_MM * dpi / 25.4   # 15mm in device pixels
        right_margin = _MARGIN_MM * dpi / 25.4   # 15mm in device pixels
        usable_width = tp.rect.width() - left_margin - right_margin
        # Weight-based: SNo=3, RefID=8, names=8, groups=6, amt=6, dates=7, status=6
        weights = [3, 8, 8, 6, 6, 8, 6, 7, 7, 6]
        total_weight = sum(weights)
        col_widths = [usable_width * w / total_weight for w in weights]

        # Calculate total pages
        rpp = tp.rows_per_page()
        total_data_rows = len(loans)
        total_pages = max(1, (total_data_rows + rpp - 1) // rpp) if total_data_rows > 0 else 1
        tp.total_pages = total_pages

        # Page 1 header
        tp.draw_page_header()

        if not loans:
            tp.draw_text_line("No matching records found.")
            tp.draw_page_footer()
            return

        tp.draw_column_headers(self._HEADERS, col_widths)

        for i, loan in enumerate(loans):
            if not tp.can_fit_row():
                tp.new_page()
                tp.draw_column_headers(self._HEADERS, col_widths)

            row = [
                str(i + 1),
                loan.reference_id,
                loan.borrower_name or "Unknown",
                loan.borrower_group or "Unknown",
                str(loan.amount),
                loan.depositor_name or "Unknown",
                loan.depositor_group or "Unknown",
                str(loan.giving_date) if loan.giving_date else "Unknown",
                str(loan.due_date) if loan.due_date else "Unknown",
                loan.status.value,
            ]
            tp.draw_row(row, col_widths, shaded=(i % 2 == 1))

        # Total count
        tp.y += 10
        tp.draw_text_line(f"Total Records: {total_data_rows}", tp.header_font)
        tp.draw_page_footer()


class ApprovalReportPrinter:
    """Prints borrower-centric grouped approval report."""

    def print_report(self, report: ReportDTO, parent_widget) -> None:
        """Open QPrintDialog and print the borrower-centric grouped report."""
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        _setup_printer(printer, landscape=True)  # many columns, use landscape

        dialog = QPrintDialog(printer, parent_widget)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return

        painter = QPainter()
        if not painter.begin(printer):
            return

        try:
            self._paint(painter, printer, report)
        finally:
            painter.end()

    # Table column definitions for the per-borrower table
    _TABLE_HEADERS = [
        "Amount", "Depositor", "Orig G.Date", "Orig D.Date",
        "New G.Date", "New D.Date", "Ext", "Unit",
        "Interest", "TDS", "CHQ", "Commission",
    ]
    # Proportional weights for column widths
    _COL_WEIGHTS = [7, 9, 8, 8, 8, 8, 4, 5, 7, 6, 6, 7]
    # Per-column alignment
    _COL_ALIGNS = [
        Qt.AlignmentFlag.AlignRight,    # Amount
        Qt.AlignmentFlag.AlignLeft,     # Depositor
        Qt.AlignmentFlag.AlignHCenter,  # Orig G.Date
        Qt.AlignmentFlag.AlignHCenter,  # Orig D.Date
        Qt.AlignmentFlag.AlignHCenter,  # New G.Date
        Qt.AlignmentFlag.AlignHCenter,  # New D.Date
        Qt.AlignmentFlag.AlignRight,    # Ext
        Qt.AlignmentFlag.AlignLeft,     # Unit
        Qt.AlignmentFlag.AlignRight,    # Interest
        Qt.AlignmentFlag.AlignRight,    # TDS
        Qt.AlignmentFlag.AlignRight,    # CHQ
        Qt.AlignmentFlag.AlignRight,    # Commission
    ]
    # Font sizes to try (auto-size: reduce if columns cannot fit)
    _FONT_SIZES = [10, 9, 8]

    def _paint(self, painter: QPainter, printer: QPrinter, report: ReportDTO) -> None:
        tp = _TablePainter(painter, printer)
        tp.title = "LOAN INTEREST REPORT"
        tp.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tp.filters_text = f"Report ID: {report.report_id}"

        # Group records by borrower, sorted alphabetically
        borrower_groups: dict[str, list] = {}
        for rec in report.records:
            name = rec.borrower_name or "Unknown"
            borrower_groups.setdefault(name, []).append(rec)

        sorted_borrowers = sorted(borrower_groups.keys(), key=str.lower)

        for name in sorted_borrowers:
            borrower_groups[name].sort(key=lambda r: r.giving_date)

        tp.total_pages = None

        # Compute usable_width with same margin philosophy as Issue 1
        dpi = printer.resolution()
        left_margin = _MARGIN_MM * dpi / 25.4
        right_margin = _MARGIN_MM * dpi / 25.4
        usable_width = tp.rect.width() - left_margin - right_margin

        # Select font size: try 10pt, 9pt, 8pt — pick largest that fits
        total_weight = sum(self._COL_WEIGHTS)
        chosen_font_size = self._FONT_SIZES[-1]  # fallback to minimum
        for fs in self._FONT_SIZES:
            test_font = _make_font(fs)
            painter.setFont(test_font)
            fm = painter.fontMetrics()
            # Check if the narrowest column can fit at least 3 chars
            min_weight = min(self._COL_WEIGHTS)
            min_col_w = usable_width * min_weight / total_weight
            if min_col_w >= fm.horizontalAdvance("WW") + _COL_PAD * 2:
                chosen_font_size = fs
                break

        body_font = _make_font(chosen_font_size)
        bold_font = _make_font(chosen_font_size, bold=True)
        tp.body_font = body_font
        # Recalculate body height for chosen font
        tp._body_h = tp._font_height(body_font) + _ROW_PAD * 2

        col_widths = [usable_width * w / total_weight for w in self._COL_WEIGHTS]

        # Helper to truncate cell text with ellipsis if it exceeds column width
        def _truncate(text: str, col_idx: int) -> str:
            painter.setFont(body_font)
            fm = painter.fontMetrics()
            avail = col_widths[col_idx] - _COL_PAD * 2
            if fm.horizontalAdvance(text) <= avail:
                return text
            while len(text) > 1 and fm.horizontalAdvance(text + "\u2026") > avail:
                text = text[:-1]
            return text + "\u2026"

        # Track grand totals
        grand_amount = Decimal(0)
        grand_interest = Decimal(0)
        grand_commission = Decimal(0)
        grand_tds = Decimal(0)

        borrower_font = _make_font(11, bold=True)

        # Page 1
        tp.draw_page_header()

        def _draw_table_headers() -> None:
            """Draw column headers for the borrower table."""
            tp.draw_column_headers(self._TABLE_HEADERS, col_widths)

        for b_idx, borrower in enumerate(sorted_borrowers):
            records = borrower_groups[borrower]

            # Need room for: borrower name + separator + header row + 1 data row + totals line (5 rows)
            needed_lines = 5
            if tp.remaining_body_space() < tp._body_h * needed_lines:
                tp.draw_page_footer()
                tp.printer.newPage()
                tp.page += 1
                tp.draw_page_header()

            # Borrower name header
            tp.draw_text_line(borrower, borrower_font)
            tp.draw_separator(indent=0)

            # Column header row
            _draw_table_headers()

            borrower_amount = Decimal(0)
            borrower_interest = Decimal(0)
            borrower_commission = Decimal(0)
            borrower_tds = Decimal(0)

            for r_idx, rec in enumerate(records):
                # Ensure row does not split across pages
                if not tp.can_fit_row():
                    tp.draw_page_footer()
                    tp.printer.newPage()
                    tp.page += 1
                    tp.draw_page_header()
                    # Repeat column headers on new page
                    tp.draw_text_line(f"{borrower} (continued)", borrower_font)
                    _draw_table_headers()

                cells = [
                    _truncate(str(rec.amount), 0),
                    _truncate(rec.depositor_name or "Unknown", 1),
                    _truncate(str(rec.giving_date), 2),
                    _truncate(str(rec.due_date) if rec.due_date else "N/A", 3),
                    _truncate(
                        str(rec.post_extension_giving_date)
                        if rec.post_extension_giving_date else "N/A", 4
                    ),
                    _truncate(
                        str(rec.post_extension_due_date)
                        if rec.post_extension_due_date else "N/A", 5
                    ),
                    _truncate(str(rec.extension_period), 6),
                    _truncate(rec.extension_period_unit.value, 7),
                    _truncate(str(rec.interest_amount or 0), 8),
                    _truncate(str(rec.tds_amount or 0), 9),
                    _truncate(str(rec.chq_amount or 0), 10),
                    _truncate(str(rec.commission_amount or 0), 11),
                ]
                tp.draw_row_aligned(
                    cells, col_widths, self._COL_ALIGNS,
                    shaded=(r_idx % 2 == 1), font=body_font,
                )

                borrower_amount += Decimal(str(rec.amount))
                borrower_interest += Decimal(str(rec.interest_amount or 0))
                borrower_commission += Decimal(str(rec.commission_amount or 0))
                borrower_tds += Decimal(str(rec.tds_amount or 0))

            # Borrower totals line
            tp.y += 4
            totals_text = (
                f"Total Amount: \u20b9 {borrower_amount}    "
                f"Total Interest: \u20b9 {borrower_interest}    "
                f"Total Commission: \u20b9 {borrower_commission}    "
                f"Total TDS: \u20b9 {borrower_tds}"
            )
            tp.draw_text_line(totals_text, bold_font)
            tp.draw_thick_separator()

            grand_amount += borrower_amount
            grand_interest += borrower_interest
            grand_commission += borrower_commission
            grand_tds += borrower_tds

        # Grand totals
        if not tp.can_fit_rows(6):
            tp.draw_page_footer()
            tp.printer.newPage()
            tp.page += 1
            tp.draw_page_header()

        tp.y += 10
        tp.draw_text_line("GRAND TOTALS", tp.header_font)
        tp.draw_separator()
        tp.draw_text_line(f"  Total Principal:  \u20b9 {grand_amount}", bold_font)
        tp.draw_text_line(f"  Total Interest:   \u20b9 {grand_interest}", bold_font)
        tp.draw_text_line(f"  Total Commission: \u20b9 {grand_commission}", bold_font)
        tp.draw_text_line(f"  Total TDS:        \u20b9 {grand_tds}", bold_font)

        tp.draw_page_footer()
