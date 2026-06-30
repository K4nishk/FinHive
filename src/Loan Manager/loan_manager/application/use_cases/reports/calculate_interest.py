from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

from dateutil.relativedelta import relativedelta

from loan_manager.application.dtos.calculation_dto import (
    CalculationLineDTO,
    CalculationRequestDTO,
    CalculationResultDTO,
)
from loan_manager.application.dtos.loan_dto import LoanFilterDTO
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.domain.services.interest_calculator import InterestCalculator
from loan_manager.domain.value_objects.status import CalculationMode, ExtensionPeriodUnit


class CalculateInterest:
    def __init__(self, uow_factory: Callable) -> None:
        self._get_loans = GetAllLoans(uow_factory)

    def execute(self, dto: CalculationRequestDTO) -> CalculationResultDTO:
        # Get loans with filters
        loans = self._get_loans.execute(dto.filters)

        # Exclude Paidoff records (is_active=False already excluded by get_all_active)

        lines: list[CalculationLineDTO] = []

        for loan in loans:
            # Determine unit per record for Both mode
            if dto.mode == CalculationMode.BOTH:
                unit = dto.extension_period_unit
            elif dto.mode == CalculationMode.MONTHLY:
                unit = ExtensionPeriodUnit.MONTHS
            elif dto.mode == CalculationMode.DAILY:
                unit = ExtensionPeriodUnit.DAYS
            else:
                unit = dto.extension_period_unit

            interest_amount = InterestCalculator.calculate(
                loan.amount, dto.interest_rate, dto.extension_period, unit
            )
            commission_amount = InterestCalculator.calculate(
                loan.amount, dto.commission_rate, dto.extension_period, unit
            )
            tds_amount = (
                InterestCalculator.calculate_tds(interest_amount) if dto.tds_flag else Decimal("0.00")
            )
            chq_amount = InterestCalculator.calculate_chq(interest_amount, tds_amount)

            # Compute post_extension dates
            post_extension_giving_date = None
            post_extension_due_date = None
            if loan.due_date is not None:
                post_extension_giving_date = loan.due_date
                if unit == ExtensionPeriodUnit.MONTHS:
                    post_extension_due_date = loan.due_date + relativedelta(months=dto.extension_period)
                else:
                    post_extension_due_date = loan.due_date + timedelta(days=dto.extension_period)

            lines.append(
                CalculationLineDTO(
                    reference_id=loan.reference_id,
                    borrower_name=loan.borrower_name,
                    depositor_name=loan.depositor_name,
                    amount=loan.amount,
                    giving_date=loan.giving_date,
                    due_date=loan.due_date,
                    extension_period=dto.extension_period,
                    extension_period_unit=unit,
                    interest_rate=dto.interest_rate,
                    commission_rate=dto.commission_rate,
                    tds_flag=dto.tds_flag,
                    interest_amount=interest_amount,
                    commission_amount=commission_amount,
                    tds_amount=tds_amount,
                    chq_amount=chq_amount,
                    post_extension_giving_date=post_extension_giving_date,
                    post_extension_due_date=post_extension_due_date,
                )
            )

        total_amount = sum(line.amount for line in lines)
        total_interest = sum(line.interest_amount for line in lines)
        total_commission = sum(line.commission_amount for line in lines)
        total_tds = sum(line.tds_amount for line in lines)

        return CalculationResultDTO(
            mode=dto.mode,
            lines=lines,
            total_amount=total_amount,
            total_interest=total_interest,
            total_commission=total_commission,
            total_tds=total_tds,
        )
