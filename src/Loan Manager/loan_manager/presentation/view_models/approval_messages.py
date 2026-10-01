"""Pure text/decision helpers for the approvals tab (KCH-245).

No Qt import here on purpose: `pending_approval_tab.py` decides what to DO
with a `(kind, text)` pair (which dialog, which buttons); this module only
decides WHAT the outcome means and WHAT to say about it, so that logic is
testable without a QApplication.
"""

from __future__ import annotations

from loan_manager.application.dtos.report_dto import ApprovalResultDTO, UndoResultDTO
from loan_manager.domain.value_objects.status import CalculationMode

# approve_outcome's `kind`:
#   "refused"     -- inactive_ref_ids present; ApproveReport refuses this
#                    REGARDLESS of `force` (approve_report.py), so the text
#                    never offers "Proceed anyway?".
#   "confirm"     -- first call hit a duplicate/deleted-ref warning; the tab
#                    must ask before retrying with force=True.
#   "done"        -- the approval succeeded.
#   "not_pending" -- ApproveReport's idempotency guard: the report was
#                    already Approved/Declined/Reverted (double-click, stale
#                    selection). Nothing to confirm -- just refresh.


def approve_outcome(result: ApprovalResultDTO, is_paidoff: bool) -> tuple[str, str]:
    if result.inactive_ref_ids:
        text = (
            "These records cannot be approved: the loan has been paid off "
            "or archived since this report was proposed -- "
            f"{', '.join(result.inactive_ref_ids)}."
        )
        return "refused", text

    if result.success:
        parts: list[str] = []
        if is_paidoff:
            parts.append(
                "This report was generated for a Paidoff loan. The loan "
                "will be moved to history. No extension will be applied."
            )
        if result.deleted_ref_ids:
            parts.append(
                "Records for these deleted loans were skipped: "
                f"{', '.join(result.deleted_ref_ids)}."
            )
        parts.append("Report approved.")
        return "done", "\n\n".join(parts)

    if result.requires_confirmation:
        parts = []
        if result.duplicate_ref_ids:
            parts.append(
                "This report shares loan records with another pending "
                "report. Approving may overwrite previous updates: "
                f"{', '.join(result.duplicate_ref_ids)}."
            )
        if result.deleted_ref_ids:
            parts.append(
                "Records for these deleted loans will be skipped: "
                f"{', '.join(result.deleted_ref_ids)}."
            )
        if is_paidoff:
            parts.append(
                "This report was generated for a Paidoff loan. The loan "
                "will be moved to history. No extension will be applied."
            )
        parts.append("Proceed anyway?")
        return "confirm", "\n\n".join(parts)

    # success=False, requires_confirmation=False, nothing else set: the only
    # path in ApproveReport that shapes a DTO this way is the PENDING-status
    # idempotency guard.
    return "not_pending", (
        "This report is no longer pending -- it may already have been "
        "approved, declined or undone. The list will refresh."
    )


# UndoApprovedReport's UndoResultDTO.reason values, per its own docstring:
# "not_approved", "paidoff_not_undoable", "changed_since_approval" (+
# conflict_ref_ids), "unrecognized_report_mode". A reason outside that set
# means a future mode this UI has not been taught about yet -- shown
# generically rather than silently blank.


def undo_refusal_text(
    result: UndoResultDTO, report_mode: CalculationMode | None = None
) -> str:
    reason = result.reason
    if reason == "not_approved":
        return "This report is not currently Approved, so it cannot be undone."
    if reason == "paidoff_not_undoable":
        return (
            "A Paidoff report cannot be undone: the loan was already "
            "archived to history."
        )
    if reason == "changed_since_approval":
        refs = (
            ", ".join(result.conflict_ref_ids)
            if result.conflict_ref_ids else "the affected records"
        )
        return f"This report cannot be undone: it has changed since approval ({refs})."
    if reason == "unrecognized_report_mode":
        # KCH-245 review cycle 1, m2: UPDATE is a KNOWN mode -- UndoApprovedReport
        # returns this same reason for it BY DESIGN (plan: "UPDATE always"),
        # never because this version doesn't recognise it. The generic
        # wording below reads like a version bug for UPDATE specifically, so
        # it gets its own, true message; any OTHER mode this UI has not been
        # taught to restore keeps the generic text.
        if report_mode == CalculationMode.UPDATE:
            return (
                "Edit (UPDATE) reports can't be undone: no before-values "
                "are stored. Nothing was changed."
            )
        return "This report's mode is not one this version knows how to undo."
    return f"Undo failed: {reason or 'unknown reason'}."
