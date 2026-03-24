"""Storage service for managing loan data persistence."""
# Try to use pandas, but fall back to built-in CSV if not available
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("⚠️  Pandas not available, using built-in CSV module")

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

# Import fallback CSV storage if pandas not available
if not HAS_PANDAS:
    from app.services.csv_storage import CSVStorageService


class StorageService:
    """Service for managing loan data storage (CSV or SQLite)."""

    def __init__(self):
        self.encryption_manager = EncryptionManager(settings.encryption_key)
        self.csv_path = settings.csv_file_path
        self.storage_type = settings.storage_type
        self._ensure_storage()

    def _ensure_storage(self):
        """Ensure storage file exists."""
        if self.storage_type == "csv":
            if not self.csv_path.exists():
                # Create empty DataFrame with all columns
                df = pd.DataFrame(columns=[
                    'id', 'borrower_name', 'amount', 'depositor_name',
                    'giving_date', 'due_date', 'borrower_group', 'depositor_group',
                    'status', 'created_at', 'updated_at'
                ])
                df.to_csv(self.csv_path, index=False, encoding='utf-8-sig')
                logger.info("csv_storage_initialized", path=str(self.csv_path))

    def _read_csv(self) -> pd.DataFrame:
        """Read CSV file and decrypt if needed."""
        try:
            if not self.csv_path.exists():
                return pd.DataFrame(columns=[
                    'id', 'borrower_name', 'amount', 'depositor_name',
                    'giving_date', 'due_date', 'borrower_group', 'depositor_group',
                    'status', 'created_at', 'updated_at'
                ])

            df = pd.read_csv(self.csv_path, encoding='utf-8-sig')

            # Decrypt sensitive fields if encryption is enabled
            if self.encryption_manager.is_enabled and len(df) > 0:
                for col in ['borrower_name', 'depositor_name']:
                    if col in df.columns:
                        df[col] = df[col].apply(
                            lambda x: self.encryption_manager.decrypt(str(x)) if pd.notna(x) else x
                        )

            return df
        except Exception as e:
            logger.error("csv_read_error", error=str(e))
            raise StorageException(f"Failed to read CSV: {str(e)}")

    def _write_csv(self, df: pd.DataFrame):
        """Write DataFrame to CSV and encrypt if needed."""
        try:
            # Create a copy for encryption
            df_to_save = df.copy()

            # Encrypt sensitive fields if encryption is enabled
            if self.encryption_manager.is_enabled and len(df_to_save) > 0:
                for col in ['borrower_name', 'depositor_name']:
                    if col in df_to_save.columns:
                        df_to_save[col] = df_to_save[col].apply(
                            lambda x: self.encryption_manager.encrypt(str(x)) if pd.notna(x) else x
                        )

            df_to_save.to_csv(self.csv_path, index=False, encoding='utf-8-sig')
            logger.info("csv_write_success", rows=len(df_to_save), path=str(self.csv_path))
        except Exception as e:
            logger.error("csv_write_error", error=str(e))
            raise StorageException(f"Failed to write CSV: {str(e)}")

    def create_loan(self, loan_data: LoanCreate) -> LoanResponse:
        """Create a new loan record."""
        try:
            df = self._read_csv()

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
                'amount': float(loan_data.amount),
                'depositor_name': loan_data.depositor_name,
                'giving_date': loan_data.giving_date.isoformat(),
                'due_date': loan_data.due_date.isoformat(),
                'borrower_group': loan_data.borrower_group or '',
                'depositor_group': loan_data.depositor_group or '',
                'status': status.value,
                'created_at': now.isoformat(),
                'updated_at': now.isoformat()
            }

            # Append new record
            df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
            self._write_csv(df)

            logger.info("loan_created", loan_id=loan_id, borrower=loan_data.borrower_name)

            return LoanResponse(**new_record)
        except Exception as e:
            logger.error("loan_create_error", error=str(e))
            raise StorageException(f"Failed to create loan: {str(e)}")

    def get_all_loans(self, filters: Optional[LoanFilters] = None) -> List[LoanResponse]:
        """Get all loans with optional filters."""
        try:
            df = self._read_csv()

            if len(df) == 0:
                return []

            # Apply filters
            if filters:
                if filters.borrower_name:
                    df = df[df['borrower_name'].str.contains(filters.borrower_name, case=False, na=False)]
                if filters.depositor_name:
                    df = df[df['depositor_name'].str.contains(filters.depositor_name, case=False, na=False)]
                if filters.status:
                    df = df[df['status'] == filters.status.value]
                if filters.date_from:
                    df = df[pd.to_datetime(df['giving_date']).dt.date >= filters.date_from]
                if filters.date_to:
                    df = df[pd.to_datetime(df['giving_date']).dt.date <= filters.date_to]

            # Convert to LoanResponse objects
            loans = []
            for _, row in df.iterrows():
                loan_dict = row.to_dict()
                # Ensure empty strings and NaN become None for optional fields
                for field in ['borrower_group', 'depositor_group']:
                    value = loan_dict.get(field)
                    if pd.isna(value) or value == '':
                        loan_dict[field] = None
                loans.append(LoanResponse(**loan_dict))

            return loans
        except Exception as e:
            logger.error("loans_fetch_error", error=str(e))
            raise StorageException(f"Failed to fetch loans: {str(e)}")

    def get_loan_by_id(self, loan_id: str) -> LoanResponse:
        """Get a specific loan by ID."""
        try:
            df = self._read_csv()
            loan_df = df[df['id'] == loan_id]

            if len(loan_df) == 0:
                raise LoanNotFoundException(f"Loan with ID {loan_id} not found")

            loan_dict = loan_df.iloc[0].to_dict()
            # Ensure empty strings and NaN become None for optional fields
            for field in ['borrower_group', 'depositor_group']:
                value = loan_dict.get(field)
                if pd.isna(value) or value == '':
                    loan_dict[field] = None

            return LoanResponse(**loan_dict)
        except LoanNotFoundException:
            raise
        except Exception as e:
            logger.error("loan_fetch_error", loan_id=loan_id, error=str(e))
            raise StorageException(f"Failed to fetch loan: {str(e)}")

    def update_loan(self, loan_id: str, loan_update: LoanUpdate) -> LoanResponse:
        """Update an existing loan."""
        try:
            df = self._read_csv()
            loan_idx = df[df['id'] == loan_id].index

            if len(loan_idx) == 0:
                raise LoanNotFoundException(f"Loan with ID {loan_id} not found")

            idx = loan_idx[0]

            # Update fields
            if loan_update.amount is not None:
                df.at[idx, 'amount'] = float(loan_update.amount)
            if loan_update.due_date is not None:
                df.at[idx, 'due_date'] = loan_update.due_date.isoformat()
            if loan_update.status is not None:
                df.at[idx, 'status'] = loan_update.status.value
            if loan_update.borrower_group is not None:
                df.at[idx, 'borrower_group'] = loan_update.borrower_group
            if loan_update.depositor_group is not None:
                df.at[idx, 'depositor_group'] = loan_update.depositor_group

            df.at[idx, 'updated_at'] = datetime.utcnow().isoformat()

            self._write_csv(df)

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
            df = self._read_csv()
            loan_df = df[df['id'] == loan_id]

            if len(loan_df) == 0:
                raise LoanNotFoundException(f"Loan with ID {loan_id} not found")

            # Remove the loan
            df = df[df['id'] != loan_id]
            self._write_csv(df)

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
            df = self._read_csv()

            if len(df) == 0:
                return {
                    "total_loans": 0,
                    "total_amount": 0.0,
                    "active_loans": 0,
                    "paid_off_loans": 0,
                    "overdue_loans": 0,
                    "by_borrower": [],
                    "by_depositor": []
                }

            stats = {
                "total_loans": len(df),
                "total_amount": float(df['amount'].sum()),
                "active_loans": len(df[df['status'] == LoanStatus.ACTIVE.value]),
                "paid_off_loans": len(df[df['status'] == LoanStatus.PAID_OFF.value]),
                "overdue_loans": len(df[df['status'] == LoanStatus.OVERDUE.value]),
                "by_borrower": df.groupby('borrower_name')['amount'].agg(['count', 'sum']).to_dict('index'),
                "by_depositor": df.groupby('depositor_name')['amount'].agg(['count', 'sum']).to_dict('index')
            }

            return stats
        except Exception as e:
            logger.error("statistics_error", error=str(e))
            raise StorageException(f"Failed to generate statistics: {str(e)}")


# Global storage service instance
# Use CSVStorageService if pandas is not available
if HAS_PANDAS:
    storage_service = StorageService()
else:
    storage_service = CSVStorageService()
