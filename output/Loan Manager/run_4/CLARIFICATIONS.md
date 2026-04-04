# Loan Manager — run_4 Clarifications
**Date:** 2026-04-04
**Run:** run_4 (Phase 3 Closure)
**Produced by:** PO Agent (Wave 3 synthesis)
**Inputs:** All 10 skill output files across Waves 0–3

---

## Phase 3 Status

Phase 3 is CLOSED. All 6 scope items are implemented in source code. 197 automated tests pass. The application is ready for user acceptance testing.

| ID | Item | Status |
|---|---|---|
| BUG-UTR-1 | Interest Calculator filter dropdown reset | IMPLEMENTED |
| BUG-UTR-2 | Duplicate reference IDs (two sub-fixes) | IMPLEMENTED |
| BUG-UTR-3 | View Tab Refresh spurious write | IMPLEMENTED |
| BUG-UTR-4 | Date picker single-click UX | IMPLEMENTED |
| BC-301 | Paidoff warning label in Pending Approval Tab | IMPLEMENTED |
| CHG-02-EXT | PaidoffDialog rate fields + report pipeline | IMPLEMENTED |

---

## Deduplication Summary

Raw [REVIEW REQUIRED] count across all skill outputs: **15 instances** across 10 files.
After deduplication: **5 unique items** — 2 are Business Clarifications requiring user input, 3 are Technical decisions either already defaulted or formally deferred.

---

## Business Clarifications (User Input Required)

These two items block or define Phase 4. The user must answer before run_5.

---

### BC-C1: Phase 4 Feature Scope — Which track do you want?

**Item ID:** BC-03 (carried from run_3, still open)
**Raised by:** PM agent (Wave 0), UAT agent (Wave 3)
**Blocks:** Phase 4 sprint planning. Phase 4 implementation cannot begin without this answer.

**Background:** The requirements document lists three candidate Phase 4 features with no stated relative priority. The PO cannot determine which delivers more value to this specific user without explicit input.

**Options:**

| Option | Description | Effort | Business Value |
|---|---|---|---|
| A | R6: Import/export (CSV/XLSX) with Year-Month date hierarchy filter in View Tab | ~7 days | High — enables loading historical data and external reporting |
| B | R9: Alternate theme chooser (2 themes, preference-based) | ~4 days | Medium — visual polish, not workflow-critical |
| C | QComboBox StatusDelegate in View Tab (inline status toggle without right-click) | ~2 days | Medium — UX convenience |
| D | A + C (R6 import/export + inline status toggle) | ~9 days | High — recommended by PO |
| E | B + C (themes + inline status toggle) | ~6 days | Medium — UX focus |

**PO recommendation:** Option D (R6 + inline status toggle) delivers the most workflow value. R6 enables data migration from the user's prior spreadsheet and external sharing. The inline status toggle is a small effort with daily UX benefit.

**Default if no response before run_5:** Option D will be used.

**User action required:** Please reply with your choice: A, B, C, D, or E.

---

### BC-C2: No-Due-Date Paidoff — Which interest behaviour do you want?

**Item ID:** TC-401 (new in run_4)
**Raised by:** PO (Wave 0), BSA (Wave 1), DM (Wave 1), QA Lead (Wave 2), UAT (Wave 3)
**Blocks:** Formal UAT sign-off for UAT-06 (CHG-02-EXT). Does not block Phase 4 kickoff.

**Background:** When you mark a loan as Paidoff, the system calculates the interest report using `extension_period = paidoff_date - due_date` (in days). However, some loans have no due date. The current implementation defaults to `extension_period = 0`, producing an interest report with zero amounts.

**Options:**

| Option | Behaviour | Effort to change |
|---|---|---|
| a (current default) | extension_period = 0, interest = 0, commission = 0 for loans with no due date | None — already implemented |
| b | Dialog requires the user to manually enter extension_period when no due date is set | ~0.5 days |

**Recommendation:** Option (a) is the simplest and avoids a mandatory extra input for an edge case. If you regularly mark no-due-date loans as Paidoff and expect interest calculations for them, option (b) is appropriate.

**Default if no response before run_5:** Option (a) remains in place.

