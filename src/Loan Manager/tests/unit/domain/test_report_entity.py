"""Report/ReportRecord entity unit tests (KCH-242).

`Report.__post_init__` is the single place the CREATE row convention is
enforced: a CREATE-mode proposal names a borrower who has no loan yet, so it
carries the OPPOSITE set of required fields to every other mode (which
describes an EXISTING loan). Getting this backwards -- e.g. requiring
`giving_date` on a CREATE record, or letting a Pending CREATE record already
carry a `reference_id` -- would either reject every legitimate agent
proposal or let one slip through with a reference_id nothing minted.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from loan_manager.domain.entities.report import Report, ReportRecord
from loan_manager.domain.value_objects.report_id import ReportId
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    ReportActor,
    ReportStatus,
)

_NOW = datetime(2026, 3, 15, 12, 0, 0)


def _record(**overrides) -> ReportRecord:
    fields = dict(
        id=None,
        report_id="RPT_20260315_001",
        reference_id="2026_03_001",
        borrower_name="borrower",
        depositor_name="depositor",
        depositor_group=None,
        amount=10000,
        giving_date=date(2026, 1, 1),
        due_date=date(2026, 4, 1),
        extension_period=3,
        extension_period_unit=ExtensionPeriodUnit.MONTHS,
        interest_rate=Decimal("12"),
        commission_rate=Decimal("6"),
        tds_flag=False,
        interest_amount=None,
        commission_amount=None,
        tds_amount=None,
        chq_amount=None,
        post_extension_giving_date=None,
        post_extension_due_date=None,
        paidoff_date=None,
    )
    fields.update(overrides)
    return ReportRecord(**fields)


def _report(mode: CalculationMode, records: list[ReportRecord], **overrides) -> Report:
    fields = dict(
        id=None,
        report_id=ReportId("RPT_20260315_001"),
        report_mode=mode,
        status=ReportStatus.PENDING,
        records=records,
        created_at=_NOW,
        updated_at=_NOW,
    )
    fields.update(overrides)
    return Report(**fields)


class TestNonCreateModeRequiresReferenceIdAndGivingDate:
    def test_extend_mode_with_reference_id_and_giving_date_is_valid(self):
        _report(CalculationMode.MONTHLY, [_record()])  # must not raise

    def test_extend_mode_without_reference_id_raises(self):
        with pytest.raises(ValueError, match="reference_id and giving_date"):
            _report(CalculationMode.MONTHLY, [_record(reference_id=None)])

    def test_paidoff_mode_without_giving_date_raises(self):
        with pytest.raises(ValueError, match="reference_id and giving_date"):
            _report(CalculationMode.PAIDOFF, [_record(giving_date=None)])


class TestCreateModeRequiresBorrowerGroupAndProposedGivingDate:
    def test_create_mode_pending_with_no_reference_id_is_valid(self):
        _report(
            CalculationMode.CREATE,
            [
                _record(
                    reference_id=None,
                    giving_date=None,
                    due_date=None,
                    borrower_group="new-group",
                    post_extension_giving_date=date(2026, 4, 1),
                    post_extension_due_date=date(2026, 7, 1),
                )
            ],
        )  # must not raise

    def test_create_mode_without_borrower_group_raises(self):
        with pytest.raises(ValueError, match="borrower_group"):
            _report(
                CalculationMode.CREATE,
                [
                    _record(
                        reference_id=None,
                        giving_date=None,
                        borrower_group=None,
                        post_extension_giving_date=date(2026, 4, 1),
                    )
                ],
            )

    def test_create_mode_without_proposed_giving_date_raises(self):
        with pytest.raises(ValueError, match="post_extension_giving_date"):
            _report(
                CalculationMode.CREATE,
                [
                    _record(
                        reference_id=None,
                        giving_date=None,
                        borrower_group="new-group",
                        post_extension_giving_date=None,
                    )
                ],
            )

    def test_create_mode_pending_record_with_reference_id_already_set_raises(self):
        """A CREATE record only gets a reference_id once ApproveReport mints
        a loan for it -- one showing up on a still-Pending report is a bug
        (e.g. a stale read, or the wrong record reused), not a valid state.
        """
        with pytest.raises(ValueError, match="reference_id=None"):
            _report(
                CalculationMode.CREATE,
                [
                    _record(
                        reference_id="2026_03_001",  # not allowed while Pending
                        giving_date=None,
                        borrower_group="new-group",
                        post_extension_giving_date=date(2026, 4, 1),
                    )
                ],
            )

    def test_create_mode_approved_record_may_carry_a_reference_id(self):
        """Once approved, the record legitimately carries the reference_id
        ApproveReport assigned -- only the Pending state forbids it."""
        _report(
            CalculationMode.CREATE,
            [
                _record(
                    reference_id="2026_03_001",
                    giving_date=None,
                    borrower_group="new-group",
                    post_extension_giving_date=date(2026, 4, 1),
                )
            ],
            status=ReportStatus.APPROVED,
        )  # must not raise


class TestReportDefaultsAndAppendedFields:
    def test_report_defaults_to_form_actor_with_no_user_request_or_turn_id(self):
        report = _report(CalculationMode.MONTHLY, [_record()])
        assert report.actor == ReportActor.FORM
        assert report.user_request is None
        assert report.turn_id is None

    def test_agent_report_carries_actor_user_request_and_turn_id(self):
        report = _report(
            CalculationMode.MONTHLY,
            [_record()],
            actor=ReportActor.AGENT,
            user_request="extend the loan for ravindra",
            turn_id="turn-123",
        )
        assert report.actor == ReportActor.AGENT
        assert report.user_request == "extend the loan for ravindra"
        assert report.turn_id == "turn-123"

    def test_report_record_defaults_borrower_group_and_due_period_to_none(self):
        record = _record()
        assert record.borrower_group is None
        assert record.due_period is None

    def test_existing_positional_construction_still_works(self):
        """generate_report.py and mark_paidoff.py build ReportRecord with
        every field they set by keyword already, but the new fields must
        still default correctly when omitted -- this is the behavioural
        contract the plan's positional-construction guarantee protects."""
        record = ReportRecord(
            None, "RPT_20260315_001", "2026_03_001", "borrower", "depositor", None,
            10000, date(2026, 1, 1), date(2026, 4, 1), 3, ExtensionPeriodUnit.MONTHS,
            Decimal("12"), Decimal("6"), False, None, None, None, None, None, None, None,
        )
        assert record.borrower_group is None
        assert record.due_period is None
