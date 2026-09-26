"""Unit tests for loan_manager.application.agent.tools.read_portfolio (KCH-237)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from loan_manager.application.agent.tools.read_portfolio import GetPortfolioSummaryTool
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans

from .conftest import make_loan, uow_factory_for

_TODAY = date(2026, 6, 1)


@dataclass(frozen=True)
class _Args:
    limit: int


def _build_tool(loans):
    clock = FixedClock(_TODAY)
    get_all_loans = GetAllLoans(uow_factory_for(loans), clock=clock)
    return GetPortfolioSummaryTool(get_all_loans, clock)


def _sample_loans():
    # "big" has one loan of 10000; "small" has two loans (4000 + 5000 =
    # 9000). A naive string/lexicographic sort of the raw per-loan amounts
    # ("10000" < "9000" as strings, since '1' < '9') would rank "small"
    # first; the correct numeric sum must rank "big" (10000) ahead of
    # "small" (9000).
    #
    # "small"'s loans are listed BEFORE "big"'s on purpose: a mutant that
    # limits before ranking (`rank_by_amount(aggregates[:limit])`, keeping
    # insertion order) would then rank "small" first too, by accident,
    # since dict-grouping preserves insertion order -- the correct
    # behaviour (rank first, THEN limit) is the only way "big" ends up
    # first regardless of which borrower was seen first.
    return [
        make_loan(
            borrower_name="small", borrower_group="bg", amount=4000,
            giving_date=date(2026, 1, 1), due_date=date(2026, 12, 31),
        ),
        make_loan(
            borrower_name="small", borrower_group="bg", amount=5000,
            giving_date=date(2026, 1, 1), due_date=date(2026, 12, 31),
        ),
        make_loan(
            borrower_name="big", borrower_group="bg", amount=10000,
            giving_date=date(2026, 1, 1), due_date=date(2026, 12, 31),
        ),
        # Not yet given (giving_date in the future) -> computed PENDING,
        # excluded from exposure entirely despite the largest amount.
        make_loan(
            borrower_name="future", borrower_group="bg", amount=999999,
            giving_date=date(2027, 1, 1), due_date=date(2027, 12, 31),
        ),
    ]


def test_ranks_borrowers_by_summed_exposure_numerically() -> None:
    tool = _build_tool(_sample_loans())
    result = tool.execute(_Args(limit=10))
    names = [row["borrower_name"] for row in result["top"]]
    assert names[:2] == ["big", "small"]
    assert result["top"][0]["exposure"] == "10000.00"
    assert result["top"][1]["exposure"] == "9000.00"


def test_pending_excluded() -> None:
    tool = _build_tool(_sample_loans())
    result = tool.execute(_Args(limit=10))
    names = [row["borrower_name"] for row in result["top"]]
    assert "future" not in names
    assert result["borrower_count"] == 2
    assert result["total_exposure"] == "19000.00"


def test_limit_applied_after_ranking() -> None:
    tool = _build_tool(_sample_loans())
    result = tool.execute(_Args(limit=1))
    assert len(result["top"]) == 1
    # "small" is inserted first (see _sample_loans) but "big" has the larger
    # exposure -- a limit-BEFORE-ranking mutant would keep "small" here.
    assert result["top"][0]["borrower_name"] == "big"
    # borrower_count and total_exposure reflect the WHOLE ranked set, not
    # the limited slice.
    assert result["borrower_count"] == 2
    assert result["total_exposure"] == "19000.00"
    assert result["top"][0]["rank"] == 1


def test_overdue_and_undated_loans_counted_in_exposure() -> None:
    """OVERDUE loans -- dated and undated alike -- are outstanding exposure
    just as much as ACTIVE ones; only PENDING is excluded. A mutant that
    narrowed `_EXPOSURE_STATUSES` to `(ACTIVE,)` would silently drop both."""
    dated_overdue = make_loan(
        borrower_name="od", borrower_group="bg", amount=7000,
        giving_date=date(2026, 1, 1), due_date=date(2026, 2, 1),
    )
    undated_overdue = make_loan(
        borrower_name="ud", borrower_group="bg", amount=8000,
        giving_date=date(2026, 1, 1), due_date=None,
    )
    tool = _build_tool([*_sample_loans(), dated_overdue, undated_overdue])

    result = tool.execute(_Args(limit=10))

    names = {row["borrower_name"] for row in result["top"]}
    assert {"od", "ud"} <= names
    assert result["borrower_count"] == 4  # big, small, od, ud (future excluded)
    # 10000 (big) + 9000 (small) + 7000 (od) + 8000 (ud)
    assert result["total_exposure"] == "34000.00"


def test_same_borrower_name_in_two_groups_stays_two_aggregates() -> None:
    """The same borrower name under two different groups is two distinct
    parties in this domain (module docstring) -- grouping by borrower_name
    alone would wrongly merge them into one aggregate."""
    loans = [
        make_loan(
            borrower_name="ravi", borrower_group="g1", amount=5000,
            giving_date=date(2026, 1, 1), due_date=date(2026, 12, 31),
        ),
        make_loan(
            borrower_name="ravi", borrower_group="g2", amount=6000,
            giving_date=date(2026, 1, 1), due_date=date(2026, 12, 31),
        ),
    ]
    tool = _build_tool(loans)

    result = tool.execute(_Args(limit=10))

    assert result["borrower_count"] == 2
    by_group = {row["borrower_group"]: row["exposure"] for row in result["top"]}
    assert by_group == {"g1": "5000.00", "g2": "6000.00"}
