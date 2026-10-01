"""The eval book: `DEMO_LOANS` plus the boundary rows the agent evals need
(KCH-248). Seeded ONLY through the encrypting repository (`demo_seed.seed`),
into a throwaway in-memory database, and never the ledger under `data/`.

`EVAL_RAW` rows are appended after the 27 demo rows (`extend_fixture`), so a
demo edit cannot desync the eval book and the eval book cannot change
`DEMO_LOANS`. The group `kumar logistics` is the date-boundary pair: one loan
whose due date IS the frozen "today" (`today < due_date` is false -> Overdue)
and one whose giving date IS today (`giving_date > today` is false -> Active).
KCH-249 appends further rows here.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.interfaces.turn_recorder import NullTurnRecorder
from loan_manager.container import Container
from loan_manager.infrastructure.database.models import Base
from loan_manager.infrastructure.database.session import DatabaseSession
from loan_manager.infrastructure.security.key_provider import set_active_key_ring
from loan_manager.infrastructure.seed import demo_seed
from loan_manager.infrastructure.seed.demo_fixture import FixtureLoan, extend_fixture
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

EVAL_RAW: tuple[dict, ...] = (
    dict(  # due_date == 2026-09-25 -> Overdue at 2026-09-25 (due today is not < today)
        borrower_name="anand kumar", borrower_group="kumar logistics",
        depositor_name="rohit bansal", depositor_group=None, amount=200000,
        giving_date=date(2026, 3, 25), due_period=None, due_date=date(2026, 9, 25),
    ),
    dict(  # giving_date == 2026-09-25 -> Active at 2026-09-25 (giving today is not > today)
        borrower_name="priya kumar", borrower_group="kumar logistics",
        depositor_name="rohit bansal", depositor_group=None, amount=100000,
        giving_date=date(2026, 9, 25), due_period=None, due_date=date(2027, 3, 25),
    ),
)

ALL_LOANS: tuple[FixtureLoan, ...] = extend_fixture(EVAL_RAW)


def use_ephemeral_key_ring() -> None:
    """For command-line entry points (no pytest key-ring fixture): a random
    key that dies with the process -- the eval database is in-memory too."""
    from finhive.db.keys import KeyRing

    set_active_key_ring(KeyRing(current_version=1, masters={1: os.urandom(32)}))


@contextmanager
def seeded_container(
    today: date, loans: tuple[FixtureLoan, ...] = ALL_LOANS
) -> Iterator[Container]:
    """A `Container` over a fresh `:memory:` database holding `loans`, its
    clock pinned to `today`. `DatabaseSession` is process-wide state, so it is
    saved and restored around the block."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    demo_seed.seed(lambda: factory(), today=today, loans=loans)

    saved = (DatabaseSession._engine, DatabaseSession._SessionLocal)
    DatabaseSession._engine, DatabaseSession._SessionLocal = engine, factory
    try:
        container = Container()
        container.clock = FixedClock(today)
        # Evals never assert on the audit row, and the SQL recorder currently
        # rejects a resolve_entity payload (float `score`); keep runs quiet.
        container.turn_recorder = NullTurnRecorder()
        yield container
    finally:
        DatabaseSession._engine, DatabaseSession._SessionLocal = saved
        engine.dispose()
