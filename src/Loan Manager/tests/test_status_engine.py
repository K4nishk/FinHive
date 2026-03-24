"""
Tests for status_engine.compute_status() and status_engine.recompute_all().

Today (frozen for all tests) = 2026-03-22.

Status rules (from R3 and R7):
  Pending  : giving_date > today
  Active   : giving_date <= today < due_date
  Overdue  : due_date <= today
  Overdue  : no due_date AND giving_date <= today  (R7)
  Pending  : no due_date AND giving_date > today   (R7 inferred)
  Paidoff  : never auto-recomputed (stays Paidoff)

[REVIEW REQUIRED] - due_date == today boundary:
  R3 states Overdue when "due_date <= today".
  The test below treats due_date == today as Overdue.
  Confirm with product owner before finalising.
"""

import pytest
from datetime import date
from typing import Optional

from loan_manager.status_engine import compute_status, recompute_all  # type: ignore[import]

TODAY: date = date(2026, 3, 22)


# ---------------------------------------------------------------------------
# compute_status – single record
# ---------------------------------------------------------------------------

class TestComputeStatusActive:
    def test_compute_status_future_due_date_returns_active(self) -> None:
        result = compute_status(
            giving_date=date(2026, 1, 2),
            due_date=date(2026, 4, 2),
            current_status="Active",
            today=TODAY,
        )
        assert result == "Active"

    def test_compute_status_giving_equals_today_future_due_date_returns_active(self) -> None:
        result = compute_status(
            giving_date=TODAY,
            due_date=date(2026, 4, 1),
            current_status="Active",
            today=TODAY,
        )
        assert result == "Active"

    @pytest.mark.parametrize(
        "ref_id,giving,due",
        [
            ("2026_01_001", date(2026, 1, 2),  date(2026, 4, 2)),
            ("2026_01_002", date(2026, 1, 4),  date(2026, 5, 4)),
            ("2026_02_001", date(2026, 2, 6),  date(2026, 5, 6)),
            ("2026_02_002", date(2026, 2, 7),  date(2026, 6, 7)),
            ("2026_02_003", date(2026, 2, 8),  date(2026, 6, 8)),
            ("2026_02_004", date(2026, 2, 8),  date(2026, 7, 8)),
            ("2026_02_005", date(2026, 2, 15), date(2026, 7, 15)),
            ("2026_02_006", date(2026, 2, 18), date(2026, 6, 18)),
            ("2026_02_007", date(2026, 2, 20), date(2026, 6, 20)),
            ("2026_02_008", date(2026, 2, 25), date(2026, 5, 25)),
            ("2026_02_009", date(2026, 2, 28), date(2026, 5, 28)),
            ("2026_03_001", date(2026, 3, 2),  date(2026, 7, 2)),
            ("2026_03_002", date(2026, 3, 5),  date(2026, 7, 5)),
        ],
    )
    def test_compute_status_sample_active_loans_return_active(
        self,
        ref_id: str,
        giving: date,
        due: date,
    ) -> None:
        """All b1-b13 sample records should remain Active on 2026-03-22."""
        result = compute_status(
            giving_date=giving,
            due_date=due,
            current_status="Active",
            today=TODAY,
        )
        assert result == "Active", f"{ref_id}: expected Active, got {result}"


class TestComputeStatusOverdue:
    def test_compute_status_past_due_date_returns_overdue(self) -> None:
        result = compute_status(
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 3, 1),
            current_status="Active",
            today=TODAY,
        )
        assert result == "Overdue"

    def test_compute_status_due_date_yesterday_returns_overdue(self) -> None:
        result = compute_status(
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 3, 21),
            current_status="Active",
            today=TODAY,
        )
        assert result == "Overdue"

    # [REVIEW REQUIRED] - due_date == today treated as Overdue per R3 ("due_date <= today")
    def test_compute_status_due_date_equals_today_returns_overdue(self) -> None:
        result = compute_status(
            giving_date=date(2026, 1, 1),
            due_date=TODAY,
            current_status="Active",
            today=TODAY,
        )
        assert result == "Overdue"


class TestComputeStatusPending:
    def test_compute_status_future_giving_date_returns_pending(self) -> None:
        result = compute_status(
            giving_date=date(2026, 4, 1),
            due_date=date(2026, 7, 1),
            current_status="Active",
            today=TODAY,
        )
        assert result == "Pending"

    def test_compute_status_giving_date_tomorrow_returns_pending(self) -> None:
        result = compute_status(
            giving_date=date(2026, 3, 23),
            due_date=date(2026, 6, 23),
            current_status="Active",
            today=TODAY,
        )
        assert result == "Pending"

    def test_compute_status_giving_far_future_no_due_date_returns_pending(self) -> None:
        """No due_date + future giving_date → Pending (R7 inferred)."""
        result = compute_status(
            giving_date=date(2026, 4, 1),
            due_date=None,
            current_status="Active",
            today=TODAY,
        )
        assert result == "Pending"


