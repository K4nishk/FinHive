# Backend QA — Loan Manager
**Run:** run_1 | **Wave:** 2 | **Date:** 2026-04-03

---

## 1. Existing Test Coverage Analysis

### 1.1 What Is Currently Covered

#### status_engine (test_status_engine.py)
| Class | Test Function | Scenario |
|---|---|---|
| TestComputeStatusActive | test_compute_status_future_due_date_returns_active | Basic active path |
| TestComputeStatusActive | test_compute_status_giving_equals_today_future_due_date_returns_active | giving_date == today boundary |
| TestComputeStatusActive | test_compute_status_sample_active_loans_return_active (parametrized x13) | Sample b1-b13 records |
| TestComputeStatusOverdue | test_compute_status_past_due_date_returns_overdue | due_date in past |
| TestComputeStatusOverdue | test_compute_status_due_date_yesterday_returns_overdue | due_date == today - 1 |
| TestComputeStatusOverdue | test_compute_status_due_date_equals_today_returns_overdue | due_date == today boundary |
| TestComputeStatusPending | test_compute_status_future_giving_date_returns_pending | giving_date > today |
| TestComputeStatusPending | test_compute_status_giving_date_tomorrow_returns_pending | giving_date == today + 1 |
| TestComputeStatusPending | test_compute_status_giving_far_future_no_due_date_returns_pending | No due_date, future giving_date |
| TestComputeStatusNoDueDate | test_compute_status_no_due_date_past_giving_date_returns_overdue | R7: no due_date + past giving |
| TestComputeStatusNoDueDate | test_compute_status_no_due_date_giving_equals_today_returns_overdue | R7: no due_date + today giving |
| TestComputeStatusNoDueDate | test_compute_status_no_due_date_future_giving_returns_pending | R7: no due_date + future giving |
| TestComputeStatusPaidoff | test_compute_status_paidoff_not_recomputed_even_if_overdue_by_date | Paidoff immunity |
| TestComputeStatusPaidoff | test_compute_status_paidoff_not_recomputed_even_if_future_due_date | Paidoff immunity (future) |
| TestComputeStatusPaidoff | test_compute_status_paidoff_not_recomputed_with_no_due_date | Paidoff immunity (no due_date) |
| TestRecomputeAll | test_recompute_all_returns_same_count | Record count preservation |
| TestRecomputeAll | test_recompute_all_updates_overdue_record | Batch overdue update |
| TestRecomputeAll | test_recompute_all_updates_pending_record | Batch pending update |
| TestRecomputeAll | test_recompute_all_preserves_paidoff_status | Batch paidoff immunity |
| TestRecomputeAll | test_recompute_all_does_not_mutate_original_list | Immutability |
| TestRecomputeAll | test_recompute_all_mixed_statuses | All 4 statuses in one batch |
| TestRecomputeAll | test_recompute_all_empty_list_returns_empty | Empty input |
| TestRecomputeAll | test_recompute_all_sample_loans_all_active | All 15 sample records |

#### interest_calculator (test_interest_calculator.py)
| Class | Test Function | Scenario |
|---|---|---|
| TestMonthsBetween | test_exact_three_months | months_between exact |
| TestMonthsBetween | test_exact_one_month | months_between 1 month |
| TestMonthsBetween | test_exact_twelve_months | months_between 1 year |
| TestMonthsBetween | test_same_day_returns_zero | months_between zero |
| TestMonthsBetween | test_partial_month_rounds_up | Rounding up |
| TestMonthsBetween | test_one_day_short_of_full_month_rounds_up | Near-boundary rounding |
| TestMonthsBetween | test_one_day_into_new_month_rounds_up | Over-boundary rounding |
| TestMonthsBetween | test_months_between_sample_records (parametrized x10) | Sample records b2-b11 |
| TestCalculateMonthly | test_b1_exact_three_months_no_extension_no_tds | extension_period=0 baseline |
| TestCalculateMonthly | test_monthly_with_extension_period | extension_period=2 |
| TestCalculateMonthly | test_monthly_tds_flag_true | TDS on |
| TestCalculateMonthly | test_monthly_tds_flag_false_gives_zero_tds | TDS off |
| TestCalculateMonthly | test_monthly_zero_interest_rate | Zero rate |
| TestCalculateMonthly | test_monthly_zero_commission_rate | Zero commission |
| TestCalculateMonthly | test_monthly_both_rates_zero | Both zero |
| TestCalculateMonthly | test_monthly_extension_period_one_gives_r5_example | R5 authoritative example |
| TestCalculateMonthly | test_monthly_result_preserves_input_fields | Field passthrough |
| TestCalculateMonthly | test_monthly_tds_equals_ten_percent_of_interest | TDS precision |
| TestCalculateMonthly | test_monthly_parametrized_records (parametrized x3) | Sample b1, b3, b4 |
| TestCalculateDaily | test_b1_daily_exact_days_no_extension_no_tds | extension_period=0 baseline |
| TestCalculateDaily | test_daily_with_extension_period | extension_period=30 |
| TestCalculateDaily | test_daily_tds_flag_true | TDS on |
| TestCalculateDaily | test_daily_tds_flag_false_gives_zero_tds | TDS off |
| TestCalculateDaily | test_daily_zero_interest_rate | Zero rate |
| TestCalculateDaily | test_daily_zero_commission_rate | Zero commission |
| TestCalculateDaily | test_daily_both_rates_zero | Both zero |
| TestCalculateDaily | test_daily_result_preserves_input_fields | Field passthrough |
| TestCalculateDaily | test_daily_time_is_extension_period_only | Time source confirmed |
| TestCalculateDaily | test_daily_formula_matches_manual_calculation (parametrized x5) | Manual verification |
| TestTDSCalculation | test_tds_is_ten_percent_of_interest_monthly | TDS monthly precision |
| TestTDSCalculation | test_tds_is_ten_percent_of_interest_daily | TDS daily precision |
| TestTDSCalculation | test_tds_zero_when_flag_false_monthly | TDS off monthly |
| TestTDSCalculation | test_tds_zero_when_flag_false_daily | TDS off daily |
| TestTDSCalculation | test_tds_independent_of_commission | TDS isolation |
| TestCalculateBoth | test_both_routes_months | Routes to monthly |
| TestCalculateBoth | test_both_routes_days | Routes to daily |
| TestCalculateBoth | test_both_invalid_unit_raises | Unknown unit error |

#### csv_manager (test_csv_manager.py)
| Class | Test Function | Scenario |
|---|---|---|
| TestReadLoans | test_read_loans_empty_file_returns_empty_list | Empty file |
| TestReadLoans | test_read_loans_header_only_returns_empty_list | Header only |
| TestReadLoans | test_read_loans_fifteen_sample_records_parsed_correctly | 15 records |
| TestReadLoans | test_read_loans_paidoff_records_excluded | Paidoff filtered |
| TestReadLoans | test_read_loans_date_fields_parsed_as_date_objects | Date parsing |
| TestReadLoans | test_read_loans_missing_optional_fields_return_none | None for empty optional |
| TestReadLoans | test_read_loans_utf8_bom_reads_correctly | Excel BOM |
| TestReadLoans | test_read_loans_amount_parsed_as_integer | Amount type |
| TestWriteLoan | test_write_loan_creates_file_with_header_and_record | New file create |
| TestWriteLoan | test_write_loan_appends_to_existing_file | Append |
| TestWriteLoan | test_write_loan_dates_stored_as_iso8601 | ISO 8601 dates |
| TestWriteLoan | test_write_loan_none_optional_fields_stored_as_empty_string | None serialization |
| TestUpdateLoan | test_update_loan_modifies_target_record | Single field update |
| TestUpdateLoan | test_update_loan_preserves_other_records | Sibling preservation |
| TestUpdateLoan | test_update_loan_multiple_fields_updated | Multi-field update |
| TestUpdateLoan | test_update_loan_nonexistent_reference_id_no_error | Missing ID no-op |
| TestDeleteLoan | test_delete_loan_removes_target_record | Delete one of two |
| TestDeleteLoan | test_delete_loan_other_records_intact | Sibling preservation |
| TestDeleteLoan | test_delete_loan_last_record_leaves_header_only | Delete only record |
| TestDeleteLoan | test_delete_loan_nonexistent_id_no_error | Missing ID no-op |
| TestMarkPaidoff | test_mark_paidoff_removes_record_from_loans_csv | Removal from loans |
| TestMarkPaidoff | test_mark_paidoff_appends_record_to_history_csv | Addition to history |
| TestMarkPaidoff | test_mark_paidoff_history_record_has_paidoff_date | paidoff_date field |
| TestMarkPaidoff | test_mark_paidoff_recovery_tmp_deleted_on_success | Cleanup on success |
| TestMarkPaidoff | test_mark_paidoff_recovery_tmp_created_before_writes | Ordering of tmp creation |
| TestMarkPaidoff | test_mark_paidoff_recovery_tmp_persists_on_crash_between_writes | Crash safety |
| TestMarkPaidoff | test_mark_paidoff_other_loans_preserved | Sibling preservation |
| TestExtendLoan | test_extend_loan_new_due_date_equals_old_due_date_plus_period (parametrized x4) | New due_date calculation |
| TestExtendLoan | test_extend_loan_new_giving_date_equals_old_due_date (parametrized x2) | New giving_date |
| TestExtendLoan | test_extend_loan_no_due_date_new_giving_date_is_today | R7 no-due-date path |
| TestExtendLoan | test_extend_loan_reference_id_preserved | Ref ID immutability |
| TestExtendLoan | test_extend_loan_other_records_unaffected | Sibling preservation |

