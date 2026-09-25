"""
ApplicationServiceLocator -- wires dependencies together.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from loan_manager.infrastructure.database.session import DatabaseSession
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService
from loan_manager.infrastructure.recovery.backup_service import BackupService
from loan_manager.infrastructure.security.key_provider import (
    load_keys,
    set_active_key_ring,
)
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import Clock, SystemClock

if TYPE_CHECKING:  # pragma: no cover - typing only
    from finhive.db.keys import KeyRing


class Container:
    def __init__(self) -> None:
        self.recovery_service = RecoveryService()
        self.backup_service = BackupService()
        self.event_bus = EventBus()
        self.clock: Clock = SystemClock()
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
            # Wires up the encrypted-column TypeDecorators (KCH-227) -- they
            # cannot reach this Container, so this is the one call site that
            # makes the just-loaded ring the active key they read.
            set_active_key_ring(self._key_ring)
        return self._key_ring
