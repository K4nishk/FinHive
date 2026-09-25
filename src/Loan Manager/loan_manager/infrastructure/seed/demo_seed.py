"""Seed a demo SQLite database with synthetic loan data (KCH-231).

Goes through the encrypting repository like any other write path -- there is
no raw `INSERT` here, so the produced file is exactly what the app itself
would have written via `CreateLoan`/`MarkPaidoff`, encryption included (ARB
D-15). `assert_seed_target` is what keeps this from ever touching the live
`data/loans.db`.

Run: `python -m loan_manager.infrastructure.seed --db data/demo.db`
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable
from datetime import date, datetime, time
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from loan_manager import config
from loan_manager.container import Container
from loan_manager.domain.entities.loan import Loan
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.money import Money
from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.infrastructure.database.models import Base
from loan_manager.infrastructure.database.session import create_sqlite_engine
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from loan_manager.infrastructure.logging.logger import get_logger
from loan_manager.infrastructure.security.key_provider import KeyConfigurationError
from loan_manager.infrastructure.seed.demo_fixture import DEMO_LOANS, FIXTURE_TODAY

logger = get_logger(__name__)

_SIDECAR_SUFFIXES = ("", "-wal", "-shm")


def _log_cli(level: int, message: str) -> None:
    """CLI-facing message (error OR the success line), through `get_logger`
    (BRIEF: no `print()` in production code) instead of `print()`.

    A `logging.StreamHandler()` constructed fresh right here, used once and
    torn down, rather than one attached permanently at import/setup time:
    `StreamHandler` binds `sys.stderr` at CONSTRUCTION, so a handler built
    once and kept around would go stale the moment anything later replaces
    `sys.stderr` (pytest's `capsys` does exactly that, per test). Building it
    at the point of use always picks up whichever `sys.stderr` is current.

    `main()` never calls `setup_logging()` (that is the GUI app's job, not a
    one-shot CLI's), so `logger` otherwise has no handler at all AND no level
    of its own -- a bare `logger.info(...)` on the success path is silently
    swallowed twice over: no handler to write it, and (`Logger.getEffectiveLevel`
    walking up to the root logger's default `WARNING`) filtered out before a
    handler would even matter, since `INFO` < `WARNING`. A successful run of
    `python -m loan_manager.infrastructure.seed` printed nothing (KCH-231 fix
    cycle 2, item 2). Both the error path (`ERROR` already clears the default
    `WARNING` threshold on its own) and the success path (`INFO` does not, so
    this also lowers the logger's own level for the duration of the call) go
    through this one helper so they share the fix.
    """
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    previous_level = logger.level
    if not logger.isEnabledFor(level):
        logger.setLevel(level)
    try:
        logger.log(level, message)
    finally:
        logger.setLevel(previous_level)
        logger.removeHandler(handler)


def _log_cli_error(message: str) -> None:
    _log_cli(logging.ERROR, message)


class SeedRefused(RuntimeError):
    """The requested `--db` target is unsafe to seed: it IS, or resolves to,
    the protected (live) database, or it already holds data and `--replace`
    was not given.
    """


def assert_seed_target(
    db_path: Path,
    *,
    protected: Path | None = None,
    replace: bool = False,
) -> None:
    """Refuse to seed onto `protected`, by identity, not by path spelling.

    `protected` defaults to `config.DEFAULT_DB_PATH`, read through the
    `config` MODULE (not imported by value at module load) and resolved at
    CALL time -- a `None` default plus `config.DEFAULT_DB_PATH` inside the
    body, rather than `protected: Path = DEFAULT_DB_PATH` in the signature.
    A default argument value is bound once, when this function is DEFINED
    (import time); binding it to the name imported by value froze in
    whatever `DEFAULT_DB_PATH` was at that moment, so a test (or a future
    caller) that does `monkeypatch.setattr(config, "DEFAULT_DB_PATH", ...)`
    to redirect the protected path never reached this function at all --
    `assert_seed_target`/`main()` kept comparing against the real, frozen
    default regardless (KCH-231 review 1, item 1a). Reading `config.
    DEFAULT_DB_PATH` from inside the function body looks it up fresh on
    every call.

    Two independent checks, because either alone misses a case the other
    catches:

    * Resolved-path equality (`Path.resolve()`) -- catches `--db
      data/loans.db` from a different working directory, `~/…`, `..`, etc.
    * `os.path.samefile` -- catches a symlink at a DIFFERENT path that
      ultimately points at `protected` (e.g. through a bind mount), which a
      pure string/resolve comparison can miss. Only attempted when both
      paths exist, which is `samefile`'s own precondition.

    Both checks run against `protected` (which defaults to `config.
    DEFAULT_DB_PATH`, as above) AND, always and separately, against `config.
    DB_PATH` -- also read fresh from the `config` module at call time, same
    reasoning. `DB_PATH` is the file the real app actually opens
    (`config.resolve_db_path`: `FINHIVE_DB_PATH` if set, else
    `DEFAULT_DB_PATH`), so when `FINHIVE_DB_PATH` points somewhere other than
    `DEFAULT_DB_PATH` it names a SECOND live database that is just as
    protected as the default one; checking `DEFAULT_DB_PATH` alone would let
    `--db` collide with it (KCH-231 fix cycle 2, item 4).

    A `db_path` that already exists and is non-empty is refused unless
    `replace=True`, in which case the file and its `-wal`/`-shm` sidecars
    (WAL journalling, KCH-231) are removed before the caller creates a fresh
    engine over the same path.
    """
    protected = config.DEFAULT_DB_PATH if protected is None else protected
    db_resolved = db_path.expanduser().resolve()

    for live_db in (protected, config.DB_PATH):
        live_resolved = live_db.expanduser().resolve()

        if db_resolved == live_resolved:
            raise SeedRefused(
                f"refusing to seed {db_path} -- it resolves to the protected "
                f"database {live_db}. Pass a different --db path."
            )

        if db_path.exists() and live_db.exists():
            try:
                if os.path.samefile(db_path, live_db):
                    raise SeedRefused(
                        f"refusing to seed {db_path} -- it is the same file as "
                        f"the protected database {live_db} (symlink)."
                    )
            except OSError:
                pass

    if db_path.exists() and db_path.stat().st_size > 0:
        if not replace:
            raise SeedRefused(
                f"{db_path} already exists and is not empty -- pass --replace "
                "to overwrite it, or choose a different --db path."
            )
        for suffix in _SIDECAR_SUFFIXES:
            sidecar = db_path.with_name(db_path.name + suffix)
            if sidecar.exists():
                sidecar.unlink()


def seed(session_factory: Callable[[], Session], *, today: date) -> int:
    """Write every `DEMO_LOANS` row through the encrypting repository, in
    one `SqlAlchemyUnitOfWork` / one commit.

    `today` pins `StatusEngine.compute` and `created_at` -- never
    `date.today()`, so the seeded statuses are reproducible regardless of
    when this actually runs (ARB: seeded data is synthetic-only). A row with
    a `paidoff_date` is archived to `loan_history` and marked inactive, same
    as the real approve-report path (`approve_report.py`), then excluded
    from `get_all_active` like any other paid-off loan.

    Returns the number of `loans` rows written (27 for `DEMO_LOANS` today;
    the archived-but-paidoff row is included in the count, not the active
    total).
    """
    session = session_factory()
    uow = SqlAlchemyUnitOfWork(session)
    created_at = datetime.combine(today, time(9, 0))
    last_order_by_year_month: dict[str, int] = {}
    count = 0

    try:
        for fixture in DEMO_LOANS:
            year, month, order = ReferenceIdService.parse(fixture.ref)
            year_month = ReferenceIdService.year_month_key(year, month)
            last_order_by_year_month[year_month] = max(
                last_order_by_year_month.get(year_month, 0), order
            )

            status = StatusEngine.compute(fixture.giving_date, fixture.due_date, today)
            loan = Loan(
                id=None,
                reference_id=ReferenceId(fixture.ref),
                borrower_name=fixture.borrower_name,
                borrower_group=fixture.borrower_group,
                depositor_name=fixture.depositor_name,
                depositor_group=fixture.depositor_group,
                amount=Money(fixture.amount),
                giving_date=fixture.giving_date,
                due_period=fixture.due_period,
                due_date=fixture.due_date,
                status=status,
                is_active=True,
                created_at=created_at,
                updated_at=created_at,
            )
            saved = uow.loans.save(loan)
            count += 1

            if fixture.paidoff_date is not None:
                uow.history.archive(saved, fixture.paidoff_date)
                uow.loans.set_inactive(fixture.ref)

        for year_month, last_order in last_order_by_year_month.items():
            uow.loan_meta.set_last_order(year_month, last_order)

        uow.commit()
    except Exception:
        uow.rollback()
        raise
    finally:
        session.close()

    return count


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m loan_manager.infrastructure.seed",
        description=(
            "Seed a demo SQLite database with synthetic loan data. "
            "Never runs against the live database -- see assert_seed_target."
        ),
    )
    parser.add_argument(
        "--db", required=True, help="Path to the demo database file to create (or replace)."
    )
    parser.add_argument(
        "--today",
        default=FIXTURE_TODAY.isoformat(),
        help=(
            "Pinned 'today' for status computation, YYYY-MM-DD "
            f"(default {FIXTURE_TODAY.isoformat()})."
        ),
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Overwrite --db (and its -wal/-shm sidecars) if it already exists and is non-empty.",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.db).expanduser().resolve()
    today = date.fromisoformat(args.today)

    # Prove the master key is usable, and BEFORE `assert_seed_target` can
    # delete anything -- `--replace` unlinks an existing non-empty target's
    # file and `-wal`/`-shm` sidecars as part of that check (KCH-231 review
    # 1, item 4): if the key turned out to be unusable, that deletion must
    # not have already happened. Same reasoning as main.py step 3a: a seed
    # encrypted under a key that turns out to be unusable is worse than no
    # file at all -- here that also means it must be worse than losing
    # whatever `--replace` was about to overwrite.
    container = Container()
    try:
        container.get_key_ring()
    except KeyConfigurationError as exc:
        _log_cli_error(f"Cannot seed demo database.\n\n{exc}")
        return 1

    try:
        assert_seed_target(db_path, replace=args.replace)
    except SeedRefused as exc:
        _log_cli_error(f"Refusing to seed: {exc}")
        return 1

    engine = create_sqlite_engine(db_path)
    try:
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        count = seed(session_factory, today=today)
        _log_cli(logging.INFO, f"Seeded {count} demo loans into {db_path}")
    finally:
        engine.dispose()

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
