from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from loan_manager.application.dtos.import_dto import ImportPreviewDTO, ImportResultDTO
from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.infrastructure.csv.import_service import CsvImportService


class ImportLoans:
    def __init__(self, uow_factory: Callable) -> None:
        self._uow_factory = uow_factory
        self._csv_service = CsvImportService()
        self._ref_id_service = ReferenceIdService()

    def preview(self, file_path: str) -> ImportPreviewDTO:
        """Parse file and count new vs existing ref_ids."""
        records = self._csv_service.parse(file_path)

        with self._uow_factory() as uow:
            new_count = 0
            overwrite_count = 0
            overwrite_ids: list[str] = []

            for rec in records:
                ref_id = rec.get("reference_id")
                if ref_id:
                    existing = uow.loans.get_by_reference_id(ref_id)
                    if existing:
                        overwrite_count += 1
                        if len(overwrite_ids) < 10:
                            overwrite_ids.append(ref_id)
                    else:
                        new_count += 1
                else:
                    new_count += 1

        return ImportPreviewDTO(
            total_new=new_count,
            total_overwrite=overwrite_count,
            sample_overwrite_ids=overwrite_ids,
            file_path=file_path,
        )

    def commit(self, file_path: str, overwrite_existing: bool = True) -> ImportResultDTO:
        """Parse, assign ref_ids, upsert records."""
        records = self._csv_service.parse(file_path)
        today = date.today()
        now = datetime.now()

        inserted = 0
        updated = 0
        skipped = 0
        errors: list[str] = []

        with self._uow_factory() as uow:
            for i, rec in enumerate(records):
                try:
                    if not rec.get("borrower_name") or not rec.get("amount"):
                        errors.append(f"Row {i + 1}: missing required fields")
                        skipped += 1
                        continue

                    ref_id = rec.get("reference_id")
                    if not ref_id:
                        # Assign new reference_id
                        year, month = today.year, today.month
                        ym_key = self._ref_id_service.year_month_key(year, month)
                        last_order = uow.loan_meta.get_last_order(ym_key)
                        ref_id = self._ref_id_service.next_id(year, month, last_order)
                        new_order = 1 if last_order is None else last_order + 1
                        uow.loan_meta.set_last_order(ym_key, new_order)

                    existing = uow.loans.get_by_reference_id(ref_id)
                    if existing and not overwrite_existing:
                        skipped += 1
                        continue

                    giving_date = rec.get("giving_date") or today
                    due_date = rec.get("due_date")
                    status = StatusEngine.compute(giving_date, due_date, today)

                    loan = Loan(
                        id=existing.id if existing else None,
                        reference_id=ReferenceId(ref_id),
                        borrower_name=rec["borrower_name"],
                        borrower_group=rec.get("borrower_group") or "",
                        depositor_name=rec.get("depositor_name") or "",
                        depositor_group=rec.get("depositor_group"),
                        amount=Money(rec["amount"]),
                        giving_date=giving_date,
                        due_period=None,
                        due_date=due_date,
                        status=status,
                        is_active=True,
                        created_at=existing.created_at if existing else now,
                        updated_at=now,
                    )

                    uow.loans.save(loan)
                    if existing:
                        updated += 1
                    else:
                        inserted += 1
                except Exception as e:
                    errors.append(f"Row {i + 1}: {str(e)}")
                    skipped += 1

            uow.commit()

        return ImportResultDTO(
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            errors=errors,
        )
