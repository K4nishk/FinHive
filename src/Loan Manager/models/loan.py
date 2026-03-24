"""Loan dataclass model."""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Loan:
    """Represents a single loan record."""

    reference_id: str
    borrower_name: str
    borrower_group: str
    amount: int  # non-negative integer, INR
    giving_date: date  # ISO 8601
    depositor_name: Optional[str] = None
    depositor_group: Optional[str] = None
    due_date: Optional[date] = None
    status: str = "Pending"  # Active, Overdue, Paidoff, Pending

    def to_csv_row(self) -> dict:
        """Convert loan to a dict suitable for csv.DictWriter."""
        return {
            "reference_id": self.reference_id,
            "borrower_name": self.borrower_name,
            "borrower_group": self.borrower_group,
            "amount": str(self.amount),
            "giving_date": self.giving_date.isoformat(),
            "depositor_name": self.depositor_name or "",
            "depositor_group": self.depositor_group or "",
            "due_date": self.due_date.isoformat() if self.due_date else "",
            "status": self.status,
        }

    @staticmethod
    def from_csv_row(row: dict) -> "Loan":
        """Parse a Loan from a csv.DictReader row dict."""
        due_date_str = row.get("due_date", "").strip()
        due_date: Optional[date] = None
        if due_date_str:
            due_date = date.fromisoformat(due_date_str)

        depositor_name_raw = row.get("depositor_name", "").strip() or None
        depositor_group_raw = row.get("depositor_group", "").strip() or None

        return Loan(
            reference_id=row["reference_id"].strip(),
            borrower_name=row["borrower_name"].strip(),
            borrower_group=row["borrower_group"].strip(),
            amount=int(row["amount"].strip()),
            giving_date=date.fromisoformat(row["giving_date"].strip()),
            depositor_name=depositor_name_raw,
            depositor_group=depositor_group_raw,
            due_date=due_date,
            status=row.get("status", "Pending").strip(),
        )


CSV_FIELDNAMES = [
    "reference_id",
    "borrower_name",
    "borrower_group",
    "amount",
    "giving_date",
    "depositor_name",
    "depositor_group",
    "due_date",
    "status",
]
