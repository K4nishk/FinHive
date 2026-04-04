# QA Lead Output: Loan Manager Prototype
**Date:** 2026-04-03
**Run:** run_1 / Wave 2
**Author:** QA Lead Agent

---

## QA Lead KT Receipt: Loan Manager Prototype

**DM schema signoff pending:** No — CSV schema confirmed (loans.csv, loans_meta.csv, pending_reports.csv, pending_report_records.csv, history.csv, recovery.tmp all present in codebase).
**SRE reliability scope received:** Pending (Wave 1 output not yet available).
**Ready to issue QA briefs:** Yes

---

## Master Test Scope: Loan Manager Prototype

### Backend test scope (pytest)

| ID | Scenario | Priority | Type | Runner Command |
|---|---|---|---|---|
| BE-01 | Status engine: compute_status returns Active for giving_date <= today < due_date | P1 | Unit | `pytest tests/test_status_engine.py::TestComputeStatusActive -v` |
| BE-02 | Status engine: compute_status returns Overdue when due_date <= today | P1 | Unit | `pytest tests/test_status_engine.py::TestComputeStatusOverdue -v` |
| BE-03 | Status engine: compute_status returns Pending when giving_date > today | P1 | Unit | `pytest tests/test_status_engine.py::TestComputeStatusPending -v` |
| BE-04 | Status engine: no due_date + giving_date <= today returns Overdue (R7) | P1 | Unit | `pytest tests/test_status_engine.py::TestComputeStatusNoDueDate -v` |
| BE-05 | Status engine: Paidoff status never recomputed | P1 | Unit | `pytest tests/test_status_engine.py::TestComputeStatusPaidoff -v` |
| BE-06 | Status engine: recompute_all batch updates mixed statuses correctly | P1 | Unit | `pytest tests/test_status_engine.py::TestRecomputeAll -v` |
| BE-07 | Status engine: recompute_all does not mutate original list | P2 | Unit | `pytest tests/test_status_engine.py::TestRecomputeAll::test_recompute_all_does_not_mutate_original_list -v` |
| BE-08 | Interest calculator: Monthly mode R5 authoritative example (10000*12*1)/(12*100)=100 | P1 | Unit | `pytest tests/test_interest_calculator.py::TestCalculateMonthly::test_monthly_extension_period_one_gives_r5_example -v` |
| BE-09 | Interest calculator: Daily mode formula (amount*rate*ext)/(365*100) | P1 | Unit | `pytest tests/test_interest_calculator.py::TestCalculateDaily -v` |
| BE-10 | Interest calculator: calculate_both routes "months" to monthly calculator | P1 | Unit | `pytest tests/test_interest_calculator.py::TestCalculateBoth::test_both_routes_months -v` |
| BE-11 | Interest calculator: calculate_both routes "days" to daily calculator | P1 | Unit | `pytest tests/test_interest_calculator.py::TestCalculateBoth::test_both_routes_days -v` |
| BE-12 | Interest calculator: calculate_both raises ValueError for unknown unit | P1 | Unit | `pytest tests/test_interest_calculator.py::TestCalculateBoth::test_both_invalid_unit_raises -v` |
| BE-13 | Interest calculator: TDS = 0.1 * interest when tds_flag=True | P1 | Unit | `pytest tests/test_interest_calculator.py::TestTDSCalculation -v` |
| BE-14 | Interest calculator: TDS = 0 when tds_flag=False | P1 | Unit | `pytest tests/test_interest_calculator.py::TestTDSCalculation::test_tds_zero_when_flag_false_monthly -v` |
| BE-15 | Interest calculator: TDS applies to interest only, not commission | P1 | Unit | `pytest tests/test_interest_calculator.py::TestTDSCalculation::test_tds_independent_of_commission -v` |
| BE-16 | Interest calculator: months_between partial month rounds UP | P2 | Unit | `pytest tests/test_interest_calculator.py::TestMonthsBetween -v` |
| BE-17 | CSV manager: read_loans excludes Paidoff records | P1 | Unit | `pytest tests/test_csv_manager.py::TestReadLoans::test_read_loans_paidoff_records_excluded -v` |
| BE-18 | CSV manager: read_loans parses dates as date objects | P1 | Unit | `pytest tests/test_csv_manager.py::TestReadLoans::test_read_loans_date_fields_parsed_as_date_objects -v` |
| BE-19 | CSV manager: read_loans parses amount as integer | P1 | Unit | `pytest tests/test_csv_manager.py::TestReadLoans::test_read_loans_amount_parsed_as_integer -v` |
| BE-20 | CSV manager: read_loans handles UTF-8 BOM (Excel export) | P2 | Unit | `pytest tests/test_csv_manager.py::TestReadLoans::test_read_loans_utf8_bom_reads_correctly -v` |
| BE-21 | CSV manager: write_loan stores dates as ISO 8601 | P1 | Unit | `pytest tests/test_csv_manager.py::TestWriteLoan::test_write_loan_dates_stored_as_iso8601 -v` |
| BE-22 | CSV manager: update_loan modifies target field only | P1 | Unit | `pytest tests/test_csv_manager.py::TestUpdateLoan -v` |
| BE-23 | CSV manager: delete_loan removes target and preserves others | P1 | Unit | `pytest tests/test_csv_manager.py::TestDeleteLoan -v` |
| BE-24 | CSV manager: mark_paidoff removes from loans.csv and appends to history.csv with paidoff_date | P1 | Unit | `pytest tests/test_csv_manager.py::TestMarkPaidoff -v` |
| BE-25 | CSV manager: mark_paidoff recovery.tmp deleted on success | P1 | Unit | `pytest tests/test_csv_manager.py::TestMarkPaidoff::test_mark_paidoff_recovery_tmp_deleted_on_success -v` |
| BE-26 | CSV manager: mark_paidoff recovery.tmp persists on crash between writes | P1 | Unit | `pytest tests/test_csv_manager.py::TestMarkPaidoff::test_mark_paidoff_recovery_tmp_persists_on_crash_between_writes -v` |
| BE-27 | CSV manager: extend_loan sets new giving_date = old due_date | P1 | Unit | `pytest tests/test_csv_manager.py::TestExtendLoan::test_extend_loan_new_giving_date_equals_old_due_date -v` |
| BE-28 | CSV manager: extend_loan sets new due_date = old due_date + period | P1 | Unit | `pytest tests/test_csv_manager.py::TestExtendLoan::test_extend_loan_new_due_date_equals_old_due_date_plus_period -v` |
| BE-29 | CSV manager: extend_loan no due_date sets new giving_date = today | P1 | Unit | `pytest tests/test_csv_manager.py::TestExtendLoan::test_extend_loan_no_due_date_new_giving_date_is_today -v` |
| BE-30 | CSV manager: extend_loan preserves reference_id | P1 | Unit | `pytest tests/test_csv_manager.py::TestExtendLoan::test_extend_loan_reference_id_preserved -v` |
| BE-31 | Ref ID manager: first loan in month generates 001 | P1 | Unit | `pytest tests/test_ref_id_manager.py::TestNextRefIdFirstEntry -v` |
| BE-32 | Ref ID manager: counter increments beyond 999 to 1000 without rollover | P1 | Unit | `pytest tests/test_ref_id_manager.py::TestNextRefIdSequentialIncrement::test_next_ref_id_counter_increments_to_1000_no_rollover -v` |
| BE-33 | Ref ID manager: all records deleted resets counter to 001 | P1 | Unit | `pytest tests/test_ref_id_manager.py::TestNextRefIdDeleteReset -v` |
| BE-34 | Ref ID manager: corrupted/missing meta CSV recovers gracefully | P2 | Unit | `pytest tests/test_ref_id_manager.py::TestRefIdManagerRecovery -v` |
| BE-35 | Ref ID manager: counters for different YYYY_MM are independent | P1 | Unit | `pytest tests/test_ref_id_manager.py::TestNextRefIdNewMonth -v` |
| BE-36 | Report manager: generate_report_id first report of day returns RPT_YYYYMMDD_001 | P1 | Unit | `pytest tests/test_report_manager.py::TestGenerateReportId::test_first_report_of_day_returns_001 -v` |
| BE-37 | Report manager: generate_report_id new calendar day resets to 001 | P1 | Unit | `pytest tests/test_report_manager.py::TestGenerateReportId::test_new_calendar_day_resets_to_001 -v` |
| BE-38 | Report manager: read_pending_reports returns only Pending status rows | P1 | Unit | `pytest tests/test_report_manager.py::TestWriteAndReadPendingReports::test_read_pending_reports_returns_only_pending_status -v` |
| BE-39 | Report manager: update_report_status marks report as Approved and updates timestamp | P1 | Unit | `pytest tests/test_report_manager.py -k "update_report_status" -v` |
| BE-40 | Report manager: decline removes report records (hard-delete) from pending_report_records.csv | P1 | Unit | `pytest tests/test_report_manager.py -k "delete_report_records" -v` |
| BE-41 | Report manager: get_active_reference_ids_in_queue returns ref_ids from Pending reports only | P1 | Unit | `pytest tests/test_report_manager.py -k "get_active_reference_ids" -v` |
| BE-42 | Report manager: duplicate reference_id across two Pending reports detected by get_active_reference_ids_in_queue | P1 | Unit | `pytest tests/test_report_manager.py -k "duplicate" -v` |
| BE-43 | Full suite: all backend unit tests pass | P1 | Suite | `pytest tests/ -v` |
| BE-44 | Full suite with coverage report | P2 | Suite | `pytest tests/ --cov=loan_manager --cov-report=term-missing -v` |

