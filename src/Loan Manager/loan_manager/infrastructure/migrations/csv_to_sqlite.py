"""
BL-24 — CSV to SQLite one-time migration.

Migrates legacy CSV files to the SQLite database on first MVP1 launch.
Run automatically by DatabaseSession.initialize() if loans.db is absent
but loans.csv is present, or triggered manually from Settings Tab.

Safe to re-run: existing records are upserted (imported data wins on collision).
Original CSV files are renamed to *.bak on success — never deleted.
"""
from __future__ import annotations

import logging
import shutil
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from loan_manager.config import DATA_DIR
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.status import LoanStatus
from loan_manager.infrastructure.csv.import_service import CsvImportService
from loan_manager.infrastructure.database.models import LoanModel, LoanMetaModel

logger = logging.getLogger(__name__)

LEGACY_FILES = {
    "loans": DATA_DIR / "loans.csv",
    "history": DATA_DIR / "history.csv",
    "pending_reports": DATA_DIR / "pending_reports.csv",
    "pending_report_records": DATA_DIR / "pending_report_records.csv",
}


class CsvToSqliteMigration:
    """Migrates legacy CSV files into the SQLite database."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._import_service = CsvImportService()

    def is_needed(self) -> bool:
        """Returns True if loans.csv exists and has data worth migrating."""
        loans_csv = LEGACY_FILES["loans"]
        return loans_csv.exists() and loans_csv.stat().st_size > 0

    def run(self) -> MigrationResult:
        """
        Execute the migration.
        Returns a MigrationResult with counts and any errors.
        """
        result = MigrationResult()

        # Migrate loans
        loans_csv = LEGACY_FILES["loans"]
        if loans_csv.exists():
            logger.info(f"Migrating {loans_csv} to SQLite")
            try:
                inserted, updated, errors = self._migrate_loans(loans_csv)
                result.loans_inserted = inserted
                result.loans_updated = updated
                result.errors.extend(errors)
                self._session.commit()
                self._backup_file(loans_csv)
                logger.info(f"Loans migration complete: {inserted} inserted, {updated} updated")
            except Exception as exc:
                self._session.rollback()
                result.errors.append(f"Loans migration failed: {exc}")
                logger.error(f"Loans migration failed: {exc}", exc_info=True)
                return result

        result.success = len(result.errors) == 0
        return result

    def _migrate_loans(self, csv_path: Path) -> tuple[int, int, list[str]]:
        inserted = 0
        updated = 0
        errors: list[str] = []
        today = date.today()

        raw_records = self._import_service.parse(str(csv_path))

        # Track used ref_ids to detect collisions
        used_ids: set[str] = set()
        existing_rows = self._session.query(LoanModel.reference_id).all()
        existing_ids = {r[0] for r in existing_rows}

        for raw in raw_records:
            try:
                ref_id = self._resolve_ref_id(raw, used_ids, existing_ids, today)
                used_ids.add(ref_id)

                giving_date = raw.get("giving_date")
                due_date = raw.get("due_date")
                status = StatusEngine.compute(giving_date, due_date, today)

                now = datetime.now()
                existing = self._session.query(LoanModel).filter_by(reference_id=ref_id).first()

                if existing:
                    # Imported data wins
                    existing.borrower_name = (raw.get("borrower_name") or "").lower().strip()
                    existing.borrower_group = (raw.get("borrower_group") or "").lower().strip()
                    existing.depositor_name = (raw.get("depositor_name") or "").lower().strip()
                    existing.depositor_group = (raw.get("depositor_group") or "").lower().strip() or None
                    existing.amount = int(raw.get("amount") or 0)
                    existing.giving_date = giving_date
                    existing.due_date = due_date
                    existing.status = status.value
                    existing.updated_at = now
                    updated += 1
                else:
                    model = LoanModel(
                        reference_id=ref_id,
                        borrower_name=(raw.get("borrower_name") or "").lower().strip(),
                        borrower_group=(raw.get("borrower_group") or "").lower().strip(),
                        depositor_name=(raw.get("depositor_name") or "").lower().strip(),
                        depositor_group=(raw.get("depositor_group") or "").lower().strip() or None,
                        amount=int(raw.get("amount") or 0),
                        giving_date=giving_date,
                        due_date=due_date,
                        status=status.value,
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                    self._session.add(model)
                    inserted += 1

                # Update meta counter
                self._update_meta_counter(ref_id)

            except Exception as exc:
                errors.append(f"Row error ({raw.get('reference_id', '?')}): {exc}")
                logger.warning(f"Skipping row due to error: {exc}")

        return inserted, updated, errors

    def _resolve_ref_id(
        self,
        raw: dict,
        used_ids: set[str],
        existing_ids: set[str],
        today: date,
    ) -> str:
        ref_id = raw.get("reference_id") or ""
        ref_id = ref_id.strip()

        if not ref_id:
            # Auto-assign using today's YYYY_MM
            year, month = today.year, today.month
            year_month = ReferenceIdService.year_month_key(year, month)
            meta = self._session.query(LoanMetaModel).filter_by(year_month=year_month).first()
            last = meta.last_order if meta else 0
            candidate = ReferenceIdService.next_id(year, month, last)
            while candidate in used_ids or candidate in existing_ids:
                last += 1
                candidate = ReferenceIdService.next_id(year, month, last)
            return candidate

        # Validate format; if non-standard, treat as missing
        try:
            ReferenceIdService.parse(ref_id)
        except (ValueError, AttributeError):
            raw["reference_id"] = ""
            return self._resolve_ref_id(raw, used_ids, existing_ids, today)

        # Standard format — check collision
        candidate = ref_id
        while candidate in used_ids:
            # Increment order to resolve collision
            y, m, o = ReferenceIdService.parse(candidate)
            candidate = ReferenceIdService.next_id(y, m, o)

        return candidate

    def _update_meta_counter(self, ref_id: str) -> None:
        try:
            year, month, order = ReferenceIdService.parse(ref_id)
            year_month = ReferenceIdService.year_month_key(year, month)
            meta = self._session.query(LoanMetaModel).filter_by(year_month=year_month).first()
            if meta:
                if order > meta.last_order:
                    meta.last_order = order
            else:
                self._session.add(LoanMetaModel(year_month=year_month, last_order=order))
        except Exception:
            pass  # Non-critical; counter can be rebuilt

    @staticmethod
    def _backup_file(path: Path) -> None:
        backup = path.with_suffix(".csv.bak")
        shutil.copy2(path, backup)
        logger.info(f"Backed up {path.name} → {backup.name}")


class MigrationResult:
    def __init__(self) -> None:
        self.success: bool = False
        self.loans_inserted: int = 0
        self.loans_updated: int = 0
        self.errors: list[str] = []

    def __repr__(self) -> str:
        return (
            f"MigrationResult(success={self.success}, "
            f"inserted={self.loans_inserted}, updated={self.loans_updated}, "
            f"errors={len(self.errors)})"
        )
