"""KCH-245: pure view-model logic, no Qt import, no QApplication needed."""

from __future__ import annotations

import pytest
from loan_manager.application.dtos.report_dto import ApprovalResultDTO, UndoResultDTO
from loan_manager.domain.value_objects.status import CalculationMode
from loan_manager.presentation.view_models.approval_messages import (
    approve_outcome,
    undo_refusal_text,
)


class TestApproveOutcome:
    def test_inactive_records_are_refused_without_a_proceed_prompt(self):
        result = ApprovalResultDTO(
            success=False,
            inactive_ref_ids=["2026_01_001"],
            requires_confirmation=False,
        )
        kind, text = approve_outcome(result, is_paidoff=False)

        assert kind == "refused"
        assert "2026_01_001" in text
        assert "Proceed" not in text, (
            "an inactive-ref refusal must never offer a Proceed anyway? "
            "choice -- ApproveReport refuses it regardless of force"
        )

    def test_deleted_records_are_listed_as_skipped_on_success(self):
        result = ApprovalResultDTO(
            success=True,
            deleted_ref_ids=["2026_01_009"],
            requires_confirmation=False,
        )
        kind, text = approve_outcome(result, is_paidoff=False)

        assert kind == "done"
        assert "2026_01_009" in text
        assert "skipped" in text.lower()

    def test_confirm_lists_duplicates_and_deleted(self):
        result = ApprovalResultDTO(
            success=False,
            duplicate_ref_ids=["2026_01_001"],
            deleted_ref_ids=["2026_01_002"],
            requires_confirmation=True,
        )
        kind, text = approve_outcome(result, is_paidoff=False)

        assert kind == "confirm"
        assert "2026_01_001" in text
        assert "2026_01_002" in text
        assert "Proceed anyway" in text

    def test_confirm_includes_paidoff_note(self):
        result = ApprovalResultDTO(
            success=False, duplicate_ref_ids=["2026_01_001"], requires_confirmation=True,
        )
        kind, text = approve_outcome(result, is_paidoff=True)
        assert kind == "confirm"
        assert "Paidoff" in text
        assert "history" in text

    def test_unsuccessful_and_not_confirming_is_not_silent(self):
        """This is ApproveReport's idempotency-guard shape: success=False,
        requires_confirmation=False, every ref-id list empty. The old tab's
        `if result.success:` branch silently did nothing for this case --
        the caller must be told, not left to guess."""
        result = ApprovalResultDTO(success=False, requires_confirmation=False)
        kind, text = approve_outcome(result, is_paidoff=False)

        assert kind == "not_pending"
        assert text
        assert "no longer pending" in text.lower()

    def test_success_without_extras_still_says_approved(self):
        result = ApprovalResultDTO(success=True)
        kind, text = approve_outcome(result, is_paidoff=False)
        assert kind == "done"
        assert "approved" in text.lower()

    def test_inactive_takes_priority_over_duplicates(self):
        """KCH-245 review cycle 1, R18: ApproveReport computes duplicates
        BEFORE the inactive-UPDATE check and returns them in the SAME DTO
        when it refuses for inactive_ref_ids (approve_report.py) -- a
        report can reach here with BOTH sets non-empty. inactive_ref_ids
        must still win: the message must refuse, and must never offer the
        duplicates' "Proceed anyway?" (which the use case does not honour
        for this refusal regardless of `force`)."""
        result = ApprovalResultDTO(
            success=False,
            inactive_ref_ids=["2026_01_001"],
            duplicate_ref_ids=["2026_01_002"],
            requires_confirmation=False,
        )
        kind, text = approve_outcome(result, is_paidoff=False)

        assert kind == "refused"
        assert "Proceed" not in text


class TestUndoRefusalText:
    @pytest.mark.parametrize(
        "reason,must_contain",
        [
            ("not_approved", "not currently Approved"),
            ("paidoff_not_undoable", "Paidoff report cannot be undone"),
            ("unrecognized_report_mode", "not one this version knows how to undo"),
        ],
    )
    def test_known_reasons(self, reason, must_contain):
        result = UndoResultDTO(success=False, reason=reason)
        text = undo_refusal_text(result)
        assert must_contain in text

    def test_changed_since_approval_includes_conflict_refs(self):
        result = UndoResultDTO(
            success=False, reason="changed_since_approval",
            conflict_ref_ids=["2026_01_001", "2026_01_002"],
        )
        text = undo_refusal_text(result)
        assert "2026_01_001" in text
        assert "2026_01_002" in text
        assert "changed since" in text.lower()

    def test_unknown_reason_gets_a_generic_message_not_a_crash(self):
        result = UndoResultDTO(success=False, reason="some_future_reason")
        text = undo_refusal_text(result)
        assert "some_future_reason" in text
        assert "Undo failed" in text

    def test_update_mode_gets_specific_wording_not_the_version_bug_message(self):
        """KCH-245 review cycle 1, m2: UndoApprovedReport returns
        "unrecognized_report_mode" for UPDATE BY DESIGN (plan: "UPDATE
        always"), never because this version doesn't know the mode. The
        generic wording reads like a bug; UPDATE gets the true one."""
        result = UndoResultDTO(success=False, reason="unrecognized_report_mode")
        text = undo_refusal_text(result, report_mode=CalculationMode.UPDATE)

        assert "no before-values are stored" in text
        assert "not one this version knows how to undo" not in text

    def test_a_genuinely_unknown_mode_keeps_the_generic_wording(self):
        """Negative control: passing a report_mode that ISN'T UPDATE must
        not accidentally trip the UPDATE-specific wording -- proves the
        branch is keyed on the mode, not merely on the reason string."""
        result = UndoResultDTO(success=False, reason="unrecognized_report_mode")
        text = undo_refusal_text(result, report_mode=CalculationMode.MONTHLY)

        assert text == "This report's mode is not one this version knows how to undo."