### Integration test scope

| ID | Scenario | Priority | Runner Command |
|---|---|---|---|
| IT-01 | Add new loan entry -> ref_id generated -> saved to loans.csv -> readable via read_loans | P1 | `pytest tests/integration/test_loan_entry_flow.py -v` |
| IT-02 | Status recompute on app launch updates all loan statuses in loans.csv | P1 | `pytest tests/integration/test_status_recompute_on_launch.py -v` |
| IT-03 | Interest calculator: filter by BorrowerGroup -> filtered records returned -> calculate -> generate report -> report appears in Pending Approval queue | P1 | `pytest tests/integration/test_calculator_to_report_flow.py -v` |
| IT-04 | Pending Approval: approve report -> loans.csv updated with new giving_date and due_date | P1 | `pytest tests/integration/test_report_approval_flow.py -v` |
| IT-05 | Pending Approval: decline report -> records deleted from pending_report_records.csv -> loans.csv unchanged | P1 | `pytest tests/integration/test_report_decline_flow.py -v` |
| IT-06 | Pending Approval: approve report containing deleted loan record -> warning raised -> only existing records updated | P2 | `pytest tests/integration/test_report_approval_deleted_loan.py -v` |
| IT-07 | Pending Approval: duplicate reference_id in two Pending reports -> conflict warning triggered on approval | P1 | `pytest tests/integration/test_duplicate_ref_id_conflict.py -v` |
| IT-08 | mark_paidoff: atomic write -> recovery.tmp present before history.csv write -> deleted on success -> persists on crash | P1 | `pytest tests/test_csv_manager.py::TestMarkPaidoff -v` |
| IT-09 | extend_loan (R4): reference_id reused -> giving_date and due_date overwritten -> status recomputed | P1 | `pytest tests/integration/test_extend_loan_flow.py -v` |
| IT-10 | CSV import: records with no reference_id auto-assigned new IDs in YYYY_MM_NNN format | P2 | `pytest tests/integration/test_csv_import.py::test_import_no_ref_id -v` |
| IT-11 | CSV import: re-import with existing reference_id overwrites record completely | P2 | `pytest tests/integration/test_csv_import.py::test_import_existing_ref_id_overwrite -v` |
| IT-12 | Pending Approval queue persists across restart (write -> reload -> queue intact) | P1 | `pytest tests/integration/test_report_persistence.py -v` |