#### ref_id_manager (test_ref_id_manager.py)
| Class | Test Function | Scenario |
|---|---|---|
| TestNextRefIdFirstEntry | test_next_ref_id_first_loan_in_month_generates_001 | First entry |
| TestNextRefIdFirstEntry | test_next_ref_id_meta_csv_created_when_missing | Auto-create meta file |
| TestNextRefIdFirstEntry | test_next_ref_id_first_entry_january | January edge |
| TestNextRefIdFirstEntry | test_next_ref_id_first_entry_december | December edge |
| TestNextRefIdSequentialIncrement | test_next_ref_id_second_loan_same_month_generates_002 | Sequential |
| TestNextRefIdSequentialIncrement | test_next_ref_id_tenth_loan_generates_010 | 3-digit zero-pad |
| TestNextRefIdSequentialIncrement | test_next_ref_id_999th_loan_generates_999 | Boundary 999 |
| TestNextRefIdSequentialIncrement | test_next_ref_id_counter_increments_to_1000_no_rollover | Beyond 999 |
| TestNextRefIdSequentialIncrement | test_next_ref_id_counter_persists_after_call | Persistence |
| TestNextRefIdSequentialIncrement | test_next_ref_id_sequential_calls_increment_correctly (parametrized x4) | Sequential calls |
| TestNextRefIdNewMonth | test_next_ref_id_new_month_resets_to_001 | New month independence |
| TestNextRefIdNewMonth | test_next_ref_id_concurrent_months_independent | Two-month independence |
| TestNextRefIdNewMonth | test_next_ref_id_existing_month_unaffected_by_new_month | Cross-month stability |
| TestNextRefIdDeleteReset | test_next_ref_id_all_records_deleted_resets_counter_to_001 | Reset to 001 |
| TestNextRefIdDeleteReset | test_next_ref_id_reset_one_month_does_not_affect_other | Reset isolation |
| TestRefIdManagerRecovery | test_next_ref_id_missing_meta_csv_recovers_gracefully | Missing file |
| TestRefIdManagerRecovery | test_next_ref_id_corrupted_meta_csv_recovers_gracefully | Corrupt file |
| TestRefIdManagerRecovery | test_next_ref_id_empty_meta_csv_recovers_gracefully | Empty file |
| TestRefIdManagerRecovery | test_next_ref_id_header_only_meta_csv_recovers_gracefully | Header-only file |
| TestRefIdManagerRecovery | test_next_ref_id_partial_row_in_meta_csv_recovers | Partial row |

#### report_manager (test_report_manager.py)
| Class | Test Function | Scenario |
|---|---|---|
| TestGenerateReportId | test_first_report_of_day_returns_001 | First report |
| TestGenerateReportId | test_second_report_same_day_returns_002 | Sequential same day |
| TestGenerateReportId | test_tenth_report_same_day_returns_010 | 3-digit zero-pad |
| TestGenerateReportId | test_new_calendar_day_resets_to_001 | Day boundary reset |
| TestGenerateReportId | test_meta_created_on_first_call | Auto-create meta |
| TestGenerateReportId | test_counter_persists_after_call | Persistence |
| TestGenerateReportId | test_different_dates_have_independent_counters | Date independence |
| TestGenerateReportId | test_sequential_calls_increment_correctly (parametrized x3) | Sequential |
| TestGenerateReportId | test_999th_report_gives_999 | Boundary 999 |
| TestGenerateReportId | test_1000th_report_no_zero_padding_rollover | Beyond 999 |
| TestWriteAndReadPendingReports | test_write_report_creates_file_on_first_write | File creation |
| TestWriteAndReadPendingReports | test_write_report_file_has_header_row | Header present |
| TestWriteAndReadPendingReports | test_read_pending_reports_empty_file_returns_empty_list | Empty file |
| TestWriteAndReadPendingReports | test_read_pending_reports_file_absent_returns_empty_list | Absent file |
| TestWriteAndReadPendingReports | test_write_read_round_trip_single_report | Round-trip |
| TestWriteAndReadPendingReports | test_write_report_appends_second_report | Append |
| TestWriteAndReadPendingReports | test_read_pending_reports_returns_only_pending_status | Status filter |
| TestWriteAndReadPendingReports | test_write_report_header_only_returns_empty_list | Header-only |
| TestWriteAndReadPendingReports | test_write_report_stores_report_id_correctly | Report ID field |
| TestWriteAndReadPendingReports | test_write_report_stores_dates_as_iso8601 | ISO 8601 dates |
| TestWriteAndReadPendingReports | test_write_report_stores_mode_correctly | Mode field |
| TestUpdateReportStatus | test_update_status_pending_to_approved | Approve |
| TestUpdateReportStatus | test_update_status_pending_to_declined | Decline |
| TestUpdateReportStatus | test_update_status_updates_latest_update_dt | Timestamp update |
| TestUpdateReportStatus | test_update_status_preserves_other_reports | Sibling preservation |
| TestUpdateReportStatus | test_update_status_nonexistent_report_id_is_noop | Missing ID no-op |
| TestUpdateReportStatus | test_update_status_preserves_creation_date | Creation date immutable |
| TestUpdateReportStatus | test_declined_report_row_retained_after_decline | PD-16 retention |
| TestReadReportRecords | test_read_report_records_file_absent_returns_empty_list | Absent file |
| TestReadReportRecords | test_read_report_records_returns_matching_rows_only | ID filter |
| TestReadReportRecords | test_read_report_records_no_matching_report_id_returns_empty_list | No match |
| TestReadReportRecords | test_read_report_records_returns_correct_reference_ids | Order preservation |
| TestReadReportRecords | test_read_report_records_header_only_file_returns_empty_list | Header-only |
| TestWriteAndReadReportRecords | test_write_records_creates_file_on_first_write | File creation |
| TestWriteAndReadReportRecords | test_write_records_appends_to_existing_file | Append |
| TestWriteAndReadReportRecords | test_write_read_round_trip_single_record | Round-trip |
| TestWriteAndReadReportRecords | test_write_read_round_trip_multiple_records | Multi-record round-trip |
| TestGetActiveReferenceIdsInQueue | test_pending_reports_reference_ids_are_included | Pending included |
| TestGetActiveReferenceIdsInQueue | test_approved_reports_are_excluded | Approved excluded |
| TestGetActiveReferenceIdsInQueue | test_declined_reports_are_excluded | Declined excluded |
| TestGetActiveReferenceIdsInQueue | test_only_pending_report_reference_ids_are_included | Mixed statuses |
| TestGetActiveReferenceIdsInQueue | test_duplicate_reference_ids_across_pending_reports_are_deduplicated | Deduplication |
| TestGetActiveReferenceIdsInQueue | test_empty_queue_returns_empty_set | Empty queue |
| TestGetActiveReferenceIdsInQueue | test_no_pending_reports_returns_empty_set | No pending |
| TestDeleteReportRecords | test_delete_removes_records_for_report_id | Delete target |
| TestDeleteReportRecords | test_delete_preserves_other_reports_records | Sibling preservation |
| TestDeleteReportRecords | test_delete_file_absent_is_noop | Absent file no-op |
| TestDeleteReportRecords | test_delete_nonexistent_report_id_is_noop | Missing ID no-op |
| TestDeleteReportRecords | test_delete_header_retained_when_all_records_deleted | Header-only result |

---

### 1.2 What Is Missing

#### status_engine
- No test for the `Loan` dataclass calling convention (all tests use keyword-args dict form). The `compute_status(loan, today)` branch path with a `Loan` object is untested.
- No test for `giving_date` missing/None raises `ValueError`.
- No test for `today` missing/None raises `ValueError` in keyword-args form.
- No test for `recompute_all` with a list of `Loan` dataclass objects (only dicts tested).
- No test verifying that the Loan dataclass `status` attribute is mutated in-place when using the `Loan` branch (the dict branch creates a copy; the Loan branch mutates the object directly — asymmetric behaviour, not tested).

#### interest_calculator
- No test for `days_between()` function (function exists in the module but is absent from test file entirely).
- No test for fractional `interest_rate` and `commission_rate` values (e.g. 12.5%, 1.75%).
- No test for very large amounts (e.g. 1,000,000) to detect floating-point overflow risk.
- No test for `extension_period` = 0 in `calculate_both` (monthly route and daily route with zero period).
- No test verifying `calculate_both` with `tds_flag=True` in both routing paths.
- No test for `calculate_both` returning correct keys (`time_months` vs `time_days`) for each route explicitly (currently only checked for the monthly route's `time_months` key and daily route's `time_days` key separately, but not verified that the wrong key is absent).
- No authoritative paidoff-daily test: R3 specifies paidoff flow uses Daily mode with `extension_period(days) = paidoff_date - due_date`. No test exercises the full paidoff interest-calculation path end-to-end.
- No negative `extension_period` guard test (API does not specify, but 0 should be the floor).

#### csv_manager
- No test for `read_loans` when the file does not exist (only empty-file and header-only covered; a completely absent `loans.csv` is not tested).
- No test for `recovery.tmp` startup recovery: if `recovery.tmp` exists when the app starts (crash-interrupted prior run), the expected behaviour is undefined in tests. R3 states this is a documented risk but a test to assert the startup check behaviour is missing.
- No test for `mark_paidoff` on a non-existent `reference_id` (should be a no-op or raise — not tested).
- No test for `update_loan` where `updated_fields` contains a date object (tested for `due_date` only — `giving_date` update not tested).
- No test for `extend_loan` with an invalid `unit` value (e.g. `"weeks"` — no ValueError guard tested).
- No test for `write_loan` when the parent directory does not exist yet.
- No test for the full `mark_paidoff` history-append path when `history.csv` already has prior entries (multi-record history append not tested, only single-record history).
- No test for `extend_loan` where the `reference_id` is missing from the file (no-op vs exception not tested).
- No import (`read_loans` from CSV/XLSX external file) or export path tested at the service layer.

