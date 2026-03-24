"""CSVManager — injectable-path class API for tests and app integration."""

import csv
from datetime import date
from pathlib import Path
from typing import Optional

from dateutil.relativedelta import relativedelta

FIELDNAMES = [
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

HISTORY_FIELDNAMES = FIELDNAMES + ["paidoff_date"]

OPTIONAL_FIELDS = {"depositor_group", "due_date", "paidoff_date"}
DATE_FIELDS = {"giving_date", "due_date", "paidoff_date"}


class CSVManager:
    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_raw(self, path: Path) -> list[dict]:
        if not path.exists() or path.stat().st_size == 0:
            return []
        with path.open("r", newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))

    def _write_raw(self, path: Path, rows: list[dict], fieldnames: list[str]) -> None:
        with open(str(path), "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _append_raw(self, path: Path, row: dict, fieldnames: list[str]) -> None:
        write_header = not path.exists() or path.stat().st_size == 0
        with open(str(path), "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    def _parse_row(self, row: dict) -> dict:
        """Convert raw CSV strings to typed Python values."""
        parsed = {}
        for key, value in row.items():
            if key == "amount":
                parsed[key] = int(value) if value else 0
            elif key in DATE_FIELDS:
                if value:
                    parsed[key] = date.fromisoformat(value)
                else:
                    parsed[key] = None
            elif key in OPTIONAL_FIELDS:
                parsed[key] = value if value else None
            else:
                parsed[key] = value
        return parsed

    def _serialise_value(self, key: str, value) -> str:
        """Convert a Python value to CSV string."""
        if value is None:
            return ""
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    def _serialise_row(self, loan: dict, fieldnames: list[str]) -> dict:
        return {k: self._serialise_value(k, loan.get(k)) for k in fieldnames}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_loans(self, loans_path: Path) -> list[dict]:
        """Read all non-Paidoff loans from loans_path. Returns list[dict] with typed values."""
        rows = self._read_raw(loans_path)
        result = []
        for row in rows:
            if row.get("status") == "Paidoff":
                continue
            result.append(self._parse_row(row))
        return result

    def write_loan(self, loans_path: Path, loan: dict) -> None:
        """Append a single loan record to loans_path. Creates file with header if absent."""
        serialised = self._serialise_row(loan, FIELDNAMES)
        self._append_raw(loans_path, serialised, FIELDNAMES)

    def update_loan(
        self, loans_path: Path, reference_id: str, updated_fields: dict
    ) -> None:
        """Update fields on the matching loan record. No-op if reference_id not found."""
        rows = self._read_raw(loans_path)
        for row in rows:
            if row["reference_id"] == reference_id:
                for key, value in updated_fields.items():
                    row[key] = self._serialise_value(key, value)
        self._write_raw(loans_path, rows, FIELDNAMES)

    def delete_loan(self, loans_path: Path, reference_id: str) -> None:
        """Remove the loan with matching reference_id. No-op if not found."""
        rows = self._read_raw(loans_path)
        filtered = [r for r in rows if r["reference_id"] != reference_id]
        self._write_raw(loans_path, filtered, FIELDNAMES)

    def mark_paidoff(
        self,
        loans_path: Path,
        history_path: Path,
        reference_id: str,
        paidoff_date: date,
    ) -> None:
        """Atomic two-write paidoff operation.

        Protocol:
        1. Write recovery.tmp (sentinel) — crash before this = no-op, safe.
        2. Append record to history.csv.
        3. Remove record from loans.csv.
        4. Delete recovery.tmp — crash after step 3 but before 4 = tmp survives (detectable).
        """
        recovery_path = loans_path.parent / "recovery.tmp"
        rows = self._read_raw(loans_path)

        target = next((r for r in rows if r["reference_id"] == reference_id), None)
        if target is None:
            return

        # Step 1 — write sentinel
        recovery_path.write_text(reference_id, encoding="utf-8")

        # Step 2 — append to history
        history_row = dict(target)
        history_row["paidoff_date"] = paidoff_date.isoformat()
        self._append_raw(history_path, history_row, HISTORY_FIELDNAMES)

        # Step 3 — remove from loans
        remaining = [r for r in rows if r["reference_id"] != reference_id]
        self._write_raw(loans_path, remaining, FIELDNAMES)

        # Step 4 — clean up sentinel
        recovery_path.unlink()

    def extend_loan(
        self,
        loans_path: Path,
        reference_id: str,
        period: int,
        unit: str,
        today: Optional[date] = None,
        new_due_date: Optional[date] = None,
    ) -> None:
        """Extend a loan's dates by period/unit.

        With due_date:
            new giving_date = old due_date
            new due_date    = old due_date + period (months or days)

        Without due_date (no-due-date branch):
            new giving_date = today (or injected today)
            new due_date    = new_due_date (caller-supplied)
        """
        rows = self._read_raw(loans_path)
        for row in rows:
            if row["reference_id"] != reference_id:
                continue

            old_due_str = row.get("due_date", "")

            if old_due_str:
                old_due = date.fromisoformat(old_due_str)
                new_giving = old_due
                if unit == "months":
                    new_due = old_due + relativedelta(months=period)
                else:
                    from datetime import timedelta
                    new_due = old_due + timedelta(days=period)
            else:
                effective_today = today if today is not None else date.today()
                new_giving = effective_today
                new_due = new_due_date

            row["giving_date"] = new_giving.isoformat()
            row["due_date"] = new_due.isoformat() if new_due else ""

        self._write_raw(loans_path, rows, FIELDNAMES)

    def batch_extend_loans(
        self,
        loans_path: Path,
        extensions: list[dict],
    ) -> None:
        """Batch-extend multiple loan records in a single CSV rewrite.

        Per PD-30: single-pass CSV rewrite for batch approval performance.

        Args:
            loans_path: Path to loans.csv
            extensions: list of dicts, each with keys:
                reference_id: str
                new_giving_date: date
                new_due_date: date or None

        Each matching loan has its giving_date and due_date replaced.
        Non-matching loans are unchanged. Unknown reference_ids are silently skipped.
        """
        rows = self._read_raw(loans_path)
        ext_map = {e["reference_id"]: e for e in extensions}
        for row in rows:
            ref = row.get("reference_id", "").strip()
            if ref in ext_map:
                ext = ext_map[ref]
                row["giving_date"] = self._serialise_value(
                    "giving_date", ext["new_giving_date"]
                )
                row["due_date"] = self._serialise_value(
                    "due_date", ext.get("new_due_date")
                )
        self._write_raw(loans_path, rows, FIELDNAMES)
