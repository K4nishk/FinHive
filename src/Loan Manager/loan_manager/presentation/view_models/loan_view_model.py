from loan_manager.application.dtos.loan_dto import LoanDTO


class LoanViewModel:
    @staticmethod
    def to_display_row(dto: LoanDTO, sno: int) -> dict:
        return {
            "sno": str(sno),
            "reference_id": dto.reference_id,
            "borrower_name": dto.borrower_name or "Unknown",
            "borrower_group": dto.borrower_group or "Unknown",
            "amount": str(dto.amount),
            "depositor_name": dto.depositor_name or "Unknown",
            "depositor_group": dto.depositor_group or "Unknown",
            "giving_date": str(dto.giving_date) if dto.giving_date else "Unknown",
            "due_date": str(dto.due_date) if dto.due_date else "Unknown",
            "status": dto.status.value,
        }