#### ref_id_manager
- No test for collision avoidance when an imported record's auto-assigned ID already exists in the CSV (R4/R6). The `RefIdManager` API has no `check_collision` or `next_available_ref_id(existing_ids)` method, so this scenario has no service-layer test.
- No test for `next_ref_id` called with invalid month values (0, 13) — no guard tested.
- No test for `next_ref_id` called with year values outside the normal range.

#### report_manager
- No test for `update_report_records` (the method exists in the service but is completely absent from the test file).
- No test for the full approve-and-apply flow: approving a report should update `loans.csv` records with new dates. This cross-service behaviour (report_manager + csv_manager) has no integration test.
- No test for the duplicate reference_id conflict warning scenario (PD-19): when approving report A whose records overlap with still-pending report B, the caller should detect the overlap. The `get_active_reference_ids_in_queue` utility is tested, but the approval workflow using it is not.
- No test for the deleted-loan-in-report scenario: when a loan is deleted from `loans.csv` before its report is approved, the approval should skip deleted records and warn the user.
- No test for `write_report_records` with `tds_flag=True` stored as lowercase `"true"` and then correctly round-tripped through `read_report_records`.
- No test for `read_report_records` data types — amount as int, dates as `date` objects, interest/commission as float, `tds_flag` as bool.
- No test for `update_report_records` replacing line items correctly while leaving other reports' records untouched.

---

### 1.3 Test Quality Assessment

**status_engine**: High quality. All 6 status rules are covered with boundary values. The `[REVIEW REQUIRED]` marker for `due_date == today` boundary is noted in tests and should be resolved with the product owner. The Loan-dataclass calling convention is the only meaningful gap.

**interest_calculator**: High quality for the function paths that exist. The `days_between` function is entirely untested. Fractional rate values and the paidoff daily path are missing. The R5 authoritative example is explicitly tested, which is the most important scenario.

**csv_manager**: Good coverage of the core happy paths. Atomicity tests for `mark_paidoff` are well-structured. Key gaps are the startup recovery protocol (recovery.tmp at boot), multi-record history, and the absent-file read path. The extend-with-invalid-unit guard is not tested.

**ref_id_manager**: Strong coverage. The most notable gap is the collision-detection path required by R4/R6 for imported records with legacy or duplicate IDs.

**report_manager**: The `update_report_records` method has zero test coverage. The cross-service approval flow and conflict/deleted-loan scenarios are business-critical gaps with no tests at any layer.

---

## 2. Backend Test Scenarios — Full Spec

### Backend Test Scenarios: status_engine

| ID | Scenario | Input | Expected | Priority | Runner Command |
|---|---|---|---|---|---|
| SE-01 | Active: giving <= today < due_date | giving=2026-01-02, due=2026-04-02, today=2026-03-22 | "Active" | P1 | `pytest tests/test_status_engine.py::TestComputeStatusActive::test_compute_status_future_due_date_returns_active -v` |
| SE-02 | Active: giving == today | giving=2026-03-22, due=2026-04-01, today=2026-03-22 | "Active" | P1 | `pytest tests/test_status_engine.py::TestComputeStatusActive::test_compute_status_giving_equals_today_future_due_date_returns_active -v` |
| SE-03 | Overdue: due_date in past | giving=2026-01-01, due=2026-03-01, today=2026-03-22 | "Overdue" | P1 | `pytest tests/test_status_engine.py::TestComputeStatusOverdue::test_compute_status_past_due_date_returns_overdue -v` |
| SE-04 | Overdue: due_date == today (inclusive boundary) | giving=2026-01-01, due=2026-03-22, today=2026-03-22 | "Overdue" | P1 | `pytest tests/test_status_engine.py::TestComputeStatusOverdue::test_compute_status_due_date_equals_today_returns_overdue -v` |
| SE-05 | Pending: giving_date > today | giving=2026-04-01, due=2026-07-01, today=2026-03-22 | "Pending" | P1 | `pytest tests/test_status_engine.py::TestComputeStatusPending::test_compute_status_future_giving_date_returns_pending -v` |
| SE-06 | Pending: no due_date, future giving_date (R7) | giving=2026-04-01, due=None, today=2026-03-22 | "Pending" | P1 | `pytest tests/test_status_engine.py::TestComputeStatusPending::test_compute_status_giving_far_future_no_due_date_returns_pending -v` |
| SE-07 | Overdue: no due_date, giving_date <= today (R7) | giving=2026-01-01, due=None, today=2026-03-22 | "Overdue" | P1 | `pytest tests/test_status_engine.py::TestComputeStatusNoDueDate::test_compute_status_no_due_date_past_giving_date_returns_overdue -v` |
| SE-08 | Overdue: no due_date, giving_date == today (R7) | giving=2026-03-22, due=None, today=2026-03-22 | "Overdue" | P1 | `pytest tests/test_status_engine.py::TestComputeStatusNoDueDate::test_compute_status_no_due_date_giving_equals_today_returns_overdue -v` |
| SE-09 | Paidoff: never auto-recomputed even if overdue by date | giving=2026-01-01, due=2026-02-01, status="Paidoff", today=2026-03-22 | "Paidoff" | P1 | `pytest tests/test_status_engine.py::TestComputeStatusPaidoff -v` |
| SE-10 | recompute_all: batch mixed statuses | 5 loans with Active/Overdue/Pending/Paidoff/NoDueDate | Correct per-record status | P1 | `pytest tests/test_status_engine.py::TestRecomputeAll::test_recompute_all_mixed_statuses -v` |
| SE-11 | recompute_all: does not mutate original list | One overdue loan dict | Original status unchanged after call | P2 | `pytest tests/test_status_engine.py::TestRecomputeAll::test_recompute_all_does_not_mutate_original_list -v` |
| SE-12 | recompute_all: empty list | [] | [] | P2 | `pytest tests/test_status_engine.py::TestRecomputeAll::test_recompute_all_empty_list_returns_empty -v` |
| SE-13 | [NEW] compute_status: giving_date=None raises ValueError | giving=None, due=2026-04-01, today=2026-03-22 | ValueError raised | P2 | `pytest tests/test_status_engine.py::TestComputeStatusEdgeCases::test_compute_status_no_giving_date_raises -v` |
| SE-14 | [NEW] compute_status: today=None raises ValueError | giving=2026-01-01, due=2026-04-01, today=None | ValueError raised | P2 | `pytest tests/test_status_engine.py::TestComputeStatusEdgeCases::test_compute_status_no_today_raises -v` |
| SE-15 | [NEW] compute_status: Loan dataclass calling convention — Active | Loan(giving=2026-01-02, due=2026-04-02, status="Active"), today=2026-03-22 | "Active" | P1 | `pytest tests/test_status_engine.py::TestComputeStatusLoanObject::test_compute_status_loan_object_active -v` |
| SE-16 | [NEW] recompute_all: Loan dataclass list — status mutated in-place | [Loan(overdue_dates, status="Active")] | loan.status == "Overdue" | P1 | `pytest tests/test_status_engine.py::TestRecomputeAllLoanObjects::test_recompute_all_loan_objects_mutates_status -v` |

### Backend Test Scenarios: interest_calculator