### Reliability test scope

| ID | Scenario | Type | Priority |
|---|---|---|---|
| RT-01 | Crash between history.csv write and loans.csv write during mark_paidoff: recovery.tmp present for manual recovery | Crash-safety | P1 |
| RT-02 | loans.csv file absent on launch: app creates empty file and starts without crash | Resilience | P1 |
| RT-03 | loans_meta.csv corrupted: RefIdManager recovers gracefully and starts counter from 001 | Resilience | P1 |
| RT-04 | pending_reports.csv absent on launch: Pending Approval tab loads empty without crash | Resilience | P1 |
| RT-05 | Concurrent read/write not required (single user, R8) but file write must be atomic to avoid partial-row CSV corruption | Atomicity | P2 |
| RT-06 | Up to 1500 loan records: recompute_all completes without observable UI freeze (< 2 sec) | Performance | P2 |
| RT-07 | Up to 1500 loan records: View Tab sort and filter completes without observable UI freeze | Performance | P2 |
| RT-08 | app.log writes do not fail silently when ./data/logs/ directory absent | Logging | P2 |

---

## Existing Test Gap Analysis

### What is currently covered

| Test File | Coverage Area |
|---|---|
| test_status_engine.py | All four status values (Active, Overdue, Pending, Paidoff), no-due-date edge cases (R7), recompute_all batch, immutability, all 15 sample records |
| test_interest_calculator.py | Monthly mode full formula + R5 authoritative example, daily mode full formula, calculate_both routing (months/days/unknown), TDS flag (true/false/independent of commission), months_between with partial-month rounding, zero-rate edge cases, result field preservation |
| test_csv_manager.py | read_loans (empty, header-only, 15 records, Paidoff exclusion, date parsing, optional None fields, UTF-8 BOM, amount as int), write_loan (create, append, ISO dates, None as empty string), update_loan (target field, other records, multiple fields, nonexistent id), delete_loan (removal, preservation, last record, nonexistent id), mark_paidoff (atomic write, recovery.tmp lifecycle, crash simulation, other loans preserved), extend_loan (months/days, no-due-date path, ref_id preserved, other records unaffected) |
| test_ref_id_manager.py | First entry (001), sequential increment (002..999..1000), new month reset, per-month isolation, delete-reset, missing/corrupted/empty/header-only/partial meta CSV recovery |
| test_report_manager.py | generate_report_id (first, second, tenth, new day reset, meta creation, counter persistence, different dates, 999, 1000), write_report + read_pending_reports round-trip, read filters Pending only, update_report_status, write/read_report_records, get_active_reference_ids_in_queue, delete_report_records |

