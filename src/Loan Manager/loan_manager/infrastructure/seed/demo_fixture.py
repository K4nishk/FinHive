"""Synthetic demo-data constants for `demo_seed.py` (KCH-231).

Pure data -- no SQLAlchemy, no PySide6, no I/O. This module must never import
`tests/`: it is the one direction of reuse allowed, `tests/fixtures/sample_data`
imports FROM here for its drift check (`test_demo_fixture.py`), not the other
way round, so a data change lands once, in this file.

All names/groups below are the lower-cased, stripped form the app itself
writes (see `application/dtos/loan_dto.LoanCreateDTO.to_lowercase`) -- the
seeder does not re-normalise, it copies these into `Loan` entities verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from loan_manager.domain.services.reference_id_service import ReferenceIdService

# Pinned "today" for demo status computation (ARB D-15 seeding is
# synthetic-only; never `date.today()` -- a moving pin would silently change
# every row's status on whatever day someone happens to run the seeder).
FIXTURE_TODAY = date(2026, 9, 25)


@dataclass(frozen=True)
class FixtureLoan:
    ref: str
    borrower_name: str
    borrower_group: str
    depositor_name: str
    depositor_group: str | None
    amount: int
    giving_date: date
    due_period: int | None
    due_date: date | None
    paidoff_date: date | None = None


# The first 15 rows are `tests/fixtures/sample_data.SAMPLE_LOANS`, byte-for-byte
# (same borrower/depositor/amount/giving_date/due_date, in the same order) --
# `test_demo_fixture.py::first_15_rows_equal_sample_data` is a drift trip-wire
# so the two never quietly diverge. `due_period=None` there too: SAMPLE_LOANS
# always sets `due_date` directly, never derives it from a period.
_RAW: tuple[dict, ...] = (
    dict(
        borrower_name="b1", borrower_group="bg1", depositor_name="d1", depositor_group="dg1",
        amount=10000, giving_date=date(2026, 1, 2), due_period=None, due_date=date(2026, 4, 2),
    ),
    dict(
        borrower_name="b2", borrower_group="bg2", depositor_name="d2", depositor_group="dg1",
        amount=10000, giving_date=date(2026, 1, 4), due_period=None, due_date=date(2026, 5, 4),
    ),
    dict(
        borrower_name="b3", borrower_group="bg3", depositor_name="d3", depositor_group="dg1",
        amount=15000, giving_date=date(2026, 2, 6), due_period=None, due_date=date(2026, 5, 6),
    ),
    dict(
        borrower_name="b4", borrower_group="bg3", depositor_name="d4", depositor_group="dg2",
        amount=20000, giving_date=date(2026, 2, 7), due_period=None, due_date=date(2026, 6, 7),
    ),
    dict(
        borrower_name="b5", borrower_group="bg4", depositor_name="d5", depositor_group="dg2",
        amount=20000, giving_date=date(2026, 2, 8), due_period=None, due_date=date(2026, 6, 8),
    ),
    dict(
        borrower_name="b6", borrower_group="bg4", depositor_name="d6", depositor_group="dg3",
        amount=15000, giving_date=date(2026, 2, 8), due_period=None, due_date=date(2026, 7, 8),
    ),
    dict(
        borrower_name="b7", borrower_group="bg5", depositor_name="d7", depositor_group="dg3",
        amount=15000, giving_date=date(2026, 2, 15), due_period=None,
        due_date=date(2026, 7, 15),
    ),
    dict(
        borrower_name="b8", borrower_group="bg5", depositor_name="d8", depositor_group="dg3",
        amount=20000, giving_date=date(2026, 2, 18), due_period=None,
        due_date=date(2026, 6, 18),
    ),
    dict(
        borrower_name="b9", borrower_group="bg1", depositor_name="d9", depositor_group="dg3",
        amount=20000, giving_date=date(2026, 2, 20), due_period=None,
        due_date=date(2026, 6, 20),
    ),
    dict(
        borrower_name="b10", borrower_group="bg6", depositor_name="d10", depositor_group="dg1",
        amount=10000, giving_date=date(2026, 2, 25), due_period=None,
        due_date=date(2026, 5, 25),
    ),
    dict(
        borrower_name="b11", borrower_group="bg6", depositor_name="d11", depositor_group="dg2",
        amount=15000, giving_date=date(2026, 2, 28), due_period=None,
        due_date=date(2026, 5, 28),
    ),
    dict(
        borrower_name="b12", borrower_group="bg7", depositor_name="d12", depositor_group="dg4",
        amount=15000, giving_date=date(2026, 3, 2), due_period=None, due_date=date(2026, 7, 2),
    ),
    dict(
        borrower_name="b13", borrower_group="bg7", depositor_name="d13", depositor_group="dg4",
        amount=10000, giving_date=date(2026, 3, 5), due_period=None, due_date=date(2026, 7, 5),
    ),
    dict(
        borrower_name="b14", borrower_group="bg8", depositor_name="d14", depositor_group=None,
        amount=15000, giving_date=date(2026, 3, 10), due_period=None,
        due_date=date(2026, 7, 10),
    ),
    dict(
        borrower_name="b15", borrower_group="bg8", depositor_name="d15", depositor_group=None,
        amount=20000, giving_date=date(2026, 3, 14), due_period=None,
        due_date=date(2026, 7, 14),
    ),
    # New rows (KCH-231 plan, ORCH-approved 2026-09-25). Statuses in the
    # comments are what StatusEngine.compute() derives at FIXTURE_TODAY --
    # not stored here, `demo_seed.seed()` computes them at seed time.
    dict(
        borrower_name="rakesh sharma", borrower_group="sharma group",
        depositor_name="meera iyer", depositor_group="chennai circle", amount=250000,
        giving_date=date(2026, 4, 10), due_period=None, due_date=date(2026, 7, 10),
    ),  # Overdue
    dict(
        borrower_name="sunita sharma", borrower_group="sharma group",
        depositor_name="arjun rao", depositor_group="chennai circle", amount=150000,
        giving_date=date(2026, 6, 1), due_period=None, due_date=date(2026, 12, 1),
    ),  # Active
    dict(
        borrower_name="vikram sharma", borrower_group="sharma group",
        depositor_name="meera iyer", depositor_group="chennai circle", amount=300000,
        giving_date=date(2026, 2, 15), due_period=None, due_date=date(2026, 8, 15),
    ),  # Overdue
    dict(
        borrower_name="anil sharma", borrower_group="sharma group",
        depositor_name="kavita nair", depositor_group=None, amount=120000,
        giving_date=date(2026, 8, 20), due_period=None, due_date=date(2027, 2, 20),
    ),  # Active
    dict(
        borrower_name="suresh iyer", borrower_group="iyer chem",
        depositor_name="farhan qureshi", depositor_group="mumbai desk", amount=500000,
        giving_date=date(2026, 5, 5), due_period=None, due_date=date(2026, 11, 5),
    ),  # Active
    dict(
        borrower_name="lakshmi iyer", borrower_group="iyer chem", depositor_name="meera iyer",
        depositor_group="chennai circle", amount=200000, giving_date=date(2026, 3, 1),
        due_period=None, due_date=date(2026, 9, 1),
    ),  # Overdue
    dict(
        borrower_name="b16", borrower_group="bg10", depositor_name="d16",
        depositor_group="dg1", amount=10000, giving_date=date(2026, 3, 20), due_period=None,
        due_date=date(2026, 10, 20),
    ),  # Active
    dict(
        borrower_name="b17", borrower_group="bg13", depositor_name="d17",
        depositor_group="dg5", amount=15000, giving_date=date(2026, 4, 2), due_period=None,
        due_date=date(2026, 12, 2),
    ),  # Active
    dict(
        borrower_name="deepak menon", borrower_group="menon traders",
        depositor_name="arjun rao", depositor_group="mumbai desk", amount=80000,
        giving_date=date(2026, 6, 15), due_period=None, due_date=None,
    ),  # Overdue, undated (G-07)
    dict(
        borrower_name="pooja verma", borrower_group="verma textiles",
        depositor_name="kavita nair", depositor_group=None, amount=175000,
        giving_date=date(2027, 1, 15), due_period=None, due_date=date(2027, 7, 15),
    ),  # Pending
    dict(
        borrower_name="ramesh gupta", borrower_group="gupta & sons",
        depositor_name="meera iyer", depositor_group="chennai circle", amount=90000,
        giving_date=date(2026, 1, 10), due_period=None, due_date=date(2026, 7, 10),
        paidoff_date=date(2026, 7, 12),
    ),  # Paidoff, archived, is_active=False
    dict(
        borrower_name="naveen rao", borrower_group="rao holdings",
        depositor_name="asha bhat", depositor_group="bangalore desk", amount=10000000,
        giving_date=date(2026, 7, 20), due_period=None, due_date=date(2027, 1, 20),
    ),  # Active. amount=10_000_000 >= 2**23 -- its SQLite minimal big-endian
    # int encoding is 4 bytes, unlike every other DEMO_LOANS amount (<=
    # 500000, <= 3 bytes), which `test_demo_seed.py`'s `>= 4 byte` raw-bytes
    # scan silently ignored (KCH-231 fix cycle 2, item 1). Group/name values
    # deliberately do not reuse bg3/dg3/bg1/"sharma group"/"iyer chem"/"meera
    # iyer" so every `CHECKPOINTS` count in this file stays correct, and the
    # giving_date (July 2026) does not fall in a year-month any existing test
    # counts rows against (see `test_next_create_loan_ref_does_not_collide`,
    # keyed on "2026_02").
)


def _build_demo_loans(raw: tuple[dict, ...]) -> tuple[FixtureLoan, ...]:
    """Assign each row a `reference_id`, sequential per `(year, month)` of
    its OWN `giving_date`, in the order rows appear above.

    Refs are computed rather than hand-typed so 26 transcribed strings can
    never drift out of sequence with each other -- `ReferenceIdService` is
    the same service `CreateLoan` uses, so `demo_seed.seed()` can derive the
    correct `loan_meta.last_order` per year-month straight from these refs
    (`ReferenceIdService.parse`), instead of a second hand-maintained count.
    """
    counts: dict[str, int] = {}
    loans = []
    for row in raw:
        year, month = row["giving_date"].year, row["giving_date"].month
        year_month = ReferenceIdService.year_month_key(year, month)
        counts[year_month] = counts.get(year_month, 0) + 1
        order = counts[year_month]
        ref = f"{year_month}_{ReferenceIdService.format_order(order)}"
        loans.append(FixtureLoan(ref=ref, **row))
    return tuple(loans)


DEMO_LOANS: tuple[FixtureLoan, ...] = _build_demo_loans(_RAW)

# Active-loan counts (post-seed, via `ILoanRepository.get_all_active`) that
# `test_demo_seed.py::checkpoints_reproduce` verifies against the seeded
# database -- (field, filter_value, expected_count). Values were counted
# against `DEMO_LOANS` above, not assumed from the plan text: row 026 (Ramesh
# Gupta, depositor "meera iyer") is paid off and archived, so
# `get_all_active` -- active loans only -- excludes it, which is why
# "meera iyer" is 3 or here rather than 4 (016, 018, 021 -- 026 is inactive).
CHECKPOINTS: tuple[tuple[str, str, int], ...] = (
    ("borrower_group", "bg3", 2),
    ("depositor_group", "dg3", 4),
    ("borrower_group", "bg1", 2),
    ("borrower_group", "sharma group", 4),
    ("borrower_group", "iyer chem", 2),
    ("depositor_name", "meera iyer", 3),
)