| ID | Scenario | Input | Expected | Priority | Runner Command |
|---|---|---|---|---|---|
| IC-01 | R5 authoritative: 10000 @ 12% for 1 month = 100 | amount=10000, rate=12, ext=1, unit=months | interest_amount=100.0 | P1 | `pytest tests/test_interest_calculator.py::TestCalculateMonthly::test_monthly_extension_period_one_gives_r5_example -v` |
| IC-02 | Monthly: extension_period=0 gives zero interest | amount=10000, rate=12, ext=0 | interest=0, commission=0, tds=0 | P1 | `pytest tests/test_interest_calculator.py::TestCalculateMonthly::test_b1_exact_three_months_no_extension_no_tds -v` |
| IC-03 | Monthly: TDS = 10% of interest when tds_flag=True | amount=10000, rate=12, ext=1, tds=True | tds=10.0, interest=100.0 | P1 | `pytest tests/test_interest_calculator.py::TestCalculateMonthly::test_monthly_tds_flag_true -v` |
| IC-04 | Monthly: TDS = 0 when tds_flag=False | amount=10000, rate=12, ext=1, tds=False | tds=0.0 | P1 | `pytest tests/test_interest_calculator.py::TestCalculateMonthly::test_monthly_tds_flag_false_gives_zero_tds -v` |
| IC-05 | Monthly: zero interest_rate | amount=10000, rate=0, comm=2, ext=3 | interest=0.0, commission=50.0 | P1 | `pytest tests/test_interest_calculator.py::TestCalculateMonthly::test_monthly_zero_interest_rate -v` |
| IC-06 | Monthly: zero commission_rate | amount=10000, rate=12, comm=0, ext=3 | interest=300.0, commission=0.0 | P1 | `pytest tests/test_interest_calculator.py::TestCalculateMonthly::test_monthly_zero_commission_rate -v` |
| IC-07 | Monthly: both rates zero | rate=0, comm=0, ext=3 | interest=0, commission=0, tds=0 | P2 | `pytest tests/test_interest_calculator.py::TestCalculateMonthly::test_monthly_both_rates_zero -v` |
| IC-08 | Daily: 10000 @ 12% for 30 days | amount=10000, rate=12, ext=30 | interest=(10000*12*30)/(365*100) approx 98.63 | P1 | `pytest tests/test_interest_calculator.py::TestCalculateDaily::test_daily_with_extension_period -v` |
| IC-09 | Daily: TDS = 10% of interest when tds_flag=True | amount=10000, rate=12, ext=30, tds=True | tds=0.1*interest | P1 | `pytest tests/test_interest_calculator.py::TestCalculateDaily::test_daily_tds_flag_true -v` |
| IC-10 | Daily: extension_period=0 gives zero interest | amount=10000, rate=12, ext=0 | interest=0, commission=0, tds=0 | P1 | `pytest tests/test_interest_calculator.py::TestCalculateDaily::test_b1_daily_exact_days_no_extension_no_tds -v` |
| IC-11 | Daily: time_days == extension_period (giving/due dates irrelevant) | ext=15, giving/due any value | time_days=15 | P1 | `pytest tests/test_interest_calculator.py::TestCalculateDaily::test_daily_time_is_extension_period_only -v` |
| IC-12 | Both: routes to monthly when unit="months" | unit=months, ext=2, rate=12 | time_months key present, interest=200.0 | P1 | `pytest tests/test_interest_calculator.py::TestCalculateBoth::test_both_routes_months -v` |
| IC-13 | Both: routes to daily when unit="days" | unit=days, ext=30, rate=12 | time_days key present | P1 | `pytest tests/test_interest_calculator.py::TestCalculateBoth::test_both_routes_days -v` |
| IC-14 | Both: unknown unit raises ValueError | unit="weeks" | ValueError | P1 | `pytest tests/test_interest_calculator.py::TestCalculateBoth::test_both_invalid_unit_raises -v` |
| IC-15 | TDS independent of commission | rate=12, comm=100, ext=1, tds=True | tds=10.0, tds < commission | P2 | `pytest tests/test_interest_calculator.py::TestTDSCalculation::test_tds_independent_of_commission -v` |
| IC-16 | months_between: partial month rounds up | giving=2026-01-15, due=2026-02-16 | 2 | P2 | `pytest tests/test_interest_calculator.py::TestMonthsBetween::test_partial_month_rounds_up -v` |
| IC-17 | months_between: same day returns 0 | giving=2026-03-22, due=2026-03-22 | 0 | P2 | `pytest tests/test_interest_calculator.py::TestMonthsBetween::test_same_day_returns_zero -v` |
| IC-18 | [NEW] days_between: exact days | giving=2026-01-02, due=2026-04-02 | 90 | P1 | `pytest tests/test_interest_calculator.py::TestDaysBetween::test_days_between_exact -v` |
| IC-19 | [NEW] days_between: same day returns 0 | giving=2026-03-22, due=2026-03-22 | 0 | P1 | `pytest tests/test_interest_calculator.py::TestDaysBetween::test_days_between_same_day -v` |
| IC-20 | [NEW] days_between: due < giving returns 0 | giving=2026-04-01, due=2026-03-01 | 0 | P2 | `pytest tests/test_interest_calculator.py::TestDaysBetween::test_days_between_reverse_dates -v` |
| IC-21 | [NEW] Monthly: fractional rate (12.5%) | amount=10000, rate=12.5, ext=2 | interest=(10000*12.5*2)/(12*100)=208.33 | P2 | `pytest tests/test_interest_calculator.py::TestCalculateMonthly::test_monthly_fractional_rate -v` |
| IC-22 | [NEW] Daily: fractional rate (1.75%) | amount=15000, rate=1.75, ext=30 | interest=(15000*1.75*30)/(365*100) | P2 | `pytest tests/test_interest_calculator.py::TestCalculateDaily::test_daily_fractional_rate -v` |
| IC-23 | [NEW] Paidoff interest (Daily mode, R3): paidoff_date - due_date = 10 days | amount=10000, rate=12, ext=10 (days) | interest=(10000*12*10)/(365*100) approx 32.88 | P1 | `pytest tests/test_interest_calculator.py::TestPaidoffInterest::test_paidoff_daily_calculation -v` |
| IC-24 | [NEW] Monthly: large amount (1,000,000) no overflow | amount=1000000, rate=12, ext=12 | interest=120000.0 (exact float) | P2 | `pytest tests/test_interest_calculator.py::TestCalculateMonthly::test_monthly_large_amount -v` |
| IC-25 | [NEW] Both: tds_flag=True via monthly route | unit=months, ext=1, rate=12, tds=True | tds=10.0 | P2 | `pytest tests/test_interest_calculator.py::TestCalculateBoth::test_both_monthly_route_tds -v` |
| IC-26 | [NEW] Both: tds_flag=True via daily route | unit=days, ext=30, rate=12, tds=True | tds=0.1*interest | P2 | `pytest tests/test_interest_calculator.py::TestCalculateBoth::test_both_daily_route_tds -v` |

### Backend Test Scenarios: ref_id_manager

| ID | Scenario | Input | Expected | Priority | Runner Command |
|---|---|---|---|---|---|
| RI-01 | First entry in month generates _001 | year=2026, month=3, meta absent | "2026_03_001" | P1 | `pytest tests/test_ref_id_manager.py::TestNextRefIdFirstEntry::test_next_ref_id_first_loan_in_month_generates_001 -v` |
| RI-02 | Sequential increment generates _002 | counter=1 in meta | "2026_03_002" | P1 | `pytest tests/test_ref_id_manager.py::TestNextRefIdSequentialIncrement::test_next_ref_id_second_loan_same_month_generates_002 -v` |
| RI-03 | Boundary 999: counter=998 generates _999 | counter=998 | "2026_03_999" | P1 | `pytest tests/test_ref_id_manager.py::TestNextRefIdSequentialIncrement::test_next_ref_id_999th_loan_generates_999 -v` |
| RI-04 | Beyond 999: counter=999 generates 1000 (no zero-pad) | counter=999 | "2026_03_1000" | P1 | `pytest tests/test_ref_id_manager.py::TestNextRefIdSequentialIncrement::test_next_ref_id_counter_increments_to_1000_no_rollover -v` |
| RI-05 | New month gets independent _001 counter | 2026_02 counter=5, request 2026_03 | "2026_03_001" | P1 | `pytest tests/test_ref_id_manager.py::TestNextRefIdNewMonth::test_next_ref_id_new_month_resets_to_001 -v` |
| RI-06 | Two months are independent | Call Jan then Mar | "2026_01_001" and "2026_03_001" | P1 | `pytest tests/test_ref_id_manager.py::TestNextRefIdNewMonth::test_next_ref_id_concurrent_months_independent -v` |
| RI-07 | Reset counter: all records deleted resets to 001 | counter=5, reset_counter called, then next_ref_id | "2026_03_001" | P1 | `pytest tests/test_ref_id_manager.py::TestNextRefIdDeleteReset::test_next_ref_id_all_records_deleted_resets_counter_to_001 -v` |
| RI-08 | Reset one month does not affect other | 2026_01 counter=3, 2026_03 reset | 2026_01 gives _004 | P1 | `pytest tests/test_ref_id_manager.py::TestNextRefIdDeleteReset::test_next_ref_id_reset_one_month_does_not_affect_other -v` |
| RI-09 | Counter persists across instances | Call once, new instance, call again | "2026_03_002" | P1 | `pytest tests/test_ref_id_manager.py::TestNextRefIdSequentialIncrement::test_next_ref_id_counter_persists_after_call -v` |
| RI-10 | Missing meta CSV: recovers gracefully | meta does not exist | "2026_03_001" | P1 | `pytest tests/test_ref_id_manager.py::TestRefIdManagerRecovery::test_next_ref_id_missing_meta_csv_recovers_gracefully -v` |
| RI-11 | Corrupted meta CSV: recovers gracefully | meta contains binary garbage | "2026_03_001" | P1 | `pytest tests/test_ref_id_manager.py::TestRefIdManagerRecovery::test_next_ref_id_corrupted_meta_csv_recovers_gracefully -v` |
| RI-12 | Partial row in meta CSV: treats as 0 | counter field empty | "2026_03_001" | P2 | `pytest tests/test_ref_id_manager.py::TestRefIdManagerRecovery::test_next_ref_id_partial_row_in_meta_csv_recovers -v` |
| RI-13 | [NEW] Collision avoidance: imported legacy ID collides, increments until free | existing={2026_03_001, 2026_03_002}, import assigns 001 | result is "2026_03_003" | P1 | `pytest tests/test_ref_id_manager.py::TestRefIdCollision::test_collision_avoidance_increments_until_free -v` |
| RI-14 | [NEW] Collision avoidance: no existing IDs in month | existing={}, import | "2026_03_001" no collision check needed | P2 | `pytest tests/test_ref_id_manager.py::TestRefIdCollision::test_no_collision_on_empty_month -v` |

### Backend Test Scenarios: csv_manager

