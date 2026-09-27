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
    CREATE = "Create"

class ExtensionPeriodUnit(str, Enum):
    MONTHS = "months"
    DAYS = "days"

class ReportActor(str, Enum):
    """Who proposed a report (KCH-242): a human via the form, or the agent
    (`Ask FinHive`, KCH-243+) on the user's behalf. Stored in `reports.actor`
    as a 5-char code (`String(5)`), so both members' values must fit."""
    FORM = "FORM"
    AGENT = "AGENT"
