"""Report dataclass models for Pending Approval workflow."""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


# ---------------------------------------------------------------------------
# CSV fieldname constants
# ---------------------------------------------------------------------------

PENDING_REPORT_FIELDNAMES = [
    "report_id",
    "report_creation_date",
    "report_latest_update_dt",
    "mode",
    "status",
]

REPORT_RECORD_FIELDNAMES = [
    "report_id",
    "reference_id",
    "borrower_name",
    "amount",
    "depositor_name",
    "giving_date",
    "due_date",
    "interest_rate",
    "commission_rate",
    "extension_period",
    "extension_period_unit",
    "tds_flag",
    "new_giving_date",
    "new_due_date",
    "interest_amount",
    "commission_amount",
    "tds_amount",
]


# ---------------------------------------------------------------------------
# PendingReport — report header record
# ---------------------------------------------------------------------------

@dataclass
class PendingReport:
    """Represents a single report header row in pending_reports.csv.

    status values: Pending, Approved, Declined
    mode values: Monthly, Daily, Both
    """

    report_id: str
    report_creation_date: date
    report_latest_update_dt: datetime
    mode: str
    status: str = "Pending"

    def to_csv_row(self) -> dict:
        """Convert to a dict suitable for csv.DictWriter."""
        return {
            "report_id": self.report_id,
            "report_creation_date": self.report_creation_date.isoformat(),
            "report_latest_update_dt": self.report_latest_update_dt.isoformat(),
            "mode": self.mode,
            "status": self.status,
        }

    @staticmethod
    def from_csv_row(row: dict) -> "PendingReport":
        """Parse a PendingReport from a csv.DictReader row dict."""
        creation_date = date.fromisoformat(row["report_creation_date"].strip())
        update_dt_raw = row["report_latest_update_dt"].strip()
        update_dt = datetime.fromisoformat(update_dt_raw)
        return PendingReport(
            report_id=row["report_id"].strip(),
            report_creation_date=creation_date,
            report_latest_update_dt=update_dt,
            mode=row["mode"].strip(),
            status=row.get("status", "Pending").strip(),
        )


# ---------------------------------------------------------------------------
# ReportRecord — individual loan-level line item within a report
# ---------------------------------------------------------------------------

@dataclass
class ReportRecord:
    """Represents a single loan line item in pending_report_records.csv."""

    report_id: str
    reference_id: str
    borrower_name: str
    amount: int
    depositor_name: Optional[str]
    giving_date: date
    due_date: Optional[date]
    interest_rate: float
    commission_rate: float
    extension_period: int
    extension_period_unit: str  # months or days
    tds_flag: bool
    new_giving_date: Optional[date]
    new_due_date: Optional[date]
    interest_amount: float
    commission_amount: float
    tds_amount: float

    def to_csv_row(self) -> dict:
        """Convert to a dict suitable for csv.DictWriter."""
        return {
            "report_id": self.report_id,
            "reference_id": self.reference_id,
            "borrower_name": self.borrower_name,
            "amount": str(self.amount),
            "depositor_name": self.depositor_name or "",
            "giving_date": self.giving_date.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else "",
            "interest_rate": str(self.interest_rate),
            "commission_rate": str(self.commission_rate),
            "extension_period": str(self.extension_period),
            "extension_period_unit": self.extension_period_unit,
            "tds_flag": "true" if self.tds_flag else "false",
            "new_giving_date": self.new_giving_date.isoformat() if self.new_giving_date else "",
            "new_due_date": self.new_due_date.isoformat() if self.new_due_date else "",
            "interest_amount": str(self.interest_amount),
            "commission_amount": str(self.commission_amount),
            "tds_amount": str(self.tds_amount),
        }

    @staticmethod
    def from_csv_row(row: dict) -> "ReportRecord":
        """Parse a ReportRecord from a csv.DictReader row dict."""
        due_date_raw = row.get("due_date", "").strip()
        due_date: Optional[date] = date.fromisoformat(due_date_raw) if due_date_raw else None

        new_giving_raw = row.get("new_giving_date", "").strip()
        new_giving_date: Optional[date] = date.fromisoformat(new_giving_raw) if new_giving_raw else None

        new_due_raw = row.get("new_due_date", "").strip()
        new_due_date: Optional[date] = date.fromisoformat(new_due_raw) if new_due_raw else None

        tds_raw = row.get("tds_flag", "false").strip().lower()
        tds_flag = tds_raw in ("true", "1", "yes")

        depositor_raw = row.get("depositor_name", "").strip() or None

        return ReportRecord(
            report_id=row["report_id"].strip(),
            reference_id=row["reference_id"].strip(),
            borrower_name=row["borrower_name"].strip(),
            amount=int(row["amount"].strip()),
            depositor_name=depositor_raw,
            giving_date=date.fromisoformat(row["giving_date"].strip()),
            due_date=due_date,
            interest_rate=float(row["interest_rate"].strip()),
            commission_rate=float(row["commission_rate"].strip()),
            extension_period=int(row["extension_period"].strip()),
            extension_period_unit=row["extension_period_unit"].strip(),
            tds_flag=tds_flag,
            new_giving_date=new_giving_date,
            new_due_date=new_due_date,
            interest_amount=float(row["interest_amount"].strip()),
            commission_amount=float(row["commission_amount"].strip()),
            tds_amount=float(row["tds_amount"].strip()),
        )
