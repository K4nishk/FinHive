from __future__ import annotations

from typing import Callable

from loan_manager.application.event_bus import EventBus
from loan_manager.domain.events.report_events import ReportDeclined


class DeclineReport:
    def __init__(self, uow_factory: Callable, event_bus: EventBus) -> None:
        self._uow_factory = uow_factory
        self._event_bus = event_bus

    def execute(self, report_id: str) -> None:
        with self._uow_factory() as uow:
            report = uow.reports.get_by_report_id(report_id)
            if report is None:
                raise ValueError(f"Report not found: {report_id}")

            uow.reports.mark_declined(report_id)
            uow.commit()

        self._event_bus.publish(ReportDeclined(report_id=report_id))
