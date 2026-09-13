"""
ApplicationServiceLocator -- wires dependencies together.
"""
from __future__ import annotations

from loan_manager.infrastructure.database.session import DatabaseSession
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService
from loan_manager.infrastructure.recovery.backup_service import BackupService
from loan_manager.application.event_bus import EventBus


class Container:
    def __init__(self) -> None:
        self.recovery_service = RecoveryService()
        self.backup_service = BackupService()
        self.event_bus = EventBus()

    def get_uow(self) -> SqlAlchemyUnitOfWork:
        session = DatabaseSession.get_session()
        return SqlAlchemyUnitOfWork(session)