### What is missing (gaps)

**Gap 1 — User-Testing Requirement 1: Interest Calculator filter regression (CRITICAL)**
- No test verifies that applying a BorrowerGroup, BorrowerName, DepositorName, or DepositorGroup filter in the Interest Calculator Tab returns a filtered record set that persists (i.e., does not revert to "All").
- This is the primary User-Testing Requirement 1 bug and has zero backend test coverage.
- New file needed: `tests/test_calculator_filter.py`
- Function patterns needed: `test_filter_by_borrower_group_returns_filtered_records`, `test_filter_persists_after_apply`, `test_filter_by_depositor_group_unknown_blank_option`

**Gap 2 — User-Testing Requirement 1: mark_paidoff UI flow not tested end-to-end**
- Backend unit tests for mark_paidoff CSV operations exist, but there is no integration test confirming: (a) Paidoff dialog prompts for paidoff_date, (b) report is generated using Daily mode with extension_period = paidoff_date - due_date, (c) record moves to history.csv, (d) record disappears from View Tab.
- New file needed: `tests/integration/test_paidoff_flow.py`
- Function patterns needed: `test_mark_paidoff_prompts_for_date`, `test_mark_paidoff_generates_daily_interest_report`, `test_mark_paidoff_record_removed_from_view`

**Gap 3 — No-due-date filter behavior in Interest Calculator (R5)**
- R5 specifies: when no filter applied, show only records with no due_date; when a filter is applied, exclude no-due-date records.
- No existing test covers this two-path filter logic.
- New file needed: `tests/test_calculator_filter.py`
- Function patterns needed: `test_no_filter_returns_only_no_due_date_records`, `test_filter_applied_excludes_no_due_date_records`

**Gap 4 — Pending Approval duplicate reference_id conflict warning**
- R5 specifies: warn user when approving a report whose reference_ids appear in another currently-Pending report.
- `get_active_reference_ids_in_queue` is tested for deduplication, but no test verifies the warning is raised during approval or the silent-overwrite behavior on Proceed.
- New file needed: `tests/integration/test_duplicate_ref_id_conflict.py`
- Function patterns needed: `test_approve_report_with_duplicate_ref_id_raises_conflict_warning`, `test_approve_proceed_silently_overwrites_other_pending_report`

