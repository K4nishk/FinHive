"""CreateLoan.stage unit tests (KCH-242).

ApproveReport's CREATE branch needs to mint and save several new loans on
its OWN already-open unit of work, then commit them together with the
report's own `mark_approved` in one transaction -- reusing `CreateLoan`
wholesale (Ponytail rung 2) rather than reimplementing reference-id minting
in `approve_report.py`. `stage()` is the extraction that makes that
possible: everything `execute()` used to do inside its `with` block, minus
the commit and the `LoanCreated` publish, both of which must wait for the
CALLER's own transaction (and, for the event, its own commit) to succeed.

Fakes, not a real database or event bus subscriber pair, on purpose: what
this file has to prove is purely behavioural -- "does `stage()` call
`commit()`?", "does it publish?" -- and a spy answers that directly, where a
real `SqlAlchemyUnitOfWork` would only prove it INDIRECTLY through what rows
happen to be visible on a shared SQLite connection.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from loan_manager.application.dtos.loan_dto import LoanCreateDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.create_loan import CreateLoan
from loan_manager.domain.events.loan_events import LoanCreated
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.domain.value_objects.reference_id import ReferenceId


class _SpyLoanMetaRepo:
    def __init__(self) -> None:
        self.last_order = None
        self.set_calls: list[tuple[str, int]] = []

    def get_last_order(self, year_month):
        return self.last_order

    def set_last_order(self, year_month, order):
        self.set_calls.append((year_month, order))
        self.last_order = order


class _SpyLoanRepo:
    def __init__(self) -> None:
        self.saved: list = []

    def get_by_reference_id(self, ref_id):
        for loan in self.saved:
            if str(loan.reference_id) == ref_id:
                return loan
        return None

    def save(self, loan):
        self.saved.append(loan)
        return loan


class _SpyUow:
    def __init__(self) -> None:
        self.loan_meta = _SpyLoanMetaRepo()
        self.loans = _SpyLoanRepo()
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def __enter__(self) -> _SpyUow:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


def _dto() -> LoanCreateDTO:
    return LoanCreateDTO(
        borrower_name="borrower",
        borrower_group="group",
        depositor_name="depositor",
        depositor_group=None,
        amount=10000,
        giving_date=date(2026, 3, 1),
        due_date=date(2026, 6, 1),
    )


def test_stage_saves_and_mints_a_reference_id_but_never_commits_or_publishes():
    uow = _SpyUow()
    published: list = []
    event_bus = EventBus()
    event_bus.subscribe(LoanCreated, published.append)

    create_loan = CreateLoan(
        uow_factory=lambda: uow,
        ref_id_service=ReferenceIdService(),
        event_bus=event_bus,
        clock=FixedClock(date(2026, 3, 15)),
    )

    loan = create_loan.stage(uow, _dto())

    assert str(loan.reference_id) == "2026_03_001"
    assert uow.loans.saved == [loan], "stage() must save the loan on the SAME uow it was given"
    assert uow.loan_meta.set_calls == [("2026_03", 1)], (
        "stage() must advance the loan_meta counter on the same uow"
    )
    assert uow.committed is False, (
        "stage() must never commit -- ApproveReport's CREATE branch commits "
        "once, atomically, after staging every record"
    )
    assert published == [], (
        "stage() must never publish LoanCreated -- only execute() does, and "
        "only after its own commit succeeds"
    )


def test_stage_mints_sequential_reference_ids_across_calls_on_the_same_uow():
    uow = _SpyUow()
    create_loan = CreateLoan(
        uow_factory=lambda: uow,
        ref_id_service=ReferenceIdService(),
        event_bus=EventBus(),
        clock=FixedClock(date(2026, 3, 15)),
    )

    first = create_loan.stage(uow, _dto())
    second = create_loan.stage(uow, _dto())

    assert str(first.reference_id) == "2026_03_001"
    assert str(second.reference_id) == "2026_03_002"
    assert uow.committed is False


def test_stage_skips_an_already_existing_reference_id_and_never_overwrites_it():
    """KCH-242 review cycle 1 (BLOCKER): `uow.loans.save()` upserts by
    reference_id, so a `loan_meta` counter that lagged behind a loan already
    on record under the NEXT id it would otherwise mint (e.g. an import that
    wrote its own explicit reference_id without bumping the counter --
    ImportLoans does exactly this, see import_loans.py) must never make
    `stage()` mint that same, already-taken id -- doing so silently
    overwrites the existing loan instead of inserting a new one.

    Repro this guards: import 2026_03_001 (loan_meta stays at None/0), then
    a CREATE approval with clock 2026-03-15 -- unguarded, stage() would mint
    2026_03_001 again and `save()` would UPDATE the existing loan in place,
    destroying it (success=True, no error).
    """
    uow = _SpyUow()
    existing = SimpleNamespace(
        reference_id=ReferenceId("2026_03_001"), is_active=True, borrower_name="original",
    )
    uow.loans.saved.append(existing)  # loan_meta.last_order stays None -- the lag

    create_loan = CreateLoan(
        uow_factory=lambda: uow,
        ref_id_service=ReferenceIdService(),
        event_bus=EventBus(),
        clock=FixedClock(date(2026, 3, 15)),
    )

    loan = create_loan.stage(uow, _dto())

    assert str(loan.reference_id) == "2026_03_002", (
        "stage() must skip past the already-existing 2026_03_001 rather "
        "than reminting it"
    )
    assert uow.loans.saved[0] is existing, (
        "the pre-existing loan must be untouched, not overwritten"
    )
    assert uow.loans.saved[1] is loan
    assert uow.loan_meta.set_calls == [("2026_03", 2)], (
        "the persisted counter must reflect the order actually minted (2), "
        "not the lagging value (None/1) stage() started from -- otherwise "
        "the very next mint would collide again"
    )


def test_stage_skips_past_several_consecutive_existing_reference_ids():
    """Same property, several collisions in a row -- proves the skip is a
    loop, not a single-step lookahead."""
    uow = _SpyUow()
    for order in (1, 2, 3):
        uow.loans.saved.append(
            SimpleNamespace(reference_id=ReferenceId.build(2026, 3, order), is_active=True)
        )

    create_loan = CreateLoan(
        uow_factory=lambda: uow,
        ref_id_service=ReferenceIdService(),
        event_bus=EventBus(),
        clock=FixedClock(date(2026, 3, 15)),
    )

    loan = create_loan.stage(uow, _dto())

    assert str(loan.reference_id) == "2026_03_004"
    assert uow.loan_meta.set_calls == [("2026_03", 4)]


def test_execute_still_commits_once_and_publishes_loan_created():
    """Unchanged-behaviour guard: execute() built on top of stage() must
    still do exactly what it did before this refactor -- one commit, one
    LoanCreated publish."""
    uow = _SpyUow()
    published: list = []
    event_bus = EventBus()
    event_bus.subscribe(LoanCreated, published.append)

    create_loan = CreateLoan(
        uow_factory=lambda: uow,
        ref_id_service=ReferenceIdService(),
        event_bus=event_bus,
        clock=FixedClock(date(2026, 3, 15)),
    )

    dto_result = create_loan.execute(_dto())

    assert uow.committed is True
    assert len(published) == 1
    assert published[0].reference_id == dto_result.reference_id == "2026_03_001"
