from enum import Enum

class LoanStatus(str, Enum):
    ACTIVE = "Active"
    OVERDUE = "Overdue"
    PENDING = "Pending"
    PAIDOFF = "Paidoff"

class ReportStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    DECLINED = "Declined"

class CalculationMode(str, Enum):
    MONTHLY = "Monthly"
    DAILY = "Daily"
    BOTH = "Both"
    PAIDOFF = "Paidoff"

class ExtensionPeriodUnit(str, Enum):
    MONTHS = "months"
    DAYS = "days"