**Gap 5 — Pending Approval: deleted loan in report queue**
- R5 specifies: if a loan is deleted from View Tab before report approval, warn user and skip deleted records on Proceed.
- No existing test.
- New file needed: `tests/integration/test_report_approval_deleted_loan.py`
- Function patterns needed: `test_approve_report_with_deleted_loan_warns_user`, `test_approve_proceed_skips_deleted_records`

**Gap 6 — CSV import service**
- R6 import rules (auto-assign ref_id, upsert on re-import, overwrite on conflict with preview dialog) have no test coverage at all.
- New file needed: `tests/test_csv_import_service.py`
- Function patterns needed: `test_import_no_ref_id_auto_assigns`, `test_import_existing_ref_id_overwrites`, `test_import_collision_after_auto_assign`

**Gap 7 — Status manual toggle rules**
- R3 defines an allowed transition matrix and special rules: Active-override prompts for new due_date (same as Extend), Paidoff is not reachable via toggle (requires CSV edit).
- No test verifies that toggling Active on an Overdue record triggers a due_date prompt rather than silently reverting.
- New file needed: `tests/test_status_toggle.py`
- Function patterns needed: `test_manual_active_override_prompts_new_due_date`, `test_paidoff_not_directly_toggleable`

**Gap 8 — Extend behavior when no due_date (R7 special case)**
- CSVManager.extend_loan covers the no-due-date path (new giving_date = today, new due_date = supplied), but there is no test confirming the UI disallows or handles the case where the user-provided new_due_date is in the past.
- New function pattern needed in `tests/test_csv_manager.py`: `test_extend_loan_no_due_date_new_due_in_past_rejected` [REVIEW REQUIRED — whether this is enforced at service or UI layer]

**Gap 9 — Report summary totals**
- R5 specifies: after calculation, summary captures total_loan_amount, total_interest, total_commission.
- No test verifies summary aggregation.
- New file needed: `tests/test_calculator_summary.py`
- Function patterns needed: `test_summary_total_loan_amount`, `test_summary_total_interest`, `test_summary_total_commission`

**Gap 10 — "Generate Report" button disabled until Calculate is clicked**
- R5 specifies this UI constraint. No test enforces it.
- This is a UI-layer concern but can be tested via widget state assertion in a GUI test.
- [REVIEW REQUIRED] — confirm whether GUI widget tests are in scope for prototype QA or deferred to UAT.

---

## Interest Calculator Tests (R5 — Highest Priority)

### Monthly mode: R5 authoritative example verification

**Test file:** `tests/test_interest_calculator.py`
**Class:** `TestCalculateMonthly`
**Function:** `test_monthly_extension_period_one_gives_r5_example`
**Runner:** `pytest tests/test_interest_calculator.py::TestCalculateMonthly::test_monthly_extension_period_one_gives_r5_example -v`

Formula verified: `(10000 * 12 * 1) / (12 * 100) = 100.00`
- amount = 10000, interest_rate = 12.0, extension_period = 1, extension_period_unit = "months"
- Time = extension_period (not giving_date to due_date gap — this is the R5 authoritative change)
- Expected interest_amount = 100.00
- COVERED: Yes

Additional monthly scenarios needed (NOT YET COVERED):
| Function Name Pattern | Scenario | Expected Result |
|---|---|---|
| `test_monthly_extension_period_3_amount_15000_rate_10` | b3: 15000, rate=10%, ext=3 | (15000*10*3)/(12*100) = 375.00 |
| `test_monthly_commission_calculated_separately_from_interest` | commission is independent additive line | commission = (amount*comm*ext)/(12*100) |
| `test_monthly_global_values_overwrite_per_record_on_header_change` | When global header rate changes, all rows recalculate | [REVIEW REQUIRED] — depends on UI orchestration layer |

### Daily mode formula

**Test file:** `tests/test_interest_calculator.py`
**Class:** `TestCalculateDaily`
**Runner:** `pytest tests/test_interest_calculator.py::TestCalculateDaily -v`

