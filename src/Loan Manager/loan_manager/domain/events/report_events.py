from dataclasses import dataclass


@dataclass(frozen=True)
class ReportGenerated:
    report_id: str


@dataclass(frozen=True)
class ReportApproved:
    report_id: str


@dataclass(frozen=True)
class ReportDeclined:
    report_id: str
