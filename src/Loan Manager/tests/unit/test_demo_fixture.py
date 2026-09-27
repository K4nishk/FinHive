"""`infrastructure/seed/demo_fixture.py` data integrity (KCH-231).

Pure-data tests -- no DB, no key ring. `test_demo_seed.py` (integration)
covers what happens once these rows go through the encrypting repository.
"""

from __future__ import annotations

from datetime import date

from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.infrastructure.seed.demo_fixture import (
    CHECKPOINTS,
    DEMO_LOANS,
    FIXTURE_TODAY,
)

from tests.fixtures.sample_data import SAMPLE_LOANS


def test_first_15_rows_equal_sample_data() -> None:
    """Drift trip-wire: the first 15 `DEMO_LOANS` rows must stay identical to
    `tests/fixtures/sample_data.SAMPLE_LOANS` -- same fields, same order --
    since `test_filter_logic.py`'s own checkpoints (bg3->2, dg3->4, ...) are
    counted against that file, not this one, and the two are meant to be one
    dataset, not two that can silently diverge.
    """
    first_15 = DEMO_LOANS[:15]
    assert len(first_15) == len(SAMPLE_LOANS) == 15

    for fixture, sample in zip(first_15, SAMPLE_LOANS, strict=True):
        assert fixture.borrower_name == sample["borrower_name"]
        assert fixture.borrower_group == sample["borrower_group"]
        assert fixture.depositor_name == sample["depositor_name"]
        assert fixture.depositor_group == sample.get("depositor_group")
        assert fixture.amount == sample["amount"]
        assert fixture.giving_date == sample["giving_date"]
        assert fixture.due_date == sample.get("due_date")
        assert fixture.due_period is None
        assert fixture.paidoff_date is None


def test_demo_loans_has_27_rows() -> None:
    assert len(DEMO_LOANS) == 27


def test_refs_unique_and_valid() -> None:
    refs = [loan.ref for loan in DEMO_LOANS]

    assert len(refs) == len(set(refs)), f"duplicate reference_id(s) in DEMO_LOANS: {refs}"
    for ref in refs:
        # Raises ValueError on a malformed ref (ReferenceId.__post_init__) --
        # this is the assertion, not a precondition.
        ReferenceId(ref)


def test_trap_rows_present() -> None:
    """Guards the specific rows the checkpoints in `CHECKPOINTS` depend on
    existing with EXACT values -- an edit to any one of these (e.g. rounding
    an amount, or "bg10" -> "bg1") would leave `test_demo_seed.py`'s
    `checkpoints_reproduce` silently counting the wrong thing rather than
    failing loudly here, next to the data.
    """
    by_borrower = {loan.borrower_name: loan for loan in DEMO_LOANS}

    # "bg10"/"bg13" deliberately share the "bg1"/"bg1x" prefix that broke
    # `ilike('%bg1%')` pre-encryption (test_filter_logic.py) -- blind-index
    # exact match must not conflate them with "bg1".
    assert by_borrower["b16"].borrower_group == "bg10"
    assert by_borrower["b16"].amount == 10000
    assert by_borrower["b17"].borrower_group == "bg13"

    # "meera iyer" (a depositor) vs "iyer chem" (a borrower group) share the
    # substring "iyer" -- CHECKPOINTS' depositor_name/borrower_group counts
    # must not bleed into each other.
    assert by_borrower["suresh iyer"].borrower_group == "iyer chem"
    assert by_borrower["rakesh sharma"].depositor_name == "meera iyer"

    # Undated loan (G-07): StatusEngine's due_date-is-None branch, not a
    # missing field.
    undated = by_borrower["deepak menon"]
    assert undated.due_date is None
    assert undated.giving_date == date(2026, 6, 15)

    # Future-giving loan: must compute Pending, not Active/Overdue.
    future = by_borrower["pooja verma"]
    assert future.giving_date > FIXTURE_TODAY

    # Paid-off loan: the only row demo_seed.seed() archives + deactivates.
    paidoff = by_borrower["ramesh gupta"]
    assert paidoff.paidoff_date == date(2026, 7, 12)
    assert sum(1 for loan in DEMO_LOANS if loan.paidoff_date is not None) == 1


def test_checkpoints_match_active_rows_in_the_fixture() -> None:
    """Cross-check `CHECKPOINTS` against `DEMO_LOANS` directly (excluding the
    one paid-off row, which `ILoanRepository.get_all_active` never returns),
    independent of the DB round-trip `test_demo_seed.py` covers. Catches a
    hand-edited count in `CHECKPOINTS` itself.
    """
    active = [loan for loan in DEMO_LOANS if loan.paidoff_date is None]

    for field, value, expected in CHECKPOINTS:
        actual = sum(1 for loan in active if getattr(loan, field) == value)
        assert actual == expected, f"{field}={value!r}: expected {expected}, fixture has {actual}"