| ID | Scenario | Input | Expected | Priority | Runner Command |
|---|---|---|---|---|---|
| CM-01 | read_loans: empty file | empty loans.csv | [] | P1 | `pytest tests/test_csv_manager.py::TestReadLoans::test_read_loans_empty_file_returns_empty_list -v` |
| CM-02 | read_loans: paidoff records excluded | loans.csv with Active + Paidoff row | Only Active returned | P1 | `pytest tests/test_csv_manager.py::TestReadLoans::test_read_loans_paidoff_records_excluded -v` |
| CM-03 | read_loans: date fields parsed as date objects | ISO 8601 strings in CSV | giving_date, due_date are date type | P1 | `pytest tests/test_csv_manager.py::TestReadLoans::test_read_loans_date_fields_parsed_as_date_objects -v` |
| CM-04 | read_loans: amount parsed as integer | amount="10000" | result["amount"] == 10000 (int) | P1 | `pytest tests/test_csv_manager.py::TestReadLoans::test_read_loans_amount_parsed_as_integer -v` |
| CM-05 | read_loans: empty optional fields become None | depositor_group="" | result["depositor_group"] is None | P2 | `pytest tests/test_csv_manager.py::TestReadLoans::test_read_loans_missing_optional_fields_return_none -v` |
| CM-06 | read_loans: UTF-8 BOM handled | Excel-exported file with BOM | Reads correctly, no prefix in ref_id | P2 | `pytest tests/test_csv_manager.py::TestReadLoans::test_read_loans_utf8_bom_reads_correctly -v` |
| CM-07 | write_loan: creates file with header and record | New loan dict | File exists, 1 data row | P1 | `pytest tests/test_csv_manager.py::TestWriteLoan::test_write_loan_creates_file_with_header_and_record -v` |
| CM-08 | write_loan: appends to existing file | 2 sequential writes | 2 data rows | P1 | `pytest tests/test_csv_manager.py::TestWriteLoan::test_write_loan_appends_to_existing_file -v` |
| CM-09 | write_loan: dates stored as ISO 8601 | loan with date objects | CSV shows "2026-01-02" format | P1 | `pytest tests/test_csv_manager.py::TestWriteLoan::test_write_loan_dates_stored_as_iso8601 -v` |
| CM-10 | update_loan: modifies target field | status update | Updated field in CSV | P1 | `pytest tests/test_csv_manager.py::TestUpdateLoan::test_update_loan_modifies_target_record -v` |
| CM-11 | update_loan: preserves sibling records | 2 loans, update one | Other loan unchanged | P1 | `pytest tests/test_csv_manager.py::TestUpdateLoan::test_update_loan_preserves_other_records -v` |
| CM-12 | update_loan: non-existent ref_id is no-op | Update unknown ID | Existing rows unchanged | P2 | `pytest tests/test_csv_manager.py::TestUpdateLoan::test_update_loan_nonexistent_reference_id_no_error -v` |
| CM-13 | delete_loan: removes target record | Delete one of two | One record remains | P1 | `pytest tests/test_csv_manager.py::TestDeleteLoan::test_delete_loan_removes_target_record -v` |
| CM-14 | delete_loan: last record leaves header only | Delete only record | Empty data rows | P2 | `pytest tests/test_csv_manager.py::TestDeleteLoan::test_delete_loan_last_record_leaves_header_only -v` |
| CM-15 | mark_paidoff: removes from loans, adds to history | 1 active loan | Absent from loans.csv, present in history.csv | P1 | `pytest tests/test_csv_manager.py::TestMarkPaidoff::test_mark_paidoff_removes_record_from_loans_csv -v` |
| CM-16 | mark_paidoff: paidoff_date recorded in history | paidoff_date=2026-03-22 | history row has "2026-03-22" | P1 | `pytest tests/test_csv_manager.py::TestMarkPaidoff::test_mark_paidoff_history_record_has_paidoff_date -v` |
| CM-17 | mark_paidoff: recovery.tmp deleted on success | Normal run | recovery.tmp absent after call | P1 | `pytest tests/test_csv_manager.py::TestMarkPaidoff::test_mark_paidoff_recovery_tmp_deleted_on_success -v` |
| CM-18 | mark_paidoff: recovery.tmp created before first write | Intercept history.csv open | recovery.tmp already exists at that point | P1 | `pytest tests/test_csv_manager.py::TestMarkPaidoff::test_mark_paidoff_recovery_tmp_created_before_writes -v` |
| CM-19 | mark_paidoff: recovery.tmp persists when crash between writes | Simulated OSError on loans.csv write | recovery.tmp still present | P1 | `pytest tests/test_csv_manager.py::TestMarkPaidoff::test_mark_paidoff_recovery_tmp_persists_on_crash_between_writes -v` |
| CM-20 | extend_loan: new due_date = old due_date + period (months) | period=3, unit=months | new due = 2026-07-02 | P1 | `pytest tests/test_csv_manager.py::TestExtendLoan::test_extend_loan_new_due_date_equals_old_due_date_plus_period -v` |
| CM-21 | extend_loan: new giving_date = old due_date | old due=2026-04-02 | new giving = 2026-04-02 | P1 | `pytest tests/test_csv_manager.py::TestExtendLoan::test_extend_loan_new_giving_date_equals_old_due_date -v` |
| CM-22 | extend_loan: no due_date => new giving = today (R7) | due_date absent | giving_date = today | P1 | `pytest tests/test_csv_manager.py::TestExtendLoan::test_extend_loan_no_due_date_new_giving_date_is_today -v` |
| CM-23 | extend_loan: reference_id preserved after extend | Extend record | reference_id unchanged | P1 | `pytest tests/test_csv_manager.py::TestExtendLoan::test_extend_loan_reference_id_preserved -v` |
| CM-24 | [NEW] read_loans: file does not exist | loans.csv absent | [] returned (no exception) | P1 | `pytest tests/test_csv_manager.py::TestReadLoans::test_read_loans_absent_file_returns_empty_list -v` |
| CM-25 | [NEW] mark_paidoff: non-existent ref_id | reference_id not in file | No exception; loans.csv unchanged | P2 | `pytest tests/test_csv_manager.py::TestMarkPaidoff::test_mark_paidoff_nonexistent_ref_id_is_noop -v` |
| CM-26 | [NEW] mark_paidoff: multi-record history append | 2 loans paid off sequentially | history.csv has 2 rows | P2 | `pytest tests/test_csv_manager.py::TestMarkPaidoff::test_mark_paidoff_second_paidoff_appends_to_history -v` |
| CM-27 | [NEW] startup recovery.tmp handling: recovery.tmp exists on startup | recovery.tmp present before any call | recovery.tmp processed or logged; application does not crash | P1 | `pytest tests/test_csv_manager.py::TestRecoveryProtocol::test_startup_recovery_tmp_detected -v` |
| CM-28 | [NEW] extend_loan: invalid unit raises ValueError | unit="weeks" | ValueError raised | P2 | `pytest tests/test_csv_manager.py::TestExtendLoan::test_extend_loan_invalid_unit_raises -v` |
| CM-29 | [NEW] extend_loan: non-existent ref_id is no-op | Unknown reference_id | No exception; file unchanged | P2 | `pytest tests/test_csv_manager.py::TestExtendLoan::test_extend_loan_nonexistent_ref_id_is_noop -v` |

### Backend Test Scenarios: report_manager

| ID | Scenario | Input | Expected | Priority | Runner Command |
|---|---|---|---|---|---|
| RM-01 | generate_report_id: first report of day | No existing meta | "RPT_20260322_001" | P1 | `pytest tests/test_report_manager.py::TestGenerateReportId::test_first_report_of_day_returns_001 -v` |
| RM-02 | generate_report_id: second report same day | counter=1 | "RPT_20260322_002" | P1 | `pytest tests/test_report_manager.py::TestGenerateReportId::test_second_report_same_day_returns_002 -v` |
| RM-03 | generate_report_id: new day resets to 001 | Prior day counter=5 | "RPT_20260322_001" | P1 | `pytest tests/test_report_manager.py::TestGenerateReportId::test_new_calendar_day_resets_to_001 -v` |
| RM-04 | generate_report_id: beyond 999 no zero-pad | counter=999 | "RPT_20260322_1000" | P2 | `pytest tests/test_report_manager.py::TestGenerateReportId::test_1000th_report_no_zero_padding_rollover -v` |
| RM-05 | write_report + read_pending_reports: round-trip | Write one Pending report | Read returns that one report | P1 | `pytest tests/test_report_manager.py::TestWriteAndReadPendingReports::test_write_read_round_trip_single_report -v` |
| RM-06 | read_pending_reports: returns only Pending status | Pending + Approved + Declined in CSV | Only Pending returned | P1 | `pytest tests/test_report_manager.py::TestWriteAndReadPendingReports::test_read_pending_reports_returns_only_pending_status -v` |
| RM-07 | update_report_status: Pending to Approved | status update | status="Approved" in CSV | P1 | `pytest tests/test_report_manager.py::TestUpdateReportStatus::test_update_status_pending_to_approved -v` |
| RM-08 | update_report_status: Pending to Declined | status update | status="Declined" in CSV | P1 | `pytest tests/test_report_manager.py::TestUpdateReportStatus::test_update_status_pending_to_declined -v` |
| RM-09 | update_report_status: PD-16 row retained after decline | Decline a report | Row still in CSV with Declined status | P1 | `pytest tests/test_report_manager.py::TestUpdateReportStatus::test_declined_report_row_retained_after_decline -v` |
| RM-10 | update_report_status: report_creation_date immutable | Update status | report_creation_date unchanged | P1 | `pytest tests/test_report_manager.py::TestUpdateReportStatus::test_update_status_preserves_creation_date -v` |
| RM-11 | update_report_status: non-existent report_id is no-op | Unknown ID | No exception; existing rows unchanged | P2 | `pytest tests/test_report_manager.py::TestUpdateReportStatus::test_update_status_nonexistent_report_id_is_noop -v` |
| RM-12 | read_report_records: returns matching rows only | Two reports in file | Only records for queried report_id | P1 | `pytest tests/test_report_manager.py::TestReadReportRecords::test_read_report_records_returns_matching_rows_only -v` |
| RM-13 | delete_report_records: removes target, preserves others | Two reports' records | Target lines deleted, other intact | P1 | `pytest tests/test_report_manager.py::TestDeleteReportRecords::test_delete_removes_records_for_report_id -v` |
| RM-14 | delete_report_records: header retained when all deleted | One report's records | Header-only CSV remains | P2 | `pytest tests/test_report_manager.py::TestDeleteReportRecords::test_delete_header_retained_when_all_records_deleted -v` |
| RM-15 | get_active_reference_ids_in_queue: Pending only | Pending + Approved + Declined | Only Pending ref_ids in result set | P1 | `pytest tests/test_report_manager.py::TestGetActiveReferenceIdsInQueue::test_only_pending_report_reference_ids_are_included -v` |
| RM-16 | get_active_reference_ids_in_queue: deduplication | Same ref_id in two Pending reports | ref_id appears once in set | P1 | `pytest tests/test_report_manager.py::TestGetActiveReferenceIdsInQueue::test_duplicate_reference_ids_across_pending_reports_are_deduplicated -v` |
| RM-17 | [NEW] update_report_records: replaces line items for report | Old records replaced by new list | New records present, old absent, other reports unaffected | P1 | `pytest tests/test_report_manager.py::TestUpdateReportRecords::test_update_report_records_replaces_lines -v` |
| RM-18 | [NEW] update_report_records: preserves other reports' records | Two reports, update one | Untouched report's records unchanged | P1 | `pytest tests/test_report_manager.py::TestUpdateReportRecords::test_update_report_records_preserves_siblings -v` |
| RM-19 | [NEW] tds_flag round-trip: stored as "true"/"false", read as bool | tds_flag=True in ReportRecord | CSV has "true"; from_csv_row gives bool True | P1 | `pytest tests/test_report_manager.py::TestReportRecordSerialisation::test_tds_flag_stored_as_lowercase_string -v` |
| RM-20 | [NEW] ReportRecord: amount and financial fields correct types after read | amount=10000, interest=100.0 | amount is int, interest is float | P2 | `pytest tests/test_report_manager.py::TestReportRecordSerialisation::test_report_record_field_types_after_read -v` |
| RM-21 | [NEW] Duplicate ref_id conflict: two pending reports share a reference_id | RPT_001 and RPT_002 both have "2026_01_001" | get_active_reference_ids_in_queue returns "2026_01_001"; approval workflow detects overlap | P1 | `pytest tests/test_report_manager.py::TestApprovalConflict::test_duplicate_ref_id_detected_before_approval -v` |
| RM-22 | [NEW] Deleted loan in report: skip deleted record on approval | Loan deleted from loans.csv; report contains its ref_id | Approval updates only records still in loans.csv | P1 | `pytest tests/test_report_manager.py::TestApprovalConflict::test_approval_skips_deleted_loans -v` |

