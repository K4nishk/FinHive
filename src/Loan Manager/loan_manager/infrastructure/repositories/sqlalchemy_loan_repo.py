from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.repositories.loan_repository import ILoanRepository
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.domain.value_objects.status import LoanStatus
from loan_manager.infrastructure.database.models import LoanModel


def loan_model_to_entity(model: LoanModel) -> Loan:
    """Map ORM model to domain entity."""
    return Loan(
        id=model.id,
        reference_id=ReferenceId(model.reference_id),
        borrower_name=model.borrower_name,
        borrower_group=model.borrower_group,
        depositor_name=model.depositor_name,
        depositor_group=model.depositor_group,
        amount=Money(model.amount),
        giving_date=model.giving_date,
        due_period=model.due_period,
        due_date=model.due_date,
        status=LoanStatus(model.status),
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def loan_entity_to_model(loan: Loan) -> LoanModel:
    """Map domain entity to ORM model."""
    model = LoanModel(
        reference_id=str(loan.reference_id),
        borrower_name=loan.borrower_name,
        borrower_group=loan.borrower_group,
        depositor_name=loan.depositor_name,
        depositor_group=loan.depositor_group,
        amount=int(loan.amount),
        giving_date=loan.giving_date,
        due_period=loan.due_period,
        due_date=loan.due_date,
        status=loan.status.value,
        is_active=loan.is_active,
        created_at=loan.created_at,
        updated_at=loan.updated_at,
    )
    if loan.id is not None:
        model.id = loan.id
    return model


class SqlAlchemyLoanRepository(ILoanRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_reference_id(self, ref_id: str) -> Optional[Loan]:
        model = (
            self._session.query(LoanModel)
            .filter(LoanModel.reference_id == ref_id)
            .first()
        )
        if model is None:
            return None
        return loan_model_to_entity(model)

    def get_all_active(self, filters: Optional[dict] = None) -> list[Loan]:
        query = self._session.query(LoanModel).filter(LoanModel.is_active == True)  # noqa: E712

        if filters:
            if filters.get("borrower_group"):
                query = query.filter(
                    LoanModel.borrower_group.ilike(f"%{filters['borrower_group']}%")
                )
            if filters.get("borrower_name"):
                query = query.filter(
                    LoanModel.borrower_name.ilike(f"%{filters['borrower_name']}%")
                )
            if filters.get("depositor_name"):
                query = query.filter(
                    LoanModel.depositor_name.ilike(f"%{filters['depositor_name']}%")
                )
            if filters.get("depositor_group"):
                query = query.filter(
                    LoanModel.depositor_group.ilike(f"%{filters['depositor_group']}%")
                )
            # by_months is NOT applied at DB level — it's an
            # application-layer filter

        models = query.all()
        return [loan_model_to_entity(m) for m in models]

    def save(self, loan: Loan) -> Loan:
        """Upsert by reference_id — if exists update, else insert."""
        ref_id_str = str(loan.reference_id)
        existing = (
            self._session.query(LoanModel)
            .filter(LoanModel.reference_id == ref_id_str)
            .first()
        )

        if existing:
            existing.borrower_name = loan.borrower_name
            existing.borrower_group = loan.borrower_group
            existing.depositor_name = loan.depositor_name
            existing.depositor_group = loan.depositor_group
            existing.amount = int(loan.amount)
            existing.giving_date = loan.giving_date
            existing.due_period = loan.due_period
            existing.due_date = loan.due_date
            existing.status = loan.status.value
            existing.is_active = loan.is_active
            existing.updated_at = loan.updated_at
            self._session.flush()
            return loan_model_to_entity(existing)
        else:
            model = loan_entity_to_model(loan)
            self._session.add(model)
            self._session.flush()
            return loan_model_to_entity(model)

    def delete(self, reference_id: str) -> None:
        model = (
            self._session.query(LoanModel)
            .filter(LoanModel.reference_id == reference_id)
            .first()
        )
        if model:
            self._session.delete(model)
            self._session.flush()

    def bulk_update_status(self, updates: list[tuple[str, LoanStatus]]) -> None:
        """Efficient bulk update of statuses."""
        for ref_id, new_status in updates:
            self._session.query(LoanModel).filter(
                LoanModel.reference_id == ref_id
            ).update(
                {"status": new_status.value, "updated_at": datetime.now()},
                synchronize_session="fetch",
            )
        self._session.flush()

    def bulk_update_dates(self, updates: list[dict]) -> None:
        """Bulk update giving_date and due_date for loans.

        updates: list of {reference_id, giving_date, due_date}
        """
        for update in updates:
            self._session.query(LoanModel).filter(
                LoanModel.reference_id == update["reference_id"]
            ).update(
                {
                    "giving_date": update["giving_date"],
                    "due_date": update["due_date"],
                    "updated_at": datetime.now(),
                },
                synchronize_session="fetch",
            )
        self._session.flush()

    def set_inactive(self, reference_id: str) -> None:
        self._session.query(LoanModel).filter(
            LoanModel.reference_id == reference_id
        ).update(
            {"is_active": False, "status": LoanStatus.PAIDOFF.value, "updated_at": datetime.now()},
            synchronize_session="fetch",
        )
        self._session.flush()

    def get_unique_values(self, field: str, active_only: bool = True) -> list[str]:
        column = getattr(LoanModel, field, None)
        if column is None:
            return []

        query = self._session.query(column).distinct()
        if active_only:
            query = query.filter(LoanModel.is_active == True)  # noqa: E712

        results = query.all()
        return sorted([r[0] for r in results if r[0] is not None])
