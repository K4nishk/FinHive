from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from loan_manager.domain.value_objects.status import ExtensionPeriodUnit


TWO_PLACES = Decimal("0.01")


class InterestCalculator:
    @staticmethod
    def calculate_monthly(amount: int, interest_rate: Decimal, extension_period: int) -> Decimal:
        """Interest = (amount x interest_rate x extension_period) / (12 x 100)"""
        result = (Decimal(amount) * interest_rate * Decimal(extension_period)) / Decimal(1200)
        return result.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_daily(amount: int, interest_rate: Decimal, extension_period: int) -> Decimal:
        """Interest = (amount x interest_rate x extension_period) / (365 x 100)"""
        result = (Decimal(amount) * interest_rate * Decimal(extension_period)) / Decimal(36500)
        return result.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_tds(interest_amount: Decimal) -> Decimal:
        """TDS = 0.1 x interest_amount"""
        result = Decimal("0.1") * interest_amount
        return result.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_chq(interest_amount: Decimal, tds_amount: Decimal) -> Decimal:
        """CHQ_Amt = interest_amount - tds_amount"""
        result = interest_amount - tds_amount
        return result.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    @classmethod
    def calculate(cls, amount: int, rate: Decimal, period: int, unit: ExtensionPeriodUnit) -> Decimal:
        """Dispatch to monthly or daily based on unit."""
        if unit == ExtensionPeriodUnit.MONTHS:
            return cls.calculate_monthly(amount, rate, period)
        else:
            return cls.calculate_daily(amount, rate, period)

    @classmethod
    def calculate_both_orchestrator(cls, records: list[dict]) -> list[dict]:
        """Process a list of record dicts, calculating interest/commission/tds/chq for each.

        Each record must have keys: amount, interest_rate, commission_rate,
        extension_period, extension_period_unit, tds_flag.

        Returns records with added: interest_amount, commission_amount, tds_amount, chq_amount.
        """
        results = []
        for record in records:
            amount = record["amount"]
            interest_rate = Decimal(str(record["interest_rate"]))
            commission_rate = Decimal(str(record["commission_rate"]))
            period = record["extension_period"]
            unit = record["extension_period_unit"]
            tds_flag = record["tds_flag"]

            if isinstance(unit, str):
                unit = ExtensionPeriodUnit(unit)

            interest_amount = cls.calculate(amount, interest_rate, period, unit)
            commission_amount = cls.calculate(amount, commission_rate, period, unit)
            tds_amount = cls.calculate_tds(interest_amount) if tds_flag else Decimal("0.00")
            chq_amount = cls.calculate_chq(interest_amount, tds_amount)

            updated = dict(record)
            updated["interest_amount"] = interest_amount
            updated["commission_amount"] = commission_amount
            updated["tds_amount"] = tds_amount
            updated["chq_amount"] = chq_amount
            results.append(updated)

        return results