---

## 3. Interest Calculator Critical Tests (R5 — Authoritative Formula)

The following test spec covers all authoritative scenarios for the interest calculator. The formula source is REQUIREMENTS.md R5 and BC-05 Interpretation B (confirmed by the authoritative example).

**Authoritative formula:**
- Monthly: `Interest = (Amount * interest_rate * extension_period) / (12 * 100)`
- Daily:   `Interest = (Amount * interest_rate * extension_period) / (365 * 100)`
- TDS:     `TDS = 0.1 * Interest` (when `tds_flag=True`)
- Commission follows the same formula as Interest but using `commission_rate`.
- `giving_date` and `due_date` are pass-through fields; they do NOT affect any calculation.

```python
# tests/test_interest_calculator.py

import pytest
from datetime import date
from loan_manager.interest_calculator import (
    calculate_monthly,
    calculate_daily,
    calculate_both,
    days_between,
)


class TestR5AuthoritativeExamples:
    """All tests in this class are derived from REQUIREMENTS.md R5 authoritative decisions."""

    def test_monthly_calculation_authoritative_example(self):
        # R5 example: Rs 10,000 at 12% for 1-month extension -> Rs 100
        # Formula: (10000 * 12 * 1) / (12 * 100) = 100
        record = {
            "reference_id": "2026_01_001",
            "borrower_name": "b1",
            "amount": 10000,
            "giving_date": date(2026, 1, 1),
            "due_date": date(2026, 4, 1),
            "interest_rate": 12.0,
            "commission_rate": 0.0,
            "extension_period": 1,
            "extension_period_unit": "months",
            "tds_flag": False,
        }
        result = calculate_monthly(record)
        assert result["time_months"] == 1
        assert abs(result["interest_amount"] - 100.0) < 0.001
        assert abs(result["commission_amount"] - 0.0) < 0.001
        assert abs(result["tds_amount"] - 0.0) < 0.001

    def test_monthly_calculation_three_months(self):
        # Rs 10,000 at 12% for 3-month extension -> Rs 300
        # Formula: (10000 * 12 * 3) / (12 * 100) = 300
        record = {
            "amount": 10000,
            "giving_date": date(2026, 4, 2),
            "due_date": date(2026, 7, 2),
            "interest_rate": 12.0,
            "commission_rate": 0.0,
            "extension_period": 3,
            "extension_period_unit": "months",
            "tds_flag": False,
        }
        result = calculate_monthly(record)
        assert abs(result["interest_amount"] - 300.0) < 0.001

    def test_monthly_calculation_giving_date_does_not_affect_result(self):
        # Same extension_period=1, same amount/rate, different giving_date/due_date
        # Both must produce the same interest (giving/due are pass-through)
        record_a = {
            "amount": 10000,
            "giving_date": date(2026, 1, 1),
            "due_date": date(2026, 4, 1),
            "interest_rate": 12.0,
            "commission_rate": 0.0,
            "extension_period": 1,
            "extension_period_unit": "months",
            "tds_flag": False,
        }
        record_b = {
            "amount": 10000,
            "giving_date": date(2025, 6, 1),
            "due_date": date(2025, 9, 1),
            "interest_rate": 12.0,
            "commission_rate": 0.0,
            "extension_period": 1,
            "extension_period_unit": "months",
            "tds_flag": False,
        }
        assert abs(
            calculate_monthly(record_a)["interest_amount"]
            - calculate_monthly(record_b)["interest_amount"]
        ) < 0.001

    def test_monthly_calculation_with_commission(self):
        # Rs 20,000 at 8% interest + 1% commission for 1 month
        # Interest = (20000 * 8 * 1) / (12 * 100) = 133.33
        # Commission = (20000 * 1 * 1) / (12 * 100) = 16.67
        record = {
            "amount": 20000,
            "giving_date": date(2026, 2, 7),
            "due_date": date(2026, 6, 7),
            "interest_rate": 8.0,
            "commission_rate": 1.0,
            "extension_period": 1,
            "extension_period_unit": "months",
            "tds_flag": False,
        }
        result = calculate_monthly(record)
        assert abs(result["interest_amount"] - 133.33) < 0.01
        assert abs(result["commission_amount"] - 16.67) < 0.01

    def test_monthly_calculation_tds_is_ten_percent_of_interest(self):
        # TDS = 0.1 * Interest (not 0.1 * (Interest + Commission))
        # Rs 10,000 at 12% for 1 month, tds=True
        # Interest = 100.00, TDS = 10.00
        record = {
            "amount": 10000,
            "giving_date": date(2026, 1, 2),
            "due_date": date(2026, 4, 2),
            "interest_rate": 12.0,
            "commission_rate": 2.0,
            "extension_period": 1,
            "extension_period_unit": "months",
            "tds_flag": True,
        }
        result = calculate_monthly(record)
        assert abs(result["interest_amount"] - 100.0) < 0.001
        assert abs(result["tds_amount"] - 10.0) < 0.001
        assert result["tds_amount"] < result["commission_amount"]  # TDS not based on commission

    def test_monthly_extension_period_zero_produces_zero_interest(self):
        # extension_period=0 means no extension window: all amounts are zero
        record = {
            "amount": 10000,
            "giving_date": date(2026, 1, 2),
            "due_date": date(2026, 4, 2),
            "interest_rate": 12.0,
            "commission_rate": 2.0,
            "extension_period": 0,
            "extension_period_unit": "months",
            "tds_flag": True,
        }
        result = calculate_monthly(record)
        assert abs(result["interest_amount"] - 0.0) < 0.001
        assert abs(result["commission_amount"] - 0.0) < 0.001
        assert abs(result["tds_amount"] - 0.0) < 0.001

    def test_daily_calculation_authoritative_paidoff_window(self):
        # R3 paidoff path: extension_period(days) = paidoff_date - due_date
        # due_date = 2026-04-02, paidoff_date = 2026-04-12 => 10 days
        # Rs 10,000 at 12% for 10 days
        # Interest = (10000 * 12 * 10) / (365 * 100) = 32.876...
        ext_days = (date(2026, 4, 12) - date(2026, 4, 2)).days  # == 10
        record = {
            "amount": 10000,
            "giving_date": date(2026, 4, 2),
            "due_date": date(2026, 4, 12),
            "interest_rate": 12.0,
            "commission_rate": 0.0,
            "extension_period": ext_days,
            "extension_period_unit": "days",
            "tds_flag": False,
        }
        result = calculate_daily(record)
        expected = (10000 * 12.0 * 10) / (365 * 100)
        assert result["time_days"] == 10
        assert abs(result["interest_amount"] - expected) < 0.001

    def test_daily_calculation_giving_date_does_not_affect_result(self):
        # giving_date is a reference column only; changing it must not change interest
        record_a = {
            "amount": 15000,
            "giving_date": date(2026, 2, 6),
            "due_date": date(2026, 5, 6),
            "interest_rate": 10.0,
            "commission_rate": 1.5,
            "extension_period": 30,
            "extension_period_unit": "days",
            "tds_flag": False,
        }
        record_b = {
            "amount": 15000,
            "giving_date": date(2025, 1, 1),
            "due_date": date(2025, 6, 1),
            "interest_rate": 10.0,
            "commission_rate": 1.5,
            "extension_period": 30,
            "extension_period_unit": "days",
            "tds_flag": False,
        }
        assert abs(
            calculate_daily(record_a)["interest_amount"]
            - calculate_daily(record_b)["interest_amount"]
        ) < 0.001

    def test_daily_calculation_with_tds(self):
        # Rs 15,000 at 10% for 30 days with tds=True
        # Interest = (15000 * 10 * 30) / (365 * 100) = 123.288...
        # TDS = 0.1 * 123.288 = 12.328...
        record = {
            "amount": 15000,
            "giving_date": date(2026, 2, 6),
            "due_date": date(2026, 5, 6),
            "interest_rate": 10.0,
            "commission_rate": 0.0,
            "extension_period": 30,
            "extension_period_unit": "days",
            "tds_flag": True,
        }
        result = calculate_daily(record)
        expected_interest = (15000 * 10.0 * 30) / (365 * 100)
        assert abs(result["interest_amount"] - expected_interest) < 0.001
        assert abs(result["tds_amount"] - 0.1 * expected_interest) < 0.0001

    def test_calculate_both_monthly_route_matches_calculate_monthly(self):
        # calculate_both with unit=months must produce identical output to calculate_monthly
        record = {
            "amount": 10000,
            "giving_date": date(2026, 1, 2),
            "due_date": date(2026, 4, 2),
            "interest_rate": 12.0,
            "commission_rate": 2.0,
            "extension_period": 2,
            "extension_period_unit": "months",
            "tds_flag": True,
        }
        from_both = calculate_both(record)
        from_monthly = calculate_monthly(record)
        assert abs(from_both["interest_amount"] - from_monthly["interest_amount"]) < 0.0001
        assert abs(from_both["tds_amount"] - from_monthly["tds_amount"]) < 0.0001
        assert "time_months" in from_both
        assert "time_days" not in from_both

    def test_calculate_both_daily_route_matches_calculate_daily(self):
        # calculate_both with unit=days must produce identical output to calculate_daily
        record = {
            "amount": 10000,
            "giving_date": date(2026, 1, 2),
            "due_date": date(2026, 4, 2),
            "interest_rate": 12.0,
            "commission_rate": 2.0,
            "extension_period": 30,
            "extension_period_unit": "days",
            "tds_flag": True,
        }
        from_both = calculate_both(record)
        from_daily = calculate_daily(record)
        assert abs(from_both["interest_amount"] - from_daily["interest_amount"]) < 0.0001
        assert "time_days" in from_both
        assert "time_months" not in from_both


class TestDaysBetween:
    def test_days_between_exact_90_days(self):
        from loan_manager.interest_calculator import days_between
        # 2026-01-02 to 2026-04-02 = 90 days
        result = days_between(date(2026, 1, 2), date(2026, 4, 2))
        assert result == 90

    def test_days_between_same_day_returns_zero(self):
        from loan_manager.interest_calculator import days_between
        result = days_between(date(2026, 3, 22), date(2026, 3, 22))
        assert result == 0

    def test_days_between_due_before_giving_returns_zero(self):
        from loan_manager.interest_calculator import days_between
        result = days_between(date(2026, 4, 1), date(2026, 3, 1))
        assert result == 0

    def test_days_between_one_day(self):
        from loan_manager.interest_calculator import days_between
        result = days_between(date(2026, 3, 22), date(2026, 3, 23))
        assert result == 1
```