Formula: `Interest = (Amount * interest_rate * extension_period) / (365 * 100)`
Time = extension_period in days (not date difference — same R5 authoritative interpretation)

Key scenario for Paidoff report (R3): `extension_period_days = paidoff_date - due_date`
- NOT CURRENTLY TESTED end-to-end: the calculate_daily function itself is covered, but the paidoff flow that computes extension_period_days from the date subtraction is not tested.
- New test pattern needed: `test_daily_paidoff_extension_period_derived_from_date_difference`
- Runner: `pytest tests/integration/test_paidoff_flow.py::test_mark_paidoff_generates_daily_interest_report -v`

### Both mode routing

**Test file:** `tests/test_interest_calculator.py`
**Class:** `TestCalculateBoth`
**Runner:** `pytest tests/test_interest_calculator.py::TestCalculateBoth -v`

- Routes "months" to calculate_monthly: COVERED
- Routes "days" to calculate_daily: COVERED
- Raises ValueError for unknown unit: COVERED
- Missing: orchestrator function for mode=Both that processes a list of records (each with its own extension_period_unit) — R5 states "There should be an orchestrator function for mode = both added to core calculator code file for testability."
- New test pattern needed: `test_both_mode_orchestrator_processes_mixed_unit_list`
- Runner: `pytest tests/test_interest_calculator.py -k "orchestrator" -v`

### Filter behavior

**NOT CURRENTLY COVERED — Critical gap per User-Testing Requirement 1**

New file: `tests/test_calculator_filter.py`

| Function Name Pattern | Scenario | Runner |
|---|---|---|
| `test_no_filter_shows_only_no_due_date_records` | No filter applied: only records without due_date shown | `pytest tests/test_calculator_filter.py::test_no_filter_shows_only_no_due_date_records -v` |
| `test_filter_applied_excludes_no_due_date_records` | Filter applied: records with no due_date excluded entirely | `pytest tests/test_calculator_filter.py::test_filter_applied_excludes_no_due_date_records -v` |
| `test_filter_by_borrower_group_returns_correct_subset` | BorrowerGroup=bg1 returns only b1, b9 | `pytest tests/test_calculator_filter.py::test_filter_by_borrower_group_returns_correct_subset -v` |
| `test_filter_by_borrower_name_returns_correct_subset` | BorrowerName=b3 returns only b3 | `pytest tests/test_calculator_filter.py::test_filter_by_borrower_name_returns_correct_subset -v` |
| `test_filter_by_depositor_name_returns_correct_subset` | DepositorName=d1 returns only b1 | `pytest tests/test_calculator_filter.py::test_filter_by_depositor_name_returns_correct_subset -v` |
| `test_filter_by_depositor_group_returns_correct_subset` | DepositorGroup=dg3 returns b6, b7, b8, b9 | `pytest tests/test_calculator_filter.py::test_filter_by_depositor_group_returns_correct_subset -v` |
| `test_filter_by_depositor_group_unknown_blank_returns_b14_b15` | DepositorGroup=Unknown/blank returns b14, b15 (records with no depositor_group) | `pytest tests/test_calculator_filter.py::test_filter_by_depositor_group_unknown_blank_returns_b14_b15 -v` |
| `test_filter_by_month_returns_due_date_in_selected_month` | ByMonth=April returns records with due_date in April of current year including Overdue | `pytest tests/test_calculator_filter.py::test_filter_by_month_returns_due_date_in_selected_month -v` |
| `test_multiple_filters_combined_returns_intersection` | BorrowerGroup=bg1 AND ByMonth=April returns intersection only | `pytest tests/test_calculator_filter.py::test_multiple_filters_combined_returns_intersection -v` |
| `test_filter_excludes_paidoff_records` | Filter dropdowns do not offer Paidoff borrowers | `pytest tests/test_calculator_filter.py::test_filter_excludes_paidoff_records -v` |

### Pending Approval: approval flow

New file: `tests/integration/test_report_approval_flow.py`

