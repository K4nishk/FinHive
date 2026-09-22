"""
ApplicationServiceLocator -- wires dependencies together.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from loan_manager.infrastructure.database.session import DatabaseSession
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService
from loan_manager.infrastructure.recovery.backup_service import BackupService
from loan_manager.infrastructure.security.key_provider import load_keys
from loan_manager.application.event_bus import EventBus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from finhive.db.keys import KeyRing


class Container:
    def __init__(self) -> None:
        self.recovery_service = RecoveryService()
        self.backup_service = BackupService()
        self.event_bus = EventBus()
        self._key_ring: KeyRing | None = None

    def get_uow(self) -> SqlAlchemyUnitOfWork:
        session = DatabaseSession.get_session()
        return SqlAlchemyUnitOfWork(session)

    def get_key_ring(self) -> KeyRing:
        """The master key ring, loaded once per process.

        Lazy rather than loaded in `__init__` so constructing a Container in a
        test that never touches encryption does not require a configured key.
        Callers that write NPI must go through here -- repositories never read
        the environment themselves.
        """
        if self._key_ring is None:
            self._key_ring = load_keys()
        return self._key_ring
