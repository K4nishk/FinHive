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


@dataclass(frozen=True)
class ReportReverted:
    """KCH-244: an APPROVED report was undone -- published after the undo's
    own commit succeeds, mirroring ReportApproved/ReportDeclined."""
    report_id: str