| Function Name Pattern | Scenario | Runner |
|---|---|---|
| `test_approve_report_updates_loans_csv_giving_and_due_dates` | On Approve, giving_date and due_date in loans.csv updated to post-extension values | `pytest tests/integration/test_report_approval_flow.py::test_approve_report_updates_loans_csv_giving_and_due_dates -v` |
| `test_approve_report_status_changes_to_approved` | report_status set to Approved in pending_reports.csv | `pytest tests/integration/test_report_approval_flow.py::test_approve_report_status_changes_to_approved -v` |
| `test_approve_report_pre_extension_values_shown_before_approval` | Pending Approval tab shows pre-extension values until approval | `pytest tests/integration/test_report_approval_flow.py::test_approve_report_pre_extension_values_shown_before_approval -v` |
| `test_generate_report_button_disabled_before_calculate` | Generate Report button is disabled until Calculate clicked | `pytest tests/integration/test_report_approval_flow.py::test_generate_report_button_disabled_before_calculate -v` [REVIEW REQUIRED — GUI widget test] |

### Conflict warning for duplicate reference_ids in Pending reports

New file: `tests/integration/test_duplicate_ref_id_conflict.py`

| Function Name Pattern | Scenario | Runner |
|---|---|---|
| `test_approve_report_with_shared_ref_id_shows_conflict_warning` | Two Pending reports share a reference_id -> warning shown on Approve | `pytest tests/integration/test_duplicate_ref_id_conflict.py::test_approve_report_with_shared_ref_id_shows_conflict_warning -v` |
| `test_approve_proceed_silently_overwrites_other_pending_report_records` | User clicks Proceed -> other pending report's records overwritten silently | `pytest tests/integration/test_duplicate_ref_id_conflict.py::test_approve_proceed_silently_overwrites_other_pending_report_records -v` |
| `test_approve_cancel_leaves_both_reports_pending` | User clicks Cancel -> both reports remain Pending, no storage change | `pytest tests/integration/test_duplicate_ref_id_conflict.py::test_approve_cancel_leaves_both_reports_pending -v` |

---

## Status Engine Tests

### All status transitions

| Transition | Rule | Test Class | Test Function | Runner |
|---|---|---|---|---|
| -> Active | giving_date <= today < due_date | TestComputeStatusActive | test_compute_status_future_due_date_returns_active | `pytest tests/test_status_engine.py::TestComputeStatusActive::test_compute_status_future_due_date_returns_active -v` |
| -> Overdue | due_date <= today | TestComputeStatusOverdue | test_compute_status_past_due_date_returns_overdue | `pytest tests/test_status_engine.py::TestComputeStatusOverdue -v` |
| -> Pending | giving_date > today | TestComputeStatusPending | test_compute_status_future_giving_date_returns_pending | `pytest tests/test_status_engine.py::TestComputeStatusPending -v` |
| -> Paidoff (preserved) | current_status=Paidoff | TestComputeStatusPaidoff | test_compute_status_paidoff_not_recomputed_even_if_overdue_by_date | `pytest tests/test_status_engine.py::TestComputeStatusPaidoff -v` |

### No due_date cases

| Scenario | Expected Status | Test Class | Test Function | Runner |
|---|---|---|---|---|
| No due_date, giving_date <= today | Overdue (R7) | TestComputeStatusNoDueDate | test_compute_status_no_due_date_past_giving_date_returns_overdue | `pytest tests/test_status_engine.py::TestComputeStatusNoDueDate::test_compute_status_no_due_date_past_giving_date_returns_overdue -v` |
| No due_date, giving_date == today | Overdue (R7) | TestComputeStatusNoDueDate | test_compute_status_no_due_date_giving_equals_today_returns_overdue | `pytest tests/test_status_engine.py::TestComputeStatusNoDueDate::test_compute_status_no_due_date_giving_equals_today_returns_overdue -v` |
| No due_date, giving_date > today | Pending (inferred) | TestComputeStatusNoDueDate | test_compute_status_no_due_date_future_giving_returns_pending | `pytest tests/test_status_engine.py::TestComputeStatusNoDueDate::test_compute_status_no_due_date_future_giving_returns_pending -v` |

**[REVIEW REQUIRED]** Boundary: `due_date == today` is treated as Overdue per `due_date <= today` (R3). Marked in test file as requiring product owner confirmation.

### Manual toggle vs auto-recompute

