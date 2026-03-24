"""CSV storage service using built-in csv module (no pandas dependency)."""
import csv
import json
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, date
from decimal import Decimal
import uuid

from app.config import settings
from app.schemas.loan import LoanCreate, LoanUpdate, LoanResponse, LoanStatus, LoanFilters
from app.core.encryption import EncryptionManager
from app.core.exceptions import LoanNotFoundException, StorageException
from app.core.logging import get_logger

logger = get_logger(__name__)


class CSVStorageService:
    """Lightweight CSV storage service using built-in csv module."""

    FIELDNAMES = [
        'id', 'borrower_name', 'amount', 'depositor_name',
        'giving_date', 'due_date', 'borrower_group', 'depositor_group',
        'status', 'paidoff_date', 'created_at', 'updated_at'
    ]

    def __init__(self):
        self.encryption_manager = EncryptionManager(settings.encryption_key)
        self.csv_path = settings.csv_file_path
        self._ensure_storage()

    def _ensure_storage(self):
        """Ensure CSV file exists with headers."""
        if not self.csv_path.exists():
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
                writer.writeheader()
            logger.info("csv_storage_initialized", path=str(self.csv_path))

    def _read_all_loans(self) -> List[Dict]:
        """Read all loans from CSV."""
        try:
            if not self.csv_path.exists():
                return []

            loans = []
            with open(self.csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Decrypt sensitive fields if encryption is enabled
                    if self.encryption_manager.is_enabled:
                        if row.get('borrower_name'):
                            row['borrower_name'] = self.encryption_manager.decrypt(row['borrower_name'])
                        if row.get('depositor_name'):
                            row['depositor_name'] = self.encryption_manager.decrypt(row['depositor_name'])
                    loans.append(row)
            return loans
        except Exception as e:
            logger.error("csv_read_error", error=str(e))
            raise StorageException(f"Failed to read CSV: {str(e)}")

    def _write_all_loans(self, loans: List[Dict]):
        """Write all loans to CSV."""
        try:
            # Create a copy for encryption
            loans_to_save = []
            for loan in loans:
                loan_copy = loan.copy()
                # Encrypt sensitive fields if encryption is enabled
                if self.encryption_manager.is_enabled:
                    if loan_copy.get('borrower_name'):
                        loan_copy['borrower_name'] = self.encryption_manager.encrypt(loan_copy['borrower_name'])
                    if loan_copy.get('depositor_name'):
                        loan_copy['depositor_name'] = self.encryption_manager.encrypt(loan_copy['depositor_name'])
                loans_to_save.append(loan_copy)

            with open(self.csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
                writer.writeheader()
                writer.writerows(loans_to_save)

            logger.info("csv_write_success", rows=len(loans_to_save), path=str(self.csv_path))
        except Exception as e:
            logger.error("csv_write_error", error=str(e))
            raise StorageException(f"Failed to write CSV: {str(e)}")

    def create_loan(self, loan_data: LoanCreate) -> LoanResponse:
        """Create a new loan record."""
        try:
            loans = self._read_all_loans()

            # Generate new loan record
            loan_id = str(uuid.uuid4())
            now = datetime.utcnow()

            # Calculate initial status
            # 1970-01-01 means "no due date" - always active
            status = LoanStatus.ACTIVE
            if loan_data.due_date != date(1970, 1, 1) and loan_data.due_date < date.today():
                status = LoanStatus.OVERDUE

            new_record = {
                'id': loan_id,
                'borrower_name': loan_data.borrower_name,
                'amount': str(float(loan_data.amount)),
                'depositor_name': loan_data.depositor_name,
                'giving_date': loan_data.giving_date.isoformat(),
                'due_date': loan_data.due_date.isoformat(),
                'borrower_group': loan_data.borrower_group or '',
                'depositor_group': loan_data.depositor_group or '',
                'status': status.value,
                'created_at': now.isoformat(),
                'updated_at': now.isoformat()
            }

            loans.append(new_record)
            self._write_all_loans(loans)

            logger.info("loan_created", loan_id=loan_id, borrower=loan_data.borrower_name)

            return LoanResponse(**new_record)
        except Exception as e:
            logger.error("loan_create_error", error=str(e))
            raise StorageException(f"Failed to create loan: {str(e)}")

    def get_all_loans(self, filters: Optional[LoanFilters] = None) -> List[LoanResponse]:
        """Get all loans with optional filters."""
        try:
            loans = self._read_all_loans()

            # Apply filters
            if filters:
                if filters.borrower_name:
                    loans = [l for l in loans if filters.borrower_name.lower() in l.get('borrower_name', '').lower()]
                if filters.depositor_name:
                    loans = [l for l in loans if filters.depositor_name.lower() in l.get('depositor_name', '').lower()]
                if filters.status:
                    loans = [l for l in loans if l.get('status') == filters.status.value]
                if filters.date_from:
                    loans = [l for l in loans if l.get('giving_date', '') >= filters.date_from.isoformat()]
                if filters.date_to:
                    loans = [l for l in loans if l.get('giving_date', '') <= filters.date_to.isoformat()]

            # Convert to LoanResponse objects
            loan_responses = []
            for loan in loans:
                # Handle optional fields
                loan['borrower_group'] = loan.get('borrower_group') or None
                loan['depositor_group'] = loan.get('depositor_group') or None
                loan_responses.append(LoanResponse(**loan))

            return loan_responses
        except Exception as e:
            logger.error("loans_fetch_error", error=str(e))
            raise StorageException(f"Failed to fetch loans: {str(e)}")

    def get_loan_by_id(self, loan_id: str) -> LoanResponse:
        """Get a specific loan by ID."""
        try:
            loans = self._read_all_loans()
            for loan in loans:
                if loan.get('id') == loan_id:
                    loan['borrower_group'] = loan.get('borrower_group') or None
                    loan['depositor_group'] = loan.get('depositor_group') or None
                    return LoanResponse(**loan)

            raise LoanNotFoundException(f"Loan with ID {loan_id} not found")
        except LoanNotFoundException:
            raise
        except Exception as e:
            logger.error("loan_fetch_error", loan_id=loan_id, error=str(e))
            raise StorageException(f"Failed to fetch loan: {str(e)}")

    def update_loan(self, loan_id: str, loan_update: LoanUpdate) -> LoanResponse:
        """Update an existing loan."""
        try:
            loans = self._read_all_loans()
            loan_found = False

            for loan in loans:
                if loan.get('id') == loan_id:
                    loan_found = True
                    # Update fields
                    if loan_update.amount is not None:
                        loan['amount'] = str(float(loan_update.amount))
                    if loan_update.due_date is not None:
                        loan['due_date'] = loan_update.due_date.isoformat()
                    if loan_update.status is not None:
                        loan['status'] = loan_update.status.value
                    if loan_update.borrower_group is not None:
                        loan['borrower_group'] = loan_update.borrower_group
                    if loan_update.depositor_group is not None:
                        loan['depositor_group'] = loan_update.depositor_group

                    loan['updated_at'] = datetime.utcnow().isoformat()
                    break

            if not loan_found:
                raise LoanNotFoundException(f"Loan with ID {loan_id} not found")

            self._write_all_loans(loans)
            logger.info("loan_updated", loan_id=loan_id)

            return self.get_loan_by_id(loan_id)
        except LoanNotFoundException:
            raise
        except Exception as e:
            logger.error("loan_update_error", loan_id=loan_id, error=str(e))
            raise StorageException(f"Failed to update loan: {str(e)}")

    def delete_loan(self, loan_id: str) -> bool:
        """Delete a loan (hard delete for CSV)."""
        try:
            loans = self._read_all_loans()
            initial_count = len(loans)

            loans = [l for l in loans if l.get('id') != loan_id]

            if len(loans) == initial_count:
                raise LoanNotFoundException(f"Loan with ID {loan_id} not found")

            self._write_all_loans(loans)
            logger.info("loan_deleted", loan_id=loan_id)
            return True
        except LoanNotFoundException:
            raise
        except Exception as e:
            logger.error("loan_delete_error", loan_id=loan_id, error=str(e))
            raise StorageException(f"Failed to delete loan: {str(e)}")

    def get_statistics(self) -> Dict:
        """Get loan statistics for reports."""
        try:
            loans = self._read_all_loans()

            if not loans:
                return {
                    "total_loans": 0,
                    "total_amount": 0.0,
                    "active_loans": 0,
                    "paid_off_loans": 0,
                    "overdue_loans": 0,
                    "by_borrower": {},
                    "by_depositor": {}
                }

            # Calculate statistics
            total_amount = sum(float(l.get('amount', 0)) for l in loans)
            active_count = len([l for l in loans if l.get('status') == LoanStatus.ACTIVE.value])
            paid_off_count = len([l for l in loans if l.get('status') == LoanStatus.PAID_OFF.value])
            overdue_count = len([l for l in loans if l.get('status') == LoanStatus.OVERDUE.value])

            # Group by borrower
            by_borrower = {}
            for loan in loans:
                name = loan.get('borrower_name', 'Unknown')
                if name not in by_borrower:
                    by_borrower[name] = {'count': 0, 'sum': 0.0}
                by_borrower[name]['count'] += 1
                by_borrower[name]['sum'] += float(loan.get('amount', 0))

            # Group by depositor
            by_depositor = {}
            for loan in loans:
                name = loan.get('depositor_name', 'Unknown')
                if name not in by_depositor:
                    by_depositor[name] = {'count': 0, 'sum': 0.0}
                by_depositor[name]['count'] += 1
                by_depositor[name]['sum'] += float(loan.get('amount', 0))

            return {
                "total_loans": len(loans),
                "total_amount": total_amount,
                "active_loans": active_count,
                "paid_off_loans": paid_off_count,
                "overdue_loans": overdue_count,
                "by_borrower": by_borrower,
                "by_depositor": by_depositor
            }
        except Exception as e:
            logger.error("statistics_error", error=str(e))
            raise StorageException(f"Failed to generate statistics: {str(e)}")


# Global storage service instance
csv_storage_service = CSVStorageService()