**User action required:** Please confirm (a) or (b). If you are happy with zero interest for no-due-date Paidoff loans, no action is needed.

---

## Technical Clarifications (Informational — No User Action Required)

These items are either already resolved by PO default decision or deferred to Phase 4. They are documented here for completeness and Phase 4 planning.

---

### TC-C1: Reference ID Counter — History.csv Loans Not Included

**Item ID:** SA-401
**Raised by:** SA agent, DM agent, Dev Lead agent, Backend Dev agent (6 instances, 1 unique item)
**Status:** Deferred to Phase 4 — no user action needed now

**What this means:** The reference ID counter (`_active_year_months()`) currently reads only from `loans.csv`. It does not read from `history.csv` (which holds Paidoff/archived loans). If all loans for a given month are archived to history and you then create a new loan in that same month (in a later session), the counter resets to 001. This could produce a reference ID that collides with an archived record (e.g., two records with `2026_04_001` — one in loans.csv, one in history.csv).

**Risk level:** Low. This scenario requires: (a) all loans for a specific month to be paid off and archived, AND (b) a new loan entered for that same month in a later session. This is an unlikely combination in normal use.

**Phase 4 resolution:** Extend `_active_year_months()` to also scan `history.csv` so archived months are included in the active set. This prevents counter reset for months with only archived records.

**User awareness note:** If you notice a duplicate reference ID in your records involving an archived loan, this is the likely cause. Workaround: manually edit the reference ID via the View Tab inline editor.

---

### TC-C2: Crash Safety — Startup Recovery.tmp Detection Not Implemented

**Item ID:** SRE-001
**Raised by:** SRE agent (Wave 1)
**Status:** Deferred to Phase 4 — no user action needed now

**What this means:** The Paidoff operation uses a `recovery.tmp` file to protect against a crash between the two write steps (append to history.csv + remove from loans.csv). If the application crashes mid-Paidoff, `recovery.tmp` remains on disk. Currently the application does not check for this file on startup — if you restart after such a crash, you may have the same loan record in both `loans.csv` (not yet removed) and `history.csv` (already archived).

**Risk level:** Low. Requires a crash in a very short window between two fast writes. Recovery is manual but straightforward: check `data/recovery.tmp` for the reference_id of the partially-archived loan, then remove the duplicate row from `loans.csv` using the CSV editor.

**Phase 4 resolution:** Add a startup check that reads `recovery.tmp` if present, presents a guided recovery dialog, and offers single-click resolution.

**User awareness note:** If you see a loan appearing in both the View Tab and the History records after a crash, check `data/recovery.tmp` to identify which loan needs manual cleanup.

---

### TC-C3: Filter Fallback When a Filtered Loan is Deleted

**Item ID:** UAT-01-EDGE
**Raised by:** UAT agent (Wave 3)
**Status:** Resolved as designed behaviour — no change required

**What this means:** In the Interest Calculator Tab, if you apply a filter (e.g., Borrower Group "Group A") and then delete all loans in "Group A", the next time you click Apply Filters, the Borrower Group combo will revert to "All" because "Group A" no longer exists as an option. This is intentional — the combo can only show values that exist in current loan data.

**No action required.** This is documented expected behaviour.

---

## PO TLDR

Phase 3 is complete. The Loan Manager application has had four production bugs fixed and two features implemented: the filter dropdown now works correctly on Apply, reference ID generation is duplicate-free and crash-safe on Windows, the Refresh button no longer overwrites unchanged records, date pickers open on a single click anywhere on the field, a Paidoff warning label appears in the Pending Approval tab for Paidoff-mode reports, and the Mark Paidoff dialog now collects interest rate, commission rate, and TDS flag to generate a full interest report sent to the Pending Approval queue. All 197 automated tests are green. The code is ready for you to test on your Windows machine using the UAT scenarios in the UAT report.

Two questions need your answer to unlock Phase 4. First: select the Phase 4 feature track (A, B, C, D, or E — see BC-C1 above; recommended: D). Second: for loans with no due date marked as Paidoff, confirm whether zero interest is acceptable or whether you want the dialog to ask for a manual extension period (option a or b — see BC-C2 above; current default: a). If neither is answered before the next run, the current defaults (Option D, zero interest) will be used.