- Auto-recompute: covered via `TestRecomputeAll` — all statuses recomputed on every call except Paidoff.
- Manual toggle: no test currently validates the UI-layer rule that Active override on an Overdue record must prompt for a new due_date. This falls in Gap 7 above.
- `recompute_all` overrides manual toggles: covered implicitly — the function always recomputes based on dates regardless of the stored status value (except Paidoff).
- New test needed: `test_recompute_all_overrides_manual_active_flag_if_dates_are_overdue`
  - Runner: `pytest tests/test_status_engine.py -k "override" -v`

---

## Test Coverage Targets

| Module | Target Coverage | Key Test File |
|---|---|---|
| loan_manager/status_engine.py | 100% | tests/test_status_engine.py |
| loan_manager/interest_calculator.py | 100% | tests/test_interest_calculator.py |
| loan_manager/csv_manager.py | 95% | tests/test_csv_manager.py |
| loan_manager/ref_id_manager.py | 100% | tests/test_ref_id_manager.py |
| loan_manager/report_manager.py | 90% | tests/test_report_manager.py |
| loan_manager/calculator_filter.py | 90% | tests/test_calculator_filter.py (new) |
| loan_manager/csv_import_service.py | 85% | tests/test_csv_import_service.py (new) |
| loan_manager/status_toggle.py (if separate) | 85% | tests/test_status_toggle.py (new) |
| Integration flows | 80% path coverage | tests/integration/* (new) |

Run coverage check:
```
pytest tests/ --cov=loan_manager --cov-report=term-missing --cov-fail-under=85 -v
```

---

## QA Signoff Criteria

### Entry Criteria (before any QA execution)

1. All P1 backend unit tests exist and are runnable via `pytest tests/ -v` with no import errors.
2. `loan_manager` package is importable from the `src/Loan Manager/` directory.
3. `pytest.ini` configures `testpaths = tests` and `pythonpath = .`.
4. Sample data files (`loans.csv`, `loans_meta.csv`, `pending_reports.csv`, `pending_report_records.csv`) present in `./data/` for integration tests.
5. No console.logs or debug print statements committed to production code.
6. Python version >= 3.10 confirmed on test machine.

### Exit Criteria (prototype release gate)

**Must pass (P1 — blocking):**
1. All BE-01 through BE-43 backend unit tests pass with zero failures.
2. IT-01, IT-03, IT-04, IT-05, IT-07, IT-08, IT-12 integration tests pass.
3. RT-01 (crash-safety test) passes.
4. Interest calculator filter: all 10 filter scenarios in `tests/test_calculator_filter.py` pass — this directly addresses User-Testing Requirement 1.
5. mark_paidoff end-to-end flow passes in `tests/integration/test_paidoff_flow.py`.
6. Duplicate reference_id conflict warning tests pass in `tests/integration/test_duplicate_ref_id_conflict.py`.
7. Overall backend coverage >= 85% (`pytest --cov=loan_manager --cov-fail-under=85`).

**Should pass (P2 — non-blocking for prototype but documented):**
1. IT-10, IT-11 CSV import integration tests pass.
2. RT-06, RT-07 performance tests complete within 2 seconds for 1500 records.
3. `test_status_toggle.py` tests pass for manual toggle transition rules.

**Deferred (out of prototype scope, log as known risk):**
1. GUI widget tests for "Generate Report" button disabled state (Gap 10).
2. Concurrent session file-locking (R8 explicitly deferred).
3. Backup copy of loans.csv before bulk Approve (R3 explicitly deferred).
4. Full history.csv in-app view (R3 — no in-app view required for prototype).

### Regression Criteria
- Any change to `interest_calculator.py` must re-run `pytest tests/test_interest_calculator.py -v` before merge.
- Any change to `status_engine.py` must re-run `pytest tests/test_status_engine.py -v` before merge.
- Any change to `csv_manager.py` must re-run `pytest tests/test_csv_manager.py -v` before merge.
- Any schema change to `pending_reports.csv` or `pending_report_records.csv` must re-run `pytest tests/test_report_manager.py -v` before merge.

### Quick smoke test command (run before any commit)
```
pytest tests/ -v --tb=short -q
```
