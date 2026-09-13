# Open Questions — Loan Manager

## OQ-01 — No-Due-Date + No-Filter Calculator Behaviour
**Question**: When no filter is applied, calculator shows records with no due_date. When a filter IS applied, those records are excluded. But what if the filter matches a record that has no due_date? Is it excluded?
**Current Spec**: "when a filter is applied, the calculator totally excludes the ones without due date"
**Interpretation**: Any filter applied = if a no-due-date record matches the filter, then it is also included. Only excluded in `ByMonth` filter due to no `due_date` value
**Status**: Confirmed.

## OQ-02 — ByMonth Filter + Overdue Records
**Question**: "ByMonth = records whose due_date is in selected month for current calendar year only INCLUDING Overdue records". Does this mean Overdue records from any month are always included when ByMonth is active, or only those whose due_date falls in the selected month?
**Interpretation**: Records whose due_date is in the selected month AND year, regardless of current date (so an Overdue April record shows in the April filter but an Overdue March record does not show up in April filter).
**Status**: Confirmed

## OQ-03 — Paidoff Report + Pending Approval Approval Flow
**Question**: When a Paidoff report is approved, is the `paidoff_date` stored in `history.csv` as a separate column, or embedded in the report record?
**Current Spec**: "`paidoff_date` can be stored for each ReportRecord as a separate column for report mode = Paidoff"
**Interpretation**: `pending_report_records.csv` has a `paidoff_date` column populated only for Paidoff-mode reports. On approval, `history.csv` row includes this date.
**Status**: Confirmed

## OQ-04 — Decline of a Paidoff Report
**Question**: If a Paidoff report is declined, the requirement says "older values are retained in the original view." Does the loan record go back to its pre-Paidoff-request status (e.g., Overdue) automatically?
**Interpretation**: Yes — loan stays visible in View Tab with its last computed status (Active/Overdue based on dates). No state change occurs.
**Status**: Confirmed

## OQ-05 — Both Mode: What happens if global extension_period_unit changes after per-record edits?
**Question**: In Both mode, user can override per-record extension_period_unit. If the global value changes, does it overwrite the per-record unit too?
**Current Spec**: "When the global header values change, the system overwrites all rows (including manually-edited rows)"
**Interpretation**: Yes — any global change resets all rows to global defaults, including unit in Both mode.
**Status**: Confirmed

## OQ-06 — Print / PDF Output Format
**Question**: Approved reports can be "downloaded as PDF or printed." Is the print layout the same as the report format specified (per-borrower breakdown)?
**Interpretation**: Yes, follow the defined report format per borrower. System print dialog handles PDF generation on macOS natively; Windows requires PDF printer.
**Status**: Confirmed

## OQ-07 — Loans_meta.csv Structure
**Question**: What exactly does `loans_meta.csv` contain? One row per YYYY_MM with last counter value?
**Interpretation**: `loans_meta.csv` has columns `[year_month, last_order]` — one row per active YYYY_MM period.
**Status**: Confirmed

## OQ-08 — Status After Extend
**Question**: After extending a loan, what is the new status? Is it recomputed immediately (Active if new giving_date <= today < new due_date)?
**Interpretation**: Yes — status is recomputed immediately after Extend using the new dates.
**Status**: Confirmed.

## OQ-09 — Theme Preferences
**Question**: User wants multiple themes. Any specific preference for light/dark or colour palette beyond the status colours already specified?
**Status**: [REVIEW REQUIRED — awaiting user preference after prototype demo]

## OQ-10 — Report ID Counter Reset
**Question**: Does the report_id order counter reset daily (since it includes date `RPT_YYYYMMDD_<order>`) or persist across days?
**Interpretation**: Counter resets per date — i.e., each new calendar day starts at 001. If `RPT_20260320_001` exists from a previous day, the next day's first report is `RPT_20260321_001`.
**Status**: Confirmed.