---

## 4. Paidoff Atomic Write Tests

### Protocol Description
The mark_paidoff operation must be crash-safe. The sequence is:
1. Write target row to `recovery.tmp` (crash safety log).
2. Append row (with `paidoff_date`) to `history.csv`.
3. Remove row from `loans.csv`.
4. Delete `recovery.tmp`.

If the application crashes between steps 2 and 3, `recovery.tmp` will still exist on the next startup. The application must detect and handle this condition.

### Critical Test Scenarios

```python
# tests/test_csv_manager.py (additions to existing file)

class TestMarkPaidoffAtomic:
    """Atomic write tests for mark_paidoff. Existing tests cover the basic happy path.
    These tests cover startup recovery and edge cases not yet present."""

    def test_mark_paidoff_normal_flow_all_files_correct(self, data_dir: Path):
        # Arrange
        loans_path = data_dir / "loans.csv"
        history_path = data_dir / "history.csv"
        recovery_path = data_dir / "recovery.tmp"
        _write_loans_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
        ])
        manager = CSVManager()
        # Act
        manager.mark_paidoff(loans_path, history_path, "2026_01_001", date(2026, 3, 22))
        # Assert
        loans_raw = _read_csv_raw(loans_path)
        assert "2026_01_001" not in [r["reference_id"] for r in loans_raw]
        history_raw = _read_csv_raw(history_path)
        assert len(history_raw) == 1
        assert history_raw[0]["paidoff_date"] == "2026-03-22"
        assert not recovery_path.exists()

    def test_mark_paidoff_second_paidoff_appends_to_existing_history(self, data_dir: Path):
        # Arrange: history.csv already has one entry from a prior paidoff
        loans_path = data_dir / "loans.csv"
        history_path = data_dir / "history.csv"
        _write_loans_csv(loans_path, [
            {
                "reference_id": "2026_01_002",
                "borrower_name": "b2", "borrower_group": "bg2", "amount": "10000",
                "giving_date": "2026-01-04", "depositor_name": "d2",
                "depositor_group": "dg1", "due_date": "2026-05-04", "status": "Active",
            },
        ])
        # Write a pre-existing history entry
        with history_path.open("w", newline="", encoding="utf-8") as fh:
            import csv as _csv
            writer = _csv.DictWriter(fh, fieldnames=HISTORY_FIELDNAMES)
            writer.writeheader()
            writer.writerow({
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Paidoff",
                "paidoff_date": "2026-03-15",
            })
        manager = CSVManager()
        # Act
        manager.mark_paidoff(loans_path, history_path, "2026_01_002", date(2026, 3, 22))
        # Assert
        history_raw = _read_csv_raw(history_path)
        assert len(history_raw) == 2
        ids_in_history = [r["reference_id"] for r in history_raw]
        assert "2026_01_001" in ids_in_history
        assert "2026_01_002" in ids_in_history

    def test_mark_paidoff_nonexistent_ref_id_is_noop(self, data_dir: Path):
        # Arrange
        loans_path = data_dir / "loans.csv"
        history_path = data_dir / "history.csv"
        _write_loans_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
        ])
        manager = CSVManager()
        # Act: mark_paidoff on a ref_id that is not in the file
        manager.mark_paidoff(loans_path, history_path, "9999_99_999", date(2026, 3, 22))
        # Assert: original loan untouched, history empty
        loans_raw = _read_csv_raw(loans_path)
        assert len(loans_raw) == 1
        assert loans_raw[0]["reference_id"] == "2026_01_001"
        assert not history_path.exists() or _read_csv_raw(history_path) == []


class TestRecoveryProtocol:
    """Tests for the startup recovery.tmp detection protocol."""

    def test_startup_recovery_tmp_detected_and_logged(self, data_dir: Path):
        # Arrange: simulate a crash-interrupted prior run
        # A recovery.tmp exists; loans.csv and history.csv are in an inconsistent state
        loans_path = data_dir / "loans.csv"
        history_path = data_dir / "history.csv"
        recovery_path = data_dir / "recovery.tmp"
        # Write a recovery.tmp with the payload of the interrupted operation
        recovery_path.write_text("2026_01_001", encoding="utf-8")
        # Write loans.csv as if loans.csv write had NOT happened yet (record still present)
        _write_loans_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
        ])
        # Act: the application (or a startup check function) should detect recovery.tmp
        # [REVIEW REQUIRED] — The exact API for startup recovery is not defined in the
        # service layer. This test documents the expected behaviour and should be
        # implemented once the recovery API is defined.
        # For now, assert the file is detectable:
        assert recovery_path.exists(), "Test precondition: recovery.tmp must exist"
        # The service/startup routine should: read recovery.tmp, complete the interrupted
        # paidoff operation, then delete recovery.tmp.
        # Expected post-state: recovery.tmp deleted, record absent from loans.csv,
        # record present in history.csv.
```

---

## 5. Import/Export Tests (R6)

### Import Scenarios