class TestComputeStatusNoDueDate:
    def test_compute_status_no_due_date_past_giving_date_returns_overdue(self) -> None:
        """R7: a loan with no due_date is Overdue when giving_date <= today."""
        result = compute_status(
            giving_date=date(2026, 1, 1),
            due_date=None,
            current_status="Active",
            today=TODAY,
        )
        assert result == "Overdue"

    def test_compute_status_no_due_date_giving_equals_today_returns_overdue(self) -> None:
        """R7: no due_date, giving_date == today → Overdue."""
        result = compute_status(
            giving_date=TODAY,
            due_date=None,
            current_status="Active",
            today=TODAY,
        )
        assert result == "Overdue"

    def test_compute_status_no_due_date_future_giving_returns_pending(self) -> None:
        """R7 inferred: no due_date, giving_date > today → Pending."""
        result = compute_status(
            giving_date=date(2026, 5, 1),
            due_date=None,
            current_status="Active",
            today=TODAY,
        )
        assert result == "Pending"


class TestComputeStatusPaidoff:
    def test_compute_status_paidoff_not_recomputed_even_if_overdue_by_date(self) -> None:
        """Paidoff records are never auto-recomputed regardless of dates."""
        result = compute_status(
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 2, 1),
            current_status="Paidoff",
            today=TODAY,
        )
        assert result == "Paidoff"

    def test_compute_status_paidoff_not_recomputed_even_if_future_due_date(self) -> None:
        result = compute_status(
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 12, 31),
            current_status="Paidoff",
            today=TODAY,
        )
        assert result == "Paidoff"

    def test_compute_status_paidoff_not_recomputed_with_no_due_date(self) -> None:
        result = compute_status(
            giving_date=date(2026, 1, 1),
            due_date=None,
            current_status="Paidoff",
            today=TODAY,
        )
        assert result == "Paidoff"


# ---------------------------------------------------------------------------
# recompute_all – batch update
# ---------------------------------------------------------------------------

class TestRecomputeAll:
    def _make_loan(
        self,
        reference_id: str,
        giving_date: date,
        due_date: Optional[date],
        status: str = "Active",
    ) -> dict:
        return {
            "reference_id": reference_id,
            "giving_date": giving_date,
            "due_date": due_date,
            "status": status,
        }

    def test_recompute_all_returns_same_count(self) -> None:
        loans = [
            self._make_loan("2026_01_001", date(2026, 1, 1), date(2026, 4, 1)),
            self._make_loan("2026_02_001", date(2026, 2, 1), date(2026, 5, 1)),
        ]
        result = recompute_all(loans, today=TODAY)
        assert len(result) == 2

    def test_recompute_all_updates_overdue_record(self) -> None:
        loans = [
            self._make_loan("2026_01_001", date(2026, 1, 1), date(2026, 2, 1), status="Active"),
        ]
        result = recompute_all(loans, today=TODAY)
        assert result[0]["status"] == "Overdue"

    def test_recompute_all_updates_pending_record(self) -> None:
        loans = [
            self._make_loan("2026_04_001", date(2026, 4, 1), date(2026, 7, 1), status="Active"),
        ]
        result = recompute_all(loans, today=TODAY)
        assert result[0]["status"] == "Pending"

    def test_recompute_all_preserves_paidoff_status(self) -> None:
        loans = [
            self._make_loan("2026_01_001", date(2026, 1, 1), date(2026, 2, 1), status="Paidoff"),
        ]
        result = recompute_all(loans, today=TODAY)
        assert result[0]["status"] == "Paidoff"

    def test_recompute_all_does_not_mutate_original_list(self) -> None:
        loans = [
            self._make_loan("2026_01_001", date(2026, 1, 1), date(2026, 2, 1), status="Active"),
        ]
        original_status = loans[0]["status"]
        recompute_all(loans, today=TODAY)
        assert loans[0]["status"] == original_status

    def test_recompute_all_mixed_statuses(self) -> None:
        loans = [
            self._make_loan("2026_01_001", date(2026, 1, 1), date(2026, 2, 1)),   # Overdue
            self._make_loan("2026_02_001", date(2026, 2, 1), date(2026, 5, 1)),   # Active
            self._make_loan("2026_04_001", date(2026, 4, 1), date(2026, 7, 1)),   # Pending
            self._make_loan("2026_01_002", date(2026, 1, 1), date(2026, 2, 1), "Paidoff"),
            self._make_loan("2026_01_003", date(2026, 1, 1), None),               # Overdue (R7)
        ]
        result = recompute_all(loans, today=TODAY)
        statuses = {r["reference_id"]: r["status"] for r in result}
        assert statuses["2026_01_001"] == "Overdue"
        assert statuses["2026_02_001"] == "Active"
        assert statuses["2026_04_001"] == "Pending"
        assert statuses["2026_01_002"] == "Paidoff"
        assert statuses["2026_01_003"] == "Overdue"

    def test_recompute_all_empty_list_returns_empty(self) -> None:
        result = recompute_all([], today=TODAY)
        assert result == []

    def test_recompute_all_sample_loans_all_active(self, sample_loans: list[tuple]) -> None:
        """All 15 sample records should result in Active status on 2026-03-22
        because all due_dates are in the future (b14, b15 have due_dates too)."""
        loans = [
            {
                "reference_id": row[0],
                "giving_date": row[4],
                "due_date": row[7],
                "status": row[8],
            }
            for row in sample_loans
        ]
        result = recompute_all(loans, today=TODAY)
        for record in result:
            assert record["status"] == "Active", (
                f"{record['reference_id']} expected Active, got {record['status']}"
            )