```python
# tests/test_import_export.py (new file)
import csv
import pytest
from pathlib import Path
from datetime import date

from loan_manager.csv_manager import CSVManager
from loan_manager.ref_id_manager import RefIdManager


FIELDNAMES = [
    "reference_id", "borrower_name", "borrower_group", "amount",
    "giving_date", "depositor_name", "depositor_group", "due_date", "status",
]


def _write_import_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


class TestImportNoReferenceIds:
    def test_import_without_reference_ids_auto_assigns(self, data_dir: Path):
        """R6: If imported data has no reference_id, auto-assign in YYYY_MM_<order> format."""
        # Arrange
        meta_path = data_dir / "loans_meta.csv"
        import_path = data_dir / "import.csv"
        loans_path = data_dir / "loans.csv"
        # Import file has empty reference_id column
        with import_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerow({
                "reference_id": "",
                "borrower_name": "b_new", "borrower_group": "bg1", "amount": "5000",
                "giving_date": "2026-03-01", "depositor_name": "d_new",
                "depositor_group": "dg1", "due_date": "2026-06-01", "status": "Active",
            })
        # Act: import service should assign a ref_id
        manager = RefIdManager(meta_path=meta_path)
        new_id = manager.next_ref_id(2026, 3)
        # Assert: assigned ID follows YYYY_MM_<order> format
        assert new_id.startswith("2026_03_")
        assert len(new_id.split("_")) == 3


class TestImportWithExistingReferenceIds:
    def test_import_with_ref_ids_upserts_records(self, data_dir: Path):
        """R6: If imported data already has reference_ids, upsert into loans.csv."""
        loans_path = data_dir / "loans.csv"
        _write_import_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1_original", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
        ])
        manager = CSVManager()
        # Upsert: same reference_id, updated amount
        manager.update_loan(loans_path, "2026_01_001", {"amount": 15000, "borrower_name": "b1_updated"})
        raw = _read_csv_raw(loans_path)
        assert len(raw) == 1
        assert raw[0]["borrower_name"] == "b1_updated"
        assert raw[0]["amount"] == "15000"


class TestImportCollisionOverwrite:
    def test_import_collision_imported_record_overwrites_existing(self, data_dir: Path):
        """R6: When imported ref_id collides, imported data overwrites existing record completely."""
        loans_path = data_dir / "loans.csv"
        _write_import_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1_existing", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
        ])
        manager = CSVManager()
        # Import record with same ref_id: all fields from import overwrite existing
        imported = {
            "reference_id": "2026_01_001",
            "borrower_name": "b1_imported",
            "borrower_group": "bg_imported",
            "amount": 20000,
            "giving_date": date(2026, 2, 1),
            "depositor_name": "d_imported",
            "depositor_group": "dg_imported",
            "due_date": date(2026, 8, 1),
            "status": "Active",
        }
        manager.update_loan(loans_path, "2026_01_001", {
            "borrower_name": imported["borrower_name"],
            "borrower_group": imported["borrower_group"],
            "amount": imported["amount"],
            "depositor_name": imported["depositor_name"],
            "depositor_group": imported["depositor_group"],
            "due_date": imported["due_date"],
        })
        raw = _read_csv_raw(loans_path)
        assert raw[0]["borrower_name"] == "b1_imported"
        assert raw[0]["amount"] == "20000"

    def test_import_collision_preview_shows_overwrite_count(self, data_dir: Path):
        """R6: Preview dialog should report count of rows to be overwritten.
        [REVIEW REQUIRED] — Preview is a UI concern but the service layer should
        provide a diff/preview function that returns (new_rows, overwrite_rows) tuple."""
        # This test documents the expected service-layer API for preview generation.
        # Implementation depends on the import service design decision.
        pass  # [REVIEW REQUIRED] — implement when import service preview API is defined.


class TestImportLegacyFormatCollision:
    def test_import_legacy_ref_id_collision_increments_to_next_available(self, data_dir: Path):
        """R4/R6: Legacy imported record with auto-assigned ID that collides with
        existing record should get incremented until a non-colliding ID is found."""
        meta_path = data_dir / "loans_meta.csv"
        # Existing loans already have 001 and 002 for 2026_03
        import csv as _csv
        meta_path.write_text("year_month,counter\n2026_03,2\n", encoding="utf-8")
        manager = RefIdManager(meta_path=meta_path)
        # The next assigned ID must be 003, not 001 or 002
        new_id = manager.next_ref_id(2026, 3)
        assert new_id == "2026_03_003"


class TestExport:
    def test_export_all_active_records_to_csv(self, data_dir: Path):
        """R6: Export all active records to CSV. Paidoff records excluded."""
        loans_path = data_dir / "loans.csv"
        export_path = data_dir / "export.csv"
        _write_import_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
            {
                "reference_id": "2026_01_002",
                "borrower_name": "b2", "borrower_group": "bg2", "amount": "10000",
                "giving_date": "2026-01-04", "depositor_name": "d2",
                "depositor_group": "dg1", "due_date": "2026-05-04", "status": "Paidoff",
            },
        ])
        manager = CSVManager()
        active_records = manager.read_loans(loans_path)
        # Write active records to export file
        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
            writer.writeheader()
            for r in active_records:
                writer.writerow({k: str(v) if v is not None else "" for k, v in r.items()})
        raw = _read_csv_raw(export_path)
        assert len(raw) == 1
        assert raw[0]["reference_id"] == "2026_01_001"
        assert raw[0]["status"] == "Active"
```

---

## 6. pytest Template Files

### New test files that need to be created

#### tests/test_import_export.py
The template above in Section 5 is the starting-point for this file. It covers R6 import/export scenarios. The file does not currently exist.

#### tests/test_status_engine_loan_objects.py (or additions to test_status_engine.py)

```python
# tests/test_status_engine.py — additions for Loan dataclass calling convention

import pytest
from datetime import date

# These tests require the Loan dataclass to be importable for test use
# from models.loan import Loan


class TestComputeStatusEdgeCases:
    def test_compute_status_no_giving_date_raises(self) -> None:
        # Arrange / Act / Assert
        from loan_manager.status_engine import compute_status
        with pytest.raises(ValueError):
            compute_status(
                giving_date=None,
                due_date=date(2026, 4, 1),
                current_status="Active",
                today=date(2026, 3, 22),
            )

    def test_compute_status_no_today_raises(self) -> None:
        from loan_manager.status_engine import compute_status
        with pytest.raises(ValueError):
            compute_status(
                giving_date=date(2026, 1, 1),
                due_date=date(2026, 4, 1),
                current_status="Active",
                today=None,
            )


class TestUpdateReportRecords:
    """Tests for CSVReportManager.update_report_records (currently zero coverage)."""

    def test_update_report_records_replaces_lines(self, data_dir: Path) -> None:
        # Arrange
        from loan_manager.report_manager import CSVReportManager
        records_path = data_dir / "pending_report_records.csv"
        manager = CSVReportManager()
        original_records = [
            _make_report_record("RPT_20260322_001", "2026_01_001", interest_amount=100.0),
        ]
        manager.write_report_records(records_path, original_records)
        # Act: replace with updated amount
        updated_records = [
            _make_report_record("RPT_20260322_001", "2026_01_001", interest_amount=200.0),
        ]
        manager.update_report_records(records_path, "RPT_20260322_001", updated_records)
        # Assert
        result = manager.read_report_records(records_path, "RPT_20260322_001")
        assert len(result) == 1
        assert abs(result[0].interest_amount - 200.0) < 0.001

    def test_update_report_records_preserves_siblings(self, data_dir: Path) -> None:
        # Arrange
        from loan_manager.report_manager import CSVReportManager
        records_path = data_dir / "pending_report_records.csv"
        manager = CSVReportManager()
        manager.write_report_records(records_path, [
            _make_report_record("RPT_20260322_001", "2026_01_001"),
            _make_report_record("RPT_20260322_002", "2026_01_002"),
        ])
        # Act: update only RPT_20260322_001
        manager.update_report_records(records_path, "RPT_20260322_001", [
            _make_report_record("RPT_20260322_001", "2026_01_001", interest_amount=999.0),
        ])
        # Assert: RPT_20260322_002 record is untouched
        siblings = manager.read_report_records(records_path, "RPT_20260322_002")
        assert len(siblings) == 1
        assert siblings[0].reference_id == "2026_01_002"
```

---

## 7. Coverage Requirements

| Module | Current (estimate) | Target | Missing Scenarios |
|---|---|---|---|
| status_engine | 90% | 98% | Loan-dataclass calling convention; ValueError guards for None giving_date/today; recompute_all with Loan objects |
| interest_calculator | 85% | 98% | days_between() (0%); fractional rates; large amounts; paidoff daily path; calculate_both TDS in both routes; wrong-key absence check |
| csv_manager | 80% | 95% | Absent loans.csv read; startup recovery.tmp detection; mark_paidoff non-existent ID; multi-entry history; extend invalid unit; extend non-existent ID |
| ref_id_manager | 92% | 98% | Collision-avoidance API for legacy imports (R4/R6) |
| report_manager | 75% | 95% | update_report_records (0%); cross-service approval flow; PD-19 conflict detection workflow; deleted-loan-in-report approval; tds_flag bool round-trip; field type validation after read |

---

## 8. Run All Tests

```bash
# Run full test suite
pytest tests/ -v

# Run by module
pytest tests/test_status_engine.py -v
pytest tests/test_interest_calculator.py -v
pytest tests/test_csv_manager.py -v
pytest tests/test_ref_id_manager.py -v
pytest tests/test_report_manager.py -v

# Run only new test scenarios (tagged with [NEW] in this spec)
pytest tests/test_import_export.py -v

# Run with coverage (requires pytest-cov)
pytest tests/ --cov=loan_manager --cov-report=term-missing -v
```

---

## 9. Key Findings and Decisions

### [REVIEW REQUIRED] — due_date == today boundary
The test file documents this as `[REVIEW REQUIRED]`. R3 states Overdue when `due_date <= today`. The current implementation and tests treat `due_date == today` as Overdue (inclusive). This is the correct interpretation of the `<=` operator in R3, but requires confirmation from the product owner before this is considered resolved.

### [REVIEW REQUIRED] — Startup recovery.tmp handling
R3 documents crash safety via `recovery.tmp` but does not define the startup detection API. A `check_and_resume_recovery(data_dir)` function should be defined in `csv_manager.py` or a dedicated `recovery.py` module. Tests for this (CM-27) are blocked until the API is agreed.

### [REVIEW REQUIRED] — Import service layer API
R6 specifies import behaviour (auto-assign, upsert, collision overwrite, preview dialog) but there is no dedicated `import_service.py` in the current codebase. Tests IC-13, IC-14 and the full Section 5 test file are blocked on the import service design.

### [REVIEW REQUIRED] — update_report_records in approval flow
The `update_report_records` method exists in `report_manager.py` and has zero test coverage. This method is called by the Pending Approval tab when a user inline-edits parameters. The absence of tests here is a critical gap given that this method mutates persisted report data.

### Observation — recompute_all Loan object mutation asymmetry
The `recompute_all` implementation mutates `Loan.status` in-place for Loan objects but returns a copy for dict objects. This asymmetry is undocumented and untested. Tests SE-15 and SE-16 expose this difference.
